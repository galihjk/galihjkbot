from __future__ import annotations

from app.database.models.autoreply_sync_run import AutoreplySyncRun
from app.database.models.feature import Feature
from app.modules.autoreply.schemas import AutoreplySnapshotInfo, AutoreplySyncResult
from app.modules.autoreply.texts import NO_SYNC_YET
from app.utils.datetime import humanize_relative

_SYNC_STATUS_LABELS = {
    "running": "Sedang berjalan",
    "success": "Berhasil",
    "failed": "Gagal",
    "unchanged": "Tidak ada perubahan",
}


def _sync_status_label(status: str) -> str:
    return _SYNC_STATUS_LABELS.get(status, status)


def format_panel(
    feature: Feature | None,
    snapshot: AutoreplySnapshotInfo | None,
    recent_sync: AutoreplySyncRun | None,
) -> str:
    enabled = feature is not None and feature.enabled_globally
    lines = [
        "💬 MSGCMD AUTOREPLY",
        f"Feature        : {'Aktif' if enabled else 'Nonaktif'}",
        f"Runtime        : {'Ready' if snapshot is not None else 'Belum ada snapshot'}",
    ]
    if snapshot is not None:
        lines.extend(
            [
                f"Snapshot       : {snapshot.public_id}",
                f"Rule aktif     : {snapshot.active_rows}",
                f"Rule nonaktif  : {snapshot.disabled_rows}",
                f"Checksum       : {snapshot.source_checksum[:12]}...",
            ]
        )
    if recent_sync is not None:
        finished = (
            humanize_relative(recent_sync.finished_at)
            if recent_sync.finished_at is not None
            else "belum selesai"
        )
        lines.extend(
            [
                f"Sync terakhir  : {finished}",
                f"Status sync    : {_sync_status_label(recent_sync.status)}",
            ]
        )
    else:
        lines.append(f"Sync terakhir  : {NO_SYNC_YET}")
    lines.append("Sumber         : Google Sheet")
    return "\n".join(lines)


def format_reload_result(
    result: AutoreplySyncResult, active_snapshot: AutoreplySnapshotInfo | None
) -> str:
    if result.status == "success":
        duration = f"{(result.duration_ms or 0) / 1000:.2f} detik"
        lines = [
            "✅ MSGCMD BERHASIL DIMUAT",
            f"Snapshot baru : {result.public_id}",
            f"Rule aktif    : {result.active_rows}",
            f"Disabled      : {result.disabled_rows}",
            f"Warning       : {result.warning_count}",
            f"Durasi        : {duration}",
            "Sumber        : Google Sheet",
        ]
        return "\n".join(lines)

    if result.status == "unchanged":
        return (
            "ℹ️ Tidak ada perubahan pada Sheet (checksum sama).\n"
            f"Snapshot aktif tetap: {result.public_id}"
        )

    active_label = active_snapshot.public_id if active_snapshot is not None else "(belum ada)"
    lines = [
        "❌ MSGCMD GAGAL DIMUAT",
        f"Snapshot aktif tetap digunakan: {active_label}",
        f"Error       : {result.error_count}",
        f"Warning     : {result.warning_count}",
        f"Referensi   : {result.error_reference}",
        "",
        "Gunakan /msgcmd_sync_errors untuk detail.",
    ]
    return "\n".join(lines)


def format_sync_errors(sync_run: AutoreplySyncRun | None) -> str:
    if sync_run is None:
        return NO_SYNC_YET

    summary = sync_run.summary_json or {}
    errors = summary.get("errors", [])
    lines = [
        f"Sync {sync_run.public_id} -- status: {_sync_status_label(sync_run.status)}",
        f"Error: {sync_run.error_count}  Warning: {sync_run.warning_count}",
    ]
    if sync_run.error_reference:
        lines.append(f"Referensi: {sync_run.error_reference}")
    if errors:
        lines.append("")
        lines.extend(f"- {message}" for message in errors)
    return "\n".join(lines)
