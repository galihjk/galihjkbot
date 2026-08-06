from __future__ import annotations

from app.modules.games.private_input import PrivateInputRegistry


def _register(registry: PrivateInputRegistry, *, user_id, session_id, ttl_seconds=60):
    return registry.register(
        user_id=user_id,
        session_id=session_id,
        purpose="answer",
        round_number=1,
        nonce="abc123",
        ttl_seconds=ttl_seconds,
    )


def test_get_returns_none_for_unknown_user():
    registry = PrivateInputRegistry()
    assert registry.get(999) is None


def test_register_then_get_roundtrips():
    registry = PrivateInputRegistry()
    _register(registry, user_id=1, session_id=42)

    entry = registry.get(1)
    assert entry is not None
    assert entry.session_id == 42
    assert entry.purpose == "answer"
    assert entry.round_number == 1
    assert entry.nonce == "abc123"


def test_expired_entry_returns_none_and_is_removed():
    registry = PrivateInputRegistry()
    _register(registry, user_id=1, session_id=42, ttl_seconds=-1)

    assert registry.get(1) is None
    # Dihapus, bukan cuma disembunyikan -- pastikan tidak nyangkut di internal dict.
    assert 1 not in registry._entries


def test_new_registration_replaces_old_context_for_same_user():
    registry = PrivateInputRegistry()
    _register(registry, user_id=1, session_id=42)
    _register(registry, user_id=1, session_id=99)

    entry = registry.get(1)
    assert entry.session_id == 99


def test_clear_removes_only_that_user():
    registry = PrivateInputRegistry()
    _register(registry, user_id=1, session_id=42)
    _register(registry, user_id=2, session_id=42)

    registry.clear(1)

    assert registry.get(1) is None
    assert registry.get(2) is not None


def test_clear_session_removes_all_users_of_that_session_only():
    registry = PrivateInputRegistry()
    _register(registry, user_id=1, session_id=42)
    _register(registry, user_id=2, session_id=42)
    _register(registry, user_id=3, session_id=99)

    registry.clear_session(42)

    assert registry.get(1) is None
    assert registry.get(2) is None
    assert registry.get(3) is not None


def test_clear_all_empties_everything():
    registry = PrivateInputRegistry()
    _register(registry, user_id=1, session_id=42)
    _register(registry, user_id=2, session_id=99)

    registry.clear_all()

    assert registry.get(1) is None
    assert registry.get(2) is None
