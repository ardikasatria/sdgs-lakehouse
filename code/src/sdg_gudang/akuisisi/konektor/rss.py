"""Konektor aliran RSS/Atom media Indonesia (``rss``), penemuan berita terkini untuk alur klaim M5.

Aliran diurai dengan ``xml.etree`` (RSS 2.0, RSS 1.0/RDF, dan Atom; tanpa ``feedparser``). Raw = XML aliran
apa adanya. Bila aliran memuat teks penuh (``content:encoded``, ``atom:content``) atau deskripsi lebih dari
``DESKRIPSI_MAKS`` karakter, yang disimpan adalah ekstrak (elemen teks penuh dibuang, deskripsi dipotong dua
kalimat) dengan sha256 dan ukuran asli dicatat (``catat_ekstrak``), karena teks penuh dilarang kebijakan
simpan (brief 4 Bagian 2.6). Halaman artikel tidak diambil.

Robots.txt host aliran diperiksa sebelum aliran diambil (opsi ``robots=0`` mematikannya; aliran memang
ditujukan untuk mesin, tetapi larangan eksplisit tetap dihormati). Jeda per host bawaan 2 detik.

Rilis: satu per pengambilan aliran, kode ``<feed>@<sha256[:12]>`` (sha256 payload asli), jenis
``tanggal_unduh``. Jalan berulang pada hari yang sama melanjutkan manifest hari itu; payload yang sha256-nya
sudah tercatat dilewati. Bronze ``artikel``: url, judul, tanggal_terbit (ISO berzona; tanpa zona dianggap
WIB), tanggal_terbit_asli, media, bahasa, ringkasan (paling banyak dua kalimat, tanpa HTML), feed,
jenis_tanggal, sumber_penemuan='rss'. Kelas C: metadata berita berhak cipta, hanya riset internal.

Opsi: ``feed=antara_ekonomi,cnn_ekonomi`` (subset), ``feed_tambah=kunci|url,kunci2|url2``,
``robots=0``, ``lanjut=0``, ``jeda_s=2.0``.
"""
from __future__ import annotations

import datetime as dt
import io
import re
import xml.etree.ElementTree as ET

from .. import inti
from . import berita_umum as U

SUMBER = "rss"

#: Aliran bawaan. URL Antara dari brief 4 Bagian 2.6 (20 butir per aliran). URL CNN Indonesia dan Detik
#: mengikuti pola yang diumumkan situsnya; keberlakuannya **[BELUM DIPERIKSA]** dari lingkungan ini
#: (tanpa akses jaringan ke media). Tempo (butir terakhir 14 Sep 2026) dan Kompas/Katadata (aliran belum
#: ditemukan) tidak dimasukkan.
FEED = {
    "antara_ekonomi": {"url": "https://www.antaranews.com/rss/ekonomi.xml",
                       "catatan": "Antara rubrik ekonomi; ketentuan Antara: reproduksi perlu izin tertulis"},
    "antara_terkini": {"url": "https://www.antaranews.com/rss/terkini.xml",
                       "catatan": "Antara berita terkini lintas rubrik (termasuk nasional)"},
    "cnn_ekonomi": {"url": "https://www.cnnindonesia.com/ekonomi/rss",
                    "catatan": "CNN Indonesia rubrik ekonomi [BELUM DIPERIKSA]"},
    "detik_finance": {"url": "https://finance.detik.com/rss",
                      "catatan": "detikFinance [BELUM DIPERIKSA]; alternatif rss.detik.com/index.php/finance"},
}

DESKRIPSI_MAKS = 1000  # deskripsi lebih panjang dianggap teks penuh dan dipotong di raw
ATOM = "http://www.w3.org/2005/Atom"
#: Elemen teks penuh (Clark notation) yang dibuang dari raw. ``media:content`` (gambar) tidak termasuk.
ELEMEN_TEKS_PENUH = {"{http://purl.org/rss/1.0/modules/content/}encoded": "content:encoded",
                     f"{{{ATOM}}}content": "atom:content"}
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"


# ---------------------------------------------------------------------------------------------------
# Fungsi murni (diuji luring)
# ---------------------------------------------------------------------------------------------------

def _lokal(tag) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _anak(el, *nama) -> ET.Element | None:
    for n in nama:
        for c in el:
            if _lokal(c.tag) == n:
                return c
    return None


def _teks(el) -> str:
    return "".join(el.itertext()).strip() if el is not None else ""


def _tautan_atom(el) -> str:
    pilihan = [c for c in el if _lokal(c.tag) == "link"]
    for c in pilihan:
        if c.get("rel", "alternate") == "alternate" and c.get("href"):
            return c.get("href").strip()
    return next((c.get("href").strip() for c in pilihan if c.get("href")), "")


def urai_feed(isi: bytes) -> dict:
    """Urai RSS 2.0, RSS 1.0 (RDF), atau Atom menjadi ``{jenis, bahasa, judul, butir}``. Setiap butir memuat
    ``url``, ``judul``, ``tanggal_asli``, ``deskripsi`` (HTML apa adanya) dan ``guid``. Elemen teks penuh
    (``content:encoded``, ``atom:content``) tidak dibaca."""
    akar = ET.fromstring(isi)
    if _lokal(akar.tag) == "feed":
        out = {"jenis": "atom", "bahasa": akar.get(XML_LANG, ""), "judul": _teks(_anak(akar, "title")), "butir": []}
        for e in (c for c in akar if _lokal(c.tag) == "entry"):
            out["butir"].append({
                "url": _tautan_atom(e), "judul": _teks(_anak(e, "title")),
                "tanggal_asli": _teks(_anak(e, "published", "updated", "issued")),
                "deskripsi": _teks(_anak(e, "summary")), "guid": _teks(_anak(e, "id"))})
        return out
    kanal = next((c for c in akar.iter() if _lokal(c.tag) == "channel"), akar)
    out = {"jenis": "rss" if _lokal(akar.tag) == "rss" else "rdf",
           "bahasa": _teks(_anak(kanal, "language")) or akar.get(XML_LANG, ""),
           "judul": _teks(_anak(kanal, "title")), "butir": []}
    for it in (c for c in akar.iter() if _lokal(c.tag) == "item"):
        url = _teks(_anak(it, "link")) or _tautan_atom(it)
        guid = _anak(it, "guid")
        if not url and guid is not None and guid.get("isPermaLink", "true") != "false":
            url = _teks(guid)
        out["butir"].append({
            "url": url, "judul": _teks(_anak(it, "title")),
            "tanggal_asli": _teks(_anak(it, "pubDate", "date", "published", "updated")),
            "deskripsi": _teks(_anak(it, "description", "summary")), "guid": _teks(guid)})
    return out


def bersihkan_feed(isi: bytes, maks: int = DESKRIPSI_MAKS) -> bytes | None:
    """XML aliran tanpa elemen teks penuh dan dengan deskripsi panjang dipotong dua kalimat. ``None`` bila
    aliran tidak memuat keduanya (raw disimpan utuh)."""
    for _, (awalan, uri) in ET.iterparse(io.BytesIO(isi), events=("start-ns",)):
        if awalan and not re.fullmatch(r"ns\d+", awalan):
            ET.register_namespace(awalan, uri)
    akar = ET.fromstring(isi)
    ubah = False
    for induk in list(akar.iter()):
        for c in list(induk):
            n = _lokal(c.tag)
            if c.tag in ELEMEN_TEKS_PENUH:
                induk.remove(c)
                ubah = True
            elif n in ("description", "summary") and len(_teks(c)) > maks:
                for anak in list(c):
                    c.remove(anak)
                c.text = U.potong_kalimat(U.buang_html(_teks(c)))
                c.attrib.pop("type", None)
                ubah = True
    return ET.tostring(akar, encoding="utf-8", xml_declaration=True) if ubah else None


def pangkas(s: str, n: int) -> str:
    s = re.sub(r"\s+", " ", s or "").strip()
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"


def baris_rss(feed: dict, kunci: str, bahasa_bawaan: str = "id") -> list[dict]:
    """Baris Bronze ``artikel`` dari aliran terurai. Butir tanpa URL dibuang."""
    bahasa = U.bahasa_baku(feed.get("bahasa")) or bahasa_bawaan
    out = []
    for i, b in enumerate(feed["butir"], start=1):
        url = (b.get("url") or "").strip()
        if not url:
            continue
        h = U.host(url)
        out.append({
            "url": url, "judul": pangkas(U.buang_html(b.get("judul")), U.PANJANG_JUDUL),
            "tanggal_terbit": U.urai_tanggal(b.get("tanggal_asli")),
            "tanggal_terbit_asli": pangkas(b.get("tanggal_asli") or "", 80),
            "media": U.cocok_domain(h, U.DOMAIN_ID) or h, "bahasa": bahasa,
            "ringkasan": U.potong_kalimat(U.buang_html(b.get("deskripsi"))),
            "feed": kunci, "jenis_tanggal": "pubdate_feed", "sumber_penemuan": SUMBER, "_urutan": i})
    return U.periksa_panjang(out)


def kode_rilis(kunci: str, sha: str) -> str:
    return f"{kunci}@{sha[:12]}"


def pilih_feed(opsi: dict) -> dict:
    feed = dict(FEED)
    for x in (opsi.get("feed_tambah") or "").split(","):
        if x.strip():
            k, _, u = x.partition("|")
            if not re.fullmatch(r"[a-z0-9_]+", k.strip()) or not u.strip().startswith(("http://", "https://")):
                raise ValueError(f"feed_tambah tidak sah: {x!r} (bentuk kunci|url)")
            feed[k.strip()] = {"url": u.strip(), "catatan": "tambahan opsi"}
    if opsi.get("feed"):
        pilih = [x.strip() for x in opsi["feed"].split(",") if x.strip()]
        tak = [x for x in pilih if x not in feed]
        if tak:
            raise ValueError(f"feed tidak dikenal: {tak}")
        feed = {k: feed[k] for k in pilih}
    return feed


# ---------------------------------------------------------------------------------------------------
# Jaringan
# ---------------------------------------------------------------------------------------------------

def jalankan(snap: inti.Snapshot, opsi: dict) -> dict:
    http = inti.Http(jeda_s=float(opsi.get("jeda_s", 2.0)), batas_waktu=60,
                     header={"Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.5"})
    if str(opsi.get("lanjut", "1")) != "0":
        U.pulihkan(snap)
    robots = U.Robots(http, snap) if str(opsi.get("robots", "1")) != "0" else None
    sudah = {b.get("sha256_asli") or b["sha256"] for n, b in snap.berkas.items() if n.startswith("feed/")}
    ringkas: dict = {}
    for kunci, f in pilih_feed(opsi).items():
        url = f["url"]
        if robots is not None and not robots.boleh(url):
            snap.tambah_galat(kunci, f"robots.txt tidak mengizinkan {url}")
            ringkas[kunci] = "robots"
            continue
        try:
            r = http.get(url)
        except Exception as e:  # noqa: BLE001
            snap.tambah_galat(kunci, e)
            ringkas[kunci] = "galat"
            continue
        isi, sha = r.content, inti.sha256_bita(r.content)
        if sha in sudah:
            ringkas[kunci] = "tidak berubah"
            continue
        try:
            urai_feed(isi)
            bersih = bersihkan_feed(isi)
        except ET.ParseError as e:
            snap.tambah_galat(kunci, f"bukan XML aliran ({len(isi)} bita, sha256 {sha[:12]}): {e}")
            ringkas[kunci] = "bukan XML"
            continue
        waktu = dt.datetime.now(inti.ZONA).strftime("%H%M%S")
        nama = f"feed/{kunci}/{waktu}-{sha[:12]}.xml"
        if bersih is None:
            snap.simpan(nama, isi, url, feed=kunci)
            simpan = isi
        else:
            snap.catat_ekstrak(nama, bersih, url, sha, len(isi), feed=kunci,
                               aturan=f"elemen teks penuh ({', '.join(sorted(ELEMEN_TEKS_PENUH.values()))}) dibuang; "
                                      f"deskripsi > {DESKRIPSI_MAKS} karakter dipotong dua kalimat")
            simpan = bersih
        sudah.add(sha)
        rows = baris_rss(urai_feed(simpan), kunci)  # dari bita yang disimpan, sama dengan bangun ulang
        rid = snap.tambah_rilis(inti.Rilis(SUMBER, kode_rilis(kunci, sha), "tanggal_unduh", snap.tanggal,
                                           "aliran tanpa nomor rilis; tanggal unduh", cakupan=f"{kunci}: {url}"))
        ringkas[kunci] = snap.tulis_bronze("artikel", rows, rid, nama)
    if robots is not None:
        snap.catatan.append({"apa": "robots.txt", "periksa": robots.log})
    return {"feed": ringkas, "rilis": len(snap.rilis)}
