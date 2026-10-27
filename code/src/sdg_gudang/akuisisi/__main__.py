"""Jalankan akuisisi.

    python3 -m sdg_gudang.akuisisi jalan <sumber> [--tanggal YYYY-MM-DD] [--opsi k=v ...]
    python3 -m sdg_gudang.akuisisi registri      # bangun data/manifests/gudang/dim_rilis.csv
    python3 -m sdg_gudang.akuisisi verifikasi    # cek sha256 raw terhadap manifest
    python3 -m sdg_gudang.akuisisi volume        # ukuran per lapis -> data/manifests/gudang/volume.json
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys

from . import inti


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Akuisisi Gudang SDG (brief 4 M2)")
    sub = ap.add_subparsers(dest="perintah", required=True)
    j = sub.add_parser("jalan")
    j.add_argument("sumber")
    j.add_argument("--tanggal")
    j.add_argument("--opsi", nargs="*", default=[])
    sub.add_parser("registri")
    sub.add_parser("verifikasi")
    sub.add_parser("volume")
    a = ap.parse_args(argv)

    if a.perintah == "jalan":
        modul = {"wdi_arsip": "wdi", "unsd_arsip": "unsd", "bps_brs": "bps"}.get(a.sumber, a.sumber)
        k = importlib.import_module(f".konektor.{modul}", __package__)
        snap = inti.Snapshot(a.sumber, **({"tanggal": a.tanggal} if a.tanggal else {}))
        opsi = dict(x.split("=", 1) for x in a.opsi)
        try:
            ringkas = k.jalankan(snap, opsi | {"sumber": a.sumber})
        except Exception as e:  # manifest tetap ditulis agar galat terlihat
            snap.tambah_galat("jalankan", e)
            print("manifest:", snap.selesai(), file=sys.stderr)
            raise
        print(json.dumps({"manifest": str(snap.selesai().relative_to(inti.AKAR))} | (ringkas or {}),
                         ensure_ascii=False))
    elif a.perintah == "registri":
        rows = inti.bangun_registri()
        print(f"{len(rows)} rilis -> {inti.MANIFEST / 'dim_rilis.csv'}")
    elif a.perintah == "verifikasi":
        masalah = {p.name: inti.verifikasi(p) for p in sorted(inti.MANIFEST.glob("*-????-??-??.json"))}
        print(json.dumps({k: v for k, v in masalah.items() if v} or "semua cocok", ensure_ascii=False, indent=1))
        return 1 if any(masalah.values()) else 0
    elif a.perintah == "volume":
        v = inti.ukur_volume()
        (inti.MANIFEST / "volume.json").write_text(json.dumps(v, indent=1) + "\n", "utf-8")
        print(json.dumps({k: v["lapis"][k]["bita"] for k in v["lapis"]} | {"baris_bronze": v["baris_bronze_total"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
