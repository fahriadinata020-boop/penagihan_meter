from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
import jwt

import os
import hashlib
import hmac

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "PLN_SWACAM_RAHASIA_SUPER_KUAT")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1 hari

def _hash_password(password: str) -> str:
    """Hash password menggunakan SHA-256 + salt sederhana."""
    salt = "PLN_SWACAM_SALT_2024"
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()

def _verify_password(plain: str, hashed: str) -> bool:
    """Verifikasi password dengan hash yang tersimpan."""
    return hmac.compare_digest(_hash_password(plain), hashed)

# Mock Database Pengguna (password disimpan sebagai hash)
USERS_DB = {
    "admin": {
        "username": "admin",
        "password": _hash_password("admin123"),
        "role": "admin",
        "full_name": "Administrator PLN",
        "phone_number": "083170558792",
        "foto_profil": None
    },
    "petugas": {
        "username": "petugas",
        "password": _hash_password("petugas123"),
        "role": "petugas",
        "full_name": "Petugas Pencatat Meter",
        "phone_number": None,
        "foto_profil": None
    }
}

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/login")

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token tidak valid atau sudah kedaluwarsa",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        if username is None or role is None:
            raise credentials_exception
        token_data = TokenData(username=username, role=role)
    except jwt.PyJWTError:
        raise credentials_exception
    
    from db_handler import get_user_by_username
    user = get_user_by_username(username.lower()) or USERS_DB.get(username.lower())
    if user is None:
        raise credentials_exception
    return user


async def get_current_admin(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akses Ditolak. Anda bukan Administrator."
        )
    return current_user

auth_router = APIRouter()

from fastapi import Query

async def get_current_user_from_query(token: str = Query(...)):
    return await get_current_user(token)

async def get_current_admin_from_query(current_user: dict = Depends(get_current_user_from_query)):
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akses Ditolak. Anda bukan Administrator."
        )
    return current_user

class RegisterRequest(BaseModel):
    username: str
    password: str
    full_name: str
    phone_number: Optional[str] = None
    role: Optional[str] = "petugas"

class ForgotPasswordRequest(BaseModel):
    username: str
    full_name: str

@auth_router.post("/api/forgot-password")
async def forgot_password(req: ForgotPasswordRequest):
    """Endpoint publik: pegawai yang lupa password mengajukan permintaan reset
    yang akan disetujui & diproses oleh Admin (tidak langsung mengubah password)."""
    from db_handler import request_password_reset, log_activity
    if not req.username or not req.full_name:
        raise HTTPException(status_code=400, detail="Username dan nama lengkap wajib diisi!")

    u_clean = req.username.strip().lower()
    ok, msg = request_password_reset(username=u_clean, full_name=req.full_name.strip())
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    log_activity(
        username=u_clean,
        role="petugas",
        action="REQUEST_RESET_PASSWORD",
        details=f"Pengguna {u_clean} mengajukan permintaan lupa password"
    )
    return {"message": msg}

@auth_router.post("/api/register")
async def register_employee(req: RegisterRequest):
    """Endpoint untuk registrasi pegawai PLN baru."""
    from db_handler import register_new_user, log_activity
    if not req.username or not req.password or not req.full_name:
        raise HTTPException(status_code=400, detail="Semua kolom wajib diisi!")
    
    u_clean = req.username.strip().lower()
    user, msg = register_new_user(
        username=u_clean,
        password=req.password,
        full_name=req.full_name.strip(),
        phone_number=(req.phone_number or "").strip() or None,
        role=req.role if req.role in ["petugas", "admin"] else "petugas"
    )
    if not user:
        raise HTTPException(status_code=400, detail=msg)
    
    log_activity(
        username=u_clean,
        role=req.role,
        action="REGISTRASI_PEGAWAI",
        details=f"Pegawai baru terdaftar: {req.full_name} ({u_clean})"
    )
    return {"message": "Registrasi pegawai berhasil! Silakan login dengan akun baru Anda.", "username": u_clean}

@auth_router.post("/api/login", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    from db_handler import get_user_by_username
    u_lower = form_data.username.lower().strip()
    user = get_user_by_username(u_lower) or USERS_DB.get(u_lower)
    
    if not user or not _verify_password(form_data.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username atau Password salah",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if user.get("status", "approved") != "approved":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akun Anda masih menunggu persetujuan (pending) atau telah ditolak oleh Admin."
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"], "role": user["role"]}, expires_delta=access_token_expires
    )
    from db_handler import log_activity
    log_activity(
        username=user["username"],
        role=user["role"],
        action="USER_LOGIN",
        details=f"User {user['username']} berhasil login"
    )
    return {"access_token": access_token, "token_type": "bearer", "role": user["role"]}



@auth_router.get("/api/me")
async def read_users_me(current_user: dict = Depends(get_current_user)):
    return {"username": current_user["username"], "role": current_user["role"], "full_name": current_user["full_name"],
            "phone_number": current_user.get("phone_number"), "foto_profil": current_user.get("foto_profil")}

# ── Admin User Management ───────────────────────────────────────────────────
@auth_router.get("/api/admin/users")
async def list_users(admin: dict = Depends(get_current_admin)):
    """Admin: Ambil daftar seluruh akun petugas/admin beserta status persetujuan."""
    from db_handler import get_all_users
    return get_all_users()

class UserStatusPayload(BaseModel):
    status: str

@auth_router.put("/api/admin/users/{user_id}/status")
async def change_user_status(user_id: int, payload: UserStatusPayload, admin: dict = Depends(get_current_admin)):
    """Admin: Setujui (approve) atau tolak (reject) akun petugas baru."""
    from db_handler import update_user_status, log_activity
    st = payload.status.lower().strip()
    if st not in ["approved", "pending", "rejected"]:
        raise HTTPException(status_code=400, detail="Status harus 'approved', 'pending', atau 'rejected'.")
    ok, msg = update_user_status(user_id, st)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    log_activity(
        username=admin["username"],
        role=admin["role"],
        action="UPDATE_USER_STATUS",
        details=f"Admin {admin['username']} mengubah status user {msg} (ID: {user_id}) menjadi {st}"
    )
    return {"message": f"Status akun '{msg}' berhasil diubah menjadi {st}.", "username": msg, "status": st}

class AdminResetPasswordPayload(BaseModel):
    new_password: str

@auth_router.post("/api/admin/users/{user_id}/reset-password")
async def reset_user_password(user_id: int, payload: AdminResetPasswordPayload, admin: dict = Depends(get_current_admin)):
    """Admin: Reset password pengguna (memproses permohonan lupa password)."""
    from db_handler import admin_reset_password, log_activity
    if not payload.new_password or len(payload.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password baru minimal 6 karakter.")
    ok, msg = admin_reset_password(user_id, payload.new_password)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    log_activity(
        username=admin["username"],
        role=admin["role"],
        action="ADMIN_RESET_PASSWORD",
        details=f"Admin {admin['username']} mereset password akun {msg} (ID: {user_id})"
    )
    return {"message": f"Password untuk akun '{msg}' berhasil direset.", "username": msg}

@auth_router.delete("/api/admin/users/{user_id}")
async def hapus_user(user_id: int, admin: dict = Depends(get_current_admin)):
    """Admin: Menghapus akun petugas secara permanen."""
    from db_handler import delete_user, log_activity
    if user_id == admin.get("id"):
        raise HTTPException(status_code=400, detail="Anda tidak bisa menghapus akun Anda sendiri.")
        
    ok, msg = delete_user(user_id)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    log_activity(
        username=admin["username"],
        role=admin["role"],
        action="ADMIN_DELETE_USER",
        details=f"Admin {admin['username']} menghapus akun {msg} (ID: {user_id})"
    )
    return {"message": f"Akun '{msg}' berhasil dihapus.", "username": msg}
