# Panduan Pengembangan Game

Dokumen ini adalah acuan tunggal untuk menambahkan game baru ke bot. Semua yang generik (lobby, ready-check, timer, lock, penyimpanan) sudah ditangani oleh **engine**; kamu hanya perlu menulis **satu class** yang mengimplementasikan `BaseGame` plus file-file pendukungnya (metadata, state, teks, keyboard).

Contoh acuan langsung: `app/modules/games/implementations/simple_game/` — tampil ke user sebagai **"Test"**. Status game ini **frozen (tidak dikembangkan lagi)** — dipertahankan apa adanya cuma untuk uji fondasi engine dan uji pilihan game di menu `/game`, tetap muncul di `development` tapi **disembunyikan otomatis saat `APP_ENV=production`** (lihat `create_game_registry()` di `app/bootstrap.py`). Jangan tambah fitur baru ke game ini — kalau ragu soal pola dasar untuk game BARU, tiru strukturnya saja, jangan diubah langsung.

**Rencana pengembangan game pertama yang sesungguhnya ada di dua dokumen terpisah:**
- [`game-design-kursi-kosong.md`](game-design-kursi-kosong.md) — spesifikasi desain murni (transkrip dari dokumen desain, diarsipkan di `archive/`)
- [`kursi-kosong-implementation-plan.md`](kursi-kosong-implementation-plan.md) — rencana pembangunannya di atas engine ini, bertahap

Beberapa bagian di panduan ini (§4, §6, §7, §11, §15, §16) sudah disesuaikan/ditambah berdasarkan yang ketahuan selama membangun Kursi Kosong — baik dari studi desain maupun dari testing manual sungguhan. Dokumen ini ditulis supaya **cukup dibaca sendiri** untuk menambah game baru — kamu seharusnya tidak perlu buka kode `simple_game`/`kursi_kosong` untuk tahu polanya, cukup baca panduan ini.

---

## 1. Peta arsitektur

```
app/modules/games/
├── engine/                    <- GENERIK, jangan diubah untuk nambah game baru
│   ├── metadata.py             GameMetadata (dataclass)
│   ├── context.py              GameContext, PlayerInfo
│   ├── result.py                GameResult
│   ├── base_game.py            BaseGame (abstract contract)
│   ├── registry.py              GameRegistry
│   ├── lock_manager.py          GameLockManager
│   ├── timer.py                 TimerRegistry
│   ├── manager.py               GameManager (koordinator lobby+lifecycle+timer)
│   └── lobby.py                  Render teks lobby/ready-check/cancelled (generik)
│
├── callbacks.py                GameCallback (skema callback generik dalam-game)
├── keyboards/lobby.py           LobbyCallback + keyboard lobby & ready-check (generik)
├── keyboards/game_menu.py       Keyboard pemilihan game (generik)
├── presenters.py                Format /gamestatus (generik)
├── router.py + handlers/        Command & callback generik (/game, /games, /gamestatus,
│                                 /cancelgame, lobby_callbacks, game_callbacks) — TIDAK
│                                 perlu disentuh untuk menambah game baru
│
└── implementations/
    └── <key_game>/              <- DI SINI kamu kerja kalau nambah game baru
        ├── metadata.py            GameMetadata spesifik game ini
        ├── state.py                Helper murni untuk bentuk state_json (opsional tapi disarankan)
        ├── keyboards.py            Keyboard spesifik game ini
        ├── texts.py                 Template teks spesifik game ini
        └── game.py                  Class implementasi BaseGame
```

**Poin penting:** menambah game baru **tidak pernah** mengubah `engine/`, `router.py`, atau `handlers/`. Semua dispatch ke game spesifik lewat `GameRegistry` + `GameCallback` yang generik. Satu-satunya titik integrasi di luar folder `implementations/<key>/` adalah **satu baris** di `app/bootstrap.py`:

```python
def create_game_registry(settings: Settings) -> GameRegistry:
    registry = GameRegistry()
    if settings.app_env != "production":
        registry.register(SimpleGame())   # game "Test", sengaja hanya untuk dev
    registry.register(YourNewGame())      # <- tambahkan di sini (tanpa syarat env kecuali kamu memang mau sembunyikan)
    return registry
```

---

## 2. Alur hidup sebuah game session

```
/game <key>  (atau pilih dari menu /game)
      │
      ▼
   LOBBY  ──(➕ Gabung / ➖ Keluar / ⏱ Extend / 🚀 Force Start / ❌ Batalkan)──┐
      │                                                    │
      │ pembuat OTOMATIS ikut join saat lobby dibuat        │
      │ 60 detik (default), bisa di-extend TANPA BATAS      │
      │ oleh siapapun yang sudah join                       │
      │ 🚀 Force Start (khusus pembuat lobi/admin, sama      │
      │ seperti ❌ Batalkan) melewati SISA WAKTU lobi kalau  │
      │ pemain sudah ≥ minimum -- langsung ke ready-check    │
      │ di bawah, TIDAK melewati ready-check itu sendiri     │
      ▼                                                    │
  waktu habis? (atau di-force-start)                        │
      ├─ pemain < minimum ──────────► CANCELLED ◄───────────┘
      │                              (pesan ramah, mention yang
      │                               sudah join, ajak undang teman,
      │                               ajakan /game lagi)
      ▼
  STARTING (= fase READY-CHECK, bukan "countdown otomatis")
      │  pesan lobby lama DITUTUP, pesan baru: mention semua
      │  pemain + tombol [✅ Siap], timer 60 detik baru
      │
      ├─ semua klik Siap SEBELUM waktu habis ──► langsung lanjut (tidak nunggu timeout)
      │
      ▼
  waktu ready-check habis?
      ├─ yang belum klik Siap di-KICK (status -> left), lalu dicek ulang:
      │     sisa < minimum ──► CANCELLED (mention yang SUDAH siap, minta maaf,
      │                         ajak undang teman, ajakan /game lagi)
      │     sisa >= minimum ─► lanjut ke RUNNING dengan sisa yang siap saja
      ▼
   RUNNING
      │  GameManager.start_game() memanggil game.initialize() lalu game.start()
      │  Semua interaksi dalam-game didelegasikan ke BaseGame implementasi kamu
      │  lewat handle_callback / handle_message / handle_timeout
      ▼
   FINISHED (menang) atau CANCELLED (dibatalkan manual via /cancelgame atau tombol)
      │
      ▼
   GameManager.finish_game() otomatis kirim "Mau main lagi? Tinggal tap: /game"
```

**Penting — ini beda dari Blueprint.docx §13**: blueprint aslinya mengusulkan "begitu minimum pemain tercapai, langsung countdown 5 detik lalu mulai". Itu **sudah diganti total** dengan mekanisme extend + ready-check di atas (permintaan eksplisit user, lihat riwayat pengembangan). Kalau kamu baca blueprint dan bingung kenapa kodenya beda, itu bukan bug — blueprint di titik ini sudah usang. Field `GameMetadata.start_countdown_seconds` di blueprint juga sudah di-rename jadi `ready_check_seconds` untuk mencerminkan makna barunya.

Status LOBBY, STARTING (=ready-check), RUNNING, FINISHED, CANCELLED semuanya generik dan **sudah ditangani `GameManager`**. Game kamu **tidak pernah** menyentuh transisi ini secara langsung — kamu hanya diberi tahu lewat `initialize()`/`start()`/`finish()` kapan game kamu boleh mulai dan selesai.

---

## 3. Kontrak yang wajib diimplementasikan: `BaseGame`

```python
# app/modules/games/engine/base_game.py
class BaseGame(ABC):
    metadata: GameMetadata

    async def can_start(self, context: GameContext) -> bool:      # sudah ada default, biasanya tidak perlu override
        return len(context.active_players) >= self.metadata.min_players

    @abstractmethod
    async def initialize(self, context: GameContext) -> None: ...   # buat state awal
    @abstractmethod
    async def start(self, context: GameContext) -> None: ...        # kirim pesan ronde pertama dst
    @abstractmethod
    async def handle_message(self, context: GameContext, message) -> None: ...
    @abstractmethod
    async def handle_callback(self, context: GameContext, callback) -> None: ...
    @abstractmethod
    async def handle_timeout(self, context: GameContext, timer_key: str) -> None: ...
    @abstractmethod
    async def finish(self, context: GameContext, result: GameResult) -> None: ...

    async def restore(self, context: GameContext) -> None:            # untuk recovery restart, BELUM dipakai (lihat §13, baris "Recovery")
        raise NotImplementedError
```

Kapan tiap method dipanggil:

| Method | Dipanggil kapan | Kewajiban |
|---|---|---|
| `initialize` | Sekali, tepat sebelum `start()`, saat status baru pindah ke RUNNING | Bangun `state_json` awal lewat `context.game_session.state_json = ...` |
| `start` | Sekali, setelah `initialize()` | Kirim pesan/keyboard ronde pertama, jadwalkan timer kalau perlu |
| `handle_callback` | Setiap kali ada tombol dalam-game ditekan (lewat `GameCallback`, lihat §5) | Parse `callback.data`, validasi pemain, update state, balas `callback.answer(...)` |
| `handle_message` | Setiap pesan teks di grup **selama status RUNNING** (kalau game kamu butuh input teks, bukan tombol) | Sama seperti handle_callback tapi dari `Message` |
| `handle_timeout` | Timer yang kamu jadwalkan sendiri via `context.game_manager.schedule_turn_timeout(...)` habis | Selesaikan ronde/giliran yang sedang berjalan |
| `finish` | Sesudah `GameManager.finish_game()` mengubah status jadi FINISHED | Hook pembersihan tambahan (boleh kosong kalau notifikasi kemenangan sudah dikirim sendiri) |
| `restore` | **Belum dipanggil di manapun** — placeholder untuk fitur recovery masa depan | Biarkan `raise NotImplementedError` kecuali kamu juga mengerjakan resume mid-round (lihat §13, baris "Recovery") |

---

## 4. `GameContext` — apa yang tersedia untuk game kamu

```python
@dataclass
class GameContext:
    bot: Bot                          # aiogram Bot, untuk send_message/edit_message_text
    db_session: AsyncSession           # sesi DB AKTIF untuk request/timer ini — jangan simpan lintas call
    game_session: GameSession          # ORM row: .state_json, .result_json, .id, dst
    telegram_chat_id: int              # chat Telegram tempat game berjalan
    game_manager: GameManager           # untuk schedule_turn_timeout / cancel_turn_timeout / finish_game
    active_players: list[PlayerInfo]    # snapshot pemain aktif SAAT context dibuat
    acting_user_id: int | None          # user.id (internal) yang MELAKUKAN aksi ini, None kalau dari timer

    @property
    def session_id(self) -> int: ...   # shortcut ke game_session.id
```

`PlayerInfo` cuma punya `user_id` (internal), `telegram_user_id`, `display_name` — dipakai untuk mention/tampilan, **bukan** untuk query DB (kalau butuh data user lengkap, query sendiri lewat `user_repository`).

**`acting_user_id` — WAJIB dipakai untuk resolusi identitas di `handle_callback`/`handle_message`, JANGAN pakai `callback.from_user.id` manual.** Field ini sudah lolos resolusi persona (`/p1`..`/p7`, lihat `app/middlewares/persona.py`) lewat `current_user.id` yang di-thread dari router (`handlers/game_callbacks.py`) ke `GameManager.handle_callback(..., acting_user_id=...)` ke `_build_context`. Kalau kamu resolve identitas sendiri dari `callback.from_user.id` (ID Telegram MENTAH dari akun yang benar-benar menekan tombol), testing solo lewat persona tidak akan pernah berfungsi — klik dengan persona apa pun akan selalu dianggap berasal dari akun ASLI, bukan virtual player yang sedang diperankan. Ini bug nyata yang ditemukan & diperbaiki di Kursi Kosong (lihat riwayat pengembangan) — pola yang benar:
```python
async def handle_callback(self, context: GameContext, callback) -> None:
    user_id = context.acting_user_id
    if user_id is None or user_id not in state["alive_user_ids"]:
        await callback.answer("Kamu tidak dalam permainan ini.", show_alert=True)
        return
    ...
```
`acting_user_id` cuma `None` kalau context dibangun dari timer (`handle_timeout`) — timeout memang tidak punya "pelaku". Untuk `handle_callback`/`handle_message`, selama router-nya benar (ikuti pola `handlers/game_callbacks.py` yang sudah ada), field ini selalu terisi.

**Catatan soal `simple_game`:** game itu masih pakai pola lama (`callback.from_user.id` manual) dan SENGAJA tidak diikutkan perbaikan ini — sesuai kebijakan frozen ("jangan dikembangkan lagi"). Jadi testing solo lewat persona untuk `simple_game` tetap tidak akan berfungsi benar; ini bukan kelupaan, cuma tidak diprioritaskan karena game itu memang cuma buat uji fondasi engine.

**Penting soal `active_players`:** ini snapshot yang diambil SEKALI saat `GameManager` membangun context untuk pemanggilan ini. Kalau kamu mengeliminasi seorang pemain di tengah `handle_callback`, `context.active_players` **tidak otomatis ter-update** — pola yang benar (lihat `SimpleGame._begin_round`) adalah selalu filter terhadap `state["alive_user_ids"]` (yang KAMU kelola sendiri di `state_json`) sebagai sumber kebenaran, dan pakai `context.active_players` cuma sebagai kamus nama untuk lookup display_name.

---

## 5. State per-game: `state_json`

Setiap `GameSession` punya kolom `state_json` (JSON blob bebas bentuk) yang **isinya 100% terserah game kamu**. Engine tidak pernah membaca isinya kecuali kolom `ready_user_ids` yang dipakai sementara oleh `GameManager` selama fase ready-check (akan ter-overwrite total begitu `initialize()` kamu jalan, jadi tidak akan konflik).

### ⚠️ GOTCHA WAJIB DIBACA: mutasi JSON tidak terdeteksi SQLAlchemy

```python
# SALAH — perubahan TIDAK akan tersimpan ke database:
state = context.game_session.state_json
state["round"] += 1
context.game_session.state_json = state   # reassignment objek yang SAMA -> SQLAlchemy tidak lihat ini sebagai "berubah"
await context.db_session.flush()
```

```python
# BENAR — selalu pakai flag_modified setelah mutasi in-place:
from sqlalchemy.orm.attributes import flag_modified

state = context.game_session.state_json
state["round"] += 1
context.game_session.state_json = state
flag_modified(context.game_session, "state_json")   # <- wajib
await context.db_session.flush()
```

Ini bug nyata yang pernah terjadi (lihat riwayat pengembangan) — round number tidak pernah benar-benar tersimpan sampai ditambahkan `flag_modified`. Di `simple_game/game.py` sudah dibungkus jadi helper `_save_state(context, state)` — **tiru pola itu**, jangan assign `state_json` manual di banyak tempat.

### Rekomendasi struktur

Pisahkan logic state jadi modul `state.py` berisi **fungsi murni** (terima/kembalikan dict biasa, tidak menyentuh DB/Telegram sama sekali) seperti `simple_game/state.py`. Ini bikin logic game gampang di-unit-test tanpa perlu database/mock Telegram sama sekali.

---

## 6. Callback dalam-game: `GameCallback`

Semua tombol DALAM game (bukan tombol lobby — itu `LobbyCallback`, sudah generik) pakai satu skema callback generik:

```python
# app/modules/games/callbacks.py
class GameCallback(CallbackData, prefix="game"):
    session_id: int
    data: str   # bebas kamu isi apa saja, kamu sendiri yang parse balik
```

Router generik (`games/handlers/game_callbacks.py`) hanya mengekstrak `session_id` dan meneruskan objek `CallbackQuery` mentah ke `GameManager.handle_callback()`, yang lalu memanggil `YourGame.handle_callback(context, callback)`. **Game kamu sendiri** yang parse ulang `callback.data`:

```python
async def handle_callback(self, context: GameContext, callback) -> None:
    parsed = GameCallback.unpack(callback.data)
    action_data = parsed.data   # string bebas — di simple_game ini nomor kursi
    ...
```

Untuk bikin keyboard, isi `data` dengan apapun yang game kamu butuh untuk membedakan aksi (nomor kursi, index pilihan, dll):

```python
InlineKeyboardButton(
    text="🪑 Kursi 1",
    callback_data=GameCallback(session_id=session_id, data="1").pack(),
)
```

Kalau butuh lebih dari satu jenis aksi (misal "pilih kartu" vs "lipat"), encode keduanya jadi satu string (misal `"fold"` vs `"card:3"`) dan parse manual di `handle_callback` — jangan bikin skema `CallbackData` baru per game kecuali `data: str` benar-benar tidak cukup.

### ⚠️ GOTCHA: callback dari ronde LAMA harus ditolak — `simple_game` saat ini TIDAK melakukan ini

Kalau game kamu punya banyak ronde berurutan (kirim pesan tombol baru tiap ronde), tombol dari ronde SEBELUMNYA masih tetap terlihat & bisa diklik di Telegram (pesan lama tidak otomatis kehilangan keyboard-nya). Kalau `handle_callback` kamu tidak memvalidasi ronde asal klik, klik yang "telat" dari ronde lama bisa salah diproses sebagai aksi ronde yang sedang berjalan.

`SimpleGame` (game "Test") **punya bug ini** — `handle_callback`-nya tidak mengecek nomor ronde sama sekali, cuma nomor kursi. Kebetulan tidak pernah ketahuan di test karena skenario test selalu klik tombol ronde yang SEDANG aktif. Ini ketahuan saat mempelajari desain Kursi Kosong (lihat `game-design-kursi-kosong.md` §9-10), yang secara eksplisit mendesain callback format `seat:{game_id}:{round_number}:{message_version}:{chair_id}` justru untuk mencegah ini.

**Pola yang benar** untuk game round-based: sertakan nomor ronde di `data`, dan validasi di awal `handle_callback` sebelum proses apapun:

```python
async def handle_callback(self, context: GameContext, callback) -> None:
    parsed = GameCallback.unpack(callback.data)
    round_number_str, action_data = parsed.data.split("-", 1)

    state = context.game_session.state_json
    if int(round_number_str) != state["round"]:
        await callback.answer("Tampilan ini sudah kedaluwarsa, tunggu ronde berikutnya.", show_alert=True)
        return
    ...
```

Ini sudah diimplementasikan nyata di `implementations/kursi_kosong/game.py` (Tahap 1) — jadi contoh acuan langsung sekarang bukan cuma `simple_game`.

### ⚠️ GOTCHA: jangan pakai `":"` sebagai separator DI DALAM `data`

Ketahuan saat implementasi Kursi Kosong Tahap 1: `GameCallback.pack()` (dari `CallbackData` bawaan aiogram) memakai `":"` sendiri untuk memisahkan field (`session_id`, `data`). Kalau isi `data` juga mengandung `":"` (misal `data=f"{round_number}:{chair_number}"`), `pack()` langsung melempar `ValueError: Separator symbol ':' can not be used in value`. **Pakai karakter lain** (project ini pakai `"-"`) untuk memisahkan sub-bagian di dalam `data`, lalu `.split("-", 1)` seperti contoh di atas.

---

## 7. Timer dalam-game

Lobby timer dan ready-check timer **sudah otomatis** ditangani `GameManager`. Untuk timer di DALAM game (ronde, giliran, dst), game kamu yang jadwalkan sendiri lewat context. Ada dua API, generalisasi multi-slot ini selesai di Tahap 0 Kursi Kosong:

```python
# Timer SATU slot per session ("round") -- cukup kalau game kamu cuma butuh
# "satu ronde = satu timeout" (pola simple_game):
context.game_manager.schedule_turn_timeout(context.session_id, delay_seconds)
context.game_manager.cancel_turn_timeout(context.session_id)

# Timer BANYAK slot per session, dibedakan lewat `name` -- independen satu
# sama lain, tidak saling cancel:
context.game_manager.schedule_timer(context.session_id, "contest:4", delay_seconds)
context.game_manager.cancel_timer(context.session_id, "contest:4")
```

`schedule_turn_timeout`/`cancel_turn_timeout` sebenarnya cuma wrapper tipis di atas `schedule_timer`/`cancel_timer` dengan `name="round"` (dipertahankan supaya `simple_game` tidak perlu diubah). **Pakai `schedule_timer`/`cancel_timer` langsung** kalau game kamu butuh beberapa timer berjalan BERSAMAAN dalam satu ronde — misalnya jendela kontes per-kursi di Kursi Kosong Tahap 2 (bisa ada beberapa kursi diperebutkan sekaligus, masing-masing punya jendela waktu sendiri).

Saat timer berbunyi, `GameManager` otomatis membangun `GameContext` **baru** (dengan `db_session` baru dari session_factory-nya sendiri, bukan session request yang sudah lama ditutup) dan memanggil `YourGame.handle_timeout(context, timer_key)` — `timer_key` berbentuk `f"turn:{session_id}:{name}"` (untuk `schedule_turn_timeout`, `name` selalu `"round"`). Kalau kamu punya beberapa timer sekaligus, `handle_timeout` bisa membedakan mana yang berbunyi lewat isi `timer_key` (misal cek `"contest:" in timer_key`). Kamu tidak perlu — dan tidak bisa — pakai `db_session` yang sama dengan yang dipakai saat menjadwalkan; selalu terima `db_session` baru dari `context` yang diberikan ke `handle_timeout`.

**Kalau bikin timer generik baru sendiri (bukan lewat `schedule_timer`/`schedule_turn_timeout`)**: pelajari dulu bug self-cancellation yang pernah terjadi di `TimerRegistry` (riwayat pengembangan) — intinya, kalau kode di dalam sebuah timer task memicu `cancel_session()`/`cancel_game()` untuk sesi yang sama, task itu bisa membatalkan DIRINYA SENDIRI di tengah eksekusi sebelum selesai commit. `TimerRegistry.cancel()` sudah dijaga (skip kalau target adalah `asyncio.current_task()`), tapi kalau kamu menulis mekanisme timer/lock BARU di luar `TimerRegistry`, waspada pola yang sama.

**Pola: timer "induk" memaksa selesaikan timer "anak" yang masih pending.** Kalau game kamu punya timer bersarang (misal timer ronde generik + beberapa timer kontes per-kursi di Kursi Kosong Tahap 2), timer yang jendelanya lebih pendek bisa saja belum sempat berbunyi ketika timer yang lebih besar (ronde) sudah habis lebih dulu. Jangan biarkan yang belum selesai itu menggantung (atau menembak nanti setelah state ronde sudah direset) — di `handle_timeout` untuk timer induk, iterasi semua timer anak yang masih ada di `state_json`, `cancel_timer(session_id, name_anak)` supaya tidak nembak dobel, lalu panggil logic resolve-nya secara langsung (bukan lewat timer). Lihat `KursiKosongGame._settle_contest`/`handle_timeout` sebagai contoh konkret: dipanggil baik oleh timer kontes normal maupun dipaksa oleh timer ronde.

**Soal granularitas lock — ini BUKAN gap, sengaja begitu:** desain Kursi Kosong (§34 di dokumen desainnya) mengusulkan lock terpisah per ronde/pemain/kursi. Engine kita cuma punya **satu lock per session** (`GameLockManager`, lihat §14 di bawah). Ini tetap cukup karena bot berjalan sebagai **satu proses Python saja** (bukan multi-worker) — satu lock per session sudah menyerialkan SEMUA mutasi untuk session itu, granularitas lebih halus baru penting kalau suatu saat ada lebih dari satu proses mengakses database yang sama secara paralel. Jangan bikin lock tambahan per-kursi/per-pemain kecuali arsitektur deployment berubah.

---

## 8. Menyelesaikan game

Saat game kamu tahu hasilnya (ada pemenang / seri / dst), panggil:

```python
from app.modules.games.engine.result import GameResult

result = GameResult(
    winner_user_id=winner_id,       # None kalau tidak ada pemenang tunggal
    summary="X menang",
    payload={"rounds": 3},          # bebas, disimpan ke game_sessions.result_json
)
await context.game_manager.finish_game(context, result)
```

`finish_game()` otomatis: ubah status ke FINISHED, catat event, panggil `YourGame.finish(context, result)`, kirim pesan "Mau main lagi? Tinggal tap: /game", lalu bersihkan semua timer & lock sesi itu. **Jangan** kirim pesan "mau main lagi" sendiri di game kamu — itu sudah generik.

---

## 9. Nada teks & pesan

Konvensi yang sudah dipakai di semua teks bot (lihat `engine/lobby.py`, `simple_game/texts.py`):

- **Santai, ramah, pakai emoji secukupnya** (bukan formal/kaku)
- **Mention pemain pakai HTML `tg://user?id=`**, bukan `@username` (supaya tetap kena walau user tidak punya username publik):
  ```python
  def _mention(player: PlayerInfo) -> str:
      return f'<a href="tg://user?id={player.telegram_user_id}">{player.display_name}</a>'
  ```
- **Saat gagal/dibatalkan**: selalu sapa pemain yang terdampak, minta maaf singkat, dan kalau alasannya "kurang pemain" tambahkan ajakan mengundang teman. Sudah ada helper generik `render_cancelled_text()` di `engine/lobby.py` — dipakai otomatis oleh `GameManager.cancel_game()`, game kamu **tidak perlu** menulis pesan cancel sendiri.
- **Setelah berakhir** (menang ATAU batal): selalu ada ajakan main lagi dengan teks command `/game` polos (bukan dibungkus format lain) supaya Telegram otomatis mengenalinya sebagai command yang bisa di-tap. Konstanta: `engine.lobby.PLAY_AGAIN_HINT`.

---

## 10. Exception yang tersedia (`app/core/exceptions.py`)

| Exception | Dilempar kapan | Siapa yang menangkap |
|---|---|---|
| `GameNotFoundError` | `registry.get(key)` untuk key yang tidak terdaftar | Handler command (`/game <key salah>`) |
| `ActiveGameExistsError` | `create_lobby()` saat grup sudah punya game aktif | Handler `/game` |
| `SessionNotFoundError` | Operasi ke `session_id` yang tidak ada | Handler callback lobby |
| `InvalidGameStateError` | Aksi tidak valid untuk status sekarang (misal Extend saat sudah RUNNING) | Handler callback lobby |
| `PlayerAlreadyJoinedError` | Join dobel | Handler callback lobby |
| `PlayerLimitReachedError` | Lobby penuh (`max_players`) | Handler callback lobby |

Game kamu (di dalam `handle_callback`/`handle_message`/`handle_timeout`) **umumnya tidak perlu** melempar exception ini — itu urusan fase lobby/ready-check yang generik. Untuk validasi dalam-game (misal "bukan giliranmu"), cukup `await callback.answer("...", show_alert=True)` lalu `return`, seperti di `SimpleGame.handle_callback`.

---

## 11. Query database yang tersedia (`app/database/repositories/game_repository.py`)

```python
create_session(session, *, group_id, game_key, created_by_user_id, min_players, max_players) -> GameSession
find_active_by_group(session, group_id) -> GameSession | None
find_by_id(session, session_id) -> GameSession | None
add_player(session, game_session_id, user_id) -> GamePlayer
find_player(session, game_session_id, user_id) -> GamePlayer | None
find_active_players(session, game_session_id) -> list[GamePlayer]   # status JOINED atau ACTIVE
count_active_players(session, game_session_id) -> int
log_event(session, game_session_id, event_type, actor_user_id=None, payload=None) -> GameEvent
```

Status pemain (`app/core/enums.py::GamePlayerStatus`): `JOINED`, `ACTIVE`, `LEFT`, `ELIMINATED`, `AFK`, `WINNER`, `DISQUALIFIED`. Game kamu boleh set `player.status` langsung (lihat `SimpleGame._resolve_round` set `ELIMINATED`/`WINNER`) — tidak perlu lewat fungsi repository khusus untuk itu, cukup ambil row via `find_player()` lalu ubah atributnya dan `flush()`.

**`AFK` sudah ada** (ditambahkan di Tahap 0 Kursi Kosong) sebagai status TERPISAH dari `ELIMINATED` — bedanya bukan cuma label, tapi konsekuensi skor: `ELIMINATED` normal tetap dapat skor partisipasi+ketahanan penuh, `AFK` kena penalti (lihat `game-design-kursi-kosong.md` §19 untuk formula lengkapnya — sudah direvisi jadi penalti PARSIAL berdasarkan diskusi dengan user, BUKAN lagi "hangus total" seperti draf desain awal). Menambah value baru lain ke enum ini juga **tidak butuh migration** (kolomnya `String` biasa).

Kalau butuh event type baru untuk audit log, tambahkan ke `GameEventType` di `app/core/enums.py` — ini cuma string biasa di kolom `String`, jadi menambah/mengganti value tidak butuh migration.

---

## 12. Checklist menambah game baru

1. Buat folder `app/modules/games/implementations/<key_game>/`
2. `metadata.py` — definisikan `GameMetadata(key=..., name=..., description=..., min_players=..., max_players=..., lobby_timeout_seconds=60, ready_check_seconds=60)`
3. `state.py` — fungsi murni untuk bentuk `state_json` kamu (opsional tapi disarankan, gampang ditest)
4. `keyboards.py` — builder `InlineKeyboardMarkup` pakai `GameCallback(session_id=..., data=...)`
5. `texts.py` — template teks (ikuti konvensi §9)
6. `game.py` — class turunan `BaseGame`, implementasikan 6 method abstrak. Resolusi identitas pemain di `handle_callback`/`handle_message` **wajib** pakai `context.acting_user_id` (§4) — JANGAN `callback.from_user.id` manual, itu bikin testing lewat persona (`/p1`..`/p7`) tidak berfungsi. Kalau game kamu naratif/bertempo santai (bukan sengaja instan), pertimbangkan pacing pesan (§16).
7. Daftarkan di `app/bootstrap.py::create_game_registry()`: `registry.register(YourGame())`
8. **Test tanpa Telegram sungguhan dulu** — panggil `GameManager` langsung dengan `Bot` palsu (lihat pola test di riwayat pengembangan: `FakeBot` dengan `send_message`/`edit_message_text` yang cuma mencatat teks) dan SQLite file sungguhan (bukan `:memory:` kalau mau tes konkurensi, karena koneksi terpisah butuh file yang sama). Uji dengan `asyncio.gather` untuk skenario dua pemain menekan tombol yang sama bersamaan — ini yang paling sering menyembunyikan bug lock/state.
9. Baru setelah lolos test manual, coba di Telegram sungguhan (bisa solo lewat `/p1`.."/p7", lihat panduan persona di riwayat pengembangan).

---

## 13. Kesesuaian dengan Blueprint.docx — ringkasan deviasi

| Bagian blueprint | Status | Catatan |
|---|---|---|
| §7 Lifecycle (CREATED→LOBBY→STARTING→RUNNING→FINISHED) | ✅ Sesuai | Nama status sama, tapi makna STARTING berubah (lihat baris berikutnya) |
| §13 Kebijakan waktu mulai (countdown 5s otomatis) | ⚠️ **Diganti total** | Diganti mekanisme extend (lobby 60s, bisa diperpanjang tanpa batas) + ready-check (mention + tombol Siap + kick otomatis). Permintaan eksplisit user. |
| §8 Kontrak `BaseGame` | ✅ Sesuai | Identik dengan contoh di blueprint, termasuk `restore()` yang belum diimplementasikan |
| §9 `GameMetadata` | ⚠️ Field berubah nama | `start_countdown_seconds` → `ready_check_seconds` (makna berubah dari "countdown sebelum mulai" jadi "durasi jendela konfirmasi siap") |
| §10 `GameRegistry` | ✅ Sesuai | Identik |
| §11 `GameManager` | ✅ Sesuai secara peran | Method bertambah banyak (`extend_lobby`, `mark_ready`, dst) karena alur baru, tapi tanggung jawabnya sama: satu-satunya pintu perubahan status |
| §14 Lock | ✅ Sesuai | Identik, plus lock sekarang juga melindungi timer lobby/ready-check timeout (tidak hanya turn timeout) |
| §15 Timer | ✅ Sesuai + 1 bug fix | Ditambah proteksi supaya timer tidak bisa membatalkan dirinya sendiri (lihat §7 dokumen ini) |
| §16.5 `game_sessions` schema | ⚠️ Beberapa kolom tidak dibuat | `public_id`, `game_expires_at`, `error_reference` sengaja belum ada — belum ada konsumennya (belum ada format kode publik seperti `U-000128` untuk sesi game, belum ada konsep durasi maksimum game, belum ada global error handler) |
| §16.6 `game_players` schema | ⚠️ Beberapa kolom tidak dibuat | `position`, `score`, `player_state_json` sengaja belum ada — belum ada game yang butuh. **Kalau game barumu butuh state per-pemain yang genuinely terpisah (bukan di level sesi), pertimbangkan tambah `player_state_json` lewat migration Alembic baru** daripada menumpuk semua di `game_sessions.state_json`. |
| §16.7 `game_events` | ✅ Sesuai | Event type di enum berbeda dari contoh blueprint (`MINIMUM_REACHED`/`COUNTDOWN_*` diganti `LOBBY_EXTENDED`/`READY_CHECK_STARTED`/`PLAYER_READY`/`PLAYER_KICKED_NOT_READY`) karena alur baru |
| §20 `/game /games /gamestatus /cancelgame` | ✅ Sesuai | Sudah ada semua |
| §21.6-21.7 Admin monitoring game (`/activegames`, `/gamesessions`, `/gameinfo`, `/admincancelgame`) | ❌ **Belum dikerjakan** | Lihat rencana pengembangan |
| §24 Recovery setelah restart | ✅ Sesuai (versi tahap awal) | `GameManager.recover_sessions()` dipanggil sekali di `main.py` sebelum polling: LOBBY/STARTING yang belum expired dijadwal ulang timernya, yang sudah expired langsung dieksekusi ulang; RUNNING di-ABORT + notifikasi ke grup (sesuai kebijakan blueprint "tahap awal" — `BaseGame.restore()` untuk resume mid-round masih `NotImplementedError`, belum dipakai) |
| §25 Global error handler | ✅ Sesuai | `app/bot/error_handler.py`, terdaftar via `dispatcher.errors.register(...)`. Beda kecil dari blueprint: belum ada `monitoring_service`/tabel metrics terpisah — error dicatat ke `logs/error.log` + notifikasi langsung ke superadmin via Telegram, bukan disimpan ke tabel DB |
| §6 Feature registry (on/off per grup) | ❌ **Belum dikerjakan** | Modul `games` saat ini selalu aktif untuk semua grup |

---

## 14. Modul pendukung (bukan bagian engine game, tapi relevan saat testing)

- **`app/modules/devtools/`** — command `/p0`.."/p7" untuk admin ber-impersonasi jadi virtual player, supaya bisa uji game multiplayer sendirian. Lihat `app/middlewares/persona.py` untuk mekanismenya. Ini alat development, aktif di semua environment (bukan cuma dev), tidak perlu diubah saat menambah game baru.

---

## 15. Sistem skor & statistik lintas-game — SELESAI (skor global+leaderboard bulanan), statistik per-game BELUM

**Skor & leaderboard: sudah dibangun**, sebagai kapabilitas engine generik (bukan spesifik Kursi Kosong), sesuai rekomendasi yang tadinya ditulis di sini:

- Tabel `user_game_scores` (`user_id`, `game_key`, `session_id`, `result_score`, `participation_score`, `survival_score`, `final_score`, `committed_at`) — dibuat Tahap 4 Kursi Kosong, formula skornya SPESIFIK Kursi Kosong (`implementations/kursi_kosong/scoring.py`), engine cuma tahu "berapa skor akhir tiap user_id" lewat hook `BaseGame.calculate_scores()`.
- **Modul baru `app/modules/leaderboard/`** (generik lintas-game, sesuai rencana di sini — "skor global yang dibagi bersama game lain"): command `/skor` (skor sendiri, global + per-grup), `/leaderboard` (leaderboard global bulan ini), `/leaderboardgrup` (leaderboard grup ini). Job bulanan otomatis (`scheduler.py`, loop `asyncio` polos 1x/hari, tanpa dependency scheduler baru) mengumumkan leaderboard ke channel (`TELEGRAM_LEADERBOARD_CHANNEL_ID`) + tiap grup, lalu **menghapus fisik** `user_game_scores` periode itu (TIDAK ADA riwayat all-time — keputusan sengaja) dan membersihkan `User`/`Group` tidak aktif >6 bulan. Detail lengkap & kronologi keputusan (termasuk kenapa destruktif) di `development-history.md`.
- Idempotensi lewat marker table `monthly_maintenance_runs` (pola exists-check, sama seperti `commit_scores`), bukan kolom timestamp per-baris.

**Statistik per-game (`games_played`, `games_won`, `/profil`) MASIH belum dibangun** — beda konsep dari skor/leaderboard di atas (ini soal riwayat "berapa kali main/menang" per game, bukan poin). Bisa dihitung on-demand dari `game_players`+`game_sessions` yang sudah ada, tidak perlu tabel agregat baru — cukup tambah query di repository kalau/ketika ada UI yang menampilkannya. Belum ada konsumennya, sengaja ditunda.

---

## 16. Pacing pesan dalam-game (jeda dramatis)

Ketahuan dari testing manual Kursi Kosong Tahap 1: kalau bot mengirim beberapa pesan berturutan TANPA jeda, permainan terasa terlalu instan/kaku — pemain baru selesai baca "Selamat datang" eh tombol kursi sudah muncul duluan, tidak ada momen "menahan napas". Ini bukan bug, tapi konvensi pacing yang **direkomendasikan** dipakai konsisten di game manapun yang naratif/bertempo santai (beda kasus kalau game kamu memang sengaja serba instan).

### Aturan umum

1. **Kapan pun bot mengirim/mengedit lebih dari satu pesan berturutan** dalam satu alur logis (contoh Kursi Kosong: narasi pembukaan → pesan ronde, narasi hasil ronde → pesan ronde berikutnya/pengumuman pemenang), beri jeda pendek `await asyncio.sleep(...)` di antaranya. Simpan angkanya sebagai konstanta di `metadata.py` game kamu (bukan hardcode di `game.py`), biar gampang di-tuning.
2. **Elemen interaktif (keyboard) tidak harus muncul bersamaan dengan teks pertamanya** — kalau mau bangun ketegangan (mis. "musik akan segera dimulai" sebelum kursi bisa dipilih): kirim teks dulu TANPA `reply_markup`, simpan `message_id`-nya di `state_json`, beri jeda **acak** (`random.uniform(min, max)` — sengaja acak biar tidak gampang ditebak polanya oleh pemain), baru `edit_message_text(text=teks_versi_final, reply_markup=keyboard, ...)` untuk memunculkan teks final DAN keyboard BARENGAN.
3. **Timer terkait (mis. batas waktu memilih) HARUS mulai dihitung SETELAH elemen interaktifnya benar-benar muncul**, bukan dari saat teks pertama dikirim — kalau tidak, jeda dramatis itu malah memotong waktu pemain buat bereaksi. Panggil `schedule_turn_timeout`/`schedule_timer` (§7) SETELAH langkah edit-reveal, bukan sebelumnya.
4. **Pesan yang sudah "usang" (mis. ronde yang baru selesai) sebaiknya ditutup**, bukan dibiarkan nongkrong dengan tombol yang kelihatan masih bisa diklik (walau secara fungsi klik ke situ mestinya sudah ditolak lewat validasi round, §6). Edit pesan lama jadi snapshot final (hasil apa adanya, keyboard dilepas) sebelum lanjut ke pesan berikutnya.
5. **Pacing ini KHUSUS pesan dalam-game (`game.py` milikmu)** — JANGAN diterapkan ke pesan sistem generik (lobby, ready-check, dst di `engine/lobby.py`/`GameManager`), itu tetap instan seperti sekarang. Kalau menurutmu pesan sistem generik juga butuh pacing, itu perubahan `engine/` yang perlu didiskusikan dulu — bukan sesuatu yang kamu tambahkan sendiri per-game.

### Contoh konkret (dari `implementations/kursi_kosong/`)

```python
# metadata.py
MESSAGE_PAUSE_SECONDS = 2       # jeda umum antar-pesan berurutan
SEAT_REVEAL_MIN_SECONDS = 3     # jeda acak sebelum elemen interaktif (kursi) muncul
SEAT_REVEAL_MAX_SECONDS = 5

# game.py
async def start(self, context: GameContext) -> None:
    await context.bot.send_message(context.telegram_chat_id, texts.WELCOME_TEXT)
    await asyncio.sleep(MESSAGE_PAUSE_SECONDS)
    await self._begin_round(context)

async def _begin_round(self, context: GameContext) -> None:
    ...
    waiting_text = texts.render_round_waiting(...)   # "Bersiaplah...", TANPA ajakan aksi/hitungan waktu
    message = await context.bot.send_message(context.telegram_chat_id, waiting_text)
    state["round_message_id"] = message.message_id
    _save_state(context, state)
    await context.db_session.flush()

    await asyncio.sleep(random.uniform(SEAT_REVEAL_MIN_SECONDS, SEAT_REVEAL_MAX_SECONDS))

    ready_text = texts.render_round_ready(...)   # ajakan aksi + hitungan waktu, BARU masuk akal di titik ini
    keyboard = keyboards.build_seat_keyboard(...)
    await context.bot.edit_message_text(
        ready_text, chat_id=context.telegram_chat_id,
        message_id=state["round_message_id"], reply_markup=keyboard,
    )

    context.game_manager.schedule_turn_timeout(context.session_id, ROUND_TIMEOUT_SECONDS)  # BARU di sini
```

### ⚠️ GOTCHA: `edit_message_reply_markup` TIDAK mengubah teks

Kalau reveal-mu perlu mengubah TEKS juga (bukan cuma menambah/melepas keyboard), pakai `edit_message_text(text=..., reply_markup=...)` — BUKAN `edit_message_reply_markup(reply_markup=...)`, yang cuma menyentuh keyboard dan membiarkan teks lama tetap nongkrong walau isinya sudah tidak relevan (mis. masih bilang "bersiaplah" padahal keyboard sudah aktif dan timer sudah jalan).

### Rekomendasi angka (bukan aturan mati)

Kursi Kosong (ronde 15 detik, tempo santai) pakai `MESSAGE_PAUSE_SECONDS=2-3` detik dan jeda reveal acak `3-5` detik. Kalau game barumu jauh lebih cepat temponya (mis. ronde 5 detik), pertimbangkan jeda lebih pendek supaya total waktu "mati" antar-ronde tidak lebih besar dari waktu aktifnya sendiri — tidak ada angka baku, sesuaikan dengan tempo game kamu, tapi **jangan nol** (itu balik ke masalah awal: terasa instan/kaku, sudah dikomplain user sekali untuk Kursi Kosong).
