from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.maintenance import MaintenanceGate
from app.database.repositories import leaderboard_repository
from app.modules.leaderboard import period, presenters
from app.utils.datetime import utcnow

logger = logging.getLogger(__name__)

_SUBSCRIBED_STATUSES = {
    ChatMemberStatus.MEMBER,
    ChatMemberStatus.ADMINISTRATOR,
    ChatMemberStatus.CREATOR,
}
_SUBSCRIPTION_CHECK_DELAY_SECONDS = 0.1


async def _check_subscribed(
    bot: Bot, channel_id: int, telegram_user_id: int
) -> bool | None:
    """`None` = cek gagal (jangan sentuh cache lama), `True`/`False` = hasil
    valid dari Telegram saat ini juga."""
    try:
        member = await bot.get_chat_member(channel_id, telegram_user_id)
    except Exception:
        logger.warning(
            "Gagal re-verify subscribe utk telegram_user_id=%s, dianggap "
            "tidak subscribe utk siklus posting ini (cache lama dipertahankan).",
            telegram_user_id,
            exc_info=True,
        )
        return None
    return member.status in _SUBSCRIBED_STATUSES


async def run_monthly_maintenance(
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    maintenance_gate: MaintenanceGate,
) -> None:
    """Job pemeliharaan bulanan: re-verify live status subscribe channel tiap
    user berskor, umumkan leaderboard GLOBAL (cuma subscriber) + antar-grup
    ke channel, umumkan leaderboard tiap grup (SEMUA member, tidak digating
    subscribe) ke grupnya, HAPUS FISIK skor periode itu (tidak ada riwayat
    all-time -- dikonfirmasi user, TETAP untuk semua user terlepas status
    subscribe), lalu bersihkan user/grup tidak aktif.

    Kalau `TELEGRAM_LEADERBOARD_CHANNEL_ID` belum diset ATAU posting ke
    channel gagal total, job DIBATALKAN SELURUHNYA -- tidak ada data yang
    dihapus tanpa pengumumannya benar-benar terkirim. Kegagalan posting ke
    SATU grup tertentu (bot di-kick dll), atau kegagalan cek subscribe SATU
    user tertentu, TIDAK membatalkan seluruh job.

    `maintenance_gate.active` diset True selama job benar-benar mengerjakan
    (re-verify -> posting -> reset -> cleanup) supaya handler mulai-game &
    autoreply bisa menolak sementara -- selalu dilepas lewat `finally` walau
    ada exception tak terduga di tengah jalan.
    """
    if settings.telegram_leaderboard_channel_id is None:
        logger.warning(
            "TELEGRAM_LEADERBOARD_CHANNEL_ID belum diset -- job pemeliharaan "
            "bulanan dilewati (skor TIDAK dihapus)."
        )
        return

    channel_id = settings.telegram_leaderboard_channel_id
    start, end, label = period.previous_period_window(settings.timezone)

    async with session_factory() as db:
        if await leaderboard_repository.has_run(db, label):
            return

        global_rows = await leaderboard_repository.sum_global_scores_by_user(db, start, end)
        group_ranking_rows = await leaderboard_repository.sum_scores_by_group(db, start, end)

    maintenance_gate.active = True
    try:
        subscribed_rows: list[tuple[object, int]] = []
        cache_updates: list[tuple[int, bool]] = []
        for user, total in global_rows:
            is_subscribed = await _check_subscribed(bot, channel_id, user.telegram_user_id)
            if is_subscribed is None:
                is_subscribed = False
            else:
                cache_updates.append((user.id, is_subscribed))
            if is_subscribed:
                subscribed_rows.append((user, total))
            await asyncio.sleep(_SUBSCRIPTION_CHECK_DELAY_SECONDS)

        if cache_updates:
            async with session_factory() as db:
                for user_id, is_subscribed in cache_updates:
                    await leaderboard_repository.set_channel_subscription(
                        db, user_id, is_subscribed
                    )
                await db.commit()

        try:
            for chunk in presenters.format_global_leaderboard(subscribed_rows):
                await bot.send_message(channel_id, chunk)
            for chunk in presenters.format_group_ranking(group_ranking_rows):
                await bot.send_message(channel_id, chunk)
        except Exception:
            logger.exception(
                "Gagal posting leaderboard ke channel, periode %s DIBATALKAN "
                "seluruhnya (tidak ada data dihapus). Akan dicoba lagi.",
                label,
            )
            return

        reset_note = presenters.format_reset_announcement(
            settings.telegram_leaderboard_channel_link
        )
        for group, _total in group_ranking_rows:
            async with session_factory() as db:
                group_rows = await leaderboard_repository.sum_group_scores_by_user(
                    db, group.id, start, end
                )
            try:
                for chunk in presenters.format_group_leaderboard(
                    group_rows, group.title or "grup ini"
                ):
                    await bot.send_message(group.telegram_chat_id, chunk)
                await bot.send_message(group.telegram_chat_id, reset_note)
            except Exception:
                logger.exception(
                    "Gagal posting leaderboard ke grup %s (periode %s), dilewati "
                    "-- job tetap lanjut.",
                    group.id, label,
                )

        async with session_factory() as db:
            deleted = await leaderboard_repository.delete_scores_in_range(db, start, end)
            await leaderboard_repository.mark_run(db, label, utcnow())
            await db.commit()
        logger.info(
            "Job pemeliharaan periode %s selesai: %s baris skor dihapus.", label, deleted
        )

        await _cleanup_inactive(session_factory, settings)
    finally:
        maintenance_gate.active = False


async def _cleanup_inactive(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings
) -> None:
    threshold = period.inactivity_threshold(settings.timezone)
    exempt_telegram_ids = set(settings.telegram_superadmin_ids)

    async with session_factory() as db:
        inactive_users = await leaderboard_repository.find_inactive_non_admin_users(
            db, threshold
        )
        to_delete_user_ids = [
            user.id for user in inactive_users
            if user.telegram_user_id not in exempt_telegram_ids
        ]
        deleted_users = await leaderboard_repository.delete_users_by_ids(
            db, to_delete_user_ids
        )

        inactive_groups = await leaderboard_repository.find_inactive_groups(db, threshold)
        deleted_groups = await leaderboard_repository.delete_groups_by_ids(
            db, [group.id for group in inactive_groups]
        )
        await db.commit()

    logger.info(
        "Pembersihan data tidak aktif (>6 bulan): %s user, %s grup dihapus.",
        deleted_users, deleted_groups,
    )
