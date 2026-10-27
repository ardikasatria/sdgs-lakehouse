"""Bangun ulang Bronze ``kkp`` (portal_local, seri nasional ``/sttk``, dan statistik per provinsi per tahun)
dari raw gudang."""
from __future__ import annotations

import json

from .. import inti
from ..konektor import kkp as k
from . import baca_raw


def _baca(snap: inti.Snapshot, nama: str) -> tuple[list[dict], str]:
    isi = baca_raw(snap, nama)
    return k.data_payload(json.loads(isi)), inti.sha256_bita(isi)


def ulang(snap: inti.Snapshot, m: dict) -> None:
    for ep, tabel in k.PORTAL_LOCAL.items():
        nama = f"portal_local/{ep}.json"
        if nama in snap.berkas:
            rows, sha = _baca(snap, nama)
            snap.tulis_bronze(tabel, k.baris_bronze(rows, ep), f"{k.SUMBER}:{k.kode_rilis(ep, sha)}", nama)
    for ep_th in k.PER_PROV.values():
        nama = f"sttk/{ep_th}.json"
        if nama in snap.berkas:
            rows, sha = _baca(snap, nama)
            snap.tulis_bronze(f"nasional_{ep_th}", k.baris_bronze(rows, ep_th),
                              f"{k.SUMBER}:{k.kode_rilis(ep_th, sha)}", nama)
    for ep in k.PER_PROV:
        awal = f"sttk/{ep}/tahun="
        for nama in sorted(n for n in snap.berkas if n.startswith(awal)):
            th = nama.removeprefix(awal).removesuffix(".json")
            rows, sha = _baca(snap, nama)
            if rows:  # tahun tanpa baris tidak masuk Bronze dan tidak bertanda rilis
                snap.tulis_bronze(ep, k.baris_bronze(rows, ep, th), f"{k.SUMBER}:{k.kode_rilis(ep, sha, th)}", nama)
