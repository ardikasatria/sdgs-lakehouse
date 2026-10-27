"""Konektor Bank Dunia: WDI terkini (``wdi``) dan arsip versi WDI sumber 57 (``wdi_arsip``).

Aturan cakupan seri (dipakai kedua sumber): **daftar seri sumber 46 "Sustainable Development Goals"**
dari API v2 (``/v2/sources/46/indicators``), yaitu daftar seri SDG yang dikurasi Bank Dunia sendiri. Metadata
seri WDI tidak memuat kolom kode indikator SDG, sehingga daftar sumber 46 adalah aturan terlacak yang
paling dekat. Untuk ``wdi`` hanya seri yang juga ada di WDI (sumber 2) yang diambil; untuk ``wdi_arsip``
hanya seri yang ada di daftar seri sumber 57. Seri yang tidak ada dicatat di manifest, tidak dipetakan ke
kode pengganti (pemetaan kode lama ke baru adalah urusan Silver).

- ``wdi``: ``/v2/country/IDN/indicator/<seri;...>?source=2``. Rilis = field ``lastupdated`` pada halaman
  respons, jenis bukti ``pembaruan_sumber``. Bronze ``nilai`` (semua sel, termasuk kosong) dan
  ``indikator`` (metadata seri WDI).
- ``wdi_arsip``: ``/v2/sources/57/country/IDN/series/<seri;...>/version/<v>/time/all``. Satu versi = satu
  rilis ``rilis_resmi`` dengan kode YYYYMM. API mengembalikan kisi padat (semua seri yang diminta x
  1960–tahun terakhir, termasuk sel kosong), sehingga Bronze ``nilai`` hanya memuat sel terisi; sel
  kosong dapat dipulihkan dari raw dan dari ketiadaan baris. Respons per versi disimpan sebagai satu
  ``versi/<v>.tar.gz`` yang anggotanya adalah badan respons apa adanya (lossless, sha256 per anggota di
  manifest), karena JSON arsip sangat berulang (sekitar 35 kali lebih kecil setelah gzip).

Opsi ``wdi_arsip`` (``--opsi k=v``): ``versi=202607,202507``, ``dari=YYYYMM``, ``sampai=YYYYMM``,
``maks_versi=N`` (N versi terbaru dari pilihan), ``estimasi=1`` (hanya cetak taksiran, tanpa unduh data),
``lanjut=0`` (abaikan manifest snapshot hari yang sama; bawaannya dilanjutkan dan versi yang sudah ada
dilewati), ``jeda_s=1.0``.
"""
from __future__ import annotations

import gzip
import io
import json
import sys
import tarfile
import time
from typing import Iterable

from .. import inti

SUMBER = ("wdi", "wdi_arsip")

API = "https://api.worldbank.org/v2"
NEGARA = "IDN"
SUMBER_SDG = 46
SUMBER_WDI = 2
SUMBER_ARSIP = 57
#: Server Bank Dunia menolak URL sekitar >1.150 karakter (HTTP 400 "Invalid URL"); diukur 20 Okt 2026.
MAKS_URL = 1100
MAKS_SERI = 60


# ---------------------------------------------------------------------------------------------------
# Fungsi murni (diuji luring)
# ---------------------------------------------------------------------------------------------------

def meta_halaman(js) -> dict:
    """Metadata halaman untuk dua bentuk respons API v2: ``[meta, data]`` dan ``{..., "source": ...}``."""
    m = js[0] if isinstance(js, list) else {k: v for k, v in js.items() if k != "source"}
    return {"page": int(m.get("page") or 1), "pages": int(m.get("pages") or 1),
            "total": int(m.get("total") or 0), "lastupdated": m.get("lastupdated") or ""}


def urai_daftar_indikator(js) -> list[dict]:
    """``/sources/<n>/indicators`` -> baris metadata seri apa adanya (topik digabung dengan ``; ``)."""
    out = []
    for x in (js[1] or []) if isinstance(js, list) else []:
        out.append({"id": x.get("id"), "name": x.get("name"), "unit": x.get("unit"),
                    "source_id": (x.get("source") or {}).get("id"),
                    "source_value": (x.get("source") or {}).get("value"),
                    "sourceNote": x.get("sourceNote"), "sourceOrganization": x.get("sourceOrganization"),
                    "topics": "; ".join(str(t.get("value", "")).strip() for t in (x.get("topics") or []))})
    return out


def urai_konsep(js, konsep: str) -> list[dict]:
    """``/sources/57/<konsep>`` -> ``[{"id", "value"}]`` sesuai urutan API."""
    for s in js.get("source", []):
        for c in s.get("concept", []):
            if c.get("id", "").lower() == konsep.lower():
                return [{"id": v["id"], "value": v.get("value", "")} for v in c.get("variable", [])]
    return []


BULAN = {b: i for i, b in enumerate(("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct",
                                     "Nov", "Dec"), 1)}


def tanggal_versi(kode: str, label: str = "") -> tuple[str, str]:
    """Tanggal rilis versi arsip = hari pertama bulan pada kode YYYYMM. Kembalikan (tanggal, catatan);
    catatan berisi ketidakcocokan bila label API (mis. "1994 Sep") menyebut tahun/bulan lain."""
    if len(kode) != 6 or not kode.isdigit() or not 1 <= int(kode[4:]) <= 12:
        raise ValueError(f"kode versi bukan YYYYMM: {kode}")
    tgl = f"{kode[:4]}-{kode[4:]}-01"
    bag = label.split()
    if len(bag) == 2 and bag[0].isdigit() and bag[1][:3] in BULAN:
        kl = f"{int(bag[0]):04d}{BULAN[bag[1][:3]]:02d}"
        if kl != kode:
            return tgl, f"label API '{label}' tidak cocok dengan kode {kode}; tanggal mengikuti kode"
    return tgl, ""


def kelompokkan(kode: list[str], awalan_url: str, akhiran_url: str = "", maks_url: int = MAKS_URL,
                maks_n: int = MAKS_SERI) -> list[list[str]]:
    """Bagi daftar seri menjadi kelompok yang URL-nya (awalan + 'a;b;c' + akhiran) tidak melewati batas."""
    out: list[list[str]] = []
    kini: list[str] = []
    for k in kode:
        calon = kini + [k]
        if kini and (len(awalan_url) + len(";".join(calon)) + len(akhiran_url) > maks_url or len(calon) > maks_n):
            out.append(kini)
            calon = [k]
        kini = calon
    if kini:
        out.append(kini)
    return out


def _datar(x: dict) -> dict:
    """Ratakan objek {id, value} bersarang menjadi kolom ``<k>_id`` dan ``<k>_value``."""
    out = {}
    for k, v in x.items():
        if isinstance(v, dict):
            out[f"{k}_id"] = v.get("id")
            out[f"{k}_value"] = v.get("value")
        else:
            out[k] = v
    return out


def baris_wdi(js) -> list[dict]:
    """Halaman ``/country/IDN/indicator/...`` -> baris apa adanya (termasuk nilai kosong)."""
    if not isinstance(js, list) or len(js) < 2 or js[1] is None:
        return []
    return [_datar(x) for x in js[1]]


def baris_arsip(js, buang_kosong: bool = True) -> list[dict]:
    """Halaman sumber 57 -> baris ``<konsep>_id``, ``<konsep>_value``, ``value``."""
    out = []
    for x in (js.get("source") or {}).get("data", []) if isinstance(js, dict) else []:
        if buang_kosong and x.get("value") is None:
            continue
        r = {}
        for v in x.get("variable", []):
            c = str(v.get("concept", "")).lower()
            r[f"{c}_id"] = v.get("id")
            r[f"{c}_value"] = v.get("value")
        r["value"] = x.get("value")
        out.append(r)
    return out


def jumlah_sel(js) -> tuple[int, int]:
    """(sel, sel terisi) pada halaman sumber 57."""
    d = (js.get("source") or {}).get("data", []) if isinstance(js, dict) else []
    return len(d), sum(1 for x in d if x.get("value") is not None)


def pilih_versi(semua: list[str], opsi: dict) -> list[str]:
    """Saring kode versi menurut opsi ``versi``, ``dari``, ``sampai``, ``maks_versi``; urut naik."""
    v = sorted(set(semua))
    if opsi.get("versi"):
        minta = [x.strip() for x in str(opsi["versi"]).split(",") if x.strip()]
        asing = [x for x in minta if x not in v]
        if asing:
            raise ValueError(f"versi tidak dikenal: {asing}")
        v = sorted(set(minta))
    if opsi.get("dari"):
        v = [x for x in v if x >= str(opsi["dari"])]
    if opsi.get("sampai"):
        v = [x for x in v if x <= str(opsi["sampai"])]
    if opsi.get("maks_versi"):
        v = v[-int(opsi["maks_versi"]):]
    return v


def tar_deterministik(anggota: Iterable[tuple[str, bytes]]) -> bytes:
    """tar.gz dengan mtime 0 agar isi yang sama selalu memberi sha256 yang sama."""
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0, compresslevel=9) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.USTAR_FORMAT) as tar:
            for nama, isi in anggota:
                ti = tarfile.TarInfo(nama)
                ti.size, ti.mtime, ti.mode = len(isi), 0, 0o644
                tar.addfile(ti, io.BytesIO(isi))
    return buf.getvalue()


def baca_tar(isi: bytes) -> dict[str, bytes]:
    with tarfile.open(fileobj=io.BytesIO(isi), mode="r:gz") as tar:
        return {m.name: tar.extractfile(m).read() for m in tar.getmembers() if m.isfile()}


# ---------------------------------------------------------------------------------------------------
# Jaringan
# ---------------------------------------------------------------------------------------------------

def _ambil(http: inti.Http, url: str) -> tuple[bytes, object]:
    r = http.get(url)
    return r.content, json.loads(r.content)


def _ambil_halaman(http: inti.Http, url_dasar: str, per_page: int) -> list[tuple[str, bytes, object]]:
    """Ambil semua halaman; kembalikan [(url, bita, json)]."""
    out, hal = [], 1
    while True:
        sep = "&" if "?" in url_dasar else "?"
        url = f"{url_dasar}{sep}format=json&per_page={per_page}&page={hal}"
        b, js = _ambil(http, url)
        out.append((url, b, js))
        m = meta_halaman(js)
        if hal >= m["pages"]:
            return out
        hal += 1


def _daftar_sdg(http: inti.Http, snap: inti.Snapshot) -> tuple[list[dict], str]:
    url = f"{API}/sources/{SUMBER_SDG}/indicators?format=json&per_page=5000"
    b, js = _ambil(http, url)
    nama = "metadata/sumber46_indikator.json"
    snap.simpan(nama, b, url, peran="daftar seri SDG Bank Dunia (aturan cakupan)")
    return urai_daftar_indikator(js), nama


def _log(*a) -> None:
    print("[wdi]", *a, file=sys.stderr, flush=True)


def jalankan(snap: inti.Snapshot, opsi: dict) -> dict:
    if opsi.get("sumber", snap.sumber) == "wdi_arsip":
        return jalankan_arsip(snap, opsi)
    return jalankan_terkini(snap, opsi)


def jalankan_terkini(snap: inti.Snapshot, opsi: dict) -> dict:
    t0 = time.monotonic()
    http = inti.Http(jeda_s=float(opsi.get("jeda_s", 1.0)))
    url = f"{API}/sources?format=json&per_page=200"
    b, js_sumber = _ambil(http, url)
    snap.simpan("metadata/sumber.json", b, url, peran="daftar sumber API v2 beserta lastupdated")
    lu_sumber = {str(s["id"]): s.get("lastupdated", "") for s in js_sumber[1]}

    sdg, berkas_sdg = _daftar_sdg(http, snap)
    url = f"{API}/sources/{SUMBER_WDI}/indicators?format=json&per_page=5000"
    b, js = _ambil(http, url)
    snap.simpan("metadata/sumber2_indikator.json", b, url, peran="metadata seri WDI")
    indikator = urai_daftar_indikator(js)
    ada = {x["id"] for x in indikator}
    kode = [x["id"] for x in sdg if x["id"] in ada]
    hilang = [x["id"] for x in sdg if x["id"] not in ada]
    snap.catatan.append(f"aturan cakupan: daftar seri sumber 46 (SDG, lastupdated {lu_sumber.get('46')}) "
                        f"yang ada di WDI sumber 2: {len(kode)} dari {len(sdg)} seri")
    snap.catatan.append(f"seri sumber 46 tidak ada di WDI terkini ({len(hilang)}): {', '.join(hilang)}")

    awal = f"{API}/country/{NEGARA}/indicator/"
    akhir = f"?source={SUMBER_WDI}&format=json&per_page=20000&page=1"
    kelompok = kelompokkan(kode, awal, akhir)
    berkas_data: list[tuple[str, list[dict], str]] = []
    for i, kel in enumerate(kelompok, 1):
        try:
            hal = _ambil_halaman(http, f"{awal}{';'.join(kel)}?source={SUMBER_WDI}", 20000)
        except Exception as e:
            snap.tambah_galat(f"data kelompok {i}", e)
            continue
        for j, (u, b, js) in enumerate(hal, 1):
            nama = f"data/kelompok-{i:02d}-hal-{j:02d}.json"
            snap.simpan(nama, b, u, seri=len(kel))
            berkas_data.append((nama, baris_wdi(js), meta_halaman(js)["lastupdated"]))
        _log(f"kelompok {i}/{len(kelompok)}: {len(kel)} seri")

    rilis = {}
    for nama, rows, lu in berkas_data:
        if lu not in rilis:
            rilis[lu] = snap.tambah_rilis(inti.Rilis(
                "wdi", lu or f"tanpa-lastupdated-{snap.tanggal}",
                "pembaruan_sumber" if lu else "tanggal_unduh", tanggal_rilis=lu or snap.tanggal,
                bukti=("field 'lastupdated' pada halaman respons /v2/country/IDN/indicator/...?source=2"
                       f"; /v2/sources menyebut WDI lastupdated {lu_sumber.get('2')}") if lu else "",
                cakupan=f"WDI sumber 2, Indonesia, {len(kode)} seri dari daftar SDG sumber 46"))
        snap.tulis_bronze("nilai", rows, rilis[lu], nama)
    if len(rilis) > 1:
        snap.catatan.append(f"lastupdated berubah selama unduhan: {sorted(rilis)}")
    if rilis:
        rid = next(iter(rilis.values()))
        snap.tulis_bronze("indikator", indikator, rid, "metadata/sumber2_indikator.json")
        snap.tulis_bronze("seri_sdg46", sdg, rid, berkas_sdg)
    return {"seri": len(kode), "seri_hilang": len(hilang), "rilis": sorted(rilis),
            "baris_nilai": snap.bronze_tabel.get("nilai", {}).get("baris", 0),
            "detik": round(time.monotonic() - t0, 1)}


# ---------------------------------------------------------------------------------------------------
# Arsip versi (sumber 57)
# ---------------------------------------------------------------------------------------------------

def pulihkan(snap: inti.Snapshot) -> bool:
    """Lanjutkan snapshot hari yang sama: muat berkas, rilis, Bronze, dan catatan dari manifest lama."""
    p = snap.manifest_dir / f"{snap.sumber}-{snap.tanggal}.json"
    if not p.exists():
        return False
    m = json.loads(p.read_text("utf-8"))
    snap.berkas.update(m.get("berkas", {}))
    snap.rilis.update(m.get("rilis", {}))
    snap.bronze_tabel.update(m.get("bronze", {}))
    snap.catatan.extend(m.get("catatan", []))
    snap.mulai = m.get("mulai", snap.mulai)
    if m.get("galat"):
        snap.catatan.append(f"galat jalan sebelumnya ({len(m['galat'])}): "
                            + "; ".join(g["apa"] for g in m["galat"])[:800])
    return True


def _versi_selesai(snap: inti.Snapshot, kode: str) -> bool:
    b = snap.berkas.get(f"versi/{kode}.tar.gz")
    if not b or f"wdi_arsip:{kode}" not in snap.rilis or "baris_bronze" not in b:
        return False
    p = snap.path(f"versi/{kode}.tar.gz")
    return p.exists() and inti.sha256_bita(p.read_bytes()) == b["sha256"]


def jalankan_arsip(snap: inti.Snapshot, opsi: dict) -> dict:
    t0 = time.monotonic()
    http = inti.Http(jeda_s=float(opsi.get("jeda_s", 1.0)))
    lanjut = str(opsi.get("lanjut", "1")) != "0" and pulihkan(snap)
    if lanjut:
        snap.catatan.append(f"{inti.sekarang()}: jalan dilanjutkan dari manifest snapshot yang sama")

    url = f"{API}/sources/{SUMBER_ARSIP}/version?format=json&per_page=1000"
    b, js = _ambil(http, url)
    snap.simpan("metadata/versi.json", b, url, peran="daftar versi arsip WDI")
    versi = urai_konsep(js, "version")
    label = {v["id"]: v["value"] for v in versi}
    url = f"{API}/sources/{SUMBER_ARSIP}/series?format=json&per_page=10000"
    b, js = _ambil(http, url)
    snap.simpan("metadata/seri_arsip.json", b, url, peran="gabungan seri semua versi arsip")
    seri_arsip = {v["id"] for v in urai_konsep(js, "series")}
    sdg, _ = _daftar_sdg(http, snap)
    kode = [x["id"] for x in sdg if x["id"] in seri_arsip]
    hilang = [x["id"] for x in sdg if x["id"] not in seri_arsip]
    catat = (f"aturan cakupan: daftar seri sumber 46 yang ada di daftar seri sumber 57: {len(kode)} dari "
             f"{len(sdg)}; tidak ada di arsip: {', '.join(hilang)}")
    if catat not in snap.catatan:
        snap.catatan.append(catat)

    pilihan = pilih_versi([v["id"] for v in versi], opsi)
    awal = f"{API}/sources/{SUMBER_ARSIP}/country/{NEGARA}/series/"
    akhir_contoh = f"/version/{pilihan[-1] if pilihan else '000000'}/time/all?format=json&per_page=10000&page=1"
    kelompok = kelompokkan(kode, awal, akhir_contoh)
    sisa = [v for v in pilihan if not _versi_selesai(snap, v)]
    taksir = (f"taksiran: {len(pilihan)} versi dipilih ({len(sisa)} belum ada), {len(kode)} seri dalam "
              f"{len(kelompok)} kelompok -> {len(sisa) * len(kelompok)} panggilan; kisi padat "
              f"~{len(kode)} seri x 67 tahun = {len(kode) * 67} sel per versi")
    _log(taksir)
    snap.catatan.append(f"{inti.sekarang()}: {taksir}")
    if str(opsi.get("estimasi", "0")) == "1":
        contoh = [pilihan[0], pilihan[len(pilihan) // 2], pilihan[-1]] if pilihan else []
        ukur = []
        for v in contoh:
            b, js = _ambil(http, f"{awal}{';'.join(kelompok[0])}/version/{v}/time/all?format=json&per_page=10000")
            sel, isi = jumlah_sel(js)
            ukur.append({"versi": v, "bita": len(b), "bita_gzip": len(gzip.compress(b)), "sel": sel, "terisi": isi})
        rata = sum(u["bita"] for u in ukur) / max(1, len(ukur))
        rata_gz = sum(u["bita_gzip"] for u in ukur) / max(1, len(ukur))
        n = len(sisa) * len(kelompok)
        hasil = {"taksiran": taksir, "contoh_kelompok_1": ukur,
                 "raw_mentah_mb": round(n * rata / 1e6, 1), "raw_gzip_mb": round(n * rata_gz / 1e6, 1)}
        _log(json.dumps(hasil))
        snap.catatan.append("estimasi dari kelompok 1 pada versi " + ", ".join(contoh) + f": raw mentah "
                            f"~{hasil['raw_mentah_mb']} MB, tar.gz ~{hasil['raw_gzip_mb']} MB")
        return hasil

    total_baris = 0
    for no, v in enumerate(sisa, 1):
        tv = time.monotonic()
        anggota, meta_anggota, rows = [], [], []
        sel = terisi = 0
        lu = set()
        try:
            for i, kel in enumerate(kelompok, 1):
                for j, (u, b, js) in enumerate(_ambil_halaman(
                        http, f"{awal}{';'.join(kel)}/version/{v}/time/all", 10000), 1):
                    nama = f"kelompok-{i:02d}-hal-{j:02d}.json"
                    anggota.append((nama, b))
                    s, t = jumlah_sel(js)
                    sel, terisi = sel + s, terisi + t
                    lu.add(meta_halaman(js)["lastupdated"])
                    meta_anggota.append({"nama": nama, "url": inti.url_aman(u), "sha256": inti.sha256_bita(b),
                                         "bita": len(b), "seri": len(kel), "sel": s, "terisi": t})
                    rows.extend(baris_arsip(js))
        except Exception as e:
            snap.tambah_galat(f"versi {v}", e)
            _log(f"versi {v}: GAGAL {e}")
            continue
        seri_terisi = sorted({r["series_id"] for r in rows})
        label_beda = sorted({r["series_id"] for r in rows if r.get("version_id") != v})
        isi = tar_deterministik(anggota)
        berkas = f"versi/{v}.tar.gz"
        snap.simpan(berkas, isi, f"{awal}<kelompok>/version/{v}/time/all", kompresi="tar.gz (mtime 0)",
                    anggota=meta_anggota, bita_mentah=sum(m["bita"] for m in meta_anggota), sel=sel,
                    sel_terisi=terisi, seri_diminta=len(kode), seri_terisi=len(seri_terisi),
                    lastupdated_respons=sorted(lu))
        tgl, cat = tanggal_versi(v, label.get(v, ""))
        rid = snap.tambah_rilis(inti.Rilis(
            "wdi_arsip", v, "rilis_resmi", tanggal_rilis=tgl,
            bukti=(f"/v2/sources/57/version id={v} value='{label.get(v, '')}'; tanggal = hari pertama bulan "
                   "kode versi (API tidak memberi tanggal harian)" + (f"; {cat}" if cat else "")),
            cakupan=f"WDI Database Archives versi {v}, Indonesia, {len(kode)} seri daftar SDG sumber 46"))
        if label_beda:
            snap.tambah_galat(f"versi {v}", f"respons memuat Version id lain untuk {len(label_beda)} seri")
        n = snap.tulis_bronze("nilai", rows, rid, berkas)
        snap.berkas[berkas]["baris_bronze"] = n
        total_baris += n
        snap.selesai()  # titik simpan: manifest selalu mencerminkan versi yang sudah lengkap
        _log(f"[{no}/{len(sisa)}] versi {v}: {terisi}/{sel} sel terisi, {len(seri_terisi)} seri, "
             f"{len(isi) / 1e3:.0f} kB, {time.monotonic() - tv:.1f} s")
    return {"versi_dipilih": len(pilihan), "versi_diunduh": len(sisa), "rilis_total": len(snap.rilis),
            "baris_bronze_jalan_ini": total_baris, "galat": len(snap.galat),
            "detik": round(time.monotonic() - t0, 1)}
