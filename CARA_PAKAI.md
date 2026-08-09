# Cara Menjalankan Aplikasi

Panduan ini untuk siapa saja yang belum pernah pakai aplikasi ini — tidak perlu paham
coding. Aplikasi ini dipakai untuk mengecek dan membetulkan data atribut IGT P4T.

## Yang Dibutuhkan

- Komputer sudah terpasang **Python** (tanya admin/tim IT kalau belum ada).
- Folder aplikasi ini (`StandarisasiAtribut`) sudah ada di komputer.

## Menjalankan Aplikasi (Cukup 1 Perintah)

**Di Windows:**
Buka folder aplikasi, lalu **klik dua kali file `run.bat`**.

**Di Mac / Linux:**
Buka Terminal di folder aplikasi ini, lalu ketik satu baris ini dan tekan Enter:

```
./run.sh
```

Tunggu sebentar (proses pertama kali bisa agak lama karena menyiapkan aplikasi).
Setelah selesai, browser akan otomatis terbuka dan aplikasi siap dipakai.

Kalau browser tidak terbuka sendiri, buka browser (Chrome/Edge) manual dan buka alamat:
`http://localhost:8501`

## Menghentikan Aplikasi

Kembali ke jendela Terminal/Command Prompt yang tadi muncul, lalu tekan `Ctrl + C`.

## Kalau Ada Masalah

- Muncul tulisan seperti `python: command not found` atau `pip tidak dikenali` →
  Python belum terpasang di komputer ini. Minta bantuan admin/tim IT untuk memasangnya.
- Muncul error lain saat menjalankan → screenshot pesan errornya dan kirim ke tim
  developer untuk dibantu.

## Halaman-Halaman di Aplikasi

- **Home** — ringkasan aturan dan hasil pengecekan data.
- **Kelola Aturan** — upload/atur daftar nilai yang dianggap benar per kategori.
- **Validasi Data** — cek struktur kolom pada file data yang diupload.
- **Koreksi Data** — perbaiki data yang salah lewat pilihan dropdown (tidak perlu ngetik kode).
