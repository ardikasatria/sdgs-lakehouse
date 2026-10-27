"""Konektor ILOSTAT SDMX REST (``https://sdmx.ilo.org/rest``) untuk Indonesia.

Aturan cakupan: semua dataflow agensi ILO yang id-nya berawalan ``DF_SDG_`` ditambah
``DF_UNE_DEAP_SEX_AGE_RT`` (tingkat pengangguran yang sudah dipakai Gold v1). Untuk setiap dataflow:

- DSD diambil (``/datastructure/ILO/<dsd>/<versi>``) agar kunci seri dapat disusun dengan ``REF_AREA=IDN``
  pada posisi dimensi yang benar dan dimensi lain kosong (semua nilai);
- data diambil dalam SDMX-CSV 1.0 (``Accept: application/vnd.sdmx.data+csv;version=1.0.0``), disimpan apa
  adanya, dan diurai ke Bronze satu tabel per dataflow (nama tabel = id dataflow huruf kecil);
- rilis = anotasi ``LAST_UPDATE`` dataflow (``dd/mm/yyyy HH:MM:SS``, zona waktu tidak dinyatakan ILO),
  jenis bukti ``pembaruan_sumber``, ``kode_rilis = <dataflow>@<LAST_UPDATE ISO>``.

Dataflow tanpa data Indonesia (HTTP 404) tetap dicatat rilisnya dan disebut di catatan manifest.
Opsi: ``dataflow=DF_A,DF_B`` (batasi), ``jeda_s=1.0``.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import sys
import time

from .. import inti

SUMBER = "ilostat"

API = "https://sdmx.ilo.org/rest"
NEGARA = "IDN"
AWALAN = "DF_SDG_"
TAMBAHAN = ("DF_UNE_DEAP_SEX_AGE_RT",)
H_STRUKTUR = {"Accept": "application/vnd.sdmx.structure+json;version=1.0"}
H_CSV = {"Accept": "application/vnd.sdmx.data+csv;version=1.0.0"}


# ---------------------------------------------------------------------------------------------------
# Fungsi murni (diuji luring)
# ---------------------------------------------------------------------------------------------------

def iso_last_update(teks: str) -> str:
    """``'11/10/2026 07:57:07'`` (hari/bulan/tahun) -> ``'2026-10-11T07:57:07'``."""
    return dt.datetime.strptime(teks.strip(), "%d/%m/%Y %H:%M:%S").isoformat()


def urai_dataflow(js: dict) -> list[dict]:
    """Respons ``/dataflow`` SDMX-JSON -> ringkasan per dataflow."""
    out = []
    for x in js.get("data", {}).get("dataflows", []):
        ann = {a.get("type"): a.get("title", "") for a in x.get("annotations", [])}
        struk = x.get("structure", "")
        dsd = struk.split("=", 1)[1] if "=" in struk else ""          # 'ILO:SDG_0852_SEX_AGE_RT(1.0)'
        agensi, _, sisa = dsd.partition(":")
        dsd_id, _, ver = sisa.partition("(")
        out.append({"id": x.get("id"), "version": x.get("version"), "agencyID": x.get("agencyID"),
                    "name": x.get("name"), "last_update": ann.get("LAST_UPDATE", ""),
                    "dsd_agensi": agensi, "dsd_id": dsd_id, "dsd_versi": ver.rstrip(")")})
    return out


def pilih_dataflow(daftar: list[dict], awalan: str = AWALAN, tambahan=TAMBAHAN, batas: list[str] | None = None):
    pilih = [d for d in daftar if str(d["id"]).startswith(awalan) or d["id"] in tambahan]
    if batas:
        pilih = [d for d in pilih if d["id"] in batas]
    return sorted(pilih, key=lambda d: d["id"])


def dimensi_dsd(js: dict) -> list[str]:
    """Dimensi non-waktu DSD berurut posisi."""
    ds = js["data"]["dataStructures"][0]["dataStructureComponents"]["dimensionList"]["dimensions"]
    return [d["id"] for d in sorted(ds, key=lambda d: d.get("position", 0))]


def kunci_seri(dimensi: list[str], negara: str = NEGARA) -> str:
    """Kunci SDMX dengan REF_AREA terisi, dimensi lain kosong: ``['REF_AREA','FREQ','SEX'] -> 'IDN..'``."""
    if "REF_AREA" not in dimensi:
        raise ValueError("DSD tanpa dimensi REF_AREA")
    return ".".join(negara if d == "REF_AREA" else "" for d in dimensi)


def baris_csv(isi: bytes) -> list[dict]:
    """SDMX-CSV -> baris apa adanya (string kosong menjadi None)."""
    teks = isi.decode("utf-8-sig")
    return [{k: (v if v != "" else None) for k, v in r.items()} for r in csv.DictReader(io.StringIO(teks))]


def rilis_dari(df: dict, cakupan: str = "") -> inti.Rilis:
    lu = df.get("last_update", "")
    if lu:
        iso = iso_last_update(lu)
        return inti.Rilis("ilostat", f"{df['id']}@{iso}", "pembaruan_sumber", tanggal_rilis=iso,
                          bukti=f"anotasi LAST_UPDATE '{lu}' pada /dataflow/ILO/{df['id']} (zona waktu tidak dinyatakan)",
                          cakupan=cakupan or df["id"])
    return inti.Rilis("ilostat", f"{df['id']}@tanpa-LAST_UPDATE", "tanggal_unduh", cakupan=cakupan or df["id"])


# ---------------------------------------------------------------------------------------------------
# Jaringan
# ---------------------------------------------------------------------------------------------------

def _log(*a) -> None:
    print("[ilostat]", *a, file=sys.stderr, flush=True)


def jalankan(snap: inti.Snapshot, opsi: dict) -> dict:
    import requests

    t0 = time.monotonic()
    http = inti.Http(jeda_s=float(opsi.get("jeda_s", 1.0)), batas_waktu=300)
    url = f"{API}/dataflow/ILO/all/latest?detail=full"
    r = http.get(url, headers=H_STRUKTUR)
    snap.simpan("metadata/dataflow.json", r.content, url, peran="daftar dataflow ILO dengan anotasi LAST_UPDATE")
    semua = urai_dataflow(json.loads(r.content))
    batas = [x.strip() for x in opsi["dataflow"].split(",")] if opsi.get("dataflow") else None
    pilih = pilih_dataflow(semua, batas=batas)
    snap.catatan.append(f"aturan cakupan: dataflow berawalan {AWALAN} ditambah {', '.join(TAMBAHAN)}: "
                        f"{len(pilih)} dari {len(semua)} dataflow ILO")

    kosong, ringkas = [], {}
    for i, df in enumerate(pilih, 1):
        try:
            url = f"{API}/datastructure/{df['dsd_agensi']}/{df['dsd_id']}/{df['dsd_versi']}"
            r = http.get(url, headers=H_STRUKTUR)
            snap.simpan(f"dsd/{df['dsd_id']}.json", r.content, url, peran=f"DSD untuk {df['id']}")
            kunci = kunci_seri(dimensi_dsd(json.loads(r.content)))
            rid = snap.tambah_rilis(rilis_dari(df, f"{df['id']} ({df['name']}), REF_AREA={NEGARA}"))
            url = f"{API}/data/{df['agencyID']},{df['id']},{df['version']}/{kunci}"
            try:
                r = http.get(url, headers=H_CSV)
            except requests.HTTPError as e:
                if getattr(e.response, "status_code", None) == 404:
                    kosong.append(df["id"])
                    ringkas[df["id"]] = 0
                    _log(f"[{i}/{len(pilih)}] {df['id']}: tidak ada data {NEGARA}")
                    continue
                raise
            nama = f"data/{df['id']}.csv"
            snap.simpan(nama, r.content, url, format="SDMX-CSV 1.0", dataflow=df["id"], kunci=kunci,
                        last_update=df["last_update"])
            n = snap.tulis_bronze(df["id"].lower(), baris_csv(r.content), rid, nama)
            ringkas[df["id"]] = n
            if n == 0:
                kosong.append(df["id"])
            _log(f"[{i}/{len(pilih)}] {df['id']}: {n} baris, LAST_UPDATE {df['last_update']}")
        except Exception as e:
            snap.tambah_galat(f"dataflow {df['id']}", e)
            _log(f"[{i}/{len(pilih)}] {df['id']}: GAGAL {e}")
    if kosong:
        snap.catatan.append(f"dataflow tanpa data {NEGARA} ({len(kosong)}): {', '.join(kosong)}")
    return {"dataflow": len(pilih), "rilis": len(snap.rilis), "tanpa_data": kosong,
            "baris": sum(ringkas.values()), "galat": len(snap.galat), "detik": round(time.monotonic() - t0, 1)}
