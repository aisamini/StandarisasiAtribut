# StandarisasiAtribut

Aplikasi Streamlit untuk validasi data spasial IGT P4T (Informasi Geospasial Tematik
Penatagunaan dan Penguasaan Tanah) terhadap ruleset atribut standar per IGT. Nama
kolom ruleset memakai nama asli sesuai **Permen ATR No. 1 Tahun 2025** (bukan skema
generik) karena langsung dipakai pengolah data.

> Bukan orang teknis / baru pertama kali pakai? Lihat **[CARA_PAKAI.md](CARA_PAKAI.md)**
> untuk panduan menjalankan aplikasi cukup dengan 1 perintah.

## Konsep Kolom IGT

Setiap IGT (mis. Penggunaan Tanah, prefix `ptn`) punya 8 kolom baku: nama kategori +
kode untuk masing-masing 4 level (KC=Kecil, MN=Menengah, BS=Besar, RI=Rinci), contoh:
`ptnObjKC`, `idptnObjKC`, `ptnObjMN`, `idptnObjMN`, dst. Daftar IGT dan prefix-nya
dikonfigurasi di `rules/igt_config.json` dan bisa ditambah lewat UI (halaman
**Kelola Aturan** → "+ Tambah IGT Baru") tanpa mengubah kode.

## Struktur Proyek

```
data/               Input data spasial (DBF/SHP/CSV) yang akan divalidasi
rules/igt_config.json  Daftar IGT (nama + prefix kolom) — sumber kebenaran validasi
rules/active/       Ruleset yang sedang dipakai, satu file CSV per IGT (4 level sekaligus)
rules/archive/      Arsip riwayat upload ruleset, bertimestamp
app/                Logika utama aplikasi (Streamlit)
  Home.py           Halaman utama
  pages/            Halaman-halaman tambahan (mis. Kelola Aturan)
  core/             Modul logika (io_utils, igt_config, rules_manager, validator)
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

1. Memilih IGT dari daftar terkonfigurasi, atau menambah IGT baru (nama + prefix kolom).
2. Mengunduh template Excel khusus IGT yang dipilih (8 kolom sesuai prefix-nya, plus 1 baris contoh).
3. Mengunggah ruleset lengkap (4 level sekaligus) untuk IGT tersebut — validasi otomatis
   memastikan 8 kolom persis sesuai (case-sensitive), file ditolak dengan pesan error jelas
   jika tidak sesuai.
4. Jika valid, file diarsipkan (bertimestamp + nama IGT) ke `rules/archive/`, lalu ruleset
   aktif IGT itu **digantikan seluruhnya** (IGT lain tidak berubah).
5. Menampilkan tabel ringkasan ruleset per IGT: status ada/belum, jumlah baris per level,
   dan tanggal terakhir diupdate.

## Validasi Data & Koreksi

Data spasial P4T di lapangan hanya punya kolom level **Rinci** per IGT (mis.
`PTNOBJRI`, sering seluruhnya huruf besar) — jadi validasi hanya mencocokkan kolom itu
ke daftar nilai valid `[prefix]ObjRI` di ruleset IGT terkait (perbandingan nama kolom
case-insensitive). Kolom Besar/Menengah/Kecil di ruleset tetap tersimpan untuk
referensi tapi tidak dipakai untuk pencocokan otomatis ini.

Banyak file data bisa digabung jadi satu dataset sebelum divalidasi — halaman
**Home** otomatis menggabungkan semua file di `data/`, atau unggah banyak file
sekaligus lewat halaman **Validasi Data**. Kolom `SUMBER_FILE` menandai file asal
tiap baris untuk pelacakan.

Tiap nilai salah diklasifikasikan **Salah Total** (kosong/dummy/kata kunci error/teks
< 3 karakter) atau **Typo** (kemungkinan cuma salah ketik). Kandidat koreksi
(rapidfuzz, top-5) dihitung sekali per nilai unik yang salah, bukan per baris. Laporan
Excel berisi 2 sheet: `Ringkasan_Validasi` (statistik per kolom) dan
`Perlu_Koreksi_Manual` (khusus baris Salah Total).

Halaman **Koreksi Data** menampilkan satu baris per nilai unik yang salah (bukan per
record) — satu koreksi berlaku untuk semua baris yang punya nilai itu, di semua file
sumbernya, dan input manual selalu diutamakan di atas pilihan dropdown kalau diisi.
Setelah koreksi diterapkan, halaman menampilkan ringkasan verifikasi ulang per kolom.
