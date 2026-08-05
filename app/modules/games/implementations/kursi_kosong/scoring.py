from __future__ import annotations

from dataclasses import dataclass

from app.core.enums import GamePlayerStatus
from app.modules.games.engine.score import ScoreBreakdown

PARTICIPATION_SCORE = 10
SURVIVAL_SCORE_PER_ROUND = 5
RESULT_SCORE_TIERS = [60, 40, 25]  # index 0 = Juara 1, dst (§27 desain)
RESULT_SCORE_DEFAULT = 10
AFK_PENALTY_BASE = 10
AFK_PENALTY_RATIO = 0.5

# §30 desain: faktor jumlah pemain AWAL (bukan jumlah yang masih hidup).
PLAYER_COUNT_FACTORS = [
    (4, 1.00),  # 3-4 pemain
    (6, 1.15),  # 5-6 pemain
    (8, 1.30),  # 7-8 pemain
]


def player_count_factor(initial_player_count: int) -> float:
    for max_count, factor in PLAYER_COUNT_FACTORS:
        if initial_player_count <= max_count:
            return factor
    return PLAYER_COUNT_FACTORS[-1][1]


@dataclass(frozen=True)
class PlayerOutcome:
    """Input murni untuk `compute_scores` -- 1 per pemain yang pernah ikut sesi."""

    user_id: int
    status: str  # GamePlayerStatus.WINNER/ELIMINATED/AFK.value
    eliminated_round: int | None  # None untuk WINNER
    final_round: int  # ronde terakhir sesi ini berjalan (utk ketahanan WINNER)
    initial_player_count: int


@dataclass(frozen=True)
class PlayerScoreResult:
    """Hasil skor 1 pemain, plus data tambahan yang dibutuhkan narasi tampilan
    (§45 desain: pesan AFK wajib menyebut angka penalti & jumlah ronde, bukan
    cuma skor akhirnya)."""

    breakdown: ScoreBreakdown
    rounds_passed: int
    penalty: int | None  # None kalau bukan AFK


def compute_scores(outcomes: list[PlayerOutcome]) -> dict[int, PlayerScoreResult]:
    """Hitung skor akhir tiap pemain sesuai §26-31 & §19 (revisi penalti AFK
    parsial) desain. Murni -- tidak sentuh DB/Telegram, gampang ditest.

    Ranking skor_hasil (§27) dihitung dari RONDE eliminasi (bukan jumlah
    pemain) supaya kompatibel dengan revisi aturan eliminasi (>1 pemain bisa
    tereliminasi bersamaan di ronde yang sama) -- yang seri di ronde yang
    sama dapat TIER YANG SAMA, tidak dipisah/dirata-rata (dikonfirmasi user).
    """
    winners = [o for o in outcomes if o.status == GamePlayerStatus.WINNER.value]
    eliminated_normal = [o for o in outcomes if o.status == GamePlayerStatus.ELIMINATED.value]
    afk = [o for o in outcomes if o.status == GamePlayerStatus.AFK.value]

    result_score_by_uid: dict[int, int] = {}
    for o in winners:
        result_score_by_uid[o.user_id] = RESULT_SCORE_TIERS[0]

    rounds_desc = sorted({o.eliminated_round for o in eliminated_normal}, reverse=True)
    for tier_index, round_number in enumerate(rounds_desc, start=1):
        tier_score = (
            RESULT_SCORE_TIERS[tier_index]
            if tier_index < len(RESULT_SCORE_TIERS)
            else RESULT_SCORE_DEFAULT
        )
        for o in eliminated_normal:
            if o.eliminated_round == round_number:
                result_score_by_uid[o.user_id] = tier_score

    results: dict[int, PlayerScoreResult] = {}

    for o in winners + eliminated_normal:
        factor = player_count_factor(o.initial_player_count)
        rounds_passed = o.final_round if o.status == GamePlayerStatus.WINNER.value else o.eliminated_round - 1
        result_score = result_score_by_uid[o.user_id]
        participation_score = PARTICIPATION_SCORE
        survival_score = SURVIVAL_SCORE_PER_ROUND * rounds_passed
        session_score = result_score + participation_score + survival_score
        final_score = round(session_score * factor)
        results[o.user_id] = PlayerScoreResult(
            breakdown=ScoreBreakdown(
                result_score=result_score,
                participation_score=participation_score,
                survival_score=survival_score,
                final_score=final_score,
            ),
            rounds_passed=rounds_passed,
            penalty=None,
        )

    for o in afk:
        factor = player_count_factor(o.initial_player_count)
        rounds_passed = (o.eliminated_round - 1) if o.eliminated_round is not None else 0
        survival_score = SURVIVAL_SCORE_PER_ROUND * rounds_passed
        penalty = round(AFK_PENALTY_BASE + AFK_PENALTY_RATIO * survival_score)
        # Bentuk sederhana (§19): skor_sesi_afk = 0,5 x skor_ketahanan_afk --
        # setara (participation_placeholder=10 + 0 + survival) - penalty.
        session_score = AFK_PENALTY_RATIO * survival_score
        final_score = round(session_score * factor)
        results[o.user_id] = PlayerScoreResult(
            breakdown=ScoreBreakdown(
                result_score=0,
                participation_score=0,
                survival_score=survival_score,
                final_score=final_score,
            ),
            rounds_passed=rounds_passed,
            penalty=penalty,
        )

    return results
