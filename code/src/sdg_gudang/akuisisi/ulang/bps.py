"""Bangun ulang Bronze ``bps`` (tabel WebAPI dan publikasi TPB) dan ``bps_brs`` dari raw gudang."""
from __future__ import annotations

import json

from .. import inti
from ..konektor import bps as k
from . import baca_raw


def _tabel(snap: inti.Snapshot) -> None:
    m = json.loads(baca_raw(snap, "manifest_asal.json"))
    katalog = []
    for nama, info in sorted(m["tabel"].items()):
        if f"json/{nama}.json" not in snap.berkas:
            continue
        rids = [f"bps:{kode}" for kode, _ in k.rilis_tabel(nama, info)]
        katalog.append(k.baris_katalog(nama, info) | {"rilis_id": ";".join(rids)})
        if not rids or f"{nama}.csv" not in snap.berkas:
            continue
        rows = [r | {"tabel": nama} for r in k.baca_csv(baca_raw(snap, f"{nama}.csv"))]
        tabel_bronze = "dinamis" if info.get("jenis") == "dinamis" else f"statis_{nama}"
        snap.tulis_bronze(tabel_bronze, rows, rids[-1], f"{nama}.csv")
    snap.tulis_bronze("katalog_tabel", katalog, f"bps:katalog@{snap.tanggal}", "manifest_asal.json")


def _publikasi(snap: inti.Snapshot) -> None:
    h1 = {f"publikasi/{f['raw_path'].rsplit('/', 1)[-1]}": f
          for f in json.loads(k.MANIFEST_H1.read_text("utf-8"))["files"]}
    for nama in sorted(n for n in snap.berkas if n.startswith("publikasi/")):
        baca_raw(snap, nama)
        f = h1[nama]
        tahun = f["source_id"].rsplit("_", 1)[-1]
        row = {"source_id": f["source_id"], "publication_id": f["publication_id"], "title": f["title"],
               "release_date": f.get("release_date"), "update_date": f.get("update_date"),
               "bytes": f["bytes"], "sha256": f["sha256"]}
        snap.tulis_bronze("publikasi", [row], f"bps:tpb-{tahun}", nama)


def _brs(snap: inti.Snapshot) -> None:
    rid_daftar = f"bps_brs:daftar@{snap.tanggal}"
    for nama in sorted(n for n in snap.berkas if n.startswith("daftar/")):
        _, rows = k.urai_daftar_brs(json.loads(baca_raw(snap, nama)))
        for b in rows:
            b["rilis_id"] = k.rilis_brs(b).rilis_id
        snap.tulis_bronze("brs", rows, rid_daftar, nama)


def ulang(snap: inti.Snapshot, m: dict) -> None:
    if snap.sumber == "bps_brs":
        _brs(snap)
    elif any(n.startswith("publikasi/") for n in snap.berkas):
        _publikasi(snap)
    else:
        _tabel(snap)
