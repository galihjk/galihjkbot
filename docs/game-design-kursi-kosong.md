# Game Design Document — Kursi Kosong

> Transkripsi lengkap dari `archive/GAME DESIGN - Kursi Kosong.docx` (diarsipkan, tidak masuk git). Dokumen ini adalah **spesifikasi desain murni** — belum dipetakan ke keputusan implementasi. Untuk rencana pembangunannya di atas engine yang sudah ada, lihat [`kursi-kosong-implementation-plan.md`](kursi-kosong-implementation-plan.md).

## 1. Ringkasan Permainan

Kursi Kosong adalah permainan grup berbasis Telegram yang mengadaptasi permainan kursi musik. Pada setiap ronde, jumlah kursi selalu **satu lebih sedikit** daripada jumlah pemain aktif. Pemain memilih kursi melalui tombol inline Telegram (callback query). Kursi yang berhasil ditempati menampilkan nama pemain. Apabila beberapa pemain memilih kursi yang sama dalam waktu berdekatan, terjadi **perebutan kursi** dan bot menentukan satu pemenang. Pemain yang tidak mendapatkan kursi ketika ronde berakhir tereliminasi. Permainan berlanjut hingga tersisa satu pemain sebagai pemenang.

Bot berperan sebagai: pengatur permainan, pembawa acara, narator, pemberi pengumuman lucu, dan pengelola skor & eliminasi.

## 2. Tujuan Permainan

Pemain menang dengan menjadi yang terakhir berhasil mendapat kursi. Untuk bertahan, pemain harus:
- memilih kursi sebelum waktu ronde habis;
- memenangkan perebutan apabila memilih kursi yang sama dengan pemain lain;
- menghindari status AFK;
- bertahan sampai ronde final.

## 3. Jumlah Pemain & Kursi

- Minimum **3** pemain, maksimum **8** pemain.
- `jumlah_kursi = jumlah_pemain_aktif - 1`

| Pemain aktif | Jumlah kursi |
|---|---|
| 8 | 7 |
| 7 | 6 |
| 6 | 5 |
| 5 | 4 |
| 4 | 3 |
| 3 | 2 |
| 2 | 1 |

## 4. Status Permainan

`LOBBY → COUNTDOWN → ROUND_ACTIVE → ROUND_RESOLVING → ROUND_RESULT → FINISHED` (atau `CANCELLED` di titik manapun setelah dimulai).

| Status | Arti |
|---|---|
| `LOBBY` | Pemain masih dapat bergabung |
| `COUNTDOWN` | Pendaftaran ditutup, permainan segera dimulai |
| `ROUND_ACTIVE` | Pemain dapat memilih kursi |
| `ROUND_RESOLVING` | Bot menutup pilihan dan menyelesaikan perebutan kursi |
| `ROUND_RESULT` | Bot mengumumkan pemain yang tereliminasi |
| `FINISHED` | Permainan selesai, pemenang sudah ditentukan |
| `CANCELLED` | Permainan dihentikan karena kesalahan sistem |

## 5. Status Pemain

| Status | Arti |
|---|---|
| `WAITING` | Pemain aktif, belum mendapat kursi |
| `CONTESTING` | Pemain sedang mengikuti perebutan kursi |
| `SEATED` | Berhasil mendapat kursi — **tidak bisa pindah kursi lagi** |
| `ELIMINATED` | Aktif tapi gagal mendapat kursi saat ronde berakhir |
| `AFK` | Tidak melakukan aksi valid pada ronde tersebut |
| `WINNER` | Pemain terakhir yang bertahan |

## 6. Durasi Ronde

- **15 detik** per ronde, tetap sama untuk semua ronde.
- Ronde bisa berakhir lebih cepat kalau seluruh kursi sudah terisi.
- Kondisi akhir ronde: `waktu_ronde_habis` **atau** `seluruh_kursi_sudah_terisi`.

## 7. Tampilan Pesan Utama

Contoh pembukaan ronde:

> 🎵 **RONDE 2 DIMULAI!**
> Tersisa 6 pemain dan hanya tersedia 5 kursi.
> Musik mulai dimainkan. Silakan memilih kursi sebelum 15 detik berakhir.
> Ingat, kursi boleh direbut. Harga diri ditanggung masing-masing.

Tombol ditampilkan **dua kursi per baris**:

```
🪑 1   🪑 2
🪑 3   🪑 4
🪑 5
```

Setelah terisi, nama pemain tampil pada tombol:

```
🪑 1 · Andi   🪑 2
🪑 3 · Budi   🪑 4
🪑 5 · Citra
```

Nama pada tombol: first name / username / nama terpotong, maksimal **10 karakter**.

## 8. Aturan Memilih Kursi

Pemain boleh memilih kursi selama: ronde masih aktif, pemain masih aktif, pemain belum punya kursi, callback dari ronde terbaru, dan waktu server belum lewat batas ronde.

Pemain yang sudah duduk **tidak bisa berpindah**. Kalau tetap coba klik tombol lain:

> *Alert:* "Kamu sudah duduk di Kursi 3. Jangan pindah-pindah, kursinya bukan kontrakan."

## 9. Format Callback Data

```
seat:{game_id}:{round_number}:{message_version}:{chair_id}
```
Contoh: `seat:8271:3:2:4`

- `game_id` — ID permainan
- `round_number` — nomor ronde
- `message_version` — versi pesan aktif (naik setiap kali bot terpaksa kirim pesan baru, lihat §36)
- `chair_id` — nomor kursi

**Callback lama harus ditolak** (round/message_version tidak cocok):

> *Alert:* "Tampilan ini sudah kedaluwarsa. Gunakan tombol pada pesan terbaru."

## 10. Aksi Valid

Aksi dianggap valid kalau: dari pemain terdaftar, pemain masih aktif, dari ronde yang sedang berjalan, diterima sebelum waktu habis, pemain belum punya kursi, dan nomor kursi tersedia di ronde itu.

**Klik ke kursi yang sudah terisi tetap dihitung valid untuk keperluan anti-AFK**, walau pemain gagal dapat kursi.

Callback yang **tidak** dianggap aksi valid: dari ronde lama, setelah ronde ditutup, dari pemain yang sudah duduk, dari pemain yang sudah tereliminasi, dari yang bukan peserta, atau data callback rusak.

## 11. Mekanisme Kursi Kosong (Contest)

Kalau pemain memilih kursi yang belum dipilih siapa pun:
1. Kursi masuk status `CONTESTED`.
2. Bot membuka jendela perebutan.
3. Pemain pertama jadi peserta pertama.
4. Pemain lain yang memilih kursi itu dalam jendela waktu yang sama ikut masuk.
5. Setelah jendela selesai, bot menentukan pemenang.

Walau hanya satu pemain yang memilih, kursi **tetap menunggu** sampai jendela perebutan selesai sebelum resmi ditetapkan (supaya orang lain masih punya kesempatan ikut rebutan).

## 12. Jendela Perebutan Kursi

- Durasi direkomendasikan: **1.200 milidetik**.
- Semua yang klik dalam jendela itu masuk ke perebutan yang **sama** — bukan diproses satu-per-satu sebagai duel berantai.

Contoh: Andi klik `10:00:01.100` → jendela tutup `10:00:02.300`. Budi (`10:00:01.310`), Citra (`10:00:01.780`), Deni (`10:00:02.100`) — keempatnya masuk perebutan yang sama.

## 13. Penentuan Pemenang Perebutan

Versi awal pakai **peluang berbobot** (bukan giliran/first-come-first-served):
- Pemain pertama (yang memicu contest): bobot **1,25**
- Pemain lain: bobot **1,00**

Contoh 4 pemain (total bobot 4,25): Andi 29,41%, Budi/Citra/Deni masing-masing 23,53%.

- **Menang** → status `SEATED`, jadi pemilik kursi, nama tampil di tombol, tidak bisa pindah lagi.
- **Kalah** → balik ke `WAITING`, masih boleh pilih kursi kosong lain, tetap dianggap aktif.

## 14. Narasi Perebutan Kursi (contoh)

> 💥 Andi dan Budi tiba di Kursi 3 hampir bersamaan. Satu kursi, dua ambisi, nol musyawarah.
> 🚨 Empat pemain menyerbu Kursi 2. Kursinya satu, rasa percaya diri mereka berempat.
> 🏆 Citra berhasil mengamankan Kursi 2! Tiga pemain lainnya kembali berdiri sambil berpura-pura tidak kecewa.

## 15. Klik ke Kursi yang Sudah Lama Ditempati

Setelah jendela perebutan selesai dan kursi resmi ditempati, kursi **tidak bisa direbut lagi**. Klik ke kursi itu: gagal dapat kursi, tetap `WAITING` & aktif, masih boleh pilih kursi lain, dapat narasi lucu.

> 😭 Budi mencoba duduk di pangkuan Andi. Kursinya satu, rasa percaya dirinya dua.
> *Alert:* "Kursi ini sudah ditempati Andi. Pilih kursi lain!"

## 16. Semua Kursi Sudah Terisi (sebelum waktu habis)

Ronde langsung ditutup, callback berikutnya ditolak, bot ambil alih, "musik dianggap berhenti", pemain tanpa kursi ditentukan, eliminasi diumumkan.

> 🔔 SEMUA KURSI SUDAH TERISI! Musik dihentikan lebih awal karena kursi sudah penuh dan panitia tidak menerima pemesanan tambahan.

## 17. Pemain Aktif tapi Tidak Kebagian Kursi

Kasus: pemain sudah memilih kursi, tapi kalah/kursi sudah terisi, masih ada kursi kosong lain, tapi waktu habis sebelum sempat pilih lagi. Pemain ini **bukan AFK** (sudah melakukan aksi valid).

```
has_valid_action = true
seat_id = null
status = ELIMINATED
elimination_reason = NO_SEAT
```

Tetap dapat: skor partisipasi, skor ronde yang sudah dilewati, skor sesi sebelum ronde eliminasi.

> 😭 Budi sudah mencoba merebut Kursi 3, tetapi kalah. Saat ia melihat Kursi 4 masih kosong, musik keburu berhenti. Sudah berusaha, tetap tidak kebagian. Kehidupan memang suka konsisten.

## 18. Pemain AFK

AFK = tidak melakukan **satu pun** aksi valid selama ronde aktif.

```
has_valid_action = false
status = AFK
is_active = false
```

Konsekuensi: langsung tereliminasi, tidak ikut ronde berikutnya, tetap tercatat di riwayat (tidak dihapus), tidak disamakan dengan "tidak pernah join".

> 💤 Deni tidak melakukan apa pun sampai musik berhenti. Ia resmi berubah dari pemain menjadi dekorasi ruangan.

## 19. Hukuman Skor AFK (penalti parsial, bukan hangus total)

AFK tetap dihukum, tapi **tidak lagi menghanguskan seluruh skor sesi** (revisi dari aturan awal — lihat diskusi di `development-history.md`). Formulanya:

```
skor_hasil_afk       = 0                                   # dipaksa 0, TIDAK ikut tabel §27 (beda dari eliminasi normal)
skor_partisipasi_afk = 0                                   # tetap 0, sama seperti aturan lama (§28)
skor_ketahanan_afk   = 5 × jumlah_ronde_yang_dilewati       # TETAP dihitung normal, TIDAK dihanguskan

penalty_afk   = 10 + 0,5 × (skor_hasil_afk + skor_ketahanan_afk)
skor_sesi_afk = (10 + skor_hasil_afk + skor_ketahanan_afk) − penalty_afk
              = 0,5 × skor_ketahanan_afk        # karena skor_hasil_afk selalu 0

skor_akhir_afk = skor_sesi_afk × faktor_jumlah_pemain (§30, sama seperti pemain normal)
```

Intinya: pemain yang AFK tetap membawa pulang **separuh skor ketahanan** yang sudah didapat sebelum AFK (dikali faktor jumlah pemain seperti biasa), kehilangan skor hasil sepenuhnya, dan skor partisipasi tetap 0 (memang sudah begitu dari definisi AFK). Nilai ini **tidak pernah negatif** (skor ketahanan minimal 0).

Contoh AFK di ronde 1 (belum lewat ronde apa pun, skor ketahanan = 0): `penalty_afk = 10 + 0,5×(0+0) = 10`, `skor_sesi_afk = 10 − 10 = 0`. Contoh AFK setelah lewat 4 ronde (skor ketahanan = 20): `penalty_afk = 10 + 0,5×(0+20) = 20`, `skor_sesi_afk = 30 − 20 = 10`.

Alasan aturan ini tetap sama seperti sebelumnya — mencegah pemain "numpang tempat" tanpa benar-benar berpartisipasi — tapi sekarang **proporsional** terhadap seberapa jauh pemain sempat bertahan, bukan pukul-rata nol untuk semua orang termasuk yang cuma kena gangguan jaringan sesaat.

**Pesan hasil akhir wajib menyebutkan angka penalti**, bukan cuma label "AFK" (lihat §45 untuk contoh format lengkap):

```
🥇 Andi — 120 poin
🥈 Budi — 80 poin
🥉 Citra — 55 poin
💤 Deni — AFK setelah lewat 4 ronde, kena penalti 20 poin, skor akhir 10 poin
```

## 20. Eliminasi Normal

Jenis: `NO_SEAT`, `LOST_CONTEST`, `TIME_EXPIRED` — semua ditampilkan ke pemain sebagai satu kategori umum: **ELIMINATED**.

> 🧍 Budi masih berdiri ketika musik berhenti. Ia sudah mencoba, tetapi furnitur memiliki rencana lain.
> ☠️ Andi tidak mendapatkan kursi. Terima kasih sudah berdiri bersama kami.

## 21. Callback Setelah Waktu Habis

Ditolak tanpa toleransi tambahan — keputusan harus konsisten berdasarkan waktu server.

> *Alert:* "Waktu sudah habis. Musik telah berhenti dan kursi tidak menerima lamaran baru."

## 22. Pemain Keluar Grup

Tidak perlu penanganan khusus. Kalau pemain tidak beraksi → otomatis jadi `AFK` lewat mekanisme normal. Event keluar-grup boleh dicatat sebagai info tambahan, tapi tidak memengaruhi alur utama.

## 23. Aturan Kapan Narasi Dikirim

**Tidak setiap klik** — supaya grup tidak penuh pesan bot. Narasi dikirim untuk: awal ronde, perebutan kursi, >2 pemain rebutan kursi sama, klik ke kursi yang sudah lama terisi, semua kursi penuh, waktu hampir habis, eliminasi, AFK, error, final, pemenang.

Klik normal ke kursi kosong cukup **callback notification** (toast kecil, bukan pesan baru):

> "Kamu sedang memperebutkan Kursi 4." → setelah menang: "Kamu berhasil mengamankan Kursi 4."

## 24. Countdown Waktu Ronde

Reminder opsional: **5 detik** ("⏳ Lima detik lagi! Yang masih berdiri, silakan panik secara profesional."), **3 detik** ("🚨 Tiga detik! ..."), **1 detik** ("⚠️ Satu detik! ..."). Cukup edit pesan di 5s dan 3s saja — jangan tiap detik (hemat request Telegram).

## 25. Ronde Final

- 2 pemain, 1 kursi, 15 detik.
- Narasi pembukaan: "🔥 RONDE FINAL! Dua pemain. Satu kursi. Tidak ada teman, tidak ada belas kasihan, hanya ada callback query."
- Pemenang → `status = WINNER`.
- Narasi kemenangan: "🏆 KITA PUNYA PEMENANG! Andi berhasil menguasai kursi terakhir dan resmi menjadi Raja Furnitur hari ini!"

## 26. Sistem Skor — Ikhtisar

Skor Kursi Kosong masuk ke **skor global bot** yang dipakai bersama game lain:

```
skor_sesi = skor_hasil + skor_partisipasi + skor_ketahanan
skor_akhir = skor_sesi × faktor_jumlah_pemain
```

Durasi main **tidak** dipakai sebagai basis skor (mudah dieksploitasi, durasi antar-game tidak seragam, AFK bisa "terlihat aktif" cuma karena game lama).

## 27. Skor Hasil (berdasarkan urutan eliminasi)

| Posisi | Skor |
|---|---|
| Juara 1 | 60 |
| Juara 2 | 40 |
| Juara 3 | 25 |
| Lainnya | 10 |

**Kalau pemain AFK**: skor hasil dipaksa **0**, TIDAK ikut tabel di atas — beda dari eliminasi normal (`NO_SEAT`/`LOST_CONTEST`/`TIME_EXPIRED`) yang tetap dapat baris yang sesuai (minimal 10 untuk "Lainnya"). Lihat §19 untuk skema penalti AFK lengkap.

## 28. Skor Partisipasi

- Minimal 1 aksi valid → **10 poin**.
- AFK → **0 poin** (skor hasil dan ketahanan AFK diatur terpisah, lihat §19 — bukan berarti skor sesi otomatis 0).
- Diberikan setelah permainan selesai (bukan real-time).

## 29. Skor Ketahanan

**5 poin per ronde yang dilewati.** Contoh: lewat 4 ronde → 4 × 5 = 20 poin. Pemenang dapat skor untuk seluruh ronde yang dilewati.

## 30. Faktor Jumlah Pemain

| Jumlah pemain awal | Faktor |
|---|---|
| 3–4 | ×1,00 |
| 5–6 | ×1,15 |
| 7–8 | ×1,30 |

Contoh: skor_hasil 60 + partisipasi 10 + ketahanan 30 = 100, dengan 8 pemain (faktor 1,30) → **skor akhir 130**.

## 31. Penanganan Skor AFK (lagi)

Skor akhir pemain AFK dihitung pakai formula penalti di §19 (**bukan** otomatis 0). Skor global **baru diperbarui setelah game selesai** (bukan per-ronde) — mencegah skor "kepalang masuk" sebelum sesi selesai, rollback rumit, exploit keluar-setelah-dapat-skor, dan inkonsistensi leaderboard.

## 32. Statistik Pemain (per game, terpisah dari skor global)

`games_played`, `games_won`, `total_rounds_survived`, `total_contests_joined`, `total_contests_won`, `total_afk`, `total_play_time`, `best_finish`.

```
Kursi Kosong
🎮 Bermain: 24 kali
🏆 Menang: 5 kali
🪑 Ronde dilewati: 78
⚔️ Perebutan dimenangkan: 19
💤 AFK: 2 kali
```

## 33. Anti-Farming

- Minimal 3 pemain untuk skor global dihitung.
- Satu akun Telegram = satu identitas pemain, tidak bisa join dobel.
- Skor disimpan **setelah** game selesai; game yang dibatalkan tidak memberi skor apapun; AFK dapat skor parsial sesuai formula penalti (§19), bukan dihanguskan total.
- Callback lama tidak bisa dihitung ulang; setiap sesi ID unik; transaksi skor hanya dijalankan **sekali**, ditandai lewat `score_committed_at` — kalau sudah terisi, tidak boleh diproses ulang.

## 34. Race Condition & Locking

Pemilihan kursi wajib pakai transaksi/lock. Yang harus dikunci: status ronde, status pemain, status kursi, daftar peserta perebutan. Tujuan: cegah pemain dapat 2 kursi, cegah 1 kursi 2 pemilik, cegah callback terlambat masuk ke ronde yang sudah selesai, pastikan semua peserta duel tercatat.

Alur callback yang disarankan:
1. Mulai transaksi
2. Ambil game & ronde aktif dengan lock
3. Validasi waktu
4. Ambil pemain dengan lock
5. Validasi status pemain
6. Ambil kursi dengan lock
7. Masukkan pemain ke contest
8. Tandai `has_valid_action`
9. Commit transaksi
10. Kirim callback response

Penyelesaian contest dilakukan oleh **satu worker/job unik** (tidak boleh diproses paralel oleh lebih dari satu proses untuk sesi yang sama).

## 35. Struktur Data (usulan desain asli)

```
Game: id, chat_id, game_type, status, started_at, finished_at, cancelled_at,
      initial_player_count, current_round, score_committed_at

GamePlayer: id, game_id, telegram_user_id, display_name, status, joined_at,
            eliminated_at, eliminated_round, elimination_reason,
            has_afk, temporary_score, final_score

Round: id, game_id, round_number, status, started_at, ends_at, finished_at,
       player_count, chair_count, message_id, message_version

RoundPlayer: id, round_id, game_player_id, status, has_valid_action,
             seat_id, first_action_at, elimination_reason

Chair: id, round_id, chair_number, status (EMPTY/CONTESTED/OCCUPIED/LOCKED),
       occupied_by, contest_started_at, contest_ends_at

ChairContestant: id, chair_id, game_player_id, clicked_at, weight, is_winner

GameEvent: id, game_id, round_id, event_type, player_id, chair_id, payload,
           created_at
```

`GameEvent` berguna untuk debugging, histori, narasi, audit, dan penyelesaian error.

## 36. Edit Pesan Telegram & Versi Pesan

Setelah kursi resmi punya pemilik, bot **edit** inline keyboard di tempat. Kalau edit berhasil → `message_version` tetap. Kalau bot terpaksa kirim pesan **baru** (edit gagal permanen) → `message_version += 1`, pesan baru jadi sumber tombol resmi, **callback dari versi lama ditolak**.

## 37. Penanganan Gagal Edit Pesan

Retry maksimal 3x: langsung → +500ms → +1.500ms. Kalau tetap gagal tapi masih bisa kirim pesan baru: kirim pemberitahuan, buat pesan status kursi terbaru, naikkan `message_version`, lanjutkan game.

> ⚠️ Tampilan kursi gagal diperbarui. MC sedang memperbaiki panggung. Permainan tetap dilanjutkan berdasarkan data yang sudah tercatat.

## 38. Error Berulang

Game **tidak langsung dihentikan** karena satu error. Urutan pemulihan: ulangi operasi → coba edit pesan → kalau gagal, kirim pesan baru → kalau berhasil, lanjutkan → kalau penyimpanan data/komunikasi tetap gagal, **batalkan**.

Error dianggap kritis kalau: DB gagal simpan status, pemilik kursi tidak bisa dipastikan, bot gagal kirim **dan** edit pesan, penyelesaian contest gagal berulang, timer ronde tidak bisa dilanjutkan, atau status pemain jadi tidak konsisten.

## 39. Pembatalan Permainan (akibat error kritis berulang)

```
game_status = CANCELLED
```
> 🚨 PERMAINAN DIHENTIKAN. MC sudah mencoba memperbaiki panggung beberapa kali, tetapi sistem masih mengalami gangguan. Permainan dihentikan agar tidak ada pemain yang dirugikan.

Akibat: semua skor sesi = 0, skor global tidak berubah, tidak ada yang dianggap AFK, tidak ada pemenang.

## 40. Pemulihan Setelah Bot Restart

Cari game dengan status `COUNTDOWN`/`ROUND_ACTIVE`/`ROUND_RESOLVING`/`ROUND_RESULT`. Kalau bisa dipulihkan: pakai waktu server, lanjutkan ronde kalau waktu masih ada, selesaikan ronde kalau waktu sudah habis, kirim pesan status terbaru, naikkan `message_version`. Kalau status tidak bisa dipastikan → `CANCELLED`.

## 41. Pengalaman Pemain Tereliminasi

Tetap bisa lihat permainan, tidak bisa tekan tombol game, callback ditolak, tetap tercatat di hasil akhir.

> *Alert:* "Kamu sudah tereliminasi. Silakan menonton sambil memberikan dukungan moral yang tidak diminta."

Versi awal **tidak perlu**: taruhan, item, achievement.

## 42. Narasi Pembukaan Permainan

> 🎙️ Selamat datang di KURSI KOSONG! Permainan yang menguji kecepatan, keberuntungan, dan kemampuan manusia memperebutkan furnitur. Setiap ronde memiliki satu kursi lebih sedikit daripada jumlah pemain. Pemain yang tidak mendapatkan kursi akan tereliminasi. Bersiaplah. Musik akan segera dimulai!

## 43. Bank Narasi per Kejadian (contoh, acak dipilih saat runtime)

**Berhasil duduk:** "✅ Andi berhasil duduk. Kursinya aman, masa depannya belum tentu." / "🎯 Budi mengamankan Kursi 4 dengan keyakinan tinggi dan informasi terbatas."

**Kalah perebutan:** "💨 Andi terpental dari Kursi 2. Gravitasi bekerja, harga diri menyusul." / "😭 Budi kalah perebutan dan kembali berdiri."

**Klik kursi terisi:** "🤨 Andi mencoba duduk di pangkuan Budi. Panitia tidak menyediakan fitur tersebut." / "🛋️ Budi mencoba mengubah satu kursi menjadi sofa keluarga."

**AFK:** "💤 Andi tampaknya sedang berdiskusi dengan alam bawah sadar." / "🛰️ Sinyal dari Citra belum berhasil diterima oleh pusat kendali."

**Eliminasi:** "☠️ Deni tidak mendapatkan kursi. Terima kasih sudah berdiri bersama kami." / "🕊️ Budi gugur dengan terhormat, meskipun sebenarnya hanya tidak kebagian tempat."

## 44. Alur Lengkap Satu Ronde

1. Hitung jumlah pemain aktif
2. Buat kursi sebanyak `pemain_aktif - 1`
3. Buat data ronde
4. Kirim pesan + tombol kursi
5. Buka ronde selama 15 detik
6. Pemain memilih kursi
7. Catat aksi valid
8. Kursi masuk jendela contest
9. Contest ditutup setelah 1.200ms
10. Pilih pemenang contest
11. Update nama di tombol
12. Kalau semua kursi penuh → tutup ronde lebih awal
13. Kalau waktu habis → tutup ronde
14. Callback baru ditolak
15. Tentukan pemain tanpa kursi
16. Kalau tidak pernah beraksi → `AFK`
17. Kalau sudah beraksi → `ELIMINATED`
18. Umumkan hasil
19. Update skor sementara
20. Mulai ronde berikutnya

## 45. Alur Akhir Permainan

1. Ronde selesai, tersisa 1 pemain aktif
2. Pemain itu → `WINNER`
3. Hitung skor final semua pemain (pemain AFK pakai formula penalti §19, bukan otomatis 0)
4. Transaksi skor global
5. Catat `score_committed_at`
6. Tampilkan hasil akhir (termasuk angka penalti eksplisit untuk pemain yang AFK)
7. Game → `FINISHED`

```
🏆 HASIL AKHIR KURSI KOSONG
🥇 Andi — 130 poin
🥈 Budi — 78 poin
🥉 Citra — 52 poin
4. Deni — 32 poin
💤 Eko — AFK di ronde 1, kena penalti 10 poin, skor akhir 0 poin

Terima kasih sudah bermain. Kursi boleh habis, persahabatan semoga tidak.
```

## 46. Konfigurasi Dasar

```
game_code = empty_chair
min_players = 3
max_players = 8
round_duration_seconds = 15
contest_window_ms = 1200
first_click_weight = 1.25
other_click_weight = 1.00
chairs_per_row = 2
participation_score = 10
survival_score_per_round = 5
afk_penalty_base = 10        # komponen flat penalti AFK (setara skor partisipasi yang hilang)
afk_penalty_ratio = 0.5      # porsi skor hasil+ketahanan yang tetap hangus saat AFK (lihat §19)
max_edit_retry = 3
```

## 47. Prioritas Pengembangan Versi Pertama

**Wajib:** lobby, 3–8 pemain, ronde 15 detik, tombol kursi (2/baris), nama di kursi, contest multi-pemain, larangan pindah kursi, eliminasi, AFK, narasi acak, skor sesi, skor global, error handling, pembatalan game, final & pengumuman pemenang.

**Belum perlu:** item, power-up, achievement, mode tertutup, level narator, spectator interaction, tim, taruhan, toko, skin, kursi khusus, sistem rank kompleks.

## 48. Prinsip Desain

- **Sederhana** — "Tekan kursi dan jangan sampai berdiri ketika musik berhenti."
- **Cepat** — maksimal 15 detik per ronde.
- **Adil** — perebutan pakai waktu server & bobot transparan.
- **Lucu** — bot jadi MC aktif dengan narasi sesuai kejadian.
- **Tidak spam** — narasi hanya di kejadian penting.
- **Tahan error** — coba perbaiki pesan sebelum membatalkan game.
- **Konsisten** — semua keputusan akhir pakai data & waktu server.
- **Terintegrasi** — skor masuk sistem global, tapi statistik game tetap terpisah.
