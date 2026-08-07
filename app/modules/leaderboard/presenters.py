from __future__ import annotations

from html import escape

from app.database.models.group import Group
from app.database.models.user import User
from app.utils.text import chunk_lines


def _user_name(user: User) -> str:
    return escape(user.display_name or user.first_name or "?")


def _mention(user: User) -> str:
    return f'<a href="tg://user?id={user.telegram_user_id}">{_user_name(user)}</a>'


def _group_name(group: Group) -> str:
    return escape(group.title or "(tanpa nama)")


def _ranked_lines(names: list[str], scores: list[int]) -> list[str]:
    return [
        f"{index}. {name} — {score} poin"
        for index, (name, score) in enumerate(zip(names, scores), start=1)
    ]


def format_own_score(
    global_total: int, group_total: int | None, group_title: str | None
) -> str:
    lines = ["📊 SKOR KAMU BULAN INI", f"Global (semua grup): {global_total} poin"]
    if group_total is not None:
        lines.append(f"Di grup {escape(group_title) if group_title else 'ini'}: {group_total} poin")
    return "\n".join(lines)


def format_subscription_notice(is_subscribed: bool, channel_link: str | None) -> str:
    """Notice status subscribe channel leaderboard, ditempel di balasan
    `/skor` -- cuma leaderboard GLOBAL (channel + `/leaderboard`) yang
    disyaratkan subscribe, leaderboard grup tidak terpengaruh sama sekali."""
    if is_subscribed:
        return "✅ Kamu sudah subscribe channel leaderboard -- skor kamu ikut masuk leaderboard global bulanan."
    where = escape(channel_link) if channel_link else "channel leaderboard resmi"
    return (
        "🔔 Kamu belum subscribe channel leaderboard, jadi skor kamu BELUM ikut "
        f"masuk leaderboard global bulanan (leaderboard grup tetap jalan seperti biasa).\n"
        f"Subscribe dulu di {where}, lalu cek lagi pakai /skor."
    )


def format_global_leaderboard(rows: list[tuple[User, int]]) -> list[str]:
    """Leaderboard GLOBAL antar-user, TANPA mention/link (dikonfirmasi user
    -- versi ini dipakai buat pengumuman channel, bukan pesan dalam grup)."""
    header = "🏆 LEADERBOARD GLOBAL BULAN INI"
    if not rows:
        return [f"{header}\n\n(belum ada skor tercatat bulan ini)"]
    lines = [header, ""] + _ranked_lines(
        [_user_name(user) for user, _ in rows], [score for _, score in rows]
    )
    return chunk_lines(lines)


def format_group_leaderboard(rows: list[tuple[User, int]], group_title: str) -> list[str]:
    """Leaderboard SATU grup, DENGAN mention -- dikirim ke grup itu sendiri
    (on-demand `/leaderboardgrup` maupun pengumuman bulanan)."""
    header = f"🏆 LEADERBOARD {escape(group_title).upper()} BULAN INI"
    if not rows:
        return [f"{header}\n\n(belum ada skor tercatat bulan ini)"]
    lines = [header, ""] + _ranked_lines(
        [_mention(user) for user, _ in rows], [score for _, score in rows]
    )
    return chunk_lines(lines)


def format_group_ranking(rows: list[tuple[Group, int]]) -> list[str]:
    """Leaderboard ANTAR-GRUP (grup vs grup, bukan cuma daftar) -- nama grup
    TANPA link, dikirim ke channel pengumuman supaya grup terpacu ramai-ramai
    main biar namanya masuk peringkat atas."""
    header = "🏘 LEADERBOARD ANTAR-GRUP BULAN INI"
    if not rows:
        return [f"{header}\n\n(belum ada grup dengan skor bulan ini)"]
    lines = [header, ""] + _ranked_lines(
        [_group_name(group) for group, _ in rows], [score for _, score in rows]
    )
    return chunk_lines(lines)


def format_reset_announcement(channel_link: str | None) -> str:
    where = escape(channel_link) if channel_link else "channel pengumuman resmi"
    return (
        "🔄 Skor bulan ini sudah diumumkan dan direset ke 0 untuk bulan baru.\n"
        f"Cek leaderboard global & antar-grup di {where}."
    )
