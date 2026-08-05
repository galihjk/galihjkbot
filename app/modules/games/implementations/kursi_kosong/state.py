from __future__ import annotations

import random as random_module

FIRST_CLICK_WEIGHT = 1.25
OTHER_CLICK_WEIGHT = 1.00


def build_initial_state(alive_user_ids: list[int]) -> dict:
    return {
        "round": 0,
        "alive_user_ids": list(alive_user_ids),
        "seats": {},
        "contests": {},
    }


def start_new_round(state: dict) -> dict:
    state["round"] += 1
    state["seats"] = {}
    state["contests"] = {}
    return state


def seat_count(state: dict) -> int:
    return max(len(state["alive_user_ids"]) - 1, 0)


def available_seats(state: dict) -> list[int]:
    taken = {int(key) for key in state["seats"]}
    total = seat_count(state)
    return [number for number in range(1, total + 1) if number not in taken]


def seat_holder(state: dict, seat_number: int) -> int | None:
    return state["seats"].get(str(seat_number))


def already_seated(state: dict, user_id: int) -> int | None:
    """Nomor kursi yang sudah ditempati user ini, kalau ada."""
    for seat_number, holder_id in state["seats"].items():
        if holder_id == user_id:
            return int(seat_number)
    return None


def user_active_contest_seat(state: dict, user_id: int) -> int | None:
    """Nomor kursi yang sedang dikontes user ini (belum resolve), kalau ada."""
    for seat_number, contest in state["contests"].items():
        if user_id in contest["contestants"]:
            return int(seat_number)
    return None


def join_contest(state: dict, seat_number: int, user_id: int) -> tuple[bool, bool]:
    """Mulai atau ikut kontes kursi ini.

    Return (joined, is_new): `is_new=True` kalau kontes ini baru dibuat oleh
    klik ini (pemanggil perlu menjadwalkan timer jendela kontes). `joined=False`
    kalau user ini sudah tercatat di kontes yang sama (klik dobel).
    """
    contests = state["contests"]
    key = str(seat_number)
    contest = contests.get(key)
    if contest is None:
        contests[key] = {"contestants": [user_id]}
        return True, True
    if user_id in contest["contestants"]:
        return False, False
    contest["contestants"].append(user_id)
    return True, False


def pop_contest(state: dict, seat_number: int) -> dict | None:
    """Ambil & hapus entri kontes kursi ini (dipakai saat resolve)."""
    return state["contests"].pop(str(seat_number), None)


def pick_contest_winner(
    contestants: list[int], rng: random_module.Random | None = None
) -> int:
    """Pilih pemenang kontes secara berbobot (§13 desain): pengklik pertama
    (index 0) bobot 1,25, sisanya 1,00."""
    rng = rng or random_module
    weights = [
        FIRST_CLICK_WEIGHT if i == 0 else OTHER_CLICK_WEIGHT
        for i in range(len(contestants))
    ]
    return rng.choices(contestants, weights=weights, k=1)[0]


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
