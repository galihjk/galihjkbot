---
title: "Desain Pengembangan Modul Autoreply"
subtitle: "Implementasi Konkret Message Command Engine (MsgCmd)"
author: "Galih Project"
date: "6 Agustus 2026"
lang: id-ID
---

\newpage

# Ringkasan Eksekutif

Dokumen ini menetapkan desain pengembangan lengkap modul `autoreply` untuk bot Telegram berbasis Python, aiogram 3, SQLAlchemy 2, Alembic, dan SQLite. Implementasi konkret modul diberi nama **Message Command Engine (MsgCmd)**. MsgCmd membaca daftar aturan dari Google Sheet yang dipublikasikan sebagai CSV, menyimpannya sebagai snapshot lokal yang tervalidasi, mencocokkan pesan grup dengan aturan tersebut, merender template dinamis, lalu mengirim respons teks atau media melalui Telegram Bot API.

Google Sheet tetap menjadi **sumber kebenaran operasional**. SQLite berfungsi sebagai cache persisten dan penyimpan snapshot terakhir yang valid. Dengan desain ini, bot tetap dapat menjalankan autoreply ketika jaringan atau Google Sheet sementara tidak tersedia, tanpa mengubah sumber pengelolaan rule bagi administrator.

Modul mengikuti arsitektur modular monolith pada blueprint utama: handler hanya menangani Telegram, service menjalankan proses bisnis, repository mengakses database, presenter menyusun keluaran admin, feature registry mengendalikan aktivasi, dan global middleware menyediakan database, tracking, permission, logging, serta rate limit.

**URL sumber Google Sheet:**

https://docs.google.com/spreadsheets/d/e/2PACX-1vQVnG67buQbKnpBoz7iqdXW4qt5ZvNAeP6rngspeFYq36rl8Xw5PIoUbpfQmUyMTqqbj6yRd551pG9O/pub?output=csv

# 1. Status dan Metadata Dokumen

| Atribut | Nilai |
|---|---|
| Nama fitur | Autoreply |
| Implementasi | Message Command Engine (MsgCmd) |
| Feature key | `autoreply` |
| Modul aplikasi | `app.modules.autoreply` |
| Status dokumen | Baseline implementasi |
| Versi desain | 1.0 |
| Target rilis awal | Fase fitur lanjutan setelah fondasi dan game engine stabil |
| Runtime | Python, aiogram 3, satu proses long polling |
| Penyimpanan | SQLite, SQLAlchemy 2 asyncio, Alembic |
| Sumber rule | Google Sheet CSV terpublikasi |
| Zona waktu | Asia/Jakarta |

# 2. Posisi dalam Arsitektur Aplikasi

MsgCmd adalah implementasi pertama dari modul `autoreply`. Modul ini tidak mengubah fondasi bot dan tidak memiliki akses langsung ke konfigurasi rahasia, transaction database, timer game, atau file `.env` dari handler.

```text
Telegram Update
      |
      v
Global Middleware
DB | User Tracking | Group Tracking | Permission | Logging | Rate Limit
      |
      v
Command dan Game Routers
      |
      v
Autoreply Router (fallback pesan teks)
      |
      v
AutoreplyService
  |-- Feature gate
  |-- RuleMatcher
  |-- TemplateRenderer
  |-- ResponseSender
  `-- Metrics / audit
      |
      v
AutoreplyRepository <--> SQLite Snapshot
      ^
      |
GoogleSheetRuleSource --> AutoreplySyncService
```

Prinsip integrasi:

1. Feature key tetap `autoreply` agar konsisten dengan feature registry aplikasi.
2. Istilah `MsgCmd` digunakan untuk engine, model rule, command admin, dan komponen implementasi.
3. Google Sheet tidak dibaca pada setiap pesan.
4. Handler tidak melakukan parsing CSV, matching kompleks, atau query SQL.
5. Router autoreply diletakkan setelah router command dan game agar tidak mengambil update yang seharusnya diproses fitur lain.
6. Isi pesan umum tidak disimpan ke database atau log.

# 3. Sasaran Pengembangan

## 3.1 Sasaran utama

- Menyediakan autoreply berbasis aturan yang dapat dikelola tanpa mengubah kode aplikasi.
- Mempertahankan Google Sheet sebagai tempat pengelolaan rule oleh administrator.
- Mendukung pencocokan exact dan contains secara case-insensitive.
- Mendukung beberapa rule cocok pada satu pesan dan dieksekusi menurut urutan baris Sheet.
- Mendukung respons teks dengan data pengguna, reply, mention, kondisi, serta tombol URL.
- Mendukung respons media melalui Telegram `file_id`.
- Mendukung rule khusus administrator.
- Mendukung aktivasi global dan override per grup melalui feature registry.
- Tetap berfungsi setelah restart atau kegagalan koneksi ke Google Sheet.
- Memberikan monitoring, audit perubahan konfigurasi, dan command admin yang jelas.
- Aman digunakan bersama game engine dan modul lain.

## 3.2 Prinsip desain

- **Sheet as source of truth:** perubahan rule dilakukan pada Google Sheet.
- **Last-known-good:** kegagalan sinkronisasi tidak menghapus snapshot aktif.
- **Atomic activation:** rule baru aktif hanya setelah seluruh dokumen lolos validasi minimum.
- **Deterministic:** hasil matching, urutan rule, dan prioritas reply harus dapat diprediksi.
- **Fail isolated:** kegagalan satu rule tidak menjatuhkan bot atau membatalkan rule lain yang aman dijalankan.
- **Privacy by default:** teks pesan tidak dicatat.
- **Operationally simple:** administrator cukup mengubah Sheet lalu menjalankan reload.

# 4. Ruang Lingkup

## 4.1 Termasuk dalam versi pertama

- Sinkronisasi CSV melalui HTTPS.
- Validasi header dan baris.
- Snapshot rule di SQLite.
- Cache rule aktif di memori.
- Pencocokan pesan teks grup.
- Exact match dan contains match.
- Rule aktif/nonaktif.
- Rule khusus administrator aplikasi.
- Reply ke pengirim atau pesan yang dibalas.
- Template dinamis lengkap.
- Inline URL button.
- Respons text, voice, document, photo, video, audio, dan sticker.
- Command admin untuk status, reload, enable, disable, format, dan pengambilan media code.
- Feature gate global dan per grup.
- Metrics, structured logging, error reference, dan health status.
- Unit test dan integration test kritis.

## 4.2 Tidak termasuk dalam versi pertama

- Editor rule di Telegram.
- Penulisan balik ke Google Sheet.
- Regex sebagai mode pencocokan.
- Fuzzy matching atau semantic matching.
- Random weighted response.
- Jadwal aktif rule.
- Rule khusus topik forum Telegram.
- Rule bercabang berdasarkan grup langsung dari kolom Sheet.
- Upload file baru ke Telegram dari URL eksternal.
- Web admin.
- Analitik isi pesan.

Fondasi database dan service harus memungkinkan fitur tersebut ditambahkan tanpa mengubah kontrak inti modul.

# 5. Terminologi

| Istilah | Definisi |
|---|---|
| Autoreply | Modul fitur yang menerima pesan dan menghasilkan respons otomatis. |
| MsgCmd | Engine konkret yang mengimplementasikan autoreply berbasis command/trigger. |
| Rule | Satu baris konfigurasi dari Google Sheet. |
| Trigger | Nilai kolom `Command` yang dicari pada pesan. |
| Subject / `sbj` | Pengguna yang mengirim pesan pemicu. |
| Object / `obj` | Pengguna yang mengirim pesan yang sedang dibalas. |
| Reply text | Teks dari pesan yang dibalas, jika tersedia. |
| Rule set | Satu snapshot lengkap hasil sinkronisasi Google Sheet. |
| Active snapshot | Rule set tervalidasi yang digunakan runtime. |
| Last-known-good | Snapshot aktif terakhir yang tetap dipakai ketika sinkronisasi baru gagal. |
| Source row | Nomor baris rule pada Google Sheet/CSV, dimulai dari baris data pertama setelah header. |

# 6. Kebutuhan Fungsional

| ID | Kebutuhan |
|---|---|
| AR-F-001 | Sistem mengambil rule dari URL Google Sheet CSV yang ditentukan konfigurasi. |
| AR-F-002 | Sistem memvalidasi header wajib sebelum mengaktifkan rule set. |
| AR-F-003 | Sistem menyimpan setiap sinkronisasi yang berhasil sebagai snapshot SQLite. |
| AR-F-004 | Sistem tetap menggunakan snapshot aktif jika sinkronisasi gagal. |
| AR-F-005 | Sistem hanya mengevaluasi pesan yang memiliki `message.text`. |
| AR-F-006 | Sistem mengabaikan pesan dari bot secara default. |
| AR-F-007 | `MatchAll=TRUE` menggunakan pencocokan seluruh teks. |
| AR-F-008 | `MatchAll` selain TRUE menggunakan pencocokan substring. |
| AR-F-009 | Pencocokan tidak membedakan huruf besar dan kecil. |
| AR-F-010 | Semua rule aktif yang cocok dijalankan menurut urutan baris sumber. |
| AR-F-011 | `AdminOnly=TRUE` hanya dapat dipicu administrator aplikasi yang berwenang. |
| AR-F-012 | `ReplyToSender=TRUE` membalas pesan pemicu. |
| AR-F-013 | `ReplyToReplied=TRUE` membalas pesan yang dibalas oleh pengguna jika tersedia. |
| AR-F-014 | Jika kedua opsi reply TRUE, `ReplyToSender` memiliki prioritas. |
| AR-F-015 | Sistem merender placeholder, kondisi, mention, dan tombol sesuai kontrak template. |
| AR-F-016 | Sistem mengirim media menggunakan Telegram `file_id`. |
| AR-F-017 | Administrator dapat memuat ulang rule tanpa restart bot. |
| AR-F-018 | Administrator dapat memperoleh media code dari pesan Telegram. |
| AR-F-019 | Feature dapat diaktifkan/dinonaktifkan global dan per grup. |
| AR-F-020 | Sistem tidak menyimpan isi pesan pemicu atau hasil render ke log/database. |
| AR-F-021 | Kegagalan satu respons dicatat dan tidak menghentikan proses bot. |
| AR-F-022 | Status sinkronisasi dan snapshot aktif tampil pada health/admin panel. |

# 7. Sumber Rule Google Sheet

## 7.1 URL sumber

Konfigurasi default:

```text
https://docs.google.com/spreadsheets/d/e/2PACX-1vQVnG67buQbKnpBoz7iqdXW4qt5ZvNAeP6rngspeFYq36rl8Xw5PIoUbpfQmUyMTqqbj6yRd551pG9O/pub?output=csv
```

URL adalah dokumen terpublikasi dan bukan rahasia. Bot token, database URL, serta kredensial lain tidak boleh ditempatkan pada Sheet.

## 7.2 Kontrak kolom

Nama header bersifat wajib dan case-sensitive agar kesalahan konfigurasi cepat terdeteksi.

| Kolom | Wajib | Tipe logis | Nilai kosong | Makna |
|---|---:|---|---|---|
| `Command` | Ya | String | Tidak boleh | Trigger yang dicari pada pesan. |
| `Message` | Ya | String | Tidak boleh | Template teks atau kode media. |
| `MatchAll` | Ya | Boolean | FALSE | TRUE untuk exact match; selain TRUE untuk contains. |
| `ReplyToSender` | Ya | Boolean | FALSE | Membalas pesan pemicu. |
| `ReplyToReplied` | Ya | Boolean | FALSE | Membalas pesan yang sedang dibalas, jika ada. |
| `AdminOnly` | Ya | Boolean | FALSE | Membatasi rule untuk administrator aplikasi. |
| `Disabled` | Ya | Boolean | FALSE | TRUE berarti rule tidak dimasukkan ke cache aktif. |

Kolom tambahan diizinkan dan disimpan pada `source_payload_json`, tetapi tidak memengaruhi runtime versi pertama. Header wajib yang hilang membuat seluruh sinkronisasi gagal.

## 7.3 Normalisasi CSV

Parser menggunakan modul standar Python `csv` dengan ketentuan:

- encoding UTF-8 dan UTF-8 BOM didukung;
- comma menjadi delimiter;
- quoted comma, quoted newline, dan escaped quote didukung;
- CRLF dan LF didukung;
- nama header tidak dipangkas atau diubah;
- nilai cell dipangkas pada sisi kiri dan kanan;
- baris kosong penuh diabaikan;
- nomor `source_row` mempertahankan posisi asli pada CSV untuk diagnosis.

Boolean dinormalisasi case-insensitive:

- TRUE, `true`, `True`, atau nilai dengan spasi di sekelilingnya dianggap benar;
- FALSE, kosong, `false`, dan `False` dianggap salah;
- nilai lain menghasilkan error pada baris tersebut.

## 7.4 Klasifikasi validasi

| Tingkat | Contoh | Dampak |
|---|---|---|
| Fatal dokumen | HTTP gagal, CSV tidak dapat dibaca, header wajib hilang | Snapshot baru ditolak; snapshot lama tetap aktif. |
| Error baris | `Command` kosong, `Message` kosong, boolean invalid, media prefix tanpa `file_id` | Sinkronisasi ditolak jika ada error baris. |
| Warning baris | Kedua reply flag TRUE, object placeholder dipakai tetapi tidak selalu ada object | Snapshot dapat aktif; warning ditampilkan pada hasil reload. |
| Informasi | Rule `Disabled=TRUE` | Disimpan pada snapshot, tetapi tidak dimasukkan ke cache aktif. |

Versi pertama menggunakan kebijakan **strict snapshot**: satu error baris menolak seluruh snapshot. Kebijakan ini mencegah sebagian perubahan Sheet aktif tanpa disadari.

# 8. Semantik Rule dan Pencocokan

## 8.1 Input yang dievaluasi

- Chat type default: `group` dan `supergroup`.
- Private chat tidak diproses sebagai autoreply kecuali konfigurasi `AUTOREPLY_ALLOW_PRIVATE=true`.
- Channel post tidak diproses pada versi pertama.
- Hanya `message.text`; caption media tidak menjadi trigger.
- Pesan dari akun bot diabaikan ketika `AUTOREPLY_IGNORE_BOTS=true`.
- Command Telegram tetap dapat menjadi trigger setelah router command yang lebih spesifik memperoleh prioritas.
- Untuk command yang ditujukan ke bot, suffix `@username_bot` pada token command pertama dinormalisasi sebelum matching.

## 8.2 Normalisasi pembanding

Normalisasi runtime:

```python
normalized_message = unicodedata.normalize("NFKC", message_text).casefold()
normalized_trigger = unicodedata.normalize("NFKC", trigger).casefold()
```

Whitespace pesan tidak dipangkas atau digabung. Dengan demikian, exact match tetap benar-benar membandingkan seluruh teks setelah normalisasi Unicode dan huruf.

## 8.3 Mode exact

Jika `MatchAll=TRUE`:

```python
matched = normalized_message == normalized_trigger
```

Contoh:

- Trigger `halo` cocok dengan `HALO`.
- Trigger `halo` tidak cocok dengan `halo semua`.
- Trigger `/ping` cocok dengan `/ping@nama_bot` setelah normalisasi command mention.

## 8.4 Mode contains

Jika `MatchAll=FALSE` atau kosong:

```python
matched = normalized_trigger in normalized_message
```

Pencarian menggunakan kemunculan pertama untuk menghitung:

- `cmd_dpn`: teks sebelum trigger;
- `cmd_ket`: teks setelah trigger.

Contoh: trigger `peluk`, pesan `Rani peluk Budi` menghasilkan `cmd_dpn="Rani "` dan `cmd_ket=" Budi"`.

## 8.5 Banyak rule cocok

- Semua rule aktif yang cocok dijalankan.
- Urutan eksekusi sama dengan `source_row` dari atas ke bawah.
- Eksekusi dilakukan serial per pesan agar urutan respons stabil.
- Satu rule hanya dijalankan sekali per pesan.
- Batas keamanan default adalah 20 respons per pesan melalui `AUTOREPLY_MAX_RESPONSES_PER_MESSAGE`.
- Jika jumlah cocok melebihi batas, rule setelah batas tidak dijalankan dan warning dicatat tanpa isi pesan.

## 8.6 Rule administrator

`AdminOnly=TRUE` diperiksa melalui `PermissionService`, bukan username Telegram. Permission yang digunakan:

```text
autoreply.trigger_admin_rule
```

Default role yang memiliki permission: operator, admin, dan superadmin. Viewer tidak memperoleh permission ini kecuali dikonfigurasi khusus.

Jika user tidak berhak, rule dianggap tidak cocok dan bot tidak mengirim pesan penolakan. Hal ini mencegah kebocoran bahwa suatu trigger administrator tersedia.

## 8.7 Target reply

Prioritas:

1. Jika `ReplyToSender=TRUE`, respons menggunakan `reply_parameters.message_id` dari pesan pemicu.
2. Jika poin 1 salah dan `ReplyToReplied=TRUE` serta terdapat `reply_to_message`, respons membalas pesan tersebut.
3. Jika `ReplyToReplied=TRUE` tetapi tidak ada pesan yang dibalas, respons dikirim tanpa reply.
4. Jika semua flag FALSE, respons dikirim sebagai pesan biasa.

# 9. Tipe Respons

## 9.1 Deteksi tipe

Kolom `Message` dianggap respons media jika dimulai tepat dengan salah satu prefix berikut:

| Prefix | Telegram method | Nilai setelah prefix |
|---|---|---|
| `*voice:` | `sendVoice` | Voice `file_id` |
| `*document:` | `sendDocument` | Document `file_id` |
| `*photo:` | `sendPhoto` | Photo `file_id` |
| `*video:` | `sendVideo` | Video `file_id` |
| `*audio:` | `sendAudio` | Audio `file_id` |
| `*sticker:` | `sendSticker` | Sticker `file_id` |

Nilai lain diperlakukan sebagai template teks.

## 9.2 Ketentuan media

- `file_id` dipangkas dan tidak boleh kosong.
- Template placeholder tidak diproses di dalam `file_id`.
- Reply target tetap diterapkan pada media.
- Caption media tidak didukung pada versi pertama karena kontrak Sheet hanya menyediakan satu kolom `Message`.
- Untuk photo yang diterima Telegram sebagai beberapa ukuran, command `/to_msgcmd` memilih `file_id` dari ukuran terbesar.
- Jika Telegram menyatakan `file_id` invalid, error dicatat per rule dan sinkronisasi tetap dianggap valid karena validitas `file_id` hanya dapat dipastikan saat pengiriman.

## 9.3 Respons teks

- `parse_mode=HTML`.
- Link preview dinonaktifkan secara default.
- Data dinamis dari Telegram selalu di-escape.
- Markup HTML yang ditulis administrator pada template dipertahankan dan dikirim ke Telegram.
- Setelah tombol diambil dari template, teks hasil akhir tidak boleh kosong. Rule yang hanya berisi tombol dinyatakan invalid pada sinkronisasi.

# 10. Bahasa Template MsgCmd

## 10.1 Model data render

```python
@dataclass(frozen=True)
class TemplateUser:
    id: int | None
    first_name: str
    last_name: str
    username: str

@dataclass(frozen=True)
class TemplateContext:
    subject: TemplateUser | None
    object: TemplateUser | None
    reply_text: str
    cmd_prefix: str
    cmd_suffix: str
```

- `subject` berasal dari `message.from_user`.
- `object` berasal dari `message.reply_to_message.from_user`.
- `reply_text` hanya berasal dari `message.reply_to_message.text`.
- Jika Telegram mengirim pesan atas nama `sender_chat`, data user yang tidak tersedia menjadi string kosong.

## 10.2 Placeholder subject

| Sintaks | Hasil |
|---|---|
| `(sbj)` | Nama lengkap subject. |
| `(sbj_dpn)` | Nama depan subject. |
| `(sbj_blk)` | Nama belakang subject. |
| `(sbj_un)` | Username subject tanpa `@`. |
| `(sbj_id)` | Numeric Telegram user ID subject. |

## 10.3 Placeholder object

| Sintaks | Hasil |
|---|---|
| `(obj)` | Nama lengkap object. |
| `(obj_dpn)` | Nama depan object. |
| `(obj_blk)` | Nama belakang object. |
| `(obj_un)` | Username object tanpa `@`. |
| `(obj_id)` | Numeric Telegram user ID object. |

Jika tidak ada object, seluruh placeholder object menghasilkan string kosong.

## 10.4 Placeholder command dan reply

| Sintaks | Hasil |
|---|---|
| `(rep_txt)` | Teks pesan yang dibalas. |
| `(cmd_dpn)` | Teks sebelum kemunculan pertama trigger. |
| `(cmd_ket)` | Teks setelah kemunculan pertama trigger. |

## 10.5 Mention

| Sintaks | Hasil |
|---|---|
| `@sbj(label)@` | Link HTML `tg://user?id=...` menuju subject dengan teks `label`. |
| `@obj(label)@` | Link HTML menuju object; menjadi kosong jika object tidak ada. |

`label` di-escape sebagai teks HTML. Mention hanya dibuat jika numeric user ID tersedia.

## 10.6 Kondisi reply dan object

| Sintaks | Ditampilkan ketika |
|---|---|
| `(isreply)teks(/isreply)` | Ada `reply_to_message`. |
| `(isnotreply)teks(/isnotreply)` | Tidak ada `reply_to_message`. |
| `(obj=sbj)teks(/obj=sbj)` | Object dan subject memiliki user ID yang sama. |
| `(obj!=sbj)teks(/obj!=sbj)` | Object dan subject berbeda. Jika object tidak ada, kondisi dianggap berbeda. |
| `(obj=sbj_as_teks)` | Menghasilkan `teks` jika object sama dengan subject; selain itu kosong. |

## 10.7 Kondisi command

| Sintaks | Ditampilkan ketika |
|---|---|
| `(ada_ket)teks(/ada_ket)` | `cmd_ket` tidak kosong. |
| `(tdk_ada_ket)teks(/tdk_ada_ket)` | `cmd_ket` kosong. |
| `(ada_dpn)teks(/ada_dpn)` | `cmd_dpn` tidak kosong. |
| `(tdk_ada_dpn)teks(/tdk_ada_dpn)` | `cmd_dpn` kosong. |

## 10.8 Kondisi username

| Sintaks | Ditampilkan ketika |
|---|---|
| `(ada_sbj_un)teks(/ada_sbj_un)` | Subject memiliki username. |
| `(tdk_ada_sbj_un)teks(/tdk_ada_sbj_un)` | Subject tidak memiliki username. |
| `(ada_obj_un)teks(/ada_obj_un)` | Object memiliki username. |
| `(tdk_ada_obj_un)teks(/tdk_ada_obj_un)` | Object tidak memiliki username. |

## 10.9 Kondisi reply text

| Sintaks | Ditampilkan ketika |
|---|---|
| `(ada_rep_txt)teks(/ada_rep_txt)` | Pesan yang dibalas mempunyai `text`. |
| `(tdk_ada_rep_txt)teks(/tdk_ada_rep_txt)` | Tidak ada reply text. |

## 10.10 Tombol URL

Sintaks:

```text
(btn=https://example.com)Buka Situs(/btn)
```

Perilaku:

- blok dihapus dari teks pesan;
- setiap blok menghasilkan satu baris inline keyboard dengan satu tombol;
- urutan tombol mengikuti kemunculan dalam template;
- scheme yang diizinkan: `https`, `http`, dan `tg`;
- label tidak boleh kosong;
- URL tidak boleh mengandung control character;
- URL invalid membuat baris rule invalid saat sinkronisasi.

## 10.11 Urutan render

Urutan wajib:

1. Evaluasi blok `isreply` dan `isnotreply`.
2. Evaluasi blok `obj=sbj` dan `obj!=sbj`.
3. Evaluasi blok keberadaan `cmd_ket`, `cmd_dpn`, username, dan reply text.
4. Evaluasi `(obj=sbj_as_...)`.
5. Ganti placeholder subject, object, reply, dan command.
6. Bentuk mention subject/object.
7. Ekstrak dan validasi tombol.
8. Validasi panjang pesan dan markup Telegram.

Blok kondisi tidak boleh nested pada versi pertama. Validator mendeteksi pasangan tag yang tidak seimbang dan menolak rule. Panjang hasil render mengikuti batas Telegram; jika melebihi batas, respons tidak dikirim dan error dicatat.

# 11. Alur Runtime Pesan

```text
Message masuk
  |
  +-- bukan message.text ----------------------> selesai
  +-- sender bot dan ignore_bots=true ---------> selesai
  +-- chat type tidak diizinkan ---------------> selesai
  |
  v
FeatureService.is_enabled("autoreply", group)
  |
  +-- tidak aktif ------------------------------> selesai
  |
  v
Game/message router yang lebih spesifik sudah memproses?
  |
  +-- ya ---------------------------------------> selesai
  |
  v
Ambil immutable cache rule aktif
  |
  v
Filter disabled + admin permission + match
  |
  v
Untuk setiap rule cocok menurut source_row
  |
  +-- bangun TemplateContext
  +-- tentukan reply target
  +-- render teks / ambil media file_id
  +-- kirim melalui ResponseSender
  +-- catat metric tanpa isi pesan
  |
  v
selesai
```

Satu update tidak membuka transaction database hanya untuk membaca rule karena cache berada di memori. Database digunakan untuk feature gate, permission context yang sudah disediakan middleware, audit admin, dan pembaruan metric agregat yang tidak dilakukan per pesan secara sinkron.

# 12. Struktur Modul

```text
app/modules/autoreply/
├── __init__.py
├── router.py
├── admin_router.py
├── handlers.py
├── admin_handlers.py
├── callbacks.py
├── keyboards.py
├── presenters.py
├── schemas.py
├── constants.py
├── exceptions.py
├── service.py
├── matcher.py
├── template_renderer.py
├── response_sender.py
├── media_code_service.py
├── sync_service.py
├── cache.py
├── validators.py
├── texts.py
└── sources/
    ├── __init__.py
    ├── base.py
    └── google_sheet.py

app/database/models/
├── autoreply_rule_set.py
├── autoreply_rule.py
└── autoreply_sync_run.py

app/database/repositories/
└── autoreply_repository.py

tests/unit/autoreply/
├── test_matcher.py
├── test_template_renderer.py
├── test_rule_validator.py
├── test_media_detection.py
└── test_cache.py

tests/integration/autoreply/
├── test_sync_google_sheet.py
├── test_runtime_flow.py
├── test_feature_gate.py
├── test_restart_recovery.py
└── test_admin_commands.py
```

# 13. Tanggung Jawab Komponen

## 13.1 Router dan handler

- Memfilter tipe update.
- Mengambil dependency dari context aiogram.
- Memanggil service.
- Menjawab callback query.
- Mengirim presenter result.
- Tidak melakukan SQL, HTTP, parsing CSV, atau matching kompleks.

## 13.2 `AutoreplyService`

- Memeriksa feature gate dan scope chat.
- Mengambil snapshot cache.
- Mengorkestrasi matcher, renderer, dan sender.
- Menegakkan batas respons per pesan.
- Mengisolasi error per rule.

## 13.3 `MsgCmdRuleMatcher`

- Menormalisasi pesan dan trigger.
- Menentukan exact/contains.
- Menghitung `cmd_dpn` dan `cmd_ket`.
- Tidak mengakses Telegram API atau database.

## 13.4 `MsgCmdTemplateRenderer`

- Membentuk hasil teks dan inline keyboard.
- Meng-escape data dinamis.
- Mengimplementasikan grammar template.
- Tidak mengirim pesan.

## 13.5 `AutoreplyResponseSender`

- Memetakan response type ke method aiogram.
- Menerapkan reply parameters, parse mode, dan link preview.
- Menangani Telegram exception terkontrol.

## 13.6 `AutoreplySyncService`

- Mengambil CSV dari source.
- Memvalidasi dokumen dan baris.
- Membuat snapshot baru.
- Mengaktifkan snapshot secara atomik.
- Memuat ulang cache setelah commit.
- Menyimpan hasil sync dan audit.

## 13.7 `GoogleSheetRuleSource`

- Menggunakan `httpx.AsyncClient`.
- Hanya melakukan HTTP GET terhadap URL konfigurasi tetap.
- Mengembalikan bytes, metadata HTTP, dan checksum.
- Tidak mengetahui model database.

## 13.8 `AutoreplyRuleCache`

- Menyimpan immutable tuple dari rule aktif.
- Pergantian cache dilindungi `asyncio.Lock`.
- Pembaca tidak menunggu selama matching.
- Menyimpan metadata snapshot: ID, checksum, waktu aktivasi, jumlah rule.

# 14. Kontrak Service

```python
class AutoreplyService:
    async def handle_message(
        self,
        message: Message,
        current_user: UserContext | None,
        current_group: GroupContext | None,
        permissions: PermissionContext,
    ) -> AutoreplyExecutionResult: ...

class AutoreplySyncService:
    async def sync(
        self,
        triggered_by_user_id: int | None,
        reason: str,
    ) -> AutoreplySyncResult: ...

    async def load_active_snapshot(self) -> AutoreplySnapshotInfo | None: ...

class MsgCmdRuleMatcher:
    def match(self, rule: CachedAutoreplyRule, text: str) -> MatchResult: ...

class MsgCmdTemplateRenderer:
    def render(
        self,
        template: str,
        context: TemplateContext,
    ) -> RenderedTextResponse: ...

class AutoreplyResponseSender:
    async def send(
        self,
        message: Message,
        rule: CachedAutoreplyRule,
        match: MatchResult,
    ) -> SendResult: ...

class MediaCodeService:
    def extract(self, replied_message: Message) -> MediaCodeResult: ...
```

Result object tidak boleh membawa seluruh isi pesan ke logging layer. Gunakan rule ID, source row, chat ID, user ID, tipe respons, status, dan durasi.

# 15. Desain Database

## 15.1 `autoreply_rule_sets`

| Kolom | Tipe | Aturan |
|---|---|---|
| `id` | Integer PK | Internal ID. |
| `public_id` | String UNIQUE | Format `ARS-000001`. |
| `source_url` | Text | URL sumber saat sync. |
| `source_checksum` | String(64) | SHA-256 bytes CSV. |
| `source_etag` | String nullable | Metadata HTTP jika tersedia. |
| `source_last_modified` | String nullable | Metadata HTTP jika tersedia. |
| `status` | String | `active`, `superseded`, `archived`. |
| `total_rows` | Integer | Jumlah baris data. |
| `active_rows` | Integer | Rule runtime aktif. |
| `disabled_rows` | Integer | Rule `Disabled=TRUE`. |
| `warning_count` | Integer | Jumlah warning validasi. |
| `imported_by_user_id` | FK nullable | Admin pemicu sync; null untuk startup. |
| `imported_at` | DateTime TZ | Waktu snapshot dibuat. |
| `activated_at` | DateTime TZ nullable | Waktu dijadikan aktif. |
| `created_at` | DateTime TZ | Audit standar. |
| `updated_at` | DateTime TZ | Audit standar. |

Constraint: maksimum satu rule set berstatus `active` secara logis, dijaga oleh transaction service dan setting `autoreply.active_rule_set_id`.

## 15.2 `autoreply_rules`

| Kolom | Tipe | Aturan |
|---|---|---|
| `id` | Integer PK | Internal ID. |
| `rule_set_id` | FK | Relasi snapshot. |
| `source_row` | Integer | Posisi rule di CSV. |
| `command` | Text | Trigger asli. |
| `normalized_command` | Text | NFKC + casefold. |
| `message_template` | Text | Template atau media code. |
| `response_type` | String | `text`, `voice`, `document`, `photo`, `video`, `audio`, `sticker`. |
| `media_file_id` | Text nullable | Nilai setelah media prefix. |
| `match_all` | Boolean | Exact vs contains. |
| `reply_to_sender` | Boolean | Reply pesan pemicu. |
| `reply_to_replied` | Boolean | Reply pesan target. |
| `admin_only` | Boolean | Permission gate. |
| `disabled` | Boolean | Tidak masuk cache aktif. |
| `source_payload_json` | JSON | Semua kolom sumber. |
| `created_at` | DateTime TZ | Audit standar. |
| `updated_at` | DateTime TZ | Audit standar. |

Constraint dan index:

- UNIQUE `(rule_set_id, source_row)`;
- INDEX `(rule_set_id, disabled, source_row)`;
- `source_row > 0`;
- `command <> ''`;
- `message_template <> ''`.

## 15.3 `autoreply_sync_runs`

| Kolom | Tipe | Aturan |
|---|---|---|
| `id` | Integer PK | Internal ID. |
| `public_id` | String UNIQUE | Format `ASY-000001`. |
| `reason` | String | `startup`, `manual`, `scheduled`. |
| `triggered_by_user_id` | FK nullable | Pemicu manual. |
| `source_url` | Text | URL yang digunakan. |
| `status` | String | `running`, `success`, `failed`, `unchanged`. |
| `http_status` | Integer nullable | Status HTTP. |
| `source_checksum` | String nullable | SHA-256 hasil unduh. |
| `total_rows` | Integer nullable | Statistik parsing. |
| `active_rows` | Integer nullable | Statistik parsing. |
| `disabled_rows` | Integer nullable | Statistik parsing. |
| `warning_count` | Integer | Jumlah warning. |
| `error_count` | Integer | Jumlah error. |
| `error_reference` | String nullable | Referensi global error. |
| `summary_json` | JSON | Ringkasan warning/error tanpa data sensitif. |
| `started_at` | DateTime TZ | Mulai. |
| `finished_at` | DateTime TZ nullable | Selesai. |
| `created_at` | DateTime TZ | Audit standar. |
| `updated_at` | DateTime TZ | Audit standar. |

## 15.4 Settings dan feature registry

Settings:

| Key | Nilai |
|---|---|
| `autoreply.active_rule_set_id` | ID snapshot aktif. |
| `autoreply.last_successful_sync_at` | Waktu sync berhasil. |
| `autoreply.last_sync_status` | Status terakhir. |

Feature registry:

- `features.feature_key = "autoreply"`;
- `enabled_globally` mengendalikan aktivasi global;
- `group_features` dapat override per grup;
- konfigurasi grup dapat memuat `allow_during_active_game` dan `max_responses_per_message`.

# 16. Algoritma Sinkronisasi

## 16.1 Proses utama

```text
Buat sync_run=running
  |
HTTP GET source URL dengan timeout
  |
Validasi status, ukuran, encoding
  |
Hitung SHA-256
  |
Jika checksum sama dengan snapshot aktif
  +--> sync_run=unchanged --> selesai
  |
Parse CSV
  |
Validasi header dan seluruh baris
  |
Jika error
  +--> sync_run=failed; pertahankan snapshot lama
  |
BEGIN TRANSACTION
  |-- insert rule_set baru
  |-- insert seluruh rule
  |-- ubah snapshot lama menjadi superseded
  |-- ubah snapshot baru menjadi active
  |-- update setting active_rule_set_id
COMMIT
  |
Bangun immutable cache baru
  |
Swap cache secara atomik
  |
Audit + sync_run=success
```

## 16.2 Batas HTTP

- Connect timeout: 5 detik.
- Read timeout total: 15 detik.
- Maksimum redirect: 5.
- Maksimum ukuran CSV: 5 MiB.
- User-Agent: nama aplikasi dan versi.
- TLS verification wajib aktif.
- Tidak ada retry pada 4xx.
- Maksimum dua percobaan untuk timeout/5xx dengan jitter singkat pada sync terjadwal; reload manual melaporkan hasil percobaan akhir.

## 16.3 Startup

1. Buka database dan jalankan migration check.
2. Muat snapshot aktif dari SQLite ke cache.
3. Jika snapshot tersedia, modul berstatus `READY_CACHED`.
4. Jika `AUTOREPLY_STARTUP_SYNC=true`, coba sinkronisasi.
5. Jika sync gagal tetapi snapshot tersedia, status menjadi `DEGRADED_CACHED`; bot tetap berjalan.
6. Jika sync gagal dan belum ada snapshot, status menjadi `DEGRADED_EMPTY`; autoreply tidak merespons dan superadmin diberi notifikasi.
7. Kegagalan autoreply tidak boleh mencegah long polling bot dimulai.

## 16.4 Retensi snapshot

- Simpan tiga snapshot sukses terakhir secara default.
- Snapshot aktif tidak boleh dihapus.
- Cleanup dilakukan setelah aktivasi sukses, bukan sebelum.
- Data sync run disimpan 30 hari atau mengikuti kebijakan metrics/log aplikasi.

# 17. Cache dan Concurrency

```python
class AutoreplyRuleCache:
    def __init__(self) -> None:
        self._snapshot = AutoreplyCacheSnapshot.empty()
        self._swap_lock = asyncio.Lock()

    def get(self) -> AutoreplyCacheSnapshot:
        return self._snapshot

    async def replace(self, snapshot: AutoreplyCacheSnapshot) -> None:
        async with self._swap_lock:
            self._snapshot = snapshot
```

Ketentuan:

- Snapshot dan rule menggunakan dataclass frozen/tuple.
- Matching tidak memegang lock.
- Dua reload bersamaan dicegah oleh `AutoreplySyncLock` global.
- Reload kedua menerima status “sinkronisasi sedang berjalan”.
- Pesan yang sedang diproses boleh menyelesaikan eksekusi dengan snapshot lama.
- Pesan berikutnya otomatis menggunakan snapshot baru.
- Pengiriman beberapa respons untuk satu pesan tetap serial.
- Pesan berbeda dapat diproses paralel oleh aiogram.

# 18. Konfigurasi Aplikasi

Tambahan `.env.example`:

```text
FEATURE_AUTOREPLY=false
AUTOREPLY_SOURCE_URL=https://docs.google.com/spreadsheets/d/e/2PACX-1vQVnG67buQbKnpBoz7iqdXW4qt5ZvNAeP6rngspeFYq36rl8Xw5PIoUbpfQmUyMTqqbj6yRd551pG9O/pub?output=csv
AUTOREPLY_STARTUP_SYNC=true
AUTOREPLY_SYNC_INTERVAL_SECONDS=0
AUTOREPLY_HTTP_CONNECT_TIMEOUT_SECONDS=5
AUTOREPLY_HTTP_READ_TIMEOUT_SECONDS=15
AUTOREPLY_MAX_SOURCE_BYTES=5242880
AUTOREPLY_MAX_RESPONSES_PER_MESSAGE=20
AUTOREPLY_KEEP_SNAPSHOTS=3
AUTOREPLY_ALLOW_PRIVATE=false
AUTOREPLY_IGNORE_BOTS=true
AUTOREPLY_DISABLE_LINK_PREVIEW=true
AUTOREPLY_PARSE_MODE=HTML
```

`AUTOREPLY_SYNC_INTERVAL_SECONDS=0` berarti periodic sync nonaktif. Operasi baseline menggunakan sync saat startup dan reload manual. Jika diaktifkan, nilai minimum yang diperbolehkan adalah 60 detik.

Konfigurasi rahasia tidak ada pada modul ini. URL sumber boleh diubah melalui environment saat deployment, tetapi command Telegram tidak boleh menerima URL arbitrary untuk mencegah SSRF.

# 19. Router dan Integrasi Modul

Urutan registrasi yang disarankan:

```python
def register_modules(dispatcher: Dispatcher) -> None:
    dispatcher.include_router(get_common_router())
    dispatcher.include_router(get_admin_router())
    dispatcher.include_router(get_games_router())
    dispatcher.include_router(get_autoreply_admin_router())
    dispatcher.include_router(get_autoreply_router())  # fallback terakhir
```

Ketentuan interaksi dengan game:

- Command game dan callback game selalu lebih dahulu.
- Pesan yang diklaim handler game tidak diteruskan ke autoreply.
- Pesan yang tidak relevan dengan state game masih dapat diproses autoreply.
- Konfigurasi grup `allow_during_active_game=false` dapat menonaktifkan seluruh autoreply ketika session game berstatus aktif.
- Default baseline `allow_during_active_game=true` agar fungsi grup umum tetap tersedia; game tertentu dapat menggunakan message exclusivity jika aturan permainannya membutuhkan.
- Autoreply tidak dapat membuat, membatalkan, atau mengubah state game.

# 20. Hak Akses

## 20.1 Permission

| Permission | Viewer | Operator | Admin | Superadmin |
|---|---:|---:|---:|---:|
| `autoreply.view_status` | Ya | Ya | Ya | Ya |
| `autoreply.view_format` | Ya | Ya | Ya | Ya |
| `autoreply.trigger_admin_rule` | Tidak | Ya | Ya | Ya |
| `autoreply.reload` | Tidak | Ya | Ya | Ya |
| `autoreply.toggle_group` | Tidak | Ya | Ya | Ya |
| `autoreply.toggle_global` | Tidak | Tidak | Ya | Ya |
| `autoreply.extract_media_code` | Tidak | Ya | Ya | Ya |
| `autoreply.view_sync_errors` | Ya | Ya | Ya | Ya |

Identitas selalu numeric Telegram user ID. Username tidak digunakan untuk otorisasi.

## 20.2 Scope command admin

- Status, reload, enable/disable global, dan laporan error diprioritaskan di private chat bot.
- Command group toggle menerima numeric chat ID dari private chat.
- `/to_msgcmd` dapat digunakan di private chat atau grup aktif oleh administrator; praktik operasional yang disarankan adalah meneruskan media ke private chat bot agar tidak memenuhi grup.
- Aksi perubahan dicatat di `audit_logs`.

# 21. Command dan Admin Panel

## 21.1 Daftar command

| Command | Fungsi |
|---|---|
| `/msgcmd` | Membuka panel MsgCmd. |
| `/msgcmd_status` | Menampilkan feature state, snapshot, dan sync terakhir. |
| `/msgcmd_reload` | Mengambil, memvalidasi, dan mengaktifkan snapshot baru. |
| `/msgcmd_enable` | Mengaktifkan feature global. |
| `/msgcmd_disable` | Menonaktifkan feature global. |
| `/msgcmd_group <chat_id> on` | Mengaktifkan override pada grup. |
| `/msgcmd_group <chat_id> off` | Menonaktifkan override pada grup. |
| `/format_msgcmd` | Menampilkan dokumentasi template. |
| `/to_msgcmd` | Mengambil media code dari pesan non-teks yang dibalas. |
| `/msgcmd_sync_errors` | Menampilkan ringkasan error/warning sync terakhir. |

## 21.2 Panel

```text
💬 MSGCMD AUTOREPLY
Feature        : Aktif
Runtime        : Ready
Snapshot       : ARS-000042
Rule aktif     : 128
Rule nonaktif  : 17
Checksum       : 97ab3c...e12f
Sync terakhir  : 6 Agustus 2026 14.20 WIB
Status sync    : Berhasil
Sumber         : Google Sheet

[🔄 Reload] [📊 Detail]
[🧩 Grup] [📖 Format]
[⏸ Nonaktifkan]
```

## 21.3 Hasil reload sukses

```text
✅ MSGCMD BERHASIL DIMUAT
Snapshot baru : ARS-000043
Rule aktif    : 129
Disabled      : 17
Warning       : 2
Durasi        : 1,24 detik
Sumber        : Google Sheet
```

## 21.4 Hasil reload gagal

```text
❌ MSGCMD GAGAL DIMUAT
Snapshot aktif tetap digunakan: ARS-000042
Error baris : 2
Warning     : 1
Referensi   : ERR-A82F10

Gunakan /msgcmd_sync_errors untuk detail.
```

Detail error tidak menampilkan isi penuh template. Contoh: `Baris 18: nilai AdminOnly harus TRUE, FALSE, atau kosong.`

## 21.5 `/to_msgcmd`

Jika command membalas media:

```text
*sticker:CAACAgUAAxkBAA...
```

Jika tidak membalas pesan:

```text
Balas sebuah voice, document, photo, video, audio, atau sticker dengan /to_msgcmd.
```

Jika membalas text:

```text
Pesan yang dibalas harus berupa media non-teks.
```

# 22. Error Handling

Exception domain:

```python
class AutoreplyError(Exception): ...
class AutoreplySourceFetchError(AutoreplyError): ...
class AutoreplySourceTooLargeError(AutoreplyError): ...
class AutoreplyCSVParseError(AutoreplyError): ...
class AutoreplyHeaderError(AutoreplyError): ...
class AutoreplyRuleValidationError(AutoreplyError): ...
class AutoreplySyncInProgressError(AutoreplyError): ...
class AutoreplySnapshotNotFoundError(AutoreplyError): ...
class AutoreplyTemplateError(AutoreplyError): ...
class AutoreplySendError(AutoreplyError): ...
class UnsupportedMediaTypeError(AutoreplyError): ...
```

Kebijakan:

- Error sync menghasilkan satu error reference dan mempertahankan snapshot lama.
- Error render satu rule: rule tersebut dilewati, rule berikutnya tetap dijalankan.
- `TelegramBadRequest`: catat rule/source row dan lanjutkan.
- `TelegramForbiddenError`: tandai grup sesuai group tracking policy dan hentikan respons untuk update tersebut.
- `TelegramRetryAfter`: hentikan sisa respons update untuk mencegah flood; serahkan retry policy pada Telegram service layer.
- Error tak terduga diteruskan ke global error handler setelah konteks minimal dicatat.
- Stack trace tidak ditampilkan di Telegram.

# 23. Logging, Metrics, dan Audit

## 23.1 Structured log

Field yang relevan:

```text
timestamp
level
module=autoreply
operation
telegram_user_id
telegram_chat_id
rule_set_id
rule_id
source_row
response_type
matched_rules_count
sent_rules_count
duration_ms
sync_run_id
error_reference
```

Dilarang dicatat:

- isi message.text;
- isi reply text;
- template hasil render;
- bot token;
- file `.env`;
- URL yang mengandung kredensial.

## 23.2 Metrics

| Metric | Unit |
|---|---|
| `autoreply_rules_active` | count |
| `autoreply_rules_disabled` | count |
| `autoreply_matches_total` | count |
| `autoreply_responses_sent_total` | count |
| `autoreply_response_errors_total` | count |
| `autoreply_messages_evaluated_total` | count |
| `autoreply_sync_success_total` | count |
| `autoreply_sync_failed_total` | count |
| `autoreply_last_sync_timestamp` | timestamp |
| `autoreply_sync_duration_ms` | millisecond |
| `autoreply_cache_age_seconds` | second |

Counter runtime dapat disimpan di memory dan diflush berkala ke `system_metrics`, bukan satu insert per pesan.

## 23.3 Audit

Aksi yang dicatat:

- enable/disable global;
- enable/disable grup;
- reload manual;
- aktivasi snapshot;
- rollback snapshot jika fitur tersebut ditambahkan;
- perubahan setting periodic sync.

Audit menyimpan old/new value dan actor user ID, tanpa isi pesan umum.

# 24. Security dan Privacy

- Source URL harus HTTPS dan berasal dari konfigurasi deployment.
- Command admin tidak boleh menerima URL sumber baru pada runtime.
- TLS verification tidak boleh dinonaktifkan.
- Ukuran response dibatasi untuk mencegah memory exhaustion.
- CSV diproses sebagai data, tidak dieksekusi sebagai kode.
- Tidak ada `eval`, dynamic import, atau ekspresi Python dari Sheet.
- Data Telegram yang disisipkan ke HTML di-escape dengan `html.escape(..., quote=True)`.
- Mention hanya dibangun dari numeric user ID.
- URL button dibatasi scheme yang diizinkan.
- User ID untuk admin diperiksa melalui permission service.
- Pesan dari bot diabaikan untuk mencegah loop antarbot.
- Isi pesan tidak disimpan.
- Google Sheet terpublikasi harus dianggap dapat dibaca publik; jangan menaruh data rahasia atau pribadi di dalamnya.
- Media `file_id` bukan bot token, tetapi tetap hanya digunakan untuk kebutuhan konten bot.

# 25. Performance dan Batas Operasional

Target awal untuk satu TV box Termux:

| Parameter | Target |
|---|---|
| Rule aktif normal | sampai 1.000 |
| Rule aktif maksimum teruji | 5.000 |
| Ukuran CSV maksimum | 5 MiB |
| Waktu matching 1.000 rule | < 25 ms pada perangkat produksi target |
| Respons maksimum per pesan | 20 |
| Cache read | tanpa database query |
| Proses bot | satu process |

Versi pertama menggunakan linear scan sesuai urutan baris. Hal ini sederhana dan memastikan urutan deterministik. Optimasi indeks trigger hanya dilakukan jika profiling menunjukkan kebutuhan, karena contains matching dan banyak rule cocok tetap memerlukan evaluasi yang hati-hati.

# 26. Lifecycle dan Recovery

## 26.1 Startup

- Load active snapshot.
- Validate cache construction.
- Optional startup sync.
- Register routers.
- Start polling.
- Notifikasi superadmin mencantumkan status autoreply.

Contoh:

```text
Server Started
Autoreply: Ready Cached
Snapshot: ARS-000042
Rules: 128 active / 17 disabled
Startup sync: Failed, cached snapshot retained
```

## 26.2 Shutdown

- Tidak ada state pesan yang perlu dipersistenkan.
- Sync task yang sedang berjalan dibatalkan dengan aman sebelum database engine ditutup.
- Snapshot aktif sudah berada di SQLite sehingga tidak perlu dump tambahan.

## 26.3 Restart

- Rule tidak hilang.
- Tidak ada retry pesan lama.
- Update pending mengikuti kebijakan global `TELEGRAM_DROP_PENDING_UPDATES`.
- Jika update lama diterima setelah restart, rule set aktif saat update diproses yang digunakan.

# 27. Strategi Testing

## 27.1 Unit test matcher

- Exact cocok dengan perbedaan huruf.
- Exact tidak cocok jika ada prefix/suffix.
- Contains cocok di awal, tengah, dan akhir.
- Contains memakai occurrence pertama untuk `cmd_dpn`/`cmd_ket`.
- Unicode NFKC dan casefold.
- Trigger kosong ditolak validator.
- Multiple rule mempertahankan source order.
- AdminOnly benar/salah.

## 27.2 Unit test renderer

- Seluruh placeholder subject.
- Seluruh placeholder object.
- Object kosong.
- Reply text ada/tidak.
- Subject sama dengan object.
- Subject berbeda dengan object.
- Seluruh conditional pair.
- Mention valid dan object mention kosong.
- HTML escape nama, username, dan reply text.
- Satu dan beberapa tombol.
- URL invalid.
- Tag tidak seimbang.
- Conditional nested ditolak.
- Output terlalu panjang.

## 27.3 Unit test media

- Deteksi setiap prefix.
- `file_id` kosong.
- Text yang menyerupai prefix tetapi tidak tepat.
- Photo memilih ukuran terbesar.
- Unsupported media pada `/to_msgcmd`.

## 27.4 Integration test sync

- Startup tanpa snapshot dan source sukses.
- Startup dengan snapshot dan source gagal.
- Reload checksum sama menghasilkan `unchanged`.
- Header hilang menolak snapshot.
- Satu baris invalid menolak seluruh snapshot.
- Transaction gagal sebelum active switch.
- Cache tetap lama jika commit gagal.
- Dua reload bersamaan.
- Retensi snapshot.

## 27.5 Integration test runtime

- Feature global off.
- Group override off.
- Dua grup berjalan paralel.
- Beberapa rule cocok dan terkirim berurutan.
- Satu send gagal, rule berikutnya tetap berjalan.
- Telegram flood wait menghentikan sisa respons.
- Pesan game yang diklaim tidak masuk autoreply.
- Pesan non-game saat game aktif dapat diproses sesuai config.
- AdminOnly menggunakan numeric user ID/permission.
- Bot sender diabaikan.

## 27.6 Acceptance test

1. Edit satu rule pada Google Sheet.
2. Jalankan `/msgcmd_reload`.
3. Pastikan snapshot baru aktif dan statistik benar.
4. Kirim trigger pada grup aktif.
5. Pastikan hasil template dan reply sesuai.
6. Putuskan koneksi internet.
7. Restart bot.
8. Pastikan snapshot terakhir masih merespons.
9. Buat baris invalid pada Sheet.
10. Reload dan pastikan snapshot aktif tidak berubah.

# 28. Kriteria Penerimaan

- Semua migration dapat dijalankan pada database kosong dan database existing.
- Bot dapat startup tanpa akses Google Sheet jika snapshot tersedia.
- Tidak ada isi pesan pada log aplikasi, error log, audit log, atau tabel module.
- Semua sintaks template pada dokumen ini memiliki unit test.
- Urutan rule sama dengan urutan Sheet.
- Google Sheet tetap menjadi satu-satunya tempat pengelolaan rule versi pertama.
- Reload invalid tidak pernah menghasilkan cache parsial.
- Enable/disable mengikuti feature registry.
- Semua admin action menggunakan permission service dan audit log.
- Autoreply tidak mengganggu handler command dan game yang lebih spesifik.
- Health panel dapat menunjukkan READY, DEGRADED_CACHED, atau DEGRADED_EMPTY.
- Deployment Termux tidak membutuhkan service tambahan.

# 29. Migration Alembic

Revision awal, contoh nama:

```text
20260806_01_add_autoreply_msgcmd_tables.py
```

Operasi upgrade:

1. Buat `autoreply_rule_sets`.
2. Buat `autoreply_rules`.
3. Buat `autoreply_sync_runs`.
4. Buat index dan foreign key.
5. Insert feature `autoreply` jika belum ada, dengan `enabled_globally=false`.
6. Insert setting default yang diperlukan.

Operasi downgrade:

- Drop tabel dalam urutan child ke parent.
- Hapus setting module.
- Jangan menghapus record feature jika telah digunakan konfigurasi lain tanpa pemeriksaan eksplisit.

Migration tidak melakukan HTTP request dan tidak mengisi rule dari Google Sheet. Initial sync dilakukan aplikasi setelah startup.

# 30. Rencana Implementasi

## Tahap 1 — Model dan migration

- Tambah enums/status.
- Buat tiga model database.
- Buat Alembic revision.
- Buat repository dan test transaction.

**Selesai jika:** migration up/down berhasil dan repository dapat membaca active snapshot.

## Tahap 2 — Source, parser, dan validator

- Implementasi HTTP source.
- Parsing CSV.
- Normalisasi boolean.
- Validator header, row, media, template, dan button.
- Checksum source.

**Selesai jika:** fixture CSV valid/invalid menghasilkan report deterministik.

## Tahap 3 — Snapshot dan cache

- Implementasi sync run.
- Atomic snapshot activation.
- Last-known-good.
- Immutable cache dan sync lock.
- Retensi snapshot.

**Selesai jika:** kegagalan transaction atau source tidak mengubah cache aktif.

## Tahap 4 — Matcher dan renderer

- Exact/contains.
- Command prefix/suffix.
- Seluruh placeholder dan conditional.
- HTML escaping.
- URL button.

**Selesai jika:** seluruh grammar memiliki unit test dan output stabil.

## Tahap 5 — Sender dan runtime handler

- Text/media sender.
- Reply parameters.
- Telegram exception policy.
- Feature gate dan permission.
- Router fallback.

**Selesai jika:** integration test message-to-response lulus.

## Tahap 6 — Admin tools

- Panel `/msgcmd`.
- Status/reload/toggle.
- Group override.
- Format help.
- Media code extraction.
- Sync error presenter.

**Selesai jika:** seluruh aksi memiliki permission dan audit.

## Tahap 7 — Monitoring dan production hardening

- Metrics dan health integration.
- Startup notification.
- Load/performance test.
- Termux smoke test.
- Dokumentasi operasi.

**Selesai jika:** bot restart offline menggunakan cached snapshot dan tidak mengganggu game aktif sesuai engine.

# 31. SOP Operasional

## 31.1 Aktivasi pertama

1. Deploy migration.
2. Pastikan `AUTOREPLY_SOURCE_URL` berisi URL yang ditetapkan.
3. Start bot dengan `FEATURE_AUTOREPLY=false`.
4. Jalankan `/msgcmd_reload` dari private chat admin.
5. Periksa warning dan jumlah rule.
6. Jalankan beberapa acceptance test pada grup testing.
7. Aktifkan global menggunakan `/msgcmd_enable`.
8. Atur override grup bila diperlukan.
9. Pantau `/msgcmd_status` dan `/health`.

## 31.2 Mengubah rule

1. Edit Google Sheet.
2. Pastikan kolom wajib tidak diubah.
3. Gunakan TRUE/FALSE atau kosong pada kolom boolean.
4. Jalankan `/msgcmd_reload`.
5. Jika gagal, buka `/msgcmd_sync_errors` dan perbaiki baris.
6. Jalankan reload ulang.
7. Uji trigger pada grup testing.

## 31.3 Menambahkan media

1. Kirim atau forward media ke bot.
2. Balas media tersebut dengan `/to_msgcmd`.
3. Salin output, contoh `*voice:<file_id>`.
4. Tempel pada kolom `Message`.
5. Reload dan uji.

## 31.4 Menangani source tidak tersedia

- Jangan disable feature jika snapshot cache masih valid.
- Periksa status jaringan dan source URL.
- Bot akan menggunakan last-known-good.
- Reload dilakukan setelah koneksi pulih.
- Jika status `DEGRADED_EMPTY`, perbaiki source lalu reload sebelum mengaktifkan feature.

# 32. Risiko dan Mitigasi

| Risiko | Dampak | Mitigasi |
|---|---|---|
| Google Sheet tidak tersedia | Rule baru tidak dapat diambil | Snapshot last-known-good. |
| Header diubah | Seluruh import gagal | Strict header validation dan laporan jelas. |
| Rule contains terlalu umum | Banyak respons/spam | Row review, limit 20, metrics, group toggle. |
| Beberapa admin reload bersamaan | Race snapshot | Global sync lock. |
| Template HTML invalid | Telegram menolak pesan | Validator dasar, error per rule, testing. |
| Nama pengguna mengandung markup | HTML injection | Escape seluruh data dinamis. |
| Media `file_id` tidak valid | Send gagal | Error terisolasi, `/to_msgcmd`, monitoring. |
| Autoreply menangkap pesan game | Gangguan permainan | Router terakhir dan game exclusivity. |
| CSV sangat besar | Memory/CPU tinggi | Batas 5 MiB dan target rule. |
| Bot membalas bot lain | Loop | Ignore bot sender default. |
| Partial update aktif | Perilaku tidak konsisten | Strict validation dan atomic switch. |
| Logging bocorkan isi pesan | Risiko privasi | Larangan content logging dan test log. |

# 33. Keputusan Baseline

| Keputusan | Nilai final |
|---|---|
| Nama modul | Autoreply |
| Engine | MsgCmd |
| Feature key | `autoreply` |
| Source of truth | Google Sheet published CSV |
| Runtime source | Immutable memory cache dari SQLite snapshot |
| Match mode | Exact atau contains |
| Case sensitivity | Case-insensitive, Unicode NFKC + casefold |
| Multi-match | Semua rule cocok, urutan source row |
| Template parse mode | Telegram HTML |
| Media | Telegram `file_id` |
| Activation | Feature registry global + group override |
| Startup source failure | Gunakan last-known-good |
| Invalid row | Tolak seluruh snapshot |
| Sync default | Startup + manual reload |
| Periodic sync | Tersedia, nonaktif default |
| Admin identity | Numeric Telegram user ID |
| Content logging | Dilarang |
| Router priority | Fallback setelah command dan game |
| Private autoreply | Nonaktif default |
| Bot sender | Diabaikan default |
| Database writes per message | Tidak ada untuk rule lookup |

# Lampiran A — Contoh Baris Google Sheet

| Command | Message | MatchAll | ReplyToSender | ReplyToReplied | AdminOnly | Disabled |
|---|---|---|---|---|---|---|
| `halo` | `Halo, (sbj_dpn)!` | TRUE | TRUE | FALSE | FALSE | FALSE |
| `peluk` | `@sbj((sbj_dpn))@ memeluk (isreply)@obj((obj_dpn))@(/isreply)(isnotreply)semua orang(/isnotreply).` | FALSE | FALSE | FALSE | FALSE | FALSE |
| `/aturan` | `<b>Aturan grup</b>\n(btn=https://example.com)Baca lengkap(/btn)` | TRUE | FALSE | FALSE | FALSE | FALSE |
| `admin test` | `Perintah admin dijalankan oleh (sbj).` | TRUE | TRUE | FALSE | TRUE | FALSE |
| `suara` | `*voice:AwACAgUAAxkBAA...` | TRUE | FALSE | FALSE | FALSE | FALSE |
| `arsip` | `Pesan ini tidak aktif.` | TRUE | FALSE | FALSE | FALSE | TRUE |

Catatan: `\n` pada contoh tabel menggambarkan line break dalam cell Sheet; cell dapat berisi newline asli karena CSV quoted newline didukung.

# Lampiran B — Contoh Template

## B.1 Subject dan object

```text
(isreply)@sbj((sbj_dpn))@ menyapa @obj((obj_dpn))@.(/isreply)
(isnotreply)Halo, @sbj((sbj_dpn))@!(/isnotreply)
```

## B.2 Command prefix/suffix

Trigger: `bilang`

```text
(ada_ket)(sbj_dpn) bilang: <i>(cmd_ket)</i>(/ada_ket)
(tdk_ada_ket)(sbj_dpn) belum menulis apa yang ingin dikatakan.(/tdk_ada_ket)
```

## B.3 Username fallback

```text
(ada_sbj_un)Username: @(sbj_un)(/ada_sbj_un)
(tdk_ada_sbj_un)(sbj_dpn) belum memiliki username.(/tdk_ada_sbj_un)
```

## B.4 Object diri sendiri

```text
(isreply)(sbj_dpn) memilih (obj=sbj_as_dirinya sendiri)(obj!=sbj)(obj_dpn)(/obj!=sbj).(/isreply)
```

## B.5 Tombol

```text
<b>Informasi lengkap</b>
(btn=https://example.com/panduan)Buka Panduan(/btn)
(btn=https://t.me/example)Buka Telegram(/btn)
```

# Lampiran C — Pseudocode Handler

```python
@router.message(F.text)
async def handle_autoreply_message(
    message: Message,
    autoreply_service: AutoreplyService,
    current_user: UserContext | None,
    current_group: GroupContext | None,
    permissions: PermissionContext,
) -> None:
    await autoreply_service.handle_message(
        message=message,
        current_user=current_user,
        current_group=current_group,
        permissions=permissions,
    )
```

```python
async def handle_message(...):
    if not self.scope_policy.accepts(message):
        return AutoreplyExecutionResult.skipped("scope")

    if not await self.feature_service.is_enabled(
        feature_key="autoreply",
        group=current_group,
    ):
        return AutoreplyExecutionResult.skipped("feature_disabled")

    snapshot = self.cache.get()
    if snapshot.is_empty:
        return AutoreplyExecutionResult.skipped("no_snapshot")

    candidates = []
    for rule in snapshot.rules:
        if rule.admin_only and not permissions.has(
            "autoreply.trigger_admin_rule"
        ):
            continue
        match = self.matcher.match(rule, message.text)
        if match.matched:
            candidates.append((rule, match))

    for rule, match in candidates[: self.max_responses(message.chat.id)]:
        try:
            await self.sender.send(message, rule, match)
        except TelegramRetryAfter:
            break
        except Exception as exc:
            await self.error_service.record_rule_error(rule, message, exc)

    return AutoreplyExecutionResult.from_counts(...)
```

# Lampiran D — Checklist Code Review

- [ ] Handler tidak menjalankan SQL atau HTTP.
- [ ] Source URL berasal dari config, bukan input user.
- [ ] Tidak ada isi pesan pada log.
- [ ] Semua data Telegram di-escape sebelum HTML render.
- [ ] Snapshot baru tidak aktif sebelum commit selesai.
- [ ] Cache lama dipertahankan jika sync gagal.
- [ ] Rule order mengikuti source row.
- [ ] Semua media prefix diuji.
- [ ] Reply precedence diuji.
- [ ] AdminOnly menggunakan permission service.
- [ ] Router autoreply didaftarkan terakhir.
- [ ] Feature global dan group override diuji.
- [ ] Startup offline dengan cached snapshot diuji.
- [ ] Migration downgrade diuji pada database test.
- [ ] Termux smoke test lulus.
