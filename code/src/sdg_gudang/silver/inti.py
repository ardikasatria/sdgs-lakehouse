"""Kontrak pemeta Silver dan aturan bersama S01-S08.

Pemeta per keluarga sumber (``silver/pemeta/<keluarga>.py``) menyatakan ``TABEL``: peta nama tabel Bronze ke
fungsi ``f(baris: dict, ctx: Konteks) -> Iterable[Sel]``. Setiap ``Sel`` adalah satu sel kandidat dengan
hasilnya: observasi, atau salah satu ``Karantina``, ``Kosong``, ``DiLuar``. Tabel Bronze yang bukan
observasi (katalog, daftar seri, daftar BRS) dinyatakan di ``METADATA`` dan tidak masuk Silver.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from functools import cached_property
from pathlib import Path

from sdg_gudang import referensi as R

AKAR = Path(__file__).resolve().parents[3]
SILVER = AKAR / "data" / "silver" / "gudang"
PADANAN_SERI = AKAR / "config" / "rekonsiliasi" / "padanan_seri.csv"

#: Keluarga sumber (praregistrasi Bagian 2): pasangan dalam satu keluarga adalah rilis x rilis.
KELUARGA = {"bps": "bps", "bps_brs": "bps", "unsd": "unsd", "unsd_arsip": "unsd", "wdi": "wdi",
            "wdi_arsip": "wdi", "ilostat": "ilostat", "who_gho": "who_gho", "bnpb": "bnpb", "sipsn": "sipsn",
            "signsmart": "signsmart", "kkp": "kkp", "gdelt": "gdelt", "rss": "rss", "ccnews": "ccnews"}

KOLOM_OBSERVASI = [
    "sumber", "keluarga", "tabel_bronze", "rilis_id", "seri_kode", "konsep_id", "indikator_id", "kode_global",
    "wilayah_kode", "tingkat", "sistem_wilayah", "periode", "jenis_periode", "bulan_acuan", "rincian",
    "nilai", "desimal", "satuan_id", "satuan_sumber", "faktor_satuan", "sifat", "status_angka", "agregasi", "cakupan_parsial",
    "aturan_silver", "baris_bronze", "_berkas_raw", "_sha256_raw", "_snapshot",
]
KOLOM_KARANTINA = ["sumber", "keluarga", "tabel_bronze", "rilis_id", "seri_kode", "alasan", "aturan", "rincian_galat",
                   "teks_wilayah", "teks_periode", "teks_nilai", "teks_satuan", "baris_bronze", "_berkas_raw",
                   "_sha256_raw", "_snapshot"]

SIFAT = ("resmi", "disesuaikan", "estimasi", "model", "tidak_diketahui")


# ---------------------------------------------------------------------------------------------------
# Hasil sel
# ---------------------------------------------------------------------------------------------------

class Gagal(Exception):
    """Sel kandidat yang tidak menjadi observasi."""


class Karantina(Gagal):
    def __init__(self, alasan: str, aturan: str, rincian: str = ""):
        super().__init__(f"{aturan} {alasan}: {rincian}")
        self.alasan, self.aturan, self.rincian = alasan, aturan, rincian


class Kosong(Gagal):
    """Nilai kosong atau penanda tidak tersedia (S03); dihitung terpisah, bukan karantina."""


class DiLuar(Gagal):
    """Wilayah di luar Indonesia atau tingkat yang tidak dimuat. ``komponen`` (opsional) membawa observasi
    kabupaten/kota yang provinsinya diketahui, sebagai bahan agregasi S09 (``silver/agregasi.py``)."""

    def __init__(self, alasan: str, komponen: dict | None = None):
        super().__init__(alasan)
        self.alasan, self.komponen = alasan, komponen


@dataclass
class Sel:
    """Satu sel kandidat. ``obs`` berisi kolom observasi bila berhasil; ``gagal`` bila tidak. ``teks`` memuat
    teks mentah wilayah, periode, nilai, dan satuan untuk baris karantina."""

    obs: dict | None = None
    gagal: Gagal | None = None
    seri_kode: str = ""
    teks: dict = field(default_factory=dict)


def sel(seri_kode: str, teks: dict, isi) -> Sel:
    """Bungkus pemanggilan pemeta satu sel: ``isi`` adalah fungsi tanpa argumen yang mengembalikan dict
    observasi atau melempar ``Gagal``."""
    try:
        return Sel(obs=isi(), seri_kode=seri_kode, teks=teks)
    except Gagal as g:
        return Sel(gagal=g, seri_kode=seri_kode, teks=teks)


# ---------------------------------------------------------------------------------------------------
# S03 nilai
# ---------------------------------------------------------------------------------------------------

PENANDA_KOSONG = {"", "-", "--", "…", "...", "na", "n/a", "nan", "none", "null", "x", ".."}
_CATATAN = re.compile(r"[*¹²³⁴⁵⁶⁷⁸⁹⁰†‡]+$|\s*\([a-z0-9]\)$", re.I)


def urai_nilai(teks, desimal_koma: bool = False) -> tuple[str, int]:
    """S03: teks nilai -> (desimal kanonik sebagai teks, jumlah desimal tersaji).

    ``desimal_koma`` untuk sumber yang memakai koma desimal dan titik ribuan. Tanpa itu, koma dianggap
    pemisah ribuan hanya bila polanya ribuan (``1,234,567``); koma lain ditolak agar tidak ditebak.
    """
    if teks is None:
        raise Kosong("nilai None")
    t = str(teks).strip().replace(" ", "").replace(" ", "")
    if t.lower() in PENANDA_KOSONG:
        raise Kosong(f"penanda kosong {t!r}")
    t = _CATATAN.sub("", t)
    if desimal_koma:
        t = t.replace(".", "").replace(",", ".")
    elif "," in t:
        if not re.fullmatch(r"-?\d{1,3}(,\d{3})+(\.\d+)?", t):
            raise Karantina("nilai_tidak_terurai", "S03", f"koma ambigu {teks!r}")
        t = t.replace(",", "")
    try:
        d = Decimal(t)
    except InvalidOperation:
        raise Karantina("nilai_tidak_terurai", "S03", repr(teks)) from None
    if not d.is_finite():
        raise Karantina("nilai_tidak_terurai", "S03", repr(teks))
    m = re.fullmatch(r"-?\d*(?:\.(\d*))?(?:[eE][-+]?\d+)?", t)
    desimal = len(m.group(1) or "") if m and "e" not in t.lower() else max(0, -d.as_tuple().exponent)
    return format(d.normalize(), "f") if d != 0 else "0", desimal


def urai_float(nilai) -> tuple[str, int]:
    """S03 untuk nilai yang sudah numerik di payload JSON (desimal dihitung dari representasi terpendek)."""
    if nilai is None or (isinstance(nilai, float) and nilai != nilai):
        raise Kosong("nilai None/NaN")
    return urai_nilai(repr(nilai) if isinstance(nilai, float) else str(nilai))


# ---------------------------------------------------------------------------------------------------
# S02 periode
# ---------------------------------------------------------------------------------------------------

BULAN = {"januari": 1, "februari": 2, "maret": 3, "april": 4, "mei": 5, "juni": 6, "juli": 7, "agustus": 8,
         "september": 9, "oktober": 10, "november": 11, "desember": 12}


def periode_tahun(teks) -> str:
    t = str(teks or "").strip().removesuffix(".0")
    if not re.fullmatch(r"(19|20)\d\d", t):
        raise Karantina("periode_tidak_terurai", "S02", repr(teks))
    return t


# ---------------------------------------------------------------------------------------------------
# S05 rincian
# ---------------------------------------------------------------------------------------------------

def rincian(dimensi: dict, total: dict[str, set] | None = None) -> str:
    """S05: dimensi -> teks kanonik ``k=v;k=v`` berurutan; dimensi bernilai total (menurut ``total`` per
    kolom, atau penanda total umum) dibuang. Semua-total -> ``total``."""
    umum = {"", "total", "_t", "_z", "jumlah", "tidak ada", "semua", "all", "both sexes", "btsx",
            "sex_t", "age_ytotal", "allarea", "all areas", "_x"}
    sisa = []
    for k, v in sorted(dimensi.items()):
        if v is None:
            continue
        vv = str(v).strip()
        if vv.lower() in umum or (total and vv in total.get(k, set())):
            continue
        sisa.append(f"{k}={vv}")
    return ";".join(sisa) or "total"


# ---------------------------------------------------------------------------------------------------
# S01 wilayah dan S04 satuan
# ---------------------------------------------------------------------------------------------------

class Rujukan:
    """Pembungkus ``referensi.Rujukan`` dengan aturan S01: tidak dikenal atau ambigu -> karantina."""

    def __init__(self):
        w, p = R.bangun_wilayah(), R.bangun_padanan()
        self.r = R.Rujukan(w, p, R.bangun_alias(w, p))
        self.provinsi = {x["wilayah_kode"] for x in w if x["tingkat"] == "provinsi"}

    def wilayah(self, sistem: str, teks, periode_kemendagri: str = R.PERIODE_TERKINI) -> int:
        f = {"bps": self.r.dari_bps, "iso3166_2": self.r.dari_iso, "nama": self.r.dari_nama,
             "kemendagri": lambda k: self.r.dari_kemendagri(k, periode_kemendagri)}[sistem]
        try:
            return f(str(teks).strip())
        except R.KodeAmbigu as e:
            raise Karantina("wilayah_ambigu", "S01", str(e)) from None
        except R.KodeTidakDikenal as e:
            raise Karantina("wilayah_tidak_dikenal", "S01", str(e)) from None

    def tingkat(self, kode: int) -> str:
        return "nasional" if kode == R.NAS else "provinsi"


@dataclass(frozen=True)
class SatuanKanonik:
    satuan_id: str
    faktor: str = "1"  # nilai_sumber * faktor = nilai dalam satuan_id


def satuan_teks(teks: str, tambahan: dict[str, SatuanKanonik] | None = None) -> SatuanKanonik:
    """S04: teks satuan sumber -> satuan kanonik ``dim_satuan``. ``tambahan`` = peta per sumber untuk teks yang
    tidak tertangkap pola ``dim_satuan`` (contoh ``Gg CO2e`` -> ton CO2e faktor 1000)."""
    t = re.sub(r"\s+", " ", str(teks or "").strip().lower())
    if tambahan and t in tambahan:
        return tambahan[t]
    try:
        return SatuanKanonik(R.satuan_dari_teks(t).satuan_id)
    except R.KodeTidakDikenal:
        raise Karantina("satuan_tidak_dikenal", "S04", repr(teks)) from None


def kali(nilai: str, faktor: str) -> str:
    if faktor == "1":
        return nilai
    d = Decimal(nilai) * Decimal(faktor)
    return format(d.normalize(), "f") if d != 0 else "0"


# ---------------------------------------------------------------------------------------------------
# S06 konsep
# ---------------------------------------------------------------------------------------------------

@dataclass
class Konteks:
    """Bahan bersama untuk pemeta: rujukan wilayah, katalog indikator, dan padanan seri."""

    @cached_property
    def rujukan(self) -> Rujukan:
        return Rujukan()

    @cached_property
    def indikator(self) -> dict[str, dict]:
        with (R.KELUAR / "dim_indikator.csv").open(encoding="utf-8") as f:
            return {r["indikator_id"]: r for r in csv.DictReader(f)}

    @cached_property
    def padanan(self) -> dict[tuple[str, str], dict]:
        if not PADANAN_SERI.exists():
            return {}
        with PADANAN_SERI.open(encoding="utf-8") as f:
            return {(r["keluarga"], r["seri_kode"]): r for r in csv.DictReader(f)}

    def konsep(self, keluarga: str, seri_kode: str, kode_global: str = "", indikator_id: str = "") -> dict:
        """S06: ``konsep_id`` dari padanan seri, lalu indikator TPB, lalu kode global, lalu seri."""
        p = self.padanan.get((keluarga, seri_kode))
        if p:
            return {"konsep_id": p["konsep_id"], "indikator_id": p.get("indikator_id") or indikator_id,
                    "kode_global": p.get("kode_global") or kode_global}
        if indikator_id and indikator_id in self.indikator:
            return {"konsep_id": indikator_id, "indikator_id": indikator_id, "kode_global": kode_global}
        if kode_global:
            return {"konsep_id": f"global:{kode_global}", "indikator_id": "", "kode_global": kode_global}
        return {"konsep_id": f"seri:{keluarga}:{seri_kode}", "indikator_id": "", "kode_global": ""}


def obs(**kw) -> dict:
    """Observasi dengan kolom bawaan; kolom wajib: seri_kode, wilayah_kode, periode, nilai."""
    bawaan = {"indikator_id": "", "kode_global": "", "tingkat": "provinsi", "sistem_wilayah": "",
              "jenis_periode": "tahun", "bulan_acuan": "", "rincian": "total", "desimal": 0,
              "satuan_id": "", "satuan_sumber": "", "faktor_satuan": "1", "sifat": "tidak_diketahui", "status_angka": "",
              "agregasi": "", "cakupan_parsial": "", "aturan_silver": ""}
    o = bawaan | kw
    o["satuan_id"] = R.ALIAS_SATUAN_LOKAL.get(o["satuan_id"], o["satuan_id"])  # satuan lokal x_ -> dim_satuan
    if o["sifat"] not in SIFAT:
        raise ValueError(f"sifat tidak dikenal: {o['sifat']}")
    return o
