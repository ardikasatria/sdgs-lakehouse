"""Konektor WHO Global Health Observatory (``who_gho``), Indonesia, indikator SDG tujuan 2, 3, dan 6.

**Aturan cakupan.** Calon indikator dikumpulkan otomatis dari dua daftar resmi WHO: (a) indikator GHO
OData (``/api/Indicator``) yang kode atau namanya memuat "SDG", dan (b) katalog indikator inti
``data.who.int`` (``/api/datadot/ddiindicators``, kolom ``AlternativeCodes`` = kode GHO), yaitu set
indikator SDG kesehatan World Health Statistics. Setiap calon diklasifikasi lewat tabel ``PETA_SDG``
(kode GHO -> kode indikator SDG) atau ``DI_LUAR`` (indikator SDG tujuan lain atau bukan SDG, dengan
alasan). Yang diambil hanya ``PETA_SDG`` dengan tujuan 2, 3, atau 6. Calon yang tidak ada di kedua tabel
dicatat di manifest untuk ditinjau, tidak diambil diam-diam. Tabel disusun dari nama indikator GHO dan
lampiran World Health Statistics; kecocokannya dengan teks lampiran WHS **[BELUM DIPERIKSA]**.

**Jalur data.** (1) GHO OData ``https://ghoapi.azureedge.net/api/<kode>?$filter=SpatialDim eq 'IDN'``.
Rilis per indikator = ``<kode>@<max Date>`` (field ``Date`` per fakta), jenis ``pembaruan_sumber``. WHO
mengumumkan OData ini akan dihentikan sekitar akhir 2025; pada 20 Okt 2026 ``/api/Indicator`` masih
menjawab tetapi setiap kueri fakta memberi HTTP 502. Karena itu jalur bawaan ``otomatis`` mencoba satu
kueri fakta lebih dulu dan, bila gagal, memakai (2) **data.who.int (DATADOT)**: katalog
``ddiindicators`` memberi ``DataExportUri`` (CSV global per indikator di blob WHO) dan ``DataUpdateLast``.
CSV global diunduh, baris ``DIM_GEO_CODE_M49 == 360`` disimpan sebagai ekstrak (sha256 dan ukuran asli
dicatat). Rilis = ``<kode>@<DataUpdateLast>`` jenis ``pembaruan_sumber``; ``Last-Modified`` blob dicatat
sebagai bukti tambahan. Indikator yang tidak ada di DATADOT dicatat sebagai galat jalur.

Bronze: ``fakta`` (OData, satu baris per fakta) atau ``fakta_datadot`` (CSV DATADOT apa adanya; kolom
ukuran seperti ``PERCENT_POP_N`` berbeda antarindikator), dan ``indikator`` (cakupan dengan kode SDG).

Opsi: ``jalur=otomatis|odata|datadot``, ``kode=A,B`` (subset), ``jeda_s=1.0``.
"""
from __future__ import annotations

import csv
import io
import re
import sys
import time

from .. import inti

SUMBER = "who_gho"

ODATA = "https://ghoapi.azureedge.net/api"
DATADOT = "https://data.who.int/api/datadot/ddiindicators"
DATADOT_PARAM = {"sf_provider": "dynamicProvider358"}
NEGARA = "IDN"
M49 = "360"
TUJUAN = ("2", "3", "6")

#: Kode GHO -> kode indikator SDG (tujuan 2, 3, 6).
PETA_SDG = {
    # Tujuan 2
    "NUTSTUNTINGPREV": "2.2.1", "NUTRITION_ANT_HAZ_NE2": "2.2.1",
    "NUTRITION_WH_2": "2.2.2", "NUTOVERWEIGHTPREV": "2.2.2", "NUTRITION_ANT_WHZ_NE2": "2.2.2",
    "NUTRITION_ANAEMIA_REPRODUCTIVEAGE_PREV": "2.2.3",
    # Tujuan 3
    "MDG_0000000026": "3.1.1", "MDG_0000000025": "3.1.2",
    "MDG_0000000007": "3.2.1", "WHOSIS_000003": "3.2.2",
    "SDGHIV": "3.3.1", "SDGHIV1524": "3.3.1", "MDG_0000000020": "3.3.2",
    "SDGMALARIA": "3.3.3", "MALARIA_EST_INCIDENCE": "3.3.3", "SDGHEPHBSAGPRV": "3.3.4", "SDGNTDTREATMENT": "3.3.5",
    "NCDMORT3070": "3.4.1", "SDG_SH_DTH_RNCOM": "3.4.1",
    "SDGSUICIDE": "3.4.2", "MH_12": "3.4.2", "SDG_SH_STA_SCIDEN": "3.4.2",
    "SA_0000001688": "3.5.2",
    "RS_198": "3.6.1", "SDGROADAGE": "3.6.1",
    "SDGFPALL": "3.7.1", "MDG_0000000003": "3.7.2",
    "UHC_INDEX_REPORTED": "3.8.1", "UHC_AVAILABILITY_SCORE": "3.8.1",
    "FINPROTECTION_CATA_TOT_10_POP": "3.8.2", "FINPROTECTION_CATA_TOT_25_POP": "3.8.2",
    "FINPROTECTION_CATA_TOT_10_LEVEL_SH": "3.8.2", "FINPROTECTION_CATA_TOT_25_LEVEL_SH": "3.8.2",
    "FINPROTECTION_CATA_TOT_10_LEVEL_MILLION": "3.8.2", "FINPROTECTION_CATA_TOT_25_LEVEL_MILLION": "3.8.2",
    "FINANCIALHARDSHIP_PROPORTIONOFPOP": "3.8.2", "FINANCIALHARDSHIP_MILLIONOFPOP": "3.8.2",
    "SDGAIRBOD": "3.9.1", "SDGAIRBODA": "3.9.1", "SDGWSHBOD": "3.9.2", "WSH_1": "3.9.2", "SDGPOISON": "3.9.3",
    "SDGTOBACCO": "3.a.1", "M_Est_tob_curr_std": "3.a.1",
    "WHS4_100": "3.b.1", "MCV2": "3.b.1", "PCV3": "3.b.1", "SDGHPVRECEIVED": "3.b.1",
    "SDGODA": "3.b.2", "SDGODA01": "3.b.2", "SDGODA02": "3.b.2", "SDGHEALTHFACILITIESESSENTIALMEDS": "3.b.3",
    "SDGSHP": "3.c.1", "HWF_0001": "3.c.1", "HWF_0006": "3.c.1", "HWF_0010": "3.c.1", "HWF_0014": "3.c.1",
    "SDGIHR": "3.d.1", "SDGIHR2018": "3.d.1", "SDGIHR2021": "3.d.1",
    "AMR_INFECT_ECOLI": "3.d.2", "AMR_INFECT_MRSA": "3.d.2",
    # Tujuan 6
    "WSH_WATER_SAFELY_MANAGED": "6.1.1", "WSH_SANITATION_SAFELY_MANAGED": "6.2.1", "WSH_HYGIENE_BASIC": "6.2.1",
    "WSH_DOMESTIC_WASTE_SAFELY_TREATED": "6.3.1", "SDGODAWS": "6.a.1",
}

#: Calon otomatis yang sengaja tidak diambil.
DI_LUAR = {
    "SDGIPV": "5.2.1 (penunjuk ke SDGIPVLT/SDGIPV12M)", "SDGIPVLT": "5.2.1", "SDGIPV12M": "5.2.1",
    "RHR_NPSV12M": "5.2.2", "SDGDISASTER": "1.5.1/11.5.1/13.1.1", "SDGCONFLICT": "16.1.2",
    "VIOLENCE_HOMICIDERATE": "16.1.1", "SDGPM25": "11.6.2", "PHE_HHAIR_PROP_POP_CLEAN_FUELS": "7.1.2",
    "SDGCODCOMPLETENESS": "17.19.2", "GHED_GGHE-DGGE_SHA2011": "1.a.2",
    "NCD_BMI_30A": "bukan indikator SDG", "NCD_BMI_PLUS2C": "bukan indikator SDG",
    "NCD_HYP_PREVALENCE_A": "bukan indikator SDG", "WHOSIS_000001": "bukan indikator SDG",
    "WHOSIS_000002": "bukan indikator SDG", "GLASSAMC_AWARE": "bukan indikator SDG",
    "VACCINEPREVENTABLE_WILDPOLIO": "bukan indikator SDG", "TB_Notification_agesex_num": "bukan indikator SDG",
    "TB_drs_rr_prct": "bukan indikator SDG", "TB_notif_num": "bukan indikator SDG",
    "TB_rdst_num": "bukan indikator SDG", "SDGOOP": "bukan indikator SDG resmi (proksi lama 3.8.2)",
}


# ---------------------------------------------------------------------------------------------------
# Fungsi murni (diuji luring)
# ---------------------------------------------------------------------------------------------------

def calon_dari_gho(indikator: list[dict]) -> set[str]:
    return {x["IndicatorCode"] for x in indikator
            if re.search("SDG", x.get("IndicatorCode", "") + " " + (x.get("IndicatorName") or ""), re.I)}


def kode_alternatif(s: str | None) -> list[str]:
    """``"MDG_0000000020,20,SDG Indicator 3.3.2,1426"`` -> ``["MDG_0000000020"]``: hanya token berbentuk kode GHO."""
    return [t.strip() for t in (s or "").split(",")
            if re.fullmatch(r"[A-Za-z][A-Za-z0-9_\-]*", t.strip())]


def klasifikasi(calon: set[str]) -> dict:
    ambil = sorted(k for k in calon | set(PETA_SDG) if PETA_SDG.get(k, "x").split(".")[0] in TUJUAN)
    luar = sorted(k for k in calon if k in DI_LUAR)
    tak = sorted(k for k in calon if k not in PETA_SDG and k not in DI_LUAR)
    return {"ambil": ambil, "di_luar": luar, "tak_terklasifikasi": tak}


def max_tanggal(fakta: list[dict], kolom: str = "Date") -> str:
    ts = sorted(str(f.get(kolom)) for f in fakta if f.get(kolom))
    return ts[-1] if ts else ""


def kode_rilis(kode: str, tanggal: str) -> str:
    return f"{kode}@{tanggal.split('.')[0]}" if tanggal else f"{kode}@tanpa_tanggal"


def saring_csv_m49(isi: bytes, m49: str = M49) -> tuple[list[str], list[list[str]]]:
    r = csv.reader(io.StringIO(isi.decode("utf-8-sig"), newline=""))
    header = next(r)
    i = header.index("DIM_GEO_CODE_M49")
    return header, [row for row in r if len(row) > i and row[i] == m49]


def tulis_csv(header: list[str], baris: list[list[str]]) -> bytes:
    s = io.StringIO()
    w = csv.writer(s, lineterminator="\n")
    w.writerow(header)
    w.writerows(baris)
    return s.getvalue().encode("utf-8")


def peta_datadot(nilai: list[dict]) -> dict[str, dict]:
    """Kode GHO -> entri katalog DATADOT (entri pertama yang mempunyai ``DataExportUri``)."""
    out: dict[str, dict] = {}
    for x in nilai:
        for k in kode_alternatif(x.get("AlternativeCodes")):
            if k not in out or (not out[k].get("DataExportUri") and x.get("DataExportUri")):
                out[k] = x
    return out


# ---------------------------------------------------------------------------------------------------
# Jaringan
# ---------------------------------------------------------------------------------------------------

def _log(*a) -> None:
    print("[who_gho]", *a, file=sys.stderr, flush=True)


def _ambil_odata(snap, http, kode, sdg) -> int:
    url = f"{ODATA}/{kode}"
    params = {"$filter": f"SpatialDim eq '{NEGARA}'"}
    fakta, hal = [], 0
    while url:
        r = http.get(url, params=params)
        nama = f"odata/{kode}.json" if hal == 0 else f"odata/{kode}_p{hal}.json"
        snap.simpan(nama, r.content, r.url, indikator=kode)
        js = r.json()
        fakta.extend(js.get("value", []))
        url, params, hal = js.get("@odata.nextLink"), None, hal + 1
    if not fakta:
        snap.catatan.append(f"{kode}: tidak ada fakta Indonesia di OData")
        return 0
    tgl = max_tanggal(fakta)
    rid = snap.tambah_rilis(inti.Rilis(SUMBER, kode_rilis(kode, tgl), "pembaruan_sumber", tgl,
                                       "max field Date fakta GHO OData (Indonesia)", cakupan=f"{kode} (SDG {sdg})"))
    rows = [{k: v for k, v in f.items()} | {"sdg_indikator": sdg} for f in fakta]
    return snap.tulis_bronze("fakta", rows, rid, f"odata/{kode}.json")


def _ambil_datadot(snap, http, kode, sdg, entri) -> int:
    url = entri.get("DataExportUri")
    if not url:
        raise LookupError("tidak ada DataExportUri di katalog DATADOT")
    r = http.get(url)
    header, baris = saring_csv_m49(r.content)
    nama = f"datadot/{entri.get('UrlName')}_{kode}.csv"
    lm = r.headers.get("Last-Modified", "")
    snap.catat_ekstrak(nama, tulis_csv(header, baris), url, inti.sha256_bita(r.content), len(r.content),
                       f"baris DIM_GEO_CODE_M49=={M49} (csv.reader); ditulis ulang csv.writer",
                       indikator=kode, last_modified=lm, etag=r.headers.get("ETag", ""),
                       data_update_last=entri.get("DataUpdateLast") or "")
    if not baris:
        snap.catatan.append(f"{kode}: tidak ada baris Indonesia di CSV DATADOT")
        return 0
    tgl = (entri.get("DataUpdateLast") or "").replace("Z", "")
    bukti = f"DataUpdateLast katalog data.who.int ddiindicators ({entri.get('UrlName')}); Last-Modified blob {lm}"
    rid = snap.tambah_rilis(inti.Rilis(SUMBER, kode_rilis(kode, tgl), "pembaruan_sumber" if tgl else "tanggal_unduh",
                                       tgl or snap.tanggal, bukti, cakupan=f"{kode} (SDG {sdg})"))
    rows = [dict(zip(header, b)) | {"sdg_indikator": sdg} for b in baris]
    return snap.tulis_bronze("fakta_datadot", rows, rid, nama)


def jalankan(snap: inti.Snapshot, opsi: dict) -> dict:
    t0 = time.monotonic()
    http = inti.Http(jeda_s=float(opsi.get("jeda_s", 1.0)), batas_waktu=180)
    r = http.get(f"{ODATA}/Indicator")
    snap.simpan("odata/Indicator.json", r.content, r.url)
    indikator = r.json()["value"]
    nama_gho = {x["IndicatorCode"]: x.get("IndicatorName") for x in indikator}

    dd: list[dict] = []
    skip = 0
    while True:  # katalog DATADOT dibatasi $top=100
        try:
            r = http.get(DATADOT, params=DATADOT_PARAM | {"$top": 100, "$skip": skip})
        except Exception as e:
            snap.tambah_galat("katalog DATADOT", e)
            break
        snap.simpan(f"datadot/ddiindicators_skip{skip:04d}.json", r.content, r.url)
        v = r.json().get("value", [])
        dd.extend(v)
        if len(v) < 100:
            break
        skip += 100
    pdd = peta_datadot(dd)

    k = klasifikasi(calon_dari_gho(indikator) | set(pdd))
    ambil = [x for x in k["ambil"] if not opsi.get("kode") or x in opsi["kode"].split(",")]
    snap.catatan.append(f"calon di luar cakupan: {k['di_luar']}")
    if k["tak_terklasifikasi"]:
        snap.catatan.append(f"calon tak terklasifikasi (tinjau PETA_SDG/DI_LUAR): {k['tak_terklasifikasi']}")
    tidak_di_gho = [x for x in ambil if x not in nama_gho]
    if tidak_di_gho:
        snap.catatan.append(f"kode PETA_SDG tidak ada di daftar Indicator GHO: {tidak_di_gho}")

    jalur = opsi.get("jalur", "otomatis")
    if jalur == "otomatis":
        uji = inti.Http(jeda_s=1.0, coba=2, batas_waktu=60)
        try:
            uji.get(f"{ODATA}/{ambil[0]}", params={"$filter": f"SpatialDim eq '{NEGARA}'", "$top": 1})
            jalur = "odata"
        except Exception as e:
            snap.tambah_galat(f"uji kueri fakta OData {ambil[0]}", e)
            jalur = "datadot"
        _log(f"jalur dipilih: {jalur}")
    snap.catatan.append(f"jalur data: {jalur}")

    baris = 0
    per_kode = {}
    for kode in ambil:
        sdg = PETA_SDG[kode]
        try:
            if jalur == "odata":
                n = _ambil_odata(snap, http, kode, sdg)
            else:
                n = _ambil_datadot(snap, http, kode, sdg, pdd.get(kode, {}))
        except Exception as e:
            snap.tambah_galat(f"{jalur} {kode}", e)
            n = None
        per_kode[kode] = n
        baris += n or 0
        _log(f"{kode} ({sdg}): {n}")
    ada = [kd for kd, n in per_kode.items() if n]
    rows = [{"IndicatorCode": kd, "IndicatorName": nama_gho.get(kd) or (pdd.get(kd) or {}).get("FullName"),
             "sdg_indikator": PETA_SDG[kd], "datadot_id": (pdd.get(kd) or {}).get("UrlName"),
             "jalur": jalur, "baris_indonesia": per_kode[kd]} for kd in ambil]
    if snap.rilis:
        rid = snap.tambah_rilis(inti.Rilis(SUMBER, f"cakupan@{snap.tanggal}", "tanggal_unduh", snap.tanggal,
                                           "daftar cakupan indikator pada tanggal unduh", cakupan="indikator"))
        snap.tulis_bronze("indikator", rows, rid, "odata/Indicator.json")
    return {"jalur": jalur, "dalam_cakupan": len(ambil), "berdata_indonesia": len(ada), "baris_bronze": baris,
            "tanpa_data": sorted(kd for kd, n in per_kode.items() if not n), "detik": round(time.monotonic() - t0)}
