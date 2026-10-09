"""
Riwayat pesan WA per pelanggan + webhook status dari Fonnte (saran #8).

  GET  /api/wa/riwayat?q=&status=&limit=   -> daftar semua pesan (halaman "Riwayat WA")
  GET  /api/wa/riwayat/{idpel}             -> semua pesan satu pelanggan
  DELETE /api/wa/riwayat/{id}              -> hapus satu pesan dari riwayat (admin)
  POST /api/wa/riwayat/hapus-massal        -> hapus beberapa pesan sekaligus (admin)
  POST /api/wa/webhook?key=...             -> dipanggil Fonnte (status terkirim/dibaca + balasan)

Webhook TIDAK memakai login (Fonnte yang memanggil), jadi dijaga kunci rahasia:
isi WA_WEBHOOK_KEY di .env, lalu daftarkan URL  https://DOMAIN-ANDA/api/wa/webhook?key=ISI_KUNCI
di dashboard Fonnte. Server harus bisa diakses dari internet (localhost/XAMPP biasa TIDAK bisa
menerima webhook kecuali memakai tunnel seperti ngrok / Cloudflare Tunnel).
"""
import hmac
import json
import os
import re
from typing import Optional
import requests

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import text

from auth import get_current_admin, get_current_user
from db_handler import SessionLocal, log_activity

router = APIRouter(prefix="/api/wa", tags=["Riwayat WA"])

RANK = {"ANTRE": 0, "TERKIRIM": 1, "DITERIMA": 2, "DIBACA": 3}
KOLOM_WAKTU = ("waktu_kirim", "waktu_diterima", "waktu_dibaca", "waktu_balasan")


def _siap():
    import wa_antrean
    if not wa_antrean.tabel_siap():
        raise HTTPException(503, wa_antrean.PESAN_MIGRASI)


def _fmt(d: dict) -> dict:
    for k in KOLOM_WAKTU:
        if d.get(k):
            d[k] = d[k].strftime("%Y-%m-%d %H:%M:%S")
    return d


_SELECT = ("SELECT r.id, r.id_pelanggan, r.no_hp, r.periode, r.nominal, r.template_kode, r.tahap, r.status, "
           "r.respon, r.dikirim_oleh, r.batch_id, r.pesan, r.waktu_kirim, r.waktu_diterima, r.waktu_dibaca, "
           "r.balasan, r.waktu_balasan, "
           "COALESCE(NULLIF(r.nama,''), (SELECT t.nama FROM tunggakan_pelanggan t WHERE t.id_pelanggan=r.id_pelanggan LIMIT 1)) AS nama "
           "FROM wa_riwayat r")


@router.get("/riwayat")
def daftar_riwayat(q: Optional[str] = None, status: Optional[str] = None,
                   limit: int = Query(200, ge=1, le=1000), user: dict = Depends(get_current_user)):
    _siap()
    where, par = [], {"lim": limit}
    if q and q.strip():
        par["q"] = f"%{q.strip()}%"
        where.append("(r.id_pelanggan LIKE :q OR r.no_hp LIKE :q OR r.nama LIKE :q OR EXISTS (SELECT 1 FROM tunggakan_pelanggan t "
                     "WHERE t.id_pelanggan=r.id_pelanggan AND t.nama LIKE :q))")
    if status and status.upper() in (*RANK, "GAGAL"):
        par["st"] = status.upper()
        where.append("r.status=:st")
    sql = _SELECT + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY r.id DESC LIMIT :lim"
    s = SessionLocal()
    try:
        return [_fmt(dict(r)) for r in s.execute(text(sql), par).mappings().all()]
    finally:
        s.close()


@router.get("/riwayat/{id_pelanggan}")
def riwayat_pelanggan(id_pelanggan: str, user: dict = Depends(get_current_user)):
    _siap()
    s = SessionLocal()
    try:
        rows = s.execute(text(_SELECT + " WHERE r.id_pelanggan=:i ORDER BY r.id DESC LIMIT 500"),
                         {"i": id_pelanggan}).mappings().all()
        return [_fmt(dict(r)) for r in rows]
    finally:
        s.close()


# ── Status Perangkat WhatsApp Fonnte ─────────────────────────────────────────
@router.get("/status-perangkat")
def status_perangkat(user: dict = Depends(get_current_user)):
    """Cek status koneksi perangkat WhatsApp dan sisa kuota via API Fonnte."""
    token = os.getenv("FONNTE_TOKEN", "").strip()
    if not token:
        return {
            "terisi": False,
            "status_api": False,
            "device_status": "disconnected",
            "device": None,
            "pesan": "FONNTE_TOKEN belum diisi di file .env"
        }
    try:
        r = requests.post("https://api.fonnte.com/device", headers={"Authorization": token}, timeout=10)
        j = r.json() if r.status_code == 200 else {}
        return {
            "terisi": True,
            "status_api": bool(j.get("status")),
            "device_status": j.get("device_status", "unknown"),  # 'connect', 'disconnect'
            "device": j.get("device"),
            "name": j.get("name"),
            "quota": j.get("quota"),
            "expired": j.get("expired"),
            "messages": j.get("messages")
        }
    except Exception as e:
        return {
            "terisi": True,
            "status_api": False,
            "device_status": "error",
            "pesan": f"Gagal menghubungi Fonnte: {e}"
        }


# ── Kotak Masuk (Inbox) Balasan Pelanggan ────────────────────────────────────
@router.get("/inbox")
def daftar_inbox(limit: int = Query(100, ge=1, le=500), user: dict = Depends(get_current_user)):
    """Daftar pesan masuk / balasan dari pelanggan WhatsApp."""
    _siap()
    s = SessionLocal()
    try:
        sql = (_SELECT + " WHERE r.balasan IS NOT NULL AND r.balasan <> '' "
               "ORDER BY r.waktu_balasan DESC, r.id DESC LIMIT :lim")
        rows = s.execute(text(sql), {"lim": limit}).mappings().all()
        return [_fmt(dict(r)) for r in rows]
    finally:
        s.close()


@router.get("/inbox/count")
def count_inbox(user: dict = Depends(get_current_user)):
    """Hitung total balasan pelanggan yang tercatat di riwayat."""
    _siap()
    s = SessionLocal()
    try:
        c = s.execute(text("SELECT COUNT(*) FROM wa_riwayat WHERE balasan IS NOT NULL AND balasan <> ''")).scalar()
        return {"total_balasan": int(c or 0)}
    finally:
        s.close()



# ─────────────────────────────────────────────────────────────
#  Hapus riwayat (admin)
#  Catatan: yang dihapus hanya catatan di database, pesan WhatsApp yang sudah terkirim tidak ditarik.
#  Efek samping: jeda minimum antar-pesan, tahap pengingat otomatis, dan angka analitik dihitung dari
#  tabel ini, jadi ikut berubah untuk pelanggan yang riwayatnya dihapus.
# ─────────────────────────────────────────────────────────────
MAX_HAPUS = 2000


class HapusRiwayatPayload(BaseModel):
    ids: list[int]


def _log_hapus(admin: dict, n: int, rincian: str):
    try:
        log_activity(username=admin.get("username", "admin"), role=admin.get("role", "admin"),
                     action="HAPUS_RIWAYAT_WA", details=f"{n} pesan dihapus dari riwayat WA: {rincian}"[:500])
    except Exception as e:
        print(f"[RIWAYAT] gagal mencatat audit: {e}")


@router.delete("/riwayat/{rid}")
def hapus_riwayat(rid: int, admin: dict = Depends(get_current_admin)):
    _siap()
    s = SessionLocal()
    try:
        row = s.execute(text("SELECT id_pelanggan, no_hp, status FROM wa_riwayat WHERE id=:i"), {"i": rid}).first()
        if not row:
            raise HTTPException(404, "Pesan tidak ditemukan (mungkin sudah dihapus).")
        s.execute(text("DELETE FROM wa_riwayat WHERE id=:i"), {"i": rid})
        s.commit()
        _log_hapus(admin, 1, f"#{rid} IDPEL {row[0]} -> {row[1]} ({row[2]})")
        return {"dihapus": 1, "message": "Pesan dihapus dari riwayat."}
    except HTTPException:
        raise
    except Exception as e:
        s.rollback()
        raise HTTPException(500, f"Gagal menghapus: {e}"[:200])
    finally:
        s.close()


@router.post("/riwayat/hapus-massal")
def hapus_riwayat_massal(payload: HapusRiwayatPayload, admin: dict = Depends(get_current_admin)):
    _siap()
    ids = list(dict.fromkeys(payload.ids))
    if not ids:
        raise HTTPException(400, "Belum ada pesan yang dipilih.")
    if len(ids) > MAX_HAPUS:
        raise HTTPException(400, f"Maksimal {MAX_HAPUS} pesan per penghapusan.")
    s = SessionLocal()
    try:
        n = 0
        for i in range(0, len(ids), 500):
            potong = ids[i:i + 500]
            marks = ",".join(f":p{k}" for k in range(len(potong)))
            par = {f"p{k}": v for k, v in enumerate(potong)}
            n += s.execute(text(f"DELETE FROM wa_riwayat WHERE id IN ({marks})"), par).rowcount
        s.commit()
        _log_hapus(admin, n, f"hapus massal ({len(ids)} dipilih)")
        return {"dihapus": n, "message": f"{n} pesan dihapus dari riwayat."}
    except Exception as e:
        s.rollback()
        raise HTTPException(500, f"Gagal menghapus: {e}"[:200])
    finally:
        s.close()


# ─────────────────────────────────────────────────────────────
#  Webhook Fonnte
# ─────────────────────────────────────────────────────────────
def petakan_status(raw) -> Optional[str]:
    """Ubah status dari Fonnte (teks bebas) ke status internal; None bila tidak dikenali."""
    s = str(raw or "").strip().lower()
    if not s or "unread" in s:
        return None
    if "read" in s or "baca" in s:
        return "DIBACA"
    if "deliver" in s or "diterima" in s:
        return "DITERIMA"
    if "sent" in s or "terkirim" in s:
        return "TERKIRIM"
    if any(w in s for w in ("fail", "gagal", "invalid", "expire", "error")):
        return "GAGAL"
    return None


def _angka(v) -> str:
    return re.sub(r"\D", "", str(v or ""))


def proses_payload(data: dict) -> dict:
    """Terapkan satu payload webhook ke wa_riwayat. Return ringkasan untuk log/uji."""
    fid = data.get("id") or data.get("message_id") or data.get("messageId")
    if isinstance(fid, (list, tuple)):
        fid = fid[0] if fid else None
    fid = str(fid) if fid not in (None, "") else None
    state = petakan_status(data.get("state") or data.get("status"))
    hasil = {"fonnte_id": fid, "state": state, "diperbarui": 0, "balasan": False}
    s = SessionLocal()
    try:
        if fid and state:
            row = s.execute(text("SELECT id, status FROM wa_riwayat WHERE fonnte_id=:f ORDER BY id DESC LIMIT 1"),
                            {"f": fid}).first()
            if row:
                rid, cur = row
                if state == "GAGAL":
                    if cur in ("ANTRE", "TERKIRIM"):
                        s.execute(text("UPDATE wa_riwayat SET status='GAGAL', respon=:r WHERE id=:i"),
                                  {"r": f"Webhook: {data.get('state') or data.get('status')}"[:255], "i": rid})
                        hasil["diperbarui"] = 1
                elif RANK.get(state, 0) > RANK.get(cur, -1):
                    kol = {"DITERIMA": "waktu_diterima=NOW()", "DIBACA": "waktu_dibaca=NOW(), "
                           "waktu_diterima=COALESCE(waktu_diterima, NOW())"}.get(state, "waktu_kirim=waktu_kirim")
                    s.execute(text(f"UPDATE wa_riwayat SET status=:st, {kol} WHERE id=:i"), {"st": state, "i": rid})
                    hasil["diperbarui"] = 1
        # pesan masuk dari pelanggan (balasan): punya pengirim + isi, tanpa id pesan keluar
        pengirim, isi = _angka(data.get("sender") or data.get("from")), data.get("message") or data.get("text")
        if pengirim and isi and not fid:
            if pengirim.startswith("0"):
                pengirim = "62" + pengirim[1:]
            n = s.execute(text(
                "UPDATE wa_riwayat SET balasan=:m, waktu_balasan=NOW() WHERE id=("
                "SELECT id FROM (SELECT id FROM wa_riwayat WHERE no_hp=:h OR RIGHT(no_hp,10)=RIGHT(:h,10) "
                "ORDER BY id DESC LIMIT 1) x)"), {"m": str(isi)[:2000], "h": pengirim}).rowcount
            hasil["balasan"] = bool(n)
        s.commit()
        return hasil
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


@router.post("/webhook")
async def webhook_fonnte(request: Request, key: str = Query("")):
    kunci = os.getenv("WA_WEBHOOK_KEY", "").strip()
    if not kunci:
        raise HTTPException(403, "WA_WEBHOOK_KEY belum diisi di .env, webhook dinonaktifkan.")
    if not hmac.compare_digest(key.encode(), kunci.encode()):
        raise HTTPException(403, "Kunci webhook salah.")
    _siap()
    mentah = (await request.body()).decode("utf-8", "replace")
    data = {}
    try:
        data = json.loads(mentah)
    except Exception:
        try:
            data = {k: v for k, v in (await request.form()).items()}
        except Exception:
            data = {}
    if not isinstance(data, dict):
        data = {}
    fid = data.get("id")
    if isinstance(fid, (list, tuple)):
        fid = fid[0] if fid else None
    s = SessionLocal()
    try:
        log_id = s.execute(text("INSERT INTO wa_webhook_log (fonnte_id, state, payload) VALUES (:f,:s,:p)"),
                           {"f": str(fid)[:60] if fid else None,
                            "s": str(data.get("state") or data.get("status") or "")[:30] or None,
                            "p": mentah[:20000]}).lastrowid
        s.commit()
    finally:
        s.close()
    try:
        hasil = proses_payload(data)
        s2 = SessionLocal()
        try:
            s2.execute(text("UPDATE wa_webhook_log SET diproses=1 WHERE id=:i"), {"i": log_id})
            s2.commit()
        finally:
            s2.close()
    except Exception as e:
        print(f"[WEBHOOK] gagal memproses: {e}")
        hasil = {"error": "gagal diproses"}
    return {"ok": True, **hasil}