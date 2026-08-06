from __future__ import annotations

import random

import pytest

from app.modules.games.implementations.kuis_kenal.questions import (
    CATEGORIES,
    QUESTIONS,
    draw_question_options,
    get_question,
    validate_question_bank,
)


def test_bank_has_at_least_60_questions():
    assert len(QUESTIONS) >= 60


def test_validate_question_bank_passes():
    validate_question_bank()  # tidak raise


def test_all_ids_unique():
    ids = [q.id for q in QUESTIONS]
    assert len(ids) == len(set(ids))


def test_no_empty_text_and_uses_subject_placeholder():
    for question in QUESTIONS:
        assert question.text.strip()
        assert "{subject}" in question.text


def test_all_categories_represented():
    used = {q.category for q in QUESTIONS}
    assert used == set(CATEGORIES)


def test_get_question_returns_expected():
    question = get_question(QUESTIONS[0].id)
    assert question.id == QUESTIONS[0].id


def test_draw_returns_exactly_count():
    ids = draw_question_options(used_question_ids=set(), count=5, rng=random.Random(1))
    assert len(ids) == 5
    assert len(set(ids)) == 5


def test_draw_avoids_used_questions_while_stock_available():
    used = {q.id for q in QUESTIONS[:55]}
    ids = draw_question_options(used_question_ids=used, count=5, rng=random.Random(2))
    assert not (set(ids) & used)


def test_draw_prefers_category_variety():
    ids = draw_question_options(used_question_ids=set(), count=5, rng=random.Random(3))
    categories = {get_question(i).category for i in ids}
    # Dengan 10 kategori dan 5 soal, round-robin harus menghasilkan variasi.
    assert len(categories) >= 4


def test_draw_falls_back_when_stock_insufficient():
    used = {q.id for q in QUESTIONS}  # semua sudah dipakai
    ids = draw_question_options(used_question_ids=used, count=5, rng=random.Random(4))
    assert len(ids) == 5


def test_draw_is_deterministic_with_same_seed():
    ids_a = draw_question_options(used_question_ids=set(), count=5, rng=random.Random(42))
    ids_b = draw_question_options(used_question_ids=set(), count=5, rng=random.Random(42))
    assert ids_a == ids_b
