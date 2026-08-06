from __future__ import annotations

from app.core.enums import GamePlayerStatus
from app.database.repositories.game_repository import find_player
from app.modules.games.engine.result import GameResult
from tests.modules.games.implementations.kuis_kenal.test_full_game import _play_one_turn


async def test_active_player_gets_participation_survival_and_result_score(game_world, kuis_kenal_game):
    game = kuis_kenal_game
    user_ids = await game_world.add_players(4)
    session_id = await game_world.start_game_now("kuis_kenal", user_ids)

    for _ in range(4):
        await _play_one_turn(game, game_world, session_id, user_ids)

    async with game_world.session_factory() as db_session:
        from app.database.repositories.game_repository import find_by_id
        from app.modules.games.engine.manager import GameManager

        game_session = await find_by_id(db_session, session_id)
        context = await game_world.manager._build_context(db_session, game_session)
        result = GameResult(winner_user_id=None, summary="test", payload={})
        scores = await game.calculate_scores(context, result)

    for uid in user_ids:
        breakdown = scores[uid]
        # tiap pemain: 1x jadi subjek (survival dari subject_turns_completed)
        # + 3x jadi answerer (confirmed) -- semua aktif, tidak ada yang AFK.
        assert breakdown.participation_score == 10
        assert breakdown.survival_score == 36 * 3 + 44 * 1
        assert breakdown.final_score == breakdown.participation_score + breakdown.survival_score + breakdown.result_score


async def test_afk_player_gets_halved_survival_and_zero_participation(game_world, kuis_kenal_game):
    game = kuis_kenal_game
    user_ids = await game_world.add_players(3)
    session_id = await game_world.start_game_now("kuis_kenal", user_ids)

    from tests.modules.games.implementations.kuis_kenal.helpers import (
        extract_start_payload,
        fire_round_timeout,
        latest_markup_to,
        open_deep_link,
        send_callback,
        send_private_text,
    )

    # Giliran 1: subjek (afk_uid) TIDAK memilih soal sama sekali -- timeout.
    # afk_strikes=1, subject_pick_timeouts=1, subject_turns_completed=0.
    state = await game_world.get_state(session_id)
    afk_uid = state["current_subject_id"]
    await fire_round_timeout(game, game_world, session_id)

    # Giliran 2: subjek berikutnya main normal, TAPI afk_uid sengaja tidak
    # menjawab sama sekali -- answerer lain tetap konfirmasi, lalu timeout
    # menjawab dipicu supaya finalize_answering mencatat missed_answer_rounds
    # untuk afk_uid.
    state = await game_world.get_state(session_id)
    subject2 = state["current_subject_id"]
    round2 = state["round"]
    subject2_chat = game_world.telegram_id_of(subject2)
    markup = latest_markup_to(game_world.bot, game_world.telegram_chat_id)
    payload = extract_start_payload(markup)
    await open_deep_link(game, game_world, session_id, payload, user_id=subject2, chat_id=subject2_chat)
    state = await game_world.get_state(session_id)
    await send_callback(
        game_world, session_id, f"{round2}-{state['message_version']}-qp-0",
        message_id=state["subject_private_message_id"], chat_id=subject2_chat, user_id=subject2,
    )

    other_answerer = next(uid for uid in user_ids if uid not in (afk_uid, subject2))
    other_chat = game_world.telegram_id_of(other_answerer)
    markup = latest_markup_to(game_world.bot, game_world.telegram_chat_id)
    answer_payload = extract_start_payload(markup)
    await open_deep_link(game, game_world, session_id, answer_payload, user_id=other_answerer, chat_id=other_chat)
    await send_private_text(game_world, session_id, "jawaban", user_id=other_answerer, chat_id=other_chat)
    state = await game_world.get_state(session_id)
    await send_callback(
        game_world, session_id, f"{round2}-0-ac-0",
        message_id=state["answer_confirmation_message_ids"][str(other_answerer)],
        chat_id=other_chat, user_id=other_answerer,
    )

    # afk_uid tidak pernah membuka/menjawab -- picu timeout menjawab.
    await fire_round_timeout(game, game_world, session_id)

    state = await game_world.get_state(session_id)
    assert state["activity"][str(afk_uid)]["missed_answer_rounds"] == 1
    judging_msg_id = state["judging_message_id"]
    judge_version = state["message_version"]
    group_id = state["answer_groups"][0]["group_id"]
    await send_callback(
        game_world, session_id, f"{round2}-{judge_version}-jt-{group_id}",
        message_id=judging_msg_id, chat_id=subject2_chat, user_id=subject2,
    )
    await send_callback(
        game_world, session_id, f"{round2}-{judge_version}-jd-0",
        message_id=judging_msg_id, chat_id=subject2_chat, user_id=subject2,
    )

    # Giliran 3 (terakhir, subjek pasti afk_uid ATAU other_answerer -- main
    # normal, tidak relevan lagi buat kriteria AFK afk_uid yang sudah terpenuhi).
    await _play_one_turn(game, game_world, session_id, user_ids)

    async with game_world.session_factory() as db_session:
        from app.database.repositories.game_repository import find_by_id

        game_session = await find_by_id(db_session, session_id)
        state = game_session.state_json
        context = await game_world.manager._build_context(db_session, game_session)
        result = GameResult(winner_user_id=None, summary="test", payload={})
        scores = await game.calculate_scores(context, result)

    activity = state["activity"][str(afk_uid)]
    assert activity["subject_pick_timeouts"] == 1
    assert activity["missed_answer_rounds"] >= 1
    from app.modules.games.implementations.kuis_kenal import state as game_state_mod

    assert game_state_mod.calculate_afk_flags(state)[afk_uid] is True

    breakdown = scores[afk_uid]
    assert breakdown.participation_score == 0
    raw_survival = (
        36 * state["activity"][str(afk_uid)]["answers_confirmed"]
        + 44 * state["activity"][str(afk_uid)]["subject_turns_completed"]
    )
    assert breakdown.survival_score == raw_survival // 2


async def test_calculate_scores_sets_player_status(game_world, kuis_kenal_game):
    game = kuis_kenal_game
    user_ids = await game_world.add_players(3)
    session_id = await game_world.start_game_now("kuis_kenal", user_ids)

    for _ in range(3):
        await _play_one_turn(game, game_world, session_id, user_ids)

    async with game_world.session_factory() as db_session:
        from app.database.repositories.game_repository import find_by_id

        game_session = await find_by_id(db_session, session_id)
        context = await game_world.manager._build_context(db_session, game_session)
        result = GameResult(winner_user_id=user_ids[0], summary="test", payload={})
        await game.calculate_scores(context, result)
        await db_session.commit()

        winner_player = await find_player(db_session, session_id, user_ids[0])
        other_player = await find_player(db_session, session_id, user_ids[1])
        assert winner_player.status == GamePlayerStatus.WINNER.value
        assert other_player.status == GamePlayerStatus.ACTIVE.value
