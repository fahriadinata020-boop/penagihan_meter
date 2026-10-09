# Catatan update modul Tunggakan, WhatsApp, dan Analitik

## Ringkasan perubahan
- Impor Tunggakan: seluruh isi file tampil (menunggak, belum jatuh tempo, lunas), kartu ringkasan bisa diklik untuk menyaring.
- Data disimpan per bulan (kolom Periode / nama file / bulan berjalan). Upload baru digabung, tidak menghapus data lama.
- Opsi "Ganti data bulan ini": hanya bulan yang ada di file yang diganti.
- Hapus data: satu baris, banyak yang dipilih, yang lunas, satu bulan, atau semua. Tercatat di Audit Log.
- Riwayat WA: nama pelanggan tampil (disimpan di wa_riwayat.nama), kartu status bisa diklik, panel detail pesan.
- Menu baru "Analitik & Laporan" (admin): tren per bulan, tingkat baca/balasan, efektivitas template, laporan Excel dan PDF.

## Kolom database baru (dibuat otomatis saat backend start)
- tunggakan_pelanggan.status_bayar, sumber_file, lunas_pada
- wa_riwayat.nama
Jika log menampilkan [DB MIGRATION ERROR], jalankan migrasi_status_bayar_nama.sql secara manual.

## Pasang
1. Salin file .env milik Anda ke folder proyek (file ini sengaja tidak disertakan karena berisi token/password).
2. pip install -r requirements.txt
3. Jalankan seperti biasa (uvicorn api:app ...).
