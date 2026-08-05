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
        "acted_user_ids": [],
    }


def start_new_round(state: dict) -> dict:
    state["round"] += 1
    state["seats"] = {}
    state["contests"] = {}
    state["acted_user_ids"] = []
    return state


def seat_count(state: dict) -> int:
    return max(len(state["alive_user_ids"]) - 1, 0)


def seat_holder(state: dict, seat_number: int) -> int | None:
    return state["seats"].get(str(seat_number))


def already_seated(state: dict, user_id: int) -> int | None:
    """Nomor kursi yang sudah ditempati user ini, kalau ada."""
    for seat_number, holder_id in state["seats"].items():
        if holder_id == user_id:
            return int(seat_number)
    return None


def mark_action_taken(state: dict, user_id: int) -> None:
    """Catat bahwa pemain ini melakukan aksi valid di ronde ini (§10 desain:
    klik apa pun dari pemain yang belum punya kursi dihitung valid, apa pun
    hasilnya) -- dipakai untuk membedakan AFK vs ELIMINATED saat resolve."""
    if user_id not in state["acted_user_ids"]:
        state["acted_user_ids"].append(user_id)


def took_action(state: dict, user_id: int) -> bool:
    return user_id in state["acted_user_ids"]


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


def resolve_round(state: dict) -> tuple[list[int], list[int]]:
    """Selesaikan ronde: kembalikan (survivor_user_ids, eliminated_user_ids).

    Kursi yang TIDAK PERNAH diklaim siapa pun tetap kosong permanen untuk
    ronde ini -- TIDAK ADA lagi pengisian acak dari pemain yang tidak
    beraksi (keputusan revisi setelah Tahap 3, lihat development-history.md).
    Semua pemain hidup yang tidak punya kursi tereliminasi BERSAMAAN --
    `eliminated_ids` bisa kosong (mustahil selama seat_count=alive-1, tapi
    valid secara tipe), berisi 1 (kasus biasa: semua kursi lain terisi),
    atau lebih dari 1 (beberapa kursi tak pernah dikontes siapa pun).
    """
    alive = list(state["alive_user_ids"])
    seated = set(state["seats"].values())
    survivors = [uid for uid in alive if uid in seated]
    eliminated = [uid for uid in alive if uid not in seated]
    state["alive_user_ids"] = survivors
    return survivors, eliminated
