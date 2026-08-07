from __future__ import annotations

from app.modules.games.engine.context import PlayerInfo
from app.modules.games.implementations.kuis_kenal import scoring
from app.modules.games.implementations.kuis_kenal import state as s
from app.modules.games.implementations.kuis_kenal import texts


def _player(uid: int, name: str) -> PlayerInfo:
    return PlayerInfo(user_id=uid, telegram_user_id=uid, display_name=name)


def test_compute_scores_active_player():
    state = s.build_initial_state([1, 2, 3])
    state["activity"]["1"] = {
        "valid_actions": 4, "answers_confirmed": 2, "correct_answers": 1,
        "subject_turns_completed": 1, "missed_answer_rounds": 0,
        "subject_pick_timeouts": 0, "judge_timeouts": 0, "afk_strikes": 0,
    }

    results = scoring.compute_scores(state)
    res = results[1]

    assert res.is_afk is False
    assert res.penalty is None
    assert res.breakdown.participation_score == 10
    assert res.breakdown.survival_score == 36 * 2 + 44 * 1
    assert res.breakdown.result_score == 36 * 1
    assert res.breakdown.final_score == 10 + (36 * 2 + 44 * 1) + 36


def test_compute_scores_afk_player_gets_penalty():
    state = s.build_initial_state([1, 2, 3])
    # afk_strikes>=2 -- salah satu kriteria §7.4, paling gampang dites langsung.
    state["activity"]["1"] = {
        "valid_actions": 2, "answers_confirmed": 1, "correct_answers": 1,
        "subject_turns_completed": 0, "missed_answer_rounds": 0,
        "subject_pick_timeouts": 0, "judge_timeouts": 0, "afk_strikes": 2,
    }

    results = scoring.compute_scores(state)
    res = results[1]

    assert res.is_afk is True
    raw_survival = 36 * 1
    raw_result = 36 * 1
    raw_participation = 10
    assert res.breakdown.participation_score == 0
    assert res.breakdown.survival_score == round(raw_survival * 0.5)
    assert res.breakdown.result_score == round(raw_result * 0.5)
    expected_final = res.breakdown.survival_score + res.breakdown.result_score
    assert res.breakdown.final_score == expected_final
    assert res.penalty == (raw_participation + raw_survival + raw_result) - expected_final


def test_compute_scores_never_active_player_gets_zero():
    state = s.build_initial_state([1, 2, 3])
    results = scoring.compute_scores(state)
    res = results[1]
    assert res.is_afk is True  # tidak ada aksi valid sama sekali
    assert res.breakdown.final_score == 0
    assert res.penalty == 0


def test_render_final_leaderboard_uses_medals_and_afk_penalty():
    winner = _player(1, "Virtual Player 2")
    runner_up = _player(2, "Galih JK DEV")
    afk_player = _player(3, "Virtual Player 1")

    entries = [
        (winner, scoring.PlayerScoreResult(
            breakdown=_breakdown(30), is_afk=False, penalty=None,
        )),
        (runner_up, scoring.PlayerScoreResult(
            breakdown=_breakdown(20), is_afk=False, penalty=None,
        )),
        (afk_player, scoring.PlayerScoreResult(
            breakdown=_breakdown(2), is_afk=True, penalty=10,
        )),
    ]

    text = texts.render_final_leaderboard(entries)
    lines = text.splitlines()

    assert lines[0] == "📊 Perolehan Skor:"
    assert "🥇" in lines[1] and "30 poin" in lines[1] and "Virtual Player 2" in lines[1]
    assert "🥈" in lines[2] and "20 poin" in lines[2]
    assert "💤" in lines[3] and "(Penalti AFK 10 poin)" in lines[3] and "2 poin" in lines[3]
    # Label lama ("Skor sementara") tidak boleh muncul di hasil akhir.
    assert "sementara" not in text.lower()


def test_render_final_result_combines_winner_line_and_leaderboard():
    winner = _player(1, "Virtual Player 2")
    text = texts.render_final_result(
        winner_rankings=[(winner, 2)],
        winner_ids=[1],
        leaderboard_entries=[(winner, scoring.PlayerScoreResult(
            breakdown=_breakdown(30), is_afk=False, penalty=None,
        ))],
    )
    assert "🏁 KUIS KENAL SELESAI!" in text
    assert "menang!" in text
    assert "📊 Perolehan Skor:" in text
    assert "sementara" not in text.lower()


def _breakdown(final_score: int):
    from app.modules.games.engine.score import ScoreBreakdown

    return ScoreBreakdown(
        result_score=0, participation_score=0, survival_score=0, final_score=final_score,
    )
