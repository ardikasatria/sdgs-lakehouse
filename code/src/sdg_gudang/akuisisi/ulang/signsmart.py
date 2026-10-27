"""Bangun ulang Bronze ``signsmart`` (emisi GRK per provinsi per tahun dan seri nasional) dari raw gudang."""
from __future__ import annotations

import json

from .. import inti
from ..konektor import signsmart as k
from . import baca_raw


def ulang(snap: inti.Snapshot, m: dict) -> None:
    for nama in sorted(n for n in snap.berkas if n.startswith("emisi_prov/")):
        th = nama.removeprefix("emisi_prov/").removesuffix(".json")
        isi = baca_raw(snap, nama)
        js = json.loads(isi)
        if isinstance(js, dict):
            snap.tulis_bronze("emisi_provinsi", k.baris_provinsi(js, th),
                              f"{k.SUMBER}:{k.kode_rilis(th, inti.sha256_bita(isi))}", nama)
    if "emisi_all.json" in snap.berkas:
        isi = baca_raw(snap, "emisi_all.json")
        snap.tulis_bronze("emisi_nasional", k.baris_nasional(json.loads(isi)),
                          f"{k.SUMBER}:emisi_all@{inti.sha256_bita(isi)[:12]}", "emisi_all.json")
