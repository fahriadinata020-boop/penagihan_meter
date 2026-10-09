import time
from contextlib import asynccontextmanager
from pathlib import Path
from collections import defaultdict
from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Depends
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import BASE_DIR, AVATAR_DIR
from db_handler import init_db
from auth import auth_router, get_current_admin, get_current_user

from tunggakan import router as tunggakan_router
from wa_antrean import router as antrean_router, mulai_worker as mulai_worker_antrean, hentikan_worker
from wa_template import router as wa_template_router
from wa_riwayat import router as wa_riwayat_router
from analitik import router as analitik_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Inisialisasi database & worker antrean
    init_db()
    mulai_worker_antrean()
    yield
    # Shutdown: Graceful stop worker antrean
    hentikan_worker()

app = FastAPI(
    title="PLN SWACAM - Penagihan & WhatsApp",
    description="""
Aplikasi terpisah untuk penagihan:
- Impor tunggakan dari Excel dan kirim pesan WhatsApp (Fonnte).
- Antrean kirim WA, template bertahap, dan riwayat/webhook WA.
- Analitik & laporan penagihan (Excel / PDF).
- Autentikasi JWT memakai tabel users yang sama dengan aplikasi Catat Meter.
    """,
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

app.include_router(auth_router)
app.include_router(tunggakan_router)
app.include_router(antrean_router)
app.include_router(wa_template_router)
app.include_router(wa_riwayat_router)
app.include_router(analitik_router)

# ── Security: CORS ──────────────────────────────────────────────────────────
import os as _os
_cors_origins = ["*"] if _os.getenv("RAILWAY_ENVIRONMENT") or _os.getenv("RENDER") else [
    "http://localhost:8001", "http://127.0.0.1:8001",
    "http://localhost:8000", "http://127.0.0.1:8000",
    "http://localhost",
    "http://localhost:80",
    "http://localhost:8080", "http://127.0.0.1:8080",
    "http://localhost:8081", "http://127.0.0.1:8081",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ── Security: Security Headers Middleware ───────────────────────────────────
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

# ── Upload foto profil ──────────────────────────────────────────────────────
MAX_FILE_SIZE_MB = 20
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".jfif", ".jif", ".png", ".webp", ".bmp", ".gif", ".avif"}

# Static Files Directory Setup
STATIC_DIR = BASE_DIR / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Foto profil dipakai bersama aplikasi Catat Meter (folder avatars yang sama, lihat AVATAR_DIR di .env)
app.mount("/avatars", StaticFiles(directory=str(AVATAR_DIR)), name="avatars")

@app.get("/")
def read_root():
    """Halaman web aplikasi Penagihan (PHP: static/index.php)."""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "Web Penagihan & WhatsApp PLN SWACAM Active"}

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "PLN SWACAM Penagihan & WA"}

def kirim_tes(phone: str, pesan: str, cb):
    import threading
    from tunggakan import kirim_fonnte_detail, normalize_wa
    def _jalan():
        no = normalize_wa(phone)
        if not no:
            cb(False, "Nomor tidak valid")
            return
        ok, ket, _ = kirim_fonnte_detail(no, pesan)
        cb(ok, ket)
    threading.Thread(target=_jalan, daemon=True).start()

class TestWAPayload(BaseModel):
    phone: str

@app.post("/api/test-wa")
async def test_wa(payload: TestWAPayload, admin: dict = Depends(get_current_admin)):
    """Admin: kirim WA percobaan untuk cek token Fonnte & nomor."""
    hasil = {}
    import threading as _t
    ev = _t.Event()
    def cb(ok, resp):
        hasil["ok"], hasil["resp"] = ok, resp
        ev.set()
    kirim_tes(payload.phone, "Tes notifikasi SWACAM PLN: WhatsApp Fonnte terhubung.", cb)
    ev.wait(20)
    return {"berhasil": hasil.get("ok", False), "respon_fonnte": hasil.get("resp", "timeout")}

@app.get("/api/users/me")
async def get_my_profile(current_user: dict = Depends(get_current_user)):
    # Kembalikan data profil dari tabel users TANPA hash password
    return {k: v for k, v in current_user.items() if k != "password"}

class UpdateProfilePayload(BaseModel):
    username: str
    full_name: str

@app.put("/api/users/me/profile")
async def update_my_profile(payload: UpdateProfilePayload, current_user: dict = Depends(get_current_user)):
    from db_handler import update_user_basic_profile, ensure_user_row
    from auth import create_access_token
    ensure_user_row(current_user)
    
    uname = payload.username.strip().lower()
    fname = payload.full_name.strip()
    
    if not uname or not fname:
        raise HTTPException(400, "Username dan Nama Lengkap tidak boleh kosong")
        
    try:
        ok = update_user_basic_profile(current_user["username"], uname, fname)
        if not ok:
            raise HTTPException(404, "Akun tidak ditemukan")
            
        # Jika username berubah, token lama (yang berisi 'sub': old_username) akan invalid di request berikutnya
        # Jadi kita buatkan token baru dan kembalikan ke frontend
        new_token = create_access_token({"sub": uname})
        
        return {
            "message": "Profil berhasil diperbarui", 
            "new_token": new_token if uname != current_user["username"] else None,
            "username": uname,
            "full_name": fname
        }
    except ValueError as e:
        raise HTTPException(400, str(e))

class UpdatePasswordPayload(BaseModel):
    new_password: str

@app.put("/api/users/me/password")
async def update_my_password(payload: UpdatePasswordPayload, current_user: dict = Depends(get_current_user)):
    from db_handler import update_user_password, ensure_user_row
    ensure_user_row(current_user)
    if not payload.new_password or len(payload.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password minimal 6 karakter.")
    if not update_user_password(current_user["username"], payload.new_password):
        raise HTTPException(status_code=404, detail="Akun tidak ditemukan di database.")
    return {"message": "Password berhasil diperbarui"}


class UpdatePhonePayload(BaseModel):
    phone_number: str

@app.put("/api/users/me/phone")
async def update_my_phone(payload: UpdatePhonePayload, current_user: dict = Depends(get_current_user)):
    """Simpan nomor WA ke tabel users, dikunci ke akun yang sedang login."""
    from db_handler import update_user_phone, ensure_user_row, get_user_by_username
    phone = "".join(c for c in (payload.phone_number or "") if c.isdigit())
    if phone and not (9 <= len(phone) <= 15):
        raise HTTPException(status_code=400, detail="Nomor WA tidak valid (contoh: 08123456789).")
    ensure_user_row(current_user)
    ok = update_user_phone(current_user["username"], phone or None)
    if not ok:
        raise HTTPException(status_code=404, detail="Akun tidak ditemukan di database.")
    saved = (get_user_by_username(current_user["username"]) or {}).get("phone_number")
    print(f"[PROFIL] No. WA {current_user['username']} tersimpan di DB: {saved}")
    return {"message": "Nomor WA berhasil disimpan", "phone_number": saved}


@app.post("/api/users/me/photo")
async def update_my_photo(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    """Upload foto profil; nama file diawali username sehingga tiap akun terpisah."""
    from db_handler import update_user_photo, ensure_user_row
    ensure_user_row(current_user)

    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Format foto tidak didukung.")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"Ukuran foto maksimal {MAX_FILE_SIZE_MB}MB.")

    uname = current_user["username"]
    filename = f"{uname}_{int(time.time())}{ext}"
    with open(AVATAR_DIR / filename, "wb") as f:
        f.write(contents)

    foto_url = f"/avatars/{filename}"
    if not update_user_photo(uname, foto_url):
        raise HTTPException(status_code=404, detail="Akun tidak ditemukan di database.")
    return {"message": "Foto profil berhasil disimpan", "foto_profil": foto_url}


