from __future__ import annotations

import random

import pytest

from app.modules.games.implementations.kuis_kenal import state as s


def build_state(n=3):
    return s.build_initial_state(list(range(1, n + 1)), rng=random.Random(0))


def test_build_initial_state_shape():
    state = build_state(3)
    assert set(state["all_user_ids"]) == {1, 2, 3}
    assert sorted(state["turn_queue"]) == [1, 2, 3]
    assert state["current_subject_id"] is None
    assert state["round"] == 0
    assert state["scores"] == {"1": 0, "2": 0, "3": 0}


def test_begin_turn_pops_queue_and_increments_round():
    state = build_state(3)
    first_subject = state["turn_queue"][0]
    s.begin_turn(state)
    assert state["current_subject_id"] == first_subject
    assert state["round"] == 1
    assert len(state["turn_queue"]) == 2
    assert first_subject not in state["turn_queue"]


def test_begin_turn_raises_when_queue_empty():
    state = build_state(1)
    state["turn_queue"] = []
    with pytest.raises(ValueError):
        s.begin_turn(state)


def test_expected_answerer_ids_excludes_subject():
    state = build_state(3)
    s.begin_turn(state)
    expected = s.expected_answerer_ids(state)
    assert state["current_subject_id"] not in expected
    assert len(expected) == 2


def test_offer_then_select_question_marks_used_and_moves_phase():
    state = build_state(3)
    s.begin_turn(state)
    s.offer_questions(state, ["q1", "q2", "q3", "q4", "q5"])
    assert state["question_nonce"] is not None

    s.select_question(state, "q2")
    assert state["selected_question_id"] == "q2"
    assert state["phase"] == s.Phase.ANSWERING.value
    assert set(state["used_question_ids"]) == {"q1", "q2", "q3", "q4", "q5"}
    assert state["answer_nonce"] is not None

    subject_activity = state["activity"][str(state["current_subject_id"])]
    assert subject_activity["valid_actions"] == 1


def test_select_question_rejects_unoffered_id():
    state = build_state(3)
    s.begin_turn(state)
    s.offer_questions(state, ["q1", "q2"])
    with pytest.raises(ValueError):
        s.select_question(state, "not-offered")


def test_reroll_marks_old_offered_as_used_and_respects_limit():
    state = build_state(3)
    s.begin_turn(state)
    s.offer_questions(state, ["q1", "q2", "q3", "q4", "q5"])
    s.reroll_questions(state, ["q6", "q7", "q8", "q9", "q10"], reroll_limit=1)
    assert set(state["used_question_ids"]) == {"q1", "q2", "q3", "q4", "q5"}
    assert state["offered_question_ids"] == ["q6", "q7", "q8", "q9", "q10"]

    with pytest.raises(ValueError):
        s.reroll_questions(state, ["q11"], reroll_limit=1)


def test_record_subject_pick_timeout_does_not_touch_scores():
    state = build_state(3)
    s.begin_turn(state)
    s.record_subject_pick_timeout(state)
    subject_activity = state["activity"][str(state["current_subject_id"])]
    assert subject_activity["subject_pick_timeouts"] == 1
    assert subject_activity["afk_strikes"] == 1
    assert subject_activity["subject_turns_completed"] == 0
    assert state["phase"] == s.Phase.RESOLVING.value


def test_answer_draft_then_confirm_flow():
    state = build_state(3)
    s.begin_turn(state)
    s.offer_questions(state, ["q1"])
    s.select_question(state, "q1")
    answerers = s.expected_answerer_ids(state)
    uid = answerers[0]

    assert s.get_answer_draft(state, uid) is None
    s.store_answer_draft(state, uid, "Jawaban pertama")
    draft = s.get_answer_draft(state, uid)
    assert draft["text"] == "Jawaban pertama"
    assert draft["revision"] == 1

    s.store_answer_draft(state, uid, "Jawaban revisi")
    draft = s.get_answer_draft(state, uid)
    assert draft["revision"] == 2

    assert not s.has_confirmed_answer(state, uid)
    s.confirm_answer(state, uid)
    assert s.has_confirmed_answer(state, uid)
    assert state["final_answers"][str(uid)]["text"] == "Jawaban revisi"
    assert state["activity"][str(uid)]["answers_confirmed"] == 1


def test_confirm_answer_without_draft_raises():
    state = build_state(3)
    s.begin_turn(state)
    with pytest.raises(ValueError):
        s.confirm_answer(state, state["all_user_ids"][0])


def test_all_expected_answers_confirmed():
    state = build_state(3)
    s.begin_turn(state)
    answerers = s.expected_answerer_ids(state)
    assert not s.all_expected_answers_confirmed(state)
    for uid in answerers:
        s.store_answer_draft(state, uid, f"jawaban {uid}")
        s.confirm_answer(state, uid)
    assert s.all_expected_answers_confirmed(state)


def test_finalize_answering_marks_missed_and_builds_groups():
    state = build_state(3)
    s.begin_turn(state)
    answerers = s.expected_answerer_ids(state)
    answered_uid, missed_uid = answerers[0], answerers[1]
    s.store_answer_draft(state, answered_uid, "Jawaban A")
    s.confirm_answer(state, answered_uid)

    s.finalize_answering(state)

    assert state["activity"][str(missed_uid)]["missed_answer_rounds"] == 1
    assert state["activity"][str(answered_uid)]["missed_answer_rounds"] == 0
    assert state["phase"] == s.Phase.JUDGING.value
    assert len(state["answer_groups"]) == 1
    assert state["answer_groups"][0]["user_ids"] == [answered_uid]


def test_build_answer_groups_generates_judge_nonce():
    # Regresi: judge_nonce sempat tidak pernah digenerate sama sekali (selalu
    # None), bikin deep link kk-j selalu ditolak "tidak berlaku" apa pun
    # nonce yang dikirim.
    state = build_state(3)
    s.begin_turn(state)
    assert state["judge_nonce"] is None

    answerers = s.expected_answerer_ids(state)
    s.store_answer_draft(state, answerers[0], "jawaban")
    s.confirm_answer(state, answerers[0])
    s.finalize_answering(state)

    assert isinstance(state["judge_nonce"], str)
    assert state["judge_nonce"]


def test_build_answer_groups_groups_by_normalized_text():
    state = build_state(4)
    s.begin_turn(state)
    answerers = s.expected_answerer_ids(state)
    s.store_answer_draft(state, answerers[0], "Kabur ke warung")
    s.confirm_answer(state, answerers[0])
    s.store_answer_draft(state, answerers[1], "  KABUR ke warung  ")
    s.confirm_answer(state, answerers[1])
    s.store_answer_draft(state, answerers[2], "Tidur")
    s.confirm_answer(state, answerers[2])

    s.build_answer_groups(state)

    groups = state["answer_groups"]
    assert len(groups) == 2
    kabur_group = next(g for g in groups if g["display_text"] == "Kabur ke warung")
    assert sorted(kabur_group["user_ids"]) == sorted([answerers[0], answerers[1]])


def test_toggle_answer_group_flips_and_has_any_correct():
    state = build_state(3)
    s.begin_turn(state)
    answerers = s.expected_answerer_ids(state)
    s.store_answer_draft(state, answerers[0], "jawaban")
    s.confirm_answer(state, answerers[0])
    s.build_answer_groups(state)
    group_id = state["answer_groups"][0]["group_id"]

    assert not s.has_any_correct_group(state)
    s.toggle_answer_group(state, group_id)
    assert s.has_any_correct_group(state)
    s.toggle_answer_group(state, group_id)
    assert not s.has_any_correct_group(state)


def test_toggle_unknown_group_raises():
    state = build_state(3)
    s.begin_turn(state)
    with pytest.raises(ValueError):
        s.toggle_answer_group(state, 999)


def test_record_judge_timeout_voids_turn():
    state = build_state(3)
    s.begin_turn(state)
    answerers = s.expected_answerer_ids(state)
    s.store_answer_draft(state, answerers[0], "jawaban")
    s.confirm_answer(state, answerers[0])
    s.build_answer_groups(state)
    s.toggle_answer_group(state, state["answer_groups"][0]["group_id"])

    s.record_judge_timeout(state)

    assert state["phase"] == s.Phase.RESOLVING.value
    assert state["scores"][str(answerers[0])] == 0  # tidak diproses ke skor
    subject_activity = state["activity"][str(state["current_subject_id"])]
    assert subject_activity["judge_timeouts"] == 1
    assert subject_activity["subject_turns_completed"] == 0


def test_resolve_turn_awards_points_for_correct_groups_only():
    state = build_state(4)
    s.begin_turn(state)
    answerers = s.expected_answerer_ids(state)
    correct_uid, wrong_uid, missing_uid = answerers[0], answerers[1], answerers[2]
    s.store_answer_draft(state, correct_uid, "benar")
    s.confirm_answer(state, correct_uid)
    s.store_answer_draft(state, wrong_uid, "salah")
    s.confirm_answer(state, wrong_uid)
    s.finalize_answering(state)

    correct_group = next(
        g for g in state["answer_groups"] if g["user_ids"] == [correct_uid]
    )
    s.toggle_answer_group(state, correct_group["group_id"])

    summary = s.resolve_turn(state)

    assert state["scores"][str(correct_uid)] == 1
    assert state["scores"][str(wrong_uid)] == 0
    assert state["activity"][str(correct_uid)]["correct_answers"] == 1
    subject_activity = state["activity"][str(state["current_subject_id"])]
    assert subject_activity["subject_turns_completed"] == 1

    successful_ids = [uid for uid, _ in summary["successful"]]
    failed_ids = [uid for uid, _ in summary["failed"]]
    assert successful_ids == [correct_uid]
    assert wrong_uid in failed_ids
    assert missing_uid in failed_ids
    failed_texts = dict(summary["failed"])
    assert failed_texts[missing_uid] is None
    assert failed_texts[wrong_uid] == "salah"


def test_advance_turn_resets_transitional_markers():
    state = build_state(3)
    s.begin_turn(state)
    s.record_subject_pick_timeout(state)
    s.advance_turn(state)
    assert state["current_subject_id"] is None
    assert state["phase"] == s.Phase.QUESTION_SELECT.value


def test_is_game_complete_after_all_turns_begun():
    state = build_state(2)
    assert not s.is_game_complete(state)
    s.begin_turn(state)
    assert not s.is_game_complete(state)
    s.begin_turn(state)
    assert s.is_game_complete(state)


def test_build_result_payload_single_winner():
    state = build_state(3)
    state["scores"] = {"1": 3, "2": 1, "3": 0}
    payload = s.build_result_payload(state)
    assert payload["winner_user_ids"] == [1]


def test_build_result_payload_tie():
    state = build_state(3)
    state["scores"] = {"1": 2, "2": 2, "3": 0}
    payload = s.build_result_payload(state)
    assert sorted(payload["winner_user_ids"]) == [1, 2]


def test_calculate_afk_flags_no_action_at_all():
    state = build_state(3)
    flags = s.calculate_afk_flags(state)
    assert all(flags.values())  # belum ada aksi apa pun sama sekali


def test_calculate_afk_flags_active_player_not_flagged():
    state = build_state(3)
    s.begin_turn(state)
    answerers = s.expected_answerer_ids(state)
    for uid in answerers:
        s.store_answer_draft(state, uid, "jawaban")
        s.confirm_answer(state, uid)
    s.offer_questions(state, ["q1"])
    s.select_question(state, "q1")

    flags = s.calculate_afk_flags(state)
    assert flags[answerers[0]] is False
    assert flags[answerers[1]] is False
    assert flags[state["current_subject_id"]] is False


def test_calculate_afk_flags_many_strikes():
    state = build_state(3)
    uid = state["all_user_ids"][0]
    state["activity"][str(uid)]["valid_actions"] = 1
    state["activity"][str(uid)]["afk_strikes"] = 2
    flags = s.calculate_afk_flags(state)
    assert flags[uid] is True


def test_normalize_answer_text():
    assert s.normalize_answer_text("  KABUR   ke Warung  ") == "kabur ke warung"
