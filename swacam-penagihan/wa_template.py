"""
Template pesan bertahap + saran otomatis (saran #4 dan #5).

Tahap (tabel wa_template, bisa diubah):
  0  PENGINGAT_RAMAH       sebelum jatuh tempo (pengaturan: tanggal 15-17), tetap lewat tombol manual
  1  PENGINGAT_1           1-6 hari setelah jatuh tempo
  2  PENGINGAT_2           7-13 hari
  3  PEMBERITAHUAN_AKHIR   14 hari ke atas

Aturan saran otomatis ("AUTO"), per pelanggan:
  - Belum jatuh tempo       -> tahap 0, HANYA bila hari ini dalam jendela pengingat (mis. tgl 15-17).
  - Sudah lewat jatuh tempo -> tahap menurut jumlah hari terlambat, TETAPI tidak boleh melompat:
                               tahap = min(tahap_menurut_hari, tahap_tertinggi_yang_pernah_dikirim + 1).
    Contoh: terlambat 11 hari tapi belum pernah dikirimi apa pun -> mulai dari PENGINGAT_1
    (bukan "pengingat kedua" yang tidak masuk akal bagi pelanggan yang belum pernah diingatkan).
"""
import datetime
from typing import List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from auth import get_current_admin
from db_handler import SessionLocal, log_activity

router = APIRouter(prefix="/api/wa/template", tags=["Template WA"])

MODE_AUTO = "AUTO"


def tabel_siap() -> bool:
    import wa_antrean
    return wa_antrean.tabel_siap()


def _pengaturan_int(s, kunci: str, default: int) -> int:
    import wa_antrean
    return wa_antrean._pengaturan_int(s, kunci, default)


# ─────────────────────────────────────────────────────────────
#  Baca template & pengaturan
# ─────────────────────────────────────────────────────────────
def daftar_template(hanya_aktif: bool = True) -> List[dict]:
    if not tabel_siap():
        return []
    s = SessionLocal()
    try:
        q = "SELECT kode, nama, tahap, hari_min, hari_max, isi, aktif FROM wa_template"
        if hanya_aktif:
            q += " WHERE aktif=1"
        q += " ORDER BY tahap"
        return [dict(r) for r in s.execute(text(q)).mappings().all()]
    finally:
        s.close()


def ambil_template(kode: str) -> Optional[dict]:
    for t in daftar_template(hanya_aktif=False):
        if t["kode"] == kode:
            return t
    return None


def jendela_pengingat(hari: datetime.date = None) -> dict:
    """Pengingat ramah hanya boleh dikirim pada tanggal mulai..selesai (default 15-17)."""
    hari = hari or datetime.date.today()
    s = SessionLocal()
    try:
        mulai = _pengaturan_int(s, "pengingat_awal_mulai", 15)
        selesai = _pengaturan_int(s, "pengingat_awal_selesai", 17)
    finally:
        s.close()
    return {"mulai": mulai, "selesai": selesai, "terbuka": mulai <= hari.day <= selesai}


def hari_selisih(row: dict) -> int:
    """>0 = terlambat N hari; <=0 = belum/tepat jatuh tempo (negatif = sebelum)."""
    if row.get("kategori") == "BELUM_JATUH_TEMPO":
        return -((row.get("sisa_hari") or 1) - 1)
    return row.get("hari_terlambat") or 1


def tahap_tertinggi(id_pelanggan: str, periode: str) -> Tuple[Optional[int], Optional[int]]:
    """(tahap_tertinggi_semua, tahap_eskalasi_tertinggi>=1) dari riwayat yang BUKAN gagal."""
    r = tahap_massal([(id_pelanggan, periode)])
    return r.get((id_pelanggan, periode or ""), (None, None))


def tahap_massal(pasangan) -> dict:
    """{(idpel, periode): (maks_semua, maks_eskalasi)} untuk banyak pelanggan sekaligus (1 query)."""
    if not tabel_siap():
        return {}
    ids = sorted({p[0] for p in pasangan})
    if not ids:
        return {}
    s = SessionLocal()
    try:
        out = {}
        for i in range(0, len(ids), 500):
            bag = ids[i:i + 500]
            marks = ",".join(f":i{n}" for n in range(len(bag)))
            rows = s.execute(text(
                "SELECT id_pelanggan, COALESCE(periode,'') AS periode, MAX(tahap) AS mx_all, "
                "MAX(CASE WHEN tahap>=1 THEN tahap END) AS mx_esk FROM wa_riwayat "
                f"WHERE status<>'GAGAL' AND tahap IS NOT NULL AND id_pelanggan IN ({marks}) "
                "GROUP BY id_pelanggan, COALESCE(periode,'')"),
                {f"i{n}": v for n, v in enumerate(bag)}).all()
            for r in rows:
                out[(r[0], r[1])] = (r[2], r[3])
        return out
    finally:
        s.close()


# ─────────────────────────────────────────────────────────────
#  Aturan pemilihan
# ─────────────────────────────────────────────────────────────
def tahap_menurut_hari(sel: int, templates: List[dict]) -> int:
    """Tahap eskalasi (>=1) menurut hari terlambat, memakai rentang hari_min/hari_max dari tabel."""
    esk = [t for t in templates if t["tahap"] >= 1]
    for t in esk:
        if sel >= t["hari_min"] and (t["hari_max"] is None or sel <= t["hari_max"]):
            return t["tahap"]
    # celah rentang: ambil tahap tertinggi yang hari_min-nya sudah terlewati
    ok = [t["tahap"] for t in esk if sel >= t["hari_min"]]
    return max(ok) if ok else 1


def pilih_otomatis(row: dict, mx_esk: Optional[int], templates: List[dict],
                   jendela: dict) -> Tuple[Optional[dict], Optional[str]]:
    """Return (template, alasan_ditolak). Tepat salah satu yang terisi."""
    by_tahap = {t["tahap"]: t for t in templates}
    sel = hari_selisih(row)
    if sel <= 0:
        if 0 not in by_tahap:
            return None, "Template pengingat ramah tidak aktif"
        if not jendela["terbuka"]:
            return None, (f"Belum jatuh tempo dan di luar masa pengingat ramah "
                          f"(tanggal {jendela['mulai']}-{jendela['selesai']})")
        return by_tahap[0], None
    kand = tahap_menurut_hari(sel, templates)
    tahap = max(1, min(kand, (mx_esk or 0) + 1))
    # bila tahap hasil hitungan tidak aktif, turun ke tahap aktif terdekat di bawahnya
    while tahap >= 1 and tahap not in by_tahap:
        tahap -= 1
    if tahap < 1:
        return None, "Tidak ada template tagihan yang aktif"
    return by_tahap[tahap], None


def siapkan_pesan(row: dict, mode: Optional[str], teks_custom: Optional[str], batas: Optional[int],
                  tahap_info: Tuple[Optional[int], Optional[int]] = (None, None),
                  templates: List[dict] = None, jendela: dict = None) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Return (pesan, kode_template, alasan_dilewati).
      mode None      -> perilaku lama (satu pesan standar, hanya untuk yang sudah lewat jatuh tempo)
      mode 'AUTO'    -> template dipilih per pelanggan (lihat aturan di atas)
      mode <KODE>    -> template tertentu; dicek cocok dengan keadaan pelanggan
    teks_custom (bila diisi dan mode bukan AUTO) memakai isi yang sudah diedit admin di textarea.
    """
    import tunggakan as tg
    sel = hari_selisih(row)
    if not mode:
        if sel <= 0:
            return None, None, f"Belum melewati batas pembayaran"
        return tg.render_pesan(teks_custom, row, batas), None, None

    templates = templates if templates is not None else daftar_template()
    if not templates:
        if sel <= 0:
            return None, None, "Belum melewati batas pembayaran"
        return tg.render_pesan(teks_custom, row, batas), None, None
    jendela = jendela or jendela_pengingat()

    if mode == MODE_AUTO:
        tpl, alasan = pilih_otomatis(row, tahap_info[1], templates, jendela)
        if alasan:
            return None, None, alasan
        isi = tpl["isi"]
    else:
        tpl = next((t for t in templates if t["kode"] == mode), None)
        if not tpl:
            return None, None, f"Template {mode} tidak ditemukan/tidak aktif"
        if tpl["tahap"] == 0:
            if sel > 0:
                return None, None, "Pengingat ramah hanya untuk pelanggan yang belum jatuh tempo"
            if not jendela["terbuka"]:
                return None, None, (f"Di luar masa pengingat ramah (tanggal {jendela['mulai']}-{jendela['selesai']})")
        elif sel <= 0:
            return None, None, "Belum melewati batas pembayaran"
        isi = (teks_custom or "").strip() or tpl["isi"]
    return tg.render_pesan(isi, row, batas), tpl["kode"], None


def perlu_konfirmasi_ulang(row: dict, kode: Optional[str], tahap_info, templates: List[dict]) -> bool:
    """Pesan serupa sudah terkirim? Eskalasi ke tahap lebih tinggi TIDAK butuh konfirmasi."""
    if (row.get("wa_status") or "BELUM") != "TERKIRIM":
        return False
    mx_all = tahap_info[0]
    tpl = next((t for t in templates if t["kode"] == kode), None)
    if tpl is None or mx_all is None:
        return True            # perilaku lama / riwayat lama tanpa info tahap
    return mx_all >= tpl["tahap"]


def tandai_tahap(tunggakan_id: int, kode: Optional[str]):
    """Simpan tahap & template terakhir yang berhasil terkirim di baris tunggakan."""
    if not kode or not tabel_siap():
        return
    s = SessionLocal()
    try:
        s.execute(text("UPDATE tunggakan_pelanggan SET tahap_wa=(SELECT tahap FROM wa_template WHERE kode=:k), "
                       "template_terakhir=:k WHERE id=:i"), {"k": kode, "i": tunggakan_id})
        s.commit()
    except Exception as e:
        s.rollback()
        print(f"[TEMPLATE] gagal menandai tahap: {e}")
    finally:
        s.close()


def perkaya_daftar(daftar: List[dict]) -> List[dict]:
    """Tambahkan saran template, tahap terakhir, dan boleh_pengingat ke tiap baris daftar tunggakan."""
    templates = daftar_template()
    if not templates:
        return daftar
    jendela = jendela_pengingat()
    info = tahap_massal([(d["id_pelanggan"], d.get("periode") or "") for d in daftar])
    nama = {t["tahap"]: t for t in templates}
    for d in daftar:
        if d.get("kategori") == "LUNAS":
            d.update(tahap_terakhir=None, tahap_terakhir_nama=None, saran_template=None,
                     saran_template_nama=None, saran_alasan="Sudah lunas", boleh_pengingat=False)
            continue
        ti = info.get((d["id_pelanggan"], d.get("periode") or ""), (None, None))
        tpl, alasan = pilih_otomatis(d, ti[1], templates, jendela)
        d["tahap_terakhir"] = ti[0]
        d["tahap_terakhir_nama"] = nama[ti[0]]["nama"] if ti[0] in nama else None
        d["saran_template"] = tpl["kode"] if tpl else None
        d["saran_template_nama"] = tpl["nama"] if tpl else None
        d["saran_alasan"] = alasan
        d["boleh_pengingat"] = bool(d.get("no_hp")) and d.get("kategori") == "BELUM_JATUH_TEMPO" and bool(tpl and tpl["tahap"] == 0)
    return daftar


# ─────────────────────────────────────────────────────────────
#  Endpoint
# ─────────────────────────────────────────────────────────────
@router.get("")
def lihat_template(admin: dict = Depends(get_current_admin)):
    if not tabel_siap():
        return {"siap": False, "templates": [], "jendela": None}
    return {"siap": True, "templates": daftar_template(hanya_aktif=False), "jendela": jendela_pengingat()}


class TemplateUbah(BaseModel):
    isi: str


@router.put("/{kode}")
def ubah_template(kode: str, body: TemplateUbah, admin: dict = Depends(get_current_admin)):
    if not tabel_siap():
        raise HTTPException(503, "Tabel belum ada. Jalankan swacam_db_migrasi_v2.sql terlebih dahulu.")
    isi = body.isi.strip()
    if len(isi) < 20:
        raise HTTPException(400, "Isi template terlalu pendek.")
    if len(isi) > 3000:
        raise HTTPException(400, "Isi template terlalu panjang (maks 3000 karakter).")
    s = SessionLocal()
    try:
        n = s.execute(text("UPDATE wa_template SET isi=:i, diubah_oleh=:u WHERE kode=:k"),
                      {"i": isi, "u": admin.get("username", "admin"), "k": kode}).rowcount
        s.commit()
        if not n:
            raise HTTPException(404, "Template tidak ditemukan.")
        log_activity(username=admin.get("username", "admin"), role=admin.get("role", "admin"),
                     action="WA_TEMPLATE_DIUBAH", details=f"Template {kode} diperbarui")
        return {"message": f"Template {kode} disimpan."}
    finally:
        s.close()