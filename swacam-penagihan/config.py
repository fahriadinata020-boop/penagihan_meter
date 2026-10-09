import os
from pathlib import Path

# Load .env file if available
BASE_DIR = Path(__file__).resolve().parent
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass

# Foto profil dipakai BERSAMA aplikasi Catat Meter (satu tabel users, satu folder avatars).
# Default: folder 'avatars' milik ../swacam-meter. Ubah lewat AVATAR_DIR di .env bila lokasinya beda.
AVATAR_DIR = Path(os.getenv("AVATAR_DIR", BASE_DIR.parent / "swacam-meter" / "avatars"))
AVATAR_DIR.mkdir(parents=True, exist_ok=True)

# Database: DUA database MySQL (satu server), TANPA fallback ke SQLite.
#   DATABASE_URL      -> database KHUSUS Penagihan (tunggakan, antrean/riwayat/template WA, pengaturan)
#   AUTH_DATABASE_URL -> database Catat Meter (swacam_db), hanya untuk tabel users & audit_logs
#                        supaya satu login/akun/foto profil tetap berlaku di kedua aplikasi.
#   DATABASE_URL=mysql+pymysql://root:password@localhost:3306/swacam_penagihan_db
#   AUTH_DATABASE_URL=mysql+pymysql://root:password@localhost:3306/swacam_db
# Railway.app menyediakan MYSQL_URL otomatis (format: mysql://user:pass@host:port/db)
# Konversi ke format pymysql jika perlu
def _fix_mysql_url(url: str) -> str:
    if url and url.startswith("mysql://"):
        url = url.replace("mysql://", "mysql+pymysql://", 1)
    return url

DATABASE_URL = _fix_mysql_url(os.getenv(
    "DATABASE_URL",
    os.getenv("MYSQL_URL", "mysql+pymysql://root:@localhost:3306/swacam_penagihan_db")
))
AUTH_DATABASE_URL = _fix_mysql_url(os.getenv(
    "AUTH_DATABASE_URL",
    os.getenv("MYSQL_URL", DATABASE_URL)  # Di cloud, bisa pakai 1 database saja
))
for _u in (DATABASE_URL, AUTH_DATABASE_URL):
    if _u.startswith("sqlite"):
        raise RuntimeError(
            "Database memakai SQLite. Aplikasi ini harus memakai MySQL, "
            "contoh: mysql+pymysql://root:@localhost:3306/swacam_penagihan_db"
        )
print(f"[CONFIG] Database penagihan : {DATABASE_URL.split('@')[-1]}")
print(f"[CONFIG] Database login/user: {AUTH_DATABASE_URL.split('@')[-1]}")
