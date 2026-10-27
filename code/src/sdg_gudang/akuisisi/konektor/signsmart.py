"""Konektor SIGN-SMART KLH (``signsmart.kemenlh.go.id/v2.1/app``): emisi gas rumah kaca per provinsi per
tahun per sektor (SDG 13.2.2).

Endpoint tak terdokumentasi (dipakai peta beranda, diperiksa 20 Okt 2026):

- ``/chart/emisi_p/emisi_prov/<tahun>`` -> ``{"energy": [{"id": "ID-AC", "value": ...}, ...], "ippu": [...],
  "agriculture": [...], "forestry": [...], "waste": [...]}``. Kunci ISO 3166-2; empat entri terakhir
  setiap sektor berkunci ``ID-AC`` (provinsi Papua pemekaran 2022 salah kunci), sehingga urutan dalam
  daftar disimpan di Bronze (``urutan``) agar baris salah kunci tetap dapat dibedakan.
- ``/res/emisi_all`` -> seri nasional per sektor (``data`` + ``categories`` tahun).
- Daftar tahun diambil dari ``<select id="year">`` beranda (2000–2026 pada 20 Okt 2026).

Penafian beranda: data bersifat dinamis dan belum melalui QA/QC. Karena itu setiap tahun dicatat sebagai
rilis ``tanggal_unduh`` dengan kode ``emisi_prov/<tahun>@<sha256[:12]>``; bukti memuat penafian.
Tahun yang semua nilainya nol dicatat sebagai tahun tanpa data (tetap disimpan apa adanya).

Bronze: ``emisi_provinsi`` (tahun_diminta, sektor, urutan, id, value), ``emisi_nasional`` (sektor, tahun,
nilai, urutan). Mutu kunci: ``periksa_batch("iso3166_2", ...)`` per tahun per sektor di ``catatan``.

Opsi: ``tahun=2019,2020`` (bawaan: semua tahun di beranda).
"""
from __future__ import annotations

import json
import re

from .. import inti

SUMBER = "signsmart"

DASAR = "https://signsmart.kemenlh.go.id/v2.1/app"
BERANDA = f"{DASAR}/"
PROV = f"{DASAR}/chart/emisi_p/emisi_prov"
NASIONAL = f"{DASAR}/res/emisi_all"
AGEN_PERAMBAN = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
                 "Chrome/126.0 Safari/537.36 LigaLakehouse-penelitian/0.2 (+https://sd.itera.ac.id)")
PENAFIAN_BAWAAN = "data bersifat dinamis dan belum melalui tahap QC/QA (penafian beranda SIGN-SMART)"


# ---------------------------------------------------------------------------------------------------
# Fungsi murni (diuji luring)
# ---------------------------------------------------------------------------------------------------

def tahun_beranda(html: str) -> list[str]:
    """Pilihan tahun dari ``<select id="year">``."""
    m = re.search(r'<select[^>]*id="year"[^>]*>(.*?)</select>', html, flags=re.S)
    if not m:
        return []
    return sorted(set(re.findall(r'<option value="(\d{4})"', m.group(1))))


def penafian(html: str) -> str:
    m = re.search(r"Disclaimer</h5>.*?<p>\s*(.*?)\s*</p>", html, flags=re.S)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def baris_provinsi(js: dict, tahun: str) -> list[dict]:
    """Satu baris per (sektor, urutan) apa adanya."""
    out = []
    for sektor, daftar in js.items():
        if not isinstance(daftar, list):
            continue
        for i, x in enumerate(daftar):
            out.append({"tahun_diminta": tahun, "sektor": sektor, "urutan": i, "id": x.get("id"),
                        "value": x.get("value")})
    return out


def ada_data(js: dict) -> bool:
    """Apakah ada nilai bukan nol pada payload tahun ini."""
    for daftar in js.values():
        if isinstance(daftar, list):
            for x in daftar:
                try:
                    if float(x.get("value") or 0) != 0:
                        return True
                except (TypeError, ValueError):
                    return True
    return False


def baris_nasional(js: dict) -> list[dict]:
    th = js.get("categories") or []
    out = []
    for s in js.get("data") or []:
        for i, v in enumerate(s.get("data") or []):
            out.append({"sektor": s.get("name"), "tahun": th[i] if i < len(th) else None, "nilai": v, "urutan": i})
    return out


def kode_rilis(tahun: str, sha: str) -> str:
    return f"emisi_prov/{tahun}@{sha[:12]}"


def ringkas_periksa(hasil: dict, nama_wilayah: dict[int, str]) -> dict:
    return {"cocok": len(hasil["cocok"]), "duplikat": hasil["duplikat"], "tidak_dikenal": hasil["tidak_dikenal"],
            "ambigu": hasil["ambigu"], "hilang": [f"{k} {nama_wilayah.get(k, '')}".strip() for k in hasil["hilang"]]}


def periksa_tahun(ruj, js: dict) -> dict:
    """``periksa_batch('iso3166_2')`` per sektor; sektor dengan urutan kunci identik digabung."""
    nama_w = {w["wilayah_kode"]: w["nama"] for w in ruj.wilayah if w["terkini"]}
    per_urutan: dict[tuple, list[str]] = {}
    for sektor, daftar in js.items():
        if isinstance(daftar, list):
            per_urutan.setdefault(tuple(x.get("id") for x in daftar), []).append(sektor)
    hasil = []
    for kunci, sektor in per_urutan.items():
        posisi_ganda = {k: [i for i, x in enumerate(kunci) if x == k] for k in set(kunci) if kunci.count(k) > 1}
        hasil.append({"sektor": sektor, "entri": len(kunci), "posisi_kunci_ganda": posisi_ganda}
                     | ringkas_periksa(ruj.periksa_batch("iso3166_2", [str(k) for k in kunci]), nama_w))
    return {"urutan_kunci_sama_antarsektor": len(per_urutan) == 1, "per_urutan": hasil}


# ---------------------------------------------------------------------------------------------------
# Jaringan
# ---------------------------------------------------------------------------------------------------

def _rujukan():
    from sdg_gudang import referensi as R

    w, p = R.bangun_wilayah(), R.bangun_padanan()
    return R.Rujukan(w, p, R.bangun_alias(w, p))


def jalankan(snap: inti.Snapshot, opsi: dict) -> dict:
    http = inti.Http(agen=AGEN_PERAMBAN, jeda_s=float(opsi.get("jeda_s", 1.0)),
                     header={"Accept": "application/json, text/javascript, */*; q=0.01",
                             "X-Requested-With": "XMLHttpRequest"})
    ruj = _rujukan()

    r = http.get(BERANDA)
    snap.simpan("beranda.html", r.content, BERANDA, jenis="beranda; sumber daftar tahun dan penafian")
    html = r.content.decode("utf-8", errors="replace")
    teks_penafian = penafian(html) or PENAFIAN_BAWAAN
    tahun = [x.strip() for x in opsi["tahun"].split(",")] if opsi.get("tahun") else tahun_beranda(html)
    if not tahun:
        snap.tambah_galat("daftar tahun", "select#year tidak ditemukan di beranda")
    snap.catatan.append({"apa": "penafian beranda", "teks": teks_penafian})

    ringkas = {"tahun_diminta": len(tahun), "tahun_berdata": [], "tahun_nol": [], "baris": 0}
    periksa = {}
    for th in tahun:
        url = f"{PROV}/{th}"
        try:
            r = http.get(url)
            js = json.loads(r.content)
        except Exception as e:  # noqa: BLE001
            snap.tambah_galat(f"emisi_prov/{th}", e)
            continue
        nama = f"emisi_prov/{th}.json"
        sha = snap.simpan(nama, r.content, url)
        berdata = isinstance(js, dict) and ada_data(js)
        rid = snap.tambah_rilis(inti.Rilis(
            SUMBER, kode_rilis(th, sha), "tanggal_unduh", snap.tanggal,
            f"tanpa tanggal rilis; endpoint tak terdokumentasi; penafian: {teks_penafian}",
            cakupan=f"emisi GRK per provinsi per sektor, tahun {th}" + ("" if berdata else " (semua nilai nol)")))
        if not isinstance(js, dict):
            snap.tambah_galat(f"emisi_prov/{th}", f"payload bukan objek: {type(js).__name__}")
            continue
        ringkas["baris"] += snap.tulis_bronze("emisi_provinsi", baris_provinsi(js, th), rid, nama)
        ringkas["tahun_berdata" if berdata else "tahun_nol"].append(th)
        periksa[th] = periksa_tahun(ruj, js) | {"berdata": berdata}
    snap.catatan.append({"apa": "periksa_batch iso3166_2 per tahun", "per_tahun": periksa})

    try:
        r = http.get(NASIONAL)
        nama = "emisi_all.json"
        sha = snap.simpan(nama, r.content, NASIONAL)
        js = json.loads(r.content)
        rid = snap.tambah_rilis(inti.Rilis(
            SUMBER, f"emisi_all@{sha[:12]}", "tanggal_unduh", snap.tanggal,
            f"tanpa tanggal rilis; endpoint tak terdokumentasi; penafian: {teks_penafian}",
            cakupan="emisi GRK nasional per sektor (grafik beranda)"))
        ringkas["baris_nasional"] = snap.tulis_bronze("emisi_nasional", baris_nasional(js), rid, nama)
    except Exception as e:  # noqa: BLE001
        snap.tambah_galat("emisi_all", e)
    return ringkas | {"rilis": len(snap.rilis)}
