from __future__ import annotations

from app.modules.games.engine.context import PlayerInfo
from app.modules.games.engine.metadata import GameMetadata

PLAY_AGAIN_HINT = "Mau main lagi? Tinggal tap: /game"


def render_lobby_text(
    metadata: GameMetadata,
    players: list[PlayerInfo],
    remaining_seconds: int,
) -> str:
    lines = [
        f"🎮 {metadata.name.upper()}",
        "Status: Menunggu pemain",
        f"Pemain: {len(players)}/{metadata.max_players}",
        f"Minimum: {metadata.min_players} pemain",
        f"Sisa waktu: ±{max(remaining_seconds, 0)} detik (bisa di-extend)",
        "",
    ]
    if players:
        lines.extend(f"{i}. {p.display_name}" for i, p in enumerate(players, start=1))
    else:
        lines.append("(belum ada pemain)")
    return "\n".join(lines)


def _mention(player: PlayerInfo) -> str:
    return f'<a href="tg://user?id={player.telegram_user_id}">{player.display_name}</a>'


def render_ready_check_text(
    metadata: GameMetadata,
    players: list[PlayerInfo],
    ready_user_ids: set[int],
    remaining_seconds: int,
) -> str:
    lines = [
        f"🎮 {metadata.name.upper()}",
        "PERMAINAN AKAN SEGERA DIMULAI!",
        "",
        "Sudah siap??",
        f"Klik tombol ✅Siap dalam {max(remaining_seconds, 0)} detik!",
        "",
        " ".join(_mention(p) for p in players),
        "",
    ]
    for player in players:
        mark = "✅" if player.user_id in ready_user_ids else "⏳"
        lines.append(f"{mark} {player.display_name}")
    return "\n".join(lines)


def render_cancelled_text(
    metadata: GameMetadata,
    reason: str,
    mentioned_players: list[PlayerInfo],
) -> str:
    mentions = " ".join(_mention(p) for p in mentioned_players)

    if reason == "insufficient_players":
        lines = [
            f"😔 {metadata.name} dibatalkan",
            f"Pemain yang gabung belum sampai minimum ({metadata.min_players}).",
        ]
        if mentions:
            lines += ["", f"Maaf ya {mentions}, udah nungguin tapi gagal jalan 🙏"]
        lines += ["", "Ajak beberapa teman lagi biar rame, yuk!"]
    elif reason == "not_enough_ready_players":
        lines = [
            f"😔 {metadata.name} dibatalkan",
            f"Yang konfirmasi siap kurang dari minimum ({metadata.min_players}).",
        ]
        if mentions:
            lines += ["", f"Maaf ya {mentions}, udah siap tapi pemain lain kurang 🙏"]
        lines += ["", "Ajak beberapa teman lagi biar rame, yuk!"]
    else:
        lines = [f"❌ {metadata.name} dibatalkan."]
        if mentions:
            lines += ["", f"Maaf ya {mentions} 🙏"]

    lines += ["", PLAY_AGAIN_HINT]
    return "\n".join(lines)
