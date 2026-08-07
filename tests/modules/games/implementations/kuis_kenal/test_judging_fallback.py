from __future__ import annotations

from app.modules.games.implementations.kuis_kenal import state as game_state
from tests.modules.games.implementations.kuis_kenal.helpers import (
    extract_start_payload,
    latest_markup_to,
    open_deep_link,
    send_callback,
    send_private_text,
)

# Chat privat "asli" yang dipakai admin untuk membuka deep link ATAS NAMA
# virtual player -- BUKAN telegram_user_id palsu milik virtual player itu
# sendiri (yang cuma dipakai game.py untuk percobaan dorong pesan LANGSUNG,
# dan yang justru harus SELALU gagal, persis seperti kondisi nyata: virtual
# player tidak punya device sungguhan, tapi admin yang memerankannya tetap
# py punya SATU chat privat asli dengan bot).
ADMIN_REAL_CHAT_ID = 42


async def test_judging_falls_back_to_group_deep_link_when_direct_dm_fails(game_world, kuis_kenal_game):
    """Simulasikan subjek yang tidak bisa di-DM langsung (mis. virtual player
    tanpa chat Telegram asli, lihat plan 'virtual player tidak bisa private
    chat') -- pastikan game TIDAK langsung menyerah (judge timeout tanpa
    poin), melainkan fallback ke pesan grup dengan deep link kk-j yang tetap
    bisa dibuka (lewat chat privat ASLI admin) dan diselesaikan normal."""
    game = kuis_kenal_game
    user_ids = await game_world.add_players(3)
    session_id = await game_world.start_game_now("kuis_kenal", user_ids)

    state = await game_world.get_state(session_id)
    subject_id = state["current_subject_id"]
    subject_fake_chat = game_world.telegram_id_of(subject_id)  # telegram_user_id palsu
    round_number = state["round"]

    markup = latest_markup_to(game_world.bot, game_world.telegram_chat_id)
    payload = extract_start_payload(markup)
    await open_deep_link(game, game_world, session_id, payload, user_id=subject_id, chat_id=ADMIN_REAL_CHAT_ID)
    state = await game_world.get_state(session_id)
    await send_callback(
        game_world, session_id, f"{round_number}-{state['message_version']}-qp-0",
        message_id=state["subject_private_message_id"], chat_id=ADMIN_REAL_CHAT_ID, user_id=subject_id,
    )

    # Dorongan pesan LANGSUNG pakai telegram_user_id palsu -- ini yang harus
    # SELALU gagal (tidak ada chat asli di baliknya), berbeda dari chat
    # privat asli admin di atas yang tetap bisa dipakai buka deep link.
    game_world.bot.fail_send_to.add(subject_fake_chat)

    answerers = [uid for uid in user_ids if uid != subject_id]
    markup = latest_markup_to(game_world.bot, game_world.telegram_chat_id)
    answer_payload = extract_start_payload(markup)
    for uid in answerers:
        chat_id = game_world.telegram_id_of(uid)
        await open_deep_link(game, game_world, session_id, answer_payload, user_id=uid, chat_id=chat_id)
        await send_private_text(game_world, session_id, f"jawaban {uid}", user_id=uid, chat_id=chat_id)
        state = await game_world.get_state(session_id)
        await send_callback(
            game_world, session_id, f"{round_number}-0-ac-0",
            message_id=state["answer_confirmation_message_ids"][str(uid)],
            chat_id=chat_id, user_id=uid,
        )

    state = await game_world.get_state(session_id)
    assert state["phase"] == game_state.Phase.JUDGING.value
    # Direct push gagal -- judging_message_id masih belum terisi (baru
    # terisi kalau subjek benar2 membuka deep link fallback).
    assert state["judging_message_id"] is None

    fallback_markup = latest_markup_to(game_world.bot, game_world.telegram_chat_id)
    fallback_payload = extract_start_payload(fallback_markup)
    assert fallback_payload is not None
    assert fallback_payload.startswith("kk-j-")

    # Subjek (admin, dari chat privat ASLI-nya) buka link fallback -- ini
    # yang butuh judge_nonce SUNGGUHAN (bukan None) supaya tidak ditolak
    # "link tidak berlaku".
    await open_deep_link(
        game, game_world, session_id, fallback_payload, user_id=subject_id, chat_id=ADMIN_REAL_CHAT_ID
    )
    state = await game_world.get_state(session_id)
    assert state["judging_message_id"] is not None

    group_id = state["answer_groups"][0]["group_id"]
    judge_version = state["message_version"]
    await send_callback(
        game_world, session_id, f"{round_number}-{judge_version}-jt-{group_id}",
        message_id=state["judging_message_id"], chat_id=ADMIN_REAL_CHAT_ID, user_id=subject_id,
    )
    await send_callback(
        game_world, session_id, f"{round_number}-{judge_version}-jd-0",
        message_id=state["judging_message_id"], chat_id=ADMIN_REAL_CHAT_ID, user_id=subject_id,
    )

    final_state = await game_world.get_state(session_id)
    correct_uid = state["answer_groups"][0]["user_ids"][0]
    assert final_state["scores"][str(correct_uid)] == 1
    # Giliran selesai dinilai normal (bukan judge timeout) -- tidak ada
    # penalti afk_strikes/judge_timeouts untuk subjek.
    assert final_state["activity"][str(subject_id)]["judge_timeouts"] == 0
    assert final_state["activity"][str(subject_id)]["subject_turns_completed"] == 1


async def test_judging_double_failure_falls_back_to_timeout(game_world, kuis_kenal_game):
    """Kalau BAHKAN pesan fallback grup juga gagal terkirim (kegagalan ganda,
    transient/sementara -- mis. blip jaringan pas momen itu saja), game
    tidak boleh macet: giliran ini dibatalkan tanpa poin (sama seperti judge
    timeout biasa) dan lanjut normal ke giliran berikutnya."""
    game = kuis_kenal_game
    user_ids = await game_world.add_players(3)
    session_id = await game_world.start_game_now("kuis_kenal", user_ids)

    state = await game_world.get_state(session_id)
    subject_id = state["current_subject_id"]
    subject_fake_chat = game_world.telegram_id_of(subject_id)
    round_number = state["round"]

    markup = latest_markup_to(game_world.bot, game_world.telegram_chat_id)
    payload = extract_start_payload(markup)
    await open_deep_link(game, game_world, session_id, payload, user_id=subject_id, chat_id=ADMIN_REAL_CHAT_ID)
    state = await game_world.get_state(session_id)
    await send_callback(
        game_world, session_id, f"{round_number}-{state['message_version']}-qp-0",
        message_id=state["subject_private_message_id"], chat_id=ADMIN_REAL_CHAT_ID, user_id=subject_id,
    )

    answer_payload = extract_start_payload(latest_markup_to(game_world.bot, game_world.telegram_chat_id))
    assert answer_payload is not None

    game_world.bot.fail_send_to.add(subject_fake_chat)  # dorongan langsung: gagal permanen (memang begitu)
    # Fallback grup: gagal SEKALI SAJA (transient) -- giliran BERIKUTNYA
    # (yang juga mengirim ke grup yang sama) harus tetap berhasil normal.
    game_world.bot.fail_send_count[game_world.telegram_chat_id] = 1
    # `_edit_or_send_new` coba EDIT pesan grup 3x dulu sebelum jatuh ke
    # `send_message` (yang baru gagal sekali di atas) -- paksa ketiga
    # percobaan edit itu gagal juga supaya benar2 sampai ke send_message.
    # Angkanya dilebihkan (bukan tepat 3) karena tiap konfirmasi jawaban
    # (2x untuk 3 pemain) JUGA memicu satu edit_message_text (menutup pesan
    # konfirmasi masing-masing) sebelum giliran sampai ke fase menilai.
    game_world.bot.fail_next_edits = 10

    answerers = [uid for uid in user_ids if uid != subject_id]
    for uid in answerers:
        chat_id = game_world.telegram_id_of(uid)
        await open_deep_link(game, game_world, session_id, answer_payload, user_id=uid, chat_id=chat_id)
        await send_private_text(game_world, session_id, f"jawaban {uid}", user_id=uid, chat_id=chat_id)
        state = await game_world.get_state(session_id)
        await send_callback(
            game_world, session_id, f"{round_number}-0-ac-0",
            message_id=state["answer_confirmation_message_ids"][str(uid)],
            chat_id=chat_id, user_id=uid,
        )

    state_after = await game_world.get_state(session_id)
    assert sum(state_after["scores"].values()) == 0
    assert state_after["activity"][str(subject_id)]["judge_timeouts"] == 1
    # Giliran berikutnya sudah dimulai normal (pesan pembuka ronde baru
    # berhasil terkirim ke grup yang sama -- membuktikan kegagalannya memang
    # cuma sementara, bukan chat yang rusak permanen).
    assert state_after["current_subject_id"] != subject_id
    assert state_after["phase"] == game_state.Phase.QUESTION_SELECT.value
