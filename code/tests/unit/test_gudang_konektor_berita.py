"""Uji luring konektor berita M5 (``gdelt``, ``rss``, ``ccnews``): urai aliran, tanggal, potong dua kalimat,
buang HTML, robots.txt, SQL BigQuery, saring GKG, pembaca WARC, kebijakan simpan, dan bangun ulang Bronze."""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from sdg_gudang.akuisisi import inti
from sdg_gudang.akuisisi.konektor import berita_umum as U
from sdg_gudang.akuisisi.konektor import ccnews, gdelt, rss
from sdg_gudang.akuisisi.ulang import bangun_ulang

TEKS_PANJANG = ("Kalimat artikel penuh yang tidak boleh disimpan. " * 80).strip()

RSS2 = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/"
     xmlns:media="http://search.yahoo.com/mrss/" xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel><title>ANTARA - Ekonomi</title><language>id-ID</language>
<item>
  <title>BPS: inflasi Oktober 2,1 persen</title>
  <link>https://www.antaranews.com/berita/1/bps-inflasi</link>
  <pubDate>Sel, 20 Okt 2026 10:15:00 +0700</pubDate>
  <description><![CDATA[<p>Jakarta (ANTARA) - Badan Pusat Statistik (BPS) mencatat inflasi 2,1 persen.
  Angka itu turun dari bulan lalu. Kepala BPS Dr. Amalia menyampaikannya di Jakarta.</p><img src="x.jpg"/>]]></description>
  <content:encoded><![CDATA[<p>{TEKS_PANJANG}</p>]]></content:encoded>
  <media:content url="https://img.antaranews.com/x.jpg" medium="image"/>
</item>
<item>
  <title>Tanpa tautan</title><description>dibuang</description>
</item>
<item>
  <title>Ekspor &amp; impor</title>
  <link>https://ekonomi.bisnis.com/read/2</link>
  <dc:date>2026-10-19T08:00:00Z</dc:date>
  <description>&lt;b&gt;Ekspor&lt;/b&gt; naik. Impor turun! Neraca surplus.</description>
</item>
</channel></rss>""".encode("utf-8")

ATOM = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xml:lang="id">
  <title>Contoh Atom</title>
  <entry>
    <title type="html">Kemiskinan &lt;em&gt;turun&lt;/em&gt;</title>
    <link rel="enclosure" href="https://contoh.id/a.mp3"/>
    <link rel="alternate" href="https://www.kompas.com/read/3"/>
    <id>tag:kompas.com,2026:3</id>
    <updated>2026-10-18T09:00:00+07:00</updated>
    <published>2026-10-18T07:30:00+07:00</published>
    <summary>Persentase penduduk miskin turun. Data BPS Maret 2026. Kalimat ketiga.</summary>
    <content type="html">TEKS PENUH</content>
  </entry>
</feed>"""


# ---------------------------------------------------------------------------------------------------
# Teks, tanggal, robots
# ---------------------------------------------------------------------------------------------------

class TestTeks(unittest.TestCase):
    def test_buang_html(self):
        self.assertEqual(U.buang_html("<p>Satu&nbsp;<b>dua</b></p><script>x()</script><br>tiga &amp; empat"),
                         "Satu dua tiga & empat")
        self.assertEqual(U.buang_html(None), "")

    def test_potong_dua_kalimat(self):
        t = "Inflasi naik 2,1 persen. Kepala BPS Dr. Amalia menyampaikannya. Kalimat ketiga dibuang."
        self.assertEqual(U.potong_kalimat(t), "Inflasi naik 2,1 persen. Kepala BPS Dr. Amalia menyampaikannya.")
        self.assertEqual(U.potong_kalimat("Ekspor naik. Impor turun! Neraca surplus."), "Ekspor naik. Impor turun!")
        self.assertEqual(U.potong_kalimat("Tanpa titik"), "Tanpa titik")
        panjang = U.potong_kalimat(TEKS_PANJANG.replace(".", ","))
        self.assertLessEqual(len(panjang), U.PANJANG_RINGKASAN)
        self.assertTrue(panjang.endswith("…"))
        for x in (t, TEKS_PANJANG, panjang):  # idempoten: aman untuk raw yang sudah dipotong
            self.assertEqual(U.potong_kalimat(U.potong_kalimat(x)), U.potong_kalimat(x))

    def test_urai_tanggal(self):
        self.assertEqual(U.urai_tanggal("Tue, 20 Oct 2026 10:15:00 +0700"), "2026-10-20T10:15:00+07:00")
        self.assertEqual(U.urai_tanggal("Sel, 20 Okt 2026 10:15:00 +0700"), "2026-10-20T10:15:00+07:00")
        self.assertEqual(U.urai_tanggal("Selasa, 20 Oktober 2026 10:15 WIB"), "2026-10-20T10:15:00+07:00")
        self.assertEqual(U.urai_tanggal("Mon, 19 Oct 2026 03:00:00 GMT"), "2026-10-19T03:00:00+00:00")
        self.assertEqual(U.urai_tanggal("2026-10-19T08:00:00Z"), "2026-10-19T08:00:00+00:00")
        self.assertEqual(U.urai_tanggal("2026-10-19 08:00:00"), "2026-10-19T08:00:00+07:00")  # tanpa zona = WIB
        self.assertEqual(U.urai_tanggal("bukan tanggal"), "")
        self.assertEqual(U.urai_tanggal(""), "")
        self.assertEqual(U.tanggal_gdelt("20261020001500"), "2026-10-20T00:15:00+00:00")
        self.assertEqual(U.tanggal_gdelt("2026"), "")

    def test_domain(self):
        self.assertEqual(U.host("https://WWW.AntaraNews.com:443/berita/1"), "antaranews.com")
        self.assertEqual(U.cocok_domain("ekonomi.bisnis.com", U.DOMAIN_ID), "bisnis.com")
        self.assertEqual(U.cocok_domain("bukanbisnis.com", U.DOMAIN_ID), "")
        self.assertEqual(U.cocok_domain("berita.pemda.go.id", ["kompas.com"]), "")
        self.assertEqual(U.cocok_domain("berita.pemda.go.id", ["kompas.com"], semua_id=True), "berita.pemda.go.id")
        self.assertEqual(U.daftar_domain({"domain": "Kompas.com", "domain_tambah": "tempo.co"}), ["kompas.com", "tempo.co"])
        with self.assertRaises(ValueError):
            U.daftar_domain({"domain": "x'; DROP"})
        self.assertEqual(U.bahasa_baku("id-ID"), "id")
        self.assertEqual(U.bahasa_baku("ind"), "id")

    def test_robots(self):
        txt = ("User-agent: *\nDisallow: /search\n\nUser-agent: LigaLakehouse-penelitian\nDisallow: /rahasia/\n"
               "\nUser-agent: GPTBot\nDisallow: /\n")
        self.assertTrue(U.boleh_robots(txt, "https://contoh.id/rss/ekonomi.xml"))
        self.assertFalse(U.boleh_robots(txt, "https://contoh.id/rahasia/a"))
        self.assertTrue(U.boleh_robots(txt, "https://contoh.id/search"))  # grup khusus agen menggantikan grup *
        self.assertFalse(U.boleh_robots("User-agent: *\nDisallow: /\n", "https://contoh.id/rss"))
        self.assertTrue(U.boleh_robots("", "https://contoh.id/rss"))


# ---------------------------------------------------------------------------------------------------
# RSS
# ---------------------------------------------------------------------------------------------------

class TestRss(unittest.TestCase):
    def test_rss2(self):
        f = rss.urai_feed(RSS2)
        self.assertEqual((f["jenis"], f["bahasa"], len(f["butir"])), ("rss", "id-ID", 3))
        rows = rss.baris_rss(f, "antara_ekonomi")
        self.assertEqual(len(rows), 2)  # butir tanpa tautan dibuang
        a, b = rows
        self.assertEqual(a["url"], "https://www.antaranews.com/berita/1/bps-inflasi")
        self.assertEqual(a["tanggal_terbit"], "2026-10-20T10:15:00+07:00")
        self.assertEqual(a["media"], "antaranews.com")
        self.assertEqual(a["bahasa"], "id")
        self.assertEqual(a["ringkasan"], "Jakarta (ANTARA) - Badan Pusat Statistik (BPS) mencatat inflasi 2,1 persen. "
                                         "Angka itu turun dari bulan lalu.")
        self.assertNotIn("tidak boleh disimpan", json.dumps(rows))
        self.assertEqual((b["judul"], b["media"], b["tanggal_terbit"]), ("Ekspor & impor", "bisnis.com", "2026-10-19T08:00:00+00:00"))
        self.assertEqual(b["ringkasan"], "Ekspor naik. Impor turun!")
        self.assertEqual({r["sumber_penemuan"] for r in rows}, {"rss"})

    def test_atom(self):
        f = rss.urai_feed(ATOM)
        self.assertEqual((f["jenis"], f["bahasa"]), ("atom", "id"))
        (r,) = rss.baris_rss(f, "x")
        self.assertEqual(r["url"], "https://www.kompas.com/read/3")
        self.assertEqual(r["judul"], "Kemiskinan turun")
        self.assertEqual(r["tanggal_terbit"], "2026-10-18T07:30:00+07:00")  # published didahulukan
        self.assertEqual(r["ringkasan"], "Persentase penduduk miskin turun. Data BPS Maret 2026.")
        self.assertNotIn("TEKS PENUH", json.dumps(r))

    def test_bersihkan_feed_membuang_teks_penuh(self):
        bersih = rss.bersihkan_feed(RSS2)
        self.assertIsNotNone(bersih)
        self.assertNotIn(b"tidak boleh disimpan", bersih)
        self.assertIn(b"img.antaranews.com", bersih)  # media:content (gambar) tetap
        self.assertEqual(rss.baris_rss(rss.urai_feed(bersih), "k"), rss.baris_rss(rss.urai_feed(RSS2), "k"))
        self.assertNotIn(b"TEKS PENUH", rss.bersihkan_feed(ATOM))
        pendek = b"<rss><channel><item><link>https://a.id/1</link><description>Pendek.</description></item></channel></rss>"
        self.assertIsNone(rss.bersihkan_feed(pendek))
        panjang = f"<rss><channel><item><link>https://a.id/1</link><description>{TEKS_PANJANG}</description></item></channel></rss>"
        b = rss.bersihkan_feed(panjang.encode())
        self.assertLess(len(b), 700)

    def test_pilih_feed(self):
        self.assertEqual(list(rss.pilih_feed({"feed": "cnn_ekonomi"})), ["cnn_ekonomi"])
        f = rss.pilih_feed({"feed_tambah": "tempo_bisnis|https://rss.tempo.co/bisnis"})
        self.assertEqual(f["tempo_bisnis"]["url"], "https://rss.tempo.co/bisnis")
        with self.assertRaises(ValueError):
            rss.pilih_feed({"feed": "tidak_ada"})
        self.assertTrue(all(v["url"].startswith("https://") and v["catatan"] for v in rss.FEED.values()))


# ---------------------------------------------------------------------------------------------------
# GDELT
# ---------------------------------------------------------------------------------------------------

def baris_gkg(rid="20261020001500-T1", tanggal="20261020001500", sumber="antaranews.com",
              url="https://www.antaranews.com/berita/9", tema="WB_697_SOCIAL_PROTECTION,10;ECON_INFLATION,40;WB_697_SOCIAL_PROTECTION,90",
              info="srclc:ind;eng:GT-IND 1.0") -> str:
    k = [""] * 27
    k[0], k[1], k[2], k[3], k[4] = rid, tanggal, "1", sumber, url
    k[7] = "WB_697_SOCIAL_PROTECTION;ECON_INFLATION"
    k[8] = tema
    k[12] = "Amalia Widyasanti,120"           # nama orang: tidak boleh ikut tersimpan
    k[22] = "45|80||inflasi turun dua persen"  # kutipan: tidak boleh ikut tersimpan
    k[25] = info
    return "\t".join(k)


class TestGdelt(unittest.TestCase):
    def test_kolom_gkg(self):
        self.assertEqual(len(gdelt.KOLOM_GKG), 27)
        self.assertEqual([gdelt.I[k] for k in ("GKGRECORDID", "DATE", "SourceCommonName", "DocumentIdentifier",
                                               "V2Themes", "TranslationInfo")], [0, 1, 3, 4, 8, 25])

    def test_sql_bq(self):
        sql, p = gdelt.sql_bq("2026-10-01", "2026-10-07", ["kompas.com", "Antaranews.com"], ["WB_", "POVERTY"])
        self.assertIn("`gdelt-bq.gdeltv2.gkg_partitioned`", sql)
        self.assertIn("_PARTITIONTIME >= TIMESTAMP(@mulai)", sql)
        self.assertIn("TIMESTAMP_ADD(TIMESTAMP(@sampai), INTERVAL 1 DAY)", sql)
        self.assertIn("IN UNNEST(@domain)", sql)
        self.assertIn("REGEXP_CONTAINS(V2Themes, @pola_tema)", sql)
        self.assertIn("SUBSTR(V2Themes, 1, 2000)", sql)
        for dilarang in ("Persons", "Quotations", "GCAM", "AllNames", "SELECT *"):
            self.assertNotIn(dilarang, sql)
        self.assertNotIn("kompas.com", sql)  # nilai lewat parameter, bukan teks SQL
        self.assertEqual(p["domain"], ["antaranews.com", "kompas.com"])
        self.assertEqual(p["pola_tema"], "(?:^|;)(?:WB_|POVERTY)")
        sql2, p2 = gdelt.sql_bq("2026-10-01", "2026-10-01", ["kompas.com"], semua_id=True)
        self.assertNotIn("pola_tema", p2)
        self.assertNotIn("REGEXP_CONTAINS", sql2)
        self.assertIn("ENDS_WITH(LOWER(SourceCommonName), '.id')", sql2)
        for salah in (("2026-10-07", "2026-10-01"), ("2026/10/01", "2026-10-02")):
            with self.assertRaises(ValueError):
                gdelt.sql_bq(*salah, ["kompas.com"])
        with self.assertRaises(ValueError):
            gdelt.daftar_tema("WB_;DROP")
        self.assertEqual(gdelt.daftar_tema("bawaan"), list(gdelt.TEMA_BAWAAN))

    def test_taksiran(self):
        self.assertFalse(gdelt.taksiran(4_900_000_000, 5)["melebihi"])
        self.assertTrue(gdelt.taksiran(5_100_000_000, 5)["melebihi"])

    def test_saring_baris_dan_csv(self):
        dom = ["antaranews.com", "bisnis.com"]
        csv_ = "\n".join([baris_gkg(), baris_gkg(rid="b", sumber="nytimes.com", url="https://nytimes.com/x"),
                          baris_gkg(rid="c", sumber="", url="https://ekonomi.bisnis.com/read/1", tema="TAX_FNCACT,3"),
                          "baris\tpendek"]) + "\n"
        rows = gdelt.saring_csv_gkg(io.StringIO(csv_), dom)
        self.assertEqual([r["GKGRECORDID"] for r in rows], ["20261020001500-T1", "c"])
        self.assertEqual(set(rows[0]), set(gdelt.KOLOM_SIMPAN))
        self.assertNotIn("Amalia", json.dumps(rows))
        self.assertNotIn("inflasi turun", json.dumps(rows))
        pola = gdelt.pola_tema(["ECON_"])
        self.assertEqual([r["GKGRECORDID"] for r in gdelt.saring_csv_gkg(io.StringIO(csv_), dom, pola=pola)],
                         ["20261020001500-T1"])

    def test_baris_artikel(self):
        r = gdelt.saring_baris_gkg(baris_gkg().split("\t"), ["antaranews.com"])
        a = gdelt.baris_artikel(r, "translation")
        self.assertEqual(a["url"], "https://www.antaranews.com/berita/9")
        self.assertEqual(a["judul"], "")
        self.assertEqual(a["tanggal_terbit"], "2026-10-20T00:15:00+00:00")
        self.assertEqual((a["media"], a["bahasa"], a["sumber_penemuan"]), ("antaranews.com", "id", "gdelt"))
        self.assertEqual(a["tema"], "WB_697_SOCIAL_PROTECTION;ECON_INFLATION")
        self.assertEqual(gdelt.bahasa_gdelt(""), "en")
        tema = ";".join(f"WB_{i:04d}_TEMA_PANJANG,{i}" for i in range(400))
        self.assertLessEqual(len(gdelt.tema_ringkas(tema)), U.PANJANG_TEMA)
        self.assertTrue(gdelt.tema_ringkas(tema).endswith("_TEMA_PANJANG"))

    def test_master_dan_langsung(self):
        master = ["1234 0123456789abcdef0123456789abcdef http://data.gdeltproject.org/gdeltv2/20261019234500.gkg.csv.zip",
                  "99 aa http://data.gdeltproject.org/gdeltv2/20261020000000.export.CSV.zip",
                  "5678 fedcba9876543210fedcba9876543210 http://data.gdeltproject.org/gdeltv2/20261020000000.translation.gkg.csv.zip",
                  "rusak"]
        d = gdelt.urai_master(master, "2026-10-20", "2026-10-20")
        self.assertEqual([(x["waktu"], x["aliran"], x["bita"]) for x in d], [("20261020000000", "translation", 5678)])
        l = gdelt.berkas_langsung("2026-10-20", "2026-10-20", "english")
        self.assertEqual(len(l), 96)
        self.assertEqual(l[1]["url"], "https://data.gdeltproject.org/gdeltv2/20261020001500.gkg.csv.zip")
        # URL http:// di masterfilelist dinormalkan ke https:// (GDELT mengalihkan 301 sejak Okt 2026)
        self.assertEqual(d[0]["url"], "https://data.gdeltproject.org/gdeltv2/20261020000000.translation.gkg.csv.zip")


# ---------------------------------------------------------------------------------------------------
# CC-NEWS / WARC
# ---------------------------------------------------------------------------------------------------

def rekaman_warc(jenis: str, uri: str, blok: bytes, tanggal="2026-10-01T01:02:03Z") -> bytes:
    h = (f"WARC/1.0\r\nWARC-Type: {jenis}\r\nWARC-Target-URI: {uri}\r\nWARC-Date: {tanggal}\r\n"
         f"WARC-Record-ID: <urn:uuid:{hashlib.md5(uri.encode()).hexdigest()}>\r\n"
         f"Content-Type: application/http; msgtype={jenis}\r\nContent-Length: {len(blok)}\r\n\r\n").encode()
    return gzip.compress(h + blok + b"\r\n\r\n")  # satu anggota gzip per rekaman, seperti WARC Common Crawl


def respons_http(html: bytes, tipe="text/html; charset=utf-8") -> bytes:
    return (f"HTTP/1.1 200 OK\r\nContent-Type: {tipe}\r\nContent-Length: {len(html)}\r\n\r\n").encode() + html


HTML_ANTARA = (b'<!doctype html><html lang="id-ID"><head><meta charset="utf-8"><title>BPS: Inflasi &amp; '
               b'harga pangan | ANTARA</title></head><body>' + TEKS_PANJANG.encode() * 30 + b"</body></html>")
HTML_JUDUL_PANJANG = b"<html><head><title>" + b"judul " * 200 + b"</title></head></html>"
WARC = b"".join([
    gzip.compress(b"WARC/1.0\r\nWARC-Type: warcinfo\r\nContent-Length: 7\r\n\r\nsoftwar\r\n\r\n"),
    rekaman_warc("request", "https://www.antaranews.com/berita/1", b"GET /berita/1 HTTP/1.1\r\n\r\n"),
    rekaman_warc("response", "https://www.antaranews.com/berita/1", respons_http(HTML_ANTARA)),
    rekaman_warc("response", "https://www.nytimes.com/x", respons_http(b"<title>NYT</title>")),
    rekaman_warc("response", "https://www.tempo.co/y", respons_http(HTML_JUDUL_PANJANG, "text/html")),
    rekaman_warc("response", "https://www.kompas.com/z.jpg", respons_http(b"\xff\xd8\xff", "image/jpeg")),
])
DOMAIN = ["antaranews.com", "tempo.co", "kompas.com"]


class TestWarc(unittest.TestCase):
    def test_baca_warc_minimal(self):
        rek = [(h["warc-type"], h.get("warc-target-uri")) for h, _ in ccnews.baca_warc(gzip.GzipFile(fileobj=io.BytesIO(WARC)))]
        self.assertEqual([r[0] for r in rek], ["warcinfo", "request", "response", "response", "response", "response"])

    def test_rekaman_minimal_dan_hash(self):
        potongan = [WARC[i:i + 97] for i in range(0, len(WARC), 97)]
        aliran = ccnews.AliranHash(potongan)
        rows = list(ccnews.rekaman_minimal(io.BufferedReader(aliran, 4096), DOMAIN))
        aliran.habiskan()
        self.assertEqual((aliran.sha.hexdigest(), aliran.bita), (hashlib.sha256(WARC).hexdigest(), len(WARC)))
        self.assertEqual([r["url"] for r in rows], ["https://www.antaranews.com/berita/1", "https://www.tempo.co/y",
                                                    "https://www.kompas.com/z.jpg"])
        a = rows[0]
        self.assertEqual((a["judul"], a["bahasa_html"], a["status_http"], a["tipe_konten"]),
                         ("BPS: Inflasi & harga pangan | ANTARA", "id-ID", 200, "text/html"))
        self.assertEqual(a["warc_date"], "2026-10-01T01:02:03Z")
        self.assertEqual(a["content_length_http"], str(len(HTML_ANTARA)))
        self.assertNotIn("tidak boleh disimpan", json.dumps(rows))
        self.assertLessEqual(len(rows[1]["judul"]), U.PANJANG_JUDUL)
        self.assertEqual(rows[2]["judul"], "")  # bukan HTML
        b = ccnews.baris_artikel(a, "CC-NEWS-20261001010203-00001")
        self.assertEqual((b["tanggal_terbit"], b["media"], b["bahasa"], b["sumber_penemuan"]),
                         ("2026-10-01T01:02:03+00:00", "antaranews.com", "id", "ccnews"))

    @unittest.skipUnless(ccnews.pilih_pembaca() == "warcio", "warcio tidak terpasang")
    def test_warcio_sama_dengan_minimal(self):
        self.assertEqual(list(ccnews.rekaman_warcio(io.BytesIO(WARC), DOMAIN)),
                         list(ccnews.rekaman_minimal(io.BytesIO(WARC), DOMAIN)))

    def test_paths_dan_pilih(self):
        p = ["crawl-data/CC-NEWS/2026/10/CC-NEWS-20261001010203-00001.warc.gz",
             "crawl-data/CC-NEWS/2026/10/CC-NEWS-20261002030405-00002.warc.gz",
             "crawl-data/CC-NEWS/2026/10/CC-NEWS-20261002230405-00003.warc.gz"]
        self.assertEqual(ccnews.urai_paths(gzip.compress(("\n".join(p) + "\n").encode())), p)
        self.assertEqual(ccnews.pilih_warc(p, hari="2026-10-02", maks=5), p[1:])
        self.assertEqual(ccnews.pilih_warc(p, berkas=["CC-NEWS-20261002230405-00003.warc.gz"]), p[2:])
        self.assertEqual(ccnews.pilih_warc(p), p[:1])
        self.assertEqual(ccnews.waktu_warc(p[0]), "2026-10-01T01:02:03+00:00")
        self.assertEqual(ccnews.url_paths("2026-10"),
                         "https://data.commoncrawl.org/crawl-data/CC-NEWS/2026/10/warc.paths.gz")
        with self.assertRaises(ValueError):
            ccnews.url_paths("2026-1")


# ---------------------------------------------------------------------------------------------------
# Kebijakan simpan: tidak ada kolom Bronze panjang selain tema
# ---------------------------------------------------------------------------------------------------

class TestKebijakanSimpan(unittest.TestCase):
    def semua_baris(self) -> list[dict]:
        rows = rss.baris_rss(rss.urai_feed(RSS2), "a") + rss.baris_rss(rss.urai_feed(ATOM), "b")
        tema = ";".join(f"WB_{i:04d}_X,{i}" for i in range(500))
        gkg = gdelt.saring_csv_gkg(io.StringIO(baris_gkg(tema=tema) + "\n"), ["antaranews.com"])
        rows += gdelt.baris_bronze(gkg, "translation")
        rows += ccnews.baris_bronze(list(ccnews.rekaman_minimal(io.BytesIO(WARC), DOMAIN)), "w")
        return rows

    def test_tidak_ada_kolom_panjang(self):
        rows = self.semua_baris()
        self.assertEqual({r["sumber_penemuan"] for r in rows}, {"rss", "gdelt", "ccnews"})
        for r in rows:
            for k, v in r.items():
                if k != "tema":
                    self.assertLessEqual(len(str(v)), 600, f"{r['sumber_penemuan']}.{k}")
        self.assertTrue(any(len(r.get("tema", "")) > 600 for r in rows))  # tema boleh panjang, tetap dibatasi
        self.assertTrue(all(len(r.get("tema", "")) <= U.PANJANG_TEMA for r in rows))

    def test_penjaga_menolak_teks_artikel(self):
        with self.assertRaises(ValueError):
            U.periksa_panjang([{"url": "https://a.id", "ringkasan": TEKS_PANJANG}])
        U.periksa_panjang([{"url": "https://a.id/" + "x" * 900, "tema": "T" * 900}])


# ---------------------------------------------------------------------------------------------------
# Jalan konektor dengan HTTP palsu, lalu bangun ulang Bronze dari raw dan manifest
# ---------------------------------------------------------------------------------------------------

class Respons:
    def __init__(self, isi: bytes, status: int = 200):
        self.content, self.status_code, self.headers = isi, status, {"Content-Length": str(len(isi))}

    def iter_content(self, n):
        for i in range(0, len(self.content), 257):  # potongan kecil agar aliran benar-benar bertahap
            yield self.content[i:i + 257]


class HttpPalsu:
    peta: dict = {}
    diminta: list = []

    def __init__(self, *a, **kw):
        pass

    def get(self, url, params=None, stream=False, **kw):
        HttpPalsu.diminta.append(url)
        if url not in self.peta:
            raise AssertionError(f"URL tak terduga: {url}")
        return Respons(self.peta[url])

    def head(self, url, **kw):
        return Respons(self.peta[url])


def zip_gkg(nama: str, teks: str) -> bytes:
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(nama, teks)
    return b.getvalue()


class TestJalanDanUlang(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        self.kw = {"raw": d / "raw", "manifest_dir": d / "man", "bronze": d / "bronze"}
        HttpPalsu.diminta = []

    def tearDown(self):
        self.tmp.cleanup()

    def ulang(self, snap):
        p = snap.selesai()
        h = bangun_ulang(p, self.kw["bronze"].parent / "bronze_ulang", self.kw["raw"])
        self.assertEqual(h["beda"], {})
        return json.loads(p.read_text("utf-8")), h

    def test_rss(self):
        HttpPalsu.peta = {"https://www.antaranews.com/robots.txt": b"User-agent: *\nDisallow: /search\n",
                          "https://www.cnnindonesia.com/robots.txt": b"User-agent: *\nDisallow: /ekonomi/\n",
                          rss.FEED["antara_ekonomi"]["url"]: RSS2, rss.FEED["cnn_ekonomi"]["url"]: ATOM}
        snap = inti.Snapshot("rss", "2026-10-20", **self.kw)
        with mock.patch.object(inti, "Http", HttpPalsu):
            r = rss.jalankan(snap, {"feed": "antara_ekonomi,cnn_ekonomi"})
            self.assertEqual(r["feed"], {"antara_ekonomi": 2, "cnn_ekonomi": "robots"})
            self.assertNotIn(rss.FEED["cnn_ekonomi"]["url"], HttpPalsu.diminta)
            nama = next(n for n in snap.berkas if n.startswith("feed/"))
            self.assertEqual(snap.berkas[nama]["disimpan"], "ekstrak")  # content:encoded dibuang dari raw
            self.assertEqual(snap.berkas[nama]["sha256_asli"], inti.sha256_bita(RSS2))
            self.assertNotIn(b"tidak boleh disimpan", (snap.folder / nama).read_bytes())
            self.assertIn(f"rss:antara_ekonomi@{inti.sha256_bita(RSS2)[:12]}", snap.rilis)
            m, h = self.ulang(snap)
            self.assertEqual(h["tabel"], {"artikel": 2})
            self.assertEqual(m["kelas_lisensi"], "C")
            self.assertFalse(m["boleh_tayang"])
            # jalan kedua hari yang sama: payload sama dilewati, manifest dilanjutkan
            snap2 = inti.Snapshot("rss", "2026-10-20", **self.kw)
            r2 = rss.jalankan(snap2, {"feed": "antara_ekonomi", "robots": "0"})
            self.assertEqual(r2["feed"], {"antara_ekonomi": "tidak berubah"})
            self.assertEqual(snap2.bronze_tabel["artikel"]["baris"], 2)

    def test_gdelt_berkas(self):
        w1, w2 = "20261020000000", "20261020001500"
        z1 = zip_gkg(f"{w1}.translation.gkg.csv", "\n".join([baris_gkg(rid="a"), baris_gkg(rid="b", sumber="lain.com",
                                                                                             url="https://lain.com/1")]) + "\n")
        z2 = zip_gkg(f"{w2}.translation.gkg.csv", baris_gkg(rid="c", tanggal=w2) + "\n")
        u1, u2 = (f"{gdelt.DATA}/{w}.translation.gkg.csv.zip" for w in (w1, w2))
        master = (f"{len(z1)} {hashlib.md5(z1).hexdigest()} {u1}\n{len(z2)} {'0' * 32} {u2}\n"
                  f"10 {'1' * 32} {gdelt.DATA}/20261021000000.translation.gkg.csv.zip\n").encode()
        HttpPalsu.peta = {gdelt.MASTER["translation"]: master, u1: z1, u2: z2}
        snap = inti.Snapshot("gdelt", "2026-10-21", **self.kw)
        with mock.patch.object(inti, "Http", HttpPalsu):
            r = gdelt.jalankan(snap, {"jalur": "berkas", "mulai": "2026-10-20", "sampai": "2026-10-20",
                                      "domain": "antaranews.com"})
        self.assertEqual(r, {"hari": 1, "artikel": 1, "berkas_gagal": 1})  # z2: md5 beda dari masterfilelist
        b = snap.berkas["gkg/translation/20261020.jsonl"]
        self.assertEqual((b["disimpan"], b["bita_asli"]), ("ekstrak", len(z1)))
        self.assertEqual(b["asal"], [f"{w1} {inti.sha256_bita(z1)} {len(z1)}"])
        self.assertEqual(snap.berkas["master/translation-2026-10-20_2026-10-20.txt"]["sha256_asli"], inti.sha256_bita(master))
        self.assertEqual(len(snap.galat), 1)
        rid = next(iter(snap.rilis.values()))
        self.assertEqual((rid["jenis_bukti_tanggal"], rid["tanggal_rilis"]), ("pembaruan_sumber", "2026-10-20T00:00:00+00:00"))
        m, h = self.ulang(snap)
        self.assertEqual(h["tabel"], {"artikel": 1})
        self.assertEqual(m["kelas_lisensi"], "A")
        self.assertFalse(m["boleh_tayang"])  # metadata berita tidak ditayangkan walau kelas A

    def test_gdelt_berkas_paralel_sama_dengan_berurutan(self):
        """``pekerja=4`` memberi ekstrak, asal, galat, dan rilis yang sama dengan jalan berurutan."""
        waktu = [f"20261020{j:02d}{m:02d}00" for j in range(2) for m in (0, 15, 30, 45)]
        zips = {w: zip_gkg(f"{w}.translation.gkg.csv", baris_gkg(rid=w, tanggal=w) + "\n") for w in waktu}
        url = {w: f"{gdelt.DATA}/{w}.translation.gkg.csv.zip" for w in waktu}
        rusak = waktu[3]  # md5 di daftar sengaja salah
        master = "".join(f"{len(z)} {'0' * 32 if w == rusak else hashlib.md5(z).hexdigest()} {url[w]}\n"
                         for w, z in zips.items()).encode()
        HttpPalsu.peta = {gdelt.MASTER["translation"]: master} | {url[w]: z for w, z in zips.items()}
        hasil = {}
        for p in ("1", "4"):
            d = Path(self.tmp.name) / f"p{p}"
            kw = {"raw": d / "raw", "manifest_dir": d / "man", "bronze": d / "bronze"}
            snap = inti.Snapshot("gdelt", "2026-10-21", **kw)
            with mock.patch.object(inti, "Http", HttpPalsu):
                r = gdelt.jalankan(snap, {"jalur": "berkas", "mulai": "2026-10-20", "sampai": "2026-10-20",
                                          "domain": "antaranews.com", "pekerja": p, "jeda_s": "0"})
            b = snap.berkas["gkg/translation/20261020.jsonl"]
            hasil[p] = (r, b["sha256_asli"], b["asal"], b["gagal"], sorted(snap.rilis),
                        (snap.folder / "gkg/translation/20261020.jsonl").read_bytes())
        self.assertEqual(hasil["1"], hasil["4"])
        self.assertEqual(hasil["4"][0], {"hari": 1, "artikel": 7, "berkas_gagal": 1})
        self.assertEqual(hasil["4"][3], [rusak])
        with mock.patch.object(inti, "Http", HttpPalsu), self.assertRaises(ValueError):
            gdelt.jalankan(inti.Snapshot("gdelt", "2026-10-21", **self.kw),
                           {"jalur": "berkas", "mulai": "2026-10-20", "sampai": "2026-10-20", "pekerja": "17"})

    def test_gdelt_bq_tanpa_paket(self):
        snap = inti.Snapshot("gdelt", "2026-10-21", **self.kw)
        with mock.patch.dict("sys.modules", {"google": None, "google.cloud": None}):
            with self.assertRaises(RuntimeError) as c:
                gdelt.jalankan(snap, {"jalur": "bq", "mulai": "2026-10-20", "sampai": "2026-10-20"})
        self.assertIn("google-cloud-bigquery", str(c.exception))

    def test_gdelt_bq_dengan_klien_palsu(self):
        """Jalur bq: dry run menolak kueri di atas maks_gb sebelum kueri sebenarnya dijalankan."""
        dijalankan = []

        class Job:
            def __init__(self, cfg):
                self.total_bytes_processed = 7_000_000_000 if cfg.dry_run else 4_000_000_000
                self.total_bytes_billed, self.job_id = self.total_bytes_processed, "job-1"

            def result(self):
                return [{"GKGRECORDID": "x", "DATE": 20261020001500, "SourceCommonName": "antaranews.com",
                         "DocumentIdentifier": "https://www.antaranews.com/b/1", "V2Themes": "WB_1,2",
                         "TranslationInfo": None}]

        class Klien:
            def __init__(self, project=None):
                pass

            def query(self, sql, job_config):
                dijalankan.append(job_config.dry_run)
                return Job(job_config)

        class Cfg:
            def __init__(self, dry_run=False, **kw):
                self.dry_run, self.kw = dry_run, kw

        bq = mock.MagicMock(Client=Klien, QueryJobConfig=Cfg)
        cloud = mock.MagicMock(bigquery=bq)
        with mock.patch.dict("sys.modules", {"google": mock.MagicMock(cloud=cloud), "google.cloud": cloud,
                                             "google.cloud.bigquery": bq}):
            snap = inti.Snapshot("gdelt", "2026-10-21", **self.kw)
            with self.assertRaises(RuntimeError):
                gdelt.jalankan(snap, {"mulai": "2026-10-20", "sampai": "2026-10-20"})
            self.assertEqual(dijalankan, [True])  # hanya dry run
            snap = inti.Snapshot("gdelt", "2026-10-21", **self.kw)
            r = gdelt.jalankan(snap, {"mulai": "2026-10-20", "sampai": "2026-10-20", "maks_gb": "8", "lanjut": "0"})
        self.assertEqual(r["artikel"], 1)
        self.assertIn("bq/2026-10-20_2026-10-20.sql", snap.berkas)
        self.ulang(snap)

    def test_ccnews(self):
        path = "crawl-data/CC-NEWS/2026/10/CC-NEWS-20261001010203-00001.warc.gz"
        HttpPalsu.peta = {ccnews.url_paths("2026-10"): gzip.compress((path + "\n").encode()),
                          f"{ccnews.DASAR}/{path}": WARC}
        snap = inti.Snapshot("ccnews", "2026-10-21", **self.kw)
        with mock.patch.object(inti, "Http", HttpPalsu):
            r = ccnews.jalankan(snap, {"bulan": "2026-10", "domain": ",".join(DOMAIN), "pembaca": "minimal"})
            self.assertEqual(r, {"warc": 1, "artikel": 3})
            b = snap.berkas["warc/CC-NEWS-20261001010203-00001.jsonl"]
            self.assertEqual((b["sha256_asli"], b["bita_asli"], b["disimpan"]), (inti.sha256_bita(WARC), len(WARC), "ekstrak"))
            self.assertNotIn(b"tidak boleh disimpan", (snap.folder / "warc/CC-NEWS-20261001010203-00001.jsonl").read_bytes())
            m, h = self.ulang(snap)
            self.assertEqual(h["tabel"], {"artikel": 3})
            # batas biaya: WARC 1 bita di atas batas ditolak sebelum diunduh
            snap2 = inti.Snapshot("ccnews", "2026-10-22", **self.kw)
            with self.assertRaises(RuntimeError):
                ccnews.jalankan(snap2, {"bulan": "2026-10", "maks_gb": str((len(WARC) - 1) / 1e9)})


if __name__ == "__main__":
    unittest.main()
