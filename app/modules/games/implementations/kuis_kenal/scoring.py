from __future__ import annotations

from dataclasses import dataclass

from app.modules.games.engine.score import ScoreBreakdown
from app.modules.games.implementations.kuis_kenal import state as game_state

# §18 rencana implementasi -- baseline ±36 poin/menit, disamakan skalanya
# dengan game lain di bot ini (lihat game-development-guide.md §15).
PARTICIPATION_SCORE = 10
SURVIVAL_SCORE_PER_ANSWER = 36
SURVIVAL_SCORE_PER_SUBJECT_TURN = 44
RESULT_SCORE_PER_CORRECT_ANSWER = 36


@dataclass(frozen=True)
class PlayerScoreResult:
    """Hasil skor 1 pemain, plus data tambahan yang dibutuhkan narasi
    tampilan (pesan AFK wajib menyebut angka penalti eksplisit, bukan cuma
    label "AFK" -- pola sama seperti Kursi Kosong)."""

    breakdown: ScoreBreakdown
    is_afk: bool
    penalty: int | None  # None kalau bukan AFK


def compute_scores(state: dict) -> dict[int, PlayerScoreResult]:
    """Hitung skor leaderboard akhir tiap pemain dari `state["activity"]`
    sesuai formula §18 rencana. Murni -- tidak sentuh DB/Telegram, gampang
    ditest. Dipakai baik untuk commit ke `user_game_scores`
    (`KuisKenalGame.calculate_scores`) maupun untuk pesan hasil akhir yang
    dilihat pemain (`_finish_game`) -- SATU sumber kebenaran supaya angka
    yang ditampilkan selalu sama persis dengan yang benar-benar dicatat."""
    afk_flags = game_state.calculate_afk_flags(state)
    results: dict[int, PlayerScoreResult] = {}

    for uid in state["all_user_ids"]:
        activity = state["activity"].get(str(uid), {})
        is_afk = afk_flags.get(uid, False)

        raw_participation = PARTICIPATION_SCORE if activity.get("valid_actions", 0) > 0 else 0
        raw_survival = (
            SURVIVAL_SCORE_PER_ANSWER * activity.get("answers_confirmed", 0)
            + SURVIVAL_SCORE_PER_SUBJECT_TURN * activity.get("subject_turns_completed", 0)
        )
        raw_result = RESULT_SCORE_PER_CORRECT_ANSWER * activity.get("correct_answers", 0)
        raw_final = raw_participation + raw_survival + raw_result

        if is_afk:
            # §18.3 rencana: floor(raw x 0,5) -- pakai // langsung (bukan
            # round(raw * AFK_PENALTY_RATIO)) supaya tidak ada potensi salah
            # pembulatan dari representasi float 0,5.
            participation = 0
            survival = raw_survival // 2
            result_score = raw_result // 2
        else:
            participation = raw_participation
            survival = raw_survival
            result_score = raw_result

        final_score = participation + survival + result_score
        penalty = raw_final - final_score if is_afk else None

        results[uid] = PlayerScoreResult(
            breakdown=ScoreBreakdown(
                result_score=result_score,
                participation_score=participation,
                survival_score=survival,
                final_score=final_score,
            ),
            is_afk=is_afk,
            penalty=penalty,
        )

    return results
