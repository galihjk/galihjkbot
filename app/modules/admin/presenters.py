from __future__ import annotations

from app.core.config import Settings
from app.core.enums import AdminRole, GameStatus
from app.database.models.game_session import GameSession
from app.database.models.group import Group
from app.database.models.user import User
from app.modules.games.engine.metadata import GameMetadata
from app.services.dashboard_service import DashboardStats
from app.services.permission_service import has_minimum_role
from app.utils.datetime import humanize_relative
from app.utils.pagination import Page

_ROLE_LABELS = {
    AdminRole.VIEWER: "Viewer",
    AdminRole.OPERATOR: "Operator",
    AdminRole.ADMIN: "Admin",
    AdminRole.SUPERADMIN: "Superadmin",
}

# (usage, deskripsi, role minimum, hanya-private-chat)
_ADMIN_COMMAND_CATALOG: list[tuple[str, list[tuple[str, str, AdminRole, bool]]]] = [
    (
        "🛠 Dashboard & Monitoring",
        [
            ("/admin, /dashboard", "Dashboard admin dengan tombol inline", AdminRole.VIEWER, True),
            ("/health", "Status kesehatan bot", AdminRole.VIEWER, True),
            ("/users [status] [page]", "Daftar pengguna", AdminRole.VIEWER, True),
            ("/user [id|username]", "Detail satu pengguna", AdminRole.VIEWER, True),
            ("/groups [status] [page]", "Daftar grup", AdminRole.VIEWER, True),
            ("/group [chat_id]", "Detail satu grup", AdminRole.VIEWER, True),
            ("/activegames", "Semua sesi game aktif lintas grup", AdminRole.VIEWER, True),
            ("/gameinfo [session_id]", "Detail satu sesi game (aktif atau selesai)", AdminRole.VIEWER, True),
        ],
    ),
    (
        "🧪 Testing solo (khusus grup)",
        [
            ("/p0 - /p7", "Ganti persona jadi virtual player (p0 = kembali ke diri sendiri)", AdminRole.VIEWER, False),
        ],
    ),
    (
        "💬 Autoreply / MsgCmd",
        [
            ("/msgcmd", "Panel MsgCmd dengan tombol", AdminRole.VIEWER, True),
            ("/msgcmd_status", "Status singkat MsgCmd", AdminRole.VIEWER, True),
            ("/msgcmd_reload", "Sinkronisasi ulang rule dari Google Sheet", AdminRole.OPERATOR, True),
            ("/msgcmd_group [chat_id] on|off", "Override aktif/nonaktif per grup", AdminRole.OPERATOR, True),
            ("/to_msgcmd", "Ambil media code dari pesan yang dibalas", AdminRole.OPERATOR, False),
            ("/msgcmd_enable", "Aktifkan autoreply secara global", AdminRole.ADMIN, True),
            ("/msgcmd_disable", "Nonaktifkan autoreply secara global", AdminRole.ADMIN, True),
            ("/format_msgcmd", "Dokumentasi format template MsgCmd", AdminRole.VIEWER, False),
            ("/msgcmd_sync_errors", "Ringkasan error/warning sync terakhir", AdminRole.VIEWER, True),
        ],
    ),
]

_GAME_STATUS_LABELS = {
    GameStatus.CREATED.value: "Baru dibuat",
    GameStatus.LOBBY.value: "Menunggu pemain",
    GameStatus.STARTING.value: "Segera dimulai",
    GameStatus.RUNNING.value: "Berlangsung",
    GameStatus.FINISHED.value: "Selesai",
    GameStatus.CANCELLED.value: "Dibatalkan",
    GameStatus.ABORTED.value: "Dihentikan (restart)",
    GameStatus.FAILED.value: "Gagal",
}


def _humanize_optional(moment) -> str:  # noqa: ANN001
    return humanize_relative(moment) if moment is not None else "-"


def format_dashboard(stats: DashboardStats, uptime: str, settings: Settings) -> str:
    lines = [
        "🛠 ADMIN DASHBOARD",
        "Status      : Online",
        f"Uptime      : {uptime}",
        f"Versi       : {settings.app_version}",
        f"Environment : {settings.app_env}",
        "",
        f"Pengguna tercatat : {stats.total_users}",
        f"Aktif 24 jam      : {stats.active_users_24h}",
        f"Grup tercatat     : {stats.total_groups}",
        "",
        "Ketik /adminhelp untuk daftar lengkap command admin.",
    ]
    return "\n".join(lines)


def format_user_code(user_id: int) -> str:
    return f"U-{user_id:06d}"


def format_user_list(page: Page[User]) -> str:
    lines = [
        "👥 DAFTAR PENGGUNA",
        f"Total: {page.total_items}",
        f"Halaman: {page.page}/{page.total_pages}",
        "",
    ]

    if not page.items:
        lines.append("(tidak ada data)")

    start_number = (page.page - 1) * page.page_size + 1
    for offset, user in enumerate(page.items):
        number = start_number + offset
        name = user.display_name or user.first_name or "(tanpa nama)"
        lines.append(f"{number}. {name}")
        lines.append(f"   ID internal: {format_user_code(user.id)}")
        lines.append(f"   Telegram ID: {user.telegram_user_id}")
        lines.append(f"   Terakhir aktif: {humanize_relative(user.last_seen_at)}")

    return "\n".join(lines)


def format_user_detail(user: User, group_count: int) -> str:
    username_line = f"@{user.username}" if user.username else "-"
    lines = [
        "👤 DETAIL PENGGUNA",
        f"Nama            : {user.display_name or user.first_name}",
        f"Username        : {username_line}",
        f"ID internal     : {format_user_code(user.id)}",
        f"Telegram ID     : {user.telegram_user_id}",
        f"Status          : {user.status}",
        f"Pertama terlihat: {humanize_relative(user.first_seen_at)}",
        f"Terakhir aktif  : {humanize_relative(user.last_seen_at)}",
        f"Grup tercatat   : {group_count}",
    ]
    return "\n".join(lines)


def format_group_list(page: Page[Group]) -> str:
    lines = [
        "🏘 DAFTAR GRUP",
        f"Total grup: {page.total_items}",
        f"Halaman: {page.page}/{page.total_pages}",
        "",
    ]

    if not page.items:
        lines.append("(tidak ada data)")

    start_number = (page.page - 1) * page.page_size + 1
    for offset, group in enumerate(page.items):
        number = start_number + offset
        lines.append(f"{number}. {group.title or '(tanpa nama)'}")
        lines.append(f"   Chat ID: {group.telegram_chat_id}")
        lines.append(f"   Terakhir aktif: {humanize_relative(group.last_activity_at)}")

    return "\n".join(lines)


def format_active_games_list(
    rows: list[tuple[GameSession, Group | None, str, int]]
) -> str:
    """`rows`: (game_session, group, nama_game, jumlah_pemain) -- satu tuple
    per sesi aktif, lintas grup. Tidak perlu paginasi (`Page`) seperti
    daftar user/grup -- jumlah sesi game aktif bersamaan selalu kecil."""
    lines = ["🎮 SESI GAME AKTIF", f"Total: {len(rows)}", ""]

    if not rows:
        lines.append("(tidak ada sesi aktif)")

    for game_session, group, game_name, player_count in rows:
        label = _GAME_STATUS_LABELS.get(game_session.status, game_session.status)
        group_title = group.title if group is not None else "(grup tidak ditemukan)"
        lines.append(f"#{game_session.id} · {game_name} · {label}")
        lines.append(f"   Grup: {group_title or '(tanpa nama)'}")
        lines.append(f"   Pemain: {player_count}")

    return "\n".join(lines)


def format_game_info_detail(
    game_session: GameSession,
    group: Group | None,
    metadata: GameMetadata,
    player_count: int,
) -> str:
    label = _GAME_STATUS_LABELS.get(game_session.status, game_session.status)
    group_title = group.title if group is not None else "(grup tidak ditemukan)"
    group_chat_id = group.telegram_chat_id if group is not None else "-"
    lines = [
        "🎮 DETAIL SESI GAME",
        f"Session ID     : {game_session.id}",
        f"Game           : {metadata.name}",
        f"Status         : {label}",
        f"Grup           : {group_title or '(tanpa nama)'}",
        f"Telegram Chat ID: {group_chat_id}",
        f"Pemain         : {player_count}/{metadata.max_players}",
        f"Dimulai        : {_humanize_optional(game_session.started_at)}",
        f"Selesai        : {_humanize_optional(game_session.finished_at)}",
    ]
    if game_session.cancellation_reason:
        lines.append(f"Alasan berhenti: {game_session.cancellation_reason}")
    return "\n".join(lines)


def format_group_detail(group: Group, member_count: int) -> str:
    lines = [
        "🏘 DETAIL GRUP",
        f"Nama              : {group.title or '(tanpa nama)'}",
        f"Telegram Chat ID  : {group.telegram_chat_id}",
        f"Status            : {group.status}",
        f"User terlihat     : {member_count}",
        f"Bot pertama aktif : {humanize_relative(group.bot_joined_at)}",
        f"Aktivitas terakhir: {humanize_relative(group.last_activity_at)}",
    ]
    return "\n".join(lines)


def format_admin_help(admin_role: AdminRole | None) -> str:
    role_label = _ROLE_LABELS.get(admin_role, "-") if admin_role is not None else "-"
    lines = [
        "🛠 DAFTAR COMMAND ADMIN",
        f"Role kamu: {role_label}",
        "✅ = bisa dipakai role kamu sekarang, 🔒 = butuh role lebih tinggi",
        "",
    ]
    for section_title, commands in _ADMIN_COMMAND_CATALOG:
        lines.append(section_title)
        for usage, description, minimum, private_only in commands:
            mark = "✅" if has_minimum_role(admin_role, minimum) else "🔒"
            scope = "" if private_only else " (bisa di grup)"
            lines.append(
                f"{mark} {usage} -- {description}{scope} [{_ROLE_LABELS[minimum]}]"
            )
        lines.append("")

    lines.append(
        "Kecuali disebut \"bisa di grup\", seluruh command di atas hanya berfungsi "
        "di chat privat dengan bot."
    )
    return "\n".join(lines)
