from __future__ import annotations

import pytest

from app.modules.games.implementations.kuis_kenal import game as kk_game
from app.modules.games.implementations.kuis_kenal.game import KuisKenalGame


@pytest.fixture(autouse=True)
def _fast_pacing(monkeypatch):
    """Nolkan jeda dramatis (§16 pacing) selama test -- perilakunya sendiri
    (urutan pesan, kapan timer mulai) tidak berubah, cuma waktu tunggu
    nyatanya yang dihilangkan supaya test tidak lambat."""
    monkeypatch.setattr(kk_game, "MESSAGE_PAUSE_SECONDS", 0)
    monkeypatch.setattr(kk_game, "REVEAL_MIN_SECONDS", 0)
    monkeypatch.setattr(kk_game, "REVEAL_MAX_SECONDS", 0)


@pytest.fixture
def kuis_kenal_game(register_game) -> KuisKenalGame:
    game = KuisKenalGame()
    register_game(game)
    return game
