from __future__ import annotations

import random
from dataclasses import dataclass

CATEGORIES = (
    "absurd",
    "kebiasaan",
    "makanan",
    "perjalanan",
    "khayalan",
    "situasi_sosial",
    "pilihan_sulit",
    "masa_depan",
    "benda",
    "hiburan",
    "sekolah",
    "pertemanan",
    "teknologi",
    "uang",
    "rumah",
    "hewan",
    "zombie",
    "misteri",
    "keberuntungan",
    "pekerjaan",
    "terkenal",
    "waktu",
    "cuaca",
    "tantangan",
    "salah_tingkah",
    "random",
    "andaikan",
    "rahasia_receh",
    "kompetisi",
    "dunia_game",
    "superhero",
    "horor_lucu",
    "nongkrong",
    "keputusan_receh",
    "kepribadian_receh",
    "skenario_dadakan",
    "dunia_aneh",
    "pengetahuan_tentang_subject",
    "reaksi",
    "siapa_subject",
    "super_receh",
)


@dataclass(frozen=True)
class Question:
    id: str
    category: str
    text: str


def _q(category: str, index: int, text: str) -> Question:
    return Question(id=f"{category}_{index:03d}", category=category, text=text)


QUESTIONS: list[Question] = [
    # absurd
    _q("absurd", 1, "Kalau {subject} mendadak jadi penjahat super, kejahatan receh apa yang paling mungkin dilakukan?"),
    _q("absurd", 2, "Kalau {subject} bisa mengecilkan diri jadi seukuran jempol selama sehari, apa yang bakal dilakukan pertama kali?"),
    _q("absurd", 3, "Superpower yang paling mungkin disalahgunakan {subject} untuk hal receh apa?"),
    _q("absurd", 4, "Kalau {subject} berubah jadi hewan selama sehari, hewan apa yang paling cocok?"),
    _q("absurd", 5, "Kalau ada tombol ajaib yang bisa menghapus satu pekerjaan rumah selamanya, apa yang dipilih {subject}?"),
    _q("absurd", 6, "Kalau {subject} tiba-tiba punya ekor, kira-kira dipakai buat apa duluan?"),
    # kebiasaan
    _q("kebiasaan", 1, "Kebiasaan kecil apa yang paling sering dilakukan {subject} tanpa sadar?"),
    _q("kebiasaan", 2, "Alasan terlambat paling masuk akal yang mungkin dipakai {subject}?"),
    _q("kebiasaan", 3, "Kalau {subject} harus hidup di satu aplikasi selama seminggu, aplikasi apa?"),
    _q("kebiasaan", 4, "Hal kecil apa yang paling mudah membuat {subject} bahagia?"),
    _q("kebiasaan", 5, "Kebiasaan {subject} yang paling mungkin bikin orang lain gemas atau geregetan?"),
    _q("kebiasaan", 6, "Kalimat apa yang paling mungkin dikatakan {subject} saat panik?"),
    # makanan
    _q("makanan", 1, "Makanan apa yang masih sanggup dimakan {subject} tiga hari berturut-turut?"),
    _q("makanan", 2, "Kalau {subject} membuka warung, warung apa yang paling mungkin dibuat?"),
    _q("makanan", 3, "Makanan aneh apa yang mungkin diam-diam disukai {subject}?"),
    _q("makanan", 4, "Kalau {subject} harus makan satu jenis makanan doang selama sebulan, makanan apa yang dipilih?"),
    _q("makanan", 5, "Minuman apa yang paling cocok jadi \"ciri khas\" {subject}?"),
    _q("makanan", 6, "Kalau {subject} jadi juri lomba masak, kriteria paling aneh apa yang dipakai buat menilai?"),
    # perjalanan
    _q("perjalanan", 1, "Kalau {subject} bisa teleport sekarang juga, tempat pertama yang akan didatangi di mana?"),
    _q("perjalanan", 2, "Oleh-oleh paling aneh apa yang mungkin dibeli {subject} saat liburan?"),
    _q("perjalanan", 3, "Kalau {subject} tersesat di tempat asing, hal pertama yang dilakukan apa?"),
    _q("perjalanan", 4, "Barang paling tidak penting apa yang kemungkinan besar selalu dibawa {subject} kalau jalan-jalan?"),
    _q("perjalanan", 5, "Kalau {subject} jadi tour guide dadakan, gaya memandu yang dipakai kira-kira seperti apa?"),
    _q("perjalanan", 6, "Kendaraan paling nyeleneh apa yang paling cocok buat {subject} pakai sehari-hari?"),
    # khayalan
    _q("khayalan", 1, "Kalau hidup {subject} jadi judul sinetron, judulnya apa?"),
    _q("khayalan", 2, "Nama kapal bajak laut milik {subject} kira-kira apa?"),
    _q("khayalan", 3, "Kalau {subject} punya robot asisten, tugas pertama yang diberikan apa?"),
    _q("khayalan", 4, "Kalau {subject} jadi karakter game, kira-kira jenis karakter apa (tank, support, dll)?"),
    _q("khayalan", 5, "Kalau {subject} bisa mengganti suara notifikasi semua orang, suara apa yang dipilih?"),
    _q("khayalan", 6, "Kalau {subject} punya kekuatan buat menghentikan waktu 5 menit sekali sehari, dipakai buat apa?"),
    # situasi_sosial
    _q("situasi_sosial", 1, "Kalau {subject} dipanggil mendadak saat lagi di luar, alasan apa yang mungkin dipakai buat kabur?"),
    _q("situasi_sosial", 2, "Kalau {subject} ikut acara reality show, alasan terkenalnya apa?"),
    _q("situasi_sosial", 3, "Di grup chat, {subject} biasanya jadi tipe yang seperti apa (rame, silent reader, dll)?"),
    _q("situasi_sosial", 4, "Kalau {subject} diundang ke acara yang tidak dikenal siapa-siapa, reaksi pertamanya apa?"),
    _q("situasi_sosial", 5, "Kalau {subject} harus jadi MC acara dadakan, gimana kira-kira gayanya?"),
    _q("situasi_sosial", 6, "Topik obrolan apa yang paling mungkin bikin {subject} tiba-tiba jadi sangat aktif ngomong?"),
    # pilihan_sulit
    _q("pilihan_sulit", 1, "Kalau {subject} mendapat sepuluh juta rupiah tetapi harus habis hari ini, pembelian pertamanya apa?"),
    _q("pilihan_sulit", 2, "Kalau {subject} harus mengenakan satu warna selama sebulan, warna apa?"),
    _q("pilihan_sulit", 3, "Kalau {subject} cuma boleh pilih satu indera buat ditingkatkan jadi super, indera apa?"),
    _q("pilihan_sulit", 4, "Kalau {subject} harus pilih antara kaya tapi bosan atau pas-pasan tapi seru, kira-kira condong ke mana?"),
    _q("pilihan_sulit", 5, "Kalau {subject} disuruh pilih tinggal di kota besar atau di desa selamanya, kira-kira pilih apa?"),
    _q("pilihan_sulit", 6, "Kalau {subject} harus melepas satu media sosial selamanya, kira-kira yang mana yang paling gampang dilepas?"),
    # masa_depan
    _q("masa_depan", 1, "Pekerjaan aneh apa yang diam-diam mungkin cocok untuk {subject}?"),
    _q("masa_depan", 2, "Kalau {subject} jadi guru, pelajaran apa yang akan diajarkan dengan cara paling kacau?"),
    _q("masa_depan", 3, "Lima tahun dari sekarang, {subject} kemungkinan besar lagi sibuk dengan apa?"),
    _q("masa_depan", 4, "Kalau {subject} punya usaha sendiri, jenis usaha apa yang paling mungkin ditekuni?"),
    _q("masa_depan", 5, "Gelar/predikat lucu apa yang paling cocok disematkan ke {subject} kalau ada acara wisuda konyol?"),
    _q("masa_depan", 6, "Kalau {subject} jadi kepala sekolah sehari, aturan aneh apa yang bakal dibuat?"),
    # benda
    _q("benda", 1, "Barang apa yang paling mungkin diberi nama oleh {subject}?"),
    _q("benda", 2, "Benda apa yang paling susah dipisahkan dari {subject}?"),
    _q("benda", 3, "Kalau {subject} cuma boleh menyelamatkan satu barang dari rumah yang kebakaran, barang apa itu?"),
    _q("benda", 4, "Barang aneh apa yang mungkin nyempil di tas/kantong {subject} kalau digeledah sekarang?"),
    _q("benda", 5, "Kalau {subject} bikin koleksi barang aneh, kira-kira koleksi apa yang paling mungkin?"),
    _q("benda", 6, "Barang apa yang menurutmu paling \"menggambarkan\" {subject} banget?"),
    # hiburan
    _q("hiburan", 1, "Lagu apa yang paling cocok diputar ketika {subject} masuk ruangan?"),
    _q("hiburan", 2, "Kalau {subject} jadi karakter animasi, gimana kira-kira ciri khasnya?"),
    _q("hiburan", 3, "Film/series apa yang paling mungkin ditonton berulang-ulang oleh {subject}?"),
    _q("hiburan", 4, "Kalau {subject} bikin konten media sosial, isi kontennya bakal soal apa?"),
    _q("hiburan", 5, "Kalau {subject} ikut kuis TV, kategori soal apa yang paling dikuasai?"),
    _q("hiburan", 6, "Karaoke, lagu apa yang paling sering (atau paling mustahil) dinyanyikan {subject}?"),

        # absurd tambahan
    _q("absurd", 7, "Kalau {subject} bangun tidur dan semua benda bisa ngomong, benda apa yang paling dulu dimarahi?"),
    _q("absurd", 8, "Kalau {subject} harus berkomunikasi cuma pakai suara hewan sehari penuh, suara hewan apa yang dipilih?"),
    _q("absurd", 9, "Kalau bayangan {subject} tiba-tiba punya kehidupan sendiri, kira-kira hal pertama yang dilakukannya apa?"),
    _q("absurd", 10, "Kalau {subject} bisa menghidupkan satu benda mati, benda apa yang dipilih?"),
    _q("absurd", 11, "Kalau {subject} mendadak punya tiga tangan, tangan ketiganya paling sering dipakai buat apa?"),
    _q("absurd", 12, "Kalau setiap kali {subject} bersin muncul sesuatu secara ajaib, paling lucu kalau yang muncul apa?"),
    _q("absurd", 13, "Kalau {subject} harus mengganti nama manusia menjadi nama makanan, nama barunya apa?"),
    _q("absurd", 14, "Kalau {subject} menjadi hantu, aktivitas iseng apa yang paling mungkin dilakukan?"),
    _q("absurd", 15, "Kalau {subject} bisa membuat satu aturan fisika baru, aturan aneh apa yang bakal dibuat?"),
    _q("absurd", 16, "Kalau {subject} terjebak di dalam mesin capit boneka, strategi keluarnya bakal seperti apa?"),

    # kebiasaan tambahan
    _q("kebiasaan", 7, "Apa yang paling mungkin dilakukan {subject} lima menit setelah bangun tidur?"),
    _q("kebiasaan", 8, "Saat baterai HP tinggal 1%, apa yang paling mungkin dilakukan {subject}?"),
    _q("kebiasaan", 9, "Kalau {subject} bilang 'sebentar', biasanya sebentar versi dia itu berapa lama?"),
    _q("kebiasaan", 10, "Apa yang paling sering dicari {subject} padahal barangnya ternyata dekat?"),
    _q("kebiasaan", 11, "Kalau lagi bosan, apa yang biasanya pertama kali dilakukan {subject}?"),
    _q("kebiasaan", 12, "Jam berapa yang paling mungkin disebut {subject} sebagai 'masih belum terlalu malam'?"),
    _q("kebiasaan", 13, "Hal apa yang paling mungkin ditunda {subject} sampai detik terakhir?"),
    _q("kebiasaan", 14, "Apa yang paling mungkin dilakukan {subject} saat menunggu orang yang terlambat?"),
    _q("kebiasaan", 15, "Kalau {subject} sedang fokus, kebiasaan aneh apa yang mungkin muncul?"),
    _q("kebiasaan", 16, "Kalau kamar {subject} tiba-tiba berantakan, benda apa yang kemungkinan paling banyak berserakan?"),

    # makanan tambahan
    _q("makanan", 7, "Kalau tengah malam {subject} tiba-tiba lapar, makanan pertama yang dicari apa?"),
    _q("makanan", 8, "Kalau {subject} harus membuat nama menu berdasarkan dirinya sendiri, nama menunya apa?"),
    _q("makanan", 9, "Makanan apa yang kemungkinan besar tidak akan dibagi {subject} meskipun diminta?"),
    _q("makanan", 10, "Kalau traktiran gratis cuma boleh satu makanan, apa yang paling mungkin dipilih {subject}?"),
    _q("makanan", 11, "Kalau {subject} menjadi makanan, makanan apa yang paling menggambarkan sifatnya?"),
    _q("makanan", 12, "Sambal level berapa yang kira-kira masih berani dicoba {subject}?"),
    _q("makanan", 13, "Kalau {subject} menemukan makanan jatuh tapi belum lima detik, kira-kira tetap dimakan atau dibuang?"),
    _q("makanan", 14, "Bagian makanan apa yang paling mungkin selalu disisakan {subject}?"),
    _q("makanan", 15, "Kalau {subject} cuma boleh memilih gorengan seumur hidup, gorengan apa yang dipilih?"),
    _q("makanan", 16, "Kalau semua makanan mendadak gratis selama satu jam, {subject} bakal berburu makanan apa dulu?"),

    # perjalanan tambahan
    _q("perjalanan", 7, "Kalau liburan tanpa rencana, {subject} lebih mungkin tersesat atau menemukan tempat seru?"),
    _q("perjalanan", 8, "Kalau {subject} ketinggalan kendaraan saat liburan, reaksi pertamanya apa?"),
    _q("perjalanan", 9, "Tempat seperti apa yang paling mungkin bikin {subject} lupa waktu saat liburan?"),
    _q("perjalanan", 10, "Kalau {subject} boleh liburan gratis tapi berangkat 10 menit lagi, barang pertama yang diambil apa?"),
    _q("perjalanan", 11, "Kalau {subject} harus road trip 12 jam, apa yang paling mungkin bikin penumpang lain kesal?"),
    _q("perjalanan", 12, "Kalau menginap di hotel mewah, fasilitas apa yang pertama kali dicoba {subject}?"),
    _q("perjalanan", 13, "Kalau {subject} pergi ke tempat bersalju, hal pertama yang kemungkinan dilakukan apa?"),
    _q("perjalanan", 14, "Kalau {subject} pergi ke pulau kosong, barang receh apa yang kemungkinan malah dibawa?"),
    _q("perjalanan", 15, "Kalau cuma boleh memilih gunung, pantai, atau kota besar, mana yang paling mungkin dipilih {subject}?"),
    _q("perjalanan", 16, "Foto liburan seperti apa yang paling mungkin diambil {subject}?"),

    # khayalan tambahan
    _q("khayalan", 7, "Kalau {subject} punya kerajaan sendiri, nama kerajaannya apa?"),
    _q("khayalan", 8, "Kalau {subject} punya mantra sihir sendiri, mantranya dipakai buat apa?"),
    _q("khayalan", 9, "Kalau {subject} menjadi bos terakhir dalam game, serangan pamungkasnya apa?"),
    _q("khayalan", 10, "Kalau {subject} punya planet sendiri, aturan paling aneh di planet itu apa?"),
    _q("khayalan", 11, "Kalau {subject} punya naga peliharaan, bakal diberi nama apa?"),
    _q("khayalan", 12, "Kalau {subject} masuk dunia kartun, benda apa yang paling mungkin dibawa pulang ke dunia nyata?"),
    _q("khayalan", 13, "Kalau {subject} menemukan lampu ajaib, permintaan pertama yang paling mungkin apa?"),
    _q("khayalan", 14, "Kalau {subject} menjadi dewa dari satu hal receh, dia bakal jadi dewa apa?"),
    _q("khayalan", 15, "Kalau mimpi {subject} bisa ditonton seperti film, genre yang paling sering muncul apa?"),
    _q("khayalan", 16, "Kalau {subject} punya markas rahasia, tempat persembunyiannya kira-kira di mana?"),

    # situasi_sosial tambahan
    _q("situasi_sosial", 7, "Kalau {subject} bertemu orang yang salah menyebut namanya, apa yang kemungkinan dilakukan?"),
    _q("situasi_sosial", 8, "Kalau semua orang mendadak diam dalam obrolan, apakah {subject} bakal memecah keheningan? Dengan apa?"),
    _q("situasi_sosial", 9, "Kalau {subject} tidak sengaja melambaikan tangan ke orang yang ternyata bukan kenalannya, reaksinya apa?"),
    _q("situasi_sosial", 10, "Kalau {subject} masuk ruangan dan semua orang menatapnya, apa yang bakal dilakukan?"),
    _q("situasi_sosial", 11, "Kalau diminta pidato tanpa persiapan, kalimat pembuka {subject} kira-kira apa?"),
    _q("situasi_sosial", 12, "Kalau {subject} menerima telepon dari nomor tidak dikenal, kemungkinan diangkat atau dibiarkan?"),
    _q("situasi_sosial", 13, "Kalau ketahuan salah kirim chat, apa yang paling mungkin dilakukan {subject}?"),
    _q("situasi_sosial", 14, "Kalau {subject} dipuji di depan banyak orang, respons pertamanya apa?"),
    _q("situasi_sosial", 15, "Kalau {subject} harus menyapa orang baru, pembuka obrolannya kira-kira tentang apa?"),
    _q("situasi_sosial", 16, "Kalau suasana nongkrong mulai membosankan, apa yang mungkin dilakukan {subject} untuk meramaikannya?"),

    # pilihan_sulit tambahan
    _q("pilihan_sulit", 7, "Kalau {subject} harus memilih tidak punya internet atau tidak punya AC selama sebulan, pilih mana?"),
    _q("pilihan_sulit", 8, "Kalau {subject} harus pilih bisa terbang atau bisa menghilang, pilih yang mana?"),
    _q("pilihan_sulit", 9, "Kalau {subject} harus hidup tanpa nasi atau tanpa mie, mana yang rela dilepas?"),
    _q("pilihan_sulit", 10, "Kalau {subject} cuma boleh tidur 4 jam atau tidak boleh minum minuman manis seminggu, pilih mana?"),
    _q("pilihan_sulit", 11, "Kalau {subject} harus memilih selalu kepanasan atau selalu kedinginan, pilih mana?"),
    _q("pilihan_sulit", 12, "Kalau {subject} harus mengulang satu hari menyenangkan atau melewati satu hari membosankan, pilih mana?"),
    _q("pilihan_sulit", 13, "Kalau {subject} dapat uang banyak tapi HP harus jadul setahun, mau atau tidak?"),
    _q("pilihan_sulit", 14, "Kalau {subject} harus memilih selalu datang 30 menit terlalu cepat atau 10 menit terlambat, pilih mana?"),
    _q("pilihan_sulit", 15, "Kalau {subject} cuma boleh menggunakan chat atau telepon selama sebulan, pilih yang mana?"),
    _q("pilihan_sulit", 16, "Kalau {subject} harus kehilangan cemilan favorit atau aplikasi favorit selama setahun, pilih mana?"),

    # masa_depan tambahan
    _q("masa_depan", 7, "Kalau {subject} terkenal suatu hari nanti, kemungkinan terkenal gara-gara apa?"),
    _q("masa_depan", 8, "Barang mahal pertama yang kemungkinan dibeli {subject} kalau sudah kaya apa?"),
    _q("masa_depan", 9, "Kalau {subject} punya rumah impian, ruangan paling aneh di rumah itu buat apa?"),
    _q("masa_depan", 10, "Kalau {subject} suatu hari menulis buku, bukunya kemungkinan membahas apa?"),
    _q("masa_depan", 11, "Kalau {subject} punya karyawan, tipe bos seperti apa kira-kira dia?"),
    _q("masa_depan", 12, "Kalau {subject} punya banyak uang dan bebas kerja apa saja, aktivitas sehari-harinya bakal seperti apa?"),
    _q("masa_depan", 13, "Apa benda yang sekarang dianggap sepele tapi mungkin suatu hari dikoleksi {subject}?"),
    _q("masa_depan", 14, "Kalau {subject} muncul di berita 10 tahun lagi, kira-kira beritanya tentang apa?"),
    _q("masa_depan", 15, "Kalau {subject} menciptakan produk sendiri, produk pertama yang dibuat apa?"),
    _q("masa_depan", 16, "Kalau {subject} pensiun sangat muda, kegiatan apa yang kemungkinan paling sering dilakukan?"),

    # benda tambahan
    _q("benda", 7, "Kalau HP {subject} bisa bicara, rahasia kebiasaan apa yang mungkin dibongkar duluan?"),
    _q("benda", 8, "Barang apa yang paling mungkin dibeli {subject} karena lucu padahal tidak dibutuhkan?"),
    _q("benda", 9, "Kalau satu barang milik {subject} punya nilai sentimental paling besar, barang apa kira-kira?"),
    _q("benda", 10, "Benda apa yang paling mungkin sering hilang di tangan {subject}?"),
    _q("benda", 11, "Kalau {subject} mendapat voucher gratis untuk satu jenis barang, barang apa yang dipilih?"),
    _q("benda", 12, "Barang apa yang kemungkinan paling sering dipinjam orang dari {subject}?"),
    _q("benda", 13, "Kalau meja {subject} diperiksa sekarang, benda paling random apa yang mungkin ditemukan?"),
    _q("benda", 14, "Benda apa yang kemungkinan dibawa {subject} meskipun sebenarnya hampir tidak pernah dipakai?"),
    _q("benda", 15, "Kalau {subject} harus membawa satu barang ke mana-mana selama seminggu, barang paling lucu apa yang cocok?"),
    _q("benda", 16, "Kalau {subject} bisa mendapatkan versi tak terbatas dari satu benda, benda apa yang dipilih?"),

    # hiburan tambahan
    _q("hiburan", 7, "Kalau kehidupan {subject} punya soundtrack, genre musiknya apa?"),
    _q("hiburan", 8, "Kalau {subject} menjadi host acara TV, acara tentang apa yang paling cocok?"),
    _q("hiburan", 9, "Kalau {subject} ikut kompetisi bakat, bakat apa yang kemungkinan ditampilkan?"),
    _q("hiburan", 10, "Kalau {subject} menjadi meme viral, ekspresi seperti apa yang paling mungkin jadi meme?"),
    _q("hiburan", 11, "Kalau {subject} punya podcast, topik yang paling sering dibahas apa?"),
    _q("hiburan", 12, "Kalau {subject} menjadi pemeran utama film, genre apa yang paling cocok?"),
    _q("hiburan", 13, "Kalau {subject} harus cosplay satu karakter, karakter seperti apa yang kemungkinan dipilih?"),
    _q("hiburan", 14, "Kalau {subject} punya channel YouTube sukses, video paling viralnya kira-kira tentang apa?"),
    _q("hiburan", 15, "Kalau {subject} ikut acara pencarian bakat tapi tidak boleh menyanyi, bakat apa yang akan ditampilkan?"),
    _q("hiburan", 16, "Kalau {subject} harus menonton satu genre film selamanya, genre apa yang dipilih?"),

    # sekolah
    _q("sekolah", 1, "Kalau ada pelajaran yang boleh dihapus oleh {subject}, pelajaran apa yang kemungkinan dipilih?"),
    _q("sekolah", 2, "Kalau {subject} lupa mengerjakan tugas, alasan pertama yang kemungkinan terpikir apa?"),
    _q("sekolah", 3, "Kalau guru tiba-tiba bilang 'keluarkan kertas', reaksi pertama {subject} apa?"),
    _q("sekolah", 4, "Kalau {subject} bebas memilih tempat duduk di kelas, posisi mana yang kemungkinan dipilih?"),
    _q("sekolah", 5, "Kalau {subject} disuruh maju tanpa tahu jawabannya, strategi bertahan hidupnya apa?"),
    _q("sekolah", 6, "Kalau ada jam kosong, aktivitas pertama yang kemungkinan dilakukan {subject} apa?"),
    _q("sekolah", 7, "Kalau {subject} jadi guru piket sehari, aturan apa yang paling mungkin dilonggarkan?"),
    _q("sekolah", 8, "Kalau {subject} dapat nilai 100 tanpa menyangka, reaksi pertamanya apa?"),
    _q("sekolah", 9, "Kalau {subject} harus presentasi sendirian, bagian apa yang paling dikhawatirkan?"),
    _q("sekolah", 10, "Kalau kantin cuma menjual satu makanan, makanan apa yang diharapkan {subject}?"),
    _q("sekolah", 11, "Apa yang dilakukan {subject} kalau namanya tiba-tiba dipanggil guru saat sedang tidak memperhatikan?"),
    _q("sekolah", 12, "Kalau ada lomba antar kelas, lomba apa yang kemungkinan paling semangat diikuti {subject}?"),
    _q("sekolah", 13, "Kalau {subject} boleh membuat satu ekstrakurikuler baru, ekskul apa yang dibuat?"),
    _q("sekolah", 14, "Kalau {subject} datang ke sekolah tapi ternyata libur, apa yang kemungkinan dilakukan setelahnya?"),
    _q("sekolah", 15, "Kalau bel pulang berbunyi 30 menit lebih cepat, apa reaksi pertama {subject}?"),

    # pertemanan
    _q("pertemanan", 1, "Kalau teman {subject} tiba-tiba mengajak pergi tanpa bilang tujuannya, apakah dia ikut?"),
    _q("pertemanan", 2, "Kalau teman lagi bad mood, cara {subject} menghiburnya kemungkinan seperti apa?"),
    _q("pertemanan", 3, "Hal receh apa yang paling mungkin membuat {subject} menagih janji teman?"),
    _q("pertemanan", 4, "Kalau ada teman tersandung di depannya, {subject} lebih dulu menolong atau tertawa?"),
    _q("pertemanan", 5, "Kalau teman ulang tahun, hadiah paling khas dari {subject} kira-kira apa?"),
    _q("pertemanan", 6, "Kalau ada rahasia receh, seberapa lama {subject} bisa menahannya untuk tidak cerita?"),
    _q("pertemanan", 7, "Kalau nongkrong berempat, peran {subject} biasanya apa?"),
    _q("pertemanan", 8, "Kalau teman meminta pendapat soal sesuatu yang jelek, sejujur apa {subject} bakal menjawab?"),
    _q("pertemanan", 9, "Kalau teman minta ditemani ke suatu tempat, alasan apa yang bisa bikin {subject} langsung setuju?"),
    _q("pertemanan", 10, "Apa hal kecil yang paling mungkin diingat {subject} tentang teman-temannya?"),
    _q("pertemanan", 11, "Kalau semua teman bingung menentukan mau makan di mana, apakah {subject} bakal menentukan tempat?"),
    _q("pertemanan", 12, "Julukan macam apa yang paling mungkin dibuat {subject} untuk temannya?"),

    # teknologi
    _q("teknologi", 1, "Kalau penyimpanan HP {subject} penuh, file apa yang kemungkinan paling susah dia hapus?"),
    _q("teknologi", 2, "Aplikasi apa yang paling membuat {subject} panik kalau tiba-tiba tidak bisa dibuka?"),
    _q("teknologi", 3, "Kalau internet mati selama sehari, kegiatan pengganti pertama {subject} apa?"),
    _q("teknologi", 4, "Kalau {subject} punya AI pribadi, tugas paling receh apa yang bakal diserahkan ke AI?"),
    _q("teknologi", 5, "Kalau boleh menciptakan aplikasi sendiri, aplikasi buatan {subject} bakal berguna untuk apa?"),
    _q("teknologi", 6, "Berapa banyak tab browser yang kira-kira sanggup dibiarkan terbuka oleh {subject}?"),
    _q("teknologi", 7, "Kalau password harus berupa satu kata lucu, kata seperti apa yang kemungkinan dipilih {subject}?"),
    _q("teknologi", 8, "Kalau HP {subject} tiba-tiba memutar suara terakhir yang dia dengar keras-keras, apa yang paling dia takutkan muncul?"),
    _q("teknologi", 9, "Kalau {subject} mendapat gadget baru, fitur apa yang pertama kali dicoba?"),
    _q("teknologi", 10, "Kalau {subject} harus memakai HP jadul seminggu, hal apa yang paling cepat bikin menyerah?"),
    _q("teknologi", 11, "Kalau galeri {subject} dibuka secara acak, jenis foto apa yang kemungkinan paling banyak muncul?"),
    _q("teknologi", 12, "Kalau {subject} tidak sengaja mengirim stiker aneh ke grup penting, apa yang bakal dilakukan?"),

    # uang
    _q("uang", 1, "Kalau {subject} menemukan uang seratus ribu di saku celana lama, pertama kali dipakai buat apa?"),
    _q("uang", 2, "Hal receh apa yang paling gampang bikin {subject} berkata 'ah, beli aja'?"),
    _q("uang", 3, "Kalau dapat cashback besar, {subject} bakal menabung atau langsung belanja lagi?"),
    _q("uang", 4, "Kalau {subject} dikasih satu juta tapi cuma boleh membeli barang tidak penting, beli apa?"),
    _q("uang", 5, "Kalau harus hemat seminggu, pengeluaran apa yang paling sulit dikurangi {subject}?"),
    _q("uang", 6, "Kalau {subject} mendadak jadi miliarder, siapa atau apa yang pertama kali ditraktir?"),
    _q("uang", 7, "Barang murah apa yang kemungkinan dianggap sangat worth it oleh {subject}?"),
    _q("uang", 8, "Kalau {subject} punya mesin pencetak uang receh, uangnya bakal paling banyak dipakai buat apa?"),
    _q("uang", 9, "Kalau mendapat voucher belanja yang kedaluwarsa malam ini, toko apa yang kemungkinan didatangi {subject}?"),
    _q("uang", 10, "Kalau {subject} harus memilih antara diskon 90% atau barang gratis misterius, pilih mana?"),

    # rumah
    _q("rumah", 1, "Kalau {subject} sendirian di rumah, aktivitas paling aneh yang mungkin dilakukan apa?"),
    _q("rumah", 2, "Ruangan mana yang paling sering ditempati {subject} kalau sedang santai?"),
    _q("rumah", 3, "Kalau listrik mati malam-malam, apa yang pertama kali dicari {subject}?"),
    _q("rumah", 4, "Kalau {subject} mendengar suara aneh dari dapur tengah malam, apa yang kemungkinan dilakukan?"),
    _q("rumah", 5, "Pekerjaan rumah apa yang paling mungkin ditunda {subject}?"),
    _q("rumah", 6, "Kalau {subject} boleh merenovasi satu bagian rumah sesuka hati, bagian apa yang dipilih?"),
    _q("rumah", 7, "Kalau ada cicak jatuh dekat {subject}, reaksinya kira-kira bagaimana?"),
    _q("rumah", 8, "Kalau {subject} kehilangan remote TV, tempat pertama yang diperiksa di mana?"),
    _q("rumah", 9, "Kalau semua makanan di rumah habis malam-malam, apa solusi {subject}?"),
    _q("rumah", 10, "Kalau kamar {subject} punya slogan, slogan yang cocok apa?"),

    # hewan
    _q("hewan", 1, "Kalau {subject} punya kucing yang bisa bicara, pertanyaan pertama yang dia tanyakan apa?"),
    _q("hewan", 2, "Hewan apa yang paling cocok menjadi partner petualangan {subject}?"),
    _q("hewan", 3, "Kalau {subject} bisa memahami satu jenis hewan, hewan apa yang dipilih?"),
    _q("hewan", 4, "Kalau {subject} harus memelihara hewan yang tidak biasa, hewan apa yang kemungkinan dipilih?"),
    _q("hewan", 5, "Kalau seekor bebek mengikuti {subject} ke mana-mana, apa yang bakal dilakukan?"),
    _q("hewan", 6, "Kalau {subject} berubah jadi kucing, aktivitas pertamanya apa?"),
    _q("hewan", 7, "Kalau {subject} menjadi burung, tempat pertama yang akan diterbangi ke mana?"),
    _q("hewan", 8, "Hewan apa yang paling menggambarkan suasana hati {subject} saat baru bangun tidur?"),
    _q("hewan", 9, "Kalau {subject} punya ayam yang bertelur benda lain, dia berharap ayamnya menghasilkan apa?"),
    _q("hewan", 10, "Kalau hewan peliharaan {subject} bisa memberi nama kepadanya, nama apa yang mungkin diberikan?"),

    # zombie
    _q("zombie", 1, "Kalau kiamat zombie dimulai sekarang, barang pertama yang diambil {subject} apa?"),
    _q("zombie", 2, "Dalam tim penyintas zombie, peran {subject} paling cocok jadi apa?"),
    _q("zombie", 3, "Kalau dikejar zombie, tempat pertama yang kemungkinan dipilih {subject} untuk bersembunyi di mana?"),
    _q("zombie", 4, "Siapa yang lebih mungkin dilakukan {subject}: melawan zombie atau kabur sekencang-kencangnya?"),
    _q("zombie", 5, "Kalau cuma boleh membawa satu makanan saat kiamat zombie, apa pilihan {subject}?"),
    _q("zombie", 6, "Kalau {subject} ternyata kebal dari zombie, hal pertama yang bakal dilakukan apa?"),
    _q("zombie", 7, "Kendaraan apa yang kemungkinan dipilih {subject} untuk kabur dari zombie?"),
    _q("zombie", 8, "Kalau markas zombie butuh nama, nama apa yang kira-kira dibuat {subject}?"),

    # misteri
    _q("misteri", 1, "Kalau {subject} menemukan pintu rahasia di rumahnya, apa yang dilakukan pertama kali?"),
    _q("misteri", 2, "Kalau ada paket misterius tanpa nama pengirim, apakah {subject} langsung membukanya?"),
    _q("misteri", 3, "Kalau {subject} menemukan peta harta karun, siapa atau apa yang pertama kali disiapkan?"),
    _q("misteri", 4, "Kalau jam 3 pagi ada yang mengetuk pintu, apa reaksi pertama {subject}?"),
    _q("misteri", 5, "Kalau {subject} melihat sesuatu bergerak sendiri, dugaan pertamanya apa?"),
    _q("misteri", 6, "Kalau ada tombol merah besar bertuliskan 'JANGAN DITEKAN', apakah {subject} bakal menekannya?"),
    _q("misteri", 7, "Kalau {subject} menemukan buku yang bisa menjawab satu pertanyaan apa pun, apa yang ditanyakan?"),
    _q("misteri", 8, "Kalau ada lemari yang ternyata portal, ke mana {subject} berharap portal itu menuju?"),
    _q("misteri", 9, "Kalau tiba-tiba semua jam berhenti tepat pukul 12, apa yang dilakukan {subject}?"),
    _q("misteri", 10, "Kalau {subject} menjadi detektif, kebiasaan khas apa yang bakal dimiliki?"),

    # keberuntungan
    _q("keberuntungan", 1, "Kalau {subject} menang undian perjalanan gratis, siapa yang kemungkinan pertama kali diajak?"),
    _q("keberuntungan", 2, "Kalau hari ini {subject} sangat beruntung, keberuntungan seperti apa yang paling diharapkan?"),
    _q("keberuntungan", 3, "Kalau menemukan mesin capit yang dijamin menang sekali, hadiah apa yang dicari {subject}?"),
    _q("keberuntungan", 4, "Kalau {subject} diberi satu kesempatan memutar roda hadiah, hadiah apa yang paling diinginkan?"),
    _q("keberuntungan", 5, "Kalau {subject} mendapat satu hari bebas dari semua kewajiban, bagaimana hari itu bakal dihabiskan?"),
    _q("keberuntungan", 6, "Kalau semua lampu lalu lintas selalu hijau untuk {subject} sehari penuh, dia bakal pergi ke mana?"),
    _q("keberuntungan", 7, "Kalau {subject} bisa mendapatkan satu barang gratis dari toko mana pun, apa yang dipilih?"),
    _q("keberuntungan", 8, "Kalau satu tebakan {subject} hari ini dijamin benar, dia bakal menebak soal apa?"),

    # pekerjaan
    _q("pekerjaan", 1, "Kalau {subject} bekerja di restoran, posisi apa yang paling cocok?"),
    _q("pekerjaan", 2, "Kalau {subject} jadi satpam sehari, hal apa yang paling mungkin dilakukan saat sepi?"),
    _q("pekerjaan", 3, "Kalau {subject} jadi CEO, kebijakan kantor paling aneh apa yang mungkin dibuat?"),
    _q("pekerjaan", 4, "Kalau {subject} harus memakai seragam kerja unik, seragam seperti apa yang cocok?"),
    _q("pekerjaan", 5, "Kalau pekerjaan {subject} cuma menekan satu tombol tiap jam, apa yang dilakukan di waktu sisanya?"),
    _q("pekerjaan", 6, "Kalau {subject} membuka jasa aneh, jasa apa yang kemungkinan laku?"),
    _q("pekerjaan", 7, "Kalau {subject} jadi kasir dan bertemu pelanggan aneh, bagaimana reaksinya?"),
    _q("pekerjaan", 8, "Kalau {subject} punya kantor sendiri, benda apa yang wajib ada di mejanya?"),
    _q("pekerjaan", 9, "Kalau {subject} bekerja dari rumah, gangguan terbesar yang kemungkinan muncul apa?"),
    _q("pekerjaan", 10, "Kalau {subject} boleh menciptakan pekerjaan baru, nama pekerjaannya apa?"),

    # terkenal
    _q("terkenal", 1, "Kalau {subject} tiba-tiba viral besok, kira-kira viral karena apa?"),
    _q("terkenal", 2, "Kalau {subject} punya satu juta followers, konten apa yang kemungkinan paling sering dibuat?"),
    _q("terkenal", 3, "Kalau {subject} diwawancarai TV, pertanyaan apa yang paling mungkin membuatnya bingung?"),
    _q("terkenal", 4, "Kalau {subject} punya fans club, nama fans club-nya apa?"),
    _q("terkenal", 5, "Kalau {subject} punya merchandise sendiri, barang apa yang dijual?"),
    _q("terkenal", 6, "Kalau {subject} masuk berita karena kejadian lucu, kejadian apa yang paling mungkin?"),
    _q("terkenal", 7, "Kalau {subject} punya slogan terkenal, bunyinya kira-kira apa?"),
    _q("terkenal", 8, "Kalau {subject} diminta tanda tangan oleh penggemar, gaya tanda tangannya seperti apa?"),

    # waktu
    _q("waktu", 1, "Kalau {subject} bisa kembali ke satu umur selama sehari, umur berapa yang kemungkinan dipilih?"),
    _q("waktu", 2, "Kalau {subject} bisa melihat dirinya 20 tahun dari sekarang selama satu menit, apa yang pertama kali dilihat?"),
    _q("waktu", 3, "Kalau {subject} bisa mengulang satu momen lucu, momen seperti apa yang bakal dipilih?"),
    _q("waktu", 4, "Kalau {subject} dilempar 100 tahun ke masa depan, hal pertama yang ingin diketahui apa?"),
    _q("waktu", 5, "Kalau {subject} hidup sehari di zaman kerajaan, peran apa yang paling cocok?"),
    _q("waktu", 6, "Kalau {subject} bisa menghentikan waktu saat satu kejadian sehari-hari, biasanya kapan?"),
    _q("waktu", 7, "Kalau {subject} bertemu dirinya sendiri waktu kecil, nasihat receh apa yang bakal diberikan?"),
    _q("waktu", 8, "Kalau {subject} menerima pesan dari dirinya di masa depan, isi pesan paling mungkin apa?"),

    # cuaca
    _q("cuaca", 1, "Kalau hujan turun tepat saat {subject} mau keluar, apa yang kemungkinan dilakukan?"),
    _q("cuaca", 2, "Kalau {subject} bisa menentukan cuaca besok, cuaca apa yang dipilih?"),
    _q("cuaca", 3, "Kalau turun hujan makanan, makanan apa yang paling diharapkan {subject}?"),
    _q("cuaca", 4, "Kalau {subject} harus memilih hidup di tempat yang selalu hujan atau selalu panas, pilih mana?"),
    _q("cuaca", 5, "Saat hujan deras dan dingin, aktivitas favorit {subject} kemungkinan apa?"),
    _q("cuaca", 6, "Kalau {subject} bisa membuat awan berbentuk apa pun, bentuk pertama yang dibuat apa?"),
    _q("cuaca", 7, "Kalau salju tiba-tiba turun di depan rumah {subject}, apa yang dilakukan pertama kali?"),
    _q("cuaca", 8, "Kalau {subject} punya payung ajaib, fitur tambahan apa yang paling dia inginkan?"),

    # tantangan
    _q("tantangan", 1, "Kalau {subject} ditantang tidak membuka HP selama 24 jam, kira-kira kuat berapa lama?"),
    _q("tantangan", 2, "Kalau {subject} harus bicara dengan suara pelan sehari penuh, kapan kemungkinan pertama kali gagal?"),
    _q("tantangan", 3, "Kalau {subject} ditantang makan tanpa sendok dan garpu sehari, makanan apa yang paling merepotkan?"),
    _q("tantangan", 4, "Kalau {subject} harus berjalan mundur selama lima menit di tempat umum, reaksinya apa?"),
    _q("tantangan", 5, "Kalau {subject} harus membuat orang tertawa dalam 30 detik, apa yang kemungkinan dilakukan?"),
    _q("tantangan", 6, "Kalau {subject} harus memakai kostum aneh sehari penuh, kostum apa yang paling cocok?"),
    _q("tantangan", 7, "Kalau {subject} harus hidup tanpa mengeluh selama sehari, hal apa yang paling mungkin membuatnya gagal?"),
    _q("tantangan", 8, "Kalau {subject} ditantang membuat makanan cuma dari tiga bahan, kira-kira bikin apa?"),
    _q("tantangan", 9, "Kalau {subject} harus menghafal sesuatu dalam lima menit, trik apa yang mungkin digunakan?"),
    _q("tantangan", 10, "Kalau {subject} harus membuat video satu menit tanpa persiapan, videonya bakal tentang apa?"),

    # salah_tingkah
    _q("salah_tingkah", 1, "Kalau {subject} terpeleset tapi tidak jatuh di depan banyak orang, apa yang dilakukan setelahnya?"),
    _q("salah_tingkah", 2, "Kalau {subject} masuk ke ruangan yang salah, bagaimana cara keluarnya?"),
    _q("salah_tingkah", 3, "Kalau {subject} manggil orang tapi ternyata salah orang, bagaimana cara menyelamatkan situasi?"),
    _q("salah_tingkah", 4, "Kalau {subject} tertawa di situasi yang seharusnya serius, bagaimana cara menahannya?"),
    _q("salah_tingkah", 5, "Kalau suara perut {subject} terdengar keras di ruangan sunyi, reaksinya apa?"),
    _q("salah_tingkah", 6, "Kalau {subject} sadar bajunya terbalik setelah lama dipakai, apa yang dilakukan?"),
    _q("salah_tingkah", 7, "Kalau {subject} menjawab pertanyaan padahal ternyata bukan dia yang ditanya, reaksinya apa?"),
    _q("salah_tingkah", 8, "Kalau {subject} gagal membuka pintu karena ternyata harus ditarik bukan didorong, apa yang dilakukan?"),
    _q("salah_tingkah", 9, "Kalau {subject} melambaikan tangan dan tidak dibalas, bagaimana cara pura-pura tidak malu?"),
    _q("salah_tingkah", 10, "Kalau HP {subject} berbunyi sangat keras di ruangan sunyi, secepat apa dia bakal panik?"),

    # random
    _q("random", 1, "Kalau {subject} harus memberi nama sebuah pulau, nama apa yang kemungkinan dipilih?"),
    _q("random", 2, "Warna apa yang paling menggambarkan energi {subject}?"),
    _q("random", 3, "Kalau {subject} adalah sebuah emoji, emoji apa yang paling cocok?"),
    _q("random", 4, "Kalau {subject} adalah suara, suara apa yang paling cocok menggambarkannya?"),
    _q("random", 5, "Kalau {subject} adalah hari dalam seminggu, hari apa yang paling cocok?"),
    _q("random", 6, "Kalau {subject} adalah sebuah kendaraan, kendaraan apa?"),
    _q("random", 7, "Kalau {subject} adalah rasa es krim, rasa apa?"),
    _q("random", 8, "Kalau {subject} adalah sebuah cuaca, cuaca apa?"),
    _q("random", 9, "Kalau {subject} adalah benda di dapur, benda apa?"),
    _q("random", 10, "Kalau {subject} adalah satu kata di kamus, kata apa yang paling cocok?"),
    _q("random", 11, "Kalau {subject} punya tombol khusus di tubuhnya, tombol itu berfungsi untuk apa?"),
    _q("random", 12, "Kalau ada patung {subject} di tengah kota, pose patungnya bakal seperti apa?"),

    # andaikan
    _q("andaikan", 1, "Kalau {subject} bangun besok dan bisa membaca pikiran, pikiran siapa yang pertama ingin dibaca?"),
    _q("andaikan", 2, "Kalau {subject} mendadak bisa berbicara semua bahasa, hal pertama yang dilakukan apa?"),
    _q("andaikan", 3, "Kalau semua orang lupa nama {subject}, nama baru apa yang mungkin dia pilih?"),
    _q("andaikan", 4, "Kalau {subject} mendapat satu ruangan rahasia gratis, ruangan itu bakal dijadikan apa?"),
    _q("andaikan", 5, "Kalau {subject} bisa menggandakan satu benda sebanyak mungkin, benda apa yang digandakan?"),
    _q("andaikan", 6, "Kalau {subject} boleh mengganti suara klakson semua kendaraan, suara apa yang dipilih?"),
    _q("andaikan", 7, "Kalau semua pintu bisa membawa {subject} ke satu tempat pilihan, tempat apa yang dipilih?"),
    _q("andaikan", 8, "Kalau {subject} bisa membuat satu hal menjadi gratis selamanya, apa yang dipilih?"),
    _q("andaikan", 9, "Kalau {subject} mendapatkan satu kloningan dirinya sendiri sehari, kloningannya disuruh apa?"),
    _q("andaikan", 10, "Kalau {subject} punya tombol undo untuk kehidupan nyata, paling sering dipakai untuk kejadian apa?"),

    # rahasia_receh
    _q("rahasia_receh", 1, "Hal receh apa yang mungkin dilakukan {subject} diam-diam tapi malu mengakuinya?"),
    _q("rahasia_receh", 2, "Makanan apa yang mungkin dimakan {subject} diam-diam supaya tidak diminta orang?"),
    _q("rahasia_receh", 3, "Apa yang mungkin dilakukan {subject} kalau yakin tidak ada seorang pun yang melihat?"),
    _q("rahasia_receh", 4, "Lagu seperti apa yang mungkin diam-diam hafal banget oleh {subject}?"),
    _q("rahasia_receh", 5, "Hal kekanak-kanakan apa yang mungkin masih disukai {subject}?"),
    _q("rahasia_receh", 6, "Apa yang mungkin pernah dicari {subject} di internet lalu langsung menghapus riwayat pencariannya karena malu?"),
    _q("rahasia_receh", 7, "Barang murah apa yang mungkin diam-diam sangat disayang {subject}?"),
    _q("rahasia_receh", 8, "Kebiasaan lucu apa yang mungkin dilakukan {subject} saat sendirian?"),

    # kompetisi
    _q("kompetisi", 1, "Kalau ada lomba tidur, seberapa yakin {subject} bisa menang?"),
    _q("kompetisi", 2, "Kalau ada lomba mencari alasan, apakah {subject} berpeluang jadi juara?"),
    _q("kompetisi", 3, "Lomba receh apa yang kemungkinan bisa dimenangkan {subject} tanpa latihan?"),
    _q("kompetisi", 4, "Kalau {subject} ikut lomba makan, makanan apa yang paling cocok untuknya?"),
    _q("kompetisi", 5, "Kalau ada lomba menahan tawa, siapa yang lebih dulu bikin {subject} kalah?"),
    _q("kompetisi", 6, "Kalau {subject} ikut lomba membuat meme, tema apa yang kemungkinan dipilih?"),
    _q("kompetisi", 7, "Kalau ada olimpiade kegiatan sehari-hari, cabang apa yang cocok untuk {subject}?"),
    _q("kompetisi", 8, "Kalau {subject} harus menantang seseorang dalam permainan, permainan apa yang paling percaya diri dipilih?"),

    # dunia_game
    _q("dunia_game", 1, "Kalau hidup punya tombol save, kapan {subject} paling sering menekannya?"),
    _q("dunia_game", 2, "Kalau hidup {subject} punya achievement, achievement pertama yang terbuka apa?"),
    _q("dunia_game", 3, "Kalau {subject} punya tiga nyawa, satu nyawa kemungkinan habis gara-gara apa?"),
    _q("dunia_game", 4, "Kalau {subject} punya inventory seperti game, benda random apa yang selalu ada di dalamnya?"),
    _q("dunia_game", 5, "Kalau {subject} menjadi NPC, kalimat apa yang bakal diulang terus?"),
    _q("dunia_game", 6, "Kalau kehidupan {subject} punya tingkat kesulitan, kira-kira sekarang sedang di level apa?"),
    _q("dunia_game", 7, "Kalau {subject} mendapatkan item legendaris, item itu punya kemampuan apa?"),
    _q("dunia_game", 8, "Kalau {subject} bisa respawn sekali, kejadian apa yang paling mungkin bikin fitur itu terpakai?"),
    _q("dunia_game", 9, "Kalau {subject} punya skill pasif, kemampuan receh apa yang paling cocok?"),
    _q("dunia_game", 10, "Kalau ada quest harian untuk {subject}, tugas paling khasnya apa?"),

    # superhero
    _q("superhero", 1, "Kalau {subject} menjadi superhero, nama hero-nya apa?"),
    _q("superhero", 2, "Musuh utama superhero {subject} kira-kira siapa atau apa?"),
    _q("superhero", 3, "Kalau {subject} punya kostum superhero, bagian paling aneh dari kostumnya apa?"),
    _q("superhero", 4, "Kalau kekuatan {subject} cuma aktif saat lapar, kekuatannya apa?"),
    _q("superhero", 5, "Kalau {subject} punya markas superhero, markasnya tersembunyi di mana?"),
    _q("superhero", 6, "Kalau {subject} menyelamatkan dunia, cara paling tidak keren yang mungkin terjadi bagaimana?"),
    _q("superhero", 7, "Kalau {subject} punya sidekick, sidekick seperti apa yang cocok?"),
    _q("superhero", 8, "Kalau kelemahan superhero {subject} adalah hal receh, kelemahannya apa?"),

    # horor_lucu
    _q("horor_lucu", 1, "Kalau {subject} melihat pocong dari jauh, reaksi pertamanya apa?"),
    _q("horor_lucu", 2, "Kalau ada suara misterius dari bawah tempat tidur, apakah {subject} berani mengecek?"),
    _q("horor_lucu", 3, "Kalau hantu muncul lalu minta tolong, apa yang kemungkinan dilakukan {subject}?"),
    _q("horor_lucu", 4, "Kalau {subject} harus tidur semalam di rumah kosong, benda apa yang wajib dibawa?"),
    _q("horor_lucu", 5, "Kalau pintu terbuka sendiri tengah malam, dugaan pertama {subject} apa?"),
    _q("horor_lucu", 6, "Kalau {subject} jadi hantu, orang seperti apa yang paling suka dijahili?"),
    _q("horor_lucu", 7, "Kalau hantu ternyata takut sama {subject}, kenapa kira-kira?"),
    _q("horor_lucu", 8, "Kalau {subject} mendengar namanya dipanggil dari ruangan kosong, apa yang dilakukan?"),

    # nongkrong
    _q("nongkrong", 1, "Kalau menentukan tempat nongkrong, faktor apa yang paling penting bagi {subject}?"),
    _q("nongkrong", 2, "Kalau semua orang bilang 'terserah', apakah {subject} akhirnya yang memilih tempat?"),
    _q("nongkrong", 3, "Saat nongkrong, makanan apa yang kemungkinan paling sering dicomot {subject} dari punya orang?"),
    _q("nongkrong", 4, "Kalau nongkrong sudah terlalu lama, tanda {subject} ingin pulang biasanya seperti apa?"),
    _q("nongkrong", 5, "Kalau ada permainan dadakan saat nongkrong, permainan apa yang kemungkinan paling disukai {subject}?"),
    _q("nongkrong", 6, "Kalau obrolan mulai gosip receh, apakah {subject} jadi pendengar atau ikut menambah cerita?"),
    _q("nongkrong", 7, "Kalau pesanan semua orang datang kecuali punya {subject}, reaksi pertamanya apa?"),
    _q("nongkrong", 8, "Kalau foto bareng harus diulang lima kali, apakah {subject} masih semangat?"),

    # keputusan_receh
    _q("keputusan_receh", 1, "Kalau {subject} harus memilih mandi dulu atau makan dulu saat lapar banget, pilih mana?"),
    _q("keputusan_receh", 2, "Kalau cuma ada dua kursi, dekat colokan atau dekat kipas, {subject} pilih mana?"),
    _q("keputusan_receh", 3, "Kalau {subject} harus memilih nasi goreng atau mie goreng sekarang, pilih apa?"),
    _q("keputusan_receh", 4, "Kalau hujan tapi cuma perlu pergi 100 meter, {subject} bakal pakai payung atau lari?"),
    _q("keputusan_receh", 5, "Kalau alarm berbunyi tapi masih punya waktu 10 menit, apakah {subject} tidur lagi?"),
    _q("keputusan_receh", 6, "Kalau ada dua antrean dengan panjang sama, bagaimana {subject} memilih antrean?"),
    _q("keputusan_receh", 7, "Kalau baterai HP 5% dan cuma ada satu colokan, apa yang paling mungkin dilakukan {subject}?"),
    _q("keputusan_receh", 8, "Kalau makanan datang tapi masih sangat panas, apakah {subject} menunggu atau langsung mencoba?"),
    _q("keputusan_receh", 9, "Kalau {subject} melihat diskon besar untuk barang yang tidak dibutuhkan, beli atau lewat?"),
    _q("keputusan_receh", 10, "Kalau ada jalan dekat tapi macet dan jalan jauh tapi lancar, {subject} pilih yang mana?"),

    # kepribadian_receh
    _q("kepribadian_receh", 1, "Kalau {subject} adalah tombol keyboard, tombol apa yang paling cocok?"),
    _q("kepribadian_receh", 2, "Kalau suasana hati {subject} hari ini jadi makanan, kira-kira makanan apa?"),
    _q("kepribadian_receh", 3, "Kalau tingkat kesabaran {subject} punya baterai, biasanya tersisa berapa persen di akhir hari?"),
    _q("kepribadian_receh", 4, "Kalau {subject} punya warning label, tulisan apa yang cocok di labelnya?"),
    _q("kepribadian_receh", 5, "Kalau {subject} dijual sebagai produk, fitur unggulannya apa?"),
    _q("kepribadian_receh", 6, "Kalau {subject} punya mode hemat energi, seperti apa tingkahnya saat mode itu aktif?"),
    _q("kepribadian_receh", 7, "Kalau {subject} punya indikator mood di atas kepala, paling sering warnanya apa?"),
    _q("kepribadian_receh", 8, "Kalau {subject} punya tombol mute, dalam situasi apa teman-temannya paling ingin menekannya?"),
    _q("kepribadian_receh", 9, "Kalau {subject} punya loading screen, tips apa yang tertulis di layar loading-nya?"),
    _q("kepribadian_receh", 10, "Kalau {subject} punya versi premium, fitur tambahan apa yang didapat?"),

    # skenario_dadakan
    _q("skenario_dadakan", 1, "Kalau {subject} tiba-tiba disuruh menyanyi di depan semua orang, apa yang dilakukan?"),
    _q("skenario_dadakan", 2, "Kalau {subject} mendadak ditunjuk jadi ketua kelompok, langkah pertama yang dilakukan apa?"),
    _q("skenario_dadakan", 3, "Kalau {subject} diberi mikrofon tanpa penjelasan, kalimat pertama yang mungkin diucapkan apa?"),
    _q("skenario_dadakan", 4, "Kalau {subject} mendadak punya waktu kosong tiga jam, bakal dipakai buat apa?"),
    _q("skenario_dadakan", 5, "Kalau ada yang memberikan {subject} ayam hidup secara tiba-tiba, apa yang bakal dilakukan?"),
    _q("skenario_dadakan", 6, "Kalau {subject} tiba-tiba harus menjaga anak kecil satu jam, kegiatan apa yang bakal dilakukan?"),
    _q("skenario_dadakan", 7, "Kalau {subject} tiba-tiba diminta memasak untuk sepuluh orang, menu apa yang dipilih?"),
    _q("skenario_dadakan", 8, "Kalau {subject} tiba-tiba muncul di panggung konser, apa yang bakal dilakukan?"),
    _q("skenario_dadakan", 9, "Kalau {subject} menemukan kursi kosong VIP di sebuah acara, apakah berani duduk?"),
    _q("skenario_dadakan", 10, "Kalau {subject} tiba-tiba harus menjaga toko sendirian, hal pertama yang dilakukan apa?"),

    # dunia_aneh
    _q("dunia_aneh", 1, "Kalau dunia menggunakan mie sebagai mata uang, apakah {subject} bakal jadi kaya atau miskin?"),
    _q("dunia_aneh", 2, "Kalau manusia harus tidur berdiri, bagaimana cara {subject} membuatnya nyaman?"),
    _q("dunia_aneh", 3, "Kalau semua kendaraan diganti hewan, hewan apa yang kemungkinan dipakai {subject}?"),
    _q("dunia_aneh", 4, "Kalau setiap orang wajib memakai topi aneh, topi seperti apa yang dipilih {subject}?"),
    _q("dunia_aneh", 5, "Kalau manusia cuma boleh bicara tiga kata per hari, tiga kata apa yang mungkin paling sering dipakai {subject}?"),
    _q("dunia_aneh", 6, "Kalau setiap rumah wajib punya perosotan, dari ruangan mana perosotan rumah {subject} dimulai?"),
    _q("dunia_aneh", 7, "Kalau semua orang punya musik latar otomatis, musik {subject} terdengar seperti apa?"),
    _q("dunia_aneh", 8, "Kalau umur manusia ditentukan dari jumlah cemilan yang dimakan, apakah {subject} bakal hidup lama?"),
    _q("dunia_aneh", 9, "Kalau setiap kebohongan membuat rambut berubah warna, seberapa warna-warni rambut {subject}?"),
    _q("dunia_aneh", 10, "Kalau semua pekerjaan diganti dengan permainan, permainan apa yang ingin dijadikan pekerjaan oleh {subject}?"),

    # pengetahuan_tentang_subject
    _q("pengetahuan_tentang_subject", 1, "Apa hal yang kemungkinan bisa membuat {subject} lupa waktu?"),
    _q("pengetahuan_tentang_subject", 2, "Apa sesuatu yang kemungkinan langsung membuat mood {subject} membaik?"),
    _q("pengetahuan_tentang_subject", 3, "Hal apa yang paling mungkin membuat {subject} berkata 'malas banget'?"),
    _q("pengetahuan_tentang_subject", 4, "Kalau diberi satu hari bebas, kegiatan apa yang kemungkinan paling dipilih {subject}?"),
    _q("pengetahuan_tentang_subject", 5, "Hal receh apa yang kemungkinan paling gampang membuat {subject} kesal?"),
    _q("pengetahuan_tentang_subject", 6, "Apa yang paling mungkin dicari {subject} saat sedang bad mood?"),
    _q("pengetahuan_tentang_subject", 7, "Dalam kondisi apa {subject} paling mungkin menjadi sangat cerewet?"),
    _q("pengetahuan_tentang_subject", 8, "Dalam kondisi apa {subject} biasanya jadi paling pendiam?"),
    _q("pengetahuan_tentang_subject", 9, "Apa yang kemungkinan langsung membuat {subject} tertarik ikut suatu kegiatan?"),
    _q("pengetahuan_tentang_subject", 10, "Apa hal yang orang baru mungkin salah tebak tentang {subject}?"),
    _q("pengetahuan_tentang_subject", 11, "Apa kemampuan kecil yang kemungkinan sebenarnya cukup jago dilakukan {subject}?"),
    _q("pengetahuan_tentang_subject", 12, "Kalau harus mendeskripsikan {subject} lewat satu benda, benda apa yang paling cocok?"),

    # reaksi
    _q("reaksi", 1, "Apa reaksi pertama {subject} kalau tiba-tiba mendapat uang gratis?"),
    _q("reaksi", 2, "Apa reaksi pertama {subject} kalau bangun dan ternyata sudah kesiangan?"),
    _q("reaksi", 3, "Apa reaksi pertama {subject} kalau namanya disebut padahal sedang melamun?"),
    _q("reaksi", 4, "Apa reaksi pertama {subject} kalau pesanan makanannya salah?"),
    _q("reaksi", 5, "Apa reaksi pertama {subject} kalau menemukan kecoa di dekat kakinya?"),
    _q("reaksi", 6, "Apa reaksi pertama {subject} kalau melihat temannya melakukan hal sangat memalukan?"),
    _q("reaksi", 7, "Apa reaksi pertama {subject} kalau menang sesuatu yang tidak disangka-sangka?"),
    _q("reaksi", 8, "Apa reaksi pertama {subject} kalau internet tiba-tiba mati saat sedang dipakai?"),
    _q("reaksi", 9, "Apa reaksi pertama {subject} kalau seseorang membatalkan janji di menit terakhir?"),
    _q("reaksi", 10, "Apa reaksi pertama {subject} kalau tiba-tiba ada kamera diarahkan kepadanya?"),
    _q("reaksi", 11, "Apa reaksi pertama {subject} kalau salah masuk kendaraan?"),
    _q("reaksi", 12, "Apa reaksi pertama {subject} kalau mengetahui besok mendadak libur?"),

    # siapa_subject
    _q("siapa_subject", 1, "Kalau {subject} menjadi karakter dalam kelompok perampok di film, perannya apa?"),
    _q("siapa_subject", 2, "Kalau {subject} menjadi anggota kru kapal bajak laut, tugasnya apa?"),
    _q("siapa_subject", 3, "Kalau {subject} masuk kelompok petualang, barang apa yang kemungkinan dia bawa?"),
    _q("siapa_subject", 4, "Kalau {subject} tinggal di kerajaan, pekerjaan apa yang cocok untuknya?"),
    _q("siapa_subject", 5, "Kalau {subject} menjadi karakter sitkom, lelucon khas tentang dirinya apa?"),
    _q("siapa_subject", 6, "Kalau {subject} menjadi karakter film horor, apakah dia bertahan sampai akhir? Kenapa?"),
    _q("siapa_subject", 7, "Kalau {subject} masuk tim pencuri profesional di film, kemampuan spesialnya apa?"),
    _q("siapa_subject", 8, "Kalau {subject} menjadi karakter anime, ciri khas yang langsung dikenali apa?"),
    _q("siapa_subject", 9, "Kalau {subject} menjadi maskot sebuah tim, bentuk maskotnya seperti apa?"),
    _q("siapa_subject", 10, "Kalau {subject} menjadi karakter dalam board game, kemampuan uniknya apa?"),

    # pertanyaan_super_receh
    _q("super_receh", 1, "Kalau ada dua bantal, {subject} lebih mungkin memakai satu atau dua-duanya?"),
    _q("super_receh", 2, "Kalau makan kerupuk, {subject} lebih mungkin menggigit sedikit-sedikit atau langsung besar?"),
    _q("super_receh", 3, "Kalau melihat kursi berputar, apakah {subject} bakal memutarnya?"),
    _q("super_receh", 4, "Kalau ada bubble wrap, apakah {subject} bakal memencetnya?"),
    _q("super_receh", 5, "Kalau ada tombol lift yang sudah menyala, apakah {subject} tetap menekannya lagi?"),
    _q("super_receh", 6, "Kalau ada tulisan 'cat basah', apakah {subject} tergoda menyentuhnya untuk memastikan?"),
    _q("super_receh", 7, "Kalau melewati cermin besar, apakah {subject} otomatis melihat dirinya sendiri?"),
    _q("super_receh", 8, "Kalau ada kursi paling empuk di ruangan, seberapa cepat {subject} mengambilnya?"),
    _q("super_receh", 9, "Kalau makanan teman terlihat lebih enak, apakah {subject} bakal minta satu?"),
    _q("super_receh", 10, "Kalau {subject} menemukan pulpen yang enak dipakai, seberapa besar kemungkinan pulpen itu jadi favorit?"),
    _q("super_receh", 11, "Kalau ada kucing lewat saat {subject} sedang ngobrol serius, apakah perhatiannya bakal teralihkan?"),
    _q("super_receh", 12, "Kalau {subject} melihat benda dengan tulisan 'jangan disentuh', apakah justru makin penasaran?"),

    
]

_BY_ID: dict[str, Question] = {q.id: q for q in QUESTIONS}


def get_question(question_id: str) -> Question:
    return _BY_ID[question_id]


def validate_question_bank() -> None:
    ids = [q.id for q in QUESTIONS]
    if len(ids) != len(set(ids)):
        raise ValueError("Ada question_id duplikat di bank pertanyaan")
    for question in QUESTIONS:
        if not question.text.strip():
            raise ValueError(f"Pertanyaan {question.id} kosong")
        if question.category not in CATEGORIES:
            raise ValueError(f"Kategori tidak dikenal: {question.category} ({question.id})")


def draw_question_options(
    *,
    used_question_ids: set[str] | list[str],
    count: int,
    rng: random.Random | None = None,
) -> list[str]:
    """Ambil `count` pertanyaan yang belum dipakai, mengusahakan variasi
    kategori lewat round-robin antar kategori. Deterministik kalau diberi
    `rng` (`random.Random` ber-seed) -- dipakai test."""
    generator = rng or random
    used = set(used_question_ids)
    available = [q for q in QUESTIONS if q.id not in used]
    if len(available) < count:
        # Stok kurang -- longgarkan (izinkan pertanyaan lama muncul lagi)
        # daripada gagal total. Seharusnya jarang terjadi kalau bank cukup
        # besar relatif jumlah giliran dalam satu sesi.
        available = list(QUESTIONS)

    by_category: dict[str, list[Question]] = {}
    for question in available:
        by_category.setdefault(question.category, []).append(question)

    categories = list(by_category.keys())
    generator.shuffle(categories)
    for bucket in by_category.values():
        generator.shuffle(bucket)

    selected: list[Question] = []
    while len(selected) < count and any(by_category.values()):
        for category in categories:
            if len(selected) >= count:
                break
            bucket = by_category.get(category)
            if bucket:
                selected.append(bucket.pop())

    return [question.id for question in selected[:count]]
