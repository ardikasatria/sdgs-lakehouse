"""Bangun ulang Bronze ``who_gho`` (``fakta`` OData, ``fakta_datadot`` DATADOT, ``indikator``) dari raw gudang."""
from __future__ import annotations

import csv
import io
import json

from .. import inti
from ..konektor import who_gho as k
from . import baca_raw


def _fakta_odata(snap: inti.Snapshot, kode: str, sdg: str) -> int | None:
    nama = f"odata/{kode}.json"
    if nama not in snap.berkas:
        return None
    fakta, hal = [], 0
    while nama in snap.berkas:
        fakta.extend(json.loads(baca_raw(snap, nama)).get("value", []))
        hal += 1
        nama = f"odata/{kode}_p{hal}.json"
    if not fakta:
        return 0
    rid = f"{k.SUMBER}:{k.kode_rilis(kode, k.max_tanggal(fakta))}"
    rows = [dict(f) | {"sdg_indikator": sdg} for f in fakta]
    return snap.tulis_bronze("fakta", rows, rid, f"odata/{kode}.json")


def _fakta_datadot(snap: inti.Snapshot, kode: str, sdg: str, entri: dict) -> int | None:
    nama = f"datadot/{entri.get('UrlName')}_{kode}.csv"
    if nama not in snap.berkas:
        return None
    r = csv.reader(io.StringIO(baca_raw(snap, nama).decode("utf-8"), newline=""))
    header = next(r)
    baris = list(r)
    if not baris:
        return 0
    tgl = (entri.get("DataUpdateLast") or "").replace("Z", "")
    rid = f"{k.SUMBER}:{k.kode_rilis(kode, tgl)}"
    rows = [dict(zip(header, b)) | {"sdg_indikator": sdg} for b in baris]
    return snap.tulis_bronze("fakta_datadot", rows, rid, nama)


def ulang(snap: inti.Snapshot, m: dict) -> None:
    indikator = json.loads(baca_raw(snap, "odata/Indicator.json"))["value"]
    nama_gho = {x["IndicatorCode"]: x.get("IndicatorName") for x in indikator}
    dd = []
    for nama in sorted(n for n in snap.berkas if n.startswith("datadot/ddiindicators_skip")):
        dd.extend(json.loads(baca_raw(snap, nama)).get("value", []))
    pdd = k.peta_datadot(dd)
    ambil = k.klasifikasi(k.calon_dari_gho(indikator) | set(pdd))["ambil"]
    jalur = next((c.split(": ", 1)[1] for c in m.get("catatan", [])
                  if isinstance(c, str) and c.startswith("jalur data: ")), "datadot")
    # Subset opsi ``kode`` tidak tercatat di manifest; jalan penuh mencatat setiap kode dalam cakupan.
    per_kode = {}
    for kode in ambil:
        sdg = k.PETA_SDG[kode]
        per_kode[kode] = (_fakta_odata(snap, kode, sdg) if jalur == "odata"
                          else _fakta_datadot(snap, kode, sdg, pdd.get(kode, {})))
    rows = [{"IndicatorCode": kd, "IndicatorName": nama_gho.get(kd) or (pdd.get(kd) or {}).get("FullName"),
             "sdg_indikator": k.PETA_SDG[kd], "datadot_id": (pdd.get(kd) or {}).get("UrlName"),
             "jalur": jalur, "baris_indonesia": per_kode[kd]} for kd in ambil]
    rid = f"{k.SUMBER}:cakupan@{snap.tanggal}"
    if rid in snap.rilis:
        snap.tulis_bronze("indikator", rows, rid, "odata/Indicator.json")
