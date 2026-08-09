# StandarisasiAtribut

Aplikasi Streamlit untuk validasi data spasial IGT P4T (Informasi Geospasial Tematik
Penatagunaan dan Penguasaan Tanah) terhadap ruleset atribut standar.

> Bukan orang teknis / baru pertama kali pakai? Lihat **[CARA_PAKAI.md](CARA_PAKAI.md)**
> untuk panduan menjalankan aplikasi cukup dengan 1 perintah.

## Struktur Proyek

```
data/               Input data spasial (DBF/SHP/CSV) yang akan divalidasi
rules/active/       Ruleset yang sedang dipakai, satu file CSV per kategori IGT
rules/archive/      Arsip riwayat upload ruleset, bertimestamp
app/                Logika utama aplikasi (Streamlit)
  Home.py           Halaman utama
  pages/            Halaman-halaman tambahan (mis. Kelola Aturan)
  core/             Modul logika (io_utils, rules_manager)
output/             Hasil laporan validasi
```

## Menjalankan Aplikasi

Cara cepat (install dependency + jalankan sekaligus):

```bash
./run.sh          # Mac/Linux
run.bat           # Windows (klik dua kali, atau jalankan dari Command Prompt)
```

Atau manual:

```bash
pip install -r requirements.txt
streamlit run app/Home.py
```

## Halaman Kelola Aturan

Halaman `Kelola Aturan` (di sidebar) memungkinkan:

1. Mengunduh template Excel kosong (kolom: `Kategori_IGT`, `Nama_Atribut`, `Nilai_Valid`).
2. Mengunggah file Excel ruleset baru.
3. Validasi otomatis kolom file terhadap template — file ditolak dengan pesan error
   yang jelas jika tidak sesuai.
4. Jika valid, file diarsipkan (bertimestamp) ke `rules/archive/`, lalu `rules/active/`
   diperbarui hanya untuk kategori yang ada di file tersebut — kategori lain tidak berubah.
5. Menampilkan tabel ringkasan aturan aktif per kategori beserta tanggal terakhir diupdate.
