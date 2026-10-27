"""Uji pembanding Spark untuk menjawab "kenapa tidak Spark?" dengan angka (unit J.62DMS00.007.1 KUK 3.1 dan 3.3).

Dua beban kerja nyata dari proyek ini dijalankan dengan data yang sama di Mac yang sama.

1. **Gudang.** Transformasi inti Gold: window ``lead()`` per (keluarga, seri, wilayah, periode, rincian) atas
   seluruh observasi Silver (sekitar 1,49 juta baris) untuk membentuk interval berlaku, ditambah agregasi per
   konsep. Mesin yang dibandingkan: Trino atas tabel Iceberg ``silver.observasi`` (yang dipakai gudang) dan Spark
   lokal atas berkas Parquet Silver yang sama. Waktu menyalakan Spark dicatat terpisah.
2. **Berita.** Penyaringan GKG GDELT ke domain media Indonesia. Sampel ``n`` zip 15 menit diunduh sekali untuk
   mengukur laju jaringan (satu utas dan ``pekerja`` utas), lalu disaring dengan (a) penyaring konektor yang
   sebenarnya, (b) penyaring Python ramping yang setara dengan versi Spark, dan (c) Spark. Spark tidak dapat
   membaca zip secara langsung, sehingga waktu ekstraksi zip ke CSV ikut dihitung pada jalur Spark.

Hasil: ``results/serkom/banding-spark-<waktu>.json`` dan ``docs/serkom/J.62DMS00.007.1/banding-spark.md``.
Butuh tumpukan gudang hidup (Trino), Java 17+, dan ``pyspark``.

    PYTHONPATH=src:. python -m eval.serkom.banding_spark --tanggal 2026-10-20 --n 12 --pekerja 8
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from sdg_gudang.akuisisi.konektor import berita_umum as U
from sdg_gudang.akuisisi.konektor import gdelt
from sdg_gudang.gudang import sidik

AKAR = Path(__file__).resolve().parents[2]
HASIL = AKAR / "results" / "serkom"
MD = AKAR / "docs" / "serkom" / "J.62DMS00.007.1" / "banding-spark.md"
KUNCI = "keluarga, seri_kode, wilayah_kode, periode, rincian"
SQL_WINDOW = (f"select count(*) as n, count(berlaku_sampai) as tergantikan from (select lead(rilis_id) over "
              f"(partition by {KUNCI} order by rilis_id) as berlaku_sampai from {{t}})")
SQL_AGREGAT = "select konsep_id, count(*) as n, count(distinct wilayah_kode) as w from {t} group by konsep_id"
POLA_HOST = r"^https?://(?:www\.)?([^/:]+)"


def waktu(f, *a, **k):
    t = time.perf_counter()
    r = f(*a, **k)
    return time.perf_counter() - t, r


def median3(f) -> tuple[float, list[float], object]:
    xs, r = [], None
    for _ in range(3):
        t, r = waktu(f)
        xs.append(round(t, 3))
    return statistics.median(xs), xs, r


# ------------------------------------------------------------------------------------------- beban gudang
def gudang_trino() -> dict:
    cur = sidik.koneksi().cursor()

    def tanya(sql):
        cur.execute(sql)
        return cur.fetchall()

    t = "silver.observasi"
    n = tanya(f"select count(*) from {t}")[0][0]
    w_med, w_xs, w_r = median3(lambda: tanya(SQL_WINDOW.format(t=t)))
    a_med, a_xs, a_r = median3(lambda: tanya(SQL_AGREGAT.format(t=t)))
    return {"baris": n, "window_s": w_med, "window_ulang": w_xs, "window_hasil": list(w_r[0]),
            "agregat_s": a_med, "agregat_ulang": a_xs, "agregat_konsep": len(a_r)}


def mulai_spark(inti: int):
    from pyspark.sql import SparkSession

    return (SparkSession.builder.master(f"local[{inti}]").appName("banding-gudang")
            .config("spark.driver.memory", "3g").config("spark.sql.shuffle.partitions", str(inti * 2))
            .config("spark.ui.enabled", "false").getOrCreate())


def silver_satu_berkas(folder: Path) -> Path:
    """Silver per sumber disatukan dan diketik persis seperti saat dimuat ke Iceberg (``muat``), agar kedua mesin
    membaca isi yang sama; waktu penyatuan tidak dihitung."""
    import pyarrow.parquet as pq

    from sdg_gudang.gudang import muat

    p = folder / "observasi.parquet"
    pq.write_table(muat.ketik(muat.baca_silver("observasi/*/*.parquet")), p)
    return p


def gudang_spark(spark, berkas: Path) -> dict:
    df = spark.read.parquet(str(berkas))
    df.createOrReplaceTempView("obs")
    n = df.count()
    w_med, w_xs, w_r = median3(lambda: spark.sql(SQL_WINDOW.format(t="obs")).collect())
    a_med, a_xs, a_r = median3(lambda: spark.sql(SQL_AGREGAT.format(t="obs")).collect())
    return {"baris": n, "window_s": w_med, "window_ulang": w_xs, "window_hasil": [w_r[0][0], w_r[0][1]],
            "agregat_s": a_med, "agregat_ulang": a_xs, "agregat_konsep": len(a_r)}


# ------------------------------------------------------------------------------------------- beban berita
def unduh(url: str, tujuan: Path) -> int:
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "banding-spark"}), timeout=120) as r:
        data = r.read()
    tujuan.write_bytes(data)
    return len(data)


def sampel_gdelt(tanggal: str, n: int, pekerja: int, folder: Path) -> dict:
    berkas = gdelt.berkas_langsung(tanggal, tanggal, "english")[:n]
    satu = berkas[: max(2, n // 4)]
    t1, b1 = waktu(lambda: sum(unduh(x["url"], folder / f"s-{i}.zip") for i, x in enumerate(satu)))
    for f in folder.glob("s-*.zip"):
        f.unlink()
    with ThreadPoolExecutor(max_workers=pekerja) as ex:
        tn, bn = waktu(lambda: sum(ex.map(lambda ix: unduh(ix[1]["url"], folder / f"{ix[0]:03d}.zip"), enumerate(berkas))))
    return {"berkas": len(berkas), "bita_zip": bn,
            "jaringan_1_utas_mb_s": round(b1 / 1e6 / t1, 1),
            f"jaringan_{pekerja}_utas_mb_s": round(bn / 1e6 / tn, 1)}


def saring_konektor(zips: list[Path]) -> int:
    n = 0
    for z in zips:
        with z.open("rb") as f:
            n += len(gdelt.saring_csv_gkg(gdelt._baris_zip(f), U.DOMAIN_ID))
    return n


def saring_ramping(zips: list[Path]) -> int:
    pola, dom, n = re.compile(POLA_HOST), set(U.DOMAIN_ID), 0
    for z in zips:
        with z.open("rb") as f:
            for b in gdelt._baris_zip(f):
                kol = b.split("\t", 5)
                if len(kol) > 4:
                    m = pola.match(kol[4])
                    if m and (m.group(1).lower() in dom or m.group(1).lower().split(".", 1)[-1] in dom):
                        n += 1
    return n


def berita_spark(spark, zips: list[Path], folder: Path) -> dict:
    from pyspark.sql import functions as F

    csv = folder / "csv"
    csv.mkdir(exist_ok=True)
    t_ekstrak, _ = waktu(lambda: [zipfile.ZipFile(z).extractall(csv) for z in zips])
    dom = list(U.DOMAIN_ID)

    def jalan():
        df = spark.read.text(str(csv))
        host = F.lower(F.regexp_extract(F.split(df.value, "\t").getItem(4), POLA_HOST, 1))
        induk = F.regexp_extract(host, r"^[^.]+\.(.+)$", 1)
        return df.where(host.isin(dom) | induk.isin(dom)).count()

    med, xs, n = median3(jalan)
    bita_csv = sum(p.stat().st_size for p in csv.rglob("*") if p.is_file())
    shutil.rmtree(csv)
    return {"ekstrak_zip_s": round(t_ekstrak, 2), "saring_s": med, "saring_ulang": xs, "baris_cocok": n,
            "bita_csv": bita_csv}


# ------------------------------------------------------------------------------------------- laporan
def tulis_md(h: dict) -> str:
    g, b = h["gudang"], h["berita"]
    zmb = b["sampel"]["bita_zip"] / 1e6
    jar = [v for k, v in b["sampel"].items() if k.startswith("jaringan_") and not k.startswith("jaringan_1_")][0]
    baris = [
        "# Uji pembanding: kenapa tidak Spark?",
        "",
        f"Dibangkitkan oleh `python -m eval.serkom.banding_spark` pada {h['mulai']} (commit `{h['commit']}`). "
        f"Mesin: {h['mesin']}. Spark {h['spark_versi']} lokal `local[{h['inti']}]`, driver 3 GB; Java {h['java']}.",
        "",
        "## 1. Beban gudang: window bitemporal atas Silver",
        "",
        f"Data: {g['trino']['baris']:,} observasi Silver. Waktu median dari tiga ulangan; menyalakan Spark "
        f"(JVM dan sesi) {h['spark_mulai_s']:.1f} s dicatat terpisah.".replace(",", "."),
        "",
        "| Mesin | Window `lead()` (s) | Agregasi per konsep (s) | Hasil window (n, tergantikan) |",
        "| --- | ---: | ---: | --- |",
        f"| Trino 476 atas Iceberg (dipakai gudang) | {g['trino']['window_s']:.2f} | {g['trino']['agregat_s']:.2f} | "
        f"{g['trino']['window_hasil']} |",
        f"| Spark lokal atas Parquet | {g['spark']['window_s']:.2f} | {g['spark']['agregat_s']:.2f} | "
        f"{g['spark']['window_hasil']} |",
        "",
        "## 2. Beban berita: saring GKG GDELT ke media Indonesia",
        "",
        f"Sampel: {b['sampel']['berkas']} zip GKG berbahasa Inggris tanggal {h['tanggal']} ({zmb:.0f} MB zip). "
        f"Laju jaringan: {b['sampel']['jaringan_1_utas_mb_s']} MB/s satu utas, {jar} MB/s {h['pekerja']} utas.",
        "",
        "| Jalur | Waktu (s) | Laju (MB zip/s) | Baris cocok |",
        "| --- | ---: | ---: | ---: |",
        f"| Python, penyaring konektor (satu inti) | {b['python_konektor_s']:.2f} | {zmb / b['python_konektor_s']:.0f} | "
        f"{b['python_konektor_baris']} |",
        f"| Python, penyaring ramping (satu inti) | {b['python_ramping_s']:.2f} | {zmb / b['python_ramping_s']:.0f} | "
        f"{b['python_ramping_baris']} |",
        f"| Spark: ekstrak zip + saring ({h['inti']} inti) | {b['spark']['ekstrak_zip_s'] + b['spark']['saring_s']:.2f} | "
        f"{zmb / (b['spark']['ekstrak_zip_s'] + b['spark']['saring_s']):.0f} | {b['spark']['baris_cocok']} |",
        "",
    ]
    return "\n".join(baris)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Uji pembanding Spark")
    ap.add_argument("--tanggal", default="2026-10-20")
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--pekerja", type=int, default=8)
    a = ap.parse_args(argv)
    inti = os.cpu_count() or 8
    HASIL.mkdir(parents=True, exist_ok=True)
    mulai = datetime.now(timezone.utc).astimezone()
    java = subprocess.run(["java", "-version"], capture_output=True, text=True).stderr.splitlines()[0]
    import pyspark

    h = {"mulai": mulai.isoformat(timespec="seconds"), "tanggal": a.tanggal, "pekerja": a.pekerja, "inti": inti,
         "commit": subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=AKAR, capture_output=True, text=True).stdout.strip(),
         "mesin": f"{os.uname().sysname} {os.uname().machine}, {inti} inti", "java": java, "spark_versi": pyspark.__version__}
    print("gudang: Trino ...", flush=True)
    h["gudang"] = {"trino": gudang_trino()}
    print("gudang: Spark ...", flush=True)
    h["spark_mulai_s"], spark = waktu(mulai_spark, inti)
    with tempfile.TemporaryDirectory(dir=AKAR / "tmp") as d:
        h["gudang"]["spark"] = gudang_spark(spark, silver_satu_berkas(Path(d)))
    with tempfile.TemporaryDirectory(dir=AKAR / "tmp") as d:
        folder = Path(d)
        print("berita: unduh sampel ...", flush=True)
        sampel = sampel_gdelt(a.tanggal, a.n, a.pekerja, folder)
        zips = sorted(folder.glob("[0-9][0-9][0-9].zip"))
        print("berita: saring ...", flush=True)
        tk, nk = waktu(saring_konektor, zips)
        tr, nr = waktu(saring_ramping, zips)
        h["berita"] = {"sampel": sampel, "python_konektor_s": round(tk, 2), "python_konektor_baris": nk,
                       "python_ramping_s": round(tr, 2), "python_ramping_baris": nr,
                       "spark": berita_spark(spark, zips, folder)}
    spark.stop()
    berkas = HASIL / f"banding-spark-{mulai.strftime('%Y%m%dT%H%M')}.json"
    berkas.write_text(json.dumps(h, indent=1, ensure_ascii=False, default=str) + "\n", "utf-8")
    MD.write_text(tulis_md(h), "utf-8")
    print(json.dumps({"hasil": str(berkas.relative_to(AKAR))}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
