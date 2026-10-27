"""Bangun ulang Bronze ``gdelt`` (hasil kueri BigQuery dan ekstrak harian berkas GKG) dari raw gudang."""
from __future__ import annotations

from .. import inti
from ..konektor import berita_umum as U
from ..konektor import gdelt as k
from . import baca_raw


def ulang(snap: inti.Snapshot, m: dict) -> None:
    for nama in sorted(n for n in snap.berkas if n.startswith("bq/") and n.endswith(".jsonl")):
        isi = baca_raw(snap, nama)
        mulai, sampai = nama.removeprefix("bq/").removesuffix(".jsonl").split("_")
        rid = f"{k.SUMBER}:{k.kode_rilis_bq(mulai, sampai, inti.sha256_bita(isi))}"
        snap.tulis_bronze("artikel", k.baris_bronze(U.baca_jsonl(isi), "bq"), rid, nama)
    for nama in sorted(n for n in snap.berkas if n.startswith("gkg/")):
        isi = baca_raw(snap, nama)
        _, aliran, hari = nama.removesuffix(".jsonl").split("/")
        rid = f"{k.SUMBER}:{k.kode_rilis_hari(aliran, hari, snap.berkas[nama]['sha256_asli'])}"
        snap.tulis_bronze("artikel", k.baris_bronze(U.baca_jsonl(isi), aliran), rid, nama)
