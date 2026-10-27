"""Muat Silver, rekonsiliasi, dan data rujukan ke Iceberg (brief 4 M4).

Namespace ``silver``: ``observasi``, ``karantina``, ``fakta_selisih`` dari ``data/silver/gudang``.
Namespace ``rujukan``: tabel ``dp_referensi`` M1 (``artefak/referensi/*.csv``), ``dim_rilis`` M2, dan
``padanan_seri`` M3. Setiap tabel ditulis ulang utuh (drop lalu create) sehingga jalan ulang dari raw
menghasilkan isi yang sama; sidik isi dihitung kemudian dari Trino, bukan dari bita berkas Parquet.

    python3 -m sdg_gudang.gudang.muat
"""
from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from sdg_gudang.akuisisi import inti as A
from sdg_gudang.silver import inti as S

S3 = os.environ.get("GUDANG_S3", "127.0.0.1:28333")
REST = os.environ.get("GUDANG_REST", "http://127.0.0.1:28181")
KUNCI = os.environ.get("GUDANG_S3_KUNCI", "<kunci-s3-lokal>")
RAHASIA = os.environ.get("GUDANG_S3_RAHASIA", "<rahasia-s3-lokal>")
BUCKET = "gudang-sdg"
PROPS = {"write.target-file-size-bytes": str(32 * 1024 * 1024), "write.parquet.compression-codec": "zstd"}
KELUAR = A.MANIFEST / "m4_muat.json"

#: Kolom bertipe bukan teks; kolom lain teks.
TIPE = {"wilayah_kode": pa.int32(), "desimal": pa.int32(), "nilai_angka": pa.float64()}


def katalog():
    from pyiceberg.catalog import load_catalog

    return load_catalog("gudang", **{"type": "rest", "uri": REST, "s3.endpoint": f"http://{S3}",
                                     "s3.access-key-id": KUNCI, "s3.secret-access-key": RAHASIA,
                                     "s3.region": "us-east-1", "s3.path-style-access": "true"})


def pastikan_bucket() -> None:
    from pyarrow import fs as pafs

    s3 = pafs.S3FileSystem(access_key=KUNCI, secret_key=RAHASIA, endpoint_override=S3, scheme="http",
                           region="us-east-1", allow_bucket_creation=True)
    if s3.get_file_info(BUCKET).type == pafs.FileType.NotFound:
        s3.create_dir(BUCKET)


def ketik(t: pa.Table) -> pa.Table:
    """Kolom serba teks Silver ke tipe ``TIPE``; ``nilai_angka`` ditambahkan dari ``nilai``."""
    if "nilai" in t.column_names and "nilai_angka" not in t.column_names:
        t = t.append_column("nilai_angka", t["nilai"])
    skema = pa.schema([(f.name, TIPE.get(f.name, pa.string())) for f in t.schema])
    return t.cast(skema)


def baca_silver(pola: str, silver: Path = S.SILVER) -> pa.Table:
    bagian = [pq.read_table(p) for p in sorted(silver.glob(pola))]
    return pa.concat_tables(bagian, promote_options="default")


def baca_csv(p: Path) -> pa.Table:
    with p.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    kolom = list(rows[0]) if rows else []
    return pa.table({k: [r[k] for r in rows] for k in kolom}, schema=pa.schema([(k, pa.string()) for k in kolom]))


def tulis(cat, nama: str, t: pa.Table) -> dict:
    ns = nama.split(".")[0]
    if (ns,) not in cat.list_namespaces():
        cat.create_namespace(ns)
    if cat.table_exists(nama):
        cat.drop_table(nama)
    tab = cat.create_table(nama, schema=t.schema, properties=PROPS)
    tab.append(t)
    return {"baris": t.num_rows, "kolom": len(t.column_names)}


def sumber_tabel() -> dict[str, pa.Table]:
    from sdg_gudang import referensi as R

    out = {"silver.observasi": ketik(baca_silver("observasi/*/*.parquet")),
           "silver.karantina": baca_silver("karantina/*/*.parquet").cast(
               pa.schema([(k, pa.string()) for k in S.KOLOM_KARANTINA])),
           "silver.fakta_selisih": baca_silver("fakta_selisih.parquet")}
    out["silver.observasi"] = out["silver.observasi"].drop_columns(["nilai_angka"]).append_column(
        "nilai_angka", out["silver.observasi"]["nilai_angka"])
    for p in sorted(R.KELUAR.glob("*.csv")):
        out[f"rujukan.{p.stem}"] = baca_csv(p)
    out["rujukan.dim_rilis"] = baca_csv(A.MANIFEST / "dim_rilis.csv")
    out["rujukan.padanan_seri"] = baca_csv(S.PADANAN_SERI)
    return out


def jalankan() -> dict:
    pastikan_bucket()
    cat = katalog()
    hasil = {nama: tulis(cat, nama, t) for nama, t in sumber_tabel().items()}
    KELUAR.write_text(json.dumps({"dimuat_pada": A.sekarang(), "tabel": hasil}, indent=1) + "\n", "utf-8")
    return hasil


def main() -> int:
    print(json.dumps(jalankan(), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
