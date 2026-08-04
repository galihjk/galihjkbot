# Panduan Pengembangan Game

Dokumen ini adalah acuan tunggal untuk menambahkan game baru ke bot. Semua yang generik (lobby, ready-check, timer, lock, penyimpanan) sudah ditangani oleh **engine**; kamu hanya perlu menulis **satu class** yang mengimplementasikan `BaseGame` plus file-file pendukungnya (metadata, state, teks, keyboard).

Contoh acuan langsung: `app/modules/games/implementations/simple_game/` — tampil ke user sebagai **"Test"**. Status game ini **frozen (tidak dikembangkan lagi)** — dipertahankan apa adanya cuma untuk uji fondasi engine dan uji pilihan game di menu `/game`, tetap muncul di `development` tapi **disembunyikan otomatis saat `APP_ENV=production`** (lihat `create_game_registry()` di `app/bootstrap.py`). Jangan tambah fitur baru ke game ini — kalau ragu soal pola dasar untuk game BARU, tiru strukturnya saja, jangan diubah langsung.

**Rencana pengembangan game pertama yang sesungguhnya ada di dua dokumen terpisah:**
- [`game-design-kursi-kosong.md`](game-design-kursi-kosong.md) — spesifikasi desain murni (transkrip dari dokumen desain, diarsipkan di `archive/`)
- [`kursi-kosong-implementation-plan.md`](kursi-kosong-implementation-plan.md) — rencana pembangunannya di atas engine ini, bertahap

Beberapa bagian di panduan ini (§6, §7, §11, §15 baru) sudah disesuaikan berdasarkan kebutuhan yang ketahuan saat mempelajari desain Kursi Kosong — dibaca dulu sebelum mulai, supaya tidak kaget saat baca rencana implementasinya.

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
   LOBBY  ──(➕ Gabung / ➖ Keluar / ⏱ Extend / ❌ Batalkan)──┐
      │                                                    │
      │ pembuat OTOMATIS ikut join saat lobby dibuat        │
      │ 60 detik (default), bisa di-extend TANPA BATAS      │
      │ oleh siapapun yang sudah join                       │
      ▼                                                    │
  waktu habis?                                             │
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

    @property
    def session_id(self) -> int: ...   # shortcut ke game_session.id
```

`PlayerInfo` cuma punya `user_id` (internal), `telegram_user_id`, `display_name` — dipakai untuk mention/tampilan, **bukan** untuk query DB (kalau butuh data user lengkap, query sendiri lewat `user_repository`).

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
    round_number_str, action_data = parsed.data.split(":", 1)

    state = context.game_session.state_json
    if int(round_number_str) != state["round"]:
        await callback.answer("Tampilan ini sudah kedaluwarsa, tunggu ronde berikutnya.", show_alert=True)
        return
    ...
```

Ini akan diperbaiki sekaligus saat implementasi Kursi Kosong (lihat rencana implementasi) — kalau kamu bikin game round-based SEBELUM itu selesai, jangan tiru bug ini dari `simple_game`, tambahkan validasi round sendiri.

---

## 7. Timer dalam-game

Lobby timer dan ready-check timer **sudah otomatis** ditangani `GameManager`. Untuk timer di DALAM game (ronde, giliran, dst), game kamu yang jadwalkan sendiri lewat context:

```python
context.game_manager.schedule_turn_timeout(context.session_id, delay_seconds)
context.game_manager.cancel_turn_timeout(context.session_id)   # kalau ronde selesai lebih cepat dari timeout
```

Saat timer ini berbunyi, `GameManager` otomatis membangun `GameContext` **baru** (dengan `db_session` baru dari session_factory-nya sendiri, bukan session request yang sudah lama ditutup) dan memanggil `YourGame.handle_timeout(context, "turn:{session_id}")`. Kamu tidak perlu — dan tidak bisa — pakai `db_session` yang sama dengan yang dipakai saat menjadwalkan; selalu terima `db_session` baru dari `context` yang diberikan ke `handle_timeout`.

**Kalau bikin timer generik baru sendiri (bukan lewat `schedule_turn_timeout`)**: pelajari dulu bug self-cancellation yang pernah terjadi di `TimerRegistry` (riwayat pengembangan) — intinya, kalau kode di dalam sebuah timer task memicu `cancel_session()`/`cancel_game()` untuk sesi yang sama, task itu bisa membatalkan DIRINYA SENDIRI di tengah eksekusi sebelum selesai commit. `TimerRegistry.cancel()` sudah dijaga (skip kalau target adalah `asyncio.current_task()`), tapi kalau kamu menulis mekanisme timer/lock BARU di luar `TimerRegistry`, waspada pola yang sama.

### ⚠️ KETERBATASAN SAAT INI: cuma 1 slot timer dalam-game per session

`schedule_turn_timeout`/`cancel_turn_timeout` cuma menyediakan **satu** slot timer per session (key tetap `turn:{session_id}`). Ini cukup untuk game yang timer-nya cuma "satu ronde = satu timeout" (seperti `simple_game`).

**Ini TIDAK cukup untuk game yang butuh beberapa timer berjalan BERSAMAAN dalam satu ronde** — misalnya Kursi Kosong, di mana tiap kursi yang mulai diperebutkan punya jendela waktu 1.200ms sendiri, dan bisa ada beberapa kursi diperebutkan bersamaan dalam satu ronde. Kalau kamu panggil `schedule_turn_timeout` lagi untuk kursi kedua sementara timer kursi pertama belum selesai, `TimerRegistry.register()` akan **membatalkan timer kursi pertama** (karena key-nya sama, `register()` selalu cancel dulu key lama sebelum pasang yang baru) — bukan berjalan paralel seperti yang dibutuhkan.

**Belum diperbaiki** — ini salah satu tugas di rencana implementasi Kursi Kosong: generalisasi jadi `schedule_timer(session_id, name, delay)` / `cancel_timer(session_id, name)` dengan key `turn:{session_id}:{name}`, plus perbaikan `TimerRegistry.cancel_session()` (saat ini pencocokan key-nya `key.partition(":")` lalu bandingkan exact sama `str(session_id)` — kalau key jadi `turn:5:chair-3`, hasil partition `sid="5:chair-3"` tidak akan cocok dengan `"5"`, jadi timer per-chair tidak akan ikut ter-cancel saat `cancel_session()` dipanggil. Perlu diubah jadi cek `sid == str(session_id) or sid.startswith(f"{session_id}:")`).

Kalau game kamu cukup dengan SATU timer per ronde, `schedule_turn_timeout` yang ada sekarang sudah cukup, tidak perlu menunggu generalisasi ini.

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

Status pemain (`app/core/enums.py::GamePlayerStatus`): `JOINED`, `ACTIVE`, `LEFT`, `ELIMINATED`, `WINNER`, `DISQUALIFIED`. Game kamu boleh set `player.status` langsung (lihat `SimpleGame._resolve_round` set `ELIMINATED`/`WINNER`) — tidak perlu lewat fungsi repository khusus untuk itu, cukup ambil row via `find_player()` lalu ubah atributnya dan `flush()`.

**Belum ada nilai `AFK`.** Desain Kursi Kosong butuh AFK sebagai status TERPISAH dari `ELIMINATED` — bukan cuma beda label, tapi beda konsekuensi skor (AFK menghanguskan seluruh skor sesi, `ELIMINATED` normal tetap dapat skor partisipasi+ketahanan). Menambah value baru ke enum ini **tidak butuh migration** (kolomnya `String` biasa), tapi kalau game kamu butuh bedakan AFK vs eliminasi normal, tambahkan `AFK = "afk"` ke `GamePlayerStatus` dulu.

Kalau butuh event type baru untuk audit log, tambahkan ke `GameEventType` di `app/core/enums.py` — ini cuma string biasa di kolom `String`, jadi menambah/mengganti value tidak butuh migration.

---

## 12. Checklist menambah game baru

1. Buat folder `app/modules/games/implementations/<key_game>/`
2. `metadata.py` — definisikan `GameMetadata(key=..., name=..., description=..., min_players=..., max_players=..., lobby_timeout_seconds=60, ready_check_seconds=60)`
3. `state.py` — fungsi murni untuk bentuk `state_json` kamu (opsional tapi disarankan, gampang ditest)
4. `keyboards.py` — builder `InlineKeyboardMarkup` pakai `GameCallback(session_id=..., data=...)`
5. `texts.py` — template teks (ikuti konvensi §9)
6. `game.py` — class turunan `BaseGame`, implementasikan 6 method abstrak
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

## 15. Sistem skor & statistik lintas-game — BELUM DIBANGUN

Ketahuan saat mempelajari desain Kursi Kosong (§26-33 di `game-design-kursi-kosong.md`): game itu butuh **skor global yang dibagi bersama game lain** ("skor Kursi Kosong masuk ke skor global bot yang dipakai bersama permainan lainnya") plus statistik per-game yang tersimpan terpisah (`games_played`, `games_won`, dst). **Kita belum punya salah satu dari ini sama sekali** — tidak ada tabel skor/leaderboard, tidak ada kolom skor yang benar-benar dipakai (`game_players.score` sengaja tidak dibuat, lihat tabel §13).

Ini bukan cuma soal Kursi Kosong — kalau dibangun HANYA khusus untuk Kursi Kosong sekarang, game berikutnya yang juga butuh skor akan menabrak keputusan yang sama lagi. **Rekomendasi: bangun sebagai kapabilitas engine generik**, bukan spesifik satu game, supaya game manapun bisa pakai lewat pola yang sama. Kerangka kasarnya (detail ada di rencana implementasi):

- Tabel baru, misal `user_game_scores` (atau nama lain): `user_id`, `game_key`, `session_id`, `result_score`, `participation_score`, `survival_score`, `final_score`, `committed_at` — mirip pola `score_committed_at` di desain (mencegah skor diproses dua kali untuk session yang sama).
- Formula skor (hasil + partisipasi + ketahanan, dikali faktor jumlah pemain) itu **spesifik Kursi Kosong**, jadi tetap tinggal di dalam `implementations/kursi_kosong/`, BUKAN di engine — engine cuma perlu tahu "berapa skor akhir tiap user_id" dan cara menyimpannya secara idempotent.
- Kemungkinan perlu 1 hook baru di `BaseGame` (misal `calculate_scores(context, result) -> dict[user_id, int]`) yang dipanggil `GameManager.finish_game()` sebelum/sesudah `finish()` — supaya commit skor terjadi di SATU tempat generik (jadi aturan "skor cuma dicommit sekali", "game yang di-cancel tidak dapat skor" otomatis berlaku ke semua game, tidak perlu diulang tiap implementasi).
- Statistik per-game (`games_played` dkk) bisa dihitung on-demand dari `game_players`+`game_sessions` yang sudah ada (tidak perlu tabel agregat baru di awal) — cukup tambah query di repository kalau/ketika ada UI yang menampilkannya (`/profil`, dsb — belum ada).

**Status: didesain di rencana implementasi, belum ada satu baris kode pun.** Jangan mulai coding Kursi Kosong sebelum keputusan arsitektur skor ini diambil, supaya tidak perlu migration ulang.
