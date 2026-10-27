"""Uji data rujukan dp_referensi (brief 4 M1): kasus kode Papua, SIGN-SMART, dan dimensi wilayah tipe 2."""
from __future__ import annotations

import csv
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from sdg_gudang import referensi as R


class TestRujukanWilayah(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        wilayah = R.bangun_wilayah()
        padanan = R.bangun_padanan()
        cls.ruj = R.Rujukan(wilayah, padanan, R.bangun_alias(wilayah, padanan))

    def test_38_provinsi_terkini_dengan_kode_unik(self):
        terkini = [w for w in self.ruj.wilayah if w["terkini"] and w["tingkat"] == "provinsi"]
        self.assertEqual(len(terkini), 38)
        for kolom in ("wilayah_kode", "kode_iso", "kode_kemendagri"):
            self.assertEqual(len({w[kolom] for w in terkini}), 38, kolom)

    def test_kode_papua_bps_berbeda_dari_kemendagri(self):
        # BPS 94 = Papua = Kemendagri 91; BPS 91 = Papua Barat = Kemendagri 92.
        r = self.ruj
        self.assertEqual(r.dari_bps("94"), 9400)
        self.assertEqual(r.dari_kemendagri("91"), 9400)
        self.assertEqual(r.dari_bps("91"), 9100)
        self.assertEqual(r.dari_kemendagri("92"), 9100)
        self.assertNotEqual(r.dari_bps("91"), r.dari_kemendagri("91"))
        for buruk in ("-", "", "NASIONAL", "9a"):
            with self.assertRaises(R.KodeTidakDikenal):
                r.dari_bps(buruk)
        h = r.periksa_batch("bps", ["-", "11"])
        self.assertEqual(h["tidak_dikenal"], ["-"])

    def test_kode_kemendagri_papua_barat_daya_berubah_antarperiode(self):
        r = self.ruj
        # 2023_1.2022 dan 2024_1.2022: Papua Barat dan Papua Barat Daya sama-sama Kemendagri 92.
        with self.assertRaises(R.KodeAmbigu):
            r.dari_kemendagri("92", periode="2024_1.2022")
        with self.assertRaises(R.KodeTidakDikenal):
            r.dari_kemendagri("96", periode="2024_1.2022")
        # mulai 2025_1.2025 Papua Barat Daya = Kemendagri 96
        self.assertEqual(r.dari_kemendagri("96"), 9200)
        self.assertEqual(r.dari_kemendagri("96", periode="2025_1.2025"), 9200)
        ambigu = {(p["periode"], p["kode_bps"]) for p in r.padanan if p["ambigu_kemendagri"]}
        self.assertEqual(ambigu, {("2023_1.2022", "91"), ("2023_1.2022", "92"),
                                  ("2024_1.2022", "91"), ("2024_1.2022", "92")})

    def test_signsmart_kode_id_ac_ganda_dikarantina(self):
        # Tiruan keluaran SIGN-SMART: 34 provinsi lama berkode ISO benar, empat provinsi Papua baru
        # semuanya berkode ID-AC (sama dengan Aceh).
        baru = {9200, 9500, 9600, 9700}
        iso = [w["kode_iso"] for w in self.ruj.wilayah if w["terkini"] and w["tingkat"] == "provinsi"
               and w["wilayah_kode"] not in baru]
        batch = iso + ["ID-AC"] * 4
        self.assertEqual(len(batch), 38)
        h = self.ruj.periksa_batch("iso3166_2", batch)
        self.assertEqual(h["duplikat"], {"ID-AC": 5})
        self.assertNotIn("ID-AC", h["cocok"])
        self.assertEqual(h["hilang"], sorted(baru | {1100}))  # Aceh ikut hilang karena kuncinya dikarantina
        self.assertEqual(len(h["cocok"]), 33)
        self.assertEqual(h["tidak_dikenal"], [])

    def test_kode_prov_geojson_tidak_unik_tetapi_nama_terpetakan(self):
        geo = json.loads(R.GEOJSON.read_text("utf-8"))
        kode_prov = Counter(f["properties"]["KODE_PROV"] for f in geo["features"])
        self.assertEqual((kode_prov["91"], kode_prov["92"]), (4, 2))
        alias = json.loads(R.KONTRAK_V3.read_text("utf-8"))["wilayah_geojson"]
        hasil = set()
        for f in geo["features"]:
            n = R.normal(f["properties"]["PROVINSI"])
            hasil.add(self.ruj.dari_nama(alias.get(n, n)))
        self.assertEqual(len(hasil), 38)

    def test_versi_asof_dan_kesebandingan(self):
        r = self.ruj
        self.assertEqual(r.versi_asof(9400, "2021-12-31")["versi"], 1)
        self.assertEqual(r.versi_asof(9400, "2022-07-25")["versi"], 2)
        self.assertFalse(r.sebanding(9400, "2021-12-31", "2023-12-31"))
        with self.assertRaises(R.KodeTidakDikenal):
            r.versi_asof(9500, "2021-12-31")
        self.assertEqual(r.versi_asof(9100, "2022-12-07")["versi"], 1)
        self.assertEqual(r.versi_asof(9100, "2022-12-08")["versi"], 2)
        self.assertEqual(r.versi_asof(6400, "2012-11-16")["versi"], 1)
        self.assertEqual(r.versi_asof(6400, "2012-11-17")["versi"], 2)
        self.assertTrue(r.sebanding(1800, "2000-12-31", "2025-12-31"))
        self.assertTrue(r.sebanding(R.NAS, "1990-01-01", "2026-01-01"))


class TestIndikatorSatuanKg(unittest.TestCase):
    def test_kg_lulus_shacl_dan_memuat_pemekaran(self):
        import rdflib

        g = R.bangun_kg(R.bangun_wilayah(), R.bangun_indikator())
        ok, laporan = R.validasi_kg(g)
        self.assertTrue(ok, laporan)
        LK = rdflib.Namespace(R.NS_KG + "ontologi#")
        WIL = rdflib.Namespace(R.NS_KG + "wilayah/")
        self.assertIn((WIL["9500/v1"], LK.pecahanDari, WIL["9400/v1"]), g)
        self.assertIn((WIL["9200/v1"], LK.pecahanDari, WIL["9100/v1"]), g)
        self.assertIn((WIL["9400/v2"], LK.menggantikan, WIL["9400/v1"]), g)

    def test_pilar_mengikuti_permen_dan_mencakup_17_tujuan(self):
        tujuan = sorted(t for _, ts in R.PILAR.values() for t in ts)
        self.assertEqual(tujuan, list(range(1, 18)))
        for r in R.bangun_indikator():
            self.assertEqual(r["pilar"], R.PILAR_TUJUAN[r["tujuan"]])

    def test_satuan_per_seribu_adalah_penyebut(self):
        s = R.satuan_dari_teks("per 1.000 kelahiran hidup")
        self.assertEqual((s.jenis, s.penyebut), ("rasio_per", 1000))
        _, pakai = R.bangun_satuan()
        self.assertTrue(all(p["satuan_id"] for p in pakai))

    def test_semua_tabel_gold_v3_terpetakan_tanpa_ambigu(self):
        peta = R.bangun_peta_tabel()
        self.assertEqual(len(peta), 76)
        for p in peta:
            self.assertNotIn(";", p["kode_tpb"], p["tabel"])
            self.assertTrue(p["kode_tpb"] or p["kode_global"] or p["hubungan"] == "bukan_indikator_tpb", p["tabel"])

    def test_bangun_deterministik(self):
        with tempfile.TemporaryDirectory() as d:
            a = R.bangun(Path(d) / "a")
            b = R.bangun(Path(d) / "b")
            self.assertEqual(a["berkas"], b["berkas"])
            self.assertTrue(a["shacl_lulus"])
            with (Path(d) / "a" / "dim_wilayah.csv").open(encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(sum(1 for r in rows if r["wilayah_kode"] in ("6400", "9100", "9400")), 6)


if __name__ == "__main__":
    unittest.main()
