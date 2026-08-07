from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.database.models  # noqa: F401  (registra semua model ke Base.metadata)
from app.database.base import Base
from app.database.repositories import group_repository, user_repository
from app.database.sqlite import register_sqlite_pragmas
from app.modules.games.callbacks import GameCallback
from app.modules.games.engine.manager import GameManager
from app.modules.games.engine.registry import GameRegistry
from app.modules.games.private_input import clear_all_private_inputs


@pytest.fixture(autouse=True)
def _isolated_private_input_registry():
    """`PrivateInputRegistry` singleton di level modul (sengaja, lihat
    `app/modules/games/private_input.py`) -- bersihkan sebelum & sesudah
    tiap test supaya skenario yang beda tidak saling mencemari."""
    clear_all_private_inputs()
    yield
    clear_all_private_inputs()


class FakeMessage:
    """Pesan Telegram tiruan -- dipakai baik untuk pesan yang "dikirim" oleh
    `FakeBot` maupun untuk mensimulasikan pesan MASUK dari seorang pemain
    (di private chat). `.answer()` selalu membalas ke chat yang sama lewat
    `FakeBot.send_message`, sama seperti method `Message.answer()` aiogram
    asli."""

    _next_id = 1

    def __init__(self, bot: "FakeBot", chat_id: int, text: str | None = None, reply_markup=None) -> None:
        self._bot = bot
        self.chat = SimpleNamespace(id=chat_id)
        self.text = text
        self.reply_markup = reply_markup
        self.message_id = FakeMessage._next_id
        FakeMessage._next_id += 1
        self.from_user = SimpleNamespace(id=0, is_bot=False)

    async def answer(self, text: str, reply_markup=None, **kwargs) -> "FakeMessage":
        return await self._bot.send_message(self.chat.id, text, reply_markup=reply_markup)


class FakeBot:
    """Bot tiruan: `send_message`/`edit_message_text`/`edit_message_reply_markup`
    cuma mencatat riwayat, tidak pernah benar-benar memanggil Telegram."""

    def __init__(self) -> None:
        self.id = id(self)
        self.sent: list[FakeMessage] = []
        self.edits: list[dict] = []
        self.fail_next_edits = 0
        # chat_id yang harus GAGAL TERUS kalau dikirimi pesan -- dipakai untuk
        # mensimulasikan chat privat yang tidak nyata sama sekali (mis.
        # telegram_user_id palsu milik virtual player).
        self.fail_send_to: set[int] = set()
        # chat_id yang gagal N kali dulu baru berhasil lagi -- dipakai untuk
        # mensimulasikan kegagalan SEMENTARA (mis. blip jaringan) tanpa harus
        # membuat chat itu rusak permanen buat sisa test.
        self.fail_send_count: dict[int, int] = {}

    async def get_me(self):
        return SimpleNamespace(id=self.id, username="test_bot")

    async def send_message(self, chat_id, text, reply_markup=None, **kwargs) -> FakeMessage:
        if chat_id in self.fail_send_to:
            raise RuntimeError(f"simulated send failure to chat {chat_id}")
        remaining = self.fail_send_count.get(chat_id)
        if remaining is not None:
            if remaining <= 1:
                del self.fail_send_count[chat_id]
            else:
                self.fail_send_count[chat_id] = remaining - 1
            raise RuntimeError(f"simulated transient send failure to chat {chat_id}")
        message = FakeMessage(self, chat_id, text, reply_markup)
        self.sent.append(message)
        return message

    async def edit_message_text(self, text, chat_id, message_id, reply_markup=None, **kwargs) -> None:
        if self.fail_next_edits > 0:
            self.fail_next_edits -= 1
            raise RuntimeError("simulated edit failure")
        self.edits.append(
            {"chat_id": chat_id, "message_id": message_id, "text": text, "reply_markup": reply_markup}
        )

    async def edit_message_reply_markup(self, chat_id, message_id, reply_markup=None, **kwargs) -> None:
        self.edits.append(
            {"chat_id": chat_id, "message_id": message_id, "text": None, "reply_markup": reply_markup}
        )

    @property
    def all_texts(self) -> list[str]:
        return [m.text for m in self.sent]

    def texts_to(self, chat_id) -> list[str]:
        return [m.text for m in self.sent if m.chat.id == chat_id]


class FakeCallback:
    """CallbackQuery tiruan: `data` sudah di-pack lewat `GameCallback`, dan
    `.message.message_id`/`.message.chat.id` bisa diisi supaya validasi
    pointer pesan otoritatif (game-development-guide.md §7.1) bisa ditest."""

    def __init__(self, session_id: int, data: str, message_id: int | None = None, chat_id: int = 0) -> None:
        self.data = GameCallback(session_id=session_id, data=data).pack()
        if message_id is not None:
            self.message = SimpleNamespace(message_id=message_id, chat=SimpleNamespace(id=chat_id))
        else:
            self.message = None
        self.from_user = SimpleNamespace(id=0)  # sengaja tidak dipakai -- identitas lewat acting_user_id
        self.answers: list[tuple[str | None, bool]] = []

    async def answer(self, text: str | None = None, show_alert: bool = False) -> None:
        self.answers.append((text, show_alert))


@pytest_asyncio.fixture
async def session_factory(tmp_path):
    db_path = tmp_path / f"test-{uuid.uuid4().hex}.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    register_sqlite_pragmas(engine)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@dataclass
class GameWorld:
    """Bungkusan siap-pakai: registry+bot+manager+group, plus helper bikin
    pemain baru & langsung mulai game -- dipakai semua test integrasi supaya
    boilerplate setup tidak diulang di tiap file test."""

    session_factory: object
    bot: FakeBot
    manager: GameManager
    group_id: int
    telegram_chat_id: int
    user_ids: list[int] = field(default_factory=list)
    telegram_ids_by_user_id: dict[int, int] = field(default_factory=dict)

    async def add_players(self, count: int, *, start_index: int = 0) -> list[int]:
        new_ids: list[int] = []
        async with self.session_factory() as db_session:
            for i in range(start_index, start_index + count):
                user = await user_repository.get_or_create_virtual_player(db_session, i)
                new_ids.append(user.id)
                self.telegram_ids_by_user_id[user.id] = user.telegram_user_id
            await db_session.commit()
        self.user_ids.extend(new_ids)
        return new_ids

    def telegram_id_of(self, user_id: int) -> int:
        return self.telegram_ids_by_user_id[user_id]

    async def start_game_now(self, game_key: str, user_ids: list[int]) -> int:
        """Lewati lobby-timer/ready-check (sudah generik & diverifikasi
        terpisah di luar test kuis_kenal) -- langsung buat lobby, join semua
        pemain, lalu paksa `start_game()` supaya sesi RUNNING dengan state
        awal game yang benar-benar terpasang."""
        async with self.session_factory() as db_session:
            game_session = await self.manager.create_lobby(
                db_session,
                group_id=self.group_id,
                telegram_chat_id=self.telegram_chat_id,
                game_key=game_key,
                created_by_user_id=user_ids[0],
            )
            session_id = game_session.id

        for uid in user_ids[1:]:
            async with self.session_factory() as db_session:
                await self.manager.join_game(db_session, session_id=session_id, internal_user_id=uid)

        async with self.session_factory() as db_session:
            await self.manager.start_game(db_session, session_id=session_id)

        return session_id

    async def get_state(self, session_id: int) -> dict:
        from app.database.repositories.game_repository import find_by_id

        async with self.session_factory() as db_session:
            game_session = await find_by_id(db_session, session_id)
            return game_session.state_json

    async def get_session(self, session_id: int):
        from app.database.repositories.game_repository import find_by_id

        async with self.session_factory() as db_session:
            return await find_by_id(db_session, session_id)


@pytest_asyncio.fixture
async def game_world(session_factory):
    bot = FakeBot()
    registry = GameRegistry()
    manager = GameManager(registry, session_factory, bot)

    async with session_factory() as db_session:
        chat_id = 1_000_000 + uuid.uuid4().int % 1_000_000
        group = await group_repository.upsert_group(
            db_session, SimpleNamespace(id=chat_id, title="Test Group", username=None, type="group")
        )
        group_id = group.id
        await db_session.commit()

    world = GameWorld(
        session_factory=session_factory,
        bot=bot,
        manager=manager,
        group_id=group_id,
        telegram_chat_id=chat_id,
    )
    yield world

    # Skenario yang tidak dimainkan sampai FINISHED/CANCELLED meninggalkan
    # timer latar belakang tergantung -- bersihkan semuanya di sini supaya
    # tidak mencemari test lain / bikin warning "Task was destroyed" (lihat
    # catatan metodologi di project-telegram-bot-status).
    for task in list(manager._timers._tasks.values()):
        if not task.done():
            task.cancel()


@pytest.fixture
def register_game(game_world):
    def _register(game) -> None:
        game_world.manager._registry.register(game)

    return _register
