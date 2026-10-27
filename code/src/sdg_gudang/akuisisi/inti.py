"""Kerangka akuisisi multisumber (brief 4 M2): raw, manifest, registri rilis, dan Bronze.

Aturan lapis (brief 4 Bagian 3.1 dan 2.4):

- **Raw** ``data/raw/gudang/<sumber>/<snapshot>/``: payload apa adanya, hanya bertambah, tidak di-commit
  (``data/raw/**`` diabaikan git). Payload yang terlalu besar untuk disimpan utuh (arsip global) dicatat
  dengan URL, ukuran, dan sha256 aslinya lalu hanya ekstrak Indonesia yang disimpan; keputusan ini
  tercatat per berkas (``disimpan = "ekstrak"``).
- **Manifest** ``data/manifests/gudang/<sumber>-<snapshot>.json``: di-commit; memuat sha256 setiap berkas,
  rilis yang terdeteksi, dan galat. Rebuild memverifikasi raw terhadap manifest.
- **Registri rilis** ``data/manifests/gudang/dim_rilis.csv``: satu baris per rilis per sumber dengan jenis
  bukti tanggal (lima tingkat, brief 4 Bagian 2.4).
- **Bronze** ``data/bronze/gudang/<sumber>/<tabel>/snapshot=<snapshot>/bagian.parquet``: baris apa adanya
  dari payload (kolom sumber sebagai teks) ditambah kolom baku ``_sumber``, ``_rilis_id``, ``_berkas_raw``,
  ``_sha256_raw``, ``_diunduh_pada``. Dimuat ke Iceberg pada M4.

Kunci API dibaca dari lingkungan atau ``.env``/``.env.local`` dan tidak pernah ditulis ke log, manifest,
atau URL yang disimpan.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

AKAR = Path(__file__).resolve().parents[3]
RAW = AKAR / "data" / "raw" / "gudang"
MANIFEST = AKAR / "data" / "manifests" / "gudang"
BRONZE = AKAR / "data" / "bronze" / "gudang"
ZONA = dt.timezone(dt.timedelta(hours=7))  # WIB

#: Urutan bukti tanggal rilis dari terkuat (brief 4 Bagian 2.4).
JENIS_BUKTI = ("rilis_resmi", "pembaruan_sumber", "tanggal_unduh_berubah", "tanggal_unduh", "tidak_diketahui")

#: Kelas tayang menurut lisensi (brief 4 Bagian 2.5).
KELAS_LISENSI = {
    "bps": "A", "bps_brs": "A", "ilostat": "A", "wdi": "A", "wdi_arsip": "A", "who_gho": "A",
    "bnpb": "A-SA", "unsd": "B", "unsd_arsip": "B", "sipsn": "B", "signsmart": "B", "kkp": "B",
    # Berita (brief 4 Bagian 2.6, M5): hanya metadata dan URL, tidak pernah teks artikel.
    "gdelt": "A", "rss": "C", "ccnews": "C",
}
LISENSI_TEKS = {
    "bps": "Term of use BPS (bebas, termasuk komersial)", "bps_brs": "Term of use BPS",
    "ilostat": "CC BY 4.0 (data ILO terbit sejak 3 Mei 2023)", "wdi": "CC BY 4.0 (World Bank)",
    "wdi_arsip": "CC BY 4.0 (World Bank)", "who_gho": "CC BY 4.0 dengan ketentuan WHO",
    "bnpb": "ODbL (CKAN BNPB)", "unsd": "tidak ditemukan lisensi terbuka; ketentuan umum PBB",
    "unsd_arsip": "tidak ditemukan lisensi terbuka; ketentuan umum PBB", "sipsn": "tidak ditemukan",
    "signsmart": "tidak jelas (halaman ketentuan berisi teks templat)", "kkp": "tidak ditemukan",
    "gdelt": "ketentuan GDELT: data terbuka, pemakaian bebas dengan sitasi GDELT Project (hanya metadata dan URL)",
    "rss": "metadata berita berhak cipta (UU 28/2014 Pasal 43c, 44(1)a); hanya riset internal, tidak ditayangkan",
    "ccnews": "Common Crawl Terms of Use; metadata berita berhak cipta, hanya riset internal, tidak ditayangkan",
}
#: Sumber berkelas A/A-SA yang tetap tidak ditayangkan (metadata berita; brief 4 Bagian 2.6).
TIDAK_DITAYANGKAN = {"gdelt"}

POLA_RAHASIA = re.compile(r"(?i)^(key|api[_-]?key|token|apikey|access_token)$")


def boleh_tayang(sumber: str) -> bool:
    """Apakah nilai dari sumber ini boleh tampil di game dan Bravais tanpa izin tambahan."""
    return KELAS_LISENSI[sumber] in ("A", "A-SA") and sumber not in TIDAK_DITAYANGKAN


def kunci(nama: str) -> str:
    """Nilai kunci dari lingkungan, lalu .env.local, lalu .env. Galat hanya menyebut nama variabel."""
    if os.environ.get(nama):
        return os.environ[nama]
    for berkas in (AKAR / ".env.local", AKAR / ".env"):
        if berkas.exists():
            for baris in berkas.read_text("utf-8").splitlines():
                k, _, v = baris.partition("=")
                if k.strip() == nama and v.strip():
                    return v.strip().strip('"').strip("'")
    raise KeyError(f"variabel {nama} tidak ditemukan di lingkungan, .env.local, atau .env")


def url_aman(url: str) -> str:
    """URL dengan parameter rahasia diganti REDACTED, untuk manifest dan log."""
    u = urlsplit(url)
    q = [(k, "REDACTED" if POLA_RAHASIA.match(k) else v) for k, v in parse_qsl(u.query, keep_blank_values=True)]
    return urlunsplit((u.scheme, u.netloc, u.path, urlencode(q, safe=":/,"), u.fragment))


def sekarang() -> str:
    return dt.datetime.now(ZONA).isoformat(timespec="seconds")


def sha256_bita(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ---------------------------------------------------------------------------------------------------
# HTTP sopan
# ---------------------------------------------------------------------------------------------------

AGEN = ("Mozilla/5.0 (compatible; LigaLakehouse-penelitian/0.2; +https://sd.itera.ac.id/liga-lakehouse) "
        "python-requests")


class Http:
    """Klien HTTP dengan jeda minimum per host, coba ulang, dan batas waktu. Tidak mencatat kunci."""

    def __init__(self, jeda_s: float = 1.0, coba: int = 4, batas_waktu: float = 120.0,
                 agen: str = AGEN, header: dict | None = None):
        import requests

        self.s = requests.Session()
        self.s.headers.update({"User-Agent": agen, "Accept-Language": "id,en;q=0.8"} | (header or {}))
        self.jeda_s, self.coba, self.batas_waktu = jeda_s, coba, batas_waktu
        self._terakhir: dict[str, float] = {}

    def _tunggu(self, host: str) -> None:
        t = self._terakhir.get(host)
        if t is not None:
            sisa = self.jeda_s - (time.monotonic() - t)
            if sisa > 0:
                time.sleep(sisa)
        self._terakhir[host] = time.monotonic()

    def get(self, url: str, params: dict | None = None, stream: bool = False, **kw):
        import requests

        host = urlsplit(url).netloc
        galat: Exception | None = None
        for i in range(self.coba):
            self._tunggu(host)
            try:
                r = self.s.get(url, params=params, timeout=self.batas_waktu, stream=stream, **kw)
                if r.status_code in (429, 500, 502, 503, 504):
                    raise requests.HTTPError(f"HTTP {r.status_code}", response=r)
                r.raise_for_status()
                return r
            except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as e:
                status = getattr(getattr(e, "response", None), "status_code", None)
                if status is not None and status not in (429, 500, 502, 503, 504):
                    raise
                galat = e
                time.sleep(min(60, 2 ** (i + 1)))
        raise RuntimeError(f"gagal setelah {self.coba} percobaan: {url_aman(url if not params else url + '?' + urlencode(params))}: {galat}")

    def head(self, url: str, **kw):
        """HEAD tanpa coba ulang (untuk taksiran ukuran); galat diteruskan ke pemanggil."""
        self._tunggu(urlsplit(url).netloc)
        return self.s.head(url, timeout=self.batas_waktu, allow_redirects=True, **kw)

    def get_json(self, url: str, params: dict | None = None, **kw):
        return self.get(url, params=params, **kw).json()


# ---------------------------------------------------------------------------------------------------
# Rilis dan snapshot
# ---------------------------------------------------------------------------------------------------

@dataclass
class Rilis:
    sumber: str
    kode_rilis: str            # kode rilis sumber atau label buatan bila sumber tidak bernomor
    jenis_bukti_tanggal: str   # salah satu JENIS_BUKTI
    tanggal_rilis: str = ""    # ISO date/datetime; kosong bila tidak diketahui
    bukti: str = ""            # dari mana tanggal diketahui (field, halaman, nomor BRS)
    batas_bawah: str = ""      # untuk tanggal_unduh_berubah: unduhan terakhir dengan isi lama
    batas_atas: str = ""       # unduhan pertama dengan isi baru
    cakupan: str = ""          # seri, tabel, atau dataflow yang dicakup rilis ini
    lisensi: str = ""          # lisensi per dataset bila berbeda dari lisensi sumber (contoh CKAN BNPB)

    def __post_init__(self) -> None:
        if self.jenis_bukti_tanggal not in JENIS_BUKTI:
            raise ValueError(f"jenis_bukti_tanggal tidak dikenal: {self.jenis_bukti_tanggal}")

    @property
    def rilis_id(self) -> str:
        return f"{self.sumber}:{self.kode_rilis}"


@dataclass
class Snapshot:
    """Satu jalan akuisisi untuk satu sumber pada satu tanggal."""

    sumber: str
    tanggal: str = field(default_factory=lambda: dt.datetime.now(ZONA).date().isoformat())
    raw: Path = RAW
    manifest_dir: Path = MANIFEST
    bronze: Path = BRONZE
    berkas: dict = field(default_factory=dict)
    rilis: dict = field(default_factory=dict)
    galat: list = field(default_factory=list)
    bronze_tabel: dict = field(default_factory=dict)
    catatan: list = field(default_factory=list)
    mulai: str = field(default_factory=sekarang)

    def __post_init__(self) -> None:
        if self.sumber not in KELAS_LISENSI:
            raise ValueError(f"sumber tidak dikenal: {self.sumber}")
        self.folder = self.raw / self.sumber / self.tanggal
        self.folder.mkdir(parents=True, exist_ok=True)

    def path(self, nama: str) -> Path:
        p = (self.folder / nama).resolve()
        if self.folder.resolve() not in p.parents:
            raise ValueError(f"nama berkas keluar dari folder snapshot: {nama}")
        return p

    def simpan(self, nama: str, isi: bytes, url: str = "", diunduh_pada: str | None = None, **meta) -> str:
        """Simpan payload apa adanya; kembalikan sha256. ``diunduh_pada`` diisi waktu unduh asli bila
        payload disalin dari snapshot lama (waktu salin dicatat terpisah oleh konektor)."""
        p = self.path(nama)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(isi)
        h = sha256_bita(isi)
        self.berkas[nama] = {"sha256": h, "bita": len(isi), "url": url_aman(url) if url else "",
                             "diunduh_pada": diunduh_pada or sekarang(), "disimpan": "utuh"} | meta
        return h

    def catat_ekstrak(self, nama: str, isi: bytes, url: str, sha256_asli: str, bita_asli: int, aturan: str,
                      **meta) -> str:
        """Simpan ekstrak dari payload besar yang tidak disimpan utuh, beserta sha256 dan ukuran aslinya."""
        h = self.simpan(nama, isi, url, **meta)
        self.berkas[nama] |= {"disimpan": "ekstrak", "sha256_asli": sha256_asli, "bita_asli": bita_asli,
                              "aturan_ekstrak": aturan}
        return h

    def tambah_rilis(self, r: Rilis) -> str:
        if r.sumber != self.sumber:
            raise ValueError("rilis dari sumber lain")
        self.rilis[r.rilis_id] = asdict(r) | {"rilis_id": r.rilis_id}
        return r.rilis_id

    def tambah_galat(self, apa: str, e: Exception | str) -> None:
        self.galat.append({"apa": apa, "galat": str(e)[:500], "waktu": sekarang()})

    def tulis_bronze(self, tabel: str, rows: Iterable[dict], rilis_id: str, berkas_raw: str) -> int:
        """Tulis baris apa adanya ke Bronze Parquet. Nilai sumber disimpan sebagai teks."""
        import pyarrow as pa
        import pyarrow.parquet as pq

        if rilis_id not in self.rilis:
            raise ValueError(f"rilis {rilis_id} belum dicatat")
        if berkas_raw not in self.berkas:
            raise ValueError(f"berkas raw {berkas_raw} belum dicatat")
        rows = list(rows)
        if not rows:
            return 0
        # Baris boleh membawa _rilis_id sendiri (contoh satu daftar BRS memuat ribuan rilis).
        for r in rows:
            if r.get("_rilis_id") not in (None, rilis_id) and r["_rilis_id"] not in self.rilis:
                raise ValueError(f"rilis baris {r['_rilis_id']} belum dicatat")
        kolom = sorted({k for r in rows for k in r} - {"_rilis_id"})
        baku = {"_sumber": self.sumber, "_berkas_raw": f"{self.sumber}/{self.tanggal}/{berkas_raw}",
                "_sha256_raw": self.berkas[berkas_raw]["sha256"], "_diunduh_pada": self.berkas[berkas_raw]["diunduh_pada"]}
        data = {k: [None if r.get(k) is None else str(r.get(k)) for r in rows] for k in kolom}
        data["_rilis_id"] = [str(r.get("_rilis_id") or rilis_id) for r in rows]
        data |= {k: [v] * len(rows) for k, v in baku.items()}
        # Skema eksplisit serba teks: kolom yang seluruhnya kosong tidak lagi bertipe null, sehingga bagian
        # dengan isi berbeda tetap dapat dibaca bersama (lihat baca_bronze).
        t = pa.table(data, schema=pa.schema([(k, pa.string()) for k in data]))
        p = self.bronze / self.sumber / tabel / f"snapshot={self.tanggal}"
        if tabel not in self.bronze_tabel and p.exists():
            # Jalan baru pada tanggal snapshot yang sama: hapus bagian lama agar tidak tertinggal. Konektor yang
            # melanjutkan jalan memulihkan bronze_tabel dari manifest sehingga cabang ini tidak dilalui.
            for lama in p.glob("bagian-*.parquet"):
                lama.unlink()
        p.mkdir(parents=True, exist_ok=True)
        ada = self.bronze_tabel.get(tabel, {"baris": 0, "bagian": 0, "kolom": []})
        nama = f"bagian-{ada['bagian']:04d}.parquet"
        pq.write_table(t, p / nama, compression="zstd")
        self.bronze_tabel[tabel] = {"baris": ada["baris"] + len(rows), "bagian": ada["bagian"] + 1,
                                    "kolom": sorted(set(ada.get("kolom", [])) | set(data))}
        return len(rows)

    def selesai(self) -> Path:
        self.manifest_dir.mkdir(parents=True, exist_ok=True)
        m = {"sumber": self.sumber, "snapshot": self.tanggal, "kelas_lisensi": KELAS_LISENSI[self.sumber],
             "lisensi": LISENSI_TEKS[self.sumber], "boleh_tayang": boleh_tayang(self.sumber),
             "mulai": self.mulai, "selesai": sekarang(),
             "berkas": dict(sorted(self.berkas.items())), "rilis": dict(sorted(self.rilis.items())),
             "bronze": dict(sorted(self.bronze_tabel.items())), "galat": self.galat, "catatan": self.catatan}
        out = self.manifest_dir / f"{self.sumber}-{self.tanggal}.json"
        out.write_text(json.dumps(m, indent=1, ensure_ascii=False) + "\n", "utf-8")
        return out


# ---------------------------------------------------------------------------------------------------
# Registri rilis dan verifikasi
# ---------------------------------------------------------------------------------------------------

KOLOM_RILIS = ["rilis_id", "sumber", "kode_rilis", "tanggal_rilis", "jenis_bukti_tanggal", "bukti",
               "batas_bawah", "batas_atas", "cakupan", "lisensi", "snapshot_pertama", "kelas_lisensi"]


def bangun_registri(manifest_dir: Path = MANIFEST) -> list[dict]:
    """Gabungkan rilis dari semua manifest menjadi ``dim_rilis.csv``. Rilis yang sama dari beberapa
    snapshot disatukan; bukti terkuat dipertahankan, snapshot pertama dicatat."""
    hasil: dict[str, dict] = {}
    for p in sorted(manifest_dir.glob("*-????-??-??.json")):
        m = json.loads(p.read_text("utf-8"))
        for rid, r in m.get("rilis", {}).items():
            baru = {k: r.get(k, "") for k in KOLOM_RILIS if k in r} | {"snapshot_pertama": m["snapshot"],
                                                                     "kelas_lisensi": m["kelas_lisensi"]}
            lama = hasil.get(rid)
            if lama is None:
                hasil[rid] = baru
            elif JENIS_BUKTI.index(baru["jenis_bukti_tanggal"]) < JENIS_BUKTI.index(lama["jenis_bukti_tanggal"]):
                hasil[rid] = baru | {"snapshot_pertama": lama["snapshot_pertama"]}
    rows = [{k: hasil[rid].get(k, "") for k in KOLOM_RILIS} for rid in sorted(hasil)]
    if rows:
        with (manifest_dir / "dim_rilis.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=KOLOM_RILIS, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
    return rows


def verifikasi(manifest: Path, raw: Path = RAW) -> list[str]:
    """Bandingkan berkas raw dengan sha256 di manifest; kembalikan daftar masalah."""
    m = json.loads(manifest.read_text("utf-8"))
    folder = raw / m["sumber"] / m["snapshot"]
    masalah = []
    for nama, b in m["berkas"].items():
        p = folder / nama
        if not p.exists():
            masalah.append(f"hilang: {nama}")
        elif sha256_bita(p.read_bytes()) != b["sha256"]:
            masalah.append(f"sha256 beda: {nama}")
    return masalah


def ukur_volume() -> dict:
    """Ukuran dan jumlah berkas per lapis dan per sumber (bahan rencana kapasitas unit 005)."""
    def ukur(p: Path) -> tuple[int, int]:
        fs = [f for f in p.rglob("*") if f.is_file()] if p.exists() else []
        return sum(f.stat().st_size for f in fs), len(fs)

    hasil: dict = {"diukur_pada": sekarang(), "lapis": {}}
    for lapis, akar in (("raw", RAW), ("bronze", BRONZE), ("manifest", MANIFEST)):
        per = {}
        if akar.exists():
            for d in sorted(x for x in akar.iterdir() if x.is_dir()):
                b, n = ukur(d)
                per[d.name] = {"bita": b, "berkas": n}
        b, n = ukur(akar)
        hasil["lapis"][lapis] = {"bita": b, "berkas": n, "per_sumber": per}
    baris = {}
    for p in sorted(MANIFEST.glob("*-????-??-??.json")):
        m = json.loads(p.read_text("utf-8"))
        for t, v in m.get("bronze", {}).items():
            baris[f"{m['sumber']}/{t}"] = baris.get(f"{m['sumber']}/{t}", 0) + v["baris"]
    hasil["baris_bronze"] = baris
    hasil["baris_bronze_total"] = sum(baris.values())
    return hasil


def baca_bronze(sumber: str, tabel: str, snapshot: str | None = None, bronze: Path = BRONZE):
    """Baca satu tabel Bronze sebagai pyarrow.Table serba teks dengan skema gabungan semua bagian.

    ``pq.read_table(folder)`` tidak aman di sini: skema bagian pertama menang (kolom bagian lain hilang
    diam-diam) dan kolom bertipe null pada bagian lama menggagalkan pembacaan.
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    akar = bronze / sumber / tabel
    pola = f"snapshot={snapshot}/bagian-*.parquet" if snapshot else "snapshot=*/bagian-*.parquet"
    bagian = sorted(akar.glob(pola))
    if not bagian:
        raise FileNotFoundError(f"Bronze {sumber}/{tabel} kosong ({pola})")
    tabel_tabel = []
    for b in bagian:
        t = pq.read_table(b)
        t = t.cast(pa.schema([(f.name, pa.string()) for f in t.schema]))
        snap_kolom = b.parent.name.split("=", 1)[1]
        tabel_tabel.append(t.append_column("_snapshot", pa.array([snap_kolom] * t.num_rows, pa.string())))
    return pa.concat_tables(tabel_tabel, promote_options="default")
