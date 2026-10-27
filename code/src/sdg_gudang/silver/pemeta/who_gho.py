"""Pemeta Silver keluarga WHO GHO: ``fakta_datadot`` (CSV data.who.int apa adanya) dan ``fakta`` (GHO OData).

- Seri = kode indikator GHO (``IND_CODE`` DATADOT, ``IndicatorCode`` OData); kode_global = kolom Bronze
  ``sdg_indikator`` (tabel ``PETA_SDG`` konektor). ``indikator`` adalah metadata cakupan.
- S01: DATADOT ``DIM_GEO_CODE_M49`` = 360 bertipe COUNTRY, OData ``SpatialDim`` = IDN bertipe COUNTRY ->
  9999 nasional; lainnya di luar.
- S02: hanya periode tahun tunggal; rentang seperti ``2002-2003`` (survei dua tahun) masuk karantina.
- S03: DATADOT memuat satu kolom ukuran ``*_N`` per indikator (``PERCENT_POP_N``, ``RATE_PER_1000_N``, ...);
  ``*_NL``/``*_NU`` adalah batas interval dan tidak menjadi observasi. Tidak ada kolom ukuran terisi -> kosong.
- S04: satuan dari pasangan (indikator, kolom ukuran) di ``SATUAN``, dicocokkan dengan nama indikator;
  ``PERCENT_POP_N`` dan ``RATE_PER_100_N`` -> persen. Penyebut yang belum ada di dim_satuan memakai id
  lokal ``x_`` di ``TAMBAHAN``. Pasangan lain -> karantina ``satuan_tidak_dikenal``.
- S05: kolom ``DIM_*`` selain geografi, waktu, dan status terbit; ``TOTAL``, kosong, dan kode populasi
  definisi indikator (``TOTAL_INDIKATOR``, contoh ``Y_LT5`` pada kematian balita) = total.
- S07: tidak ada kolom komentar di DATADOT. Sifat dari nama indikator WHO: "model-based" -> model;
  "Estimated/Estimate of" -> estimasi; periode sesudah tahun snapshot (proyeksi, contoh tembakau 2030) ->
  model; selain itu tidak_diketahui. OData: kolom ``Comments`` dengan aturan kata yang sama.
"""
from __future__ import annotations

import re
from functools import lru_cache

from sdg_gudang import referensi as R
from sdg_gudang.akuisisi import inti as A

from .. import inti as S

METADATA = {"indikator"}

BUKAN_DIMENSI = {"DIM_GEO_CODE_M49", "DIM_GEO_CODE_TYPE", "DIM_PUBLISH_STATE_CODE", "DIM_TIME", "DIM_TIME_TYPE"}

#: Kode "semua" per indikator (S05): dimensi yang menyatakan populasi definisi indikator, bukan rincian.
#: ``GHE000000`` = semua sebab (jumlah lima sebab lain sama dengan nilainya); ``GENERALPOPULATION`` = semua umur.
TOTAL_INDIKATOR = {
    "MDG_0000000007": {"DIM_AGE": {"Y_LT5"}},
    "WHOSIS_000003": {"DIM_AGE": {"D_LE27"}},
    "NCDMORT3070": {"DIM_AGE": {"YEARS30-69"}},
    "SDGFPALL": {"DIM_AGE": {"Y15T49"}, "DIM_SEX": {"FEMALE"}},
    "NUTRITION_ANAEMIA_REPRODUCTIVEAGE_PREV": {"DIM_SEX": {"FEMALE"}},
    "MDG_0000000003": {"DIM_SEX": {"FEMALE"}},
    "SDGAIRBODA": {"DIM_DEATH_CAUSE_GHE": {"GHE000000"}},
    "SDGHEPHBSAGPRV": {"DIM_POP_TYPE": {"GENERALPOPULATION"}},
}
TOTAL_UMUM = {"TOTAL", "GENERALPOPULATION"}
#: Padanan ``TOTAL_INDIKATOR`` untuk kode dimensi OData (``Dim1Type`` -> kode).
TOTAL_ODATA = {k: {"SEX": {"SEX_FMLE"}} for k in
               ("MDG_0000000003", "SDGFPALL", "NUTRITION_ANAEMIA_REPRODUCTIVEAGE_PREV")}

#: S04: teks satuan -> satuan lokal ``x_`` (belum ada di dim_satuan; referensi tidak diubah).
TAMBAHAN = {
    "per 1.000 penduduk berisiko": S.SatuanKanonik("x_per_1000_penduduk_berisiko"),
    "per 1.000 penduduk tidak terinfeksi": S.SatuanKanonik("x_per_1000_penduduk_tidak_terinfeksi"),
    "per 1.000 perempuan 10-14 tahun": S.SatuanKanonik("x_per_1000_perempuan_10_14"),
    "per 10.000 penduduk": S.SatuanKanonik("x_per_10000_penduduk"),
    "per 100.000 penduduk": S.SatuanKanonik("x_per_100000_penduduk"),
    "per 100.000 kelahiran hidup": S.SatuanKanonik("x_per_100000_kelahiran_hidup"),
    "liter alkohol murni per kapita": S.SatuanKanonik("x_liter_alkohol_murni_per_kapita"),
    "skor": S.SatuanKanonik("x_skor"),
    "us$ per kapita": S.SatuanKanonik("x_usd_per_kapita"),
    "juta us$ konstan 2024": S.SatuanKanonik("x_usd_konstan_2024", "1000000"),
}
SATUAN_KOLOM = {"PERCENT_POP_N": "persen", "RATE_PER_100_N": "persen"}
#: (indikator, kolom ukuran) -> teks satuan, dari nama indikator WHO (``IndicatorName``).
SATUAN = {
    ("MALARIA_EST_INCIDENCE", "RATE_PER_1000_N"): "per 1.000 penduduk berisiko",
    ("MDG_0000000007", "RATE_PER_1000_N"): "per 1.000 kelahiran hidup",
    ("WHOSIS_000003", "RATE_PER_1000_N"): "per 1.000 kelahiran hidup",
    ("SDGHIV", "RATE_PER_1000_N"): "per 1.000 penduduk tidak terinfeksi",
    **{(k, "RATE_PER_10000_N"): "per 10.000 penduduk" for k in ("HWF_0001", "HWF_0006", "HWF_0010", "HWF_0014")},
    **{(k, "RATE_PER_100000_N"): "per 100.000 penduduk"
       for k in ("MDG_0000000020", "RS_198", "SDGAIRBODA", "SDGPOISON", "SDGSUICIDE", "SDGWSHBOD")},
    ("MDG_0000000026", "RATE_PER_100000_N"): "per 100.000 kelahiran hidup",
    ("SA_0000001688", "RATE_PER_CAPITA_N"): "liter alkohol murni per kapita",
    ("UHC_INDEX_REPORTED", "INDEX_N"): "indeks",
    ("SDGIHR2021", "INDEX_N"): "skor",
    ("SDGNTDTREATMENT", "COUNT_N"): "orang",
    ("SDGODA01", "MONEY_N"): "us$ per kapita",
    ("SDGODAWS", "MONEY_N"): "juta us$ konstan 2024",
}
#: Angka kelahiran remaja (3.7.2): penyebut bergantung pada kelompok umur.
SATUAN_UMUR = {("MDG_0000000003", "Y15T19"): "per 1.000 perempuan 15-19 tahun",
               ("MDG_0000000003", "Y10T14"): "per 1.000 perempuan 10-14 tahun"}


@lru_cache(maxsize=1)
def nama_indikator() -> dict[str, str]:
    try:
        t = A.baca_bronze("who_gho", "indikator")
    except FileNotFoundError:
        return {}
    rows = t.select(["IndicatorCode", "IndicatorName"]).to_pylist()
    return {r["IndicatorCode"]: r["IndicatorName"] or "" for r in rows}


def satuan(kode: str, kolom: str, umur: str = "") -> S.SatuanKanonik:
    teks = SATUAN_UMUR.get((kode, umur)) or SATUAN.get((kode, kolom)) or SATUAN_KOLOM.get(kolom)
    if teks is None:
        raise S.Karantina("satuan_tidak_dikenal", "S04", f"{kode} kolom {kolom}")
    return S.satuan_teks(teks, TAMBAHAN)


def sifat(teks: str, periode: str, snapshot: str) -> str:
    if periode[:4].isdigit() and snapshot[:4].isdigit() and int(periode[:4]) > int(snapshot[:4]):
        return "model"
    t = teks.lower()
    if "model-based" in t or "modelled" in t or "modeled" in t:
        return "model"
    if re.search(r"\bestimated\b|\bestimate of\b", t):
        return "estimasi"
    return "tidak_diketahui"


def rincian(dim: dict, kode: str) -> str:
    total = TOTAL_INDIKATOR.get(kode, {})
    bersih = {k: v for k, v in dim.items() if v is not None and str(v).strip() not in TOTAL_UMUM}
    return S.rincian(bersih, total)


def datadot(b: dict, ctx: S.Konteks):
    kode = (b.get("IND_CODE") or b.get("IND_PER_CODE") or "").strip()
    ukuran = {k: v for k, v in b.items()
              if re.fullmatch(r"[A-Z0-9_]+_N", k) and not k.startswith("DIM_") and (v or "").strip()}
    kolom = next(iter(ukuran), "")
    teks = {"wilayah": b.get("DIM_GEO_CODE_M49"), "periode": b.get("DIM_TIME"),
            "nilai": ukuran.get(kolom), "satuan": kolom}

    def isi():
        if (b.get("DIM_GEO_CODE_TYPE") or "").strip() != "COUNTRY":
            raise S.DiLuar(f"tingkat_{(b.get('DIM_GEO_CODE_TYPE') or 'kosong').lower()}")
        if (b.get("DIM_GEO_CODE_M49") or "").strip() != "360":
            raise S.DiLuar("bukan_indonesia")
        if len(ukuran) > 1:
            raise S.Karantina("ukuran_ganda", "S03", ",".join(sorted(ukuran)))
        nilai, desimal = S.urai_nilai(ukuran.get(kolom))
        if (b.get("DIM_TIME_TYPE") or "YEAR").strip() != "YEAR":
            raise S.Karantina("periode_tidak_terurai", "S02", f"{b.get('DIM_TIME_TYPE')} {b.get('DIM_TIME')!r}")
        periode = S.periode_tahun(b.get("DIM_TIME"))
        st = satuan(kode, kolom, (b.get("DIM_AGE") or "").strip())
        dim = {k: v for k, v in b.items() if k.startswith("DIM_") and k not in BUKAN_DIMENSI}
        nama = nama_indikator().get(kode) or b.get("IND_NAME") or ""
        return S.obs(seri_kode=kode, **ctx.konsep("who_gho", kode, (b.get("sdg_indikator") or "").strip()),
                     wilayah_kode=R.NAS, tingkat="nasional", sistem_wilayah="m49", periode=periode,
                     rincian=rincian(dim, kode), nilai=S.kali(nilai, st.faktor), desimal=desimal,
                     satuan_id=st.satuan_id, satuan_sumber=kolom, faktor_satuan=st.faktor,
                     sifat=sifat(nama, periode, b.get("_snapshot") or ""),
                     aturan_silver="S01;S02;S03;S04;S05;S06;S07")

    yield S.sel(kode, teks, isi)


def _total_odata(v: str) -> bool:
    return bool(re.search(r"_(BTSX|TOT|TOTL|TOTAL)$", v)) or v in TOTAL_UMUM


def odata(b: dict, ctx: S.Konteks):
    kode = (b.get("IndicatorCode") or "").strip()
    teks = {"wilayah": b.get("SpatialDim"), "periode": b.get("TimeDim"), "nilai": b.get("NumericValue"),
            "satuan": ""}

    def isi():
        if (b.get("SpatialDimType") or "").strip() != "COUNTRY":
            raise S.DiLuar(f"tingkat_{(b.get('SpatialDimType') or 'kosong').lower()}")
        if (b.get("SpatialDim") or "").strip() != "IDN":
            raise S.DiLuar("bukan_indonesia")
        nilai, desimal = S.urai_nilai(b.get("NumericValue"))
        if (b.get("TimeDimType") or "YEAR").strip() != "YEAR":
            raise S.Karantina("periode_tidak_terurai", "S02", f"{b.get('TimeDimType')} {b.get('TimeDim')!r}")
        periode = S.periode_tahun(b.get("TimeDim"))
        dim = {}
        for jenis, isi_dim in (("Dim1Type", "Dim1"), ("Dim2Type", "Dim2"), ("Dim3Type", "Dim3"),
                               ("DataSourceDimType", "DataSourceDim")):
            v = (b.get(isi_dim) or "").strip()
            if b.get(jenis) and v and not _total_odata(v):
                dim[b[jenis]] = v
        umur = next((re.sub(r"^AGEGROUP_YEARS(\d+)-(\d+)$", r"Y\1T\2", v) for v in dim.values()
                     if v.startswith("AGEGROUP_")), "")
        teks_satuan = SATUAN_UMUR.get((kode, umur)) or next(
            (t for (k, _), t in SATUAN.items() if k == kode), None)
        nama = nama_indikator().get(kode, "")
        if teks_satuan is None and "(%)" in nama:
            teks_satuan = "persen"
        if teks_satuan is None:
            raise S.Karantina("satuan_tidak_dikenal", "S04", f"{kode} (OData tanpa kolom ukuran)")
        st = S.satuan_teks(teks_satuan, TAMBAHAN)
        komentar = f"{nama} {b.get('Comments') or ''}"
        return S.obs(seri_kode=kode, **ctx.konsep("who_gho", kode, (b.get("sdg_indikator") or "").strip()),
                     wilayah_kode=R.NAS, tingkat="nasional", sistem_wilayah="iso3166_1_alpha3", periode=periode,
                     rincian=S.rincian(dim, TOTAL_ODATA.get(kode, {})), nilai=S.kali(nilai, st.faktor), desimal=desimal,
                     satuan_id=st.satuan_id, satuan_sumber=teks_satuan, faktor_satuan=st.faktor,
                     sifat=sifat(komentar, periode, b.get("_snapshot") or ""),
                     aturan_silver="S01;S02;S03;S04;S05;S06;S07")

    yield S.sel(kode, teks, isi)


TABEL = {"fakta_datadot": datadot, "fakta": odata}
