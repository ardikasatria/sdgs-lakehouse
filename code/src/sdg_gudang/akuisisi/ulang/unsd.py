"""Bangun ulang Bronze ``unsd`` (seri, data_indonesia lewat API) dan ``unsd_arsip`` (ekstrak Indonesia) dari raw gudang."""
from __future__ import annotations

import collections
import csv
import gzip
import io
import json
import re

from .. import inti
from ..konektor import unsd as k
from . import RawBeda, baca_raw


def _api(snap: inti.Snapshot) -> None:
    seri_rows, peta_rilis = k.urai_daftar_seri(json.loads(baca_raw(snap, "series_list.json")))
    utama = f"unsd:{collections.Counter(peta_rilis.values()).most_common(1)[0][0]}"
    snap.tulis_bronze("seri", seri_rows, utama, "series_list.json")

    def urutan(nama: str) -> tuple[int, int]:  # goal_GG_data.json lalu goal_GG_data_pN.json
        g, p = re.fullmatch(r"goal_(\d+)_data(?:_p(\d+))?\.json", nama).groups()
        return int(g), int(p or 1)

    dilihat: set = set()
    for nama in sorted((n for n in snap.berkas if n.startswith("goal_")), key=urutan):
        g = urutan(nama)[0]
        per_rilis: dict[str, list] = collections.defaultdict(list)
        for d in json.loads(baca_raw(snap, nama)).get("data", []):
            row = k.ratakan_baris_api(d)
            kunci = k.kunci_obs_api(row)
            if kunci in dilihat:
                continue
            dilihat.add(kunci)
            row["_tujuan_permintaan"] = str(g)
            kode = peta_rilis.get(row.get("series")) or ""
            rid = f"unsd:{kode}" if f"unsd:{kode}" in snap.rilis else utama
            per_rilis[rid].append(row)
        for rid, rows in per_rilis.items():
            snap.tulis_bronze("data_indonesia", rows, rid, nama)


def _arsip(snap: inti.Snapshot) -> None:
    # Rilis per berkas arsip: cakupan konektor = "<berkas_arsip>; <n> seri Indonesia".
    rilis_berkas = {r["cakupan"].split("; ", 1)[0]: rid for rid, r in snap.rilis.items()}
    ekstrak = [(n, b) for n, b in snap.berkas.items() if n.startswith("indonesia/")]
    # Urutan proses konektor (pilih_berkas): tanggal halaman, berkas "prior to" lebih dulu.
    ekstrak.sort(key=lambda x: (x[1]["tanggal_halaman"], not re.search(r"_(Before|Prior)_", x[1]["berkas_arsip"])))
    for nama, info in ekstrak:
        teks = gzip.decompress(baca_raw(snap, nama)).decode("utf-8")
        r = csv.reader(io.StringIO(teks, newline=""))
        header = next(r)
        rows = k.baris_arsip_ke_dict(header, list(r))
        if len(rows) != info.get("baris_indonesia", len(rows)):
            raise RawBeda(f"{snap.sumber}/{snap.tanggal}: {nama} {len(rows)} baris, manifest {info['baris_indonesia']}")
        rid = rilis_berkas.get(info["berkas_arsip"])
        if rid is None:
            raise RawBeda(f"{snap.sumber}/{snap.tanggal}: rilis untuk {info['berkas_arsip']} tidak ada di manifest")
        if rows:
            snap.tulis_bronze("data_indonesia", rows, rid, nama)


def ulang(snap: inti.Snapshot, m: dict) -> None:
    if snap.sumber == "unsd_arsip":
        _arsip(snap)
    else:
        _api(snap)
