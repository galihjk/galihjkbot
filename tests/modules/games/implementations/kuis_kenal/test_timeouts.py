from __future__ import annotations

from app.core.enums import GameStatus
from app.modules.games.implementations.kuis_kenal import state as game_state
from tests.modules.games.implementations.kuis_kenal.helpers import (
    extract_start_payload,
    fire_round_timeout,
    latest_markup_to,
    open_deep_link,
    send_callback,
    send_private_text,
)


async def test_question_pick_timeout_skips_turn_without_scoring(game_world, kuis_kenal_game):
    game = kuis_kenal_game
    user_ids = await game_world.add_players(3)
    session_id = await game_world.start_game_now("kuis_kenal", user_ids)

    state_before = await game_world.get_state(session_id)
    subject_id = state_before["current_subject_id"]

    await fire_round_timeout(game, game_world, session_id)

    state_after = await game_world.get_state(session_id)
    assert state_after["current_subject_id"] != subject_id  # sudah lanjut ke pemain berikutnya
    assert state_after["round"] == 2
    assert sum(state_after["scores"].values()) == 0

    activity = state_after["activity"][str(subject_id)]
    assert activity["subject_pick_timeouts"] == 1
    assert activity["afk_strikes"] == 1
    assert activity["subject_turns_completed"] == 0

    session = await game_world.get_session(session_id)
    assert session.status == GameStatus.RUNNING.value
    assert any("tidak memilih soal" in t for t in game_world.bot.all_texts)


async def test_answer_timeout_finalizes_with_partial_answers(game_world, kuis_kenal_game):
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
    await send_callback(
        game_world, session_id, f"{round_number}-{state['message_version']}-qp-0",
        message_id=state["subject_private_message_id"], chat_id=subject_chat, user_id=subject_id,
    )

    answerers = [uid for uid in user_ids if uid != subject_id]
    answering_uid, silent_uid = answerers[0], answerers[1]

    state = await game_world.get_state(session_id)
    markup = latest_markup_to(game_world.bot, game_world.telegram_chat_id)
    answer_payload = extract_start_payload(markup)
    chat_id = game_world.telegram_id_of(answering_uid)
    await open_deep_link(game, game_world, session_id, answer_payload, user_id=answering_uid, chat_id=chat_id)
    await send_private_text(game_world, session_id, "jawabanku", user_id=answering_uid, chat_id=chat_id)
    state = await game_world.get_state(session_id)
    await send_callback(
        game_world, session_id, f"{round_number}-0-ac-0",
        message_id=state["answer_confirmation_message_ids"][str(answering_uid)],
        chat_id=chat_id, user_id=answering_uid,
    )

    # silent_uid tidak pernah menjawab -- langsung picu timeout menjawab.
    await fire_round_timeout(game, game_world, session_id)

    state = await game_world.get_state(session_id)
    assert state["phase"] == game_state.Phase.JUDGING.value
    assert state["activity"][str(silent_uid)]["missed_answer_rounds"] == 1
    assert state["activity"][str(answering_uid)]["missed_answer_rounds"] == 0
    assert len(state["answer_groups"]) == 1  # cuma 1 jawaban final yang masuk


async def test_judge_timeout_voids_turn_without_scoring(game_world, kuis_kenal_game):
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
    await send_callback(
        game_world, session_id, f"{round_number}-{state['message_version']}-qp-0",
        message_id=state["subject_private_message_id"], chat_id=subject_chat, user_id=subject_id,
    )

    answerers = [uid for uid in user_ids if uid != subject_id]
    state = await game_world.get_state(session_id)
    markup = latest_markup_to(game_world.bot, game_world.telegram_chat_id)
    answer_payload = extract_start_payload(markup)
    for uid in answerers:
        chat_id = game_world.telegram_id_of(uid)
        await open_deep_link(game, game_world, session_id, answer_payload, user_id=uid, chat_id=chat_id)
        await send_private_text(game_world, session_id, f"jawaban {uid}", user_id=uid, chat_id=chat_id)
        state = await game_world.get_state(session_id)
        await send_callback(
            game_world, session_id, f"{round_number}-0-ac-0",
            message_id=state["answer_confirmation_message_ids"][str(uid)],
            chat_id=chat_id, user_id=uid,
        )

    state = await game_world.get_state(session_id)
    assert state["phase"] == game_state.Phase.JUDGING.value
    # subjek menandai satu jawaban benar tapi TIDAK menekan selesai -- lalu timeout.
    group_id = state["answer_groups"][0]["group_id"]
    await send_callback(
        game_world, session_id, f"{round_number}-{state['message_version']}-jt-{group_id}",
        message_id=state["judging_message_id"], chat_id=subject_chat, user_id=subject_id,
    )

    await fire_round_timeout(game, game_world, session_id)

    state_after = await game_world.get_state(session_id)
    assert sum(state_after["scores"].values()) == 0
    activity = state_after["activity"][str(subject_id)]
    assert activity["judge_timeouts"] == 1
    assert activity["afk_strikes"] == 1
    assert activity["subject_turns_completed"] == 0
    assert state_after["current_subject_id"] != subject_id
