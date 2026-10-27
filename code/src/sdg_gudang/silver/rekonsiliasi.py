"""Rekonsiliasi multisumber sadar vintage (brief 4 M3): pasangan, status K0, kelas sebab K1-K9.

Aturan dibekukan di ``docs/gudang/m3-praregistrasi-rekonsiliasi.md`` dan
``config/rekonsiliasi/aturan_rekonsiliasi.csv``; padanan seri di ``config/rekonsiliasi/padanan_seri.csv``.
Modul ini menolak berjalan bila salah satu dari ketiga berkas itu mempunyai perubahan yang belum di-commit,
dan mencatat sha256 serta commit terakhir ketiganya di setiap keluaran.

Operasionalisasi yang tidak tertulis rinci di praregistrasi, dicatat di laporan M3 sebagai klarifikasi:

- **Tanggal rilis** dari ``dim_rilis.csv``; bila kosong, ``batas_atas`` bila tercatat, lalu ``snapshot_pertama``
  (Bagian 5). Urutan ``batas_atas`` ditambahkan 21 Okt 2026 (penyimpangan 2 laporan M3): arsip PBB
  ``2019.Q1.G.01`` hanya mempunyai batas atas, dan tanpa itu diurutkan sebagai rilis PBB terbaru.
- **K2**: wilayah terdampak pemekaran (induk atau pecahan di ``referensi.PEMEKARAN``) dan tanggal rilis kedua
  sisi mengapit tanggal berlakunya pemekaran, atau salah satu sisi bertanda ``cakupan_parsial``.
- **Periode sumber x sumber**: seri yang padanannya menyatakan ``bulan_dipakai`` dipasangkan pada tahun
  dengan observasi bulan atau semester acuan itu; ``jenis_periode`` asli tetap dibawa sehingga K4 dapat menilai.
- **Satuan sumber x sumber**: satuan pasangan adalah ``satuan_id`` padanan (dikurasi dari metadata).

    python3 -m sdg_gudang.silver.rekonsiliasi
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import subprocess
import sys
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

from sdg_gudang import referensi as R
from sdg_gudang.akuisisi import inti as A

from . import inti as S
from .jalan import tulis_parquet

PRAREG = S.AKAR / "docs" / "gudang" / "m3-praregistrasi-rekonsiliasi.md"
ATURAN = S.AKAR / "config" / "rekonsiliasi" / "aturan_rekonsiliasi.csv"
BEKU = (PRAREG, ATURAN, S.PADANAN_SERI)
RINGKASAN = A.MANIFEST / "m3_rekonsiliasi_ringkasan.json"
KELUARGA_INTERNASIONAL = {"unsd", "wdi", "ilostat", "who_gho"}

KOLOM_SELISIH = [
    "jenis_pasangan", "konsep_id", "wilayah_kode", "periode", "rincian",
    "keluarga_a", "sumber_a", "rilis_a", "seri_a", "nilai_a", "desimal_a", "tanggal_rilis_a", "jenis_periode_a",
    "sifat_a", "hubungan_a",
    "keluarga_b", "sumber_b", "rilis_b", "seri_b", "nilai_b", "desimal_b", "tanggal_rilis_b", "jenis_periode_b",
    "sifat_b", "hubungan_b",
    "satuan_a", "satuan_b", "status", "selisih_mutlak", "selisih_relatif", "kelas_sebab", "aturan", "tingkat_bukti",
    "alasan", "jeda_hari",
]


# ---------------------------------------------------------------------------------------------------
# Penjaga praregistrasi
# ---------------------------------------------------------------------------------------------------

def jejak_beku() -> dict:
    """sha256 dan commit terakhir berkas beku; galat bila ada perubahan yang belum di-commit."""
    out = {}
    for p in BEKU:
        rel = str(p.relative_to(S.AKAR))
        kotor = subprocess.run(["git", "status", "--porcelain", "--", rel], cwd=S.AKAR, capture_output=True,
                               text=True, check=True).stdout.strip()
        commit = subprocess.run(["git", "log", "-1", "--format=%H %cI", "--", rel], cwd=S.AKAR,
                                capture_output=True, text=True, check=True).stdout.strip()
        if kotor or not commit:
            raise RuntimeError(f"{rel} belum di-commit atau berubah; perbandingan ditolak (praregistrasi M3)")
        out[rel] = {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "commit": commit}
    return out


# ---------------------------------------------------------------------------------------------------
# Bahan
# ---------------------------------------------------------------------------------------------------

def tanggal_efektif(r: dict) -> str:
    """Tanggal rilis; bila kosong, batas atas tanggal rilis; bila kosong juga, tanggal snapshot pertama."""
    return (r.get("tanggal_rilis") or r.get("batas_atas") or r.get("snapshot_pertama") or "")[:10]


def baca_rilis() -> dict[str, str]:
    with (A.MANIFEST / "dim_rilis.csv").open(encoding="utf-8") as f:
        return {r["rilis_id"]: tanggal_efektif(r) for r in csv.DictReader(f)}


def baca_observasi(silver: Path = S.SILVER) -> list[dict]:
    import pyarrow.parquet as pq

    rows = []
    for p in sorted((silver / "observasi").glob("*/*.parquet")):
        rows += pq.read_table(p).to_pylist()
    return rows


def baca_padanan() -> list[dict]:
    with S.PADANAN_SERI.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def wilayah_pemekaran() -> dict[int, list[str]]:
    """wilayah_kode induk atau pecahan -> tanggal berlaku pemekaran yang menyentuhnya."""
    out = defaultdict(list)
    for p in R.PEMEKARAN:
        for k in (p.kode_bps, p.induk_bps):
            out[int(k) * 100].append(p.berlaku)
    return out


# ---------------------------------------------------------------------------------------------------
# K0: status
# ---------------------------------------------------------------------------------------------------

def satu_satuan_terakhir(o: dict) -> Decimal:
    """Satu satuan pada desimal terakhir yang tersaji sumber, dalam satuan kanonik (dikali faktor S04)."""
    return Decimal(1).scaleb(-int(o.get("desimal") or 0)) * Decimal(o.get("faktor_satuan") or "1")


def status(a: dict, b: dict) -> tuple[str, Decimal]:
    """K0a sama, K0b pembulatan (selisih <= satu satuan desimal terakhir sisi yang lebih kasar), atau selisih."""
    na, nb = Decimal(a["nilai"]), Decimal(b["nilai"])
    d = abs(na - nb)
    if d == 0:
        return "sama", d
    return ("pembulatan" if d <= max(satu_satuan_terakhir(a), satu_satuan_terakhir(b)) else "selisih"), d


# ---------------------------------------------------------------------------------------------------
# K1-K9
# ---------------------------------------------------------------------------------------------------

def k1_skala(a: dict, b: dict) -> str:
    if a["satuan"] != b["satuan"] and "tidak_ada" not in (a["satuan"], b["satuan"]):
        return f"satuan {a['satuan']} lawan {b['satuan']}"
    na, nb = float(a["nilai"]), float(b["nilai"])
    if na == 0 or nb == 0 or (na < 0) != (nb < 0):
        return ""
    lg = math.log10(abs(na / nb))
    k = round(lg)
    if k != 0 and abs(k) <= 6 and abs(abs(na / nb) / 10 ** k - 1) <= 0.01:
        return f"rasio nilai {na / nb:.6g} ~ 10^{k}"
    return ""


def k2_wilayah(a: dict, b: dict, wilayah: int, pemekaran: dict[int, list[str]]) -> str:
    if a.get("cakupan_parsial") or b.get("cakupan_parsial"):
        return f"cakupan parsial: {a.get('cakupan_parsial') or b.get('cakupan_parsial')}"
    for t in pemekaran.get(wilayah, []):
        lo, hi = sorted((a["tanggal_rilis"], b["tanggal_rilis"]))
        if lo < t <= hi:
            return f"rilis mengapit pemekaran {t}"
    return ""


def k3_granularitas(a: dict, b: dict) -> str:
    if a.get("agregasi") or b.get("agregasi"):
        return f"agregasi Silver: {a.get('agregasi') or b.get('agregasi')}"
    return "tingkat berbeda" if a["tingkat"] != b["tingkat"] else ""


def k4_periode(a: dict, b: dict) -> str:
    if a["jenis_periode"] != b["jenis_periode"]:
        return f"jenis periode {a['jenis_periode']} lawan {b['jenis_periode']}"
    if (a.get("bulan_acuan") or "") != (b.get("bulan_acuan") or ""):
        return f"bulan acuan {a.get('bulan_acuan') or '-'} lawan {b.get('bulan_acuan') or '-'}"
    return ""


def k5_definisi(a: dict, b: dict) -> str:
    beda = [f"{x['keluarga']}:{x['hubungan']}" for x in (a, b) if x.get("hubungan") not in ("", None, "sama", "metodologi_beda")]
    return "hubungan padanan " + ", ".join(beda) if beda else ""


def k7_turunan(a: dict, b: dict, riwayat_bps: dict) -> tuple[str, int | None]:
    """Sumber internasional yang nilainya sama dengan nilai BPS dari rilis lain untuk kunci yang sama."""
    if {a["keluarga"], b["keluarga"]} & {"bps"} and ({a["keluarga"], b["keluarga"]} & KELUARGA_INTERNASIONAL):
        bps, intl = (a, b) if a["keluarga"] == "bps" else (b, a)
        for lain in riwayat_bps.get(bps["kunci_bps"], []):
            if lain["rilis_id"] == bps["rilis_id"]:
                continue
            if status(intl, lain)[0] in ("sama", "pembulatan"):
                from datetime import date
                jeda = (date.fromisoformat(intl["tanggal_rilis"]) - date.fromisoformat(lain["tanggal_rilis"])).days
                return f"sama dengan BPS {lain['rilis_id']}", jeda
    return "", None


def k8_metodologi(a: dict, b: dict) -> str:
    sifat = {a["sifat"], b["sifat"]}
    if sifat & {"estimasi", "model"} and sifat & {"resmi", "disesuaikan"}:
        return f"sifat {a['sifat']} lawan {b['sifat']}"
    if "metodologi_beda" in (a.get("hubungan"), b.get("hubungan")):
        return "hubungan padanan metodologi_beda"
    return ""


def klasifikasi(jenis: str, a: dict, b: dict, wilayah: int, pemekaran, riwayat_bps) -> dict:
    """Aturan pertama yang cocok, urut K1..K9 (praregistrasi Bagian 4)."""
    urutan = [("K1", "satuan_skala", "teramati", lambda: k1_skala(a, b)),
              ("K2", "cakupan_wilayah", "kandidat", lambda: k2_wilayah(a, b, wilayah, pemekaran)),
              ("K3", "granularitas", "teramati", lambda: k3_granularitas(a, b)),
              ("K4", "periode_acuan", "kandidat", lambda: k4_periode(a, b)),
              ("K5", "definisi", "kandidat", lambda: k5_definisi(a, b) if jenis == "sumber_x_sumber" else "")]
    if jenis == "rilis_x_rilis":
        urutan.append(("K6", "vintage", "teramati", lambda: "dua rilis berurutan satu keluarga"))
    for aturan, kelas, bukti, uji in urutan:
        alasan = uji()
        if alasan:
            return {"kelas_sebab": kelas, "aturan": aturan, "tingkat_bukti": bukti, "alasan": alasan}
    if jenis == "sumber_x_sumber":
        alasan, jeda = k7_turunan(a, b, riwayat_bps)
        if alasan:
            return {"kelas_sebab": "turunan", "aturan": "K7", "tingkat_bukti": "teramati", "alasan": alasan,
                    "jeda_hari": jeda}
        alasan = k8_metodologi(a, b)
        if alasan:
            return {"kelas_sebab": "metodologi", "aturan": "K8", "tingkat_bukti": "kandidat", "alasan": alasan}
    return {"kelas_sebab": "tidak_terjelaskan", "aturan": "K9", "tingkat_bukti": "tidak_terselesaikan",
            "alasan": "tidak ada aturan K1-K8 yang cocok"}


# ---------------------------------------------------------------------------------------------------
# Pasangan
# ---------------------------------------------------------------------------------------------------

def baris_pasangan(jenis: str, konsep: str, kunci: tuple, a: dict, b: dict, pemekaran, riwayat_bps) -> dict:
    st, d = status(a, b)
    out = {"jenis_pasangan": jenis, "konsep_id": konsep, "wilayah_kode": kunci[0], "periode": kunci[1],
           "rincian": kunci[2], "status": st, "selisih_mutlak": str(d),
           "selisih_relatif": "" if Decimal(a["nilai"]) == 0 else f"{float(d / abs(Decimal(a['nilai']))):.6g}",
           "satuan_a": a["satuan"], "satuan_b": b["satuan"]}
    for sisi, o in (("a", a), ("b", b)):
        out |= {f"keluarga_{sisi}": o["keluarga"], f"sumber_{sisi}": o["sumber"], f"rilis_{sisi}": o["rilis_id"],
                f"seri_{sisi}": o["seri_kode"], f"nilai_{sisi}": o["nilai"], f"desimal_{sisi}": o["desimal"],
                f"tanggal_rilis_{sisi}": o["tanggal_rilis"], f"jenis_periode_{sisi}": o["jenis_periode"],
                f"sifat_{sisi}": o["sifat"], f"hubungan_{sisi}": o.get("hubungan", "")}
    if st == "selisih":
        out |= klasifikasi(jenis, a, b, int(kunci[0]), pemekaran, riwayat_bps)
    return out


def rilis_x_rilis(obs: list[dict], pemekaran) -> list[dict]:
    """Dua rilis berurutan menurut (tanggal_rilis, rilis_id) dalam satu keluarga, seri, dan kunci."""
    grup = defaultdict(list)
    for o in obs:
        grup[(o["keluarga"], o["seri_kode"], o["wilayah_kode"], o["periode"], o["rincian"])].append(o)
    out = []
    for (kel, seri, w, per, rin), rows in grup.items():
        per_rilis = {}
        for o in rows:  # satu observasi per rilis (S08 sudah menjamin kunci unik per rilis dalam satu tabel)
            per_rilis.setdefault(o["rilis_id"], o)
        urut = sorted(per_rilis.values(), key=lambda o: (o["tanggal_rilis"], o["rilis_id"]))
        for a, b in zip(urut, urut[1:]):
            out.append(baris_pasangan("rilis_x_rilis", seri, (w, per, rin), a, b, pemekaran, {}))
    return out


def sumber_x_sumber(obs: list[dict], padanan: list[dict], pemekaran) -> tuple[list[dict], list[dict]]:
    """Antarkeluarga per konsep padanan; tiap keluarga diwakili rilis terbarunya per kunci."""
    p_seri = {(p["keluarga"], p["seri_kode"]): p for p in padanan}
    per_konsep = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))  # konsep -> kunci -> keluarga -> obs
    riwayat_bps = defaultdict(list)
    tidak_cocok = Counter()
    for o in obs:
        p = p_seri.get((o["keluarga"], o["seri_kode"]))
        if not p:
            continue
        if o["rincian"] != (p["rincian"] or "total"):
            continue
        per = o["periode"]
        if p["bulan_dipakai"]:
            if o.get("bulan_acuan") != p["bulan_dipakai"]:
                continue
            per = per[:4]
        elif o["jenis_periode"] != "tahun":
            tidak_cocok[f"{o['keluarga']}:{o['seri_kode']}:periode_{o['jenis_periode']}"] += 1
            continue
        x = o | {"hubungan": p["hubungan"], "satuan": p["satuan_id"] or o["satuan_id"], "kunci_bps": None}
        kunci = (o["wilayah_kode"], per, "total")
        if o["keluarga"] == "bps":
            x["kunci_bps"] = (p["konsep_id"],) + kunci
            riwayat_bps[x["kunci_bps"]].append(x)
        per_konsep[p["konsep_id"]][kunci][o["keluarga"]].append(x)
    out = []
    for konsep, per_kunci in per_konsep.items():
        for kunci, per_kel in per_kunci.items():
            wakil = {k: max(v, key=lambda o: (o["tanggal_rilis"], o["rilis_id"])) for k, v in per_kel.items()}
            for ka, kb in itertools.combinations(sorted(wakil), 2):
                out.append(baris_pasangan("sumber_x_sumber", konsep, kunci, wakil[ka], wakil[kb], pemekaran,
                                          riwayat_bps))
    return out, [{"seri": k, "observasi_dilewati": v} for k, v in sorted(tidak_cocok.items())]


# ---------------------------------------------------------------------------------------------------
# Ringkasan
# ---------------------------------------------------------------------------------------------------

def wilson(k: int, n: int, z: float = 1.959964) -> list[float]:
    if n == 0:
        return [math.nan, math.nan]
    p = k / n
    t = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    return [round(c - t, 4), round(c + t, 4)]


def ringkas(pasangan: list[dict]) -> dict:
    out = {}
    for jenis in ("rilis_x_rilis", "sumber_x_sumber"):
        ps = [p for p in pasangan if p["jenis_pasangan"] == jenis]
        sel = [p for p in ps if p["status"] == "selisih"]
        terjelaskan = [p for p in sel if p["kelas_sebab"] != "tidak_terjelaskan"]
        teramati = [p for p in sel if p["tingkat_bukti"] == "teramati"]
        per_pas = Counter(f"{p['keluarga_a']}x{p['keluarga_b']}" for p in ps)
        out[jenis] = {
            "pasangan": len(ps), "status": dict(Counter(p["status"] for p in ps)),
            "kelas_sebab": dict(Counter(p["kelas_sebab"] for p in sel).most_common()),
            "proporsi_terjelaskan": round(len(terjelaskan) / len(sel), 4) if sel else None,
            "wilson95_terjelaskan": wilson(len(terjelaskan), len(sel)),
            "proporsi_teramati": round(len(teramati) / len(sel), 4) if sel else None,
            "wilson95_teramati": wilson(len(teramati), len(sel)),
            "per_pasangan_keluarga": dict(sorted(per_pas.items())),
            "status_per_pasangan_keluarga": {
                k: dict(Counter(p["status"] for p in ps if f"{p['keluarga_a']}x{p['keluarga_b']}" == k))
                for k in sorted(per_pas)},
        }
    return out


def jalankan(silver: Path = S.SILVER) -> dict:
    beku = jejak_beku()
    tgl = baca_rilis()
    obs = [o | {"tanggal_rilis": tgl.get(o["rilis_id"]) or o["_snapshot"], "satuan": o["satuan_id"]}
           for o in baca_observasi(silver)]
    pemekaran = wilayah_pemekaran()
    pasangan = rilis_x_rilis(obs, pemekaran)
    sxs, dilewati = sumber_x_sumber(obs, baca_padanan(), pemekaran)
    pasangan += sxs
    tulis_parquet(pasangan, KOLOM_SELISIH, silver / "fakta_selisih.parquet")
    hasil = {"dijalankan_pada": A.sekarang(), "berkas_beku": beku, "observasi_silver": len(obs),
             "ringkasan": ringkas(pasangan), "padanan_dilewati_periode": dilewati}
    RINGKASAN.write_text(json.dumps(hasil, indent=1, ensure_ascii=False) + "\n", "utf-8")
    return hasil


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description="Rekonsiliasi multisumber M3").parse_args(argv)
    h = jalankan()
    print(json.dumps(h["ringkasan"], indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
