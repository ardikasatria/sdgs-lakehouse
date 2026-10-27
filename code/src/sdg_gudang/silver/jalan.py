"""Bangun Silver dari Bronze: pemeta per sumber, karantina, S08 kunci ganda, ringkasan dan sidik isi.

    python3 -m sdg_gudang.silver [sumber ...]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import io
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from sdg_gudang.akuisisi import inti as A

from . import inti as S

#: Keluarga pemeta per sumber (modul ``silver/pemeta/<modul>.py``).
PEMETA = {"bps": "bps", "unsd": "unsd", "unsd_arsip": "unsd", "wdi": "wdi", "wdi_arsip": "wdi",
          "ilostat": "ilostat", "who_gho": "who_gho", "bnpb": "bnpb", "sipsn": "sipsn",
          "signsmart": "signsmart", "kkp": "kkp"}
RINGKASAN = A.MANIFEST / "silver_ringkasan.json"
KUNCI_S08 = ("rilis_id", "seri_kode", "wilayah_kode", "periode", "rincian")


def tabel_bronze(sumber: str, bronze: Path = A.BRONZE) -> list[str]:
    d = bronze / sumber
    return sorted(p.name for p in d.iterdir() if p.is_dir()) if d.exists() else []


def sidik(rows: list[dict], kolom: list[str]) -> str:
    """sha256 isi baris yang diurutkan, sebagai CSV; tidak bergantung pada versi Parquet."""
    s = io.StringIO()
    w = csv.writer(s, lineterminator="\n")
    for r in sorted(tuple("" if r.get(k) is None else str(r.get(k)) for k in kolom) for r in rows):
        w.writerow(r)
    return hashlib.sha256(s.getvalue().encode("utf-8")).hexdigest()


def tulis_parquet(rows: list[dict], kolom: list[str], p: Path) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    p.parent.mkdir(parents=True, exist_ok=True)
    data = {k: [None if r.get(k) is None else str(r.get(k)) for r in rows] for k in kolom}
    pq.write_table(pa.table(data, schema=pa.schema([(k, pa.string()) for k in kolom])), p, compression="zstd")


def petakan_tabel(sumber: str, tabel: str, fungsi, ctx: S.Konteks, bronze: Path = A.BRONZE,
                  agregasi: dict | None = None) -> dict:
    """Petakan satu tabel Bronze. Kembalikan observasi, karantina, dan hitungan per hasil. ``agregasi`` (bobot,
    ambang) mengaktifkan S09 atas komponen kabupaten/kota; hasilnya dihitung terpisah dari sel Bronze."""
    t = A.baca_bronze(sumber, tabel, bronze=bronze)
    keluarga = S.KELUARGA[sumber]
    hitung = Counter()
    alasan = Counter()
    obs, kar, komponen = [], [], []
    baris_tanpa_sel = 0
    for i, b in enumerate(t.to_pylist()):
        umum = {"sumber": sumber, "keluarga": keluarga, "tabel_bronze": tabel, "rilis_id": b["_rilis_id"],
                "baris_bronze": f"{b['_snapshot']}:{i}", "_berkas_raw": b["_berkas_raw"],
                "_sha256_raw": b["_sha256_raw"], "_snapshot": b["_snapshot"]}
        n = 0
        for s in fungsi(b, ctx):
            n += 1
            if s.obs is not None:
                hitung["silver"] += 1
                obs.append(umum | s.obs)
            elif isinstance(s.gagal, S.Karantina):
                hitung["karantina"] += 1
                alasan[s.gagal.alasan] += 1
                kar.append(umum | {"seri_kode": s.seri_kode, "alasan": s.gagal.alasan, "aturan": s.gagal.aturan,
                                   "rincian_galat": s.gagal.rincian} | {f"teks_{k}": v for k, v in s.teks.items()})
            elif isinstance(s.gagal, S.Kosong):
                hitung["kosong"] += 1
            else:
                hitung["di_luar"] += 1
                alasan[f"di_luar:{s.gagal.alasan}"] += 1
                if agregasi is not None and getattr(s.gagal, "komponen", None):
                    komponen.append(umum | s.gagal.komponen)
        baris_tanpa_sel += n == 0
    if komponen:
        from .agregasi import agregasikan

        o9, k9 = agregasikan(komponen, agregasi.get("bobot"), agregasi.get("ambang"))
        obs += o9
        kar += k9
        hitung["agregat_silver"], hitung["agregat_karantina"] = len(o9), len(k9)
        if k9:
            alasan["cakupan_agregasi_kurang"] += len(k9)
    obs, kar_s08, gabung = s08(obs)
    hitung["silver"] -= len(kar_s08) + gabung  # S08 atas sel Bronze; observasi agregat S09 berkunci rilis sendiri
    hitung["karantina"] += len(kar_s08)
    hitung["gabung_s08"] = gabung
    if kar_s08:
        alasan["kunci_ganda_beda_nilai"] += len(kar_s08)
    kar += kar_s08
    return {"obs": obs, "kar": kar, "hitung": dict(hitung), "alasan": dict(alasan),
            "baris_bronze": t.num_rows, "baris_tanpa_sel": baris_tanpa_sel}


def s08(obs: list[dict]) -> tuple[list[dict], list[dict], int]:
    """S08: kunci sama nilai sama disatukan (baris pertama dipertahankan); kunci sama nilai beda -> karantina.
    Kembalikan observasi tetap, baris karantina, dan jumlah baris yang disatukan."""
    grup = defaultdict(list)
    for o in obs:
        grup[tuple(o[k] for k in KUNCI_S08)].append(o)
    tetap, kar, gabung = [], [], 0
    for rows in grup.values():
        if len({r["nilai"] for r in rows}) == 1:
            tetap.append(rows[0])
            gabung += len(rows) - 1
        else:
            for r in rows:
                kar.append({k: r.get(k) for k in S.KOLOM_KARANTINA if k in r} | {
                    "alasan": "kunci_ganda_beda_nilai", "aturan": "S08",
                    "rincian_galat": f"{len(rows)} baris, nilai {sorted({x['nilai'] for x in rows})[:4]}",
                    "teks_nilai": r["nilai"], "teks_periode": r["periode"], "teks_wilayah": str(r["wilayah_kode"])})
    return tetap, kar, gabung


def jalankan(sumber_pilih: list[str] | None = None, bronze: Path = A.BRONZE, keluar: Path = S.SILVER,
             ringkasan: Path = RINGKASAN) -> dict:
    ctx = S.Konteks()
    ringkas = json.loads(ringkasan.read_text("utf-8")) if ringkasan.exists() else {"tabel": {}}
    for sumber in sumber_pilih or list(PEMETA):
        modul = importlib.import_module(f".pemeta.{PEMETA[sumber]}", __package__)
        for tabel in tabel_bronze(sumber, bronze):
            kunci = f"{sumber}/{tabel}"
            if tabel in getattr(modul, "METADATA", ()):
                ringkas["tabel"][kunci] = {"jenis": "metadata"}
                continue
            fungsi = modul.TABEL.get(tabel) or modul.TABEL.get("*")
            if fungsi is None:
                ringkas["tabel"][kunci] = {"jenis": "tanpa_pemeta"}
                continue
            h = petakan_tabel(sumber, tabel, fungsi, ctx, bronze, getattr(modul, "AGREGASI", {}).get(tabel))
            tulis_parquet(h["obs"], S.KOLOM_OBSERVASI, keluar / "observasi" / sumber / f"{tabel}.parquet")
            tulis_parquet(h["kar"], S.KOLOM_KARANTINA, keluar / "karantina" / sumber / f"{tabel}.parquet")
            ringkas["tabel"][kunci] = {
                "jenis": "observasi", "baris_bronze": h["baris_bronze"], "baris_tanpa_sel": h["baris_tanpa_sel"],
                **{k: h["hitung"].get(k, 0) for k in ("silver", "karantina", "kosong", "di_luar", "gabung_s08",
                                                       "agregat_silver", "agregat_karantina")},
                "alasan": dict(sorted(h["alasan"].items())),
                "sidik_observasi": sidik(h["obs"], S.KOLOM_OBSERVASI)}
            print(json.dumps({kunci: {k: v for k, v in ringkas["tabel"][kunci].items() if k != "sidik_observasi"}},
                             ensure_ascii=False), file=sys.stderr)
    ringkas["tabel"] = dict(sorted(ringkas["tabel"].items()))
    ringkas["dibangun_pada"] = A.sekarang()
    ringkasan.write_text(json.dumps(ringkas, indent=1, ensure_ascii=False) + "\n", "utf-8")
    return ringkas


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Bangun Silver Gudang SDG (brief 4 M3)")
    ap.add_argument("sumber", nargs="*")
    ap.add_argument("--ringkasan", type=Path, default=RINGKASAN)
    a = ap.parse_args(argv)
    jalankan(a.sumber or None, ringkasan=a.ringkasan)
    return 0


if __name__ == "__main__":
    sys.exit(main())
