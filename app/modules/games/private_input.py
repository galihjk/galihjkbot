from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.utils.datetime import utcnow


@dataclass
class PendingPrivateInput:
    user_id: int
    session_id: int
    purpose: str
    round_number: int
    nonce: str
    expires_at: datetime


class PrivateInputRegistry:
    """Registry generik: satu konteks input privat aktif per user, lintas
    game apa pun. Sengaja in-memory (bukan tabel DB) -- kebijakan recovery
    engine sudah meng-ABORT sesi RUNNING saat restart (lihat
    `game-development-guide.md` §13), jadi tidak ada konteks privat yang
    genuinely perlu dipulihkan setelah proses hidup kembali. Modul ini tidak
    pernah membaca/mengubah state spesifik game apa pun -- cuma menyimpan
    "milik siapa, sesi mana, untuk apa"."""

    def __init__(self) -> None:
        self._entries: dict[int, PendingPrivateInput] = {}

    def register(
        self,
        *,
        user_id: int,
        session_id: int,
        purpose: str,
        round_number: int,
        nonce: str,
        ttl_seconds: float,
    ) -> PendingPrivateInput:
        entry = PendingPrivateInput(
            user_id=user_id,
            session_id=session_id,
            purpose=purpose,
            round_number=round_number,
            nonce=nonce,
            expires_at=utcnow() + timedelta(seconds=ttl_seconds),
        )
        # Membuka konteks baru menggantikan konteks privat lama milik user
        # (§3.3 desain) -- termasuk kalau konteks lama itu punya sesi lain.
        self._entries[user_id] = entry
        return entry

    def get(self, user_id: int) -> PendingPrivateInput | None:
        entry = self._entries.get(user_id)
        if entry is None:
            return None
        if entry.expires_at <= utcnow():
            del self._entries[user_id]
            return None
        return entry

    def clear(self, user_id: int) -> None:
        self._entries.pop(user_id, None)

    def clear_session(self, session_id: int) -> None:
        stale = [uid for uid, entry in self._entries.items() if entry.session_id == session_id]
        for uid in stale:
            del self._entries[uid]

    def clear_all(self) -> None:
        self._entries.clear()


_registry = PrivateInputRegistry()


def register_private_input(
    *,
    user_id: int,
    session_id: int,
    purpose: str,
    round_number: int,
    nonce: str,
    ttl_seconds: float,
) -> PendingPrivateInput:
    return _registry.register(
        user_id=user_id,
        session_id=session_id,
        purpose=purpose,
        round_number=round_number,
        nonce=nonce,
        ttl_seconds=ttl_seconds,
    )


def get_private_input(user_id: int) -> PendingPrivateInput | None:
    return _registry.get(user_id)


def clear_private_input(user_id: int) -> None:
    _registry.clear(user_id)


def clear_session_private_inputs(session_id: int) -> None:
    _registry.clear_session(session_id)


def clear_all_private_inputs() -> None:
    """Dipanggil sekali saat startup bot supaya jelas bahwa tidak ada
    konteks privat yang "diwarisi" dari proses sebelumnya (walau secara
    teknis registry modul-level baru ini memang selalu kosong di proses
    baru) -- dan dipakai test untuk isolasi antar skenario karena registry
    ini singleton di level modul."""
    _registry.clear_all()
