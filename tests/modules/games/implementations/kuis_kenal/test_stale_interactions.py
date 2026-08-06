from __future__ import annotations

from app.modules.games.implementations.kuis_kenal import state as game_state
from app.modules.games.implementations.kuis_kenal.links import build_deep_link_payload
from tests.modules.games.implementations.kuis_kenal.helpers import (
    extract_start_payload,
    latest_markup_to,
    open_deep_link,
    send_callback,
)


async def test_old_round_callback_is_rejected(game_world, kuis_kenal_game):
    game = kuis_kenal_game
    user_ids = await game_world.add_players(3)
    session_id = await game_world.start_game_now("kuis_kenal", user_ids)

    state = await game_world.get_state(session_id)
    subject_id = state["current_subject_id"]
    subject_chat = game_world.telegram_id_of(subject_id)

    callback = await send_callback(
        game_world, session_id, f"0-{state['message_version']}-qp-0",  # round 0 -- sudah tidak ada
        message_id=state["subject_private_message_id"], chat_id=subject_chat, user_id=subject_id,
    )
    assert callback.answers
    assert callback.answers[-1][1] is True  # show_alert

    # State tidak berubah -- soal belum terpilih.
    state_after = await game_world.get_state(session_id)
    assert state_after["selected_question_id"] is None


async def test_non_authoritative_message_id_is_rejected(game_world, kuis_kenal_game):
    game = kuis_kenal_game
    user_ids = await game_world.add_players(3)
    session_id = await game_world.start_game_now("kuis_kenal", user_ids)

    state = await game_world.get_state(session_id)
    subject_id = state["current_subject_id"]
    subject_chat = game_world.telegram_id_of(subject_id)

    markup = latest_markup_to(game_world.bot, game_world.telegram_chat_id)
    payload = extract_start_payload(markup)
    await open_deep_link(game, game_world, session_id, payload, user_id=subject_id, chat_id=subject_chat)
    state = await game_world.get_state(session_id)
    real_pointer = state["subject_private_message_id"]
    assert real_pointer is not None

    callback = await send_callback(
        game_world, session_id, f"{state['round']}-{state['message_version']}-qp-0",
        message_id=real_pointer + 999, chat_id=subject_chat, user_id=subject_id,
    )
    assert callback.answers[-1][1] is True

    state_after = await game_world.get_state(session_id)
    assert state_after["selected_question_id"] is None


async def test_non_subject_cannot_pick_question(game_world, kuis_kenal_game):
    game = kuis_kenal_game
    user_ids = await game_world.add_players(3)
    session_id = await game_world.start_game_now("kuis_kenal", user_ids)

    state = await game_world.get_state(session_id)
    subject_id = state["current_subject_id"]
    other_uid = next(uid for uid in user_ids if uid != subject_id)
    other_chat = game_world.telegram_id_of(other_uid)

    callback = await send_callback(
        game_world, session_id, f"{state['round']}-{state['message_version']}-qp-0",
        message_id=state["subject_private_message_id"], chat_id=other_chat, user_id=other_uid,
    )
    assert callback.answers[-1][1] is True

    state_after = await game_world.get_state(session_id)
    assert state_after["selected_question_id"] is None


async def test_subject_cannot_open_answer_deep_link_for_own_turn(game_world, kuis_kenal_game):
    game = kuis_kenal_game
    user_ids = await game_world.add_players(3)
    session_id = await game_world.start_game_now("kuis_kenal", user_ids)

    state = await game_world.get_state(session_id)
    subject_id = state["current_subject_id"]
    subject_chat = game_world.telegram_id_of(subject_id)

    payload = build_deep_link_payload("answer", session_id, state["round"], "irrelevantnonce")
    incoming = await open_deep_link(game, game_world, session_id, payload, user_id=subject_id, chat_id=subject_chat)

    texts_sent = game_world.bot.texts_to(subject_chat)
    assert any("tidak berlaku" in t for t in texts_sent)


async def test_non_participant_cannot_use_deep_link(game_world, kuis_kenal_game):
    game = kuis_kenal_game
    user_ids = await game_world.add_players(3)
    session_id = await game_world.start_game_now("kuis_kenal", user_ids)
    outsiders = await game_world.add_players(1, start_index=99)
    outsider_id = outsiders[0]
    outsider_chat = game_world.telegram_id_of(outsider_id)

    state = await game_world.get_state(session_id)
    markup = latest_markup_to(game_world.bot, game_world.telegram_chat_id)
    payload = extract_start_payload(markup)

    await open_deep_link(game, game_world, session_id, payload, user_id=outsider_id, chat_id=outsider_chat)

    texts_sent = game_world.bot.texts_to(outsider_chat)
    assert any("bukan peserta" in t for t in texts_sent)


async def test_reroll_limit_enforced(game_world, kuis_kenal_game):
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
        game_world, session_id, f"{round_number}-{state['message_version']}-qr-0",
        message_id=state["subject_private_message_id"], chat_id=subject_chat, user_id=subject_id,
    )
    state = await game_world.get_state(session_id)
    assert state["question_reroll_count"] == 1

    callback = await send_callback(
        game_world, session_id, f"{round_number}-{state['message_version']}-qr-0",
        message_id=state["subject_private_message_id"], chat_id=subject_chat, user_id=subject_id,
    )
    assert callback.answers[-1][1] is True
    assert "sudah pakai" in callback.answers[-1][0]

    state_after = await game_world.get_state(session_id)
    assert state_after["question_reroll_count"] == 1  # tidak bertambah


async def test_double_click_judgement_done_is_idempotent(game_world, kuis_kenal_game):
    game = kuis_kenal_game
    user_ids = await game_world.add_players(3)
    session_id = await game_world.start_game_now("kuis_kenal", user_ids)

    state = await game_world.get_state(session_id)
    subject_id = state["current_subject_id"]
    subject_chat = game_world.telegram_id_of(subject_id)
    round_number = state["round"]

    from tests.modules.games.implementations.kuis_kenal.helpers import send_private_text

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
    group_id = state["answer_groups"][0]["group_id"]
    judging_msg_id = state["judging_message_id"]
    version = state["message_version"]
    await send_callback(
        game_world, session_id, f"{round_number}-{version}-jt-{group_id}",
        message_id=judging_msg_id, chat_id=subject_chat, user_id=subject_id,
    )

    first = await send_callback(
        game_world, session_id, f"{round_number}-{version}-jd-0",
        message_id=judging_msg_id, chat_id=subject_chat, user_id=subject_id,
    )
    score_after_first = (await game_world.get_state(session_id))["scores"]

    # Klik "jd" kedua (terlambat/dobel) -- fase sudah tidak JUDGING lagi utk
    # ronde ini (sudah advance ke ronde berikutnya), harus ditolak diam-diam
    # tanpa mengubah skor lagi.
    second = await send_callback(
        game_world, session_id, f"{round_number}-{version}-jd-0",
        message_id=judging_msg_id, chat_id=subject_chat, user_id=subject_id,
    )
    score_after_second = (await game_world.get_state(session_id))["scores"]

    assert score_after_first == score_after_second
    assert second.answers[-1][1] is True
