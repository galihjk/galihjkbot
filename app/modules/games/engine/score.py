from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScoreBreakdown:
    result_score: int
    participation_score: int
    survival_score: int
    final_score: int
