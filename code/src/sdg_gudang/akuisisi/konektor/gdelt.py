"""Konektor GDELT 2.0 Global Knowledge Graph (``gdelt``): penemuan URL berita media Indonesia untuk alur
klaim M5 (brief 4 Bagian 2.6 dan 5.2). Hanya metadata dan URL; GDELT tidak menyimpan teks artikel.

Dua jalur (opsi ``jalur=bq|berkas``):

1. **BigQuery** ``gdelt-bq.gdeltv2.gkg_partitioned``, disaring ``_PARTITIONTIME`` (partisi harian UTC),
   ``SourceCommonName`` dalam daftar domain, dan opsional ``V2Themes`` memuat tema (``tema=WB_,UNGP_`` atau
   ``tema=bawaan``). Biaya dihitung lebih dulu dengan *dry run*; jalan ditolak bila bita yang diproses
   melebihi ``maks_gb`` (bawaan 5 GB = 5e9 bita), dan kueri sebenarnya memakai ``maximum_bytes_billed`` yang
   sama sebagai pagar kedua. Saringan domain dan tema **tidak** mengurangi bita yang dipindai (tabel tidak
   dikluster); hanya rentang partisi dan kolom yang dipilih yang menentukan biaya. Raw = hasil kueri sebagai
   JSONL (kolom GKGRECORDID, DATE, SourceCommonName, DocumentIdentifier, V2Themes dipotong, TranslationInfo)
   ditambah teks SQL dan parameternya.
2. **Berkas GKG mentah** ``https://data.gdeltproject.org/gdeltv2/YYYYMMDDHHMMSS[.translation].gkg.csv.zip``
   (15 menit; sejak Okt 2026 alamat ``http://`` dialihkan 301 ke ``https://``, dan URL ``http://`` di
   masterfilelist dinormalkan ke ``https://``). Daftar berkas dari ``masterfilelist[-translation].txt``
   (dialirkan; baris dalam rentang tanggal disimpan sebagai ekstrak dengan sha256 daftar asli), md5 setiap zip
   diperiksa terhadap daftar. Zip dialirkan ke berkas sementara, baris domain terpilih diambil, lalu zip
   dibuang; dengan ``pekerja=N`` sampai N zip satu hari diunduh dan disaring bersamaan (satu klien HTTP per
   utas, jeda per utas), dan hasilnya digabung menurut cap waktu sehingga ekstrak sama dengan jalan berurutan.
   Penyempitnya jaringan, bukan CPU (ukuran 21 Okt 2026: buka zip dan saring sekitar 95 MB zip/s per inti),
   sehingga utas cukup dan Spark tidak dipakai (brief 4 Bagian 3.5). Ekstrak per hari UTC per
   aliran ``gkg/<aliran>/<YYYYMMDD>.jsonl`` memakai kolom yang sama dengan jalur BigQuery; ``sha256_asli``
   ekstrak adalah sidik gabungan (sha256 atas baris ``<url> <sha256>`` terurut) dan setiap zip asal dicatat di
   ``asal`` (``<cap waktu> <sha256> <bita>``).

Rilis: BigQuery ``bq/<mulai>_<sampai>@<sha12>`` (``tanggal_unduh``); berkas ``gkg/<aliran>/<YYYYMMDD>@<sha12>``
(``pembaruan_sumber``, tanggal = cap waktu berkas 15 menit terakhir hari itu). Bronze ``artikel``: url,
judul (kosong), tanggal_terbit (DATE GDELT, UTC; ini waktu GDELT melihat artikel, bukan tanggal terbit
media), media, bahasa (dari ``srclc`` TranslationInfo; kosong = aliran Inggris), tema (nama tema unik,
dipotong), gkg_id, aliran, jenis_tanggal='gdelt_date', sumber_penemuan='gdelt'. Kelas A (ketentuan GDELT:
pemakaian bebas dengan sitasi) tetapi tidak ditayangkan karena metadata berita.

Opsi: ``jalur=bq|berkas`` (bawaan bq), ``mulai=YYYY-MM-DD``, ``sampai=YYYY-MM-DD`` (bawaan kemarin UTC),
``domain=..``/``domain_tambah=..``, ``semua_id=1``, ``tema=..``, ``maks_gb=5``, ``estimasi=1`` (hanya
taksiran), ``proyek=<GCP project>`` (jalur bq), ``aliran=translation,english`` dan ``daftar=master|langsung``
dan ``maks_berkas=2000`` dan ``pekerja=1`` (1–16; jalur berkas), ``lanjut=0``, ``jeda_s=1.0``.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import re
import sys
import tempfile
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor
from typing import Iterator

from .. import inti
from . import berita_umum as U

SUMBER = "gdelt"

TABEL_BQ = "gdelt-bq.gdeltv2.gkg_partitioned"
DATA = "https://data.gdeltproject.org/gdeltv2"
MAKS_PEKERJA = 16
MASTER = {"english": f"{DATA}/masterfilelist.txt", "translation": f"{DATA}/masterfilelist-translation.txt"}
TEMA_BAWAAN = ("WB_", "UNGP_", "ECON_", "POVERTY", "UNEMPLOYMENT")
MAKS_TEMA_RAW = 2000

#: Kolom GKG 2.1 (codebook GDELT GKG V2.1), indeks berbasis 0.
KOLOM_GKG = ("GKGRECORDID", "DATE", "SourceCollectionIdentifier", "SourceCommonName", "DocumentIdentifier",
             "Counts", "V2Counts", "Themes", "V2Themes", "Locations", "V2Locations", "Persons", "V2Persons",
             "Organizations", "V2Organizations", "V2Tone", "Dates", "GCAM", "SharingImage", "RelatedImages",
             "SocialImageEmbeds", "SocialVideoEmbeds", "Quotations", "AllNames", "Amounts", "TranslationInfo",
             "Extras")
I = {k: i for i, k in enumerate(KOLOM_GKG)}
#: Kolom yang disimpan (raw jalur bq dan ekstrak jalur berkas). Nama orang, kutipan, dan GCAM tidak diambil.
KOLOM_SIMPAN = ("GKGRECORDID", "DATE", "SourceCommonName", "DocumentIdentifier", "V2Themes", "TranslationInfo")
POLA_BERKAS = re.compile(r"/(\d{14})\.(translation\.)?gkg\.csv\.zip$")


# ---------------------------------------------------------------------------------------------------
# Fungsi murni (diuji luring)
# ---------------------------------------------------------------------------------------------------

def _tanggal(s: str) -> dt.date:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s or ""):
        raise ValueError(f"tanggal harus YYYY-MM-DD: {s!r}")
    return dt.date.fromisoformat(s)


def daftar_tema(opsi_tema: str | None) -> list[str]:
    if not opsi_tema:
        return []
    if opsi_tema.strip() == "bawaan":
        return list(TEMA_BAWAAN)
    tema = [t.strip().upper() for t in opsi_tema.split(",") if t.strip()]
    for t in tema:
        if not re.fullmatch(r"[A-Z0-9_]+", t):
            raise ValueError(f"tema tidak sah: {t!r}")
    return tema


def pola_tema(tema: list[str]) -> str:
    """Regex (RE2 dan Python) yang cocok bila salah satu nama tema di V2Themes diawali salah satu ``tema``."""
    return "(?:^|;)(?:" + "|".join(re.escape(t) for t in tema) + ")" if tema else ""


def sql_bq(mulai: str, sampai: str, domain: list[str], tema: list[str] | None = None,
           semua_id: bool = False, maks_tema: int = MAKS_TEMA_RAW) -> tuple[str, dict]:
    """SQL berparameter dan nilai parameternya. Rentang partisi ``[mulai, sampai]`` inklusif (hari UTC)."""
    a, b = _tanggal(mulai), _tanggal(sampai)
    if a > b:
        raise ValueError("mulai setelah sampai")
    if not domain:
        raise ValueError("daftar domain kosong")
    syarat_domain = ["LOWER(SourceCommonName) IN UNNEST(@domain)",
                     "EXISTS (SELECT 1 FROM UNNEST(@domain) AS d WHERE ENDS_WITH(LOWER(SourceCommonName), CONCAT('.', d)))"]
    if semua_id:
        syarat_domain.append("ENDS_WITH(LOWER(SourceCommonName), '.id')")
    sql = (f"SELECT GKGRECORDID, DATE, SourceCommonName, DocumentIdentifier,\n"
           f"  SUBSTR(V2Themes, 1, {int(maks_tema)}) AS V2Themes, TranslationInfo\n"
           f"FROM `{TABEL_BQ}`\n"
           f"WHERE _PARTITIONTIME >= TIMESTAMP(@mulai)\n"
           f"  AND _PARTITIONTIME < TIMESTAMP_ADD(TIMESTAMP(@sampai), INTERVAL 1 DAY)\n"
           f"  AND ({' OR '.join(syarat_domain)})\n")
    param = {"mulai": a.isoformat(), "sampai": b.isoformat(), "domain": sorted(d.lower() for d in domain)}
    if tema:
        sql += "  AND REGEXP_CONTAINS(V2Themes, @pola_tema)\n"
        param["pola_tema"] = pola_tema(tema)
    sql += "ORDER BY DATE, DocumentIdentifier"
    return sql, param


def taksiran(bita: int, maks_gb: float) -> dict:
    return {"bita_diproses": int(bita), "gb": round(bita / 1e9, 3), "maks_gb": maks_gb,
            "melebihi": bita > maks_gb * 1e9}


def saring_baris_gkg(kolom: list[str], domain, semua_id: bool = False, pola: str = "") -> dict | None:
    """Baris GKG (sudah dipecah tab) -> dict ``KOLOM_SIMPAN`` bila domain (dan tema) cocok, selain itu None."""
    if len(kolom) <= I["DocumentIdentifier"]:
        return None
    sumber = kolom[I["SourceCommonName"]].strip()
    if not (U.cocok_domain(sumber, domain, semua_id) or U.cocok_domain(U.host(kolom[I["DocumentIdentifier"]]),
                                                                         domain, semua_id)):
        return None
    tema = kolom[I["V2Themes"]] if len(kolom) > I["V2Themes"] else ""
    if pola and not re.search(pola, tema):
        return None
    ambil = lambda k: kolom[I[k]] if len(kolom) > I[k] else ""  # noqa: E731
    return {"GKGRECORDID": ambil("GKGRECORDID"), "DATE": ambil("DATE"), "SourceCommonName": sumber,
            "DocumentIdentifier": ambil("DocumentIdentifier"), "V2Themes": tema[:MAKS_TEMA_RAW],
            "TranslationInfo": ambil("TranslationInfo")}


def saring_csv_gkg(baris, domain, semua_id: bool = False, pola: str = "") -> list[dict]:
    """Saring aliran baris teks CSV GKG (tab) -> daftar dict ``KOLOM_SIMPAN``."""
    out = []
    for b in baris:
        r = saring_baris_gkg(b.rstrip("\r\n").split("\t"), domain, semua_id, pola)
        if r:
            out.append(r)
    return out


def bahasa_gdelt(info: str | None) -> str:
    """``srclc:ind;eng:GT-IND 1.0`` -> ``id``; kosong (aliran Inggris) -> ``en``."""
    m = re.search(r"srclc:([A-Za-z]+)", info or "")
    return U.bahasa_baku(m.group(1)) if m else "en"


def tema_ringkas(v2: str | None, maks: int = U.PANJANG_TEMA) -> str:
    """``WB_1_X,12;ECON_Y,40;WB_1_X,90`` -> ``WB_1_X;ECON_Y`` (unik, urutan pertama), dipotong pada batas tema."""
    out: list[str] = []
    for bagian in (v2 or "").split(";"):
        t = bagian.split(",", 1)[0].strip()
        if not t or t in out:
            continue
        if len(";".join(out + [t])) > maks:
            break
        out.append(t)
    return ";".join(out)


def baris_artikel(r: dict, aliran: str) -> dict:
    url = str(r.get("DocumentIdentifier") or "").strip()
    h = U.host(url) or str(r.get("SourceCommonName") or "").lower()
    return {"url": url, "judul": "", "tanggal_terbit": U.tanggal_gdelt(r.get("DATE")),
            "media": U.cocok_domain(h, U.DOMAIN_ID, semua_id=True) or str(r.get("SourceCommonName") or h).lower(),
            "bahasa": bahasa_gdelt(r.get("TranslationInfo")), "tema": tema_ringkas(r.get("V2Themes")),
            "gkg_id": str(r.get("GKGRECORDID") or ""), "aliran": aliran, "jenis_tanggal": "gdelt_date",
            "sumber_penemuan": SUMBER}


def baris_bronze(rows: list[dict], aliran: str) -> list[dict]:
    return U.periksa_panjang([baris_artikel(r, aliran) | {"_urutan": i} for i, r in enumerate(rows, start=1)])


def urai_master(baris, mulai: str, sampai: str) -> list[dict]:
    """Baris ``<bita> <md5> <url>`` masterfilelist -> berkas GKG dalam rentang hari UTC ``[mulai, sampai]``."""
    a, b = _tanggal(mulai).strftime("%Y%m%d"), _tanggal(sampai).strftime("%Y%m%d")
    out = []
    for x in baris:
        bagian = x.strip().split()
        if len(bagian) != 3:
            continue
        m = POLA_BERKAS.search(bagian[2])
        if m and a <= m.group(1)[:8] <= b:
            url = re.sub(r"^http://data\.gdeltproject\.org/gdeltv2", DATA, bagian[2])
            out.append({"url": url, "bita": int(bagian[0]) if bagian[0].isdigit() else None,
                        "md5": bagian[1], "waktu": m.group(1),
                        "aliran": "translation" if m.group(2) else "english"})
    return out


def berkas_langsung(mulai: str, sampai: str, aliran: str) -> list[dict]:
    """Daftar berkas 15 menit tanpa masterfilelist (tanpa md5 dan ukuran)."""
    a, b = _tanggal(mulai), _tanggal(sampai)
    out, t = [], dt.datetime(a.year, a.month, a.day)
    while t.date() <= b:
        w = t.strftime("%Y%m%d%H%M%S")
        out.append({"url": f"{DATA}/{w}.{'translation.' if aliran == 'translation' else ''}gkg.csv.zip",
                    "bita": None, "md5": "", "waktu": w, "aliran": aliran})
        t += dt.timedelta(minutes=15)
    return out


def sidik_gabungan(asal: list[dict]) -> str:
    return inti.sha256_bita("\n".join(sorted(f"{a['url']} {a['sha256']}" for a in asal)).encode("utf-8"))


def kode_rilis_bq(mulai: str, sampai: str, sha: str) -> str:
    return f"bq/{mulai}_{sampai}@{sha[:12]}"


def kode_rilis_hari(aliran: str, hari: str, sha: str) -> str:
    return f"gkg/{aliran}/{hari}@{sha[:12]}"


# ---------------------------------------------------------------------------------------------------
# Jaringan
# ---------------------------------------------------------------------------------------------------

def _log(pesan: str) -> None:
    print(f"[gdelt] {pesan}", file=sys.stderr, flush=True)


def _rentang(opsi: dict) -> tuple[str, str]:
    kemarin = (dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)).isoformat()
    sampai = opsi.get("sampai") or kemarin
    return opsi.get("mulai") or sampai, sampai


def _bq(snap: inti.Snapshot, opsi: dict, domain: list[str], tema: list[str]) -> dict:
    try:
        from google.cloud import bigquery
    except ImportError as e:
        raise RuntimeError("jalur bq memerlukan paket google-cloud-bigquery (pip install google-cloud-bigquery) "
                           "dan kredensial (gcloud auth application-default login atau "
                           "GOOGLE_APPLICATION_CREDENTIALS)") from e
    mulai, sampai = _rentang(opsi)
    awal = f"bq/{mulai}_{sampai}"
    if f"{awal}.jsonl" in snap.berkas:  # diperiksa sebelum kueri berbiaya
        raise RuntimeError(f"{awal} sudah tercatat di snapshot {snap.tanggal}; pakai lanjut=0 untuk mengulang")
    maks_gb = float(opsi.get("maks_gb", 5))
    sql, param = sql_bq(mulai, sampai, domain, tema, semua_id=opsi.get("semua_id") == "1")
    qp = [bigquery.ArrayQueryParameter(k, "STRING", v) if isinstance(v, list)
          else bigquery.ScalarQueryParameter(k, "STRING", v) for k, v in param.items()]
    client = bigquery.Client(project=opsi.get("proyek") or None)
    kering = client.query(sql, job_config=bigquery.QueryJobConfig(dry_run=True, use_query_cache=False,
                                                                  query_parameters=qp))
    est = taksiran(kering.total_bytes_processed or 0, maks_gb)
    snap.catatan.append({"apa": "taksiran BigQuery (dry run)", "rentang": [mulai, sampai]} | est)
    _log(f"dry run: {est['gb']} GB diproses (batas {maks_gb} GB)")
    if est["melebihi"]:
        raise RuntimeError(f"kueri memproses {est['gb']} GB > maks_gb={maks_gb}; persempit rentang tanggal "
                           f"atau naikkan maks_gb secara sadar")
    if opsi.get("estimasi") == "1":
        return {"estimasi": est}
    job = client.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=qp,
                                                               maximum_bytes_billed=int(maks_gb * 1e9)))
    rows = [{k: ("" if r.get(k) is None else str(r.get(k))) for k in KOLOM_SIMPAN} for r in job.result()]
    for r in rows:
        r["V2Themes"] = r["V2Themes"][:MAKS_TEMA_RAW]
    snap.simpan(f"{awal}.sql", (sql + "\n-- parameter\n-- " + json.dumps(param, sort_keys=True) + "\n").encode("utf-8"),
                f"bigquery://{TABEL_BQ}")
    isi = U.jsonl(rows)
    sha = snap.simpan(f"{awal}.jsonl", isi, f"bigquery://{TABEL_BQ}", job_id=job.job_id,
                      bita_diproses=job.total_bytes_processed, bita_ditagih=job.total_bytes_billed)
    rid = snap.tambah_rilis(inti.Rilis(SUMBER, kode_rilis_bq(mulai, sampai, sha), "tanggal_unduh", snap.tanggal,
                                       "hasil kueri BigQuery GKG; partisi harian tanpa nomor rilis",
                                       cakupan=f"{TABEL_BQ} partisi {mulai}..{sampai}; {len(rows)} baris"))
    n = snap.tulis_bronze("artikel", baris_bronze(rows, "bq"), rid, f"{awal}.jsonl")
    return {"artikel": n, "bita_diproses": job.total_bytes_processed}


def _unduh_zip(http: inti.Http, url: str) -> tuple[tempfile.SpooledTemporaryFile, str, str, int]:
    """Alirkan zip ke berkas sementara; kembalikan berkas, sha256, md5, dan ukuran."""
    r = http.get(url, stream=True)
    f = tempfile.SpooledTemporaryFile(max_size=64 * 2**20)
    h, m, n = hashlib.sha256(), hashlib.md5(), 0  # md5 hanya untuk mencocokkan masterfilelist
    for c in r.iter_content(2**20):
        h.update(c)
        m.update(c)
        n += len(c)
        f.write(c)
    f.seek(0)
    return f, h.hexdigest(), m.hexdigest(), n


def _baris_zip(f) -> Iterator[str]:
    with zipfile.ZipFile(f) as z:
        for nama in z.namelist():
            with z.open(nama) as g:
                yield from io.TextIOWrapper(g, encoding="utf-8", errors="replace", newline="\n")


def _daftar_master(http: inti.Http, snap: inti.Snapshot, aliran: str, mulai: str, sampai: str) -> list[dict]:
    url = MASTER[aliran]
    nama = f"master/{aliran}-{mulai}_{sampai}.txt"
    r = http.get(url, stream=True)
    h, n, sisa, simpan = hashlib.sha256(), 0, b"", []
    a, b = _tanggal(mulai).strftime("%Y%m%d"), _tanggal(sampai).strftime("%Y%m%d")
    for c in r.iter_content(2**20):
        h.update(c)
        n += len(c)
        bagian = (sisa + c).split(b"\n")
        sisa = bagian.pop()
        for x in bagian:
            m = POLA_BERKAS.search(x.decode("ascii", "replace").strip())
            if m and a <= m.group(1)[:8] <= b:
                simpan.append(x.decode("ascii", "replace").strip())
    if sisa.strip():
        simpan.append(sisa.decode("ascii", "replace").strip())
    isi = ("\n".join(simpan) + "\n").encode("ascii")
    snap.catat_ekstrak(nama, isi, url, h.hexdigest(), n, aturan=f"baris berkas GKG ber-cap waktu {a}..{b}")
    return [x for x in urai_master(simpan, mulai, sampai) if x["aliran"] == aliran]


def _berkas(snap: inti.Snapshot, opsi: dict, domain: list[str], tema: list[str]) -> dict:
    http = inti.Http(jeda_s=float(opsi.get("jeda_s", 1.0)), batas_waktu=300)
    mulai, sampai = _rentang(opsi)
    semua_id, pola = opsi.get("semua_id") == "1", pola_tema(tema)
    aliran_pilih = [x.strip() for x in opsi.get("aliran", "translation").split(",") if x.strip()]
    for a in aliran_pilih:
        if a not in MASTER:
            raise ValueError(f"aliran tidak dikenal: {a}")
    daftar = []
    for a in aliran_pilih:
        daftar += (berkas_langsung(mulai, sampai, a) if opsi.get("daftar") == "langsung"
                   else _daftar_master(http, snap, a, mulai, sampai))
    maks_berkas, maks_gb = int(opsi.get("maks_berkas", 2000)), float(opsi.get("maks_gb", 5))
    bita = sum(x["bita"] or 0 for x in daftar)
    est = {"berkas": len(daftar), "bita_unduh": bita, "gb": round(bita / 1e9, 3), "maks_gb": maks_gb,
           "maks_berkas": maks_berkas, "ukuran_diketahui": all(x["bita"] for x in daftar)}
    snap.catatan.append({"apa": "taksiran unduhan GKG", "rentang": [mulai, sampai], "aliran": aliran_pilih} | est)
    _log(f"{len(daftar)} berkas, {est['gb']} GB")
    if len(daftar) > maks_berkas or bita > maks_gb * 1e9:
        raise RuntimeError(f"unduhan {len(daftar)} berkas / {est['gb']} GB melebihi maks_berkas={maks_berkas} "
                           f"atau maks_gb={maks_gb}")
    if opsi.get("estimasi") == "1":
        return {"estimasi": est}
    pekerja = int(opsi.get("pekerja", 1))
    if not 1 <= pekerja <= MAKS_PEKERJA:
        raise ValueError(f"pekerja harus 1..{MAKS_PEKERJA}: {pekerja}")
    lokal = threading.local()

    def olah(x: dict) -> tuple[dict, dict | None, Exception | None]:
        """Unduh, periksa md5, dan saring satu zip; galat dikembalikan agar dicatat di utas utama."""
        if pekerja == 1:
            h = http
        else:
            if not hasattr(lokal, "http"):  # inti.Http tidak aman dipakai bersama antarutas
                lokal.http = inti.Http(jeda_s=float(opsi.get("jeda_s", 1.0)), batas_waktu=300)
            h = lokal.http
        try:
            f, sha, md5, n = _unduh_zip(h, x["url"])
        except Exception as e:  # noqa: BLE001  GDELT kadang melewatkan satu interval 15 menit
            return x, None, e
        try:
            if x["md5"] and md5 != x["md5"]:
                raise ValueError(f"md5 {md5} beda dari masterfilelist {x['md5']}")
            return x, {"rows": saring_csv_gkg(_baris_zip(f), domain, semua_id, pola), "sha256": sha, "bita": n}, None
        except (ValueError, zipfile.BadZipFile) as e:
            return x, None, e
        finally:
            f.close()

    per_hari: dict[tuple[str, str], list[dict]] = {}
    for x in daftar:
        per_hari.setdefault((x["aliran"], x["waktu"][:8]), []).append(x)
    ringkas = {"hari": 0, "artikel": 0, "berkas_gagal": 0}
    for (aliran, hari), xs in sorted(per_hari.items()):
        nama = f"gkg/{aliran}/{hari}.jsonl"
        if nama in snap.berkas:
            continue  # sudah selesai pada jalan sebelumnya hari ini
        rows, asal, gagal = [], [], []
        xs = sorted(xs, key=lambda y: y["waktu"])
        if pekerja > 1:
            with ThreadPoolExecutor(max_workers=pekerja) as ex:
                hasil = list(ex.map(olah, xs))  # map menjaga urutan masukan
        else:
            hasil = [olah(x) for x in xs]
        for x, r, e in hasil:
            if e is not None:
                gagal.append(x["waktu"])
                snap.tambah_galat(x["url"], e)
                continue
            rows += r["rows"]
            asal.append({"url": x["url"], "sha256": r["sha256"], "bita": r["bita"], "waktu": x["waktu"]})
        if not asal:
            continue
        sidik = sidik_gabungan(asal)
        snap.catat_ekstrak(nama, U.jsonl(rows), f"{DATA}/{hari}*.{'translation.' if aliran == 'translation' else ''}gkg.csv.zip",
                           sidik, sum(a["bita"] for a in asal),
                           aturan="baris SourceCommonName/host URL dalam daftar domain"
                                  + (f" dan V2Themes cocok {pola}" if pola else "")
                                  + "; kolom " + ",".join(KOLOM_SIMPAN) + f"; V2Themes dipotong {MAKS_TEMA_RAW} karakter; "
                                  "sha256_asli = sha256 baris '<url> <sha256>' terurut semua zip asal",
                           asal=[f"{a['waktu']} {a['sha256']} {a['bita']}" for a in asal], gagal=gagal)
        terakhir = max(a["waktu"] for a in asal)
        rid = snap.tambah_rilis(inti.Rilis(
            SUMBER, kode_rilis_hari(aliran, hari, sidik), "pembaruan_sumber", U.tanggal_gdelt(terakhir),
            "cap waktu nama berkas GKG 15 menit (UTC), berkas terakhir hari itu",
            cakupan=f"GKG {aliran} {hari}: {len(asal)} berkas, {len(gagal)} gagal"))
        ringkas["artikel"] += snap.tulis_bronze("artikel", baris_bronze(rows, aliran), rid, nama)
        ringkas["hari"] += 1
        ringkas["berkas_gagal"] += len(gagal)
        snap.selesai()  # manifest sementara agar jalan panjang dapat dilanjutkan
        _log(f"{aliran} {hari}: {len(rows)} baris dari {len(asal)} berkas")
    return ringkas


def jalankan(snap: inti.Snapshot, opsi: dict) -> dict:
    if str(opsi.get("lanjut", "1")) != "0":
        U.pulihkan(snap)
    domain = U.daftar_domain(opsi)
    tema = daftar_tema(opsi.get("tema"))
    snap.catatan.append({"apa": "saringan", "jalur": opsi.get("jalur", "bq"), "domain": domain, "tema": tema,
                         "semua_id": opsi.get("semua_id") == "1"})
    jalur = opsi.get("jalur", "bq")
    if jalur == "bq":
        return _bq(snap, opsi, domain, tema)
    if jalur == "berkas":
        return _berkas(snap, opsi, domain, tema)
    raise ValueError(f"jalur tidak dikenal: {jalur}")
