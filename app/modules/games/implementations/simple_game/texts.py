from __future__ import annotations

from app.modules.games.engine.context import PlayerInfo


def render_round_start(
    round_number: int,
    players: list[PlayerInfo],
    seat_total: int,
    timeout_seconds: int,
) -> str:
    names = ", ".join(p.display_name for p in players)
    return (
        f"🪑 RONDE {round_number}\n"
        f"Pemain tersisa: {len(players)}\n"
        f"({names})\n\n"
        f"Tersedia {seat_total} kursi. Rebutan sekarang!\n"
        f"Waktu: {timeout_seconds} detik"
    )


def render_round_result(eliminated_name: str | None, survivor_names: list[str]) -> str:
    lines = []
    if eliminated_name:
        lines.append(f"❌ {eliminated_name} tidak kebagian kursi dan tereliminasi!")
    else:
        lines.append("Ronde selesai.")
    lines.append("")
    lines.append("Pemain tersisa:")
    lines.extend(f"- {name}" for name in survivor_names)
    return "\n".join(lines)


def render_winner(winner_name: str) -> str:
    return f"🏆 {winner_name} adalah pemenangnya! Selamat!"
