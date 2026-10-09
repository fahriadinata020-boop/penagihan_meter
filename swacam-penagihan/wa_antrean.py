"""
Antrean pengiriman WhatsApp di SERVER (saran #1).

Dulu: tombol "Kirim WA ke Terpilih" memanggil API satu per satu dari browser,
sehingga bila tab ditutup proses berhenti.

Sekarang:
  1. Browser hanya membuat antrean  ->  POST /api/tunggakan/antrean
  2. Worker (thread di server) mengirim satu per satu dengan jeda otomatis.
  3. Hasil tiap pesan tercatat di tabel wa_antrean + wa_riwayat meski halaman ditutup.
  4. Halaman bisa dibuka lagi kapan saja -> GET /api/tunggakan/antrean/aktif

Tetap TIDAK ADA pengiriman otomatis: antrean hanya dibuat saat admin menekan tombol.

Butuh tabel dari swacam_db_migrasi_v2.sql (wa_batch, wa_antrean, wa_riwayat, pengaturan).
"""
import datetime
import random
import threading
from typing import List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import inspect, text
from sqlalchemy.exc import DBAPIError

from auth import get_current_admin, get_current_user
from db_handler import SessionLocal, TunggakanPelanggan, engine, log_activity

router = APIRouter(prefix="/api/tunggakan/antrean", tags=["Antrean Kirim WA"])

TABEL_WAJIB = ("wa_batch", "wa_antrean", "wa_riwayat", "pengaturan")
PESAN_MIGRASI = "Tabel antrean belum ada. Jalankan swacam_db_migrasi_v2.sql di phpMyAdmin terlebih dahulu."
MAKS_ANTREAN = 2000
STATUS_AKTIF = ("MENUNGGU", "BERJALAN")

_tabel_ok = False
_stop = threading.Event()
_thread: Optional[threading.Thread] = None


class JedaMinimumError(Exception):
    """Pelanggan sudah dikirimi pesan dalam jeda minimum (ditolak trigger database)."""


def tabel_siap() -> bool:
    global _tabel_ok
    if _tabel_ok:
        return True
    try:
        ada = set(inspect(engine).get_table_names())
        _tabel_ok = all(t in ada for t in TABEL_WAJIB)
    except Exception:
        _tabel_ok = False
    return _tabel_ok


def _butuh_tabel():
    if not tabel_siap():
        raise HTTPException(503, PESAN_MIGRASI)


def _pengaturan_int(s, kunci: str, default: int) -> int:
    try:
        v = s.execute(text("SELECT nilai FROM pengaturan WHERE kunci=:k"), {"k": kunci}).scalar()
        return int(str(v).strip()) if v is not None else default
    except Exception:
        return default


def cek_jam_operasional() -> Tuple[bool, str, dict]:
    """Cek apakah saat ini berada dalam jam operasional pengiriman WA (WIB).

    Mencegah pesan terkirim di larut malam yang dapat mengganggu pelanggan dan memicu laporan spam.
    """
    s = SessionLocal()
    try:
        aktif = bool(_pengaturan_int(s, "jam_operasional_aktif", 1))
        mulai = _pengaturan_int(s, "jam_operasional_mulai", 8)       # 08:00 WIB
        selesai = _pengaturan_int(s, "jam_operasional_selesai", 17)  # 17:00 WIB
        try:
            from zoneinfo import ZoneInfo
            now_wib = datetime.datetime.now(ZoneInfo("Asia/Jakarta"))
        except Exception:
            now_wib = datetime.datetime.now()
        jam = now_wib.hour
        info = {
            "aktif": aktif,
            "mulai": mulai,
            "selesai": selesai,
            "jam_sekarang": jam,
            "waktu_sekarang": now_wib.strftime("%H:%M:%S")
        }
        if not aktif:
            return True, "Jam operasional dinonaktifkan (pengiriman 24 jam diperbolehkan).", info
        if mulai <= jam < selesai:
            return True, f"Dalam jam operasional ({mulai:02d}:00 - {selesai:02d}:00 WIB).", info
        return False, f"Di luar jam operasional ({mulai:02d}:00 - {selesai:02d}:00 WIB, saat ini {now_wib.strftime('%H:%M')} WIB). Pengiriman dijeda demi kenyamanan pelanggan.", info
    finally:
        s.close()


# ─────────────────────────────────────────────────────────────
#  Riwayat (dipakai juga oleh kirim satuan di tunggakan.py)
# ─────────────────────────────────────────────────────────────
def catat_riwayat_awal(row: dict, pesan: str, oleh: str, no_hp: str = None,
                       batch_id: int = None, template_kode: str = None) -> int:
    """Catat pesan berstatus ANTRE. Trigger database menolak bila pelanggan yang sama
    sudah dikirimi pesan dalam jeda minimum -> JedaMinimumError."""
    s = SessionLocal()
    try:
        r = s.execute(text(
            "INSERT INTO wa_riwayat (id_pelanggan, nama, tunggakan_id, batch_id, no_hp, periode, nominal, "
            "template_kode, tahap, pesan, status, dikirim_oleh) "
            "VALUES (:idp, :nm, :tid, :bid, :hp, :per, :nom, :tpl, "
            "(SELECT tahap FROM wa_template WHERE kode=:tpl), :psn, 'ANTRE', :oleh)"),
            {"idp": row.get("id_pelanggan"), "nm": (row.get("nama") or None), "tid": row.get("id"), "bid": batch_id,
             "hp": no_hp or row.get("no_hp"), "per": row.get("periode"), "nom": row.get("nominal"),
             "tpl": template_kode, "psn": pesan, "oleh": oleh})
        s.commit()
        return r.lastrowid
    except DBAPIError as e:
        s.rollback()
        if "jeda minimum" in str(e).lower():
            jam = _pengaturan_int(s, "jeda_minimum_jam", 24)
            raise JedaMinimumError(f"Pelanggan ini sudah dikirimi pesan dalam {jam} jam terakhir.")
        raise
    finally:
        s.close()


def catat_riwayat_hasil(riwayat_id: int, berhasil: bool, keterangan: str, fonnte_id: str = None):
    s = SessionLocal()
    try:
        s.execute(text("UPDATE wa_riwayat SET status=:st, fonnte_id=:f, respon=:r WHERE id=:i"),
                  {"st": "TERKIRIM" if berhasil else "GAGAL", "f": fonnte_id,
                   "r": (keterangan or "")[:255], "i": riwayat_id})
        s.commit()
    finally:
        s.close()


# ─────────────────────────────────────────────────────────────
#  Worker
# ─────────────────────────────────────────────────────────────
def _hitung_batch(s, batch_id: int):
    """Hitung ulang counter batch dari tabel antrean; tutup batch bila tidak ada yang tersisa.
    Return status batch terkini."""
    s.execute(text(
        "UPDATE wa_batch SET "
        "terkirim=(SELECT COUNT(*) FROM wa_antrean WHERE batch_id=:b AND status='TERKIRIM'), "
        "gagal=(SELECT COUNT(*) FROM wa_antrean WHERE batch_id=:b AND status='GAGAL'), "
        "dilewati=(SELECT COUNT(*) FROM wa_antrean WHERE batch_id=:b AND status IN ('DILEWATI','DIBATALKAN')) "
        "WHERE id=:b"), {"b": batch_id})
    sisa = s.execute(text("SELECT COUNT(*) FROM wa_antrean WHERE batch_id=:b "
                          "AND status IN ('MENUNGGU','MEMPROSES')"), {"b": batch_id}).scalar()
    st = s.execute(text("SELECT status FROM wa_batch WHERE id=:b"), {"b": batch_id}).scalar()
    if not sisa and st in STATUS_AKTIF:
        s.execute(text("UPDATE wa_batch SET status='SELESAI', selesai_pada=NOW() WHERE id=:b"), {"b": batch_id})
        st = "SELESAI"
        _batch_selesai(s, batch_id)
    s.commit()
    return st


def _batch_selesai(s, batch_id: int):
    b = s.execute(text("SELECT total, terkirim, gagal, dilewati, dibuat_oleh FROM wa_batch WHERE id=:b"),
                  {"b": batch_id}).mappings().first()
    if not b:
        return
    ringkas = f"{b['terkirim']} terkirim, {b['gagal']} gagal, {b['dilewati']} dilewati dari {b['total']}"
    log_activity(username=b["dibuat_oleh"], role="admin", action="WA_ANTREAN_SELESAI",
                 details=f"Antrean #{batch_id}: {ringkas}")


def _jadwalkan_sisa(s, batch_id: int, jeda: int):
    d = max(1, int(round(jeda * random.uniform(0.75, 1.25))))
    s.execute(text("UPDATE wa_antrean SET jadwal_kirim=DATE_ADD(NOW(), INTERVAL :d SECOND) "
                   "WHERE batch_id=:b AND status='MENUNGGU'"), {"d": d, "b": batch_id})


def _selesaikan_item(s, item_id: int, status: str, respon: str):
    s.execute(text("UPDATE wa_antrean SET status=:st, respon=:r WHERE id=:i"),
              {"st": status, "r": (respon or "")[:255], "i": item_id})


def proses_satu() -> bool:
    """Ambil & kirim satu pesan yang sudah waktunya. Return True bila ada yang diproses."""
    import tunggakan as tg
    ok_jam, _, _ = cek_jam_operasional()
    if not ok_jam:
        return False

    s = SessionLocal()
    try:
        cand = s.execute(text(
            "SELECT id FROM wa_antrean WHERE status='MENUNGGU' AND (jadwal_kirim IS NULL OR jadwal_kirim <= NOW()) "
            "ORDER BY id LIMIT 1")).first()
        if not cand:
            return False
        # klaim atomik (aman bila server dijalankan lebih dari satu proses)
        klaim = s.execute(text("UPDATE wa_antrean SET status='MEMPROSES', diproses_pada=NOW(), "
                               "percobaan=percobaan+1 WHERE id=:i AND status='MENUNGGU'"), {"i": cand[0]})
        s.commit()
        if klaim.rowcount != 1:
            return True
        it = s.execute(text("SELECT * FROM wa_antrean WHERE id=:i"), {"i": cand[0]}).mappings().first()
        bid = it["batch_id"]
        b = s.execute(text("SELECT jeda_detik, dibuat_oleh FROM wa_batch WHERE id=:b"), {"b": bid}).mappings().first()
        jeda, oleh = (b["jeda_detik"], b["dibuat_oleh"]) if b else (8, "admin")
        s.execute(text("UPDATE wa_batch SET status='BERJALAN', mulai_pada=COALESCE(mulai_pada, NOW()) "
                       "WHERE id=:b AND status='MENUNGGU'"), {"b": bid})
        s.commit()

        x = s.get(TunggakanPelanggan, it["tunggakan_id"]) if it["tunggakan_id"] else None
        alasan = None
        tahap = None
        if it["template_kode"]:
            tahap = s.execute(text("SELECT tahap FROM wa_template WHERE kode=:k"), {"k": it["template_kode"]}).scalar()
        if x is None:
            alasan = "Data tunggakan sudah dihapus dari daftar"
        elif x.jatuh_tempo:
            sel = (datetime.date.today() - x.jatuh_tempo).days
            if tahap == 0 and sel > 0:
                alasan = "Sudah lewat jatuh tempo, pengingat ramah tidak relevan lagi"
            elif tahap != 0 and sel <= 0:
                alasan = f"Belum melewati batas pembayaran (tanggal {x.jatuh_tempo.day})"
        if alasan:
            _selesaikan_item(s, it["id"], "DILEWATI", alasan)
            _hitung_batch(s, bid)
            return True

        # catat riwayat dulu: trigger database menolak bila terlalu sering (jeda minimum)
        try:
            rid = catat_riwayat_awal(x.to_dict(), it["pesan"], oleh, no_hp=it["no_hp"],
                                     batch_id=bid, template_kode=it["template_kode"])
        except JedaMinimumError as e:
            _selesaikan_item(s, it["id"], "DILEWATI", str(e))
            _hitung_batch(s, bid)
            return True

        ok, ket, fid = tg.kirim_fonnte_detail(it["no_hp"], it["pesan"])
        catat_riwayat_hasil(rid, ok, ket, fid)

        if not ok and ket.startswith("Gagal terhubung") and it["percobaan"] < _pengaturan_int(s, "antrean_maks_percobaan", 2):
            # gangguan jaringan sementara -> coba lagi nanti (bukan penolakan dari Fonnte)
            s.execute(text("UPDATE wa_antrean SET status='MENUNGGU', respon=:r, "
                           "jadwal_kirim=DATE_ADD(NOW(), INTERVAL :d SECOND) WHERE id=:i"),
                      {"r": ket[:255], "d": max(15, jeda * 3), "i": it["id"]})
            s.commit()
            return True

        _selesaikan_item(s, it["id"], "TERKIRIM" if ok else "GAGAL", ket)
        x.wa_status = "TERKIRIM" if ok else "GAGAL"
        x.wa_waktu = datetime.datetime.now()
        x.wa_respon = ket
        if ok:
            x.wa_jumlah_kirim = (x.wa_jumlah_kirim or 0) + 1
        s.commit()
        if ok:
            import wa_template
            wa_template.tandai_tahap(x.id, it["template_kode"])
        log_activity(username=oleh, role="admin",
                     action="WA_TUNGGAKAN_TERKIRIM" if ok else "WA_TUNGGAKAN_GAGAL",
                     details=f"[Antrean #{bid}] IDPEL {x.id_pelanggan} -> {it['no_hp']}: {ket}")
        _jadwalkan_sisa(s, bid, jeda)
        _hitung_batch(s, bid)
        return True
    except Exception as e:
        s.rollback()
        print(f"[ANTREAN] error: {e}")
        return False
    finally:
        s.close()


def _pulihkan_terhenti():
    """Pesan yang sedang diproses saat server mati: statusnya tidak pasti, JANGAN dikirim ulang
    otomatis (bisa dobel). Tandai GAGAL supaya admin memeriksa manual."""
    s = SessionLocal()
    try:
        rows = s.execute(text("SELECT DISTINCT batch_id FROM wa_antrean WHERE status='MEMPROSES'")).fetchall()
        s.execute(text("UPDATE wa_antrean SET status='GAGAL', respon='Terhenti saat server dimatikan, cek status WA manual' "
                       "WHERE status='MEMPROSES'"))
        s.commit()
        for (bid,) in rows:
            _hitung_batch(s, bid)
    except Exception as e:
        s.rollback()
        print(f"[ANTREAN] pemulihan gagal: {e}")
    finally:
        s.close()


def _loop():
    while not _stop.is_set():
        ok_jam, _, _ = cek_jam_operasional()
        if not ok_jam:
            _stop.wait(15.0)  # Tunggu 15 detik saat di luar jam kerja
            continue
        sibuk = proses_satu()
        _stop.wait(0.3 if sibuk else 1.5)


def mulai_worker():
    """Dipanggil sekali saat server start (startup_event)."""
    global _thread
    if not tabel_siap():
        print(f"[ANTREAN] {PESAN_MIGRASI} Worker tidak dijalankan.")
        return
    if _thread and _thread.is_alive():
        return
    _pulihkan_terhenti()
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="wa-antrean", daemon=True)
    _thread.start()
    print("[ANTREAN] Worker kirim WA berjalan.")


def hentikan_worker():
    _stop.set()


# ─────────────────────────────────────────────────────────────
#  Endpoint
# ─────────────────────────────────────────────────────────────
class AntreanPayload(BaseModel):
    ids: List[int]
    template: Optional[str] = None
    batas_tanggal: Optional[int] = None
    kirim_ulang: bool = False
    template_kode: Optional[str] = None   # None = pesan standar lama | 'AUTO' | kode wa_template


def _batch_dict(b) -> dict:
    d = dict(b)
    for k in ("dibuat_pada", "mulai_pada", "selesai_pada"):
        if d.get(k):
            d[k] = d[k].strftime("%Y-%m-%d %H:%M:%S")
    return d


@router.post("")
def buat_antrean(payload: AntreanPayload, user: dict = Depends(get_current_user)):
    import os
    _butuh_tabel()
    if not os.getenv("FONNTE_TOKEN", "").strip():
        raise HTTPException(400, "FONNTE_TOKEN belum diisi di file .env")
    ids = list(dict.fromkeys(payload.ids))
    if not ids:
        raise HTTPException(400, "Belum ada pelanggan yang dipilih.")
    if len(ids) > MAKS_ANTREAN:
        raise HTTPException(400, f"Maksimal {MAKS_ANTREAN} pelanggan per antrean.")

    s = SessionLocal()
    try:
        aktif = s.execute(text("SELECT id FROM wa_batch WHERE status IN ('MENUNGGU','BERJALAN') LIMIT 1")).first()
        if aktif:
            raise HTTPException(409, {"batch_id": aktif[0],
                                      "pesan": f"Antrean #{aktif[0]} masih berjalan. Tunggu selesai atau hentikan dulu."})
        import wa_template as wt
        templates = wt.daftar_template()
        jendela = wt.jendela_pengingat() if templates else None
        data = [(rid, s.get(TunggakanPelanggan, rid)) for rid in ids]
        info = wt.tahap_massal([(x.id_pelanggan, x.periode or "") for _, x in data if x])
        siap, dilewati = [], []
        for rid, x in data:
            if not x:
                dilewati.append({"id": rid, "alasan": "Data tidak ditemukan"})
                continue
            if x.status_bayar == "LUNAS":
                dilewati.append({"id": rid, "id_pelanggan": x.id_pelanggan, "alasan": "Sudah lunas"})
                continue
            if not x.no_hp:
                dilewati.append({"id": rid, "id_pelanggan": x.id_pelanggan, "alasan": "Nomor WA kosong/tidak valid"})
                continue
            row = x.to_dict()
            ti = info.get((x.id_pelanggan, x.periode or ""), (None, None))
            pesan, kode, alasan = wt.siapkan_pesan(row, payload.template_kode, payload.template,
                                                   payload.batas_tanggal, ti, templates, jendela)
            if alasan:
                dilewati.append({"id": rid, "id_pelanggan": x.id_pelanggan, "alasan": alasan})
            elif not payload.kirim_ulang and wt.perlu_konfirmasi_ulang(row, kode, ti, templates):
                dilewati.append({"id": rid, "id_pelanggan": x.id_pelanggan, "alasan": "Sudah pernah terkirim"})
            else:
                siap.append((x, pesan, kode))
        if not siap:
            raise HTTPException(400, "Tidak ada pelanggan yang bisa dikirimi (semua dilewati: "
                                     f"{', '.join(sorted({d['alasan'] for d in dilewati}))}).")

        jeda = min(max(_pengaturan_int(s, "jeda_antar_pesan_detik", 8), 3), 120)
        bid = s.execute(text("INSERT INTO wa_batch (status, jenis, jeda_detik, total, dibuat_oleh) "
                             "VALUES ('MENUNGGU','TAGIHAN',:j,:t,:u)"),
                        {"j": jeda, "t": len(siap), "u": user.get("username", "admin")}).lastrowid
        ringkas = {}
        for x, pesan, kode in siap:
            s.execute(text("INSERT INTO wa_antrean (batch_id, tunggakan_id, id_pelanggan, no_hp, template_kode, pesan) "
                           "VALUES (:b,:t,:i,:h,:k,:p)"),
                      {"b": bid, "t": x.id, "i": x.id_pelanggan, "h": x.no_hp, "k": kode, "p": pesan})
            ringkas[kode or "standar"] = ringkas.get(kode or "standar", 0) + 1
        s.commit()
        log_activity(username=user.get("username", "admin"), role=user.get("role", "admin"),
                     action="WA_ANTREAN_DIBUAT",
                     details=f"Antrean #{bid}: {len(siap)} pesan, jeda ±{jeda} detik, {len(dilewati)} dilewati")
        return {"batch_id": bid, "diantrekan": len(siap), "dilewati": dilewati, "jeda_detik": jeda,
                "per_template": ringkas,
                "perkiraan_menit": round(len(siap) * jeda / 60, 1)}
    finally:
        s.close()


@router.get("/aktif")
def antrean_aktif(user: dict = Depends(get_current_user)):
    """Antrean yang sedang berjalan (null bila tidak ada). Dipakai halaman saat dibuka kembali."""
    if not tabel_siap():
        return {"batch": None, "tabel_siap": False}
    s = SessionLocal()
    try:
        b = s.execute(text("SELECT * FROM wa_batch WHERE status IN ('MENUNGGU','BERJALAN') "
                           "ORDER BY id DESC LIMIT 1")).mappings().first()
        return {"batch": _batch_dict(b) if b else None, "tabel_siap": True}
    finally:
        s.close()


@router.get("/{batch_id}")
def detail_antrean(batch_id: int, user: dict = Depends(get_current_user)):
    _butuh_tabel()
    s = SessionLocal()
    try:
        b = s.execute(text("SELECT * FROM wa_batch WHERE id=:b"), {"b": batch_id}).mappings().first()
        if not b:
            raise HTTPException(404, "Antrean tidak ditemukan.")
        items = s.execute(text("SELECT id_pelanggan, no_hp, status, respon, diproses_pada FROM wa_antrean "
                               "WHERE batch_id=:b ORDER BY id LIMIT 500"), {"b": batch_id}).mappings().all()
        menunggu = s.execute(text("SELECT COUNT(*) FROM wa_antrean WHERE batch_id=:b AND status IN ('MENUNGGU','MEMPROSES')"),
                             {"b": batch_id}).scalar()
        out = _batch_dict(b)
        out["menunggu"] = menunggu
        out["items"] = [{**dict(i), "diproses_pada": i["diproses_pada"].strftime("%H:%M:%S") if i["diproses_pada"] else None}
                        for i in items]
        return out
    finally:
        s.close()


@router.post("/{batch_id}/batal")
def batalkan_antrean(batch_id: int, user: dict = Depends(get_current_user)):
    _butuh_tabel()
    s = SessionLocal()
    try:
        b = s.execute(text("SELECT status FROM wa_batch WHERE id=:b"), {"b": batch_id}).scalar()
        if b is None:
            raise HTTPException(404, "Antrean tidak ditemukan.")
        if b not in STATUS_AKTIF:
            raise HTTPException(400, "Antrean ini sudah selesai.")
        n = s.execute(text("UPDATE wa_antrean SET status='DIBATALKAN', respon='Dibatalkan admin' "
                           "WHERE batch_id=:b AND status='MENUNGGU'"), {"b": batch_id}).rowcount
        s.execute(text("UPDATE wa_batch SET status='DIBATALKAN', selesai_pada=NOW() WHERE id=:b"), {"b": batch_id})
        s.commit()
        _hitung_batch(s, batch_id)
        log_activity(username=user.get("username", "admin"), role=user.get("role", "admin"),
                     action="WA_ANTREAN_DIBATALKAN", details=f"Antrean #{batch_id} dihentikan, {n} pesan dibatalkan")
        return {"message": f"Antrean dihentikan, {n} pesan dibatalkan.", "dibatalkan": n}
    finally:
        s.close()


# ── Pengaturan Jam Operasional Pengiriman WA (Anti-Spam / Etika) ───────────
class JamOperasionalPayload(BaseModel):
    aktif: bool
    mulai: int
    selesai: int


@router.get("/jam-operasional")
def get_jam_operasional(user: dict = Depends(get_current_user)):
    """Cek pengaturan dan status jam operasional pengiriman WA saat ini."""
    ok, ket, info = cek_jam_operasional()
    return {"bisa_kirim": ok, "keterangan": ket, **info}


@router.put("/jam-operasional")
def set_jam_operasional(payload: JamOperasionalPayload, admin: dict = Depends(get_current_admin)):
    """Admin: Atur jam operasional pengiriman WA (WIB) agar tidak mengganggu pelanggan di malam hari."""
    if not (0 <= payload.mulai <= 23) or not (1 <= payload.selesai <= 24) or payload.mulai >= payload.selesai:
        raise HTTPException(400, "Rentang jam tidak valid. Pastikan jam mulai < jam selesai (contoh: 08:00 - 17:00).")
    s = SessionLocal()
    try:
        def _set(k, v, ket):
            ada = s.execute(text("SELECT kunci FROM pengaturan WHERE kunci=:k"), {"k": k}).first()
            if ada:
                s.execute(text("UPDATE pengaturan SET nilai=:v, diubah_oleh=:u, diubah_pada=NOW() WHERE kunci=:k"),
                          {"v": str(v), "u": admin["username"], "k": k})
            else:
                s.execute(text("INSERT INTO pengaturan (kunci, nilai, keterangan, diubah_oleh, diubah_pada) VALUES (:k,:v,:c,:u,NOW())"),
                          {"k": k, "v": str(v), "c": ket, "u": admin["username"]})

        _set("jam_operasional_aktif", "1" if payload.aktif else "0", "Batasi pengiriman hanya pada jam kerja")
        _set("jam_operasional_mulai", str(payload.mulai), "Jam mulai pengiriman WA (WIB)")
        _set("jam_operasional_selesai", str(payload.selesai), "Jam selesai pengiriman WA (WIB)")
        s.commit()

        log_activity(
            username=admin["username"],
            role=admin["role"],
            action="UPDATE_JAM_OPERASIONAL",
            details=f"Jam operasional WA diubah: {'Aktif' if payload.aktif else 'Nonaktif'} ({payload.mulai:02d}:00 - {payload.selesai:02d}:00 WIB)"
        )
        ok, ket, info = cek_jam_operasional()
        return {"message": "Pengaturan jam operasional berhasil diperbarui.", "bisa_kirim": ok, "keterangan": ket, **info}
    finally:
        s.close()