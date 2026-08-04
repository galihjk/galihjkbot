from __future__ import annotations

import random as random_module


def build_initial_state(alive_user_ids: list[int]) -> dict:
    return {
        "round": 0,
        "alive_user_ids": list(alive_user_ids),
        "seats": {},
    }


def start_new_round(state: dict) -> dict:
    state["round"] += 1
    state["seats"] = {}
    return state


def seat_count(state: dict) -> int:
    return max(len(state["alive_user_ids"]) - 1, 0)


def available_seats(state: dict) -> list[int]:
    taken = {int(key) for key in state["seats"]}
    total = seat_count(state)
    return [number for number in range(1, total + 1) if number not in taken]


def claim_seat(state: dict, seat_number: int, user_id: int) -> bool:
    key = str(seat_number)
    if key in state["seats"]:
        return False
    if user_id in state["seats"].values():
        return False
    if seat_number not in range(1, seat_count(state) + 1):
        return False
    state["seats"][key] = user_id
    return True


def is_round_complete(state: dict) -> bool:
    return len(state["seats"]) >= seat_count(state)


def resolve_round(
    state: dict, rng: random_module.Random | None = None
) -> tuple[list[int], int | None]:
    """Selesaikan ronde: kembalikan (survivor_user_ids, eliminated_user_id).

    Invarian: kursi = jumlah_hidup - 1, jadi tepat 1 pemain tereliminasi.
    Kalau ada pemain yang belum pilih kursi saat waktu habis, sisa kursi
    diisi acak dari mereka supaya yang benar-benar tereliminasi tetap 1 orang.
    """
    rng = rng or random_module
    alive = list(state["alive_user_ids"])
    seated = list(state["seats"].values())
    target = seat_count(state)

    unseated = [uid for uid in alive if uid not in seated]
    rng.shuffle(unseated)

    remaining_slots = max(target - len(seated), 0)
    survivors = seated + unseated[:remaining_slots]
    eliminated = unseated[remaining_slots:]

    eliminated_user_id = eliminated[0] if eliminated else None
    state["alive_user_ids"] = survivors
    return survivors, eliminated_user_id
