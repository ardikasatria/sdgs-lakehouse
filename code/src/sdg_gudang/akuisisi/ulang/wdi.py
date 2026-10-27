"""Bangun ulang Bronze ``wdi`` (nilai, indikator, seri_sdg46) dan ``wdi_arsip`` (nilai per versi) dari raw gudang."""
from __future__ import annotations

import json

from .. import inti
from ..konektor import wdi as k
from . import RawBeda, baca_raw


def _terkini(snap: inti.Snapshot) -> None:
    rilis: dict[str, str] = {}
    for nama in sorted(n for n in snap.berkas if n.startswith("data/")):
        js = json.loads(baca_raw(snap, nama))
        lu = k.meta_halaman(js)["lastupdated"]
        # Id sama dengan tambah_rilis di konektor: "wdi:<lastupdated>" atau cadangan tanggal unduh.
        rilis.setdefault(lu, f"wdi:{lu or f'tanpa-lastupdated-{snap.tanggal}'}")
        snap.tulis_bronze("nilai", k.baris_wdi(js), rilis[lu], nama)
    if not rilis:
        return
    rid = next(iter(rilis.values()))
    indikator = k.urai_daftar_indikator(json.loads(baca_raw(snap, "metadata/sumber2_indikator.json")))
    snap.tulis_bronze("indikator", indikator, rid, "metadata/sumber2_indikator.json")
    berkas_sdg = "metadata/sumber46_indikator.json"
    snap.tulis_bronze("seri_sdg46", k.urai_daftar_indikator(json.loads(baca_raw(snap, berkas_sdg))), rid, berkas_sdg)


def _arsip(snap: inti.Snapshot) -> None:
    for nama in sorted(n for n in snap.berkas if n.startswith("versi/")):
        info = snap.berkas[nama]
        v = nama.removeprefix("versi/").removesuffix(".tar.gz")
        isi = k.baca_tar(baca_raw(snap, nama))
        rows = []
        for a in info.get("anggota") or [{"nama": n} for n in sorted(isi)]:
            b = isi[a["nama"]]
            if "sha256" in a and inti.sha256_bita(b) != a["sha256"]:
                raise RawBeda(f"{snap.sumber}/{snap.tanggal}: sha256 anggota {nama}:{a['nama']} beda dari manifest")
            rows.extend(k.baris_arsip(json.loads(b)))
        snap.tulis_bronze("nilai", rows, f"wdi_arsip:{v}", nama)


def ulang(snap: inti.Snapshot, m: dict) -> None:
    if snap.sumber == "wdi_arsip":
        _arsip(snap)
    else:
        _terkini(snap)
