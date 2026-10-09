import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Date, Text, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
from config import DATABASE_URL

Base = declarative_base()

class SwacamReading(Base):
    __tablename__ = 'swacam_readings'

    id = Column(Integer, primary_key=True, autoincrement=True)
    id_pelanggan = Column(String(50), nullable=True, index=True)
    no_seri_meter = Column(String(50), nullable=True)
    stand_meter = Column(Float, nullable=True)
    stand_meter_raw = Column(String(50), nullable=True)
    waktu_catat = Column(DateTime, default=datetime.datetime.now)
    nama_file_foto = Column(String(255), nullable=False)
    confidence_score = Column(Float, default=0.0)
    uploader_username = Column(String(50), nullable=True)
    status_validasi = Column(String(30), default='SUCCESS')
    link_drive = Column(String(500), nullable=True)
    catatan = Column(Text, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    daya = Column(Integer, nullable=True)
    periode_bulan = Column(String(20), nullable=True) # e.g. "2024-01"
    pemakaian_kwh = Column(Float, nullable=True)
    tagihan_rupiah = Column(Float, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "id_pelanggan": self.id_pelanggan,
            "no_seri_meter": self.no_seri_meter,
            "daya": self.daya,
            "periode_bulan": self.periode_bulan,
            "stand_meter": self.stand_meter,
            "stand_meter_raw": self.stand_meter_raw,
            "pemakaian_kwh": self.pemakaian_kwh,
            "tagihan_rupiah": self.tagihan_rupiah,
            "waktu_catat": self.waktu_catat.strftime("%Y-%m-%d %H:%M:%S") if self.waktu_catat else None,
            "nama_file_foto": self.nama_file_foto,
            "confidence_score": self.confidence_score,
            "status_validasi": self.status_validasi,
            "link_drive": self.link_drive,
            "catatan": self.catatan,
            "latitude": self.latitude,
            "longitude": self.longitude
        }

class UserAccount(Base):
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

class AuditLog(Base):
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


# pool_pre_ping: tes koneksi sebelum dipakai (hindari error 2013 'Lost connection' karena koneksi basi)
# pool_recycle: buang koneksi lama tiap 5 menit supaya tidak diputus MySQL
engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True, pool_recycle=300)
SessionLocal = sessionmaker(bind=engine)

def init_db():
    """Membuat tabel database jika belum ada, dan migrasi kolom baru jika diperlukan."""
    Base.metadata.create_all(bind=engine)
    _migrate_missing_columns()
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
    session = SessionLocal()
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
    session = SessionLocal()
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

def update_user_password(username: str, new_password: str) -> bool:
    session = SessionLocal()
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

    inspector = inspect(engine)
    existing_columns = {col["name"] for col in inspector.get_columns("swacam_readings")}

    expected_columns = {
        "latitude": "FLOAT",
        "longitude": "FLOAT",
        "no_seri_meter": "VARCHAR(50)",
        "daya": "INTEGER",
        "periode_bulan": "VARCHAR(20)",
        "pemakaian_kwh": "FLOAT",
        "tagihan_rupiah": "FLOAT"
    }

    with engine.connect() as conn:
        for col_name, col_type in expected_columns.items():
            if col_name not in existing_columns:
                conn.execute(text(f"ALTER TABLE swacam_readings ADD COLUMN {col_name} {col_type}"))
                conn.commit()
                print(f"[DB MIGRATION] Kolom '{col_name}' berhasil ditambahkan ke tabel swacam_readings.")

    # Migrasi tabel users (mis. reset_requested untuk fitur Lupa Password)
    if "users" in inspector.get_table_names():
        existing_user_columns = {col["name"] for col in inspector.get_columns("users")}
        expected_user_columns = {"reset_requested": "BOOLEAN DEFAULT 0", "phone_number": "VARCHAR(20)", "foto_profil": "VARCHAR(255)"}
        with engine.connect() as conn:
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

def save_reading(id_pelanggan: str, stand_meter: float, stand_meter_raw: str,
                 nama_file_foto: str, confidence_score: float = 1.0,
                 status_validasi: str = "SUCCESS", catatan: str = "",
                 link_drive: str = "", latitude: float = None,
                 longitude: float = None, no_seri_meter: str = None,
                 daya: int = None, periode_bulan: str = None,
                 pemakaian_kwh: float = None, tagihan_rupiah: float = None,
                 uploader_username: str = None) -> SwacamReading:
    """Menyimpan hasil bacaan meter ke database."""
    session = SessionLocal()
    try:
        record = SwacamReading(
            id_pelanggan=id_pelanggan,
            no_seri_meter=no_seri_meter,
            stand_meter=stand_meter,
            stand_meter_raw=stand_meter_raw,
            nama_file_foto=nama_file_foto,
            link_drive=link_drive,
            confidence_score=confidence_score,
            status_validasi=status_validasi,
            catatan=catatan,
            uploader_username=uploader_username,
            latitude=latitude,
            longitude=longitude,
            daya=daya,
            periode_bulan=periode_bulan,
            pemakaian_kwh=pemakaian_kwh,
            tagihan_rupiah=tagihan_rupiah
        )

        session.add(record)
        session.commit()
        session.refresh(record)
        return record
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def check_duplicate_reading(id_pelanggan: str, stand_meter: float, periode_bulan: str = None) -> SwacamReading:
    """Mengecek apakah IDPEL dan Stand Meter yang sama sudah pernah diinput sebelumnya di bulan yang sama."""
    if not id_pelanggan or stand_meter is None:
        return None
    session = SessionLocal()
    try:
        query = session.query(SwacamReading).filter(
            SwacamReading.id_pelanggan == id_pelanggan,
            SwacamReading.stand_meter == stand_meter
        )
        if periode_bulan:
            query = query.filter(SwacamReading.periode_bulan == periode_bulan)
        return query.order_by(SwacamReading.id.desc()).first()
    finally:
        session.close()

def get_reading_by_id(reading_id: int) -> SwacamReading:
    """Mengambil satu data pencatatan berdasarkan ID."""
    session = SessionLocal()
    try:
        return session.query(SwacamReading).filter(SwacamReading.id == reading_id).first()
    finally:
        session.close()

def get_last_reading_by_idpel(id_pelanggan: str, exclude_id: int = None) -> SwacamReading:
    """Mengambil data pencatatan terakhir untuk ID Pelanggan tertentu."""
    if not id_pelanggan:
        return None
    session = SessionLocal()
    try:
        q = session.query(SwacamReading).filter(
            SwacamReading.id_pelanggan == id_pelanggan
        )
        if exclude_id is not None:
            q = q.filter(SwacamReading.id != exclude_id)
        return q.order_by(SwacamReading.id.desc()).first()
    finally:
        session.close()

def get_initial_daya_by_idpel(id_pelanggan: str, exclude_id: int = None):
    """Daya (VA) AWAL pelanggan = daya pada pencatatan paling pertama yang punya data daya."""
    if not id_pelanggan:
        return None
    session = SessionLocal()
    try:
        q = session.query(SwacamReading).filter(
            SwacamReading.id_pelanggan == id_pelanggan,
            SwacamReading.daya.isnot(None),
        )
        if exclude_id is not None:
            q = q.filter(SwacamReading.id != exclude_id)
        rec = q.order_by(SwacamReading.id.asc()).first()
        return rec.daya if rec else None
    finally:
        session.close()

def delete_reading(reading_id: int) -> bool:
    """Menghapus data pencatatan berdasarkan ID."""
    session = SessionLocal()
    try:
        record = session.query(SwacamReading).filter(SwacamReading.id == reading_id).first()
        if record:
            session.delete(record)
            session.commit()
            return True
        return False
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def delete_all_readings() -> int:
    """Menghapus SEMUA data pencatatan meter. Mengembalikan jumlah baris yang dihapus."""
    session = SessionLocal()
    try:
        n = session.query(SwacamReading).delete(synchronize_session=False)
        session.commit()
        return n
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def update_reading(reading_id: int, id_pelanggan: str, stand_meter: float,
                   stand_meter_raw: str, confidence_score: float,
                   status_validasi: str, catatan: str,
                   latitude: float = None, longitude: float = None,
                   no_seri_meter: str = None) -> SwacamReading:
    """Memperbarui data pencatatan hasil cek ulang AI."""
    session = SessionLocal()
    try:
        record = session.query(SwacamReading).filter(SwacamReading.id == reading_id).first()
        if record:
            record.id_pelanggan = id_pelanggan
            record.no_seri_meter = no_seri_meter
            record.stand_meter = stand_meter
            record.stand_meter_raw = stand_meter_raw
            record.confidence_score = confidence_score
            record.status_validasi = status_validasi
            record.catatan = catatan
            record.latitude = latitude
            record.longitude = longitude
            session.commit()
            session.refresh(record)
            return record
        return None
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def get_all_readings():
    """Mengambil semua riwayat pencatatan meteran dari database."""
    session = SessionLocal()
    try:
        return session.query(SwacamReading).order_by(SwacamReading.id.desc()).all()
    finally:
        session.close()

def log_activity(username: str, role: str, action: str, details: str = None, ip_address: str = None):
    """Mencatat aktivitas pengguna ke tabel audit_logs."""
    session = SessionLocal()
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
    session = SessionLocal()
    try:
        logs = session.query(AuditLog).order_by(AuditLog.id.desc()).limit(limit).all()
        return [l.to_dict() for l in logs]
    finally:
        session.close()

def get_user_by_username(username: str):
    """Mengambil akun pegawai dari database berdasarkan username."""
    session = SessionLocal()
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
    session = SessionLocal()
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
    session = SessionLocal()
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
    session = SessionLocal()
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
    session = SessionLocal()
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
    session = SessionLocal()
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