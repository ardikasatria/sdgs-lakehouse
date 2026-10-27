"""Bangun ulang Bronze ``ccnews`` dari ekstrak metadata per WARC di raw gudang (WARC asli tidak disimpan)."""
from __future__ import annotations

from .. import inti
from ..konektor import berita_umum as U
from ..konektor import ccnews as k
from . import baca_raw


def ulang(snap: inti.Snapshot, m: dict) -> None:
    for nama in sorted(n for n in snap.berkas if n.startswith("warc/")):
        warc = nama.removeprefix("warc/").removesuffix(".jsonl")
        rows = U.baca_jsonl(baca_raw(snap, nama))
        snap.tulis_bronze("artikel", k.baris_bronze(rows, warc), f"{k.SUMBER}:{warc}", nama)
