from __future__ import annotations

import logging
from datetime import timedelta

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm.attributes import flag_modified

from app.core.enums import GameEventType, GamePlayerStatus, GameStatus
from app.core.exceptions import (
    ActiveGameExistsError,
    InvalidGameStateError,
    PlayerAlreadyJoinedError,
    PlayerLimitReachedError,
    SessionNotFoundError,
)
from app.database.models.game_player import GamePlayer
from app.database.models.game_session import GameSession
from app.database.repositories import game_repository, group_repository, user_repository
from app.modules.games.engine.context import GameContext, PlayerInfo
from app.modules.games.engine.lobby import (
    PLAY_AGAIN_HINT,
    render_cancelled_text,
    render_lobby_text,
    render_ready_check_text,
)
from app.modules.games.engine.lock_manager import GameLockManager
from app.modules.games.engine.registry import GameRegistry
from app.modules.games.engine.timer import TimerRegistry
from app.modules.games.keyboards.lobby import build_lobby_keyboard, build_ready_check_keyboard
from app.utils.datetime import utcnow

logger = logging.getLogger(__name__)


class GameManager:
    def __init__(
        self,
        registry: GameRegistry,
        session_factory: async_sessionmaker[AsyncSession],
        bot: Bot,
    ) -> None:
        self._registry = registry
        self._session_factory = session_factory
        self._bot = bot
        self._locks = GameLockManager()
        self._timers = TimerRegistry()

    # ------------------------------------------------------------------
    # Lobby lifecycle (dipanggil dari handler request-scoped)
    # ------------------------------------------------------------------

    async def create_lobby(
        self,
        db_session: AsyncSession,
        *,
        group_id: int,
        telegram_chat_id: int,
        game_key: str,
        created_by_user_id: int,
    ) -> GameSession:
        game = self._registry.get(game_key)

        existing = await game_repository.find_active_by_group(db_session, group_id)
        if existing is not None:
            raise ActiveGameExistsError(str(existing.id))

        game_session = await game_repository.create_session(
            db_session,
            group_id=group_id,
            game_key=game_key,
            created_by_user_id=created_by_user_id,
            min_players=game.metadata.min_players,
            max_players=game.metadata.max_players,
        )
        game_session.status = GameStatus.LOBBY.value
        game_session.lobby_expires_at = utcnow() + timedelta(
            seconds=game.metadata.lobby_timeout_seconds
        )
        await db_session.flush()
        await game_repository.log_event(
            db_session,
            game_session.id,
            GameEventType.LOBBY_CREATED.value,
            actor_user_id=created_by_user_id,
        )

        # Pembuat lobby otomatis ikut join.
        await game_repository.add_player(db_session, game_session.id, created_by_user_id)
        await db_session.flush()
        await game_repository.log_event(
            db_session,
            game_session.id,
            GameEventType.PLAYER_JOINED.value,
            actor_user_id=created_by_user_id,
        )

        active_players = await game_repository.find_active_players(
            db_session, game_session.id
        )
        player_infos = await self._to_player_infos(db_session, active_players)
        text = render_lobby_text(
            game.metadata, player_infos, game.metadata.lobby_timeout_seconds
        )
        message = await self._bot.send_message(
            telegram_chat_id, text, reply_markup=build_lobby_keyboard(game_session.id)
        )
        game_session.lobby_message_id = message.message_id
        await db_session.commit()

        self._schedule_lobby_timeout(game_session.id, game.metadata.lobby_timeout_seconds)
        return game_session

    async def join_game(
        self, db_session: AsyncSession, *, session_id: int, internal_user_id: int
    ) -> GameSession:
        lock = self._locks.get(session_id)
        async with lock:
            game_session = await game_repository.find_by_id(db_session, session_id)
            if game_session is None:
                raise SessionNotFoundError(str(session_id))
            if game_session.status != GameStatus.LOBBY.value:
                raise InvalidGameStateError(game_session.status)

            existing_player = await game_repository.find_player(
                db_session, session_id, internal_user_id
            )
            if existing_player is not None and existing_player.status in (
                GamePlayerStatus.JOINED.value,
                GamePlayerStatus.ACTIVE.value,
            ):
                raise PlayerAlreadyJoinedError(str(internal_user_id))

            active_players = await game_repository.find_active_players(
                db_session, session_id
            )
            if len(active_players) >= game_session.max_players:
                raise PlayerLimitReachedError(str(session_id))

            if existing_player is not None:
                existing_player.status = GamePlayerStatus.JOINED.value
                existing_player.left_at = None
            else:
                await game_repository.add_player(db_session, session_id, internal_user_id)
            await db_session.flush()

            await game_repository.log_event(
                db_session,
                session_id,
                GameEventType.PLAYER_JOINED.value,
                actor_user_id=internal_user_id,
            )

            await self._refresh_lobby_message(db_session, game_session)
            # Commit di dalam lock: mencegah request lain (yang menunggu lock ini)
            # membaca state basi sebelum perubahan benar-benar tersimpan.
            await db_session.commit()
            return game_session

    async def leave_game(
        self, db_session: AsyncSession, *, session_id: int, internal_user_id: int
    ) -> GameSession:
        lock = self._locks.get(session_id)
        async with lock:
            game_session = await game_repository.find_by_id(db_session, session_id)
            if game_session is None:
                raise SessionNotFoundError(str(session_id))
            if game_session.status != GameStatus.LOBBY.value:
                raise InvalidGameStateError(game_session.status)

            player = await game_repository.find_player(
                db_session, session_id, internal_user_id
            )
            if player is None or player.status not in (
                GamePlayerStatus.JOINED.value,
                GamePlayerStatus.ACTIVE.value,
            ):
                raise InvalidGameStateError("not_joined")

            player.status = GamePlayerStatus.LEFT.value
            player.left_at = utcnow()
            await db_session.flush()
            await game_repository.log_event(
                db_session,
                session_id,
                GameEventType.PLAYER_LEFT.value,
                actor_user_id=internal_user_id,
            )

            await self._refresh_lobby_message(db_session, game_session)
            await db_session.commit()
            return game_session

    async def extend_lobby(
        self, db_session: AsyncSession, *, session_id: int, internal_user_id: int
    ) -> GameSession:
        lock = self._locks.get(session_id)
        async with lock:
            game_session = await game_repository.find_by_id(db_session, session_id)
            if game_session is None:
                raise SessionNotFoundError(str(session_id))
            if game_session.status != GameStatus.LOBBY.value:
                raise InvalidGameStateError(game_session.status)

            player = await game_repository.find_player(
                db_session, session_id, internal_user_id
            )
            if player is None or player.status not in (
                GamePlayerStatus.JOINED.value,
                GamePlayerStatus.ACTIVE.value,
            ):
                raise InvalidGameStateError("not_joined")

            game = self._registry.get(game_session.game_key)
            game_session.lobby_expires_at = utcnow() + timedelta(
                seconds=game.metadata.lobby_timeout_seconds
            )
            await db_session.flush()
            await game_repository.log_event(
                db_session,
                session_id,
                GameEventType.LOBBY_EXTENDED.value,
                actor_user_id=internal_user_id,
            )

            self._schedule_lobby_timeout(session_id, game.metadata.lobby_timeout_seconds)
            await self._refresh_lobby_message(db_session, game_session)
            await db_session.commit()
            return game_session

    async def mark_ready(
        self, db_session: AsyncSession, *, session_id: int, internal_user_id: int
    ) -> GameSession:
        lock = self._locks.get(session_id)
        async with lock:
            game_session = await game_repository.find_by_id(db_session, session_id)
            if game_session is None:
                raise SessionNotFoundError(str(session_id))
            if game_session.status != GameStatus.STARTING.value:
                raise InvalidGameStateError(game_session.status)

            player = await game_repository.find_player(
                db_session, session_id, internal_user_id
            )
            if player is None or player.status not in (
                GamePlayerStatus.JOINED.value,
                GamePlayerStatus.ACTIVE.value,
            ):
                raise InvalidGameStateError("not_in_game")

            state = game_session.state_json
            ready_ids = set(state.get("ready_user_ids", []))
            ready_ids.add(internal_user_id)
            state["ready_user_ids"] = list(ready_ids)
            game_session.state_json = state
            flag_modified(game_session, "state_json")
            await db_session.flush()
            await game_repository.log_event(
                db_session,
                session_id,
                GameEventType.PLAYER_READY.value,
                actor_user_id=internal_user_id,
            )

            active_players = await game_repository.find_active_players(
                db_session, session_id
            )
            all_ready = all(p.user_id in ready_ids for p in active_players)

            if all_ready:
                self._timers.cancel(f"starting:{session_id}")
                await self.start_game(db_session, session_id=session_id)
            else:
                await self._refresh_ready_check_message(
                    db_session, game_session, active_players, ready_ids
                )
                await db_session.commit()

            return game_session

    async def cancel_game(
        self,
        db_session: AsyncSession,
        *,
        session_id: int,
        reason: str,
        cancelled_by_user_id: int | None = None,
    ) -> GameSession:
        game_session = await game_repository.find_by_id(db_session, session_id)
        if game_session is None:
            raise SessionNotFoundError(str(session_id))
        if game_session.status not in (
            GameStatus.LOBBY.value,
            GameStatus.STARTING.value,
        ):
            raise InvalidGameStateError(game_session.status)

        game = self._registry.get(game_session.game_key)
        # Diambil SEBELUM status berubah: pemain yang masih aktif saat ini
        # (yang sudah join kalau dibatalkan dari lobby, atau yang sudah
        # konfirmasi siap kalau dibatalkan dari ready-check, karena yang
        # belum siap sudah di-kick lebih dulu) -- untuk disapa di pesan.
        active_players = await game_repository.find_active_players(
            db_session, session_id
        )
        mentioned_players = await self._to_player_infos(db_session, active_players)

        game_session.status = GameStatus.CANCELLED.value
        game_session.cancelled_at = utcnow()
        game_session.cancellation_reason = reason
        await db_session.flush()
        await game_repository.log_event(
            db_session,
            session_id,
            GameEventType.GAME_CANCELLED.value,
            actor_user_id=cancelled_by_user_id,
            payload={"reason": reason},
        )

        self._timers.cancel_session(session_id)
        self._locks.remove(session_id)

        if game_session.lobby_message_id is not None:
            group = await group_repository.find_by_id(db_session, game_session.group_id)
            if group is not None:
                text = render_cancelled_text(game.metadata, reason, mentioned_players)
                try:
                    await self._bot.edit_message_text(
                        text,
                        chat_id=group.telegram_chat_id,
                        message_id=game_session.lobby_message_id,
                    )
                except Exception:
                    logger.exception(
                        "Gagal mengedit pesan lobby saat cancel, session %s", session_id
                    )

        await db_session.commit()
        return game_session

    async def start_game(self, db_session: AsyncSession, *, session_id: int) -> GameSession:
        game_session = await game_repository.find_by_id(db_session, session_id)
        if game_session is None:
            raise SessionNotFoundError(str(session_id))

        game = self._registry.get(game_session.game_key)
        active_players = await game_repository.find_active_players(db_session, session_id)
        if len(active_players) < game.metadata.min_players:
            return await self.cancel_game(
                db_session, session_id=session_id, reason="insufficient_players"
            )

        game_session.status = GameStatus.RUNNING.value
        game_session.started_at = utcnow()
        await db_session.flush()
        await game_repository.log_event(
            db_session, session_id, GameEventType.GAME_STARTED.value
        )

        if game_session.lobby_message_id is not None:
            group = await group_repository.find_by_id(db_session, game_session.group_id)
            if group is not None:
                try:
                    await self._bot.edit_message_text(
                        "🎮 Game dimulai!",
                        chat_id=group.telegram_chat_id,
                        message_id=game_session.lobby_message_id,
                    )
                except Exception:
                    logger.exception(
                        "Gagal mengedit pesan lobby saat mulai, session %s", session_id
                    )

        context = await self._build_context(db_session, game_session, active_players)
        await game.initialize(context)
        await game.start(context)
        await db_session.commit()
        return game_session

    # ------------------------------------------------------------------
    # Dispatch dalam-game (delegasi ke BaseGame implementasi)
    # ------------------------------------------------------------------

    async def handle_callback(
        self, db_session: AsyncSession, *, session_id: int, callback: object
    ) -> None:
        lock = self._locks.get(session_id)
        async with lock:
            game_session = await game_repository.find_by_id(db_session, session_id)
            if game_session is None or game_session.status != GameStatus.RUNNING.value:
                return
            game = self._registry.get(game_session.game_key)
            context = await self._build_context(db_session, game_session)
            await game.handle_callback(context, callback)
            await db_session.commit()

    async def handle_message(
        self, db_session: AsyncSession, *, session_id: int, message: object
    ) -> None:
        lock = self._locks.get(session_id)
        async with lock:
            game_session = await game_repository.find_by_id(db_session, session_id)
            if game_session is None or game_session.status != GameStatus.RUNNING.value:
                return
            game = self._registry.get(game_session.game_key)
            context = await self._build_context(db_session, game_session)
            await game.handle_message(context, message)
            await db_session.commit()

    def schedule_timer(self, session_id: int, name: str, delay_seconds: float) -> None:
        self._timers.schedule(
            f"turn:{session_id}:{name}",
            delay_seconds,
            self._make_timer_runner(session_id, name),
        )

    def cancel_timer(self, session_id: int, name: str) -> None:
        self._timers.cancel(f"turn:{session_id}:{name}")

    def schedule_turn_timeout(self, session_id: int, delay_seconds: float) -> None:
        self.schedule_timer(session_id, "round", delay_seconds)

    def cancel_turn_timeout(self, session_id: int) -> None:
        self.cancel_timer(session_id, "round")

    async def finish_game(self, context: GameContext, result) -> None:  # noqa: ANN001
        game_session = context.game_session
        game_session.status = GameStatus.FINISHED.value
        game_session.finished_at = utcnow()
        game_session.result_json = {
            "winner_user_id": result.winner_user_id,
            "summary": result.summary,
            "payload": result.payload,
        }
        await context.db_session.flush()
        await game_repository.log_event(
            context.db_session,
            game_session.id,
            GameEventType.GAME_FINISHED.value,
            actor_user_id=result.winner_user_id,
            payload=result.payload,
        )

        game = self._registry.get(game_session.game_key)
        await game.finish(context, result)

        try:
            await context.bot.send_message(context.telegram_chat_id, PLAY_AGAIN_HINT)
        except Exception:
            logger.exception(
                "Gagal mengirim ajakan main lagi, session %s", game_session.id
            )

        self._timers.cancel_session(game_session.id)
        self._locks.remove(game_session.id)

    # ------------------------------------------------------------------
    # Recovery setelah restart (dipanggil sekali saat startup, sebelum
    # long polling dimulai)
    # ------------------------------------------------------------------

    async def recover_sessions(self) -> None:
        async with self._session_factory() as db_session:
            sessions = await game_repository.find_all_active(db_session)
            snapshots = [
                (s.id, s.status, s.lobby_expires_at, s.starting_expires_at)
                for s in sessions
            ]

        if not snapshots:
            return

        logger.info("Memulihkan %s game session aktif setelah restart", len(snapshots))
        for session_id, status, lobby_expires_at, starting_expires_at in snapshots:
            try:
                if status == GameStatus.RUNNING.value:
                    await self._abort_running_session(session_id)
                elif status == GameStatus.LOBBY.value:
                    await self._recover_lobby_session(session_id, lobby_expires_at)
                elif status == GameStatus.STARTING.value:
                    await self._recover_starting_session(session_id, starting_expires_at)
            except Exception:
                logger.exception(
                    "Gagal memulihkan session %s (status=%s)", session_id, status
                )

    async def _recover_lobby_session(
        self, session_id: int, lobby_expires_at  # noqa: ANN001
    ) -> None:
        remaining = (
            (lobby_expires_at - utcnow()).total_seconds() if lobby_expires_at else 0
        )
        if remaining <= 0:
            await self._resolve_lobby_timeout(session_id)
        else:
            self._schedule_lobby_timeout(session_id, remaining)

    async def _recover_starting_session(
        self, session_id: int, starting_expires_at  # noqa: ANN001
    ) -> None:
        remaining = (
            (starting_expires_at - utcnow()).total_seconds()
            if starting_expires_at
            else 0
        )
        if remaining <= 0:
            await self._resolve_starting_timeout(session_id)
        else:
            self._schedule_starting_timeout(session_id, remaining)

    async def _abort_running_session(self, session_id: int) -> None:
        async with self._session_factory() as db_session:
            game_session = await game_repository.find_by_id(db_session, session_id)
            if game_session is None or game_session.status != GameStatus.RUNNING.value:
                return

            game = self._registry.get(game_session.game_key)
            game_session.status = GameStatus.ABORTED.value
            game_session.cancelled_at = utcnow()
            game_session.cancellation_reason = "server_restart"
            await db_session.flush()
            await game_repository.log_event(
                db_session,
                session_id,
                GameEventType.GAME_CANCELLED.value,
                payload={"reason": "server_restart"},
            )

            self._timers.cancel_session(session_id)
            self._locks.remove(session_id)

            group = await group_repository.find_by_id(db_session, game_session.group_id)
            if group is not None:
                text = (
                    f"⚠️ {game.metadata.name} terhenti karena bot baru saja restart.\n"
                    "Maaf atas ketidaknyamanannya!\n\n"
                    f"{PLAY_AGAIN_HINT}"
                )
                try:
                    await self._bot.send_message(group.telegram_chat_id, text)
                except Exception:
                    logger.exception(
                        "Gagal mengirim notifikasi abort, session %s", session_id
                    )

            await db_session.commit()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _refresh_lobby_message(self, db_session, game_session) -> None:  # noqa: ANN001
        if game_session.lobby_message_id is None:
            return
        group = await group_repository.find_by_id(db_session, game_session.group_id)
        if group is None:
            return

        game = self._registry.get(game_session.game_key)
        active_players = await game_repository.find_active_players(
            db_session, game_session.id
        )
        player_infos = await self._to_player_infos(db_session, active_players)
        remaining = (
            (game_session.lobby_expires_at - utcnow()).total_seconds()
            if game_session.lobby_expires_at
            else 0
        )
        text = render_lobby_text(game.metadata, player_infos, int(remaining))

        try:
            await self._bot.edit_message_text(
                text,
                chat_id=group.telegram_chat_id,
                message_id=game_session.lobby_message_id,
                reply_markup=build_lobby_keyboard(game_session.id),
            )
        except Exception:
            logger.exception(
                "Gagal memperbarui pesan lobby, session %s", game_session.id
            )

    async def _refresh_ready_check_message(
        self,
        db_session,  # noqa: ANN001
        game_session,  # noqa: ANN001
        active_players: list[GamePlayer],
        ready_ids: set[int],
    ) -> None:
        if game_session.lobby_message_id is None:
            return
        group = await group_repository.find_by_id(db_session, game_session.group_id)
        if group is None:
            return

        game = self._registry.get(game_session.game_key)
        player_infos = await self._to_player_infos(db_session, active_players)
        remaining = (
            (game_session.starting_expires_at - utcnow()).total_seconds()
            if game_session.starting_expires_at
            else 0
        )
        text = render_ready_check_text(game.metadata, player_infos, ready_ids, int(remaining))

        try:
            await self._bot.edit_message_text(
                text,
                chat_id=group.telegram_chat_id,
                message_id=game_session.lobby_message_id,
                reply_markup=build_ready_check_keyboard(game_session.id),
            )
        except Exception:
            logger.exception(
                "Gagal memperbarui pesan ready-check, session %s", game_session.id
            )

    async def _to_player_infos(
        self, db_session, players: list[GamePlayer]  # noqa: ANN001
    ) -> list[PlayerInfo]:
        infos: list[PlayerInfo] = []
        for player in players:
            user = await user_repository.find_by_id(db_session, player.user_id)
            if user is not None:
                infos.append(
                    PlayerInfo(
                        user_id=user.id,
                        telegram_user_id=user.telegram_user_id,
                        display_name=user.display_name or user.first_name or "Pemain",
                    )
                )
        return infos

    async def _build_context(
        self,
        db_session,  # noqa: ANN001
        game_session: GameSession,
        active_players: list[GamePlayer] | None = None,
    ) -> GameContext:
        if active_players is None:
            active_players = await game_repository.find_active_players(
                db_session, game_session.id
            )

        group = await group_repository.find_by_id(db_session, game_session.group_id)
        telegram_chat_id = group.telegram_chat_id if group else 0

        return GameContext(
            bot=self._bot,
            db_session=db_session,
            game_session=game_session,
            telegram_chat_id=telegram_chat_id,
            game_manager=self,
            active_players=await self._to_player_infos(db_session, active_players),
        )

    def _schedule_lobby_timeout(self, session_id: int, delay_seconds: float) -> None:
        self._timers.schedule(
            f"lobby:{session_id}", delay_seconds, self._make_lobby_timeout_runner(session_id)
        )

    def _schedule_starting_timeout(self, session_id: int, delay_seconds: float) -> None:
        self._timers.schedule(
            f"starting:{session_id}",
            delay_seconds,
            self._make_starting_timeout_runner(session_id),
        )

    def _make_lobby_timeout_runner(self, session_id: int):
        async def _runner() -> None:
            await self._resolve_lobby_timeout(session_id)

        return _runner

    async def _resolve_lobby_timeout(self, session_id: int) -> None:
        lock = self._locks.get(session_id)
        async with lock:
            async with self._session_factory() as db_session:
                game_session = await game_repository.find_by_id(db_session, session_id)
                if game_session is None or game_session.status != GameStatus.LOBBY.value:
                    return

                game = self._registry.get(game_session.game_key)
                active_players = await game_repository.find_active_players(
                    db_session, session_id
                )

                if len(active_players) < game.metadata.min_players:
                    await self.cancel_game(
                        db_session,
                        session_id=session_id,
                        reason="insufficient_players",
                    )
                    return

                await self._begin_ready_check(
                    db_session, game_session, game, active_players
                )

    async def _begin_ready_check(
        self,
        db_session,  # noqa: ANN001
        game_session: GameSession,
        game,  # noqa: ANN001
        active_players: list[GamePlayer],
    ) -> None:
        game_session.status = GameStatus.STARTING.value
        game_session.starting_expires_at = utcnow() + timedelta(
            seconds=game.metadata.ready_check_seconds
        )
        game_session.state_json = {"ready_user_ids": []}
        flag_modified(game_session, "state_json")
        await db_session.flush()
        await game_repository.log_event(
            db_session, game_session.id, GameEventType.READY_CHECK_STARTED.value
        )

        player_infos = await self._to_player_infos(db_session, active_players)
        group = await group_repository.find_by_id(db_session, game_session.group_id)
        text = render_ready_check_text(
            game.metadata, player_infos, set(), game.metadata.ready_check_seconds
        )

        if group is not None:
            if game_session.lobby_message_id is not None:
                try:
                    await self._bot.edit_message_text(
                        "🔒 Lobi ditutup, cek konfirmasi siap di bawah.",
                        chat_id=group.telegram_chat_id,
                        message_id=game_session.lobby_message_id,
                    )
                except Exception:
                    logger.exception(
                        "Gagal menutup pesan lobby, session %s", game_session.id
                    )

            try:
                message = await self._bot.send_message(
                    group.telegram_chat_id,
                    text,
                    reply_markup=build_ready_check_keyboard(game_session.id),
                )
                game_session.lobby_message_id = message.message_id
                await db_session.flush()
            except Exception:
                logger.exception(
                    "Gagal mengirim pesan ready-check, session %s", game_session.id
                )

        await db_session.commit()
        self._schedule_starting_timeout(game_session.id, game.metadata.ready_check_seconds)

    def _make_starting_timeout_runner(self, session_id: int):
        async def _runner() -> None:
            await self._resolve_starting_timeout(session_id)

        return _runner

    async def _resolve_starting_timeout(self, session_id: int) -> None:
        lock = self._locks.get(session_id)
        async with lock:
            async with self._session_factory() as db_session:
                game_session = await game_repository.find_by_id(db_session, session_id)
                if (
                    game_session is None
                    or game_session.status != GameStatus.STARTING.value
                ):
                    return

                state = game_session.state_json
                ready_ids = set(state.get("ready_user_ids", []))
                active_players = await game_repository.find_active_players(
                    db_session, session_id
                )

                not_ready = [p for p in active_players if p.user_id not in ready_ids]
                for player in not_ready:
                    player.status = GamePlayerStatus.LEFT.value
                    player.left_at = utcnow()
                    await game_repository.log_event(
                        db_session,
                        session_id,
                        GameEventType.PLAYER_KICKED_NOT_READY.value,
                        actor_user_id=player.user_id,
                    )
                await db_session.flush()

                remaining_players = await game_repository.find_active_players(
                    db_session, session_id
                )
                game = self._registry.get(game_session.game_key)

                if len(remaining_players) < game.metadata.min_players:
                    await self.cancel_game(
                        db_session,
                        session_id=session_id,
                        reason="not_enough_ready_players",
                    )
                    return

                await self.start_game(db_session, session_id=session_id)

    def _make_timer_runner(self, session_id: int, name: str):
        timer_key = f"turn:{session_id}:{name}"

        async def _runner() -> None:
            lock = self._locks.get(session_id)
            async with lock:
                async with self._session_factory() as db_session:
                    game_session = await game_repository.find_by_id(
                        db_session, session_id
                    )
                    if (
                        game_session is None
                        or game_session.status != GameStatus.RUNNING.value
                    ):
                        return
                    game = self._registry.get(game_session.game_key)
                    context = await self._build_context(db_session, game_session)
                    await game.handle_timeout(context, timer_key)
                    await db_session.commit()

        return _runner
