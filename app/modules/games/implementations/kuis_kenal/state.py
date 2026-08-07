from __future__ import annotations

import random
import re
import secrets
import unicodedata
from enum import Enum

from app.utils.datetime import utcnow


class Phase(str, Enum):
    QUESTION_SELECT = "question_select"
    ANSWERING = "answering"
    JUDGING = "judging"
    RESOLVING = "resolving"
    FINISHED = "finished"


def _empty_activity() -> dict:
    return {
        "valid_actions": 0,
        "answers_confirmed": 0,
        "correct_answers": 0,
        "subject_turns_completed": 0,
        "missed_answer_rounds": 0,
        "subject_pick_timeouts": 0,
        "judge_timeouts": 0,
        "afk_strikes": 0,
    }


def _activity_for(state: dict, user_id: int) -> dict:
    return state["activity"].setdefault(str(user_id), _empty_activity())


def _mark_valid_action(state: dict, user_id: int) -> None:
    _activity_for(state, user_id)["valid_actions"] += 1


def _bump_message_version(state: dict) -> None:
    state["message_version"] = state.get("message_version", 1) + 1


# ----------------------------------------------------------------------
# Setup & antrean giliran
# ----------------------------------------------------------------------


def build_initial_state(user_ids: list[int], *, rng: random.Random | None = None) -> dict:
    order = list(user_ids)
    (rng or random).shuffle(order)
    return {
        "schema_version": 1,
        "phase": Phase.QUESTION_SELECT.value,
        "round": 0,
        "message_version": 1,
        "all_user_ids": list(user_ids),
        "turn_queue": order,
        "current_subject_id": None,
        "offered_question_ids": [],
        "used_question_ids": [],
        "selected_question_id": None,
        "question_reroll_count": 0,
        "question_nonce": None,
        "answer_nonce": None,
        "judge_nonce": None,
        "answer_drafts": {},
        "final_answers": {},
        "answer_groups": [],
        "next_group_id": 1,
        "scores": {str(uid): 0 for uid in user_ids},
        "activity": {str(uid): _empty_activity() for uid in user_ids},
        "public_message_id": None,
        "subject_private_message_id": None,
        "answer_confirmation_message_ids": {},
        "judging_message_id": None,
        "phase_started_at": None,
        "turn_started_at": None,
    }


def begin_turn(state: dict) -> dict:
    """Pop pemain berikutnya dari `turn_queue` jadi `current_subject_id` dan
    reset seluruh state per-giliran. Pemilihan lima soal dilakukan terpisah
    lewat `offer_questions()` (butuh bank pertanyaan dari `questions.py`,
    di luar tanggung jawab modul murni ini)."""
    if not state["turn_queue"]:
        raise ValueError("turn_queue kosong, tidak ada giliran berikutnya")

    state["current_subject_id"] = state["turn_queue"].pop(0)
    state["round"] += 1
    state["phase"] = Phase.QUESTION_SELECT.value
    state["offered_question_ids"] = []
    state["selected_question_id"] = None
    state["question_reroll_count"] = 0
    state["question_nonce"] = None
    state["answer_nonce"] = None
    state["judge_nonce"] = None
    state["answer_drafts"] = {}
    state["final_answers"] = {}
    state["answer_groups"] = []
    state["next_group_id"] = 1
    state["public_message_id"] = None
    state["subject_private_message_id"] = None
    state["answer_confirmation_message_ids"] = {}
    state["judging_message_id"] = None
    state["turn_started_at"] = utcnow().isoformat()
    _bump_message_version(state)
    return state


def is_game_complete(state: dict) -> bool:
    return not state["turn_queue"]


def expected_answerer_ids(state: dict) -> list[int]:
    subject_id = state["current_subject_id"]
    return [uid for uid in state["all_user_ids"] if uid != subject_id]


def is_participant(state: dict, user_id: int) -> bool:
    return user_id in state["all_user_ids"]


def is_current_subject(state: dict, user_id: int) -> bool:
    return state["current_subject_id"] == user_id


def is_current_round(state: dict, round_number: int) -> bool:
    return state["round"] == round_number


# ----------------------------------------------------------------------
# Pemilihan soal
# ----------------------------------------------------------------------


def offer_questions(state: dict, question_ids: list[str]) -> dict:
    state["offered_question_ids"] = list(question_ids)
    state["question_nonce"] = secrets.token_hex(4)
    _bump_message_version(state)
    return state


def reroll_questions(state: dict, new_question_ids: list[str], *, reroll_limit: int) -> dict:
    if state["question_reroll_count"] >= reroll_limit:
        raise ValueError("batas reroll sudah tercapai")

    # §5.2: lima soal LAMA yang dibuang tetap dianggap sudah dipakai supaya
    # tidak muncul lagi walau tidak pernah benar-benar dipilih.
    used = set(state["used_question_ids"])
    used.update(state["offered_question_ids"])
    state["used_question_ids"] = list(used)

    state["offered_question_ids"] = list(new_question_ids)
    state["question_reroll_count"] += 1
    state["question_nonce"] = secrets.token_hex(4)
    _mark_valid_action(state, state["current_subject_id"])
    _bump_message_version(state)
    return state


def select_question(state: dict, question_id: str) -> dict:
    if question_id not in state["offered_question_ids"]:
        raise ValueError("question_id bukan salah satu dari yang ditawarkan")

    state["selected_question_id"] = question_id
    used = set(state["used_question_ids"])
    used.update(state["offered_question_ids"])
    state["used_question_ids"] = list(used)

    state["phase"] = Phase.ANSWERING.value
    state["answer_nonce"] = secrets.token_hex(4)
    state["phase_started_at"] = utcnow().isoformat()
    _mark_valid_action(state, state["current_subject_id"])
    _bump_message_version(state)
    return state


def record_subject_pick_timeout(state: dict) -> dict:
    """§7.1: pemain aktif tidak memilih soal -- giliran dilewati tanpa poin
    untuk siapa pun, TIDAK menghitung `subject_turns_completed`."""
    activity = _activity_for(state, state["current_subject_id"])
    activity["subject_pick_timeouts"] += 1
    activity["afk_strikes"] += 1
    state["phase"] = Phase.RESOLVING.value
    return state


# ----------------------------------------------------------------------
# Menjawab & konfirmasi
# ----------------------------------------------------------------------


def has_confirmed_answer(state: dict, user_id: int) -> bool:
    return str(user_id) in state["final_answers"]


def get_answer_draft(state: dict, user_id: int) -> dict | None:
    return state["answer_drafts"].get(str(user_id))


def store_answer_draft(state: dict, user_id: int, text: str) -> dict:
    key = str(user_id)
    existing = state["answer_drafts"].get(key)
    revision = existing["revision"] + 1 if existing else 1
    state["answer_drafts"][key] = {
        "text": text,
        "revision": revision,
        "updated_at": utcnow().isoformat(),
    }
    _mark_valid_action(state, user_id)
    return state


def clear_answer_draft(state: dict, user_id: int) -> dict:
    state["answer_drafts"].pop(str(user_id), None)
    return state


def confirm_answer(state: dict, user_id: int) -> dict:
    key = str(user_id)
    draft = state["answer_drafts"].get(key)
    if draft is None:
        raise ValueError("tidak ada draft jawaban untuk user ini")

    state["final_answers"][key] = {
        "text": draft["text"],
        "revision": draft["revision"],
        "confirmed_at": utcnow().isoformat(),
    }
    activity = _activity_for(state, user_id)
    activity["answers_confirmed"] += 1
    return state


def all_expected_answers_confirmed(state: dict) -> bool:
    expected = expected_answerer_ids(state)
    return all(str(uid) in state["final_answers"] for uid in expected)


# ----------------------------------------------------------------------
# Penilaian
# ----------------------------------------------------------------------


def normalize_answer_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).strip().lower()
    return re.sub(r"\s+", " ", normalized)


def finalize_answering(state: dict) -> dict:
    """Tutup fase menjawab (dipanggil baik saat semua sudah konfirmasi lebih
    cepat, maupun saat timer answering habis): tandai pemain yang belum
    mengonfirmasi jawaban final sebagai `missed_answer_rounds`, lalu bangun
    `answer_groups` dari jawaban final yang MASUK saja."""
    for uid in expected_answerer_ids(state):
        if str(uid) not in state["final_answers"]:
            _activity_for(state, uid)["missed_answer_rounds"] += 1
    return build_answer_groups(state)


def build_answer_groups(state: dict) -> dict:
    """Kelompokkan `final_answers` berdasar normalisasi ringan (§5.5) --
    HANYA untuk tampilan/pengelompokan, bukan penentu benar/salah."""
    groups_by_norm: dict[str, dict] = {}
    order: list[str] = []
    for uid_str, answer in state["final_answers"].items():
        norm = normalize_answer_text(answer["text"])
        if norm not in groups_by_norm:
            groups_by_norm[norm] = {
                "normalized_text": norm,
                "display_text": answer["text"],
                "user_ids": [],
            }
            order.append(norm)
        groups_by_norm[norm]["user_ids"].append(int(uid_str))

    next_id = state.get("next_group_id", 1)
    groups = []
    for norm in order:
        group = groups_by_norm[norm]
        groups.append(
            {
                "group_id": next_id,
                "normalized_text": group["normalized_text"],
                "display_text": group["display_text"],
                "user_ids": group["user_ids"],
                "is_correct": False,
            }
        )
        next_id += 1

    state["answer_groups"] = groups
    state["next_group_id"] = next_id
    state["phase"] = Phase.JUDGING.value
    state["phase_started_at"] = utcnow().isoformat()
    # Nonce fase menilai -- baru digenerate di sini (bukan di begin_turn),
    # mirip pola answer_nonce di select_question. Sempat lupa dibuat sama
    # sekali sebelumnya, bikin deep link kk-j selalu ditolak "tidak berlaku"
    # apa pun nonce yang dikirim (bandingannya selalu vs None).
    state["judge_nonce"] = secrets.token_hex(4)
    _bump_message_version(state)
    return state


def toggle_answer_group(state: dict, group_id: int) -> dict:
    for group in state["answer_groups"]:
        if group["group_id"] == group_id:
            group["is_correct"] = not group["is_correct"]
            return state
    raise ValueError("group_id tidak ditemukan")


def has_any_correct_group(state: dict) -> bool:
    return any(group["is_correct"] for group in state["answer_groups"])


def record_judge_timeout(state: dict) -> dict:
    """§7.3: pemain aktif tidak menyelesaikan penilaian -- giliran dibatalkan
    TANPA poin untuk siapa pun, jawaban tidak diproses ke skor benar."""
    activity = _activity_for(state, state["current_subject_id"])
    activity["judge_timeouts"] += 1
    activity["afk_strikes"] += 1
    state["phase"] = Phase.RESOLVING.value
    return state


def resolve_turn(state: dict) -> dict:
    """Terapkan skor internal ronde berdasar `answer_groups` yang sudah
    ditandai pemain aktif, catat statistik aktivitas, dan kembalikan summary
    murni untuk dirender jadi teks hasil ronde. Idempotensi (jangan dipanggil
    dua kali untuk ronde yang sama) adalah tanggung jawab pemanggil
    (`game.py`, lewat guard fase `resolving` -- lihat game-development-guide
    §7/§21), bukan tanggung jawab fungsi murni ini."""
    correct_ids: set[int] = set()
    for group in state["answer_groups"]:
        if group["is_correct"]:
            correct_ids.update(group["user_ids"])

    successful: list[tuple[int, str]] = []
    failed: list[tuple[int, str | None]] = []
    for uid in expected_answerer_ids(state):
        final = state["final_answers"].get(str(uid))
        text = final["text"] if final else None
        if uid in correct_ids:
            successful.append((uid, text or ""))
        else:
            failed.append((uid, text))

    for uid, _ in successful:
        key = str(uid)
        state["scores"][key] = state["scores"].get(key, 0) + 1
        _activity_for(state, uid)["correct_answers"] += 1

    subject_id = state["current_subject_id"]
    subject_activity = _activity_for(state, subject_id)
    subject_activity["subject_turns_completed"] += 1
    _mark_valid_action(state, subject_id)

    state["phase"] = Phase.RESOLVING.value

    return {
        "question_id": state["selected_question_id"],
        "subject_id": subject_id,
        "successful": successful,
        "failed": failed,
        "round": state["round"],
    }


# ----------------------------------------------------------------------
# Transisi antar-giliran & hasil akhir
# ----------------------------------------------------------------------


def advance_turn(state: dict) -> dict:
    """Reset penanda "giliran sedang berjalan" di antara satu giliran yang
    baru diresolve dan giliran berikutnya (atau akhir game)."""
    state["current_subject_id"] = None
    state["phase"] = Phase.QUESTION_SELECT.value
    return state


def build_result_payload(state: dict) -> dict:
    scores = dict(state["scores"])
    max_score = max(scores.values()) if scores else 0
    winner_ids = [int(uid) for uid, score in scores.items() if score == max_score]
    return {
        "rounds": state["round"],
        "scores": scores,
        "winner_user_ids": winner_ids,
        "activity": state["activity"],
    }


def calculate_afk_flags(state: dict) -> dict[int, bool]:
    """§7.4: penetapan AFK murni dari counter aktivitas -- dipakai baik untuk
    keputusan `GamePlayerStatus` maupun basis skor leaderboard (§18.3). Tidak
    mengeluarkan pemain dari antrean, cuma menghitung flag per user."""
    expected_answers = max(len(state["all_user_ids"]) - 1, 0)
    flags: dict[int, bool] = {}
    for uid in state["all_user_ids"]:
        activity = state["activity"].get(str(uid), _empty_activity())
        no_valid_action = activity["valid_actions"] == 0
        failed_own_turn = (
            activity["subject_pick_timeouts"] > 0 or activity["judge_timeouts"] > 0
        )
        missed_half_or_more = (
            expected_answers > 0
            and activity["missed_answer_rounds"] >= expected_answers / 2
        )
        many_strikes = activity["afk_strikes"] >= 2
        flags[uid] = bool(
            no_valid_action or (failed_own_turn and missed_half_or_more) or many_strikes
        )
    return flags
