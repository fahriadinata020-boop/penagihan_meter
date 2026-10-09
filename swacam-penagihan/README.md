# SWACAM — Aplikasi 2: Penagihan & WhatsApp
Impor tunggakan (Excel), kirim WA lewat Fonnte (antrean + template bertahap), riwayat/webhook WA, analitik & laporan Excel/PDF.

```bash
pip install -r requirements.txt
cp .env.example .env   # isi FONNTE_TOKEN, JWT_SECRET_KEY (sama dengan Catat Meter), DATABASE_URL
uvicorn api:app --port 8001
php -S localhost:8081 -t static
```
Memakai DUA database: `swacam_penagihan_db` (tunggakan, wa_*, pengaturan; impor swacam_penagihan_db.sql) dan `swacam_db` milik Catat Meter (hanya users & audit_logs, untuk login bersama). Detail perubahan modul ada di CATATAN_UPDATE.md.
Dokumentasi API: http://localhost:8001/docs. Lihat ../README.md untuk hubungan dengan aplikasi Catat Meter.
