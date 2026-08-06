# Panduan Pengembangan Game

Dokumen ini adalah acuan **mandiri** untuk menambahkan game baru ke bot — cukup baca dokumen ini, tidak perlu membuka source code game manapun yang sudah ada untuk tahu polanya. Semua yang generik (lobby, ready-check, timer, lock, penyimpanan, skor/leaderboard) sudah ditangani oleh **engine**; kamu hanya perlu menulis **satu class** yang mengimplementasikan `BaseGame` plus file-file pendukungnya (metadata, state, teks, keyboard).

---

## 1. Peta arsitektur

```
app/modules/games/
├── engine/                    <- GENERIK, jangan diubah untuk nambah game baru
│   ├── metadata.py             GameMetadata (dataclass)
│   ├── context.py              GameContext, PlayerInfo
│   ├── result.py                GameResult
│   ├── score.py                  ScoreBreakdown (lihat §15)
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
├── router.py + handlers/        Command & callback generik (/game, /games, /howtoplay,
│                                 /gamestatus, /cancelgame, lobby_callbacks, game_callbacks)
│                                 — TIDAK perlu disentuh untuk menambah game baru
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
    registry.register(YourNewGame())
    return registry
```

Kalau game kamu masih eksperimen/belum siap tampil di production, bungkus registrasinya:

```python
    if settings.app_env != "production":
        registry.register(YourExperimentalGame())
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
   (+ cek skor lewat calculate_scores(), lihat §15)
```

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

    async def restore(self, context: GameContext) -> None:            # untuk recovery restart, BELUM dipakai (lihat §13)
        raise NotImplementedError

    async def calculate_scores(                                        # opsional, lihat §15
        self, context: GameContext, result: GameResult
    ) -> dict[int, "ScoreBreakdown"]:
        return {}
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
| `restore` | **Belum dipanggil di manapun** — placeholder untuk fitur recovery masa depan | Biarkan `raise NotImplementedError` kecuali kamu juga mengerjakan resume mid-round |
| `calculate_scores` | Sesudah `finish()`, dari `GameManager.finish_game()` | Opsional — return `{}` (default) kalau game kamu tidak punya sistem skor. Lihat §15 |

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

**`acting_user_id` — WAJIB dipakai untuk resolusi identitas di `handle_callback`/`handle_message`, JANGAN pakai `callback.from_user.id` manual.** Field ini sudah lolos resolusi persona (`/p1`..`/p7`, lihat §14) lewat `current_user.id` yang di-thread dari router ke `GameManager.handle_callback(..., acting_user_id=...)` ke `_build_context`. Kalau kamu resolve identitas sendiri dari `callback.from_user.id` (ID Telegram MENTAH dari akun yang benar-benar menekan tombol), testing solo lewat persona tidak akan pernah berfungsi — klik dengan persona apa pun akan selalu dianggap berasal dari akun ASLI, bukan virtual player yang sedang diperankan. Ini bug nyata yang pernah ditemukan (dan diperbaiki di level engine) — pola yang benar:

```python
async def handle_callback(self, context: GameContext, callback) -> None:
    user_id = context.acting_user_id
    if user_id is None or user_id not in state["alive_user_ids"]:
        await callback.answer("Kamu tidak dalam permainan ini.", show_alert=True)
        return
    ...
```

`acting_user_id` cuma `None` kalau context dibangun dari timer (`handle_timeout`) — timeout memang tidak punya "pelaku". Untuk `handle_callback`/`handle_message`, selama kamu tidak resolve identitas manual sendiri, field ini selalu terisi dengan benar.

**Penting soal `active_players`:** ini snapshot yang diambil SEKALI saat `GameManager` membangun context untuk pemanggilan ini. Kalau kamu mengeliminasi seorang pemain di tengah `handle_callback`, `context.active_players` **tidak otomatis ter-update** — pola yang benar adalah selalu filter terhadap `state["alive_user_ids"]` (yang KAMU kelola sendiri di `state_json`) sebagai sumber kebenaran, dan pakai `context.active_players` cuma sebagai kamus nama untuk lookup display_name.

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

Ini bug nyata yang pernah terjadi — round number tidak pernah benar-benar tersimpan sampai ditambahkan `flag_modified`. Bungkus pola ini jadi satu helper kecil di `game.py` kamu sendiri:

```python
def _save_state(context: GameContext, state: dict) -> None:
    context.game_session.state_json = state
    flag_modified(context.game_session, "state_json")
```

lalu panggil `_save_state(context, state)` tiap kali mutasi — jangan assign `state_json` manual berulang-ulang di banyak tempat.

### Rekomendasi struktur

Pisahkan logic state jadi modul `state.py` berisi **fungsi murni** (terima/kembalikan dict biasa, tidak menyentuh DB/Telegram sama sekali). Ini bikin logic game gampang di-unit-test tanpa perlu database/mock Telegram sama sekali.

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
    action_data = parsed.data   # string bebas -- misalnya nomor kursi, index kartu, dll
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

### ⚠️ GOTCHA: callback dari ronde LAMA harus ditolak

Kalau game kamu punya banyak ronde berurutan (kirim pesan tombol baru tiap ronde), tombol dari ronde SEBELUMNYA masih tetap terlihat & bisa diklik di Telegram (pesan lama tidak otomatis kehilangan keyboard-nya). Kalau `handle_callback` kamu tidak memvalidasi ronde asal klik, klik yang "telat" dari ronde lama bisa salah diproses sebagai aksi ronde yang sedang berjalan.

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

### ⚠️ GOTCHA: jangan pakai `":"` sebagai separator DI DALAM `data`

`GameCallback.pack()` (dari `CallbackData` bawaan aiogram) memakai `":"` sendiri untuk memisahkan field (`session_id`, `data`). Kalau isi `data` juga mengandung `":"` (misal `data=f"{round_number}:{chair_number}"`), `pack()` langsung melempar `ValueError: Separator symbol ':' can not be used in value`. **Pakai karakter lain** (mis. `"-"`) untuk memisahkan sub-bagian di dalam `data`, lalu `.split("-", 1)` seperti contoh di atas.

---

## 7. Timer dalam-game

Lobby timer dan ready-check timer **sudah otomatis** ditangani `GameManager`. Untuk timer di DALAM game (ronde, giliran, dst), game kamu yang jadwalkan sendiri lewat context. Ada dua API:

```python
# Timer SATU slot per session ("round") -- cukup kalau game kamu cuma butuh
# "satu ronde = satu timeout":
context.game_manager.schedule_turn_timeout(context.session_id, delay_seconds)
context.game_manager.cancel_turn_timeout(context.session_id)

# Timer BANYAK slot per session, dibedakan lewat `name` -- independen satu
# sama lain, tidak saling cancel:
context.game_manager.schedule_timer(context.session_id, "contest:4", delay_seconds)
context.game_manager.cancel_timer(context.session_id, "contest:4")
```

`schedule_turn_timeout`/`cancel_turn_timeout` sebenarnya cuma wrapper tipis di atas `schedule_timer`/`cancel_timer` dengan `name="round"`. **Pakai `schedule_timer`/`cancel_timer` langsung** kalau game kamu butuh beberapa timer berjalan BERSAMAAN dalam satu ronde — misalnya beberapa "kontes" independen berjalan sekaligus, masing-masing punya jendela waktunya sendiri (mis. beberapa slot yang diperebutkan bersamaan, tiap slot dapat jendela konfirmasi sendiri).

Saat timer berbunyi, `GameManager` otomatis membangun `GameContext` **baru** (dengan `db_session` baru dari session_factory-nya sendiri, bukan session request yang sudah lama ditutup) dan memanggil `YourGame.handle_timeout(context, timer_key)` — `timer_key` berbentuk `f"turn:{session_id}:{name}"` (untuk `schedule_turn_timeout`, `name` selalu `"round"`). Kalau kamu punya beberapa timer sekaligus, `handle_timeout` bisa membedakan mana yang berbunyi lewat isi `timer_key` (misal cek `"contest:" in timer_key`). Kamu tidak perlu — dan tidak bisa — pakai `db_session` yang sama dengan yang dipakai saat menjadwalkan; selalu terima `db_session` baru dari `context` yang diberikan ke `handle_timeout`.

**Kalau bikin timer generik baru sendiri (bukan lewat `schedule_timer`/`schedule_turn_timeout`)**: waspada bug self-cancellation — kalau kode di dalam sebuah timer task memicu `cancel_session()`/`cancel_game()` untuk sesi yang sama, task itu bisa membatalkan DIRINYA SENDIRI di tengah eksekusi sebelum selesai commit. `TimerRegistry.cancel()` sudah dijaga (skip kalau target adalah `asyncio.current_task()`), tapi kalau kamu menulis mekanisme timer/lock BARU di luar `TimerRegistry`, waspada pola yang sama.

**Pola: timer "induk" memaksa selesaikan timer "anak" yang masih pending.** Kalau game kamu punya timer bersarang (misal timer ronde generik + beberapa timer kontes per-slot), timer yang jendelanya lebih pendek bisa saja belum sempat berbunyi ketika timer yang lebih besar (ronde) sudah habis lebih dulu. Jangan biarkan yang belum selesai itu menggantung (atau menembak nanti setelah state ronde sudah direset) — di `handle_timeout` untuk timer induk, iterasi semua timer anak yang masih ada di `state_json`, `cancel_timer` supaya tidak nembak dobel, lalu panggil logic resolve-nya secara langsung (bukan lewat timer):

```python
async def handle_timeout(self, context: GameContext, timer_key: str) -> None:
    if timer_key.endswith(":round"):
        state = context.game_session.state_json
        for pending_id in list(state.get("pending_contests", {})):
            context.game_manager.cancel_timer(context.session_id, f"contest:{pending_id}")
            await self._resolve_contest(context, pending_id)   # dipanggil LANGSUNG, bukan lewat timer
        await self._resolve_round(context)
    elif ":contest:" in timer_key:
        contest_id = timer_key.rsplit(":", 1)[-1]
        await self._resolve_contest(context, contest_id)
```

**Soal granularitas lock — ini BUKAN gap, sengaja begitu:** engine cuma punya **satu lock per session** (`GameLockManager`, lihat §14 di bawah), bukan lock terpisah per ronde/pemain/slot. Ini tetap cukup karena bot berjalan sebagai **satu proses Python saja** (bukan multi-worker) — satu lock per session sudah menyerialkan SEMUA mutasi untuk session itu, granularitas lebih halus baru penting kalau suatu saat ada lebih dari satu proses mengakses database yang sama secara paralel. Jangan bikin lock tambahan per-elemen kecuali arsitektur deployment berubah.

### 7.1 Ketahanan panggilan Telegram: retry & fallback

`edit_message_text`/`edit_message_reply_markup` BISA gagal karena sebab yang tidak selalu bisa diperbaiki dengan sekali coba ulang instan (network blip, rate limit sesaat, dst). Kalau kamu cuma `try/except` lalu diam, keyboard/teks pesan bisa basi di mata pemain SELAMANYA walau state di database tetap benar. Pola yang direkomendasikan (dipakai konsisten untuk semua pesan ronde yang bisa di-edit berulang kali dalam satu ronde — reveal awal, update tampilan, reminder, dst):

1. **Retry beberapa kali dengan jeda meningkat** (mis. 3x: langsung, +500ms, +1.500ms) sebelum menyerah.
2. **Kalau tetap gagal, JANGAN diam** — kirim pesan BARU berisi teks+keyboard yang sama, simpan `message_id` pesan baru itu di `state_json` sebagai pointer "pesan otoritatif saat ini" (timpa yang lama).
3. **Tolak callback yang datang dari pesan yang sudah tidak otoritatif** — di `handle_callback`, setelah validasi nomor ronde (§6), bandingkan juga `callback.message.message_id` dengan pointer yang tersimpan di state; kalau tidak cocok, tolak dengan alert yang sama seperti callback ronde lama. Ini mencegah dua pesan "kelihatan aktif" bersamaan di grup kalau fallback terjadi.

```python
async def _edit_with_fallback(context: GameContext, state: dict, text: str, reply_markup) -> None:
    message_id = state.get("active_message_id")
    for delay in (0, 0.5, 1.5):
        if delay:
            await asyncio.sleep(delay)
        try:
            await context.bot.edit_message_text(
                text, chat_id=context.telegram_chat_id, message_id=message_id, reply_markup=reply_markup,
            )
            return
        except Exception:
            continue

    # Ke-3 percobaan gagal -- kirim pesan baru sebagai pengganti, jadikan otoritatif.
    new_message = await context.bot.send_message(
        context.telegram_chat_id, text, reply_markup=reply_markup
    )
    state["active_message_id"] = new_message.message_id
    _save_state(context, state)
    await context.db_session.commit()
```

```python
# Di handle_callback, SETELAH validasi nomor ronde:
current_message_id = state.get("active_message_id")
callback_message_id = getattr(getattr(callback, "message", None), "message_id", None)
if current_message_id is not None and callback_message_id != current_message_id:
    await callback.answer("Tampilan ini sudah kedaluwarsa. Gunakan tombol pada pesan terbaru.", show_alert=True)
    return
```

Perbandingan `message_id` di atas ditulis permisif (`getattr` berlapis) supaya tidak crash kalau objek `callback` (di test ad-hoc kamu sendiri, misalnya) tidak punya atribut `.message` sama sekali — gagal terbuka (permissive), bukan gagal tertutup, karena ini soal UX anti-kebingungan, bukan soal keamanan.

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

`finish_game()` otomatis: ubah status ke FINISHED, catat event, panggil `YourGame.finish(context, result)`, panggil `YourGame.calculate_scores(context, result)` kalau kamu implementasikan (§15), kirim pesan "Mau main lagi? Tinggal tap: /game", lalu bersihkan semua timer & lock sesi itu. **Jangan** kirim pesan "mau main lagi" sendiri di game kamu — itu sudah generik.

---

## 9. Nada teks & pesan

Konvensi yang sudah dipakai di semua teks bot generik (`engine/lobby.py`):

- **Santai, ramah, pakai emoji secukupnya** (bukan formal/kaku)
- **Mention pemain pakai HTML `tg://user?id=`**, bukan `@username` (supaya tetap kena walau user tidak punya username publik). Bot ini pakai `ParseMode.HTML` sebagai default, jadi **selalu `escape()` nama user** sebelum diinterpolasi ke teks — nama yang kebetulan mengandung `<`/`&` (mis. hasil copy-paste dari tempat lain) bisa merusak parsing HTML kalau tidak di-escape:
  ```python
  from html import escape

  def _mention(player: PlayerInfo) -> str:
      name = escape(player.display_name)
      return f'<a href="tg://user?id={player.telegram_user_id}">{name}</a>'
  ```
- **Saat gagal/dibatalkan**: selalu sapa pemain yang terdampak, minta maaf singkat, dan kalau alasannya "kurang pemain" tambahkan ajakan mengundang teman. Sudah ada helper generik `render_cancelled_text()` di `engine/lobby.py` — dipakai otomatis oleh `GameManager.cancel_game()`, game kamu **tidak perlu** menulis pesan cancel sendiri.
- **Setelah berakhir** (menang ATAU batal): selalu ada ajakan main lagi dengan teks command `/game` polos (bukan dibungkus format lain) supaya Telegram otomatis mengenalinya sebagai command yang bisa di-tap. Konstanta: `engine.lobby.PLAY_AGAIN_HINT` (juga menyebut `/skor`, lihat §15).

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

Game kamu (di dalam `handle_callback`/`handle_message`/`handle_timeout`) **umumnya tidak perlu** melempar exception ini — itu urusan fase lobby/ready-check yang generik. Untuk validasi dalam-game (misal "bukan giliranmu"), cukup `await callback.answer("...", show_alert=True)` lalu `return`.

---

## 11. Query database yang tersedia (`app/database/repositories/game_repository.py`)

```python
create_session(session, *, group_id, game_key, created_by_user_id, min_players, max_players) -> GameSession
find_active_by_group(session, group_id) -> GameSession | None
find_by_id(session, session_id) -> GameSession | None
find_all_active(session) -> list[GameSession]   # lintas SEMUA grup, dipakai recovery & admin monitoring
add_player(session, game_session_id, user_id) -> GamePlayer
find_player(session, game_session_id, user_id) -> GamePlayer | None
find_active_players(session, game_session_id) -> list[GamePlayer]   # status JOINED atau ACTIVE
find_all_players(session, game_session_id) -> list[GamePlayer]      # semua status, buat hitung skor akhir
count_active_players(session, game_session_id) -> int
log_event(session, game_session_id, event_type, actor_user_id=None, payload=None) -> GameEvent
```

Status pemain (`app/core/enums.py::GamePlayerStatus`): `JOINED`, `ACTIVE`, `LEFT`, `ELIMINATED`, `AFK`, `WINNER`, `DISQUALIFIED`. Game kamu boleh set `player.status` langsung — tidak perlu lewat fungsi repository khusus untuk itu, cukup ambil row via `find_player()` lalu ubah atributnya dan `flush()`.

**`AFK` sudah ada** sebagai status TERPISAH dari `ELIMINATED` — bedanya bukan cuma label, tapi konsekuensi skor: `ELIMINATED` normal tetap dapat skor partisipasi+ketahanan penuh, `AFK` bisa kamu beri penalti sendiri lewat `calculate_scores()` (§15). Menambah value baru lain ke enum ini juga **tidak butuh migration** (kolomnya `String` biasa).

Kalau butuh event type baru untuk audit log, tambahkan ke `GameEventType` di `app/core/enums.py` — ini cuma string biasa di kolom `String`, jadi menambah/mengganti value tidak butuh migration.

---

## 12. Checklist menambah game baru

1. Buat folder `app/modules/games/implementations/<key_game>/`
2. `metadata.py` — definisikan `GameMetadata(key=..., name=..., description=..., min_players=..., max_players=..., lobby_timeout_seconds=60, ready_check_seconds=60, how_to_play=...)`. `how_to_play` adalah teks cara main yang ditampilkan di `/howtoplay` (boleh multi-baris/poin-poin, lihat `implementations/kursi_kosong/metadata.py` sebagai contoh) — beda dari `description` yang cuma ringkasan 1-2 kalimat.
3. `state.py` — fungsi murni untuk bentuk `state_json` kamu (opsional tapi disarankan, gampang ditest)
4. `keyboards.py` — builder `InlineKeyboardMarkup` pakai `GameCallback(session_id=..., data=...)`
5. `texts.py` — template teks (ikuti konvensi §9)
6. `game.py` — class turunan `BaseGame`, implementasikan 6 method abstrak. Resolusi identitas pemain di `handle_callback`/`handle_message` **wajib** pakai `context.acting_user_id` (§4) — JANGAN `callback.from_user.id` manual, itu bikin testing lewat persona (`/p1`..`/p7`) tidak berfungsi. Kalau game kamu naratif/bertempo santai (bukan sengaja instan), pertimbangkan pacing pesan (§16).
7. Daftarkan di `app/bootstrap.py::create_game_registry()`: `registry.register(YourGame())`
8. **Test tanpa Telegram sungguhan dulu** — panggil `GameManager` langsung dengan `Bot` palsu (`FakeBot` dengan `send_message`/`edit_message_text` yang cuma mencatat teks ke list, tidak benar-benar memanggil Telegram) dan SQLite file sungguhan (bukan `:memory:` kalau mau tes konkurensi, karena koneksi terpisah butuh file yang sama). Uji dengan `asyncio.gather` untuk skenario dua pemain menekan tombol yang sama bersamaan — ini yang paling sering menyembunyikan bug lock/state.
9. Baru setelah lolos test manual, coba di Telegram sungguhan — bisa solo lewat `/p1`.."/p7" (lihat §14 untuk cara kerjanya).
10. Kalau game kamu punya sistem skor, implementasikan `calculate_scores()` (§15) — otomatis terhubung ke `/skor` dan leaderboard bulanan, tidak perlu ubah apa pun di luar game kamu sendiri.

---

## 13. Penyesuaian dari blueprint arsitektur awal

Kontrak `BaseGame`, `GameRegistry`, `GameManager`, lock, timer, event log (`game_events`), command generik (`/game /games /howtoplay /gamestatus /cancelgame`), recovery restart, dan global error handler semuanya konsisten dengan blueprint arsitektur awal proyek ini — tidak ada penyesuaian berarti yang perlu diketahui untuk menambah game baru. Yang berbeda dan PENTING diketahui:

| Area | Penyesuaian |
|---|---|
| Kebijakan waktu mulai lobby | Rencana awal "begitu minimum pemain tercapai, langsung countdown 5 detik" **diganti total** dengan mekanisme extend (lobby bisa diperpanjang tanpa batas) + ready-check (mention + tombol Siap + kick otomatis) — lihat §2. Field `GameMetadata` terkait juga di-rename jadi `ready_check_seconds` (dari nama lama yang menyiratkan "countdown"). |
| Kolom schema `game_sessions`/`game_players` | Beberapa kolom yang tadinya diusulkan (`public_id`, `game_expires_at`, `error_reference`, `position`, `score`, `player_state_json`) **sengaja belum dibuat** — belum ada konsumennya. **Kalau game barumu butuh state per-pemain yang genuinely terpisah** (bukan di level sesi), pertimbangkan tambah `player_state_json` lewat migration Alembic baru daripada menumpuk semua di `game_sessions.state_json`. |
| Admin monitoring game lintas grup | `/activegames` (daftar semua sesi aktif) dan `/gameinfo <session_id>` (detail satu sesi) **sudah ada** (private chat, admin-only). `/gamesessions` dan `/admincancelgame` **belum dikerjakan** — sengaja di luar cakupan sampai ada yang butuh. |
| Feature registry (on/off fitur per grup) | **Belum dikerjakan** — modul `games` saat ini selalu aktif untuk semua grup, tidak ada toggle per grup dari database. |
| Recovery setelah restart | Versi tahap awal: LOBBY/STARTING yang belum expired dijadwal ulang timernya; RUNNING di-ABORT (bukan resume mid-round) + notifikasi ke grup. `BaseGame.restore()` untuk resume mid-round masih `NotImplementedError`, belum dipakai. |

---

## 14. Modul pendukung (bukan bagian engine game, tapi relevan saat testing/dipakai game manapun)

- **`app/modules/devtools/`** — command `/p0`.."/p7" untuk admin ber-impersonasi jadi virtual player, supaya bisa uji game multiplayer sendirian. Mekanismenya lewat middleware persona yang meresolusi identitas "yang benar-benar bertindak" — ini alasan §4 mewajibkan `context.acting_user_id` daripada `callback.from_user.id` manual. Alat development, aktif di semua environment (bukan cuma dev), tidak perlu diubah saat menambah game baru.
- **`app/modules/leaderboard/`** — `/skor`, `/leaderboard`, `/leaderboardgrup` + job pengumuman/reset skor bulanan. Generik lintas-game, otomatis mencakup game barumu selama kamu implementasikan `calculate_scores()` (§15) — tidak ada yang perlu disentuh di modul ini.

---

## 15. Sistem skor & leaderboard

Skor **generik lintas-game** — kalau game kamu punya konsep menang/kalah/poin, cukup implementasikan satu method opsional, sisanya (perintah cek skor, leaderboard, pengumuman bulanan) otomatis berlaku tanpa kamu sentuh apa pun di luar game kamu sendiri.

### Kontrak yang harus kamu implementasikan

```python
from app.modules.games.engine.score import ScoreBreakdown

async def calculate_scores(
    self, context: GameContext, result: GameResult
) -> dict[int, ScoreBreakdown]:
    # key: user_id (internal), value: breakdown skor akhir user itu utk sesi ini
    return {
        user_id: ScoreBreakdown(
            result_score=...,        # skor dari hasil (menang/kalah/ranking), bebas skala
            participation_score=...,  # skor karena ikut aktif berpartisipasi
            survival_score=...,       # skor karena "bertahan" (opsional, isi 0 kalau tidak relevan)
            final_score=...,          # total akhir -- ini yang benar-benar dipakai buat leaderboard
        )
        for user_id in ...
    }
```

Default (kalau tidak di-override) mengembalikan `{}` — game tanpa sistem skor tidak perlu peduli sama sekali dengan bagian ini. **Bentuk formula skornya terserah game kamu** (hasil + partisipasi + ketahanan, dikali faktor apa pun yang relevan buat game kamu, atau sesederhana "menang = 10, kalah = 0") — engine cuma butuh angka akhirnya per `user_id`, tidak peduli bagaimana kamu menghitungnya. **Tapi SKALA-nya bukan bebas sepenuhnya** — lihat subbagian fairness di bawah sebelum menentukan angka-angka konkretnya, supaya game kamu tidak mendominasi (atau kalah jauh) di leaderboard global cuma karena skalanya beda dari game lain.

### Apa yang terjadi otomatis sesudahnya

`GameManager.finish_game()` memanggil `calculate_scores()` lalu commit hasilnya ke tabel `user_game_scores` (idempoten — kalau `finish_game()` sampai terpanggil dua kali untuk sesi yang sama, skor tidak dobel-commit). Sejak titik itu, TANPA kamu perlu menyentuh apa pun lagi:

- Pemain bisa cek skornya sendiri lewat `/skor` (skor global lintas semua game + skor di grup itu kalau dipanggil dari dalam grup).
- `/leaderboard` (global) dan `/leaderboardgrup` (per grup) menampilkan ranking bulan berjalan, tergabung dengan skor dari game lain apa pun yang juga mengimplementasikan `calculate_scores()`.
- Tiap tanggal 1, job otomatis mengumumkan leaderboard bulan yang baru berakhir ke channel pengumuman + tiap grup, lalu **menghapus fisik** baris skor periode itu (tidak ada riwayat all-time — ini keputusan produk yang sengaja, bukan bug kalau kamu lihat skor lama sudah tidak ada lagi setelah tanggal 1).

Kalau game kamu tidak punya konsep skor sama sekali (misal murni kooperatif tanpa menang/kalah), biarkan `calculate_scores()` di nilai default (`{}`) — tidak ada baris yang ter-commit, tidak muncul di leaderboard, tidak ada efek samping apa pun.

### Kalibrasi skala biar adil lintas game

`/leaderboard` (global) menjumlahkan `final_score` mentah dari SEMUA game yang ada. Kalau skala poin tiap game beda jauh, game dengan skala lebih besar otomatis mendominasi leaderboard — bukan karena pemainnya lebih hebat, cuma karena angkanya lebih besar. Dua hal yang perlu diperhatikan saat merancang formula skor game baru:

1. **Sisakan skor minimal buat yang cepat tersingkir.** Jangan biarkan pemain yang kalah/tereliminasi di awal permainan dapat nol mutlak — mereka sudah menginvestasikan waktu sejak join lobi. Sisipkan komponen FLAT kecil (skor partisipasi) yang didapat siapa pun yang sempat beraksi valid, terlepas dari hasil akhirnya.
2. **Samakan LAJU perolehan poin (poin per menit), bukan cuma total per sesi.** Komponen yang skala terhadap seberapa lama/jauh pemain bertahan (ronde, giliran, dst) itu yang menentukan laju ini — kalibrasi konstantanya pakai DURASI NYATA, bukan tebakan. `GameSession.started_at`/`finished_at` (kolom generik, otomatis terisi tiap sesi, gratis dipakai) memberi durasi sungguhan tiap sesi — hitung `skor_sesi ÷ menit` dari beberapa sesi nyata (variasi ukuran lobi/skenario), lalu sesuaikan konstantanya sampai laju itu sepadan dengan game lain di bot ini.

**Angka acuan/baseline** (titik awal yang direkomendasikan, bukan aturan mati — sesuaikan lagi kalau game kamu punya karakteristik jauh berbeda):

- Skor partisipasi: **10 poin** untuk aksi valid, **0** kalau tidak beraksi sama sekali.
- Target laju: **±36 poin per menit** durasi sesi nyata, dirata-rata lintas ukuran lobi/skenario — bukan target presisi per sesi individual (variasi kecepatan pemain, manusia bukan robot, bikin tiap sesi individual tidak akan pernah persis sama).
- Pemain yang tidak aktif (AFK/setara): dapat sekitar **separuh** dari laju itu — tetap kehilangan skor partisipasi sepenuhnya, tapi komponen yang sudah terkumpul sebelum jadi tidak-aktif tetap dihargai separuhnya, bukan dihanguskan total.

Bentuk generiknya: `skor_sesi = skor_partisipasi_minimal + skor_progresif(waktu/giliran yang dilewati)`, lalu kalikan faktor lain yang relevan (mis. ukuran lobi) kalau game kamu butuh itu.

---

## 16. Pacing pesan dalam-game (jeda dramatis)

Kalau bot mengirim beberapa pesan berturutan TANPA jeda, permainan bisa terasa terlalu instan/kaku — pemain baru selesai baca pesan pembuka eh tombol aksi sudah muncul duluan, tidak ada momen "menahan napas". Ini bukan wajib, tapi konvensi pacing yang **direkomendasikan** dipakai konsisten di game manapun yang naratif/bertempo santai (beda kasus kalau game kamu memang sengaja serba instan).

### Aturan umum

1. **Kapan pun bot mengirim/mengedit lebih dari satu pesan berturutan** dalam satu alur logis (contoh: narasi pembukaan → pesan ronde, narasi hasil ronde → pesan ronde berikutnya/pengumuman pemenang), beri jeda pendek `await asyncio.sleep(...)` di antaranya. Simpan angkanya sebagai konstanta di `metadata.py` game kamu (bukan hardcode di `game.py`), biar gampang di-tuning.
2. **Elemen interaktif (keyboard) tidak harus muncul bersamaan dengan teks pertamanya** — kalau mau bangun ketegangan (mis. "musik akan segera dimulai" sebelum kursi bisa dipilih): kirim teks dulu TANPA `reply_markup`, simpan `message_id`-nya di `state_json`, beri jeda **acak** (`random.uniform(min, max)` — sengaja acak biar tidak gampang ditebak polanya oleh pemain), baru `edit_message_text(text=teks_versi_final, reply_markup=keyboard, ...)` untuk memunculkan teks final DAN keyboard BARENGAN.
3. **Timer terkait (mis. batas waktu memilih) HARUS mulai dihitung SETELAH elemen interaktifnya benar-benar muncul**, bukan dari saat teks pertama dikirim — kalau tidak, jeda dramatis itu malah memotong waktu pemain buat bereaksi. Panggil `schedule_turn_timeout`/`schedule_timer` (§7) SETELAH langkah edit-reveal, bukan sebelumnya.
4. **Pesan yang sudah "usang" (mis. ronde yang baru selesai) sebaiknya ditutup**, bukan dibiarkan nongkrong dengan tombol yang kelihatan masih bisa diklik (walau secara fungsi klik ke situ mestinya sudah ditolak lewat validasi round, §6). Edit pesan lama jadi snapshot final (hasil apa adanya, keyboard dilepas) sebelum lanjut ke pesan berikutnya.
5. **Pacing ini KHUSUS pesan dalam-game (`game.py` milikmu)** — JANGAN diterapkan ke pesan sistem generik (lobby, ready-check, dst di `engine/lobby.py`/`GameManager`), itu tetap instan seperti sekarang. Kalau menurutmu pesan sistem generik juga butuh pacing, itu perubahan `engine/` yang perlu didiskusikan dulu — bukan sesuatu yang kamu tambahkan sendiri per-game.

### Contoh konkret

```python
# metadata.py
MESSAGE_PAUSE_SECONDS = 2       # jeda umum antar-pesan berurutan
REVEAL_MIN_SECONDS = 3           # jeda acak sebelum elemen interaktif muncul
REVEAL_MAX_SECONDS = 5

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

    await asyncio.sleep(random.uniform(REVEAL_MIN_SECONDS, REVEAL_MAX_SECONDS))

    ready_text = texts.render_round_ready(...)   # ajakan aksi + hitungan waktu, BARU masuk akal di titik ini
    keyboard = keyboards.build_action_keyboard(...)
    await context.bot.edit_message_text(
        ready_text, chat_id=context.telegram_chat_id,
        message_id=state["round_message_id"], reply_markup=keyboard,
    )

    context.game_manager.schedule_turn_timeout(context.session_id, ROUND_TIMEOUT_SECONDS)  # BARU di sini
```

### ⚠️ GOTCHA: `edit_message_reply_markup` TIDAK mengubah teks

Kalau reveal-mu perlu mengubah TEKS juga (bukan cuma menambah/melepas keyboard), pakai `edit_message_text(text=..., reply_markup=...)` — BUKAN `edit_message_reply_markup(reply_markup=...)`, yang cuma menyentuh keyboard dan membiarkan teks lama tetap nongkrong walau isinya sudah tidak relevan (mis. masih bilang "bersiaplah" padahal keyboard sudah aktif dan timer sudah jalan).

### Rekomendasi angka (bukan aturan mati)

Untuk ronde bertempo santai (10-20 detik), `MESSAGE_PAUSE_SECONDS=2-3` detik dan jeda reveal acak `3-5` detik terasa pas. Kalau game barumu jauh lebih cepat temponya (mis. ronde 5 detik), pertimbangkan jeda lebih pendek supaya total waktu "mati" antar-ronde tidak lebih besar dari waktu aktifnya sendiri — tidak ada angka baku, sesuaikan dengan tempo game kamu, tapi **jangan nol** (itu balik ke masalah awal: terasa instan/kaku).
