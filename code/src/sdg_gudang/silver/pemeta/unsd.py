"""Pemeta Silver keluarga UNSD: API basis data SDG global (``unsd``) dan arsip 48 rilis CSV (``unsd_arsip``).

Kedua kanal berformat panjang (satu baris satu observasi). API memberi dimensi sebagai ``dim_<nama>`` dan atribut
``atr_<nama>``; arsip memberi kolom bernama sama tanpa awalan dan ``NA`` untuk dimensi yang tidak berlaku.

- S01: ``GeoAreaCode`` M49 360 -> nasional 9999 (``m49``); kode lain -> di luar. Baris dengan dimensi ``Cities``
  terisi adalah data kota -> di luar tingkat yang dimuat.
- S02: ``TimePeriod`` (arsip) atau ``timePeriodStart`` (API) adalah tahun; akhiran ``.0`` dibuang.
  ``Time_Detail`` (rentang survei seperti ``2015-2017``) tidak mengubah periode: tahun acuan UNSD dipakai apa adanya
  agar kedua kanal sebanding (API tidak membawa ``time_detail``).
- S03: ``NaN``/``NA`` -> kosong; ``N`` dan ``NV`` (tanpa nilai) juga kosong. Nilai batas ``<0.5``, ``<5``, ``>95``
  bukan angka titik -> karantina ``nilai_batas``.
- S04: kode ``Units`` -> ``dim_satuan`` lewat ``SATUAN``. Kelipatan (``_M``, ``_TH``, ``_B``) menjadi faktor.
  ``UnitMultiplier`` hanya bernilai UNIT atau MILLION untuk kode ``_M`` (sudah dihitung pada kode), jadi tidak dipakai
  lagi. Tahun dasar harga konstan diambil dari deskripsi seri, lalu ``BasePeriod``, dan masuk ke ``satuan_id``.
- S05: semua kolom dimensi (termasuk ``Bounds`` arsip) masuk ``rincian``; kode total dari data ada di ``TOTAL``.
  ``Counterpart`` berisi kode negara ISO alfa-2, sehingga ``NA`` di sana adalah Namibia, bukan "tidak berlaku":
  pada API (yang memakai null untuk tidak berlaku) ``NA`` dimensi selalu harfiah; pada arsip ``NA`` Counterpart
  harfiah hanya untuk seri yang memakai dimensi Counterpart (``seri_counterpart``).
  ``Reporting Type`` G (data global, satu-satunya nilai di kedua kanal selain NA) dianggap bawaan; nilai lain (N)
  menjadi rincian.
- S06: ``Indicator``/``indicator`` -> ``kode_global`` (beberapa kode digabung ``|`` berurutan). API memberi
  semua kode seri dalam satu baris; arsip mengulang observasi sekali per kode indikator, jadi kode arsip
  dikumpulkan per (rilis, seri) lewat ``indikator_arsip`` agar kedua kanal memakai konsep yang sama. Baris ulangan
  itu bernilai sama dan disatukan S08.
- S07: ``Nature`` -> sifat lewat ``SIFAT``.
"""
from __future__ import annotations

import re
from functools import lru_cache

from sdg_gudang import referensi as R
from sdg_gudang.akuisisi import inti as A

from .. import inti as S

METADATA = {"seri"}
K = S.SatuanKanonik

#: S07. G (global monitoring data) adalah angka yang dihasilkan lembaga kustodian untuk pemantauan global, biasanya
#: dari data negara yang diolah atau dilengkapi lembaga itu; tidak dinyatakan sebagai model, jadi dicatat estimasi.
SIFAT = {"C": "resmi", "CA": "disesuaikan", "E": "estimasi", "M": "model", "G": "estimasi",
         "N": "tidak_diketahui", "NA": "tidak_diketahui", "": "tidak_diketahui"}

#: S05: kode total per dimensi yang tidak tertangkap penanda umum ``S.rincian`` (_T, TOTAL, ALL, ALLAREA).
#: ANYS = langganan internet "any speed", jumlah semua kelas kecepatan.
TOTAL = {"Sex": {"BOTHSEX"}, "Age": {"ALLAGE"}, "Policy Domains": {"ALLDOMAINS"},
         "Substance use disorders": {"DRUG_TOTAL"}, "Type of speed": {"ANYS"}, "Reporting Type": {"G"}}

#: Kolom arsip yang bukan dimensi (atribut, kode, teks, penunjuk).
BUKAN_DIMENSI = {
    "Freq", "GeoAreaCode", "GeoAreaName", "Goal", "ID", "Indicator", "Nature", "ObservationID", "ReleaseName",
    "ReleaseStatus", "SeriesCode", "SeriesDescription", "SeriesID", "SeriesObservationCount", "Source", "Source Type",
    "Target", "TimePeriod", "Time_Detail", "UnitMultiplier", "Units", "Value", "ValueType", "nomor_baris", "FootNote",
    "BasePeriod", "LowerBound", "UpperBound", "TimeCoverage", "isDSDSeries", "GeoInfoUrl", "Observation Status",
    "Quality degree", "Cities"}
TIDAK_BERLAKU = {None, "", "NA"}
KOSONG_UNSD = {"n", "nv"}

#: S04: kode Units -> (satuan_id, faktor). ``{b}`` diganti tahun dasar (atau dibuang bila tidak dinyatakan).
SATUAN = {
    "PERCENT": ("persen", "1"),
    "PER_POP_U5": ("persen", "1"),  # deskripsi seri: "Proportion of children ... (%)"
    "PER_MARW_20T24Y": ("persen", "1"),  # deskripsi seri: "Proportion of women aged 20-24 ... (%)"
    "NUMBER": ("x_jumlah", "1"),
    "NUM_TH": ("x_jumlah", "1000"),
    "NUM_M": ("x_jumlah", "1000000"),
    "NUM_U5_M": ("jiwa", "1000000"),  # anak balita, juta
    "Ratio": ("x_rasio", "1"),
    "INDEX": ("indeks", "1"),
    "SCORE": ("x_skor", "1"),
    "BOOL": ("x_biner", "1"),
    "TONNES": ("kilogram", "1000"),
    "TONNES_M": ("kilogram", "1000000000"),
    "KG": ("kilogram", "1"),
    "MT_CO2E": ("ton_co2e", "1000000"),
    "KMSQ": ("hektar", "100"),
    "HA_TH": ("ribu_hektar", "1"),
    "T_PER_HA": ("x_kg_per_hektar", "1000"),
    "CUR_LCU": ("x_lcu_berlaku", "1"),
    "CUR_LCU_M": ("x_lcu_berlaku", "1000000"),
    "CU_USD": ("x_usd_berlaku", "1"),
    "CU_USD_M": ("x_usd_berlaku", "1000000"),
    "CU_USD_B": ("x_usd_berlaku", "1000000000"),
    "CON_USD": ("x_usd_konstan{b}", "1"),
    "CON_10USD": ("x_usd_konstan{b}", "1"),  # deskripsi seri: "constant 2010 United States dollars"
    "CON_USD_M": ("x_usd_konstan{b}", "1000000"),
    "CON_PPP_USD": ("x_ppp_konstan{b}", "1"),
    "KG_PER_CON_USD": ("x_kg_per_usd_konstan{b}", "1"),
    "MJ_PER_GDP_CON_PPP_USD": ("x_mj_per_ppp_konstan{b}", "1"),
    "USD/m3": ("x_usd_per_m3", "1"),
    "PER_100_POP": ("x_per_100_penduduk", "1"),
    "PER_1000_POP": ("per_1000_penduduk", "1"),
    "PER_10000_POP": ("x_per_10000_penduduk", "1"),
    "PER_100000_POP": ("x_per_100000_penduduk", "1"),
    "PER_1000000_POP": ("x_per_1000000_penduduk", "1"),
    "PER_1000_LIVE_BIRTHS": ("per_1000_kelahiran_hidup", "1"),
    "PER_100000_LIVE_BIRTHS": ("x_per_100000_kelahiran_hidup", "1"),
    "PER_1000_UNINFECTED_POP": ("x_per_1000_penduduk_tidak_terinfeksi", "1"),
    "W_PER_CAPITA": ("x_watt_per_kapita", "1"),
    "mgr/m^3": ("x_mikrogram_per_m3", "1"),  # deskripsi seri: "micrograms per cubic meter"
    "LTPUREAL": ("x_liter_alkohol_murni_per_kapita", "1"),
    "M3_PER_SEC": ("x_m3_per_detik", "1"),
    "TEU": ("x_teu", "1"),
    "T_KM": ("x_ton_km", "1"),
    "P_KM": ("x_penumpang_km", "1"),
    "NUM_ITEMS_PER_100M2": ("x_item_per_100m2", "1"),
}
_TAHUN_DASAR = re.compile(
    r"(?:constant |of )(\d{4}) (?:united states dollars|international \$|purchasing power parity)", re.IGNORECASE)


def satuan(units: str, deskripsi: str, base: str) -> S.SatuanKanonik:
    """S04: kode Units -> satuan kanonik; tahun dasar dari deskripsi seri, lalu ``BasePeriod``."""
    p = SATUAN.get((units or "").strip())
    if p is None:
        raise S.Karantina("satuan_tidak_dikenal", "S04", repr(units))
    sid, faktor = p
    if "{b}" in sid:
        m = _TAHUN_DASAR.search(deskripsi or "")
        b = m.group(1) if m else (base or "").strip().removesuffix(".0")
        sid = sid.replace("{b}", f"_{b}" if re.fullmatch(r"\d{4}", b) else "")
    return K(sid, faktor)


def nilai(teks):
    """S03 dengan penanda khusus UNSD."""
    t = (teks or "").strip()
    if t.lower() in KOSONG_UNSD:
        raise S.Kosong(f"penanda kosong {t!r}")
    if re.fullmatch(r"[<>≤≥]=?\s*-?[\d.,]+", t):
        raise S.Karantina("nilai_batas", "S03", repr(teks))
    return S.urai_nilai(t)


@lru_cache(maxsize=1)
def seri_counterpart() -> frozenset[str]:
    """Seri arsip yang memakai dimensi Counterpart (ada nilai selain NA/null)."""
    t = A.baca_bronze("unsd_arsip", "data_indonesia").select(["SeriesCode", "Counterpart"]).to_pylist()
    return frozenset(r["SeriesCode"] for r in t if r["Counterpart"] not in TIDAK_BERLAKU)


@lru_cache(maxsize=1)
def indikator_arsip() -> dict[tuple[str, str], str]:
    """(rilis_id, SeriesCode) -> semua kode indikator seri itu pada rilis arsip tersebut."""
    t = A.baca_bronze("unsd_arsip", "data_indonesia").select(["_rilis_id", "SeriesCode", "Indicator"]).to_pylist()
    kumpul: dict[tuple[str, str], set] = {}
    for r in t:
        kumpul.setdefault((r["_rilis_id"], r["SeriesCode"]), set()).add(r["Indicator"] or "")
    return {k: "|".join(sorted(v)) for k, v in kumpul.items()}


def kode_global(teks) -> str:
    return "|".join(sorted({k.strip() for k in str(teks or "").split("|") if k.strip()}))


def _sel(ctx, *, seri, geo, kota, tahun, nilai_teks, units, deskripsi, base, dimensi, nature, indikator,
         na_harfiah=frozenset()):
    teks = {"wilayah": geo, "periode": tahun, "nilai": nilai_teks, "satuan": units}

    def isi():
        if str(geo or "").strip() != "360":
            raise S.DiLuar("bukan_indonesia")
        if kota not in TIDAK_BERLAKU:
            raise S.DiLuar("kota")
        v, desimal = nilai(nilai_teks)
        periode = S.periode_tahun(tahun)
        st = satuan(units, deskripsi, base)
        sifat = SIFAT.get((nature or "").strip())
        if sifat is None:
            raise S.Karantina("sifat_tidak_dikenal", "S07", repr(nature))
        dim = {k: v for k, v in dimensi.items() if v not in TIDAK_BERLAKU or (v == "NA" and k in na_harfiah)}
        return S.obs(seri_kode=seri, **ctx.konsep("unsd", seri, kode_global(indikator)), wilayah_kode=R.NAS,
                     tingkat="nasional", sistem_wilayah="m49", periode=periode, rincian=S.rincian(dim, TOTAL),
                     nilai=S.kali(v, st.faktor), desimal=desimal, satuan_id=st.satuan_id, satuan_sumber=units,
                     faktor_satuan=st.faktor, sifat=sifat, aturan_silver="S01;S02;S03;S04;S05;S06;S07")

    return S.sel(seri, teks, isi)


def data_api(b: dict, ctx: S.Konteks):
    dim = {k.removeprefix("dim_"): v for k, v in b.items() if k.startswith("dim_") and k != "dim_Cities"}
    yield _sel(ctx, seri=b["series"], geo=b["geoAreaCode"], kota=b.get("dim_Cities"), tahun=b["timePeriodStart"],
               nilai_teks=b["value"], units=b["atr_Units"], deskripsi=b["seriesDescription"], base=b["basePeriod"],
               dimensi=dim, nature=b["atr_Nature"], indikator=b["indicator"], na_harfiah=frozenset(dim))


def data_arsip(b: dict, ctx: S.Konteks):
    dim = {k: v for k, v in b.items() if k not in BUKAN_DIMENSI and not k.startswith("_")}
    yield _sel(ctx, seri=b["SeriesCode"], geo=b["GeoAreaCode"], kota=b.get("Cities"), tahun=b["TimePeriod"],
               nilai_teks=b["Value"], units=b["Units"], deskripsi=b["SeriesDescription"], base=b.get("BasePeriod"),
               dimensi=dim, nature=b["Nature"], indikator=indikator_arsip()[(b["_rilis_id"], b["SeriesCode"])],
               na_harfiah={"Counterpart"} if b["SeriesCode"] in seri_counterpart() else frozenset())


def data_indonesia(b: dict, ctx: S.Konteks):
    return data_api(b, ctx) if "series" in b else data_arsip(b, ctx)


TABEL = {"data_indonesia": data_indonesia}
