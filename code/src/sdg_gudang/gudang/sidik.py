"""Sidik isi Gold dan data product (brief 4 M4: rebuild dari raw memberi hash Gold yang sama).

Setiap tabel ``gold.*`` dan ``dp.*`` dibaca dari Trino, baris diurutkan sebagai teks, lalu di-hash sha256.
Sidik tidak bergantung pada bita berkas Parquet, nomor snapshot Iceberg, atau urutan tulis. Gabungan sidik
semua tabel adalah ``sidik_gold``.

    python3 -m sdg_gudang.gudang.sidik [--keluar BERKAS]
"""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

from sdg_gudang.akuisisi import inti as A

KELUAR = A.MANIFEST / "m4_sidik_gold.json"


def koneksi():
    import trino

    return trino.dbapi.connect(host=os.environ.get("GUDANG_TRINO_HOST", "127.0.0.1"),
                               port=int(os.environ.get("GUDANG_TRINO_PORT", "28080")), user="gudang",
                               catalog="iceberg")


def sidik_tabel(cur, nama: str) -> dict:
    cur.execute(f"select * from {nama}")
    kolom = [d[0] for d in cur.description]
    baris = sorted("\x1f".join("" if v is None else str(v) for v in r) for r in cur.fetchall())
    h = hashlib.sha256(("\x1e".join(kolom) + "\n").encode("utf-8"))
    for b in baris:
        h.update(b.encode("utf-8") + b"\n")
    return {"baris": len(baris), "kolom": len(kolom), "sha256": h.hexdigest()}


def jalankan(keluar: Path = KELUAR) -> dict:
    cur = koneksi().cursor()
    tabel = []
    for ns in ("gold", "dp"):
        cur.execute(f"show tables from {ns}")
        tabel += [f"{ns}.{r[0]}" for r in cur.fetchall()]
    per = {t: sidik_tabel(cur, t) for t in sorted(tabel)}
    gabung = hashlib.sha256("".join(f"{t}:{v['sha256']}\n" for t, v in per.items()).encode()).hexdigest()
    out = {"diukur_pada": A.sekarang(), "sidik_gold": gabung, "tabel": per}
    keluar.write_text(json.dumps(out, indent=1) + "\n", "utf-8")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Sidik isi Gold dan data product")
    ap.add_argument("--keluar", type=Path, default=KELUAR)
    a = ap.parse_args(argv)
    out = jalankan(a.keluar)
    print(json.dumps({"sidik_gold": out["sidik_gold"], "tabel": len(out["tabel"])}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
