"""Fungsi bersama konektor berita ``gdelt``, ``rss``, dan ``ccnews`` (brief 4 Bagian 2.6 dan 5.2). Bukan sumber.

**Kebijakan simpan (mengikat).** Gudang hanya menyimpan URL, judul, tanggal terbit, media (domain), bahasa,
dan untuk RSS ringkasan butir aliran paling banyak dua kalimat. Teks penuh artikel tidak pernah disimpan
dan tidak diambil pada tahap penemuan. Robots.txt (RFC 9309) diperiksa lewat ``urllib.robotparser``
sebelum mengambil apa pun dari situs media; jeda per host diatur ``inti.Http``.

Semua fungsi di sini murni (tanpa jaringan) kecuali ``Robots.boleh``, yang mengambil robots.txt sekali per
host lewat ``inti.Http`` dan mencatatnya ke raw.
"""
from __future__ import annotations

import datetime as dt
import html
import re
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

from .. import inti

#: Token produk untuk pencocokan robots.txt (bagian dari ``inti.AGEN``).
TOKEN_ROBOTS = "LigaLakehouse-penelitian"

#: Media daring Indonesia terpilih (domain terdaftar -> nama). Subdomain ikut cocok (``ekonomi.bisnis.com``).
#: Disusun dari daftar media nasional berbahasa Indonesia dan dua media berbahasa Inggris terbitan Indonesia;
#: ketersediaannya di GDELT dan CC-NEWS **[BELUM DIPERIKSA]** sampai jalan pertama di Mac.
DOMAIN_ID = {
    "antaranews.com": "Antara", "kompas.com": "Kompas", "kompas.id": "Kompas.id", "detik.com": "Detik",
    "cnnindonesia.com": "CNN Indonesia", "cnbcindonesia.com": "CNBC Indonesia", "tempo.co": "Tempo",
    "liputan6.com": "Liputan6", "kontan.co.id": "Kontan", "bisnis.com": "Bisnis Indonesia",
    "katadata.co.id": "Katadata", "republika.co.id": "Republika", "tribunnews.com": "Tribun",
    "okezone.com": "Okezone", "sindonews.com": "Sindonews", "merdeka.com": "Merdeka", "suara.com": "Suara",
    "kumparan.com": "Kumparan", "idntimes.com": "IDN Times", "beritasatu.com": "Beritasatu",
    "investor.id": "Investor Daily", "jpnn.com": "JPNN", "mediaindonesia.com": "Media Indonesia",
    "tirto.id": "Tirto", "viva.co.id": "Viva", "inews.id": "iNews", "medcom.id": "Medcom",
    "thejakartapost.com": "The Jakarta Post", "jakartaglobe.id": "Jakarta Globe",
}

PANJANG_RINGKASAN = 400   # batas karakter ringkasan dua kalimat
PANJANG_JUDUL = 300
PANJANG_TEMA = 1000
PANJANG_MAKS_BRONZE = 600  # penjaga: kolom selain tema/url yang lebih panjang menandakan teks artikel bocor

#: Singkatan yang titiknya bukan akhir kalimat (huruf kecil, tanpa titik).
SINGKATAN = {"dr", "drs", "dra", "ir", "prof", "h", "hj", "no", "jl", "kab", "prov", "kec", "tbk", "pt", "st",
             "sdr", "bpk", "mr", "mrs", "ms", "dll", "dsb", "dkk", "vs", "sd", "smp", "sma", "a.n", "u.p",
             "m.si", "m.sc", "s.e", "s.h", "s.t", "s.pd", "jan", "feb", "mar", "apr", "jun", "jul", "agu",
             "agt", "sep", "sept", "okt", "nov", "des", "rp"}

BULAN_ID = {"jan": "Jan", "feb": "Feb", "mar": "Mar", "apr": "Apr", "mei": "May", "jun": "Jun", "jul": "Jul",
            "agu": "Aug", "agt": "Aug", "ags": "Aug", "sep": "Sep", "okt": "Oct", "nov": "Nov", "des": "Dec"}
HARI_ID = {"sen", "sel", "rab", "kam", "jum", "sab", "min"}

BAHASA_639_3 = {"ind": "id", "eng": "en", "msa": "ms", "zsm": "ms", "jav": "jv", "sun": "su", "zho": "zh",
                "ara": "ar", "jpn": "ja", "kor": "ko", "fra": "fr", "deu": "de", "spa": "es", "nld": "nl"}


# ---------------------------------------------------------------------------------------------------
# Domain dan media
# ---------------------------------------------------------------------------------------------------

def host(url: str) -> str:
    """Host huruf kecil tanpa port dan tanpa ``www.``."""
    h = (urlsplit(url.strip()).hostname or "").lower().rstrip(".")
    return h[4:] if h.startswith("www.") else h


def cocok_domain(h: str, domain, semua_id: bool = False) -> str:
    """Domain terdaftar yang cocok dengan host ``h`` (tepat atau subdomain), atau ``""``. Dengan ``semua_id``,
    host ber-TLD ``.id`` yang tidak terdaftar dikembalikan apa adanya."""
    h = (h or "").lower().rstrip(".")
    h = h[4:] if h.startswith("www.") else h
    for d in sorted(domain, key=len, reverse=True):
        if h == d or h.endswith("." + d):
            return d
    if semua_id and h.endswith(".id"):
        return h
    return ""


def daftar_domain(opsi: dict) -> list[str]:
    """Domain dari opsi ``domain=a,b`` (ganti) atau ``domain_tambah=a,b`` (tambah ke ``DOMAIN_ID``)."""
    def pisah(s):
        return [x.strip().lower() for x in (s or "").split(",") if x.strip()]

    dasar = pisah(opsi.get("domain")) or list(DOMAIN_ID)
    hasil = sorted(set(dasar) | set(pisah(opsi.get("domain_tambah"))))
    for d in hasil:
        if not re.fullmatch(r"[a-z0-9-]+(\.[a-z0-9-]+)+", d):
            raise ValueError(f"domain tidak sah: {d!r}")
    return hasil


def bahasa_baku(kode: str | None) -> str:
    """``id-ID`` -> ``id``; ``ind`` -> ``id``; kosong tetap kosong."""
    k = (kode or "").strip().lower().replace("_", "-").split("-")[0]
    return BAHASA_639_3.get(k, k)


# ---------------------------------------------------------------------------------------------------
# Teks: HTML, kalimat, tanggal
# ---------------------------------------------------------------------------------------------------

class _Teks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.bagian: list[str] = []
        self._abaikan = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._abaikan += 1
        elif tag in ("br", "p", "div", "li"):
            self.bagian.append(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._abaikan:
            self._abaikan -= 1

    def handle_data(self, data):
        if not self._abaikan:
            self.bagian.append(data)


def buang_html(s: str | None) -> str:
    """Teks polos dari potongan HTML: tag dan skrip dibuang, entitas diurai, spasi dirapikan."""
    if not s:
        return ""
    p = _Teks()
    p.feed(s)
    p.close()
    return re.sub(r"\s+", " ", html.unescape("".join(p.bagian))).strip()


_AKHIR = re.compile(r"[.!?…]+[\"'”’)]*(?=\s|$)")


def potong_kalimat(teks: str, n: int = 2, maks: int = PANJANG_RINGKASAN) -> str:
    """Paling banyak ``n`` kalimat pertama, lalu dipangkas ke ``maks`` karakter pada batas kata (dengan "…").
    Titik setelah singkatan, inisial satu huruf, atau di antara angka tidak dihitung akhir kalimat.
    Idempoten: memotong hasil potongan memberi hasil yang sama."""
    teks = re.sub(r"\s+", " ", teks or "").strip()
    akhir, hitung = len(teks), 0
    for m in _AKHIR.finditer(teks):
        kata = re.findall(r"[\w.]+$", teks[:m.start()])
        token = kata[0].lower() if kata else ""
        if m.group(0).startswith(".") and (token in SINGKATAN or re.fullmatch(r"\w", token)):
            continue
        hitung += 1
        if hitung == n:
            akhir = m.end()
            break
    out = teks[:akhir].strip()
    if len(out) > maks:
        out = out[:maks - 1].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"
    return out


def _tz(d: dt.datetime, bawaan: dt.tzinfo) -> dt.datetime:
    return d.replace(tzinfo=bawaan) if d.tzinfo is None else d


def urai_tanggal(s: str | None, bawaan: dt.tzinfo = inti.ZONA) -> str:
    """RFC 822 (termasuk nama hari/bulan Indonesia) atau ISO 8601 -> ISO dengan zona waktu; kosong bila gagal.
    Tanggal tanpa zona dianggap WIB (aliran media Indonesia)."""
    s = (s or "").strip()
    if not s:
        return ""
    try:
        d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        return _tz(d, bawaan).isoformat(timespec="seconds")
    except ValueError:
        pass
    t = re.sub(r"\s+", " ", s.replace(",", ", ")).strip()
    kata = t.split(" ")
    # nama hari Indonesia (Sel, Selasa) tidak dikenal email.utils; nama hari tidak diperlukan untuk tanggal
    kata = [w for w in kata if not (w.rstrip(",").isalpha() and w.rstrip(",").lower()[:3] in HARI_ID)]
    kata = [BULAN_ID.get(w.lower()[:3], w) if w.isalpha() and w.lower()[:3] in BULAN_ID and len(w) <= 9 else w
            for w in kata]
    t = " ".join(kata).replace("WIB", "+0700").replace("WITA", "+0800").replace("WIT", "+0900")
    try:
        d = parsedate_to_datetime(t)
    except (TypeError, ValueError, IndexError):
        return ""
    if d is None:
        return ""
    return _tz(d, bawaan).isoformat(timespec="seconds")


def tanggal_gdelt(s: str | int | None) -> str:
    """``20250101001500`` (UTC) -> ``2025-01-01T00:15:00+00:00``."""
    s = str(s or "").strip()
    if not re.fullmatch(r"\d{14}", s):
        return ""
    return dt.datetime.strptime(s, "%Y%m%d%H%M%S").replace(tzinfo=dt.timezone.utc).isoformat()


# ---------------------------------------------------------------------------------------------------
# Penjaga kebijakan simpan
# ---------------------------------------------------------------------------------------------------

def periksa_panjang(rows: list[dict], maks: int = PANJANG_MAKS_BRONZE, kecuali=("tema", "url")) -> list[dict]:
    """Tolak baris Bronze yang memuat kolom teks lebih panjang dari ``maks`` (kecuali ``tema`` dan ``url``).
    Kolom panjang menandakan teks artikel ikut tersimpan, yang dilarang kebijakan simpan."""
    for r in rows:
        for k, v in r.items():
            if k not in kecuali and v is not None and len(str(v)) > maks:
                raise ValueError(f"kolom {k} sepanjang {len(str(v))} karakter melanggar kebijakan simpan ({r.get('url')})")
    return rows


# ---------------------------------------------------------------------------------------------------
# Robots.txt (RFC 9309)
# ---------------------------------------------------------------------------------------------------

def boleh_robots(robots_txt: str, url: str, agen: str = TOKEN_ROBOTS) -> bool:
    """Apakah ``url`` boleh diambil menurut isi robots.txt untuk agen ``agen`` (fungsi murni)."""
    rp = RobotFileParser()
    rp.parse(robots_txt.splitlines())
    return rp.can_fetch(agen, url)


class Robots:
    """Cache robots.txt per host. RFC 9309: 4xx = semua boleh; 5xx atau tak terjangkau = semua dilarang.
    Setiap robots.txt yang terbaca disimpan ke raw ``robots/<host>-<sha12>.txt`` sebagai bukti."""

    def __init__(self, http: inti.Http, snap: inti.Snapshot | None = None):
        self.http, self.snap = http, snap
        self.cache: dict[str, tuple[str, str | None]] = {}  # host -> (status, isi)
        self.log: list[dict] = []

    def _muat(self, akar: str) -> tuple[str, str | None]:
        import requests

        url = f"{akar}/robots.txt"
        try:
            r = self.http.get(url)
        except requests.HTTPError as e:
            kode = getattr(getattr(e, "response", None), "status_code", None) or 0
            return ("tidak_ada" if 400 <= kode < 500 else "galat", None)
        except Exception:  # noqa: BLE001  koneksi gagal setelah coba ulang
            return ("galat", None)
        isi = r.content.decode("utf-8", errors="replace")
        if self.snap is not None:
            sha = inti.sha256_bita(r.content)
            self.snap.simpan(f"robots/{urlsplit(akar).netloc}-{sha[:12]}.txt", r.content, url)
        return ("ada", isi)

    def boleh(self, url: str) -> bool:
        u = urlsplit(url)
        akar = f"{u.scheme}://{u.netloc}"
        if akar not in self.cache:
            self.cache[akar] = self._muat(akar)
        status, isi = self.cache[akar]
        hasil = True if status == "tidak_ada" else False if status == "galat" else boleh_robots(isi, url)
        self.log.append({"url": inti.url_aman(url), "robots": status, "boleh": hasil})
        return hasil


# ---------------------------------------------------------------------------------------------------
# Lanjutan snapshot dan JSONL
# ---------------------------------------------------------------------------------------------------

def pulihkan(snap: inti.Snapshot) -> bool:
    """Lanjutkan snapshot hari yang sama (aliran RSS diambil beberapa kali sehari; jalan GDELT/CC-NEWS panjang):
    muat berkas, rilis, Bronze, dan catatan dari manifest lama."""
    import json

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
        snap.catatan.append({"apa": "galat jalan sebelumnya", "galat": m["galat"]})
    return True


def jsonl(rows: list[dict]) -> bytes:
    import json

    return "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows).encode("utf-8")


def baca_jsonl(isi: bytes) -> list[dict]:
    import json

    return [json.loads(x) for x in isi.decode("utf-8").splitlines() if x.strip()]
