"""
Modul Tagihan Menunggak -> WhatsApp manual via Fonnte.

Alur:
  1. Admin upload file Excel (.xlsx) / CSV berisi data pelanggan.
  2. Sistem membaca file, mendeteksi pelanggan yang MENUNGGAK
     (belum lunas dan sudah melewati tanggal jatuh tempo, default tanggal 20).
  3. Admin melihat daftar di dashboard, lalu menekan tombol "Kirim WA"
     (satu per satu atau banyak sekaligus). TIDAK ADA pengiriman otomatis.
  4. Pesan dikirim lewat Fonnte memakai FONNTE_TOKEN dari file .env.
"""
import csv
import io
import os
import re
import datetime
from typing import Optional, List

import requests
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from sqlalchemy import text
from auth import get_current_admin, get_current_admin_from_query, get_current_user, get_current_user_from_query
from db_handler import SessionLocal, AuthSessionLocal, TunggakanPelanggan, log_activity

router = APIRouter(prefix="/api/tunggakan", tags=["Tagihan Menunggak"])

BATAS_TANGGAL_DEFAULT = int(os.getenv("BATAS_TANGGAL_TUNGGAKAN", "20"))
KONTAK_PLN = os.getenv("KONTAK_PLN", "Contact Center PLN 123")
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_BARIS = 20000

BULAN_ID = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
            "Agustus", "September", "Oktober", "November", "Desember"]

PESAN_DEFAULT = (
    "Yth. Bapak/Ibu Pelanggan PLN, {nama} dengan ID Pelanggan {idpel}.\n\n"
    "Sebagai bentuk pelayanan terbaik, kami mengingatkan bahwa periode pembayaran "
    "tagihan listrik berlangsung setiap tanggal 2 hingga tanggal 20 setiap bulan.\n\n"
    "Kami menghimbau Bapak/Ibu untuk melakukan pembayaran sebelum tanggal 20 melalui "
    "kanal pembayaran resmi seperti PLN Mobile maupun gerai pembayaran lainnya.\n\n"
    "Apabila hingga melewati tanggal 20 tagihan listrik belum diselesaikan, maka sesuai "
    "ketentuan yang berlaku akan dilakukan pemutusan sementara aliran listrik sampai "
    "dengan kewajiban pembayaran dipenuhi.\n\n"
    "Terima kasih atas perhatian dan kerja sama Bapak/Ibu dalam menjaga kelancaran pelayanan kelistrikan.\n\n"
    "Salam hormat,\n"
    "PT PLN (Persero) UID S2JB."
)

PLACEHOLDERS = ["nama", "idpel", "periode", "tagihan", "jatuh_tempo",
                "hari_terlambat", "alamat", "batas_tanggal", "salam", "kontak"]


# ─────────────────────────────────────────────────────────────
#  Helper umum
# ─────────────────────────────────────────────────────────────
def _norm(s) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def _cell_text(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def normalize_wa(phone) -> Optional[str]:
    """Ubah ke format 62xxxxxxxxxx. Return None bila tidak valid."""
    if phone is None:
        return None
    if isinstance(phone, float):
        phone = str(int(phone)) if phone.is_integer() else str(phone)
    digits = "".join(c for c in str(phone) if c.isdigit())
    if not digits:
        return None
    if digits.startswith("0"):
        digits = "62" + digits[1:]
    elif digits.startswith("8"):
        digits = "62" + digits
    if not digits.startswith("62") or not (10 <= len(digits) <= 15):
        return None
    return digits


def _to_number(v) -> Optional[float]:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = re.sub(r"[^\d,.\-]", "", str(v))
    if not s:
        return None
    # format Indonesia: 1.250.000,50  |  format biasa: 1,250,000.50
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".") if len(s.split(",")[-1]) <= 2 else s.replace(",", "")
    elif s.count(".") > 1 or (s.count(".") == 1 and len(s.split(".")[-1]) == 3):
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def _to_date(v) -> Optional[datetime.date]:
    if v is None or v == "":
        return None
    if isinstance(v, datetime.datetime):
        return v.date()
    if isinstance(v, datetime.date):
        return v
    s = str(v).strip().split(" ")[0].split("T")[0]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%Y/%m/%d", "%d.%m.%Y"):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


_BULAN_MAP = {
    "januari": 1, "jan": 1, "februari": 2, "feb": 2, "maret": 3, "mar": 3, "april": 4, "apr": 4,
    "mei": 5, "may": 5, "juni": 6, "jun": 6, "juli": 7, "jul": 7, "agustus": 8, "agu": 8,
    "agt": 8, "agust": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9, "oktober": 10,
    "okt": 10, "oct": 10, "november": 11, "nov": 11, "desember": 12, "des": 12, "dec": 12,
}


def _parse_periode(v):
    """Return (tahun, bulan) atau None."""
    if v is None or v == "":
        return None
    if isinstance(v, (datetime.datetime, datetime.date)):
        return v.year, v.month
    s = str(v).strip().lower()
    m = re.fullmatch(r"(\d{4})[-/.]?(\d{1,2})", s)            # 2026-09 / 202609
    if m and 1 <= int(m.group(2)) <= 12:
        return int(m.group(1)), int(m.group(2))
    m = re.fullmatch(r"(\d{1,2})[-/.](\d{4})", s)              # 09/2026
    if m and 1 <= int(m.group(1)) <= 12:
        return int(m.group(2)), int(m.group(1))
    m = re.fullmatch(r"([a-z]+)[\s\-/.]*(\d{4})", s)           # September 2026
    if m and m.group(1) in _BULAN_MAP:
        return int(m.group(2)), _BULAN_MAP[m.group(1)]
    return None


def _periode_dari_nama(filename: str):
    """Cari bulan (dan tahun bila ada) di nama file, mis. 'Data Agustus 2026.xlsx' -> (2026, 8)."""
    nama = re.sub(r"[^a-z0-9]+", " ", str(filename or "").lower())
    m = re.search(r"\b(" + "|".join(sorted(_BULAN_MAP, key=len, reverse=True)) + r")\b(?:\s+(20\d{2}))?", nama)
    if not m:
        return None
    th = int(m.group(2)) if m.group(2) else None
    return th, _BULAN_MAP[m.group(1)]


def _label_periode(v) -> str:
    p = _parse_periode(v)
    if p:
        return f"{BULAN_ID[p[1] - 1]} {p[0]}"
    return _cell_text(v)


def rupiah(n) -> str:
    if n is None:
        return "-"
    return "Rp " + f"{int(round(n)):,}".replace(",", ".")


# ─────────────────────────────────────────────────────────────
#  Baca file Excel / CSV (format bebas: kolom dikenali dari nama header)
# ─────────────────────────────────────────────────────────────
# Urutan penting: field yang lebih spesifik diperiksa lebih dulu.
FIELD_KEYS = [
    ("tgl_bayar", ["tanggalbayar", "tglbayar", "tanggalpembayaran", "tglpembayaran", "tglbyr",
                   "tanggallunas", "tgllunas", "paiddate"]),
    ("jatuh_tempo", ["jatuhtempo", "tgljatuhtempo", "duedate", "batasbayar", "batasakhir"]),
    ("status", ["statusbayar", "statuspembayaran", "statuspelunasan", "statustunggakan",
                "statustagihan", "status", "keteranganbayar", "pembayaran"]),
    ("tunggakan", ["tunggakan", "tunggak", "sisatagihan", "kekurangan", "outstanding"]),
    ("periode", ["periode", "bulan", "blth"]),
    ("tagihan", ["tagihan", "nominal", "rptag", "totalbayar", "jumlah", "total", "amount", "biaya"]),
    ("no_hp", ["nohp", "nomorhp", "nowa", "nomorwa", "whatsapp", "telepon", "telp", "phone",
               "handphone", "kontak", "hp", "wa"]),
    ("idpel", ["idpel", "idpelanggan", "nopelanggan", "nomorpelanggan", "nopel", "idpelanggan"]),
    ("nama", ["nama", "pelanggan"]),
    ("alamat", ["alamat"]),
]
LABEL_FIELD = {"idpel": "ID Pelanggan", "nama": "Nama", "no_hp": "No. WA/HP", "alamat": "Alamat",
               "periode": "Periode", "tagihan": "Tagihan", "tunggakan": "Tunggakan",
               "status": "Status bayar", "tgl_bayar": "Tanggal bayar", "jatuh_tempo": "Jatuh tempo"}
KECUALI = {"nama": ("foto", "file", "seri"), "tagihan": ("kwh",), "status": ("validasi",)}
KATA_BELUM = ("belum", "tunggak", "unpaid", "nunggak", "tertunda", "outstanding", "kurang")
KATA_LUNAS = ("lunas", "sudah", "paid", "terbayar", "selesai")


def _cocok(norm_header: str, kw: str) -> bool:
    return norm_header == kw if len(kw) <= 3 else kw in norm_header


def _petakan_header(row) -> dict:
    """Return {field: index_kolom} dari satu baris header."""
    heads = [_norm(c) for c in row]
    mapping, dipakai = {}, set()
    for field, kws in FIELD_KEYS:
        for i, h in enumerate(heads):
            if i in dipakai or not h:
                continue
            if field in KECUALI and any(x in h for x in KECUALI[field]):
                continue
            if any(_cocok(h, kw) for kw in kws):
                mapping[field] = i
                dipakai.add(i)
                break
    return mapping


def _header_valid(m: dict) -> bool:
    return ("idpel" in m or "nama" in m) and len(m) >= 2


def _baca_sheets(filename: str, content: bytes) -> List[list]:
    """Return daftar baris per sheet: [rows_sheet1, rows_sheet2, ...]."""
    name = (filename or "").lower()
    if name.endswith(".csv"):
        text = None
        for enc in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                text = content.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        try:
            dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        return [[r for r in csv.reader(io.StringIO(text), dialect)]]
    if name.endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(content), data_only=True, read_only=True)
        return [[list(r) for r in ws.iter_rows(values_only=True)] for ws in wb.worksheets]
    if name.endswith(".xls"):
        raise ValueError("Format .xls lama belum didukung. Buka di Excel lalu simpan sebagai .xlsx.")
    raise ValueError("Format file tidak didukung. Gunakan .xlsx atau .csv")


def analisis_file(filename: str, content: bytes, batas: int, today: datetime.date = None) -> dict:
    """Baca file dan klasifikasikan tiap baris. Tidak menyentuh database.

    Tiap pelanggan yang belum lunas dimasukkan ke hasil['menunggak'] dengan 'kategori':
      - MENUNGGAK            : hari ini sudah melewati tanggal jatuh tempo (tanggal 20)
      - BELUM_JATUH_TEMPO    : belum lunas tetapi belum lewat tanggal jatuh tempo (hanya pemberitahuan)
    """
    today = today or datetime.date.today()
    sheets = _baca_sheets(filename, content)
    if sum(len(x) for x in sheets) > MAX_BARIS:
        raise ValueError(f"Baris terlalu banyak (maksimal {MAX_BARIS}).")

    hasil = {"menunggak": [], "lunas_list": [], "lunas": 0, "kosong": 0, "kolom_terbaca": {}, "peringatan": [],
             "sheet_terbaca": 0}
    status_tak_dikenal = 0
    ada_kolom_status = False
    periode_otomatis = False
    p_file = _periode_dari_nama(filename)

    for rows in sheets:
        hdr_idx, mapping = None, {}
        for i, r in enumerate(rows[:20]):
            m = _petakan_header(r)
            if _header_valid(m) and len(m) > len(mapping):
                hdr_idx, mapping = i, m
        if hdr_idx is None:
            continue
        hasil["sheet_terbaca"] += 1
        head = rows[hdr_idx]
        if not hasil["kolom_terbaca"]:
            hasil["kolom_terbaca"] = {LABEL_FIELD[f]: _cell_text(head[i]) for f, i in mapping.items()}
        if any(k in mapping for k in ("status", "tunggakan", "tgl_bayar")):
            ada_kolom_status = True

        def ambil(row, field):
            i = mapping.get(field)
            return row[i] if i is not None and i < len(row) else None

        for row in rows[hdr_idx + 1:]:
            idpel = _cell_text(ambil(row, "idpel")) or _cell_text(ambil(row, "nama"))
            if not idpel:
                hasil["kosong"] += 1
                continue

            # 1) Sudah lunas atau belum?  (status -> tunggakan -> tanggal bayar -> anggap belum lunas)
            tunggakan = _to_number(ambil(row, "tunggakan"))
            tgl_bayar = _to_date(ambil(row, "tgl_bayar"))
            st = _norm(ambil(row, "status"))
            belum_lunas = None
            if st:
                if any(k in st for k in KATA_BELUM):
                    belum_lunas = True
                elif any(k in st for k in KATA_LUNAS):
                    belum_lunas = False
                else:
                    status_tak_dikenal += 1
            if belum_lunas is None and "tunggakan" in mapping:
                belum_lunas = bool(tunggakan and tunggakan > 0)
            if belum_lunas is None and "tgl_bayar" in mapping:
                belum_lunas = tgl_bayar is None
            if belum_lunas is None:
                belum_lunas = True
            periode_raw = ambil(row, "periode")
            if _parse_periode(periode_raw) is None and not _cell_text(periode_raw):
                # file tidak punya isi Periode: pakai bulan dari nama file, kalau tidak ada pakai bulan ini
                th, bl = p_file if p_file else (None, today.month)
                periode_raw = f"{th or today.year}-{bl:02d}"
                periode_otomatis = True
            if not belum_lunas:
                hasil["lunas"] += 1
                hp_l = ambil(row, "no_hp")
                hasil["lunas_list"].append({
                    "id_pelanggan": idpel,
                    "nama": _cell_text(ambil(row, "nama")) or None,
                    "no_hp": normalize_wa(hp_l),
                    "alamat": _cell_text(ambil(row, "alamat")) or None,
                    "periode": _label_periode(periode_raw) or None,
                    "nominal": _to_number(ambil(row, "tagihan")) or tunggakan,
                    "jatuh_tempo": _to_date(ambil(row, "jatuh_tempo")),
                    "kategori": "LUNAS",
                })
                continue

            # 2) Jatuh tempo (tanggal 20 pada bulan periode, atau kolom Jatuh Tempo)
            due = _to_date(ambil(row, "jatuh_tempo"))
            if due is None:
                p = _parse_periode(periode_raw) or (today.year, today.month)
                try:
                    due = datetime.date(p[0], p[1], batas)
                except ValueError:
                    due = datetime.date(p[0], p[1], 28)

            nominal = tunggakan if (tunggakan and tunggakan > 0) else _to_number(ambil(row, "tagihan"))
            hp_raw = ambil(row, "no_hp")
            hasil["menunggak"].append({
                "id_pelanggan": idpel,
                "nama": _cell_text(ambil(row, "nama")) or None,
                "no_hp": normalize_wa(hp_raw),
                "alamat": _cell_text(ambil(row, "alamat")) or None,
                "periode": _label_periode(periode_raw) or None,
                "nominal": nominal,
                "jatuh_tempo": due,
                "kategori": "MENUNGGAK" if today > due else "BELUM_JATUH_TEMPO",
            })

    if hasil["sheet_terbaca"] == 0:
        raise ValueError("Kolom ID Pelanggan / Nama tidak ditemukan di file ini. "
                         "Pastikan baris judul kolom ada (contoh: ID Pelanggan, Nama, No WA, Tagihan, Status). "
                         "Anda juga bisa memakai template yang disediakan.")
    if not ada_kolom_status:
        hasil["peringatan"].append("File tidak punya kolom Status / Tunggakan / Tanggal Bayar, sehingga semua "
                                   "baris dianggap BELUM LUNAS. Periksa daftar sebelum mengirim.")
    elif status_tak_dikenal:
        hasil["peringatan"].append(f"{status_tak_dikenal} baris punya isi kolom Status yang tidak dikenali "
                                   "(bukan 'lunas'/'belum bayar'); statusnya ditentukan dari kolom lain atau dianggap belum lunas.")
    if periode_otomatis:
        hasil["peringatan"].append("Kolom Periode tidak ada / kosong, jadi data disimpan pada bulan yang terbaca dari nama file "
                                   "(bila tidak ada, bulan ini). Tambahkan kolom Periode agar tepat, contoh: 2026-08.")
    if "Nomor WA/HP" not in hasil["kolom_terbaca"] and "No. WA/HP" not in hasil["kolom_terbaca"]:
        hasil["peringatan"].append("Kolom No. WA/HP tidak ditemukan, pesan belum bisa dikirim.")

    hasil["total_baris"] = len(hasil["menunggak"]) + hasil["lunas"]
    return hasil


# ─────────────────────────────────────────────────────────────
#  Susun pesan & kirim via Fonnte
# ─────────────────────────────────────────────────────────────
def _salam(now: datetime.datetime = None) -> str:
    if now is None:
        try:
            from zoneinfo import ZoneInfo
            now = datetime.datetime.now(ZoneInfo("Asia/Jakarta"))
        except Exception:
            now = datetime.datetime.now()
    h = now.hour
    if 4 <= h < 11:
        return "pagi"
    if 11 <= h < 15:
        return "siang"
    if 15 <= h < 18:
        return "sore"
    return "malam"


def render_pesan(template: Optional[str], row: dict, batas: int = None) -> str:
    template = (template or "").strip() or PESAN_DEFAULT
    jt = row.get("jatuh_tempo")
    nilai = {
        "nama": (row.get("nama") or "Pelanggan").title(),
        "idpel": row.get("id_pelanggan") or "-",
        "periode": row.get("periode") or "-",
        "tagihan": rupiah(row.get("nominal")),
        "jatuh_tempo": jt if isinstance(jt, str) else (jt.strftime("%d-%m-%Y") if jt else "-"),
        "hari_terlambat": str(row.get("hari_terlambat") if row.get("hari_terlambat") is not None else "-"),
        "alamat": row.get("alamat") or "-",
        "batas_tanggal": str(batas or BATAS_TANGGAL_DEFAULT),
        "salam": _salam(),
        "kontak": KONTAK_PLN,
    }
    return re.sub(r"\{(\w+)\}", lambda m: nilai.get(m.group(1), m.group(0)), template)


def kirim_fonnte_detail(phone: str, message: str):
    """Kirim satu pesan WA lewat Fonnte. Return (berhasil, keterangan, id_pesan_fonnte)."""
    token = os.getenv("FONNTE_TOKEN", "").strip()
    if not token:
        return False, "FONNTE_TOKEN belum diisi di file .env", None
    target = normalize_wa(phone)
    if not target:
        return False, "Nomor WA tidak valid", None
    try:
        r = requests.post(
            "https://api.fonnte.com/send",
            headers={"Authorization": token},
            data={"target": target, "message": message, "countryCode": "62"},
            timeout=30,
        )
        try:
            j = r.json()
        except Exception:
            return False, f"Respon Fonnte tidak dikenali (HTTP {r.status_code})", None
        if j.get("status"):
            fid = j.get("id")
            if isinstance(fid, (list, tuple)):
                fid = fid[0] if fid else None
            return True, str(j.get("detail") or "terkirim")[:200], (str(fid)[:60] if fid else None)
        return False, str(j.get("reason") or j.get("detail") or "ditolak Fonnte")[:200], None
    except requests.RequestException as e:
        return False, f"Gagal terhubung ke Fonnte: {e}"[:200], None


def kirim_fonnte(phone: str, message: str):
    """Kirim satu pesan WA lewat Fonnte. Return (berhasil, keterangan)."""
    ok, ket, _ = kirim_fonnte_detail(phone, message)
    return ok, ket


# ─────────────────────────────────────────────────────────────
#  Endpoint API (khusus admin)
# ─────────────────────────────────────────────────────────────
class PesanPayload(BaseModel):
    template: Optional[str] = None
    batas_tanggal: Optional[int] = None
    template_kode: Optional[str] = None   # None = pesan standar lama | 'AUTO' = saran otomatis | kode wa_template


class PreviewPayload(PesanPayload):
    id: int


class KirimPayload(PesanPayload):
    kirim_ulang: bool = False


@router.get("/pesan-default")
def pesan_default(user: dict = Depends(get_current_user)):
    return {
        "template": PESAN_DEFAULT,
        "placeholders": PLACEHOLDERS,
        "batas_tanggal": BATAS_TANGGAL_DEFAULT,
        "token_fonnte_terisi": bool(os.getenv("FONNTE_TOKEN", "").strip()),
    }


@router.get("/template")
def unduh_template(user: dict = Depends(get_current_user_from_query)):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    wb = Workbook()
    ws = wb.active
    ws.title = "Data Pelanggan"
    ws.append(["ID Pelanggan", "Nama", "No WA", "Alamat", "Periode", "Tagihan", "Status"])
    ws.append(["535500409050", "Budi Santoso", "081234567890", "Jl. Merdeka No. 1, Medan", "2026-09", 185000, "Belum Bayar"])
    ws.append(["535500409051", "Siti Aminah", "082198765432", "Jl. Sudirman No. 5, Medan", "2026-09", 240500, "Lunas"])
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1A6FD4")
    for col, w in zip("ABCDEFG", (18, 24, 16, 34, 12, 14, 14)):
        ws.column_dimensions[col].width = w
    ws2 = wb.create_sheet("Petunjuk")
    for line in [
        "Kolom wajib: ID Pelanggan. Agar WA terkirim, isi juga No WA dan Nama.",
        "Kolom Status diisi 'Lunas' atau 'Belum Bayar'. Bisa diganti kolom 'Tunggakan' (nominal) atau 'Tanggal Bayar'.",
        "Kolom opsional: Alamat, Periode (contoh 2026-09 atau September 2026), Tagihan, Jatuh Tempo.",
        f"Pelanggan dianggap menunggak bila belum lunas dan hari ini sudah melewati tanggal {BATAS_TANGGAL_DEFAULT} (atau tanggal pada kolom Jatuh Tempo).",
        "Nama kolom tidak harus persis sama; sistem mengenali variasi seperti 'No HP', 'IDPEL', 'Nama Pelanggan'.",
    ]:
        ws2.append([line])
    ws2.column_dimensions["A"].width = 120
    buf = io.BytesIO()
    wb.save(buf)
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="template_tunggakan_pln.xlsx"'},
    )


@router.post("/upload")
async def upload_tunggakan(
    file: UploadFile = File(...),
    batas_tanggal: Optional[int] = Form(None),
    mode: str = Form("gabung"),          # 'gabung' = data lama dipertahankan | 'ganti' = hapus data lama
    user: dict = Depends(get_current_user),
):
    ganti_total = (mode or "").strip().lower() == "ganti"
    content = await file.read()
    if not content:
        raise HTTPException(400, "File kosong.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(400, "Ukuran file maksimal 5 MB.")
    batas = batas_tanggal if batas_tanggal and 1 <= batas_tanggal <= 31 else BATAS_TANGGAL_DEFAULT
    try:
        hasil = analisis_file(file.filename, content, batas)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(400, f"File tidak bisa dibaca: {e}")

    baru = {}
    for r in hasil["lunas_list"]:           # data lunas ikut disimpan supaya seluruh isi file tampil di dashboard
        baru[(r["id_pelanggan"], r["periode"] or "")] = r
    for r in hasil["menunggak"]:            # bila ada duplikat, yang belum lunas didahulukan
        baru[(r["id_pelanggan"], r["periode"] or "")] = r

    ditambah = diperbarui = dihapus = 0
    s = SessionLocal()
    try:
        lama = {(x.id_pelanggan, x.periode or ""): x for x in s.query(TunggakanPelanggan).all()}
        # Mode 'gabung' (bawaan): data lama TIDAK dihapus. Yang sama (IDPEL + periode) diperbarui,
        # yang baru ditambahkan. Mode 'ganti': data lama yang tidak ada di file baru dihapus.
        if ganti_total:      # hanya periode (bulan) yang ada di file ini yang diganti; bulan lain tidak disentuh
            periode_file = {k[1] for k in baru}
            for key, x in lama.items():
                if key[1] in periode_file and key not in baru:
                    s.delete(x)
                    dihapus += 1
        for key, r in baru.items():
            x = lama.get(key)
            if x:
                diperbarui += 1
            else:
                x = TunggakanPelanggan(id_pelanggan=r["id_pelanggan"], periode=r["periode"], wa_status="BELUM")
                s.add(x)
                ditambah += 1
            x.status_bayar = "LUNAS" if r["kategori"] == "LUNAS" else "BELUM"
            if x.status_bayar == "LUNAS":
                if x.lunas_pada is None:      # catat saat pertama kali terbaca lunas
                    x.lunas_pada = datetime.datetime.now()
            else:
                x.lunas_pada = None
            # nama/no HP/alamat kosong di file baru tidak menimpa isian lama yang sudah ada
            x.nama = r["nama"] or x.nama
            x.no_hp = r["no_hp"] or x.no_hp
            x.alamat = r["alamat"] or x.alamat
            x.nominal = r["nominal"] if r["nominal"] is not None else x.nominal
            x.jatuh_tempo = r["jatuh_tempo"] or x.jatuh_tempo
            x.sumber_file = (file.filename or "")[:150]
            x.diupload_oleh = user.get("username")
            x.diupload_pada = datetime.datetime.now()
        s.commit()
    except Exception as e:
        s.rollback()
        raise HTTPException(500, f"Gagal menyimpan ke database: {e}")
    finally:
        s.close()

    try:
        s2 = SessionLocal()
        total_tersimpan = s2.query(TunggakanPelanggan).count()
        s2.close()
    except Exception:
        total_tersimpan = len(baru)
    semua = [r for r in baru.values() if r["kategori"] != "LUNAS"]
    menunggak = [r for r in semua if r["kategori"] == "MENUNGGAK"]
    belum_jt = [r for r in semua if r["kategori"] == "BELUM_JATUH_TEMPO"]
    tanpa_hp = sum(1 for r in semua if not r["no_hp"])
    hari_ini = datetime.date.today()

    # Pemberitahuan bila belum melewati tanggal batas
    pemberitahuan = None
    if belum_jt:
        terdekat = min(r["jatuh_tempo"] for r in belum_jt)
        sisa = (terdekat - hari_ini).days + 1          # hari sampai tanggal batas terlewati
        pemberitahuan = (
            f"Hari ini tanggal {hari_ini.day}. {len(belum_jt)} pelanggan belum lunas, tetapi belum melewati "
            f"batas pembayaran (tanggal {terdekat.day}). Pesan WA tagihan baru bisa dikirim setelah tanggal "
            f"{terdekat.day} ({sisa} hari lagi, mulai {(terdekat + datetime.timedelta(days=1)).strftime('%d-%m-%Y')})."
        )

    log_activity(username=user.get("username", "user"), role=user.get("role", "petugas"), action="UPLOAD_TUNGGAKAN",
                 details=f"{file.filename}: {len(menunggak)} menunggak, {len(belum_jt)} belum jatuh tempo, "
                         f"{hasil['lunas']} lunas (batas tgl {batas}), mode {'ganti total' if ganti_total else 'gabung'}, "
                         f"+{ditambah} baru, {diperbarui} diperbarui, {dihapus} dihapus")
    return {
        "nama_file": file.filename,
        "batas_tanggal": batas,
        "hari_ini": hari_ini.strftime("%Y-%m-%d"),
        "total_baris": hasil["total_baris"],
        "tersimpan": len(baru),
        "menunggak": len(menunggak),
        "belum_jatuh_tempo": len(belum_jt),
        "lunas": hasil["lunas"],
        "tanpa_nomor_wa": tanpa_hp,
        "ditambahkan": ditambah,
        "diperbarui": diperbarui,
        "dihapus_dari_daftar_lama": dihapus,
        "mode": "ganti" if ganti_total else "gabung",
        "periode_tersimpan": sorted({k[1] for k in baru if k[1]}),
        "total_tersimpan": total_tersimpan,
        "kolom_terbaca": hasil["kolom_terbaca"],
        "sheet_terbaca": hasil["sheet_terbaca"],
        "pemberitahuan": pemberitahuan,
        "peringatan": hasil["peringatan"],
    }


@router.get("")
def daftar_tunggakan(user: dict = Depends(get_current_user)):
    s = SessionLocal()
    try:
        rows = s.query(TunggakanPelanggan).order_by(TunggakanPelanggan.jatuh_tempo.asc(),
                                                    TunggakanPelanggan.id.asc()).all()
        daftar = [r.to_dict() for r in rows]
    finally:
        s.close()
    try:   # saran template + tahap terakhir per pelanggan (butuh swacam_db_migrasi_v2.sql)
        import wa_template
        daftar = wa_template.perkaya_daftar(daftar)
    except Exception as e:
        print(f"[TUNGGAKAN] saran template dilewati: {e}")
    return daftar


def _ambil(s, rid: int) -> TunggakanPelanggan:
    x = s.query(TunggakanPelanggan).filter(TunggakanPelanggan.id == rid).first()
    if not x:
        raise HTTPException(404, "Data tidak ditemukan.")
    return x


@router.post("/preview")
def preview_pesan(payload: PreviewPayload, user: dict = Depends(get_current_user)):
    import wa_template as wt
    s = SessionLocal()
    try:
        x = _ambil(s, payload.id)
        if x.status_bayar == "LUNAS":
            raise HTTPException(400, "Pelanggan ini sudah lunas, tidak perlu dikirimi pesan.")
        ti = wt.tahap_tertinggi(x.id_pelanggan, x.periode or "")
        pesan, kode, alasan = wt.siapkan_pesan(x.to_dict(), payload.template_kode, payload.template,
                                               payload.batas_tanggal, ti)
        if alasan:
            raise HTTPException(400, alasan)
        return {"pesan": pesan, "no_hp": x.no_hp, "template_kode": kode}
    finally:
        s.close()


@router.post("/{rid}/kirim")
def kirim_wa(rid: int, payload: KirimPayload, user: dict = Depends(get_current_user)):
    import wa_antrean
    import wa_template as wt
    s = SessionLocal()
    try:
        x = _ambil(s, rid)
        if x.status_bayar == "LUNAS":
            raise HTTPException(400, "Pelanggan ini sudah lunas, tidak perlu dikirimi pesan.")
        if not x.no_hp:
            raise HTTPException(400, "Nomor WA pelanggan kosong/tidak valid.")
        row = x.to_dict()
        ti = wt.tahap_tertinggi(x.id_pelanggan, x.periode or "")
        templates = wt.daftar_template()
        pesan, kode, alasan = wt.siapkan_pesan(row, payload.template_kode, payload.template,
                                               payload.batas_tanggal, ti, templates)
        if alasan:
            raise HTTPException(400, alasan)
        if wt.perlu_konfirmasi_ulang(row, kode, ti, templates) and not payload.kirim_ulang:
            raise HTTPException(409, "Pesan sudah pernah terkirim ke pelanggan ini.")
        riwayat_id = None
        if wa_antrean.tabel_siap():   # riwayat + jeda minimum antar kirim (butuh swacam_db_migrasi_v2.sql)
            try:
                riwayat_id = wa_antrean.catat_riwayat_awal(row, pesan, user.get("username", "petugas"),
                                                           template_kode=kode)
            except wa_antrean.JedaMinimumError as e:
                raise HTTPException(429, str(e))
        ok, ket, fid = kirim_fonnte_detail(x.no_hp, pesan)
        if riwayat_id:
            wa_antrean.catat_riwayat_hasil(riwayat_id, ok, ket, fid)
        x.wa_status = "TERKIRIM" if ok else "GAGAL"
        x.wa_waktu = datetime.datetime.now()
        x.wa_respon = ket
        if ok:
            x.wa_jumlah_kirim = (x.wa_jumlah_kirim or 0) + 1
        s.commit()
        if ok:
            wt.tandai_tahap(x.id, kode)
        log_activity(username=user.get("username", "petugas"), role=user.get("role", "petugas"),
                     action="WA_TUNGGAKAN_TERKIRIM" if ok else "WA_TUNGGAKAN_GAGAL",
                     details=f"IDPEL {x.id_pelanggan} -> {x.no_hp} [{kode or 'standar'}]: {ket}")
        return {"berhasil": ok, "keterangan": ket, "wa_status": x.wa_status, "template_kode": kode}
    finally:
        s.close()


class UpdateTunggakanPayload(BaseModel):
    nama: Optional[str] = None
    no_hp: Optional[str] = None
    status_bayar: Optional[str] = None   # "LUNAS" | "BELUM"
    nominal: Optional[float] = None
    alamat: Optional[str] = None


@router.put("/{rid}")
def update_tunggakan(rid: int, payload: UpdateTunggakanPayload, user: dict = Depends(get_current_user)):
    """Petugas/Admin: Perbarui informasi pelanggan (Nama, No. WA, Alamat, Nominal) atau Tandai Lunas."""
    s = SessionLocal()
    try:
        x = _ambil(s, rid)
        perubahan = []
        if payload.status_bayar is not None:
            st = payload.status_bayar.upper().strip()
            if st in ("LUNAS", "BELUM"):
                if x.status_bayar != st:
                    x.status_bayar = st
                    if st == "LUNAS":
                        x.lunas_pada = datetime.datetime.now()
                        perubahan.append("Status -> LUNAS")
                    else:
                        x.lunas_pada = None
                        perubahan.append("Status -> BELUM LUNAS")
        if payload.nama is not None:
            nm = payload.nama.strip()
            if nm and nm != x.nama:
                x.nama = nm
                perubahan.append(f"Nama -> {nm}")
        if payload.no_hp is not None:
            hp = normalize_wa(payload.no_hp) or payload.no_hp.strip()
            if hp != x.no_hp:
                x.no_hp = hp
                perubahan.append(f"No WA -> {hp}")
        if payload.nominal is not None:
            if payload.nominal != x.nominal:
                x.nominal = float(payload.nominal)
                perubahan.append(f"Nominal -> {payload.nominal}")
        if payload.alamat is not None:
            x.alamat = payload.alamat.strip()
            perubahan.append("Alamat diperbarui")

        s.commit()
        s.refresh(x)
        row = x.to_dict()

        log_activity(
            username=user.get("username", "petugas"),
            role=user.get("role", "petugas"),
            action="UPDATE_TUNGGAKAN",
            details=f"IDPEL {x.id_pelanggan} diperbarui: {', '.join(perubahan) if perubahan else 'tanpa perubahan'}"
        )
        return {"message": "Data pelanggan berhasil diperbarui.", "data": row}
    except HTTPException:
        raise
    except Exception as e:
        s.rollback()
        raise HTTPException(500, f"Gagal memperbarui data pelanggan: {e}")
    finally:
        s.close()


# ── Sinkronisasi Otomatis dari Hasil Catat Meter (swacam_readings) ───────────
@router.get("/sync-meter/periode")
def list_periode_meter(user: dict = Depends(get_current_user)):
    """Ambil daftar periode bulan yang tersedia di tabel swacam_readings (Catat Meter)."""
    s = AuthSessionLocal()
    try:
        rows = s.execute(text(
            "SELECT COALESCE(periode_bulan, '') AS periode, "
            "COUNT(*) AS total_meter, "
            "SUM(CASE WHEN tagihan_rupiah > 0 THEN 1 ELSE 0 END) AS ada_tagihan, "
            "SUM(COALESCE(tagihan_rupiah, 0)) AS total_nominal "
            "FROM swacam_readings WHERE status_validasi IN ('SUCCESS', 'VALID') "
            "GROUP BY periode_bulan ORDER BY periode_bulan DESC"
        )).mappings().all()
        return [dict(r) for r in rows if r["periode"]]
    except Exception as e:
        raise HTTPException(500, f"Gagal membaca data Catat Meter: {e}")
    finally:
        s.close()


class SyncMeterPayload(BaseModel):
    periode: str
    batas_tanggal: Optional[int] = None
    mode: str = "gabung"   # 'gabung' | 'ganti'


@router.post("/sync-meter")
def sync_dari_catat_meter(payload: SyncMeterPayload, user: dict = Depends(get_current_user)):
    """Tarik data tagihan dari hasil pembacaan meter (Catat Meter) langsung ke tabel penagihan."""
    p_clean = payload.periode.strip()
    if not p_clean:
        raise HTTPException(400, "Periode bulan wajib dipilih.")

    batas = payload.batas_tanggal if payload.batas_tanggal and 1 <= payload.batas_tanggal <= 31 else BATAS_TANGGAL_DEFAULT
    ganti_total = (payload.mode or "").strip().lower() == "ganti"

    # 1. Baca data dari swacam_db.swacam_readings
    auth_s = AuthSessionLocal()
    try:
        readings = auth_s.execute(text(
            "SELECT id_pelanggan, periode_bulan, COALESCE(tagihan_rupiah, 0) AS nominal, "
            "waktu_catat, uploader_username, catatan "
            "FROM swacam_readings "
            "WHERE status_validasi IN ('SUCCESS', 'VALID') AND periode_bulan = :p "
            "AND tagihan_rupiah > 0"
        ), {"p": p_clean}).mappings().all()
    except Exception as e:
        raise HTTPException(500, f"Gagal mengambil data dari Catat Meter: {e}")
    finally:
        auth_s.close()

    if not readings:
        raise HTTPException(404, f"Tidak ada data pembacaan valid dengan tagihan > 0 untuk periode '{p_clean}'.")

    label_per = _label_periode(p_clean) or p_clean
    p_parsed = _parse_periode(p_clean)
    today = datetime.date.today()
    if p_parsed:
        try:
            jt = datetime.date(p_parsed[0], p_parsed[1], batas)
        except ValueError:
            jt = datetime.date(p_parsed[0], p_parsed[1], 28)
    else:
        jt = datetime.date(today.year, today.month, batas)

    ditambah = diperbarui = 0
    s = SessionLocal()
    try:
        if ganti_total:
            s.query(TunggakanPelanggan).filter(TunggakanPelanggan.periode == label_per).delete()

        lama = {(x.id_pelanggan, x.periode or ""): x for x in s.query(TunggakanPelanggan).filter(TunggakanPelanggan.periode == label_per).all()}

        for r in readings:
            idp = str(r["id_pelanggan"]).strip()
            nom = float(r["nominal"] or 0)
            key = (idp, label_per)
            x = lama.get(key)
            if x:
                diperbarui += 1
                x.nominal = nom
                x.jatuh_tempo = jt
                x.sumber_file = f"Catat Meter ({p_clean})"
                x.diupload_oleh = user.get("username")
                x.diupload_pada = datetime.datetime.now()
            else:
                x = TunggakanPelanggan(
                    id_pelanggan=idp,
                    nama=f"Pelanggan {idp}",
                    periode=label_per,
                    nominal=nom,
                    jatuh_tempo=jt,
                    status_bayar="BELUM",
                    wa_status="BELUM",
                    sumber_file=f"Catat Meter ({p_clean})",
                    diupload_oleh=user.get("username"),
                    diupload_pada=datetime.datetime.now()
                )
                s.add(x)
                lama[key] = x
                ditambah += 1

        s.commit()
    except Exception as e:
        s.rollback()
        raise HTTPException(500, f"Gagal menyimpan data sinkronisasi: {e}")
    finally:
        s.close()

    log_activity(
        username=user.get("username", "petugas"),
        role=user.get("role", "petugas"),
        action="SYNC_CATAT_METER",
        details=f"Sinkronisasi periode {label_per}: {len(readings)} tagihan, +{ditambah} baru, {diperbarui} diperbarui."
    )
    return {
        "periode": label_per,
        "total_dibaca": len(readings),
        "ditambahkan": ditambah,
        "diperbarui": diperbarui,
        "mode": "ganti" if ganti_total else "gabung",
        "message": f"Berhasil menarik {len(readings)} data tagihan dari Catat Meter ({label_per})."
    }


class HapusPayload(BaseModel):
    ids: List[int]


@router.post("/hapus-massal")
def hapus_massal(payload: HapusPayload, admin: dict = Depends(get_current_admin)):
    ids = list(dict.fromkeys(payload.ids))
    if not ids:
        raise HTTPException(400, "Belum ada data yang dipilih.")
    if len(ids) > MAX_BARIS:
        raise HTTPException(400, f"Maksimal {MAX_BARIS} data per penghapusan.")
    s = SessionLocal()
    try:
        n = 0
        for i in range(0, len(ids), 500):
            n += (s.query(TunggakanPelanggan).filter(TunggakanPelanggan.id.in_(ids[i:i + 500]))
                  .delete(synchronize_session=False))
        s.commit()
        log_activity(username=admin.get("username", "admin"), role=admin.get("role", "admin"),
                     action="HAPUS_MASSAL_TUNGGAKAN", details=f"{n} baris dihapus dari daftar tunggakan")
        return {"dihapus": n, "message": f"{n} data dihapus."}
    except Exception as e:
        s.rollback()
        raise HTTPException(500, f"Gagal menghapus: {e}")
    finally:
        s.close()


@router.delete("/periode/{periode}")
def hapus_periode(periode: str, admin: dict = Depends(get_current_admin)):
    s = SessionLocal()
    try:
        n = s.query(TunggakanPelanggan).filter(TunggakanPelanggan.periode == periode).delete()
        s.commit()
        log_activity(username=admin.get("username", "admin"), role=admin.get("role", "admin"),
                     action="HAPUS_PERIODE_TUNGGAKAN", details=f"Data {periode}: {n} baris dihapus")
        return {"message": f"Data {periode}: {n} baris dihapus."}
    finally:
        s.close()


@router.delete("/{rid}")
def hapus_satu(rid: int, admin: dict = Depends(get_current_admin)):
    s = SessionLocal()
    try:
        x = _ambil(s, rid)
        info = f"IDPEL {x.id_pelanggan} ({x.nama or '-'}), {x.periode or '-'}"
        s.delete(x)
        s.commit()
        log_activity(username=admin.get("username", "admin"), role=admin.get("role", "admin"),
                     action="HAPUS_TUNGGAKAN", details=info)
        return {"message": "Data dihapus."}
    finally:
        s.close()


@router.delete("")
def hapus_semua(admin: dict = Depends(get_current_admin)):
    s = SessionLocal()
    try:
        n = s.query(TunggakanPelanggan).delete()
        s.commit()
        log_activity(username=admin.get("username", "admin"), role=admin.get("role", "admin"),
                     action="HAPUS_SEMUA_TUNGGAKAN", details=f"{n} baris dihapus (semua bulan)")
        return {"message": f"{n} data dihapus."}
    finally:
        s.close()