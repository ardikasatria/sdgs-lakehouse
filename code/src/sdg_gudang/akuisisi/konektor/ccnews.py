"""Konektor Common Crawl CC-NEWS (``ccnews``): arsip WARC berita untuk menemukan artikel lama media Indonesia.

Daftar WARC sebulan dari ``https://data.commoncrawl.org/crawl-data/CC-NEWS/YYYY/MM/warc.paths.gz`` (disimpan
utuh). WARC terpilih (sekitar 1 GB per berkas) dialirkan dan didekompresi sambil berjalan; sha256 dan ukuran
WARC asli dihitung dari aliran yang sama. Hanya rekaman ``response`` yang host ``WARC-Target-URI``-nya cocok
dengan daftar domain yang dicatat, dan **hanya metadatanya**: url, WARC-Date, host, status HTTP,
Content-Length (blok WARC dan header HTTP), tipe konten, ``<title>`` dan atribut ``lang`` HTML dari 64 KB
pertama badan respons. Badan respons tidak pernah ditulis ke disk. Ekstrak per WARC
``warc/<nama>.jsonl`` dicatat dengan ``catat_ekstrak`` (sha256 dan ukuran WARC asli).

Pembaca WARC: ``warcio`` bila terpasang, selain itu pembaca gzip-WARC minimal di modul ini (``pembaca=``
``otomatis|warcio|minimal``; pembaca yang dipakai dicatat per ekstrak).

Rilis: satu per WARC, kode = nama berkas WARC tanpa ekstensi, jenis ``pembaruan_sumber`` (cap waktu pada
nama berkas). Bronze ``artikel``: url, judul, tanggal_terbit (WARC-Date = waktu perayapan, batas atas tanggal
terbit), media, bahasa (atribut ``lang`` HTML), status_http, panjang_konten, tipe_konten, berkas_warc,
jenis_tanggal='warc_date', sumber_penemuan='ccnews'. Kelas C: metadata berita berhak cipta, riset internal.

Opsi: ``bulan=YYYY-MM`` (wajib), ``hari=YYYY-MM-DD`` (WARC yang cap waktunya pada hari itu),
``berkas=<nama>,<nama>`` (WARC tertentu), ``maks_berkas=1``, ``maks_gb=5`` (batas total unduhan; ukuran
dari HEAD), ``estimasi=1``, ``domain=..``/``domain_tambah=..``, ``semua_id=1``, ``pembaca=..``,
``lanjut=0``, ``jeda_s=1.0``.
"""
from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import io
import re
import sys
import zlib
from typing import Iterator

from .. import inti
from . import berita_umum as U

SUMBER = "ccnews"

DASAR = "https://data.commoncrawl.org"
AWALAN_BADAN = 65536          # badan respons yang dibaca untuk <title>
AWALAN_HEADER_HTTP = 16384    # ruang tambahan untuk header HTTP
POLA_WARC = re.compile(r"CC-NEWS-(\d{14})-(\d+)\.warc\.gz$")


# ---------------------------------------------------------------------------------------------------
# Pembaca WARC minimal (fungsi murni atas aliran; diuji luring)
# ---------------------------------------------------------------------------------------------------

class AliranHash(io.RawIOBase):
    """Aliran baca yang menghitung sha256 dan jumlah bita dari potongan (``iter_content``) yang dilewatinya."""

    def __init__(self, potongan):
        self._it = iter(potongan)
        self._sisa = b""
        self.sha = hashlib.sha256()
        self.bita = 0

    def readable(self) -> bool:
        return True

    def readinto(self, b) -> int:
        while not self._sisa:
            try:
                c = next(self._it)
            except StopIteration:
                return 0
            if c:
                self.sha.update(c)
                self.bita += len(c)
                self._sisa = c
        n = min(len(b), len(self._sisa))
        b[:n] = self._sisa[:n]
        self._sisa = self._sisa[n:]
        return n

    def habiskan(self) -> None:
        while self.readinto(bytearray(2**20)):
            pass


class Blok:
    """Blok konten satu rekaman WARC: dibaca paling banyak ``panjang`` bita, sisanya dilewati."""

    def __init__(self, f, panjang: int):
        self.f, self.sisa = f, panjang

    def read(self, n: int = -1) -> bytes:
        n = self.sisa if n is None or n < 0 else min(n, self.sisa)
        out = b""
        while len(out) < n:
            c = self.f.read(n - len(out))
            if not c:
                break
            out += c
        self.sisa -= len(out)
        return out

    def habiskan(self) -> None:
        while self.sisa > 0 and self.read(min(self.sisa, 2**20)):
            pass


def baca_warc(f) -> Iterator[tuple[dict, Blok]]:
    """Rekaman dari aliran WARC yang sudah didekompresi (``gzip.GzipFile`` membaca gzip multi-anggota).
    Menghasilkan (header WARC dengan kunci huruf kecil, blok konten). Blok yang tidak dibaca habis dilewati."""
    while True:
        baris = f.readline()
        if not baris:
            return
        if not baris.strip():
            continue  # \r\n\r\n penutup rekaman sebelumnya
        if not baris.startswith(b"WARC/"):
            raise ValueError(f"bukan awal rekaman WARC: {baris[:40]!r}")
        header = {}
        while True:
            b = f.readline()
            if not b or not b.strip():
                break
            k, _, v = b.decode("utf-8", "replace").partition(":")
            header[k.strip().lower()] = v.strip()
        blok = Blok(f, int(header.get("content-length") or 0))
        yield header, blok
        blok.habiskan()


def urai_http(awal: bytes) -> tuple[int | None, dict, bytes]:
    """Awal blok respons HTTP -> (status, header huruf kecil, awal badan)."""
    kepala, pisah, badan = awal.partition(b"\r\n\r\n")
    if not pisah:
        kepala, pisah, badan = awal.partition(b"\n\n")
    baris = kepala.decode("iso-8859-1").splitlines()
    m = re.match(r"HTTP/\S+\s+(\d{3})", baris[0] if baris else "")
    header = {}
    for x in baris[1:]:
        k, _, v = x.partition(":")
        if k:
            header[k.strip().lower()] = v.strip()
    return (int(m.group(1)) if m else None), header, badan


def _dekode_badan(badan: bytes, header: dict) -> bytes:
    if "gzip" in header.get("content-encoding", "").lower() and badan[:2] == b"\x1f\x8b":
        try:
            return zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(badan, AWALAN_BADAN)
        except zlib.error:
            return b""
    return badan


def judul_html(badan: bytes, tipe_konten: str = "") -> tuple[str, str]:
    """(judul ``<title>``, atribut ``lang`` ``<html>``) dari awal badan HTML."""
    m = re.search(r"charset=[\"']?([\w-]+)", tipe_konten or "", re.I) or \
        re.search(rb"<meta[^>]+charset=[\"']?([\w-]+)", badan[:4096], re.I)
    kode = m.group(1) if m else "utf-8"
    kode = kode.decode("ascii", "replace") if isinstance(kode, bytes) else kode
    try:
        teks = badan.decode(kode, errors="replace")
    except LookupError:
        teks = badan.decode("utf-8", errors="replace")
    t = re.search(r"<title[^>]*>(.*?)</title\s*>", teks, re.I | re.S)
    lang = re.search(r"<html\b[^>]*?\blang\s*=\s*[\"']?([A-Za-z]{2,3}(?:[-_][A-Za-z0-9]+)?)", teks, re.I)
    judul = U.buang_html(t.group(1)) if t else ""
    return judul[:U.PANJANG_JUDUL], (lang.group(1) if lang else "")


def meta_rekaman(header: dict, awal: bytes) -> dict:
    """Metadata rekaman ``response`` yang host-nya cocok; ``awal`` = awal blok (header HTTP + badan)."""
    url = header.get("warc-target-uri", "").strip("<> ")
    status, hh, badan = urai_http(awal)
    tipe = hh.get("content-type", "")
    judul, lang = judul_html(_dekode_badan(badan[:AWALAN_BADAN], hh), tipe) if "html" in tipe.lower() or not tipe else ("", "")
    return {"url": url, "warc_date": header.get("warc-date", ""), "host": U.host(url),
            "status_http": status, "content_length": header.get("content-length", ""),
            "content_length_http": hh.get("content-length", ""), "tipe_konten": tipe.split(";")[0].strip()[:100],
            "judul": judul, "bahasa_html": lang, "warc_record_id": header.get("warc-record-id", "")}


def _cocok(header: dict, domain, semua_id: bool) -> bool:
    return header.get("warc-type") == "response" and bool(
        U.cocok_domain(U.host(header.get("warc-target-uri", "").strip("<> ")), domain, semua_id))


def rekaman_minimal(aliran, domain, semua_id: bool = False) -> Iterator[dict]:
    """Metadata rekaman cocok dari aliran WARC gzip (terkompresi) dengan pembaca minimal."""
    for header, blok in baca_warc(gzip.GzipFile(fileobj=aliran)):
        if _cocok(header, domain, semua_id):
            yield meta_rekaman(header, blok.read(AWALAN_HEADER_HTTP + AWALAN_BADAN))


def rekaman_warcio(aliran, domain, semua_id: bool = False) -> Iterator[dict]:
    """Seperti ``rekaman_minimal`` dengan ``warcio.ArchiveIterator`` (badan tidak didekode ulang oleh warcio,
    sehingga hasilnya sama dengan pembaca minimal)."""
    from warcio.archiveiterator import ArchiveIterator

    for rec in ArchiveIterator(aliran, no_record_parse=True):
        header = {k.lower(): v for k, v in rec.rec_headers.headers}
        if _cocok(header, domain, semua_id):
            yield meta_rekaman(header, rec.raw_stream.read(AWALAN_HEADER_HTTP + AWALAN_BADAN))


def pilih_pembaca(nama: str = "otomatis") -> str:
    if nama == "minimal":
        return "minimal"
    try:
        import warcio  # noqa: F401
        return "warcio"
    except ImportError:
        if nama == "warcio":
            raise
        return "minimal"


# ---------------------------------------------------------------------------------------------------
# Daftar WARC, rilis, Bronze
# ---------------------------------------------------------------------------------------------------

def url_paths(bulan: str) -> str:
    if not re.fullmatch(r"\d{4}-\d{2}", bulan or ""):
        raise ValueError(f"bulan harus YYYY-MM: {bulan!r}")
    return f"{DASAR}/crawl-data/CC-NEWS/{bulan[:4]}/{bulan[5:]}/warc.paths.gz"


def urai_paths(isi_gz: bytes) -> list[str]:
    return [x.strip() for x in gzip.decompress(isi_gz).decode("utf-8").splitlines() if x.strip()]


def waktu_warc(path: str) -> str:
    m = POLA_WARC.search(path)
    return U.tanggal_gdelt(m.group(1)) if m else ""


def pilih_warc(paths: list[str], hari: str | None = None, berkas: list[str] | None = None,
               maks: int = 1) -> list[str]:
    """WARC terpilih: nama tertentu, atau yang cap waktunya pada ``hari``, atau semua; lalu ``maks`` pertama."""
    if berkas:
        out = [p for p in paths if p.rsplit("/", 1)[-1] in set(berkas)]
    elif hari:
        h = hari.replace("-", "")
        out = [p for p in paths if (m := POLA_WARC.search(p)) and m.group(1).startswith(h)]
    else:
        out = list(paths)
    return out[:maks]


def nama_warc(path: str) -> str:
    return path.rsplit("/", 1)[-1].removesuffix(".warc.gz")


def baris_artikel(r: dict, warc: str) -> dict:
    h = r.get("host") or U.host(r.get("url", ""))
    return {"url": r.get("url", ""), "judul": r.get("judul", ""), "tanggal_terbit": U.urai_tanggal(r.get("warc_date"), dt.timezone.utc),
            "media": U.cocok_domain(h, U.DOMAIN_ID, semua_id=True) or h, "bahasa": U.bahasa_baku(r.get("bahasa_html")),
            "status_http": r.get("status_http"), "panjang_konten": r.get("content_length"),
            "tipe_konten": r.get("tipe_konten", ""), "berkas_warc": warc, "jenis_tanggal": "warc_date",
            "sumber_penemuan": SUMBER}


def baris_bronze(rows: list[dict], warc: str) -> list[dict]:
    return U.periksa_panjang([baris_artikel(r, warc) | {"_urutan": i} for i, r in enumerate(rows, start=1)])


# ---------------------------------------------------------------------------------------------------
# Jaringan
# ---------------------------------------------------------------------------------------------------

def _log(pesan: str) -> None:
    print(f"[ccnews] {pesan}", file=sys.stderr, flush=True)


def jalankan(snap: inti.Snapshot, opsi: dict) -> dict:
    http = inti.Http(jeda_s=float(opsi.get("jeda_s", 1.0)), batas_waktu=600)
    if str(opsi.get("lanjut", "1")) != "0":
        U.pulihkan(snap)
    domain, semua_id = U.daftar_domain(opsi), opsi.get("semua_id") == "1"
    pembaca = pilih_pembaca(opsi.get("pembaca", "otomatis"))
    bulan = opsi.get("bulan") or ""
    url = url_paths(bulan)
    r = http.get(url)
    nama_paths = f"paths/{bulan}.warc.paths.gz"
    if nama_paths not in snap.berkas or snap.berkas[nama_paths]["sha256"] != inti.sha256_bita(r.content):
        snap.simpan(nama_paths, r.content, url)
    paths = urai_paths(r.content)
    pilihan = pilih_warc(paths, opsi.get("hari"), [x.strip() for x in opsi.get("berkas", "").split(",") if x.strip()],
                         int(opsi.get("maks_berkas", 1)))
    pilihan = [p for p in pilihan if f"warc/{nama_warc(p)}.jsonl" not in snap.berkas]
    maks_gb = float(opsi.get("maks_gb", 5))
    ukuran = {}
    for p in pilihan:
        try:
            ukuran[p] = int(http.head(f"{DASAR}/{p}").headers.get("Content-Length") or 0)
        except Exception as e:  # noqa: BLE001
            snap.tambah_galat(f"HEAD {p}", e)
            ukuran[p] = 0
    total = sum(ukuran.values())
    est = {"warc_bulan": len(paths), "warc_pilih": len(pilihan), "bita_unduh": total, "gb": round(total / 1e9, 3),
           "maks_gb": maks_gb, "ukuran_diketahui": all(ukuran.values())}
    snap.catatan.append({"apa": "taksiran unduhan CC-NEWS", "bulan": bulan, "domain": domain,
                         "semua_id": semua_id, "pembaca": pembaca} | est)
    _log(f"{len(pilihan)} WARC dari {len(paths)}, {est['gb']} GB (batas {maks_gb} GB)")
    if total > maks_gb * 1e9:
        raise RuntimeError(f"unduhan {est['gb']} GB melebihi maks_gb={maks_gb}")
    if opsi.get("estimasi") == "1":
        return {"estimasi": est}
    baca = rekaman_warcio if pembaca == "warcio" else rekaman_minimal
    ringkas = {"warc": 0, "artikel": 0}
    for p in pilihan:
        u = f"{DASAR}/{p}"
        try:
            resp = http.get(u, stream=True)
            aliran = AliranHash(resp.iter_content(2**20))
            rows = list(baca(io.BufferedReader(aliran, 2**20), domain, semua_id))
            aliran.habiskan()
        except Exception as e:  # noqa: BLE001
            snap.tambah_galat(u, e)
            continue
        nama, warc = f"warc/{nama_warc(p)}.jsonl", nama_warc(p)
        snap.catat_ekstrak(nama, U.jsonl(rows), u, aliran.sha.hexdigest(), aliran.bita, pembaca=pembaca,
                           aturan="rekaman response dengan host dalam daftar domain; hanya metadata (url, WARC-Date, "
                                  "status, Content-Length, tipe, <title> dan lang dari 64 KB pertama); badan dibuang")
        rid = snap.tambah_rilis(inti.Rilis(SUMBER, warc, "pembaruan_sumber", waktu_warc(p),
                                           "cap waktu pada nama berkas WARC CC-NEWS (UTC)",
                                           cakupan=f"{p}; {len(rows)} rekaman cocok"))
        ringkas["artikel"] += snap.tulis_bronze("artikel", baris_bronze(rows, warc), rid, nama)
        ringkas["warc"] += 1
        snap.selesai()  # manifest sementara agar jalan panjang dapat dilanjutkan
        _log(f"{warc}: {len(rows)} rekaman cocok, {aliran.bita / 1e9:.2f} GB")
    return ringkas
