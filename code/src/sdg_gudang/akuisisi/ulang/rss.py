"""Bangun ulang Bronze ``rss`` dari XML aliran (utuh atau ekstrak tanpa teks penuh) di raw gudang."""
from __future__ import annotations

from .. import inti
from ..konektor import rss as k
from . import baca_raw


def ulang(snap: inti.Snapshot, m: dict) -> None:
    # Nama berkas feed/<kunci>/<HHMMSS>-<sha12>.xml: urutan nama = urutan pengambilan dalam satu hari.
    for nama in sorted(n for n in snap.berkas if n.startswith("feed/")):
        b = snap.berkas[nama]
        kunci = b.get("feed") or nama.split("/")[1]
        rows = k.baris_rss(k.urai_feed(baca_raw(snap, nama)), kunci)
        rid = f"{k.SUMBER}:{k.kode_rilis(kunci, b.get('sha256_asli') or b['sha256'])}"
        snap.tulis_bronze("artikel", rows, rid, nama)
