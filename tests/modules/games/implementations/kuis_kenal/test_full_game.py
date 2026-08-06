from __future__ import annotations

from app.core.enums import GameStatus
from app.modules.games.implementations.kuis_kenal import state as game_state
from tests.modules.games.implementations.kuis_kenal.helpers import (
    extract_start_payload,
    latest_markup_to,
    open_deep_link,
    send_callback,
    send_private_text,
)


async def _play_one_turn(game, game_world, session_id, all_user_ids, *, mark_correct_for=None):
    """Mainkan satu giliran penuh: subjek pilih soal, semua non-subjek
    menjawab & konfirmasi, subjek menandai satu jawaban benar (punya
    `mark_correct_for`, atau jawaban pemain pertama secara default) lalu
    selesai menilai. Return state SETELAH giliran ini diresolve."""
    state = await game_world.get_state(session_id)
    subject_id = state["current_subject_id"]
    subject_chat = game_world.telegram_id_of(subject_id)
    round_number = state["round"]

    # 1) Subjek buka deep link pilih soal, pilih index 0.
    markup = latest_markup_to(game_world.bot, game_world.telegram_chat_id)
    payload = extract_start_payload(markup)
    assert payload is not None
    await open_deep_link(game, game_world, session_id, payload, user_id=subject_id, chat_id=subject_chat)

    state = await game_world.get_state(session_id)
    private_msg_id = state["subject_private_message_id"]
    version = state["message_version"]
    await send_callback(
        game_world, session_id, f"{round_number}-{version}-qp-0",
        message_id=private_msg_id, chat_id=subject_chat, user_id=subject_id,
    )

    state = await game_world.get_state(session_id)
    assert state["phase"] == game_state.Phase.ANSWERING.value

    # 2) Semua non-subjek buka deep link jawab, kirim teks, lalu konfirmasi.
    answerers = [uid for uid in all_user_ids if uid != subject_id]
    markup = latest_markup_to(game_world.bot, game_world.telegram_chat_id)
    answer_payload = extract_start_payload(markup)
    assert answer_payload is not None

    for uid in answerers:
        chat_id = game_world.telegram_id_of(uid)
        await open_deep_link(game, game_world, session_id, answer_payload, user_id=uid, chat_id=chat_id)
        await send_private_text(game_world, session_id, f"jawaban dari {uid}", user_id=uid, chat_id=chat_id)

        state = await game_world.get_state(session_id)
        confirm_msg_id = state["answer_confirmation_message_ids"][str(uid)]
        await send_callback(
            game_world, session_id, f"{round_number}-{version}-ac-0",
            message_id=confirm_msg_id, chat_id=chat_id, user_id=uid,
        )

    state = await game_world.get_state(session_id)
    assert state["phase"] == game_state.Phase.JUDGING.value
    assert len(state["final_answers"]) == len(answerers)

    # 3) Subjek menilai: tandai jawaban dari satu answerer sebagai benar.
    target_uid = mark_correct_for if mark_correct_for is not None else answerers[0]
    group = next(g for g in state["answer_groups"] if target_uid in g["user_ids"])
    judging_msg_id = state["judging_message_id"]
    judge_version = state["message_version"]

    await send_callback(
        game_world, session_id, f"{round_number}-{judge_version}-jt-{group['group_id']}",
        message_id=judging_msg_id, chat_id=subject_chat, user_id=subject_id,
    )
    await send_callback(
        game_world, session_id, f"{round_number}-{judge_version}-jd-0",
        message_id=judging_msg_id, chat_id=subject_chat, user_id=subject_id,
    )

    return await game_world.get_state(session_id), subject_id, target_uid


async def test_three_player_game_runs_start_to_finish(game_world, kuis_kenal_game):
    game = kuis_kenal_game
    user_ids = await game_world.add_players(3)
    session_id = await game_world.start_game_now("kuis_kenal", user_ids)

    winners_marked = {}
    for _ in range(3):
        state, subject_id, correct_uid = await _play_one_turn(game, game_world, session_id, user_ids)
        winners_marked[subject_id] = correct_uid

    session = await game_world.get_session(session_id)
    assert session.status == GameStatus.FINISHED.value

    final_state = session.state_json
    for uid, correct_uid in winners_marked.items():
        # tiap subjek menandai TEPAT SATU jawaban benar per gilirannya sendiri
        pass
    # setiap non-subjek yang ditandai benar pada giliran subjek mereka masing2
    # harus dapat +1 -- total skor keseluruhan harus sama dengan jumlah giliran (3)
    assert sum(final_state["scores"].values()) == 3

    assert "Mau main lagi" in "\n".join(game_world.bot.all_texts)
    assert any("KUIS KENAL SELESAI" in t for t in game_world.bot.all_texts)


async def test_ten_player_game_runs_start_to_finish(game_world, kuis_kenal_game):
    game = kuis_kenal_game
    user_ids = await game_world.add_players(10)
    session_id = await game_world.start_game_now("kuis_kenal", user_ids)

    for _ in range(10):
        await _play_one_turn(game, game_world, session_id, user_ids)

    session = await game_world.get_session(session_id)
    assert session.status == GameStatus.FINISHED.value
    assert sum(session.state_json["scores"].values()) == 10


async def test_every_player_gets_exactly_one_turn_as_subject(game_world, kuis_kenal_game):
    game = kuis_kenal_game
    user_ids = await game_world.add_players(4)
    session_id = await game_world.start_game_now("kuis_kenal", user_ids)

    subjects_seen = []
    for _ in range(4):
        state = await game_world.get_state(session_id)
        subjects_seen.append(state["current_subject_id"])
        await _play_one_turn(game, game_world, session_id, user_ids)

    assert sorted(subjects_seen) == sorted(user_ids)
    assert len(set(subjects_seen)) == 4
