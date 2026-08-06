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
