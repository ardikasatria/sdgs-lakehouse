"""Uji ketersambungan antarlapis terhadap SLA (unit J.62DMS00.007.1 KUK 4.3 dan 4.4).

Ambang dibaca dari ``config/sla/lapis.yaml``, yang ditetapkan sebelum uji pertama. Satu jalan uji:

1. **Ingest.** sha256 setiap berkas Raw dicocokkan dengan manifest, dan umur snapshot terakhir per sumber diukur.
2. **Proses.** Job Dagster ``gudang_penuh`` dijalankan dari Raw tanpa jaringan dengan ``DAGSTER_HOME`` sendiri,
   sehingga waktu tiap langkah (Bronze, Silver, rekonsiliasi, kualitas, muat Iceberg, kontrak, dbt) dapat dibaca
   dari penyimpanan run. Hasil uji dbt dan keterlacakan Silver ikut diperiksa.
3. **Sajian.** Kesegaran setiap data product dibandingkan dengan ``sla.kesegaran_hari`` di YAML-nya, latency query
   titik ke setiap data product diukur lewat Trino, ekspor Gold ke masukan paket level dibandingkan sha256-nya
   dengan versi ter-commit, dan API game produksi dipanggil dari luar.
4. **Keterulangan.** Sidik Gold dihitung dan dibandingkan dengan acuan.

Hasil ditulis ke ``results/serkom/uji-sla-<waktu>.json`` dan log Markdown ``docs/serkom/J.62DMS00.007.1/log-uji-sla.md``.
Tumpukan gudang dihapus beserta volumenya lalu dinyalakan ulang di awal langkah proses. Manifest yang hanya berubah stempel waktunya dikembalikan ke
versi ter-commit setelah uji, seperti pada uji operasi.

    PYTHONPATH=src python -m sdg_gudang.gudang.uji_sla [--tanpa-api]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

import yaml

from sdg_gudang.akuisisi import inti as A
from sdg_gudang.gudang import sidik

AKAR = A.AKAR
KONFIG = AKAR / "config" / "sla" / "lapis.yaml"
MESH = AKAR / "config" / "mesh"
HASIL = AKAR / "results" / "serkom"
LOG_MD = AKAR / "docs" / "serkom" / "J.62DMS00.007.1" / "log-uji-sla.md"
MASUKAN = AKAR / "artefak" / "v4" / "masukan"
BERKAS_JEMBATAN = ("gudang_tayang.csv", "gudang_pasangan.csv", "keterkaitan_deret.csv", "keterkaitan_korelasi.csv")


def p95(xs: list[float]) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(0.95 * (len(xs) - 1))))]


def jalankan(cmd: list[str], env: dict | None = None) -> tuple[float, str]:
    t = time.perf_counter()
    r = subprocess.run(cmd, cwd=AKAR, env={**os.environ, **(env or {})}, capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(r.stdout[-3000:] + r.stderr[-3000:])
        raise SystemExit(f"gagal: {' '.join(cmd)}")
    return time.perf_counter() - t, r.stdout


def cek(nilai, ambang, lulus: bool, satuan: str = "") -> dict:
    return {"nilai": nilai, "ambang": ambang, "satuan": satuan, "lulus": bool(lulus)}


# ------------------------------------------------------------------------------------------------- ingest
def uji_ingest(sla: dict, tanggal: date) -> dict:
    manifest = sorted(A.MANIFEST.glob("*-????-??-??.json"))
    total, masalah, umur = 0, [], {}
    for p in manifest:
        m = json.loads(p.read_text("utf-8"))
        total += len(m.get("berkas", {}))
        masalah += [f"{p.name}: {x}" for x in A.verifikasi(p)]
        snap = date.fromisoformat(m["snapshot"][:10])
        umur[m["sumber"]] = min(umur.get(m["sumber"], 10**6), (tanggal - snap).days)
    integritas = (total - len(masalah)) / total if total else 0.0
    batas = sla["kesegaran_snapshot_hari"]
    return {
        "berkas_raw": total,
        "integritas_raw": cek(round(integritas, 4), sla["integritas_raw"], integritas >= sla["integritas_raw"]),
        "masalah": masalah[:20],
        "umur_snapshot_hari": umur,
        "kesegaran_snapshot": cek(max(umur.values()), batas, max(umur.values()) <= batas, "hari"),
    }


# ------------------------------------------------------------------------------------------------- proses
def langkah_dagster(home: Path) -> dict:
    os.environ["DAGSTER_HOME"] = str(home)
    from dagster import DagsterInstance

    inst = DagsterInstance.get()
    run = inst.get_runs(limit=1)[0]
    out = {}
    for s in inst.get_run_step_stats(run.run_id):
        out[s.step_key] = {"detik": round((s.end_time or 0) - (s.start_time or 0), 1), "status": str(s.status.value)}
    return {"run_id": run.run_id, "status": str(run.status.value), "langkah": out}


def hasil_dbt() -> dict:
    kandidat = sorted((AKAR / "dbt" / "gudang_sdg" / "target").rglob("run_results.json"), key=lambda p: p.stat().st_mtime)
    if not kandidat:
        return {"node": 0, "status": {}}
    rr = json.loads(kandidat[-1].read_text("utf-8"))
    st: dict = {}
    for r in rr.get("results", []):
        st[r["status"]] = st.get(r["status"], 0) + 1
    return {"node": len(rr.get("results", [])), "status": st, "berkas": str(kandidat[-1].relative_to(AKAR))}


COMPOSE = ["docker-compose", "-f", "infra/gudang/compose.yml"]
WADAH = ("gudang-sdg-trino-1", "gudang-sdg-iceberg-rest-1", "gudang-sdg-s3-1")


def tumpukan_dari_nol(batas_s: int = 300) -> dict:
    """Tumpukan dan volumenya dihapus lalu dinyalakan ulang, seperti uji operasi: Gold dibangun dari Raw saja."""
    t_turun, _ = jalankan([*COMPOSE, "down", "-v"])
    t_naik, _ = jalankan([*COMPOSE, "up", "-d"])
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < batas_s:
        st = [subprocess.run(["docker", "inspect", "-f", "{{.State.Health.Status}}", w], capture_output=True,
                             text=True).stdout.strip() for w in WADAH]
        if all(x == "healthy" for x in st):
            return {"turun_s": round(t_turun, 1), "naik_sampai_sehat_s": round(t_naik + time.perf_counter() - t0, 1)}
        time.sleep(3)
    raise SystemExit("tumpukan gudang tidak sehat dalam batas waktu")


def uji_proses(sla: dict) -> dict:
    home = Path(tempfile.mkdtemp(prefix="dagster-", dir=AKAR / "tmp"))
    tumpukan = tumpukan_dari_nol()
    t_parse, _ = jalankan_dbt_parse()
    t_job, _ = jalankan([sys.executable, "-m", "dagster", "job", "execute", "-m", "sdg_gudang.gudang.orkestrasi",
                         "-j", "gudang_penuh"], env={"DAGSTER_HOME": str(home), "PYTHONPATH": "src"})
    d = langkah_dagster(home)
    batas = sla["langkah_maks_s"]
    langkah = {k: cek(v["detik"], batas.get(k), batas.get(k) is None or v["detik"] <= batas[k], "s")
               for k, v in d["langkah"].items()}
    dbt = hasil_dbt()
    gagal = dbt["status"].get("error", 0) + dbt["status"].get("fail", 0)
    kualitas = json.loads((A.MANIFEST / "m3_kualitas.json").read_text("utf-8"))
    lacak = min(v.get("keterlacakan", 0.0) for v in kualitas["per_sumber"].values())
    return {
        "tumpukan": tumpukan,
        "dbt_parse_s": round(t_parse, 1),
        "job_s": cek(round(t_job, 1), sla["job_maks_s"], t_job <= sla["job_maks_s"], "s"),
        "run": {"run_id": d["run_id"], "status": d["status"]},
        "langkah": langkah,
        "dbt": dbt,
        "uji_dbt_gagal": cek(gagal, sla["uji_dbt_gagal_maks"], gagal <= sla["uji_dbt_gagal_maks"]),
        "keterlacakan_silver_min": cek(lacak, sla["keterlacakan"], lacak >= sla["keterlacakan"]),
    }


def jalankan_dbt_parse() -> tuple[float, str]:
    t = time.perf_counter()
    r = subprocess.run(["dbt", "parse", "--quiet"], cwd=AKAR / "dbt" / "gudang_sdg",
                       env={**os.environ, "DBT_PROFILES_DIR": "."}, capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(r.stdout[-3000:] + r.stderr[-3000:])
        raise SystemExit("gagal: dbt parse")
    return time.perf_counter() - t, r.stdout


# ------------------------------------------------------------------------------------------------- sajian
def uji_data_product(sla: dict, tanggal: date) -> dict:
    cur = sidik.koneksi().cursor()
    out = {}
    for y in sorted(MESH.glob("*.yaml")):
        p = yaml.safe_load(y.read_text("utf-8"))
        nama = p["nama"]
        cur.execute(f"show tables from dp like '{nama}%'")
        tabel = [r[0] for r in cur.fetchall()] or [nama]
        for t in tabel:
            cur.execute(f"select * from dp.{t} limit 0")
            kolom = [c[0] for c in cur.description]
            cur.execute(f"select count(*) from dp.{t}")
            n = cur.fetchone()[0]
            r = {"baris": cek(n, sla["baris_minimum"], n >= sla["baris_minimum"])}
            batas = (p.get("sla") or {}).get("kesegaran_hari")
            waktu = "berlaku_sejak" if "berlaku_sejak" in kolom else ("snapshot_pertama" if "snapshot_pertama" in kolom else None)
            if batas and waktu:
                cur.execute(f"select max({waktu}) from dp.{t}")
                terbaru = cur.fetchone()[0]
                terbaru = terbaru if isinstance(terbaru, date) else date.fromisoformat(str(terbaru)[:10])
                umur = (tanggal - terbaru).days
                r["kesegaran"] = cek(umur, batas, umur <= batas, "hari")
                r["rilis_terbaru"] = terbaru.isoformat()
            kunci = [k for k in ("konsep_id", "wilayah_kode") if k in kolom]
            lat = []
            if kunci:
                cur.execute(f"select distinct {', '.join(kunci)} from dp.{t} limit {sla['query_per_produk']}")
                titik = cur.fetchall()
                for nilai in titik:
                    syarat = " and ".join(f"{k} = {v!r}" if isinstance(v, str) else f"{k} = {v}" for k, v in zip(kunci, nilai))
                    t0 = time.perf_counter()
                    cur.execute(f"select * from dp.{t} where {syarat}")
                    cur.fetchall()
                    lat.append((time.perf_counter() - t0) * 1000)
            if lat:
                r["query_p95_ms"] = cek(round(p95(lat), 1), sla["query_p95_ms"], p95(lat) <= sla["query_p95_ms"], "ms")
                r["query_n"] = len(lat)
            out[t] = r
    return out


def uji_jembatan(sla: dict) -> dict:
    with tempfile.TemporaryDirectory(dir=AKAR / "tmp") as d:
        t, _ = jalankan([sys.executable, "-m", "sdg_game.jembatan", "ekspor",
                         "--ekspor", f"{d}/gudang_tayang.csv", "--pasangan", f"{d}/gudang_pasangan.csv",
                         "--deret", f"{d}/keterkaitan_deret.csv", "--korelasi", f"{d}/keterkaitan_korelasi.csv"],
                        env={"PYTHONPATH": "src"})
        sama = {f: hashlib.sha256((Path(d) / f).read_bytes()).hexdigest()
                == hashlib.sha256((MASUKAN / f).read_bytes()).hexdigest() for f in BERKAS_JEMBATAN}
    return {"waktu_s": cek(round(t, 1), sla["waktu_maks_s"], t <= sla["waktu_maks_s"], "s"),
            "identik": cek(sama, True, all(sama.values()))}


def uji_api(sla: dict, gzip: bool = False) -> dict:
    """Panggil API produksi dari luar. ``gzip=True`` meniru peramban (``Accept-Encoding: gzip``); tanpa itu jawaban
    dikirim tanpa kompresi."""
    lat, galat, bita = [], 0, 0
    kepala = {"User-Agent": "uji-sla-gudang"} | ({"Accept-Encoding": "gzip"} if gzip else {})
    for _ in range(sla["permintaan"]):
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(urllib.request.Request(sla["url"], headers=kepala), timeout=30) as r:
                bita = len(r.read())
                if r.status != 200:
                    galat += 1
        except Exception:  # noqa: BLE001 - setiap kegagalan dihitung sebagai galat
            galat += 1
        lat.append((time.perf_counter() - t0) * 1000)
        time.sleep(0.5)
    return {"url": sla["url"], "gzip": gzip, "bita_jawaban": bita, "p50_ms": round(statistics.median(lat), 1),
            "p95_ms": cek(round(p95(lat), 1), sla["p95_ms"], p95(lat) <= sla["p95_ms"], "ms"),
            "galat": cek(galat, sla["galat_maks"], galat <= sla["galat_maks"])}


# ------------------------------------------------------------------------------------------------- berita GDELT
def uji_gdelt(manifest: Path, sla: dict, durasi_s: float) -> dict:
    """Nilai satu jalan konektor GDELT jalur berkas dari manifestnya.

    Per (aliran, hari): berkas yang tercantum di masterfilelist = berkas berhasil + berkas gagal; SLA meminta 96
    berkas tercantum dan 0 gagal md5/unduh. Laju = total bita zip / durasi jalan; waktu per hari dari selisih
    stempel ``diunduh_pada`` ekstrak berurutan."""
    m = json.loads(manifest.read_text("utf-8"))
    hari, bita, stempel = {}, 0, []
    for nama, b in sorted(m["berkas"].items()):
        if not nama.startswith("gkg/"):
            continue
        _, aliran, h = nama.split("/")
        asal, gagal = b.get("asal", []), b.get("gagal", [])
        bita += sum(int(x.split()[2]) for x in asal)
        n = len(asal) + len(gagal)
        hari[f"{aliran}/{h[:8]}"] = {"berkas": len(asal), "gagal": len(gagal), "tercantum": n,
                                     "lengkap": n == sla["berkas_per_hari_per_aliran"] and not gagal}
        stempel.append(datetime.fromisoformat(b["diunduh_pada"]))
    stempel.sort()
    per_hari_s = [(b - a).total_seconds() for a, b in zip(stempel, stempel[1:])]
    laju = bita / 1e6 / durasi_s if durasi_s else 0.0
    gagal = sum(v["gagal"] for v in hari.values())
    lengkap = sum(v["lengkap"] for v in hari.values())
    # satu hari = dua aliran berurutan; batas per hari dibandingkan dengan dua kali median per ekstrak
    hari_menit = 2 * statistics.median(per_hari_s) / 60 if per_hari_s else durasi_s / 60
    return {
        "manifest": str(manifest.relative_to(AKAR)),
        "per_hari": hari,
        "bita_zip": bita,
        "durasi_s": round(durasi_s, 1),
        "berkas_lengkap": cek(f"{lengkap}/{len(hari)}", f"{len(hari)}/{len(hari)}", lengkap == len(hari)),
        "md5_dan_unduh_gagal": cek(gagal, sla["md5_gagal_maks"], gagal <= sla["md5_gagal_maks"]),
        "laju_mb_s": cek(round(laju, 1), sla["laju_min_mb_s"], laju >= sla["laju_min_mb_s"], "MB/s"),
        "satu_hari_menit": cek(round(hari_menit, 1), sla["hari_maks_menit"], hari_menit <= sla["hari_maks_menit"], "menit"),
    }


def tulis_md_gdelt(g: dict, opsi: str) -> str:
    baris = ["", "## Ingest berita GDELT pada jendela tanggal nyata", "",
             f"Perintah: `make m5-jalan-gdelt OPSI=\"{opsi}\"`; manifest `{g['manifest']}`. "
             f"Unduhan {g['bita_zip'] / 1e9:.2f} GB zip dalam {g['durasi_s']:.0f} s.", "",
             "| Pemeriksaan | Nilai | Ambang | Hasil |", "| --- | --- | --- | --- |"]
    for k in ("berkas_lengkap", "md5_dan_unduh_gagal", "laju_mb_s", "satu_hari_menit"):
        c = g[k]
        baris.append(f"| {k} | {c['nilai']} {c['satuan']} | {c['ambang']} {c['satuan']} | "
                     f"{'lulus' if c['lulus'] else '**gagal**'} |")
    baris += ["", "| Aliran/hari | Berkas | Gagal | Tercantum di masterfilelist |", "| --- | ---: | ---: | ---: |"]
    baris += [f"| {k} | {v['berkas']} | {v['gagal']} | {v['tercantum']} |" for k, v in g["per_hari"].items()]
    return "\n".join(baris) + "\n"


# ------------------------------------------------------------------------------------------------- laporan
def kumpulkan_cek(obj, jalur="") -> list[tuple[str, dict]]:
    out = []
    if isinstance(obj, dict):
        if set(obj) >= {"nilai", "ambang", "lulus"}:
            return [(jalur, obj)]
        for k, v in obj.items():
            out += kumpulkan_cek(v, f"{jalur}.{k}" if jalur else k)
    return out


def tulis_md(h: dict) -> str:
    semua = kumpulkan_cek({k: h[k] for k in ("ingest", "proses", "sajian", "keterulangan")})
    lulus = sum(c["lulus"] for _, c in semua)
    baris = [
        "# Log uji SLA antarlapis",
        "",
        f"Dibangkitkan oleh `python -m sdg_gudang.gudang.uji_sla` pada {h['mulai']} (commit `{h['commit']}`). "
        f"Ambang dari `config/sla/lapis.yaml` (ditetapkan {h['ambang_ditetapkan']}). Mesin: {h['mesin']}.",
        "",
        f"**Ringkasan:** {lulus} dari {len(semua)} pemeriksaan lulus. Sidik Gold `{h['keterulangan']['sidik_gold'][:8]}…`.",
        "",
        "| Lapis | Pemeriksaan | Nilai | Ambang | Hasil |",
        "| --- | --- | --- | --- | --- |",
    ]
    for jalur, c in semua:
        lapis, _, nama = jalur.partition(".")
        nilai = c["nilai"] if not isinstance(c["nilai"], dict) else ", ".join(f"{k}={v}" for k, v in c["nilai"].items())
        baris.append(f"| {lapis} | {nama} | {nilai} {c['satuan']} | {c['ambang']} {c['satuan']} | "
                     f"{'lulus' if c['lulus'] else '**gagal**'} |")
    baris += ["", "Waktu langkah job (detik): " + ", ".join(
        f"{k} {v['nilai']}" for k, v in h["proses"]["langkah"].items()) + ".", ""]
    return "\n".join(baris)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Uji ketersambungan antarlapis terhadap SLA")
    ap.add_argument("--tanpa-api", action="store_true", help="lewati panggilan ke API produksi")
    ap.add_argument("--hanya-api", action="store_true", help="ukur ulang API produksi tanpa kompresi dan dengan gzip")
    ap.add_argument("--gdelt", type=Path, help="hanya nilai manifest jalan GDELT (tanpa job gudang)")
    ap.add_argument("--durasi", type=float, default=0.0, help="durasi jalan GDELT dalam detik")
    ap.add_argument("--opsi", default="", help="opsi jalan GDELT, untuk dicatat di log")
    a = ap.parse_args(argv)
    sla = yaml.safe_load(KONFIG.read_text("utf-8"))
    if a.hanya_api:
        api = sla["sajian"]["api_produksi"]
        d = {"diukur_pada": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
             "tanpa_kompresi": uji_api(api), "gzip": uji_api(api, gzip=True)}
        HASIL.mkdir(parents=True, exist_ok=True)
        (HASIL / f"uji-sla-api-{datetime.now().strftime('%Y%m%dT%H%M')}.json").write_text(
            json.dumps(d, indent=1) + "\n", "utf-8")
        baris = ["", "## API produksi: diagnosis latency", "",
                 "Uji pertama memanggil API tanpa `Accept-Encoding`, sehingga daftar level dikirim tanpa kompresi. "
                 "Peramban selalu meminta gzip. Ambang tidak diubah; kedua cara diukur ulang dan dicatat "
                 f"({d['diukur_pada']}).", "",
                 "| Cara panggil | Ukuran jawaban | p50 | p95 | Ambang p95 | Hasil |", "| --- | ---: | ---: | ---: | ---: | --- |"]
        for k, v in (("tanpa kompresi", d["tanpa_kompresi"]), ("gzip (seperti peramban)", d["gzip"])):
            baris.append(f"| {k} | {v['bita_jawaban'] / 1000:.1f} KB | {v['p50_ms']:.0f} ms | {v['p95_ms']['nilai']:.0f} ms | "
                         f"{v['p95_ms']['ambang']} ms | {'lulus' if v['p95_ms']['lulus'] else '**gagal**'} |")
        isi = LOG_MD.read_text("utf-8").split("\n## API produksi: diagnosis latency")[0].rstrip()
        sisa = ""
        if "\n## Ingest berita GDELT" in isi:
            isi, sisa = isi.split("\n## Ingest berita GDELT", 1)
            sisa = "\n## Ingest berita GDELT" + sisa
        LOG_MD.write_text(isi.rstrip() + "\n" + "\n".join(baris) + "\n" + sisa, "utf-8")
        print(json.dumps({k: (v["p95_ms"] if isinstance(v, dict) else v) for k, v in d.items()}))
        return 0
    if a.gdelt:
        g = uji_gdelt(a.gdelt.resolve(), sla["ingest_berita_gdelt"], a.durasi)
        HASIL.mkdir(parents=True, exist_ok=True)
        berkas = HASIL / f"uji-sla-gdelt-{datetime.now().strftime('%Y%m%dT%H%M')}.json"
        berkas.write_text(json.dumps(g, indent=1, ensure_ascii=False) + "\n", "utf-8")
        isi = LOG_MD.read_text("utf-8") if LOG_MD.exists() else "# Log uji SLA antarlapis\n"
        isi = isi.split("\n## Ingest berita GDELT")[0].rstrip() + "\n" + tulis_md_gdelt(g, a.opsi)
        LOG_MD.write_text(isi, "utf-8")
        print(json.dumps({k: v for k, v in g.items() if k != "per_hari"}, ensure_ascii=False))
        return 0
    (AKAR / "tmp").mkdir(exist_ok=True)
    HASIL.mkdir(parents=True, exist_ok=True)
    bersih = set(subprocess.run(["git", "diff", "--name-only", "--", str(A.MANIFEST)], cwd=AKAR, capture_output=True,
                                text=True).stdout.split())
    try:
        mulai = datetime.now(timezone.utc).astimezone()
        tanggal = mulai.date()
        h = {
            "mulai": mulai.isoformat(timespec="seconds"),
            "commit": subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=AKAR, capture_output=True, text=True).stdout.strip(),
            "ambang_ditetapkan": str(sla["tanggal_ditetapkan"]),
            "mesin": f"{os.uname().sysname} {os.uname().machine}, {os.cpu_count()} inti",
        }
        print("ingest ...", flush=True)
        h["ingest"] = uji_ingest(sla["ingest"], tanggal)
        print("proses (job gudang_penuh) ...", flush=True)
        h["proses"] = uji_proses(sla["proses"])
        print("sajian ...", flush=True)
        h["sajian"] = {"data_product": uji_data_product(sla["sajian"]["data_product"], tanggal),
                       "jembatan_ke_paket": uji_jembatan(sla["sajian"]["jembatan_ke_paket"])}
        if not a.tanpa_api:
            h["sajian"]["api_produksi"] = uji_api(sla["sajian"]["api_produksi"])
        print("keterulangan (sidik Gold) ...", flush=True)
        with tempfile.TemporaryDirectory(dir=AKAR / "tmp") as d:
            s = sidik.jalankan(Path(d) / "sidik.json")
        acuan = sla["keterulangan"]["sidik_gold_acuan"]
        h["keterulangan"] = {"sidik_gold": s["sidik_gold"],
                             "sama_dengan_acuan": cek(s["sidik_gold"][:12], acuan[:12], s["sidik_gold"] == acuan)}
        h["selesai"] = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        berkas = HASIL / f"uji-sla-{mulai.strftime('%Y%m%dT%H%M')}.json"
        berkas.write_text(json.dumps(h, indent=1, ensure_ascii=False, default=str) + "\n", "utf-8")
        LOG_MD.write_text(tulis_md(h), "utf-8")
    finally:
        # manifest yang bersih sebelum uji hanya berubah stempel waktunya; dikembalikan ke versi ter-commit
        kotor = set(subprocess.run(["git", "diff", "--name-only", "--", str(A.MANIFEST)], cwd=AKAR,
                                   capture_output=True, text=True).stdout.split())
        pulih = sorted(kotor - bersih)
        if pulih:
            subprocess.run(["git", "checkout", "--", *pulih], cwd=AKAR, check=True)
    semua = kumpulkan_cek({k: h[k] for k in ("ingest", "proses", "sajian", "keterulangan")})
    print(json.dumps({"hasil": str(berkas.relative_to(AKAR)), "lulus": sum(c["lulus"] for _, c in semua),
                      "pemeriksaan": len(semua), "manifest_dipulihkan": len(pulih)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
