"""Konektor basis data SDG global PBB: rilis terkini lewat API (``unsd``) dan arsip snapshot (``unsd_arsip``).

Kedua sumber berkelas lisensi B (hanya untuk gudang riset dan rekonsiliasi, tidak tayang di game).

- ``unsd``: API ``https://unstats.un.org/sdgapi/v1/sdg``. Cakupan: **semua seri rilis terkini yang
  mempunyai data Indonesia** (kode area M49 ``360``). Cara paling hemat yang diukur 20 Okt 2026 adalah
  ``Goal/Data?goal=<g>&areaCode=360&pageSize=100000`` untuk 17 tujuan (17 permintaan, setiap respons satu
  halaman), ditambah ``Series/List?allreleases=false`` (kode rilis per seri) dan ``Series/LastUpdated``
  (tanggal rilis). Seri yang dipetakan ke lebih dari satu tujuan muncul di beberapa respons; Bronze
  ``data_indonesia`` memuat setiap observasi sekali (kunci: seri, periode, dimensi, atribut, nilai).
  Rilis = kode ``release`` seri (mis. ``2026.Q3.G.01``), jenis bukti ``rilis_resmi``, tanggal dari
  ``Series/LastUpdated``. Bronze ``seri`` memuat daftar seri global.
- ``unsd_arsip``: halaman ``https://unstats.un.org/sdgs/indicators/database/archive`` mendaftar berkas
  ``*_CSV.zip`` per pembaruan sejak 29 Mar 2019, berpasangan "prior to <tanggal>" (``Before``/``Prior``) dan
  "on <tanggal>" (``After``/``Onward``). Berkas berisi seluruh dunia (zip 22–70 MB, CSV sampai 1,8 GB),
  sehingga setiap zip diunduh mengalir ke berkas sementara, sha256 dan ukurannya dihitung, baris
  Indonesia diambil dengan ``csv.reader`` penuh (sel catatan kaki dapat memuat baris baru, jadi saring
  substring per baris fisik tidak aman), lalu zip dihapus. Paling banyak satu zip global ada di disk.
  Ekstrak disimpan sebagai ``indonesia/<berkas>.csv.gz`` (header asli + baris Indonesia, ditulis ulang
  ``csv.writer``, gzip mtime 0). Satu berkas arsip = satu rilis ``rilis_resmi``; kode = nilai terbanyak
  kolom ``ReleaseName`` pada ekstrak (bila kolom tidak ada, diturunkan dari nama berkas, mis.
  ``2026_Q3.1`` -> ``2026.Q3.G.01``); bila kode sudah dipakai berkas lain pada snapshot yang sama,
  ditambah ``@<YYYYMMDD>`` tanggal halaman. Tanggal rilis berkas "on" = tanggal halaman; berkas "prior to"
  menyatakan keadaan sebelum tanggal itu, sehingga tanggal rilisnya dikosongkan dan tanggal halaman
  dicatat sebagai ``batas_atas``.

  Pilihan bawaan: semua berkas "on" ditambah berkas "prior to" tertua (29 Mar 2019, keadaan sebelum
  snapshot pertama). Berkas "prior to" lain pada dasarnya sama dengan berkas "on" pembaruan sebelumnya
  dan dilewati kecuali ``jenis=semua``.

Opsi ``unsd_arsip`` (``--opsi k=v``): ``rilis=2019.Q2.G.01,...`` (cocok dengan kode turunan nama berkas),
``berkas=<nama tanpa _CSV.zip>,...``, ``dari=YYYY-MM-DD``, ``sampai=YYYY-MM-DD``, ``maks=N`` (N berkas
tertua dari pilihan yang belum diproses), ``jenis=sesudah|semua``, ``estimasi=1`` (HEAD saja, cetak taksiran
ukuran dan waktu), ``lanjut=0`` (abaikan manifest snapshot hari yang sama; bawaannya berkas yang sudah
tercatat dilewati sehingga jalan dapat dilanjutkan), ``jeda_s=1.0``.
"""
from __future__ import annotations

import collections
import csv
import datetime as dt
import gzip
import hashlib
import io
import json
import os
import re
import sys
import tempfile
import time
import zipfile
from typing import Iterable

from .. import inti

SUMBER = ("unsd", "unsd_arsip")

API = "https://unstats.un.org/sdgapi/v1/sdg"
HALAMAN_ARSIP = "https://unstats.un.org/sdgs/indicators/database/archive"
KODE_AREA = "360"
NAMA_AREA = "Indonesia"
JUMLAH_TUJUAN = 17

#: Kolom atribut (bukan dimensi) pada CSV arsip; tidak dipakai sebagai kunci sel.
KOLOM_ATRIBUT = {"Nature", "UnitMultiplier", "Observation Status"}
#: Kolom identitas baris dan metadata CSV arsip yang bukan dimensi.
KOLOM_BUKAN_DIMENSI = {
    "", "nomor_baris", "ID", "Goal", "Target", "Indicator", "ReleaseStatus", "ReleaseName", "SeriesID",
    "SeriesCode", "isDSDSeries", "SeriesDescription", "SeriesObservationCount", "GeoAreaCode", "GeoAreaName",
    "TimePeriod", "Value", "ValueType", "Time_Detail", "TimeCoverage", "UpperBound", "LowerBound",
    "BasePeriod", "Source", "GeoInfoUrl", "FootNote", "ObservationID",
}
BULAN = {b: i for i, b in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}


# ---------------------------------------------------------------------------------------------------
# Fungsi murni (diuji luring)
# ---------------------------------------------------------------------------------------------------

def tanggal_halaman(teks: str) -> str:
    """``30-Sep-26`` -> ``2026-09-30``."""
    m = re.fullmatch(r"\s*(\d{1,2})-([A-Za-z]{3})-(\d{2})\s*", teks)
    if not m:
        raise ValueError(f"tanggal arsip tidak dikenal: {teks!r}")
    return dt.date(2000 + int(m.group(3)), BULAN[m.group(2).lower()], int(m.group(1))).isoformat()


def kode_dari_nama(nama: str) -> str:
    """Kode rilis dari nama berkas arsip: ``2026_Q3.1_AllData_After_20260930_CSV.zip`` -> ``2026.Q3.G.01``,
    ``2021_Q1_AllData_...`` -> ``2021.Q1.G.01``. Berkas 2019-03-29 tidak bernomor -> ``""``."""
    m = re.match(r"(\d{4})_Q(\d)(?:\.(\d+))?_AllData", nama.rsplit("/", 1)[-1])
    if not m:
        return ""
    return f"{m.group(1)}.Q{m.group(2)}.G.{int(m.group(3) or 1):02d}"


def urai_halaman_arsip(html: str) -> list[dict]:
    """Daftar berkas arsip dari tabel halaman: satu entri per baris tabel yang memuat tautan ``_CSV.zip``."""
    hasil = []
    for baris in re.findall(r"<tr>(.*?)</tr>", html, re.S | re.I):
        tds = [re.sub(r"<[^>]+>", "", t).strip() for t in re.findall(r"<td[^>]*>(.*?)</td>", baris, re.S | re.I)]
        csvs = re.findall(r'href="([^"]*_CSV\.zip)"', baris, re.I)
        if not csvs or not tds:
            continue
        url = csvs[0]
        if url.startswith("/"):
            url = "https://unstats.un.org" + url
        nama = url.rsplit("/", 1)[-1]
        stem = nama[: -len("_CSV.zip")]
        rs = re.findall(r'href="([^"]*_R\.zip)"', baris, re.I)
        jenis = "sebelum" if re.search(r"_(Before|Prior)_", nama) else "sesudah"
        hasil.append({"tanggal": tanggal_halaman(tds[0]), "deskripsi": tds[1] if len(tds) > 1 else "",
                      "jenis": jenis, "berkas": stem, "url": url, "url_r": rs[0] if rs else "",
                      "kode_nama": kode_dari_nama(nama)})
    return hasil


def pilih_berkas(daftar: list[dict], opsi: dict, sudah: Iterable[str] = ()) -> list[dict]:
    """Subset berkas menurut opsi, urut dari tertua. ``sudah`` = stem berkas yang sudah diproses."""
    jenis = opsi.get("jenis", "sesudah")
    if jenis == "semua":
        pilih = list(daftar)
    else:
        pilih = [d for d in daftar if d["jenis"] == "sesudah"]
        sebelum = [d for d in daftar if d["jenis"] == "sebelum"]
        if sebelum:  # keadaan sebelum snapshot pertama
            tertua = min(sebelum, key=lambda d: d["tanggal"])
            if tertua["tanggal"] <= min((d["tanggal"] for d in pilih), default="9999"):
                pilih.append(tertua)
    if opsi.get("rilis"):
        k = set(opsi["rilis"].split(","))
        pilih = [d for d in pilih if d["kode_nama"] in k]
    if opsi.get("berkas"):
        k = set(opsi["berkas"].split(","))
        pilih = [d for d in pilih if d["berkas"] in k]
    if opsi.get("dari"):
        pilih = [d for d in pilih if d["tanggal"] >= opsi["dari"]]
    if opsi.get("sampai"):
        pilih = [d for d in pilih if d["tanggal"] <= opsi["sampai"]]
    sudah = set(sudah)
    pilih = sorted((d for d in pilih if d["berkas"] not in sudah),
                   key=lambda d: (d["tanggal"], d["jenis"] != "sebelum"))
    if opsi.get("maks"):
        pilih = pilih[: int(opsi["maks"])]
    return pilih


def saring_indonesia(teks: Iterable[str]) -> tuple[list[str], list[list[str]]]:
    """Header dan baris Indonesia dari aliran teks CSV arsip global (``csv.reader`` penuh)."""
    r = csv.reader(teks)
    header = next(r)
    header = [h.lstrip("﻿") for h in header]
    if "GeoAreaCode" in header:
        i, cocok = header.index("GeoAreaCode"), KODE_AREA
    elif "GeoAreaName" in header:
        i, cocok = header.index("GeoAreaName"), NAMA_AREA
    else:
        raise ValueError("kolom GeoAreaCode/GeoAreaName tidak ada di header arsip")
    baris = [row for row in r if len(row) > i and row[i].strip() == cocok]
    return header, baris


def tulis_csv_gz(header: list[str], baris: list[list[str]]) -> bytes:
    """CSV ber-gzip deterministik (mtime 0)."""
    s = io.StringIO()
    w = csv.writer(s, lineterminator="\n")
    w.writerow(header)
    w.writerows(baris)
    return gzip.compress(s.getvalue().encode("utf-8"), compresslevel=9, mtime=0)


def baris_arsip_ke_dict(header: list[str], baris: list[list[str]]) -> list[dict]:
    """Baris CSV arsip ke dict; kolom tanpa nama (indeks R) diberi nama ``nomor_baris``."""
    nama = ["nomor_baris" if h == "" else h for h in header]
    return [dict(zip(nama, row)) for row in baris]


def kode_terbanyak(rows: list[dict], kolom: str = "ReleaseName") -> tuple[str, dict]:
    c = collections.Counter(r.get(kolom, "") for r in rows if r.get(kolom, "") not in ("", "NA"))
    return (c.most_common(1)[0][0] if c else ""), dict(c)


def kunci_sel_arsip(r: dict) -> tuple:
    """Kunci sel (seri, periode, dimensi). Kolom dimensi = kolom yang bukan identitas/metadata/atribut;
    nilai kosong dan ``NA`` disamakan agar kolom baru di rilis berikutnya tidak membuat sel baru. Kolom baku
    Bronze (awalan ``_``) diabaikan sehingga fungsi ini dapat dipakai langsung pada baris Bronze."""
    dim = tuple(sorted((k, v) for k, v in r.items()
                       if k not in KOLOM_BUKAN_DIMENSI and k not in KOLOM_ATRIBUT and not k.startswith("_")
                       and v not in ("", "NA", None)))
    return (r.get("SeriesCode", ""), str(r.get("TimePeriod", "")).removesuffix(".0"), dim)


def _angka(v):
    try:
        return round(float(v), 9)
    except (TypeError, ValueError):
        return (v or "").strip()


def sel_berubah(lama: list[dict], baru: list[dict]) -> dict:
    """Bandingkan dua rilis berurutan pada tingkat sel. Nilai dibandingkan sebagai angka bila bisa."""
    a = {kunci_sel_arsip(r): _angka(r.get("Value")) for r in lama}
    b = {kunci_sel_arsip(r): _angka(r.get("Value")) for r in baru}
    sama = a.keys() & b.keys()
    berubah = sum(1 for k in sama if a[k] != b[k])
    seri_berubah = sorted({k[0] for k in sama if a[k] != b[k]})
    return {"sel_lama": len(a), "sel_baru": len(b), "sel_sama_kunci": len(sama), "nilai_berubah": berubah,
            "sel_hilang": len(a.keys() - b.keys()), "sel_muncul": len(b.keys() - a.keys()),
            "seri_nilai_berubah": len(seri_berubah)}


def ratakan_baris_api(d: dict) -> dict:
    """Baris ``Goal/Data`` ke dict datar: daftar digabung ``|``, dimensi dan atribut diberi awalan."""
    out = {}
    for k, v in d.items():
        if k in ("dimensions", "attributes") and isinstance(v, dict):
            awal = "dim_" if k == "dimensions" else "atr_"
            out |= {awal + kk: vv for kk, vv in v.items()}
        elif isinstance(v, list):
            out[k] = "|".join("" if x is None else str(x) for x in v)
        elif isinstance(v, float) and k == "timePeriodStart" and v.is_integer():
            out[k] = str(int(v))
        else:
            out[k] = v
    return out


def kunci_obs_api(r: dict) -> tuple:
    return tuple(sorted((k, "" if v is None else str(v)) for k, v in r.items() if k != "goal"))


def urai_daftar_seri(js: list) -> tuple[list[dict], dict]:
    """Daftar seri ``Series/List`` -> baris Bronze dan peta kode seri -> kode rilis."""
    rows, peta = [], {}
    for s in js:
        rows.append({"code": s.get("code"), "description": s.get("description"), "release": s.get("release"),
                     "goal": "|".join(s.get("goal") or []), "target": "|".join(s.get("target") or []),
                     "indicator": "|".join(s.get("indicator") or []), "uri": s.get("uri")})
        peta[s.get("code")] = s.get("release") or ""
    return rows, peta


# ---------------------------------------------------------------------------------------------------
# Jaringan
# ---------------------------------------------------------------------------------------------------

def _log(*a) -> None:
    print("[unsd]", *a, file=sys.stderr, flush=True)


def _pulihkan(snap: inti.Snapshot, opsi: dict) -> None:
    """Muat manifest snapshot hari yang sama agar jalan panjang dapat dilanjutkan."""
    p = snap.manifest_dir / f"{snap.sumber}-{snap.tanggal}.json"
    if opsi.get("lanjut", "1") == "0" or not p.exists():
        return
    m = json.loads(p.read_text("utf-8"))
    hilang = [n for n in m.get("berkas", {}) if not (snap.folder / n).exists()]
    if hilang:
        snap.catatan.append(f"manifest lama diabaikan: {len(hilang)} berkas raw hilang")
        return
    snap.berkas.update(m.get("berkas", {}))
    snap.rilis.update(m.get("rilis", {}))
    snap.bronze_tabel.update(m.get("bronze", {}))
    snap.catatan.extend(c for c in m.get("catatan", []) if c not in snap.catatan)
    snap.galat.extend(m.get("galat", []))
    snap.mulai = m.get("mulai", snap.mulai)
    _log(f"melanjutkan snapshot {snap.tanggal}: {len(snap.berkas)} berkas, {len(snap.rilis)} rilis sudah ada")


def jalankan_api(snap: inti.Snapshot, opsi: dict) -> dict:
    http = inti.Http(jeda_s=float(opsi.get("jeda_s", 1.0)), batas_waktu=300)
    t0 = time.monotonic()
    r = http.get(f"{API}/Series/LastUpdated")
    snap.simpan("series_lastupdated.json", r.content, r.url)
    terakhir = str(r.json()).strip()
    r = http.get(f"{API}/Series/List", params={"allreleases": "false"})
    snap.simpan("series_list.json", r.content, r.url)
    seri_rows, peta_rilis = urai_daftar_seri(r.json())
    kode_rilis = collections.Counter(peta_rilis.values())
    for kode, n in sorted(kode_rilis.items()):
        snap.tambah_rilis(inti.Rilis(
            "unsd", kode or "tanpa_kode", "rilis_resmi" if kode else "tidak_diketahui",
            terakhir if kode == kode_rilis.most_common(1)[0][0] else "",
            "field release di Series/List?allreleases=false; tanggal dari Series/LastUpdated",
            cakupan=f"{n} seri global"))
    utama = f"unsd:{kode_rilis.most_common(1)[0][0]}"
    snap.tulis_bronze("seri", seri_rows, utama, "series_list.json")

    dilihat: set = set()
    seri_id: set = set()
    total, dobel = 0, 0
    for g in range(1, JUMLAH_TUJUAN + 1):
        hal, halaman = 1, 1
        while hal <= halaman:
            nama = f"goal_{g:02d}_data.json" if hal == 1 else f"goal_{g:02d}_data_p{hal}.json"
            try:
                r = http.get(f"{API}/Goal/Data", params={"goal": g, "areaCode": KODE_AREA,
                                                         "pageSize": 100000, "page": hal})
            except Exception as e:
                snap.tambah_galat(f"Goal/Data goal={g} page={hal}", e)
                break
            snap.simpan(nama, r.content, r.url)
            js = r.json()
            halaman = int(js.get("totalPages") or 1)
            per_rilis: dict[str, list] = collections.defaultdict(list)
            for d in js.get("data", []):
                row = ratakan_baris_api(d)
                k = kunci_obs_api(row)
                if k in dilihat:
                    dobel += 1
                    continue
                dilihat.add(k)
                seri_id.add(row.get("series"))
                row["_tujuan_permintaan"] = str(g)
                kode = peta_rilis.get(row.get("series")) or ""
                rid = f"unsd:{kode}" if f"unsd:{kode}" in snap.rilis else utama
                per_rilis[rid].append(row)
            for rid, rows in per_rilis.items():
                total += snap.tulis_bronze("data_indonesia", rows, rid, nama)
            _log(f"goal {g} hal {hal}/{halaman}: {len(js.get('data', []))} baris")
            hal += 1
    for rid in snap.rilis:
        kode = snap.rilis[rid]["kode_rilis"]
        n = sum(1 for s in seri_id if (peta_rilis.get(s) or "tanpa_kode") == kode)
        snap.rilis[rid]["cakupan"] += f"; {n} seri dengan data Indonesia"
    snap.catatan.append(f"{dobel} baris Goal/Data dobel antartujuan (seri multi-indikator) dilewati di Bronze")
    return {"seri_global": len(seri_rows), "seri_indonesia": len(seri_id), "baris_bronze": total,
            "baris_dobel": dobel, "rilis": sorted(snap.rilis), "detik": round(time.monotonic() - t0)}


def _unduh_ke_sementara(http: inti.Http, url: str) -> tuple[str, str, int, float]:
    """Unduh mengalir ke berkas sementara; kembalikan (path, sha256, bita, detik)."""
    t = time.monotonic()
    h = hashlib.sha256()
    n = 0
    fd, path = tempfile.mkstemp(prefix="unsd_arsip_", suffix=".zip")
    try:
        with os.fdopen(fd, "wb") as f:
            r = http.get(url, stream=True)
            for blok in r.iter_content(1 << 20):
                f.write(blok)
                h.update(blok)
                n += len(blok)
            r.close()
    except BaseException:
        os.unlink(path)
        raise
    return path, h.hexdigest(), n, time.monotonic() - t


def _ekstrak_zip(path: str) -> tuple[list[str], list[list[str]], list[str], str]:
    """Header dan baris Indonesia dari semua anggota CSV zip; kembalikan juga nama anggota dan pengodean."""
    header: list[str] = []
    semua: list[list[str]] = []
    anggota = []
    with zipfile.ZipFile(path) as z:
        nama_csv = [n for n in z.namelist() if n.lower().endswith(".csv")]
        for nama in nama_csv:
            for enc in ("utf-8-sig", "cp1252", "latin-1"):
                try:
                    with z.open(nama) as f:
                        h, rows = saring_indonesia(io.TextIOWrapper(f, encoding=enc, newline=""))
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValueError(f"pengodean {nama} tidak dikenali")
            if header and h != header:
                raise ValueError(f"header anggota {nama} berbeda dari anggota pertama")
            header = h
            semua.extend(rows)
            anggota.append(nama)
    return header, semua, anggota, enc


def jalankan_arsip(snap: inti.Snapshot, opsi: dict) -> dict:
    http = inti.Http(jeda_s=float(opsi.get("jeda_s", 1.0)), batas_waktu=300)
    _pulihkan(snap, opsi)
    r = http.get(HALAMAN_ARSIP)
    if "halaman_arsip.html" not in snap.berkas:
        snap.simpan("halaman_arsip.html", r.content, r.url)
    daftar = urai_halaman_arsip(r.text)
    if not daftar:
        raise RuntimeError("tidak ada tautan *_CSV.zip di halaman arsip")
    sudah = {b.get("berkas_arsip") for b in snap.berkas.values() if b.get("berkas_arsip")}
    pilih = pilih_berkas(daftar, opsi, sudah)
    _log(f"halaman arsip: {len(daftar)} berkas CSV; {len(sudah)} sudah diproses; {len(pilih)} dipilih")

    if opsi.get("estimasi") == "1":
        total = 0
        for d in pilih:
            h = http.s.head(d["url"], timeout=60)
            total += int(h.headers.get("Content-Length") or 0)
        kec = float(opsi.get("kecepatan_mb_s", 0.48))
        _log(f"taksiran: {len(pilih)} zip, {total / 1e6:.0f} MB, unduh ~{total / 1e6 / kec / 60:.0f} menit "
             f"pada {kec} MB/s ditambah ~20 s urai per GB CSV")
        return {"dipilih": [d["berkas"] for d in pilih], "bita_zip": total}

    hasil = []
    t0 = time.monotonic()
    for i, d in enumerate(pilih, 1):
        try:
            path, sha, bita, detik_unduh = _unduh_ke_sementara(http, d["url"])
        except Exception as e:
            snap.tambah_galat(f"unduh {d['berkas']}", e)
            continue
        try:
            t = time.monotonic()
            header, baris, anggota, enc = _ekstrak_zip(path)
            detik_urai = time.monotonic() - t
        except Exception as e:
            snap.tambah_galat(f"urai {d['berkas']}", e)
            continue
        finally:
            os.unlink(path)
        rows = baris_arsip_ke_dict(header, baris)
        kode, sebaran = kode_terbanyak(rows)
        kode = kode or d["kode_nama"] or f"arsip-{d['tanggal'].replace('-', '')}"
        if f"unsd_arsip:{kode}" in snap.rilis:
            kode = f"{kode}@{d['tanggal'].replace('-', '')}"
        nama = f"indonesia/{d['berkas']}.csv.gz"
        snap.catat_ekstrak(nama, tulis_csv_gz(header, baris), d["url"], sha, bita,
                           f"baris GeoAreaCode=={KODE_AREA} (csv.reader penuh atas {', '.join(anggota)}, "
                           f"pengodean {enc}); ditulis ulang csv.writer; gzip mtime 0",
                           berkas_arsip=d["berkas"], tanggal_halaman=d["tanggal"], deskripsi=d["deskripsi"],
                           baris_indonesia=len(rows), release_name=sebaran,
                           detik_unduh=round(detik_unduh, 1), detik_urai=round(detik_urai, 1))
        sesudah = d["jenis"] == "sesudah"
        rid = snap.tambah_rilis(inti.Rilis(
            "unsd_arsip", kode, "rilis_resmi", d["tanggal"] if sesudah else "",
            f"halaman arsip UNSD: '{d['deskripsi']}'; kolom ReleaseName {sebaran or 'tidak ada'}",
            batas_atas="" if sesudah else d["tanggal"],
            cakupan=f"{d['berkas']}; {len({r.get('SeriesCode') for r in rows})} seri Indonesia"))
        n = snap.tulis_bronze("data_indonesia", rows, rid, nama) if rows else 0
        lama = [g for g in snap.galat if g["apa"] in (f"unduh {d['berkas']}", f"urai {d['berkas']}")]
        if lama:  # galat jalan sebelumnya untuk berkas ini sudah teratasi
            snap.galat = [g for g in snap.galat if g not in lama]
            snap.catatan.append(f"{d['berkas']}: galat jalan sebelumnya ({lama[0]['galat'][:80]}) teratasi pada jalan lanjutan")
        snap.selesai()  # manifest sementara agar jalan dapat dilanjutkan
        hasil.append({"berkas": d["berkas"], "rilis": rid, "baris": n, "mb_zip": round(bita / 1e6, 1)})
        lalu = time.monotonic() - t0
        _log(f"{i}/{len(pilih)} {d['berkas']}: {n} baris Indonesia, zip {bita / 1e6:.1f} MB, unduh "
             f"{detik_unduh:.0f} s, urai {detik_urai:.0f} s; sisa ~{lalu / i * (len(pilih) - i) / 60:.0f} menit")
    return {"diproses": hasil, "rilis_total": len(snap.rilis), "detik": round(time.monotonic() - t0)}


def jalankan(snap: inti.Snapshot, opsi: dict) -> dict:
    if opsi.get("sumber", snap.sumber) == "unsd_arsip":
        return jalankan_arsip(snap, opsi)
    return jalankan_api(snap, opsi)
