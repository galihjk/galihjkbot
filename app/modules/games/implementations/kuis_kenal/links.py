from __future__ import annotations

from dataclasses import dataclass

from app.modules.games.implementations.kuis_kenal.metadata import DEEP_LINK_PREFIX

_PURPOSE_TO_CODE = {
    "question_select": "q",
    "answer": "a",
    "judge": "j",
}
_CODE_TO_PURPOSE = {code: purpose for purpose, code in _PURPOSE_TO_CODE.items()}

_BASE36_DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"


def _to_base36(number: int) -> str:
    if number == 0:
        return "0"
    digits: list[str] = []
    while number > 0:
        number, remainder = divmod(number, 36)
        digits.append(_BASE36_DIGITS[remainder])
    return "".join(reversed(digits))


@dataclass(frozen=True)
class DeepLinkPayload:
    purpose: str
    session_id: int
    round_number: int
    nonce: str


def build_deep_link_payload(
    purpose: str, session_id: int, round_number: int, nonce: str
) -> str:
    code = _PURPOSE_TO_CODE[purpose]
    return (
        f"{DEEP_LINK_PREFIX}{code}-{_to_base36(session_id)}-"
        f"{_to_base36(round_number)}-{nonce}"
    )


def parse_deep_link_payload(payload: str) -> DeepLinkPayload | None:
    if not payload.startswith(DEEP_LINK_PREFIX):
        return None
    rest = payload[len(DEEP_LINK_PREFIX) :]
    parts = rest.split("-")
    if len(parts) != 4:
        return None
    code, session_b36, round_b36, nonce = parts
    purpose = _CODE_TO_PURPOSE.get(code)
    if purpose is None or not nonce:
        return None
    try:
        session_id = int(session_b36, 36)
        round_number = int(round_b36, 36)
    except ValueError:
        return None
    return DeepLinkPayload(
        purpose=purpose, session_id=session_id, round_number=round_number, nonce=nonce
    )
