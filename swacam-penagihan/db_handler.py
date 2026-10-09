import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Date, Text, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
from config import DATABASE_URL, AUTH_DATABASE_URL

# Base = tabel KHUSUS penagihan (DATABASE_URL). AuthBase = tabel bersama dengan Catat Meter (AUTH_DATABASE_URL).
Base = declarative_base()
AuthBase = declarative_base()

class UserAccount(AuthBase):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)
    role = Column(String(30), default='petugas')
    full_name = Column(String(100), nullable=True)
    phone_number = Column(String(20), nullable=True)
    foto_profil = Column(String(255), nullable=True)
    status = Column(String(20), default='pending')
    reset_requested = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.now)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "full_name": self.full_name,
            "phone_number": self.phone_number,
            "foto_profil": self.foto_profil,
            "status": self.status,
            "reset_requested": bool(self.reset_requested),
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None
        }

class AuditLog(AuthBase):
    __tablename__ = 'audit_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.datetime.now)
    username = Column(String(50), nullable=False)
    role = Column(String(30), nullable=False)
    action = Column(String(100), nullable=False)
    details = Column(Text, nullable=True)
    ip_address = Column(String(50), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M:%S") if self.timestamp else None,
            "username": self.username,
            "role": self.role,
            "action": self.action,
            "details": self.details,
            "ip_address": self.ip_address
        }


class TunggakanPelanggan(Base):
    """Data pelanggan menunggak hasil baca file Excel (untuk pengiriman WA manual via Fonnte)."""
    __tablename__ = 'tunggakan_pelanggan'

    id = Column(Integer, primary_key=True, autoincrement=True)
    id_pelanggan = Column(String(50), nullable=False, index=True)
    nama = Column(String(150), nullable=True)
    no_hp = Column(String(30), nullable=True)
    alamat = Column(String(255), nullable=True)
    periode = Column(String(30), nullable=True)
    nominal = Column(Float, nullable=True)
    jatuh_tempo = Column(Date, nullable=True)
    wa_status = Column(String(20), default='BELUM')   # BELUM | TERKIRIM | GAGAL
    wa_waktu = Column(DateTime, nullable=True)
    wa_respon = Column(String(255), nullable=True)
    wa_jumlah_kirim = Column(Integer, default=0)
    lunas_pada = Column(DateTime, nullable=True)   # kapan data ini pertama kali terbaca LUNAS (untuk analitik efektivitas template)
    sumber_file = Column(String(150), nullable=True)   # nama file upload terakhir yang memuat data ini
    status_bayar = Column(String(10), default='BELUM')   # BELUM | LUNAS (data lunas ikut disimpan agar seluruh isi file tampil)
    diupload_oleh = Column(String(50), nullable=True)
    diupload_pada = Column(DateTime, default=datetime.datetime.now)

    def to_dict(self):
        hari, sisa, kategori = None, None, "MENUNGGAK"
        lunas = (self.status_bayar or "BELUM") == "LUNAS"
        if lunas:
            kategori = "LUNAS"
        elif self.jatuh_tempo:
            selisih = (datetime.date.today() - self.jatuh_tempo).days
            if selisih > 0:
                hari = selisih
            else:
                kategori, sisa = "BELUM_JATUH_TEMPO", -selisih + 1
        return {
            "id": self.id,
            "id_pelanggan": self.id_pelanggan,
            "nama": self.nama,
            "no_hp": self.no_hp,
            "alamat": self.alamat,
            "periode": self.periode,
            "nominal": self.nominal,
            "jatuh_tempo": self.jatuh_tempo.strftime("%Y-%m-%d") if self.jatuh_tempo else None,
            "hari_terlambat": hari,
            "sisa_hari": sisa,
            "kategori": kategori,
            "status_bayar": "LUNAS" if lunas else "BELUM",
            "wa_status": self.wa_status or "BELUM",
            "wa_waktu": self.wa_waktu.strftime("%Y-%m-%d %H:%M:%S") if self.wa_waktu else None,
            "wa_respon": self.wa_respon,
            "wa_jumlah_kirim": self.wa_jumlah_kirim or 0,
            "sumber_file": self.sumber_file,
            "lunas_pada": self.lunas_pada.strftime("%Y-%m-%d %H:%M:%S") if self.lunas_pada else None,
            "diupload_oleh": self.diupload_oleh,
            "diupload_pada": self.diupload_pada.strftime("%Y-%m-%d %H:%M:%S") if self.diupload_pada else None,
        }


# pool_pre_ping: tes koneksi sebelum dipakai (hindari error 2013 'Lost connection' karena koneksi basi)
# pool_recycle: buang koneksi lama tiap 5 menit supaya tidak diputus MySQL
engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True, pool_recycle=300)
SessionLocal = sessionmaker(bind=engine)

# Koneksi ke database Catat Meter (swacam_db): hanya untuk users & audit_logs
auth_engine = create_engine(AUTH_DATABASE_URL, echo=False, pool_pre_ping=True, pool_recycle=300)
AuthSessionLocal = sessionmaker(bind=auth_engine)

def _ensure_database(url: str):
    """Buat database MySQL-nya bila belum ada (supaya tidak error 'Unknown database')."""
    from sqlalchemy.engine import make_url
    u = make_url(url)
    nama = u.database
    if not nama:
        return
    try:
        tmp = create_engine(u.set(database=None))
        with tmp.connect() as c:
            c.execute(__import__("sqlalchemy").text(
                f"CREATE DATABASE IF NOT EXISTS `{nama}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
            c.commit()
        tmp.dispose()
    except Exception as e:
        print(f"[DB] Tidak bisa memastikan database '{nama}' ada: {e}")

def init_db():
    """Membuat tabel database jika belum ada, dan migrasi kolom baru jika diperlukan."""
    _ensure_database(DATABASE_URL)
    Base.metadata.create_all(bind=engine)          # tabel penagihan -> swacam_penagihan_db
    AuthBase.metadata.create_all(bind=auth_engine) # users & audit_logs -> swacam_db (dibuat hanya bila belum ada)
    _migrate_missing_columns()
    try:
        _migrate_modul_wa()
    except Exception as e:
        print(f"[DB MIGRATION] modul WA dilewati: {e}")
    seed_default_users()

def _hash_pw(password: str) -> str:
    import hashlib
    return hashlib.sha256(f"PLN_SWACAM_SALT_2024{password}".encode()).hexdigest()

def seed_default_users():
    """Pastikan akun bawaan (admin, petugas) ADA di tabel users, jadi profil admin
    juga tersimpan di database (bukan di dictionary memori yang hilang saat restart)."""
    defaults = [
        ("admin", "admin123", "admin", "Administrator PLN"),
        ("petugas", "petugas123", "petugas", "Petugas Pencatat Meter"),
    ]
    session = AuthSessionLocal()
    try:
        for uname, pw, role, name in defaults:
            if not session.query(UserAccount).filter(UserAccount.username == uname).first():
                session.add(UserAccount(username=uname, password=_hash_pw(pw), role=role,
                                        full_name=name, status="approved"))
                print(f"[DB SEED] Akun bawaan '{uname}' dibuat di tabel users.")
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"[DB SEED ERROR] {e}")
    finally:
        session.close()

def ensure_user_row(u: dict) -> bool:
    """Jika akun (mis. admin/petugas bawaan) belum ada di tabel users, buatkan barisnya
    supaya update profil selalu tersimpan di database."""
    session = AuthSessionLocal()
    try:
        if session.query(UserAccount).filter(UserAccount.username == u["username"].lower()).first():
            return True
        session.add(UserAccount(username=u["username"].lower(), password=u["password"],
                                role=u.get("role", "petugas"), full_name=u.get("full_name"),
                                phone_number=u.get("phone_number"), foto_profil=u.get("foto_profil"),
                                status="approved"))
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        print(f"[DB ensure_user_row ERROR] {e}")
        return False
    finally:
        session.close()
def update_user_basic_profile(old_username: str, new_username: str, full_name: str) -> bool:
    session = AuthSessionLocal()
    try:
        user = session.query(UserAccount).filter(UserAccount.username == old_username).first()
        if not user: return False
        
        # Cek jika username baru sudah ada dan bukan milik user ini
        if new_username.lower() != old_username.lower():
            cek = session.query(UserAccount).filter(UserAccount.username == new_username.lower()).first()
            if cek: raise ValueError("Username sudah digunakan")
            user.username = new_username.lower()
            
        user.full_name = full_name
        session.commit()
        return True
    except ValueError as e:
        raise
    except Exception:
        session.rollback()
        return False
    finally:
        session.close()


def update_user_password(username: str, new_password: str) -> bool:
    session = AuthSessionLocal()
    try:
        user = session.query(UserAccount).filter(UserAccount.username == username.lower()).first()
        if not user:
            return False
        user.password = _hash_pw(new_password)
        session.commit()
        return True
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def _migrate_missing_columns():
    """Menambahkan kolom baru ke tabel lama (mis. latitude/longitude) tanpa menghapus data yang sudah ada."""
    from sqlalchemy import inspect, text

    inspector = inspect(auth_engine)

    # Migrasi tabel users (mis. reset_requested untuk fitur Lupa Password)
    if "users" in inspector.get_table_names():
        existing_user_columns = {col["name"] for col in inspector.get_columns("users")}
        expected_user_columns = {"reset_requested": "BOOLEAN DEFAULT 0", "phone_number": "VARCHAR(20)", "foto_profil": "VARCHAR(255)"}
        with auth_engine.connect() as conn:
            for col_name, col_type in expected_user_columns.items():
                if col_name not in existing_user_columns:
                    try:
                        conn.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}"))
                        conn.commit()
                        print(f"[DB MIGRATION] Kolom '{col_name}' berhasil ditambahkan ke tabel users.")
                    except Exception as e:
                        conn.rollback()
                        print(f"[DB MIGRATION ERROR] Gagal menambah kolom users.{col_name}: {e}. "
                              f"Jalankan manual: ALTER TABLE users ADD COLUMN {col_name} {col_type};")

def _migrate_modul_wa():
    """Kolom tambahan modul tunggakan/WA: status_bayar (data lunas ikut tampil) dan nama di riwayat WA
    (supaya nama tidak hilang saat daftar tunggakan diganti oleh upload baru)."""
    from sqlalchemy import inspect, text
    import re
    insp = inspect(engine)
    tabel = set(insp.get_table_names())
    with engine.connect() as conn:
        if "tunggakan_pelanggan" in tabel:
            kol = {c["name"] for c in insp.get_columns("tunggakan_pelanggan")}
            if "lunas_pada" not in kol:
                try:
                    conn.execute(text("ALTER TABLE tunggakan_pelanggan ADD COLUMN lunas_pada DATETIME NULL"))
                    conn.execute(text("UPDATE tunggakan_pelanggan SET lunas_pada=COALESCE(diupload_pada, NOW()) "
                                      "WHERE status_bayar='LUNAS' AND lunas_pada IS NULL"))
                    conn.commit()
                    print("[DB MIGRATION] Kolom 'lunas_pada' ditambahkan ke tunggakan_pelanggan.")
                except Exception as e:
                    conn.rollback()
                    print(f"[DB MIGRATION ERROR] tunggakan_pelanggan.lunas_pada: {e}")
            if "sumber_file" not in kol:
                try:
                    conn.execute(text("ALTER TABLE tunggakan_pelanggan ADD COLUMN sumber_file VARCHAR(150) NULL"))
                    conn.commit()
                    print("[DB MIGRATION] Kolom 'sumber_file' ditambahkan ke tunggakan_pelanggan.")
                except Exception as e:
                    conn.rollback()
                    print(f"[DB MIGRATION ERROR] tunggakan_pelanggan.sumber_file: {e}")
            if "status_bayar" not in kol:
                try:
                    conn.execute(text("ALTER TABLE tunggakan_pelanggan ADD COLUMN status_bayar VARCHAR(10) NOT NULL DEFAULT 'BELUM'"))
                    conn.commit()
                    print("[DB MIGRATION] Kolom 'status_bayar' ditambahkan ke tunggakan_pelanggan.")
                except Exception as e:
                    conn.rollback()
                    print(f"[DB MIGRATION ERROR] tunggakan_pelanggan.status_bayar: {e}")
        if "wa_riwayat" in tabel:
            kol = {c["name"] for c in insp.get_columns("wa_riwayat")}
            if "nama" not in kol:
                try:
                    conn.execute(text("ALTER TABLE wa_riwayat ADD COLUMN nama VARCHAR(150) NULL AFTER id_pelanggan"))
                    conn.commit()
                    print("[DB MIGRATION] Kolom 'nama' ditambahkan ke wa_riwayat.")
                except Exception as e:
                    conn.rollback()
                    print(f"[DB MIGRATION ERROR] wa_riwayat.nama: {e}")
                    return
            # isi nama untuk riwayat lama: dari daftar tunggakan, lalu dari teks pesan ("Bapak/Ibu <Nama>.")
            try:
                conn.execute(text("UPDATE wa_riwayat r JOIN tunggakan_pelanggan t ON t.id_pelanggan=r.id_pelanggan "
                                  "SET r.nama=t.nama WHERE (r.nama IS NULL OR r.nama='') AND t.nama IS NOT NULL AND t.nama<>''"))
                conn.commit()
                sisa = conn.execute(text("SELECT id, pesan FROM wa_riwayat WHERE (nama IS NULL OR nama='') AND pesan IS NOT NULL")).fetchall()
                for rid, pesan in sisa:
                    m = re.search(r"Bapak/Ibu\s+(.+?)[.,:\n]", pesan or "")
                    if m and m.group(1).strip().lower() != "pelanggan":
                        conn.execute(text("UPDATE wa_riwayat SET nama=:n WHERE id=:i"), {"n": m.group(1).strip()[:150], "i": rid})
                conn.commit()
            except Exception as e:
                conn.rollback()
                print(f"[DB MIGRATION] isi nama riwayat dilewati: {e}")


def log_activity(username: str, role: str, action: str, details: str = None, ip_address: str = None):
    """Mencatat aktivitas pengguna ke tabel audit_logs."""
    session = AuthSessionLocal()
    try:
        log_entry = AuditLog(
            username=username,
            role=role,
            action=action,
            details=details,
            ip_address=ip_address
        )
        session.add(log_entry)
        session.commit()
        return log_entry
    except Exception as e:
        session.rollback()
        print(f"[AUDIT LOG ERROR] {e}")
    finally:
        session.close()

def get_all_audit_logs(limit: int = 100):
    """Mengambil log aktivitas terbaru."""
    session = AuthSessionLocal()
    try:
        logs = session.query(AuditLog).order_by(AuditLog.id.desc()).limit(limit).all()
        return [l.to_dict() for l in logs]
    finally:
        session.close()

def get_user_by_username(username: str):
    """Mengambil akun pegawai dari database berdasarkan username."""
    session = AuthSessionLocal()
    try:
        user = session.query(UserAccount).filter(UserAccount.username == username.lower()).first()
        if user:
            return {
                "id": user.id,
                "username": user.username,
                "password": user.password,
                "role": user.role,
                "full_name": user.full_name,
                "status": user.status,
                "phone_number": user.phone_number,
                "foto_profil": user.foto_profil
            }
        return None
    finally:
        session.close()

def update_user_phone(username: str, phone_number: str):
    """Update nomor WA milik SATU akun saja (dicari berdasarkan username miliknya sendiri),
    supaya perubahan akun A tidak pernah menimpa data akun B."""
    session = AuthSessionLocal()
    try:
        user = session.query(UserAccount).filter(UserAccount.username == username.lower()).first()
        if not user:
            return False
        user.phone_number = phone_number
        session.commit()
        return True
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def update_user_photo(username: str, foto_profil: str):
    """Update foto profil milik SATU akun saja (dicari berdasarkan username miliknya sendiri)."""
    session = AuthSessionLocal()
    try:
        user = session.query(UserAccount).filter(UserAccount.username == username.lower()).first()
        if not user:
            return False
        user.foto_profil = foto_profil
        session.commit()
        return True
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def register_new_user(username: str, password: str, full_name: str, phone_number: str = None, role: str = "petugas"):
    """Daftar pegawai baru ke database (password di-hash sebelum disimpan)."""
    import hashlib
    session = AuthSessionLocal()
    try:
        existing = session.query(UserAccount).filter(UserAccount.username == username.lower()).first()
        if existing:
            return None, "Username sudah terdaftar!"
        
        # Hash password sebelum disimpan
        salt = "PLN_SWACAM_SALT_2024"
        hashed_password = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
        
        new_user = UserAccount(
            username=username.lower(),
            password=hashed_password,
            full_name=full_name,
            phone_number=phone_number,
            role=role
        )
        session.add(new_user)
        session.commit()
        session.refresh(new_user)
        return new_user, "Berhasil"
    except Exception as e:
        session.rollback()
        return None, str(e)
    finally:
        session.close()

def request_password_reset(username: str, full_name: str):
    """Menandai akun untuk diminta reset password oleh Admin.
    Identitas dicek sederhana (username + nama lengkap harus cocok) agar
    tidak sembarang orang bisa memicu permintaan reset akun orang lain."""
    session = AuthSessionLocal()
    try:
        user = session.query(UserAccount).filter(UserAccount.username == username.lower().strip()).first()
        if not user:
            return False, "Username tidak ditemukan."
        if (user.full_name or "").strip().lower() != (full_name or "").strip().lower():
            return False, "Nama lengkap tidak cocok dengan data akun."
        user.reset_requested = True
        session.commit()
        return True, "Permintaan reset password terkirim. Tunggu persetujuan Admin."
    except Exception as e:
        session.rollback()
        return False, str(e)
    finally:
        session.close()

def admin_reset_password(user_id: int, new_password: str):
    """Admin mengatur ulang password pengguna secara langsung."""
    import hashlib
    session = AuthSessionLocal()
    try:
        user = session.query(UserAccount).filter(UserAccount.id == user_id).first()
        if not user:
            return False, "User tidak ditemukan."
        salt = "PLN_SWACAM_SALT_2024"
        user.password = hashlib.sha256(f"{salt}{new_password}".encode()).hexdigest()
        user.reset_requested = False
        session.commit()
        return True, user.username
    except Exception as e:
        session.rollback()
        return False, str(e)
    finally:
        session.close()

def get_all_users():
    """Mengambil seluruh data akun pengguna (termasuk status approval & permintaan reset password)."""
    session = AuthSessionLocal()
    try:
        users = session.query(UserAccount).order_by(UserAccount.id.desc()).all()
        return [u.to_dict() for u in users]
    finally:
        session.close()

def update_user_status(user_id: int, new_status: str):
    """Admin menyetujui (approve) atau menolak (reject) akun pengguna."""
    session = AuthSessionLocal()
    try:
        user = session.query(UserAccount).filter(UserAccount.id == user_id).first()
        if not user:
            return False, "Pengguna tidak ditemukan."
        user.status = new_status
        session.commit()
        return True, user.username
    except Exception as e:
        session.rollback()
        return False, str(e)
    finally:
        session.close()

def delete_user(user_id: int):
    """Admin menghapus akun pengguna."""
    session = AuthSessionLocal()
    try:
        user = session.query(UserAccount).filter(UserAccount.id == user_id).first()
        if not user:
            return False, "Pengguna tidak ditemukan."
        username = user.username
        session.delete(user)
        session.commit()
        return True, username
    except Exception as e:
        session.rollback()
        return False, str(e)
    finally:
        session.close()