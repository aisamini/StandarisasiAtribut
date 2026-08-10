# Klasifikasi Resmi Bawaan

Taruh file Excel klasifikasi resmi (Juknis/Permen) di sini, satu subfolder per IGT.
Folder untuk 4 IGT bawaan sudah dibuat:

```
rules/presets/Penggunaan_Tanah/
rules/presets/Pemanfaatan_Tanah/
rules/presets/Pemilikan_Tanah/
rules/presets/Penguasaan_Tanah/
```

- Format file: `.xlsx`, 1 kolom sesuai IGT-nya (mis. `PTNOBJRI` untuk Penggunaan
  Tanah — nama kolom tidak harus persis huruf besar/kecil), berisi daftar nilai valid
  level Rinci. Sama seperti template yang bisa diunduh di tab "Upload Aturan Kustom"
  pada halaman Kelola Aturan.
- Nama file jadi label di dropdown aplikasi (underscore diganti spasi) — pakai nama
  deskriptif & konsisten, mis. `Permen_ATR_No1_2025.xlsx` → tampil sebagai
  "Permen ATR No1 2025".
- Boleh lebih dari satu file per folder (mis. beberapa versi/revisi) — semua akan
  muncul sebagai pilihan terpisah.
- Untuk IGT baru yang ditambahkan lewat aplikasi (tombol "+ Tambah IGT Baru"), buat
  subfolder baru di sini dengan nama sesuai `slugify()` nama IGT tsb (spasi diganti
  underscore) kalau ingin menyediakan preset untuknya juga.

Lihat README.md di root proyek bagian "Klasifikasi Resmi Bawaan" untuk detail lebih
lengkap.
