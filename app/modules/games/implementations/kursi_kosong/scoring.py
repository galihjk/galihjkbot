from __future__ import annotations

from dataclasses import dataclass

from app.core.enums import GamePlayerStatus
from app.modules.games.engine.score import ScoreBreakdown

PARTICIPATION_SCORE = 10
SURVIVAL_SCORE_PER_ROUND = 10  # dinaikkan dari 5 -- lihat development-history.md
                                 # (revisi fairness poin/menit lintas-game)
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
    """Hitung skor akhir tiap pemain sesuai §28-31 & §19 (revisi penalti AFK
    parsial) desain. Murni -- tidak sentuh DB/Telegram, gampang ditest.

    Skor hasil (ranking juara) SENGAJA DIHAPUS (revisi fairness poin/menit
    lintas-game, lihat development-history.md) -- "menang" sekarang murni
    soal skor_ketahanan (1 ronde lebih lama dari runner-up), bukan lompatan
    tier terpisah. `result_score` tetap ada di `ScoreBreakdown` (kontrak
    generik engine) tapi selalu 0 untuk game ini.
    """
    winners = [o for o in outcomes if o.status == GamePlayerStatus.WINNER.value]
    eliminated_normal = [o for o in outcomes if o.status == GamePlayerStatus.ELIMINATED.value]
    afk = [o for o in outcomes if o.status == GamePlayerStatus.AFK.value]

    results: dict[int, PlayerScoreResult] = {}

    for o in winners + eliminated_normal:
        factor = player_count_factor(o.initial_player_count)
        rounds_passed = o.final_round if o.status == GamePlayerStatus.WINNER.value else o.eliminated_round - 1
        participation_score = PARTICIPATION_SCORE
        survival_score = SURVIVAL_SCORE_PER_ROUND * rounds_passed
        session_score = participation_score + survival_score
        final_score = round(session_score * factor)
        results[o.user_id] = PlayerScoreResult(
            breakdown=ScoreBreakdown(
                result_score=0,
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
        # setara (partisipasi=10 + survival) - penalty. Ini TIDAK berubah oleh
        # penghapusan skor_hasil di atas -- AFK_PENALTY_BASE=10 memang persis
        # mencoret skor_partisipasi (10) yang pemain normal dapat, jadi
        # hasilnya selalu 0,5x ketahanan apa pun formula pemain normal.
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
