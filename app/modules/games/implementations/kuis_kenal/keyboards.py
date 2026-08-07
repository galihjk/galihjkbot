from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.modules.games.callbacks import GameCallback
from app.modules.games.implementations.kuis_kenal.links import build_deep_link_payload

_NUMBER_EMOJI = ("1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣")
_LABEL_MAX_LENGTH = 40


def _deep_link_url(bot_username: str, payload: str) -> str:
    return f"https://t.me/{bot_username}?start={payload}"


def _callback_data(session_id: int, round_number: int, version: int, action: str, value: int) -> str:
    return GameCallback(
        session_id=session_id, data=f"{round_number}-{version}-{action}-{value}"
    ).pack()


def build_group_choose_question_link(
    bot_username: str, session_id: int, round_number: int, nonce: str
) -> InlineKeyboardMarkup:
    payload = build_deep_link_payload("question_select", session_id, round_number, nonce)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📝 Pilih Soal", url=_deep_link_url(bot_username, payload)
                )
            ]
        ]
    )


def build_group_answer_link(
    bot_username: str, session_id: int, round_number: int, nonce: str
) -> InlineKeyboardMarkup:
    payload = build_deep_link_payload("answer", session_id, round_number, nonce)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✍️ Jawab Privat", url=_deep_link_url(bot_username, payload)
                )
            ]
        ]
    )


def build_group_judge_link(
    bot_username: str, session_id: int, round_number: int, nonce: str
) -> InlineKeyboardMarkup:
    payload = build_deep_link_payload("judge", session_id, round_number, nonce)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔍 Periksa Jawaban", url=_deep_link_url(bot_username, payload)
                )
            ]
        ]
    )


def build_private_question_keyboard(
    session_id: int,
    round_number: int,
    version: int,
    question_count: int,
    *,
    can_reroll: bool,
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=_NUMBER_EMOJI[i],
                callback_data=_callback_data(session_id, round_number, version, "qp", i),
            )
            for i in range(question_count)
        ]
    ]
    if can_reroll:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🔀 Ambil 5 soal lain",
                    callback_data=_callback_data(session_id, round_number, version, "qr", 0),
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_answer_confirmation_keyboard(
    session_id: int, round_number: int, version: int
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Ya, kirim",
                    callback_data=_callback_data(session_id, round_number, version, "ac", 0),
                ),
                InlineKeyboardButton(
                    text="✏️ Ubah",
                    callback_data=_callback_data(session_id, round_number, version, "ae", 0),
                ),
            ]
        ]
    )


def build_judging_keyboard(
    session_id: int,
    round_number: int,
    version: int,
    groups: list[dict],
) -> InlineKeyboardMarkup:
    rows = []
    for group in groups:
        mark = "✅" if group["is_correct"] else "⬜"
        label = group["display_text"]
        if len(label) > _LABEL_MAX_LENGTH:
            label = label[: _LABEL_MAX_LENGTH - 1] + "…"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{mark} {label}",
                    callback_data=_callback_data(
                        session_id, round_number, version, "jt", group["group_id"]
                    ),
                )
            ]
        )

    has_any_correct = any(group["is_correct"] for group in groups)
    finish_caption = "✅ Selesai Menilai" if has_any_correct else "TIDAK ADA YANG BENAR"
    rows.append(
        [
            InlineKeyboardButton(
                text=finish_caption,
                callback_data=_callback_data(session_id, round_number, version, "jd", 0),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)
