"""Bangun ulang Bronze ``ilostat`` (SDMX-CSV per dataflow) dari raw gudang."""
from __future__ import annotations

import json

from .. import inti
from ..konektor import ilostat as k
from . import baca_raw


def ulang(snap: inti.Snapshot, m: dict) -> None:
    dfs = {d["id"]: d for d in k.urai_dataflow(json.loads(baca_raw(snap, "metadata/dataflow.json")))}
    for nama in sorted(n for n in snap.berkas if n.startswith("data/")):
        info = snap.berkas[nama]
        df = dfs.get(info["dataflow"]) or {"id": info["dataflow"], "last_update": info.get("last_update", "")}
        rid = k.rilis_dari(df).rilis_id
        snap.tulis_bronze(df["id"].lower(), k.baris_csv(baca_raw(snap, nama)), rid, nama)
