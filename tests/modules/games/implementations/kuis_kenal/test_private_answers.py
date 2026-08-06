from __future__ import annotations

from app.modules.games.implementations.kuis_kenal.metadata import ANSWER_MAX_LENGTH
from tests.modules.games.implementations.kuis_kenal.helpers import (
    extract_start_payload,
    latest_markup_to,
    open_deep_link,
    send_private_text,
)


async def _get_to_answering(game_world, kuis_kenal_game):
    game = kuis_kenal_game
    user_ids = await game_world.add_players(3)
    session_id = await game_world.start_game_now("kuis_kenal", user_ids)

    state = await game_world.get_state(session_id)
    subject_id = state["current_subject_id"]
    subject_chat = game_world.telegram_id_of(subject_id)
    round_number = state["round"]

    markup = latest_markup_to(game_world.bot, game_world.telegram_chat_id)
    payload = extract_start_payload(markup)
    await open_deep_link(game, game_world, session_id, payload, user_id=subject_id, chat_id=subject_chat)
    state = await game_world.get_state(session_id)

    from tests.modules.games.implementations.kuis_kenal.helpers import send_callback

    await send_callback(
        game_world, session_id, f"{round_number}-{state['message_version']}-qp-0",
        message_id=state["subject_private_message_id"], chat_id=subject_chat, user_id=subject_id,
    )

    answerer_id = next(uid for uid in user_ids if uid != subject_id)
    answerer_chat = game_world.telegram_id_of(answerer_id)
    markup = latest_markup_to(game_world.bot, game_world.telegram_chat_id)
    answer_payload = extract_start_payload(markup)
    await open_deep_link(game, game_world, session_id, answer_payload, user_id=answerer_id, chat_id=answerer_chat)

    return game, session_id, subject_id, subject_chat, answerer_id, answerer_chat


async def test_empty_answer_rejected(game_world, kuis_kenal_game):
    game, session_id, subject_id, subject_chat, answerer_id, answerer_chat = await _get_to_answering(
        game_world, kuis_kenal_game
    )
    await send_private_text(game_world, session_id, "   ", user_id=answerer_id, chat_id=answerer_chat)
    state = await game_world.get_state(session_id)
    assert state["answer_drafts"] == {}
    assert any("kosong" in t for t in game_world.bot.texts_to(answerer_chat))


async def test_command_rejected_as_answer(game_world, kuis_kenal_game):
    game, session_id, subject_id, subject_chat, answerer_id, answerer_chat = await _get_to_answering(
        game_world, kuis_kenal_game
    )
    await send_private_text(game_world, session_id, "/skor", user_id=answerer_id, chat_id=answerer_chat)
    state = await game_world.get_state(session_id)
    assert state["answer_drafts"] == {}


async def test_too_long_answer_rejected(game_world, kuis_kenal_game):
    game, session_id, subject_id, subject_chat, answerer_id, answerer_chat = await _get_to_answering(
        game_world, kuis_kenal_game
    )
    long_text = "a" * (ANSWER_MAX_LENGTH + 1)
    await send_private_text(game_world, session_id, long_text, user_id=answerer_id, chat_id=answerer_chat)
    state = await game_world.get_state(session_id)
    assert state["answer_drafts"] == {}
    assert any("panjang" in t for t in game_world.bot.texts_to(answerer_chat))


async def test_non_text_message_rejected(game_world, kuis_kenal_game):
    game, session_id, subject_id, subject_chat, answerer_id, answerer_chat = await _get_to_answering(
        game_world, kuis_kenal_game
    )
    from tests.conftest import FakeMessage

    sticker_message = FakeMessage(game_world.bot, answerer_chat, text=None)
    async with game_world.session_factory() as db_session:
        await game_world.manager.handle_message(
            db_session, session_id=session_id, message=sticker_message, acting_user_id=answerer_id
        )
    state = await game_world.get_state(session_id)
    assert state["answer_drafts"] == {}
    assert any("teks" in t for t in game_world.bot.texts_to(answerer_chat))


async def test_subject_message_ignored(game_world, kuis_kenal_game):
    game, session_id, subject_id, subject_chat, answerer_id, answerer_chat = await _get_to_answering(
        game_world, kuis_kenal_game
    )
    # Subjek TIDAK punya konteks privat "answer" aktif (dia yang punya
    # konteks question_select tadi) -- pesan ini seharusnya tidak diproses
    # sebagai jawaban sama sekali.
    await send_private_text(game_world, session_id, "aku curang", user_id=subject_id, chat_id=subject_chat)
    state = await game_world.get_state(session_id)
    assert state["answer_drafts"] == {}


async def test_valid_answer_stored_as_draft_and_prompts_confirmation(game_world, kuis_kenal_game):
    game, session_id, subject_id, subject_chat, answerer_id, answerer_chat = await _get_to_answering(
        game_world, kuis_kenal_game
    )
    await send_private_text(game_world, session_id, "Jawaban valid", user_id=answerer_id, chat_id=answerer_chat)
    state = await game_world.get_state(session_id)
    assert state["answer_drafts"][str(answerer_id)]["text"] == "Jawaban valid"
    assert str(answerer_id) in state["answer_confirmation_message_ids"]
    assert any("Sudah yakin" in t for t in game_world.bot.texts_to(answerer_chat))
