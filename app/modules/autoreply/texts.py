from __future__ import annotations

FEATURE_ENABLED_GLOBAL = "✅ Fitur autoreply diaktifkan secara global."
FEATURE_DISABLED_GLOBAL = "⏸ Fitur autoreply dinonaktifkan secara global."
GROUP_NOT_FOUND = "Grup tidak ditemukan. Bot harus pernah menerima pesan dari grup itu."
GROUP_FEATURE_ENABLED = "✅ Autoreply diaktifkan untuk grup {chat_id}."
GROUP_FEATURE_DISABLED = "⏸ Autoreply dinonaktifkan untuk grup {chat_id}."
GROUP_COMMAND_USAGE = "Gunakan: /msgcmd_group <chat_id> on|off"
NO_SYNC_YET = "Belum ada sinkronisasi yang tercatat."
TO_MSGCMD_NO_REPLY = (
    "Balas sebuah voice, document, photo, video, audio, atau sticker dengan /to_msgcmd."
)

FORMAT_HELP_TEXT = """\
📖 FORMAT TEMPLATE MSGCMD

Placeholder subject: (sbj) (sbj_dpn) (sbj_blk) (sbj_un) (sbj_id)
Placeholder object : (obj) (obj_dpn) (obj_blk) (obj_un) (obj_id)
Command & reply    : (rep_txt) (cmd_dpn) (cmd_ket)

Mention:
  @sbj(label)@   -> link ke subject
  @obj(label)@   -> link ke object (kosong jika tidak ada object)

Kondisi (tidak boleh nested):
  (isreply)...(/isreply)          (isnotreply)...(/isnotreply)
  (obj=sbj)...(/obj=sbj)          (obj!=sbj)...(/obj!=sbj)
  (obj=sbj_as_teks)                -> "teks" jika object = subject
  (ada_ket)...(/ada_ket)           (tdk_ada_ket)...(/tdk_ada_ket)
  (ada_dpn)...(/ada_dpn)           (tdk_ada_dpn)...(/tdk_ada_dpn)
  (ada_sbj_un)...(/ada_sbj_un)     (tdk_ada_sbj_un)...(/tdk_ada_sbj_un)
  (ada_obj_un)...(/ada_obj_un)     (tdk_ada_obj_un)...(/tdk_ada_obj_un)
  (ada_rep_txt)...(/ada_rep_txt)   (tdk_ada_rep_txt)...(/tdk_ada_rep_txt)

Tombol URL:
  (btn=https://contoh.com)Label(/btn)
  Skema diizinkan: https, http, tg. Label tidak boleh kosong.

Media (kolom Message diawali prefix ini, tanpa placeholder di dalamnya):
  *voice:<file_id>  *document:<file_id>  *photo:<file_id>
  *video:<file_id>  *audio:<file_id>     *sticker:<file_id>

Kolom wajib di Sheet: Command, Message, MatchAll, ReplyToSender,
ReplyToReplied, AdminOnly, Disabled (TRUE/FALSE/kosong)."""
