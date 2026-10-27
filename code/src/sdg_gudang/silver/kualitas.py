"""Laporan kualitas awal per sumber (brief 4 M3; unit J.62DMS00.012.1).

Dimensi dan standar minimum dibekukan di praregistrasi M3 Bagian 8. Keluaran:

- ``data/manifests/gudang/m3_kualitas.json``: ukuran per sumber dan per tabel.
- ``docs/serkom/J.62DMS00.012.1/kualitas-per-sumber.csv``: satu baris per sumber per dimensi dengan status
  memenuhi standar atau tidak.
- ``docs/serkom/J.62DMS00.012.1/prioritas-perbaikan.csv``: masalah (alasan karantina, pelanggaran validitas,
  kelengkapan rendah) diurutkan menurut baris terdampak x bobot dampak.

    python3 -m sdg_gudang.silver.kualitas
"""
from __future__ import annotations

import csv
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path

from sdg_gudang.akuisisi import inti as A

from . import inti as S
from .jalan import RINGKASAN as RINGKASAN_SILVER
from .rekonsiliasi import RINGKASAN as RINGKASAN_REKON

KELUAR_JSON = A.MANIFEST / "m3_kualitas.json"
SERKOM = S.AKAR / "docs" / "serkom" / "J.62DMS00.012.1"
STANDAR = {"keterpetakan": 0.95, "keunikan": 0, "validitas": 0.99, "kelengkapan": 0.90, "keterlacakan": 1.0}

#: Kata pada nama seri yang menandai persen yang sah di luar 0-100: angka kasar, laju, rasio, indeks, neraca
#: dan arus bersih, persen terhadap agregat lain (PDB, GNI, ekspor, anggaran), dan angka "% of relevant age
#: group" (angka kasar penyelesaian sekolah).
BUKAN_PROPORSI = re.compile(r"kasar|gross|laju|pertumbuhan|growth|rasio|ratio|indeks|index|parity|change|"
                            r"perubahan|annual|balance|surplus|deficit|net |of gdp|of gni|proportion of gdp|"
                            r"proportion of gni|of exports|approved budget|relevant age group|terhadap pdb", re.I)
SATUAN_TAK_NEGATIF = {"jumlah", "massa", "luas", "laju_massa", "massa_setara"}


def baca_parquet(pola: str, silver: Path = S.SILVER) -> list[dict]:
    import pyarrow.parquet as pq

    rows = []
    for p in sorted(silver.glob(pola)):
        rows += pq.read_table(p).to_pylist()
    return rows


def nama_seri() -> dict[tuple[str, str], str]:
    """Nama seri dari metadata Bronze per keluarga, untuk menentukan jenis proporsi."""
    out = {}

    def coba(sumber, tabel, kode, nama, awalan=""):
        try:
            for r in A.baca_bronze(sumber, tabel).select([kode, nama]).to_pylist():
                out[(S.KELUARGA[sumber], f"{awalan}{r[kode]}")] = r[nama] or ""
        except (FileNotFoundError, KeyError):
            pass

    coba("bps", "katalog_tabel", "var", "judul", "var")
    coba("unsd", "seri", "code", "description")
    coba("wdi", "seri_sdg46", "id", "name")
    coba("wdi", "indikator", "id", "name")
    coba("who_gho", "indikator", "IndicatorCode", "IndicatorName")
    return out


def satuan_jenis() -> dict[str, str]:
    with (S.AKAR / "artefak" / "referensi" / "dim_satuan.csv").open(encoding="utf-8") as f:
        return {r["satuan_id"]: r["jenis"] for r in csv.DictReader(f)}


def validitas(obs: list[dict], nama: dict, jenis: dict) -> tuple[Counter, Counter, list[dict]]:
    diuji, langgar, contoh = Counter(), Counter(), []
    for o in obs:
        j = jenis.get(o["satuan_id"], "")
        v = Decimal(o["nilai"])
        if o["satuan_id"] == "persen":
            if BUKAN_PROPORSI.search(nama.get((o["keluarga"], o["seri_kode"]), "")):
                continue
            ok = 0 <= v <= 100
        elif j in SATUAN_TAK_NEGATIF:
            ok = v >= 0
        else:
            continue
        diuji[o["sumber"]] += 1
        if not ok:
            langgar[o["sumber"]] += 1
            if len(contoh) < 200:
                contoh.append({k: o[k] for k in ("sumber", "seri_kode", "wilayah_kode", "periode", "rincian", "nilai",
                                                  "satuan_id")})
    return diuji, langgar, contoh


def kelengkapan(obs: list[dict], ruj: S.Rujukan) -> dict[str, dict]:
    """Provinsi berdata / provinsi berlaku as-of akhir tahun periode, per (sumber, seri, tahun), rincian total."""
    berlaku = {}
    for th in range(1960, 2031):
        tgl = f"{th}-12-31"
        n = 0
        for w in ruj.provinsi:
            try:
                ruj.r.versi_asof(w, tgl)
                n += 1
            except Exception:  # noqa: BLE001 - wilayah belum ada pada tanggal itu
                pass
        berlaku[str(th)] = n
    grup = defaultdict(set)
    for o in obs:
        if o["tingkat"] == "provinsi" and o["rincian"] == "total":
            grup[(o["sumber"], o["seri_kode"], o["periode"][:4], o["rilis_id"])].add(o["wilayah_kode"])
    per_sumber = defaultdict(list)
    for (sumber, seri, th, _), ws in grup.items():
        if berlaku.get(th):
            per_sumber[sumber].append(min(1.0, len(ws) / berlaku[th]))
    return {s: {"sel_seri_tahun": len(v), "rerata": round(statistics.mean(v), 4),
                "proporsi_memenuhi": round(sum(x >= STANDAR["kelengkapan"] for x in v) / len(v), 4)}
            for s, v in sorted(per_sumber.items())}


def ketepatan_waktu(obs: list[dict]) -> dict[str, dict]:
    """Median hari dari akhir periode ke rilis pertama yang memuat kunci itu; proporsi bukti tanggal lemah."""
    with (A.MANIFEST / "dim_rilis.csv").open(encoding="utf-8") as f:
        rilis = {r["rilis_id"]: r for r in csv.DictReader(f)}
    pertama = {}
    for o in obs:
        r = rilis.get(o["rilis_id"], {})
        if r.get("jenis_bukti_tanggal") not in ("rilis_resmi", "pembaruan_sumber") or not r.get("tanggal_rilis"):
            continue
        k = (o["sumber"], o["seri_kode"], o["wilayah_kode"], o["periode"], o["rincian"])
        t = r["tanggal_rilis"][:10]
        if k not in pertama or t < pertama[k]:
            pertama[k] = t
    jeda = defaultdict(list)
    for (sumber, *_, per, _), t in pertama.items():
        akhir = date(int(per[:4]), 12, 31)
        jeda[sumber].append((date.fromisoformat(t) - akhir).days)
    lemah = defaultdict(Counter)
    for r in rilis.values():
        lemah[r["sumber"]][r["jenis_bukti_tanggal"] in ("tanggal_unduh", "tanggal_unduh_berubah", "tidak_diketahui", "")] += 1
    out = {}
    for s in sorted(set(jeda) | set(lemah)):
        n = sum(lemah[s].values())
        out[s] = {"median_jeda_hari": statistics.median(jeda[s]) if jeda[s] else None,
                  "rilis": n, "proporsi_bukti_lemah": round(lemah[s][True] / n, 4) if n else None}
    return out


def keterlacakan(rows: list[dict]) -> tuple[Counter, Counter, list[str]]:
    """Baris per sumber dan baris yang ``_sha256_raw``-nya cocok dengan manifest."""
    sha = {}
    for p in A.MANIFEST.glob("*-????-??-??.json"):
        m = json.loads(p.read_text("utf-8"))
        for nama, b in m["berkas"].items():
            sha[f"{m['sumber']}/{m['snapshot']}/{nama}"] = b["sha256"]
    n, ok, gagal = Counter(), Counter(), set()
    for r in rows:
        n[r["sumber"]] += 1
        if sha.get(r["_berkas_raw"]) == r["_sha256_raw"]:
            ok[r["sumber"]] += 1
        else:
            gagal.add(r["_berkas_raw"])
    return n, ok, sorted(gagal)[:20]


def bobot(obs: list[dict]) -> dict[tuple[str, str], int]:
    """3 bila seri dipakai paket level (peta tabel Gold v3), 2 bila terpetakan ke katalog TPB, 1 selain itu."""
    with (S.AKAR / "artefak" / "referensi" / "peta_tabel_indikator.csv").open(encoding="utf-8") as f:
        level = {(("bps" if r["sumber"].startswith("BPS") else r["sumber"].lower()),
                  (f"var{r['sumber_id']}" if r["sumber"].startswith("BPS") else r["sumber_id"]))
                 for r in csv.DictReader(f)}
    out = {}
    for o in obs:
        k = (o["keluarga"], o["seri_kode"])
        out[k] = max(out.get(k, 1), 3 if k in level else 2 if o["indikator_id"] else 1)
    return out


def jalankan() -> dict:
    ringkas_silver = json.loads(RINGKASAN_SILVER.read_text("utf-8"))
    obs = baca_parquet("observasi/*/*.parquet")
    kar = baca_parquet("karantina/*/*.parquet")
    nama, jenis = nama_seri(), satuan_jenis()
    ruj = S.Rujukan()

    per_sumber = defaultdict(lambda: Counter())
    for k, t in ringkas_silver["tabel"].items():
        if t.get("jenis") != "observasi":
            continue
        s = k.split("/")[0]
        for f in ("baris_bronze", "silver", "karantina", "kosong", "di_luar", "gabung_s08"):
            per_sumber[s][f] += t.get(f, 0)
    keunikan = Counter(r["sumber"] for r in kar if r["alasan"] == "kunci_ganda_beda_nilai")
    diuji, langgar, contoh_langgar = validitas(obs, nama, jenis)
    lengkap = kelengkapan(obs, ruj)
    tepat = ketepatan_waktu(obs)
    n_lacak, ok_lacak, gagal_lacak = keterlacakan(obs + kar)
    rekon = json.loads(RINGKASAN_REKON.read_text("utf-8")) if RINGKASAN_REKON.exists() else {}
    konsistensi = (rekon.get("ringkasan", {}).get("sumber_x_sumber", {}) or {}).get("status_per_pasangan_keluarga", {})

    baris_csv, hasil = [], {}
    for s in sorted(per_sumber):
        c = per_sumber[s]
        terpetakan = (c["silver"] + c["gabung_s08"]) / max(1, c["silver"] + c["gabung_s08"] + c["karantina"])
        val = 1 - langgar[s] / diuji[s] if diuji[s] else None
        kons = {k: v for k, v in konsistensi.items() if S.KELUARGA[s] in k.split("x")}
        hasil[s] = {"hitungan": dict(c), "keterpetakan": round(terpetakan, 4), "keunikan": keunikan[s],
                    "validitas": None if val is None else round(val, 4), "validitas_diuji": diuji[s],
                    "kelengkapan": lengkap.get(s), "ketepatan_waktu": tepat.get(s),
                    "konsistensi": kons,
                    "keterlacakan": round(ok_lacak[s] / n_lacak[s], 4) if n_lacak[s] else None}
        for dim, nilai, std, ok in (
                ("keterpetakan", round(terpetakan, 4), "≥ 0,95", terpetakan >= STANDAR["keterpetakan"]),
                ("keunikan", keunikan[s], "0", keunikan[s] == 0),
                ("validitas", hasil[s]["validitas"], "≥ 0,99", val is None or val >= STANDAR["validitas"]),
                ("kelengkapan", (lengkap.get(s) or {}).get("rerata"), "≥ 0,90 per seri-tahun",
                 s not in lengkap or lengkap[s]["rerata"] >= STANDAR["kelengkapan"]),
                ("ketepatan_waktu", (tepat.get(s) or {}).get("median_jeda_hari"), "dilaporkan", None),
                ("keterlacakan", hasil[s]["keterlacakan"], "1,00", ok_lacak[s] == n_lacak[s])):
            baris_csv.append({"sumber": s, "dimensi": dim, "nilai": "" if nilai is None else nilai, "standar": std,
                              "memenuhi": "" if ok is None else ("ya" if ok else "tidak")})

    w = bobot(obs)
    masalah = Counter()
    for r in kar:
        masalah[(r["sumber"], r["alasan"], r["seri_kode"])] += 1
    for c in contoh_langgar:
        masalah[(c["sumber"], "di_luar_domain_satuan", c["seri_kode"])] += 1
    prioritas = sorted(({"sumber": s, "masalah": a, "seri_kode": k, "baris": n, "bobot": w.get((S.KELUARGA[s], k), 1),
                         "skor": n * w.get((S.KELUARGA[s], k), 1)} for (s, a, k), n in masalah.items()),
                       key=lambda x: (-x["skor"], x["sumber"], x["seri_kode"]))

    out = {"dibangun_pada": A.sekarang(), "standar": STANDAR, "per_sumber": hasil,
           "keterlacakan": {"baris": sum(n_lacak.values()), "cocok": sum(ok_lacak.values()),
                            "berkas_gagal": gagal_lacak},
           "contoh_pelanggaran_validitas": contoh_langgar[:50]}
    KELUAR_JSON.write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str) + "\n", "utf-8")
    SERKOM.mkdir(parents=True, exist_ok=True)
    for nama_berkas, rows in (("kualitas-per-sumber.csv", baris_csv), ("prioritas-perbaikan.csv", prioritas)):
        with (SERKOM / nama_berkas).open("w", encoding="utf-8", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
            wr.writeheader()
            wr.writerows(rows)
    return out


def main() -> int:
    out = jalankan()
    print(json.dumps({s: {k: v for k, v in h.items() if k in ("keterpetakan", "keunikan", "validitas")}
                      for s, h in out["per_sumber"].items()}, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
