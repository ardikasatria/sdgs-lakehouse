"""Konektor BPS: snapshot tabel WebAPI yang sudah ada (``bps``) dan Berita Resmi Statistik (``bps_brs``).

``bps`` **tidak mengunduh ulang**. Snapshot bertanggal ``raw/bps/<tanggal>/`` (dibuat
``scrapping-bps-data.py``; ``manifest.json`` mendaftar tabel, ``last_update``, sha256 JSON) didaftarkan ke
gudang: setiap payload ``json/<tabel>.json`` dan CSV panjangnya disalin byte demi byte ke
``data/raw/gudang/bps/<tanggal>/`` lewat ``snap.simpan`` (sha256 JSON dicocokkan dengan ``sha256_json``
manifest asal; selisih dicatat sebagai galat), ``diunduh_pada`` berkas diganti waktu unduh asli
(``disalin_pada`` = waktu salin). Jalankan dengan ``--tanggal`` = tanggal snapshot asal agar folder gudang
mencerminkan folder asal.

- Rilis: satu per tabel per nilai ``last_update`` WebAPI, jenis ``pembaruan_sumber``, kode
  ``<var>@<last_update>`` (tabel dinamis) atau ``tabel<table_id>@<last_update>`` (tabel statis). Tabel
  yang sama dengan ``last_update`` sama pada dua snapshot menghasilkan ``rilis_id`` yang sama, sehingga
  registri menyatukannya.
- Bronze ``dinamis`` (CSV panjang seragam: var_id, wilayah, turvar, tahun, periode, nilai, satuan) dengan
  kolom tambahan ``tabel``; ``statis_<tabel>`` per tabel statis (kolom berbeda per tabel); ``katalog_tabel``
  (satu baris per tabel dari manifest asal).

``--opsi asal=h1`` (dengan ``--tanggal 2026-09-08``, tanggal unduh H1) mendaftarkan dua edisi publikasi
*Indikator TPB Indonesia* 2024 dan 2025 dari ``data/raw/h1/publications`` sebagai rilis ``rilis_resmi``
(kode ``tpb-<tahun>``, tanggal ``rl_date`` katalog publikasi WebAPI yang tercatat di
``data/manifests/h1-free-publications.json``). PDF disalin; isinya tidak diurai di sini.

``bps_brs``: daftar ``model=pressrelease`` domain 0000 (nasional) semua halaman. Raw = setiap halaman
daftar apa adanya (``daftar/hal-NNNN.json``). Setiap BRS adalah jangkar rilis ``rilis_resmi`` dengan kode
``brs-<id>``, tanggal ``rl_date``, cakupan = judul. Karena ``Snapshot.tulis_bronze`` hanya menerima satu
``rilis_id`` per panggilan, Bronze ``brs`` ditulis per halaman dengan ``_rilis_id`` = rilis daftar
(``daftar@<snapshot>``, jenis ``tanggal_unduh``) dan kolom ``rilis_id`` per baris menunjuk rilis BRS-nya.
Rincian ``model=pressrelease&id=..`` tidak diambil: daftar sudah memuat judul, abstrak, tanggal, subjek,
dan URL PDF. Kunci API dibaca dari ``BPS_API_KEY`` dan tidak pernah disimpan.

Opsi ``bps_brs``: ``maks_hal=N``, ``jeda_s=1.0``.
"""
from __future__ import annotations

import csv
import io
import json
import sys
import time
from pathlib import Path

from .. import inti

SUMBER = ("bps", "bps_brs")

ASAL_BPS = inti.AKAR / "raw" / "bps"
ASAL_H1 = inti.AKAR / "data" / "raw" / "h1" / "publications"
MANIFEST_H1 = inti.AKAR / "data" / "manifests" / "h1-free-publications.json"
WEBAPI = "https://webapi.bps.go.id/v1/api"


# ---------------------------------------------------------------------------------------------------
# Fungsi murni (diuji luring)
# ---------------------------------------------------------------------------------------------------

def iso_waktu(s: str) -> str:
    """``2026-08-26 08:29:01.103415`` -> ``2026-08-26T08:29:01``."""
    s = (s or "").strip()
    return s.split(".")[0].replace(" ", "T") if s else ""


def rilis_tabel(nama: str, info: dict) -> list[tuple[str, str]]:
    """(kode_rilis, tanggal ISO) untuk setiap nilai ``last_update`` tabel."""
    pengenal = str(info["var"]) if info.get("var") is not None else (
        f"tabel{info['table_id']}" if info.get("table_id") is not None else nama)
    lus = sorted({iso_waktu(x) for x in (info.get("last_update") or []) if x})
    return [(f"{pengenal}@{lu}", lu) for lu in lus]


def baca_csv(isi: bytes) -> list[dict]:
    return list(csv.DictReader(io.StringIO(isi.decode("utf-8-sig"), newline="")))


def baris_katalog(nama: str, info: dict) -> dict:
    return {"tabel": nama} | {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v)
                              for k, v in info.items()}


def urai_daftar_brs(js: dict) -> tuple[dict, list[dict]]:
    """Halaman daftar pressrelease -> (meta halaman, baris). Galat API -> ValueError."""
    if js.get("status") != "OK":
        raise ValueError(f"status WebAPI {js.get('status')!r}: {str(js.get('message', ''))[:200]}")
    if js.get("data-availability") != "available":
        return {"page": 0, "pages": 0, "total": 0}, []
    meta, rows = js["data"][0], js["data"][1]
    return meta, [dict(r) for r in rows]


def rilis_brs(r: dict) -> inti.Rilis:
    return inti.Rilis("bps_brs", f"brs-{r['brs_id']}", "rilis_resmi", r.get("rl_date") or "",
                      "rl_date daftar pressrelease WebAPI BPS (domain 0000)", cakupan=(r.get("title") or "")[:300])


# ---------------------------------------------------------------------------------------------------
# bps: daftarkan snapshot yang ada
# ---------------------------------------------------------------------------------------------------

def _log(*a) -> None:
    print("[bps]", *a, file=sys.stderr, flush=True)


def _salin(snap: inti.Snapshot, nama: str, sumber: Path, diunduh: str, **meta) -> str:
    isi = sumber.read_bytes()
    h = snap.simpan(nama, isi, **meta, asal=str(sumber.relative_to(inti.AKAR)))
    b = snap.berkas[nama]
    b["disalin_pada"] = b["diunduh_pada"]
    if diunduh:
        b["diunduh_pada"] = diunduh
    return h


def jalankan_tabel(snap: inti.Snapshot, opsi: dict) -> dict:
    asal = Path(opsi.get("asal_dir") or ASAL_BPS / snap.tanggal)
    if not (asal / "manifest.json").exists():
        raise FileNotFoundError(f"snapshot asal tidak ada: {asal}")
    m = json.loads((asal / "manifest.json").read_text("utf-8"))
    global_unduh = m.get("diunduh", "")
    _salin(snap, "manifest_asal.json", asal / "manifest.json", global_unduh)
    katalog = []
    baris_total = 0
    for nama, info in sorted(m["tabel"].items()):
        diunduh = info.get("diunduh") or global_unduh
        pj, pc = asal / "json" / f"{nama}.json", asal / f"{nama}.csv"
        if not pj.exists():
            snap.tambah_galat(f"tabel {nama}", f"payload JSON tidak ada: {pj.name}")
            continue
        h = _salin(snap, f"json/{nama}.json", pj, diunduh, tabel=nama)
        if info.get("sha256_json") and h != info["sha256_json"]:
            snap.tambah_galat(f"tabel {nama}", "sha256 JSON berbeda dari manifest asal")
        rids = []
        for kode, lu in rilis_tabel(nama, info):
            rids.append(snap.tambah_rilis(inti.Rilis(
                "bps", kode, "pembaruan_sumber", lu, "last_update WebAPI BPS (manifest snapshot asal)",
                cakupan=f"{nama}: {info.get('judul', '')}"[:300])))
        katalog.append(baris_katalog(nama, info) | {"rilis_id": ";".join(rids)})
        if not rids:
            snap.tambah_galat(f"tabel {nama}", "last_update kosong; Bronze tidak ditulis")
            continue
        if not pc.exists():
            snap.tambah_galat(f"tabel {nama}", f"CSV panjang tidak ada: {pc.name}")
            continue
        _salin(snap, f"{nama}.csv", pc, diunduh, tabel=nama, turunan_dari=f"json/{nama}.json")
        rows = [r | {"tabel": nama} for r in baca_csv(pc.read_bytes())]
        tabel_bronze = "dinamis" if info.get("jenis") == "dinamis" else f"statis_{nama}"
        baris_total += snap.tulis_bronze(tabel_bronze, rows, rids[-1], f"{nama}.csv")
    rid_kat = snap.tambah_rilis(inti.Rilis(
        "bps", f"katalog@{snap.tanggal}", "tanggal_unduh", iso_waktu(global_unduh.replace("T", " ")[:19]) or snap.tanggal,
        "waktu unduh manifest snapshot asal; rilis per tabel ada di kolom rilis_id", cakupan=f"katalog {asal.name}"))
    snap.tulis_bronze("katalog_tabel", katalog, rid_kat, "manifest_asal.json")
    snap.catatan.append(f"didaftarkan dari {asal.relative_to(inti.AKAR)} tanpa unduh ulang; "
                        "Bronze memakai rilis last_update terakhir bila tabel punya lebih dari satu")
    return {"tabel": len(m["tabel"]), "rilis": len(snap.rilis), "baris_bronze": baris_total}


def jalankan_h1(snap: inti.Snapshot, opsi: dict) -> dict:
    m = json.loads(MANIFEST_H1.read_text("utf-8"))
    rows = []
    for f in m["files"]:
        p = inti.AKAR / f["raw_path"]
        nama = f"publikasi/{p.name}"
        h = _salin(snap, nama, p, m.get("retrieved_at", ""), publication_id=f["publication_id"],
                   judul=f["title"])
        if h != f["sha256"]:
            snap.tambah_galat(nama, "sha256 berbeda dari manifest H1")
        tahun = f["source_id"].rsplit("_", 1)[-1]
        rid = snap.tambah_rilis(inti.Rilis(
            "bps", f"tpb-{tahun}", "rilis_resmi", f.get("release_date") or "",
            f"rl_date katalog publikasi WebAPI BPS pub_id {f['publication_id']} (data/manifests/h1-free-publications.json)",
            cakupan=f["title"]))
        row = {"source_id": f["source_id"], "publication_id": f["publication_id"], "title": f["title"],
               "release_date": f.get("release_date"), "update_date": f.get("update_date"),
               "bytes": f["bytes"], "sha256": f["sha256"]}
        snap.tulis_bronze("publikasi", [row], rid, nama)
        rows.append(row)
    snap.catatan.append("edisi publikasi TPB didaftarkan dari data/raw/h1; isi PDF tidak diurai")
    return {"publikasi": len(rows), "rilis": sorted(snap.rilis)}


# ---------------------------------------------------------------------------------------------------
# bps_brs: Berita Resmi Statistik
# ---------------------------------------------------------------------------------------------------

def jalankan_brs(snap: inti.Snapshot, opsi: dict) -> dict:
    try:
        kunci = inti.kunci("BPS_API_KEY")
    except KeyError as e:
        snap.tambah_galat("kunci", e)
        return {"galat": "BPS_API_KEY tidak ada"}
    http = inti.Http(jeda_s=float(opsi.get("jeda_s", 1.0)))
    t0 = time.monotonic()
    rid_daftar = snap.tambah_rilis(inti.Rilis(
        "bps_brs", f"daftar@{snap.tanggal}", "tanggal_unduh", snap.tanggal,
        "tanggal unduh daftar pressrelease; rilis tiap BRS ada di kolom rilis_id", cakupan="daftar BRS domain 0000"))
    hal, halaman, total, maks, meta = 1, 1, 0, int(opsi.get("maks_hal", 10 ** 6)), {}
    while hal <= min(halaman, maks):
        params = {"model": "pressrelease", "domain": "0000", "lang": "ind", "page": hal, "key": kunci}
        try:
            r = http.get(f"{WEBAPI}/list", params=params)
            meta, rows = urai_daftar_brs(r.json())
        except Exception as e:  # pesan galat requests dapat memuat URL berkunci
            snap.tambah_galat(f"daftar hal {hal}", str(e).replace(kunci, "REDACTED"))
            break
        nama = f"daftar/hal-{hal:04d}.json"
        snap.simpan(nama, r.content, r.url)
        halaman = int(meta.get("pages") or 0)
        for b in rows:
            b["rilis_id"] = snap.tambah_rilis(rilis_brs(b))
        total += snap.tulis_bronze("brs", rows, rid_daftar, nama)
        if hal % 20 == 0 or hal == halaman:
            _log(f"hal {hal}/{halaman}: {total} BRS")
        hal += 1
    return {"brs": total, "halaman": hal - 1, "total_api": meta.get("total", 0),
            "detik": round(time.monotonic() - t0)}


def jalankan(snap: inti.Snapshot, opsi: dict) -> dict:
    if opsi.get("sumber", snap.sumber) == "bps_brs":
        return jalankan_brs(snap, opsi)
    if opsi.get("asal") == "h1":
        return jalankan_h1(snap, opsi)
    return jalankan_tabel(snap, opsi)
