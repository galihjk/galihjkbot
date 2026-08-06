from __future__ import annotations

import asyncio

from app.modules.games.implementations.kuis_kenal import state as game_state
from tests.modules.games.implementations.kuis_kenal.helpers import (
    extract_start_payload,
    latest_markup_to,
    open_deep_link,
    send_callback,
    send_private_text,
)


async def _reach_answering(game_world, kuis_kenal_game, n=3):
    game = kuis_kenal_game
    user_ids = await game_world.add_players(n)
    session_id = await game_world.start_game_now("kuis_kenal", user_ids)

    state = await game_world.get_state(session_id)
    subject_id = state["current_subject_id"]
    subject_chat = game_world.telegram_id_of(subject_id)
    round_number = state["round"]

    markup = latest_markup_to(game_world.bot, game_world.telegram_chat_id)
    payload = extract_start_payload(markup)
    await open_deep_link(game, game_world, session_id, payload, user_id=subject_id, chat_id=subject_chat)
    state = await game_world.get_state(session_id)
    await send_callback(
        game_world, session_id, f"{round_number}-{state['message_version']}-qp-0",
        message_id=state["subject_private_message_id"], chat_id=subject_chat, user_id=subject_id,
    )
    return game, session_id, user_ids, subject_id, round_number


async def test_two_players_confirm_answers_concurrently(game_world, kuis_kenal_game):
    game, session_id, user_ids, subject_id, round_number = await _reach_answering(game_world, kuis_kenal_game, n=3)
    answerers = [uid for uid in user_ids if uid != subject_id]

    markup = latest_markup_to(game_world.bot, game_world.telegram_chat_id)
    answer_payload = extract_start_payload(markup)
    for uid in answerers:
        chat_id = game_world.telegram_id_of(uid)
        await open_deep_link(game, game_world, session_id, answer_payload, user_id=uid, chat_id=chat_id)
        await send_private_text(game_world, session_id, f"jawaban {uid}", user_id=uid, chat_id=chat_id)

    state = await game_world.get_state(session_id)
    pointers = state["answer_confirmation_message_ids"]

    async def _confirm(uid):
        chat_id = game_world.telegram_id_of(uid)
        await send_callback(
            game_world, session_id, f"{round_number}-0-ac-0",
            message_id=pointers[str(uid)], chat_id=chat_id, user_id=uid,
        )

    await asyncio.gather(*(_confirm(uid) for uid in answerers))

    state = await game_world.get_state(session_id)
    # Kedua jawaban tercatat FINAL persis sekali, tidak ada yang hilang/dobel,
    # dan fase sudah lanjut ke judging (semua jawaban sudah masuk).
    assert len(state["final_answers"]) == len(answerers)
    for uid in answerers:
        assert state["final_answers"][str(uid)]["text"] == f"jawaban {uid}"
    assert state["phase"] == game_state.Phase.JUDGING.value
    assert len(state["answer_groups"]) == len(answerers)


async def test_double_click_confirm_only_applies_once(game_world, kuis_kenal_game):
    game, session_id, user_ids, subject_id, round_number = await _reach_answering(game_world, kuis_kenal_game, n=3)
    answerer = next(uid for uid in user_ids if uid != subject_id)
    chat_id = game_world.telegram_id_of(answerer)

    markup = latest_markup_to(game_world.bot, game_world.telegram_chat_id)
    answer_payload = extract_start_payload(markup)
    await open_deep_link(game, game_world, session_id, answer_payload, user_id=answerer, chat_id=chat_id)
    await send_private_text(game_world, session_id, "jawabanku", user_id=answerer, chat_id=chat_id)

    state = await game_world.get_state(session_id)
    pointer = state["answer_confirmation_message_ids"][str(answerer)]

    async def _confirm():
        await send_callback(
            game_world, session_id, f"{round_number}-0-ac-0",
            message_id=pointer, chat_id=chat_id, user_id=answerer,
        )

    results = await asyncio.gather(_confirm(), _confirm(), return_exceptions=True)
    for r in results:
        assert not isinstance(r, Exception)

    state = await game_world.get_state(session_id)
    assert state["activity"][str(answerer)]["answers_confirmed"] == 1


async def test_two_concurrent_question_picks_only_one_wins(game_world, kuis_kenal_game):
    game, session_id, user_ids, subject_id, round_number = await _reach_answering(game_world, kuis_kenal_game, n=3)
    # _reach_answering sudah memilih soal index 0 -- simulasikan klik dobel
    # lain ke index 1 SETELAH itu (skenario: dua callback index berbeda
    # nyaris bersamaan sebelum salah satu diproses). Karena keduanya
    # diserialkan lewat lock session yang sama, klik kedua harus ditolak
    # (fase sudah ANSWERING, bukan lagi QUESTION_SELECT).
    state = await game_world.get_state(session_id)
    assert state["phase"] == game_state.Phase.ANSWERING.value
    subject_chat = game_world.telegram_id_of(subject_id)

    callback = await send_callback(
        game_world, session_id, f"{round_number}-{state['message_version']}-qp-1",
        message_id=state["subject_private_message_id"], chat_id=subject_chat, user_id=subject_id,
    )
    assert callback.answers[-1][1] is True  # ditolak, show_alert

    state_after = await game_world.get_state(session_id)
    assert state_after["selected_question_id"] == state["selected_question_id"]  # tidak berubah
