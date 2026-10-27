"""Pemeta Silver keluarga ILOSTAT: satu tabel Bronze per dataflow SDMX-CSV (``df_sdg_*``, ``df_une_deap_sex_age_rt``).

- Seri: kolom ``INDICATOR`` bila ada; SDMX-CSV ILO tidak memuatnya, sehingga seri = id dataflow tanpa ``DF_``
  (``SDG_0852_SEX_AGE_RT``). ``MEASURE`` tidak dipakai karena dua dataflow berbagi ``SDG_0852_RT``.
- kode_global (S06) diurai dari empat karakter kode dataflow ``DF_SDG_<tt i k>_...``: dua karakter tujuan,
  satu target, satu indikator (``0852`` -> 8.5.2, ``1041`` -> 10.4.1, ``08B1`` -> 8.b.1). Huruf di posisi
  pertama menggantikan nol depan tujuan satu digit dan menandai varian seri indikator yang sama, menurut nama
  dataflow di ``metadata/dataflow.json`` raw: ``A871`` (kegiatan ekonomi) lawan ``B871`` (ditambah pekerjaan
  rumah tangga), ``B552/B831/B852/B922/U552`` (definisi ICLS ke-19), ``B821`` (PPP 2021 lawan US$ 2015 pada
  ``0821``), ``T552`` (posisi manajerial seluruhnya lawan manajer senior dan menengah pada ``0552``),
  ``F881/N881`` (cedera fatal/nonfatal). Jadi ``A871`` -> 8.7.1, ``B821`` -> 8.2.1, ``T552`` -> 5.5.2.
  ``DF_UNE_DEAP_SEX_AGE_RT`` (ICLS ke-13, bukan dataflow SDG) -> 8.5.2 lewat ``KODE_GLOBAL``.
- S01: ``REF_AREA`` = ``IDN`` -> 9999 nasional; kode lain di luar.
- S02: ``FREQ`` A -> ``YYYY``; Q -> ``YYYY-Qn`` (triwulan); M -> ``YYYY-MM`` (bulan). Bulan acuan dari
  ``NOTE_SOURCE`` "Data reference period: <bulan>" atau, untuk triwulan dengan catatan "Twice a year: February
  and August", Q1 -> 2 dan Q3 -> 8 (putaran Sakernas Februari dan Agustus).
- S04: ``UNIT_MEASURE`` PT -> persen; SC (skor kepatuhan 8.8.2, skor strategi 8.b.1) -> ``x_skor``; LC
  (mata uang lokal) hanya untuk upah per jam 8.5.1 dengan catatan ``IDR`` -> ``rupiah_per_jam``; lainnya
  karantina. ``UNIT_MULT`` = eksponen 10 dan hanya sah untuk ``UNIT_MEASURE_TYPE`` NB (faktor 10^m).
- S05: dimensi = kolom selain atribut SDMX (SEX, AGE, ECO, OCU, SOC, DSB, ...); ``FREQ`` dan ``MEASURE``
  tidak masuk rincian (periode sudah membedakan frekuensi). Kode "semua" per dataflow di ``TOTAL``.
- S07: SOURCE "ILO - Modelled Estimates" -> model; OBS_STATUS E -> estimasi; survei/sensus nasional
  (``LFS``, ``PC``, ``CLS``, ...) dan "ILO - Social Security Inquiry Database" (data administrasi negara) ->
  resmi; "ILO - Calculations based on ..." (pengodean teks oleh ILO) -> estimasi; lainnya tidak_diketahui.
"""
from __future__ import annotations

import re
from decimal import Decimal

from sdg_gudang import referensi as R

from .. import inti as S

METADATA: set[str] = set()

#: Kolom atribut dan identitas SDMX-CSV ILO; kolom lain (selain ``_*``) adalah dimensi rincian.
BUKAN_DIMENSI = {"DATAFLOW", "REF_AREA", "FREQ", "MEASURE", "INDICATOR", "TIME_PERIOD", "OBS_VALUE",
                 "OBS_STATUS", "UNIT_MEASURE_TYPE", "UNIT_MEASURE", "UNIT_MULT", "SOURCE", "NOTE_SOURCE",
                 "NOTE_INDICATOR", "NOTE_CLASSIF", "DECIMALS", "UPPER_BOUND", "LOWER_BOUND"}

#: Kode "semua" per dataflow (S05), diputuskan dari data. ``SEX_T`` sudah tertangkap penanda total umum.
#: Pada pengangguran ``AGE_YTHADULT_YGE15`` (15+) adalah total; skema umur lain (AGGREGATE, 10YRBANDS,
#: 5YRBANDS) mengulang populasi 15+ dengan kode sendiri dan tetap sebagai rincian, agar satu kode saja yang
#: menjadi ``total``. A871/B871 Indonesia hanya memuat ``AGE_CLDVERSION_Y15-17`` (bukan 5-17): tanpa total.
TOTAL = {
    "SDG_0111_SEX_AGE_RT": {"AGE": {"AGE_YTHADULT_YGE15"}},
    "SDG_0131_SEX_SOC_RT": {"SOC": {"SOC_CONTIG_TOTAL"}},
    "SDG_0831_SEX_ECO_RT": {"ECO": {"ECO_SECTOR_TOTAL"}},
    "SDG_0851_SEX_OCU_NB": {"OCU": {"OCU_SKILL_TOTAL"}},
    "SDG_0852_SEX_AGE_RT": {"AGE": {"AGE_YTHADULT_YGE15"}},
    "SDG_0852_SEX_DSB_RT": {"DSB": {"DSB_STATUS_TOTAL"}},
    "UNE_DEAP_SEX_AGE_RT": {"AGE": {"AGE_YTHADULT_YGE15"}},
}
KODE_GLOBAL = {"UNE_DEAP_SEX_AGE_RT": "8.5.2"}

#: S04: teks satuan yang disusun pemeta -> satuan kanonik. ``x_`` = satuan lokal yang belum ada di dim_satuan.
TAMBAHAN = {"skor": S.SatuanKanonik("x_skor")}
SATUAN_UNIT = {"PT": "persen", "SC": "skor"}


def dataflow(b: dict) -> str:
    """``'ILO:DF_SDG_0852_SEX_AGE_RT(1.0)'`` -> ``'DF_SDG_0852_SEX_AGE_RT'``."""
    m = re.fullmatch(r"(?:[^:]+:)?(DF_[A-Z0-9_]+)(?:\([^)]*\))?", (b.get("DATAFLOW") or "").strip())
    return m.group(1) if m else ""


def kode_global(seri: str) -> str:
    if seri in KODE_GLOBAL:
        return KODE_GLOBAL[seri]
    m = re.fullmatch(r"SDG_([0-9A-Z]{4})_.*", seri)
    if not m:
        return ""
    k = m.group(1)
    tujuan = int(k[1]) if k[0].isalpha() else int(k[:2])
    if not 1 <= tujuan <= 17 or not k[3].isdigit():
        return ""
    return f"{tujuan}.{k[2].lower()}.{k[3]}"


def periode(b: dict) -> dict:
    frek, t = (b.get("FREQ") or "A").strip(), (b.get("TIME_PERIOD") or "").strip()
    catatan = f"{b.get('NOTE_SOURCE') or ''} | {b.get('NOTE_INDICATOR') or ''}"
    m = re.search(r"Data reference period: (\w+)", catatan)
    bulan = {"january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7, "august": 8,
             "september": 9, "october": 10, "november": 11, "december": 12}
    acuan = str(bulan[m.group(1).lower()]) if m and m.group(1).lower() in bulan else ""
    if frek == "A":
        return {"periode": S.periode_tahun(t), "jenis_periode": "tahun", "bulan_acuan": acuan}
    if frek == "Q" and (m := re.fullmatch(r"((?:19|20)\d\d)-?Q([1-4])", t)):
        if not acuan and "February and August" in catatan:
            acuan = {"1": "2", "3": "8"}.get(m.group(2), "")
        return {"periode": f"{m.group(1)}-Q{m.group(2)}", "jenis_periode": "triwulan", "bulan_acuan": acuan}
    if frek == "M" and (m := re.fullmatch(r"((?:19|20)\d\d)-?M?(0[1-9]|1[0-2])", t)):
        return {"periode": f"{m.group(1)}-{m.group(2)}", "jenis_periode": "bulan",
                "bulan_acuan": str(int(m.group(2)))}
    raise S.Karantina("periode_tidak_terurai", "S02", f"FREQ {frek!r} TIME_PERIOD {t!r}")


def satuan(b: dict, seri: str) -> tuple[S.SatuanKanonik, str]:
    jenis, unit = (b.get("UNIT_MEASURE_TYPE") or "").strip(), (b.get("UNIT_MEASURE") or "").strip()
    mult = (b.get("UNIT_MULT") or "0").strip()
    sumber = f"{jenis}/{unit}/UNIT_MULT={mult}"
    teks = SATUAN_UNIT.get(unit, "")
    if unit == "LC" and seri.startswith("SDG_0851_") and "IDR" in (b.get("NOTE_INDICATOR") or ""):
        teks = "rupiah per jam"  # 8.5.1: upah rata-rata per jam, mata uang lokal rupiah
    if not re.fullmatch(r"-?\d+", mult) or (mult != "0" and jenis != "NB"):
        raise S.Karantina("satuan_tidak_dikenal", "S04", f"UNIT_MULT {mult!r} pada {jenis}")
    st = S.satuan_teks(teks or sumber, TAMBAHAN)
    if mult == "0":
        return st, sumber
    return S.SatuanKanonik(st.satuan_id, S.kali(st.faktor, format(Decimal(10) ** int(mult), "f"))), sumber


def sifat(b: dict) -> str:
    src = (b.get("SOURCE") or "").strip()
    if "Modelled Estimates" in src:
        return "model"
    if (b.get("OBS_STATUS") or "").strip() == "E":
        return "estimasi"
    if re.match(r"[A-Z]+ - ", src) and not src.startswith("ILO "):
        return "resmi"
    if src.startswith("ILO - Social Security Inquiry"):
        return "resmi"
    if src.startswith("ILO - Calculations"):
        return "estimasi"
    return "tidak_diketahui"


def observasi(b: dict, ctx: S.Konteks):
    df = dataflow(b)
    seri = (b.get("INDICATOR") or "").strip() or df.removeprefix("DF_")
    teks = {"wilayah": b.get("REF_AREA"), "periode": f"{b.get('FREQ')} {b.get('TIME_PERIOD')}",
            "nilai": b.get("OBS_VALUE"), "satuan": f"{b.get('UNIT_MEASURE_TYPE')}/{b.get('UNIT_MEASURE')}"}

    def isi():
        if not seri:
            raise S.Karantina("seri_tidak_dikenal", "S06", f"DATAFLOW {b.get('DATAFLOW')!r}")
        area = (b.get("REF_AREA") or "").strip()
        if area != "IDN":
            raise S.DiLuar("bukan_indonesia")
        nilai, desimal = S.urai_nilai(b.get("OBS_VALUE"))
        p = periode(b)
        st, satuan_sumber = satuan(b, seri)
        dim = {k: v for k, v in b.items() if k not in BUKAN_DIMENSI and not k.startswith("_")}
        return S.obs(seri_kode=seri, **ctx.konsep("ilostat", seri, kode_global(df.removeprefix("DF_") or seri)),
                     wilayah_kode=R.NAS, tingkat="nasional", sistem_wilayah="iso3166_1_alpha3", **p,
                     rincian=S.rincian(dim, TOTAL.get(df.removeprefix("DF_"), {})),
                     nilai=S.kali(nilai, st.faktor), desimal=desimal, satuan_id=st.satuan_id,
                     satuan_sumber=satuan_sumber, faktor_satuan=st.faktor, sifat=sifat(b),
                     aturan_silver="S01;S02;S03;S04;S05;S06;S07")

    yield S.sel(seri, teks, isi)


TABEL = {"*": observasi}
