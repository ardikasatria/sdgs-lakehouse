"""Bangun ulang Bronze ``bnpb`` (DataStore CKAN dan berkas unduh tangan) dari raw gudang."""
from __future__ import annotations

import json

from .. import inti
from ..konektor import bnpb as k
from . import baca_raw


def ulang(snap: inti.Snapshot, m: dict) -> None:
    paket = []
    for nama in sorted(n for n in snap.berkas if n.startswith("ckan/package_search-")):
        paket += json.loads(baca_raw(snap, nama))["result"]["results"]
    tangan = {}
    for nama, info in snap.berkas.items():
        if nama.startswith("tangan/"):
            tangan[(nama.split("/")[1], info["resource_id"])] = nama
    # Urutan sama dengan jalan akuisisi: dataset urut nama, resource urut CKAN.
    for pkg in sorted(paket, key=lambda d: d["name"]):
        for res in pkg.get("resources", []):
            rid = k.rilis_resource(pkg, res).rilis_id
            nama = tangan.get((pkg["name"], res["id"]))
            if nama is not None:
                lokal = snap.berkas[nama].get("berkas_lokal", nama).rsplit("/", 1)[-1]
                for lembar, kepala, baris in k.baris_xlsx(baca_raw(snap, nama), lokal):
                    rows = [r | {"_lembar": lembar} for r in k.baris_bronze(baris, pkg, res)]
                    snap.tulis_bronze(k.kelas_tabel(kepala), rows, rid, nama)
                continue
            nama = f"datastore/{pkg['name']}/{res['id']}.json"
            if nama not in snap.berkas:
                continue
            fields, records = k.gabung_halaman(json.loads(baca_raw(snap, nama))["halaman"])
            tabel = k.kelas_tabel([f for f in fields if f != "_id"])
            snap.tulis_bronze(tabel, k.baris_bronze(records, pkg, res), rid, nama)
