"""Bangun ulang Bronze dari raw dan manifest, tanpa jaringan (brief 4 M3 dan M4).

Bronze tidak di-commit; raw dan manifest di-commit. Modul ini memulihkan ``Snapshot`` dari manifest
(berkas beserta sha256 dan waktu unduh asli, rilis), membaca setiap berkas raw dengan verifikasi sha256,
lalu memanggil fungsi urai konektor yang sama dengan jalan akuisisi untuk menulis Bronze. Manifest dan
raw tidak pernah ditulis. Jumlah baris per tabel Bronze dibandingkan dengan yang tercatat di manifest.

Setiap sumber mempunyai modul ``ulang/<keluarga>.py`` dengan fungsi ``ulang(snap, m)``; ``m`` adalah
isi manifest. Modul yang sama boleh melayani beberapa sumber (contoh ``wdi`` dan ``wdi_arsip``).

    python3 -m sdg_gudang.akuisisi.ulang [sumber ...] [--bronze DIR]
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

from .. import inti

MODUL = {"wdi_arsip": "wdi", "unsd_arsip": "unsd", "bps_brs": "bps"}


class RawBeda(ValueError):
    """Berkas raw hilang atau sha256-nya tidak cocok dengan manifest."""


def baca_raw(snap: inti.Snapshot, nama: str) -> bytes:
    """Isi berkas raw yang tercatat di manifest, setelah sha256 diverifikasi."""
    if nama not in snap.berkas:
        raise RawBeda(f"{snap.sumber}/{snap.tanggal}: {nama} tidak tercatat di manifest")
    p = snap.folder / nama
    if not p.exists():
        raise RawBeda(f"{snap.sumber}/{snap.tanggal}: {nama} hilang dari raw")
    isi = p.read_bytes()
    if inti.sha256_bita(isi) != snap.berkas[nama]["sha256"]:
        raise RawBeda(f"{snap.sumber}/{snap.tanggal}: sha256 {nama} beda dari manifest")
    return isi


def snapshot_dari_manifest(manifest: Path, bronze: Path = inti.BRONZE, raw: Path = inti.RAW) -> tuple[inti.Snapshot, dict]:
    m = json.loads(manifest.read_text("utf-8"))
    snap = inti.Snapshot(m["sumber"], m["snapshot"], raw=raw, manifest_dir=manifest.parent, bronze=bronze)
    snap.berkas = m["berkas"]
    snap.rilis = m["rilis"]
    return snap, m


def bangun_ulang(manifest: Path, bronze: Path = inti.BRONZE, raw: Path = inti.RAW) -> dict:
    """Bangun ulang Bronze satu manifest. Kembalikan baris per tabel (dibangun lawan manifest)."""
    snap, m = snapshot_dari_manifest(manifest, bronze, raw)
    modul = importlib.import_module(f".{MODUL.get(snap.sumber, snap.sumber)}", __package__)
    modul.ulang(snap, m)
    harap = {t: v["baris"] for t, v in m.get("bronze", {}).items()}
    dapat = {t: v["baris"] for t, v in snap.bronze_tabel.items()}
    beda = {t: {"manifest": harap.get(t, 0), "ulang": dapat.get(t, 0)}
            for t in sorted(harap.keys() | dapat.keys()) if harap.get(t, 0) != dapat.get(t, 0)}
    return {"manifest": manifest.name, "tabel": dapat, "beda": beda}


def manifest_semua(sumber: list[str] | None = None, manifest_dir: Path = inti.MANIFEST) -> list[Path]:
    ps = sorted(manifest_dir.glob("*-????-??-??.json"))
    if sumber:
        ps = [p for p in ps if p.name.rsplit("-", 3)[0] in sumber]
    return [p for p in ps if json.loads(p.read_text("utf-8")).get("bronze")]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Bangun ulang Bronze dari raw dan manifest")
    ap.add_argument("sumber", nargs="*")
    ap.add_argument("--bronze", type=Path, default=inti.BRONZE)
    a = ap.parse_args(argv)
    gagal = 0
    for p in manifest_semua(a.sumber or None):
        try:
            h = bangun_ulang(p, a.bronze)
        except Exception as e:  # satu sumber gagal tidak menghentikan yang lain
            print(json.dumps({"manifest": p.name, "galat": f"{type(e).__name__}: {e}"}, ensure_ascii=False))
            gagal += 1
            continue
        gagal += bool(h["beda"])
        print(json.dumps({"manifest": h["manifest"], "baris": sum(h["tabel"].values()), "beda": h["beda"]},
                         ensure_ascii=False))
    return 1 if gagal else 0


if __name__ == "__main__":
    sys.exit(main())
