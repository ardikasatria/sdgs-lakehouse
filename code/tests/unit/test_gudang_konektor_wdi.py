"""Uji luring konektor Bank Dunia (WDI dan arsip sumber 57) dengan cuplikan payload kecil."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sdg_gudang.akuisisi import inti
from sdg_gudang.akuisisi.konektor import wdi

HAL_WDI = [
    {"page": 1, "pages": 1, "per_page": 20000, "total": 2, "sourceid": None, "lastupdated": "2026-10-08"},
    [{"indicator": {"id": "SP.POP.TOTL", "value": "Population, total"}, "country": {"id": "ID", "value": "Indonesia"},
      "countryiso3code": "IDN", "date": "2025", "value": 285721236, "unit": "", "obs_status": "", "decimal": 0},
     {"indicator": {"id": "SI.POV.DDAY", "value": "Poverty headcount"}, "country": {"id": "ID", "value": "Indonesia"},
      "countryiso3code": "IDN", "date": "1960", "value": None, "scale": "", "unit": "", "obs_status": "", "decimal": 1}],
]

HAL_ARSIP = {"page": 1, "pages": 1, "per_page": 1000, "total": 2, "lastupdated": "2025-10-29", "source": {
    "id": "57", "name": "WDI Database Archives", "data": [
        {"variable": [{"concept": "Country", "id": "IDN", "value": "Indonesia"},
                      {"concept": "Time", "id": "YR1960", "value": "1960"},
                      {"concept": "Series", "id": "SP.POP.TOTL", "value": "Population, total"},
                      {"concept": "Version", "id": "202607", "value": "2026 Jul"}], "value": 88296070},
        {"variable": [{"concept": "Country", "id": "IDN", "value": "Indonesia"},
                      {"concept": "Time", "id": "YR1961", "value": "1961"},
                      {"concept": "Series", "id": "SP.POP.TOTL", "value": "Population, total"},
                      {"concept": "Version", "id": "202607", "value": "2026 Jul"}], "value": None}]}}

VERSI = {"page": 1, "pages": 1, "per_page": 500, "total": 3, "source": [{"id": "57", "name": "WDI Database Archives",
         "concept": [{"id": "version", "name": "version", "variable": [
             {"id": "198904", "value": "1989 Apr"}, {"id": "199309", "value": "1994 Sep"},
             {"id": "202607", "value": "2026 Jul"}]}]}]}

INDIKATOR = [{"page": 1, "pages": 1, "per_page": "2000", "total": 1},
             [{"id": "AG.LND.FRST.K2", "name": "Forest area (sq. km)", "unit": "",
               "source": {"id": "46", "value": "Sustainable Development Goals "}, "sourceNote": "x",
               "sourceOrganization": "FAO", "topics": [{"id": "1", "value": "Agriculture  "}, {"id": "6", "value": "Environment "}]}]]


class TestWdiMurni(unittest.TestCase):
    def test_baris_wdi_meratakan_objek_dan_mempertahankan_nilai_kosong(self):
        rows = wdi.baris_wdi(HAL_WDI)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["indicator_id"], "SP.POP.TOTL")
        self.assertEqual(rows[0]["country_value"], "Indonesia")
        self.assertEqual(rows[0]["value"], 285721236)
        self.assertIsNone(rows[1]["value"])
        self.assertEqual(wdi.meta_halaman(HAL_WDI)["lastupdated"], "2026-10-08")
        self.assertEqual(wdi.baris_wdi([{"page": 1}, None]), [])

    def test_baris_arsip_membuang_sel_kosong_dan_menghitung_sel(self):
        rows = wdi.baris_arsip(HAL_ARSIP)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0], {"country_id": "IDN", "country_value": "Indonesia", "time_id": "YR1960",
                                   "time_value": "1960", "series_id": "SP.POP.TOTL", "series_value": "Population, total",
                                   "version_id": "202607", "version_value": "2026 Jul", "value": 88296070})
        self.assertEqual(len(wdi.baris_arsip(HAL_ARSIP, buang_kosong=False)), 2)
        self.assertEqual(wdi.jumlah_sel(HAL_ARSIP), (2, 1))
        self.assertEqual(wdi.meta_halaman(HAL_ARSIP), {"page": 1, "pages": 1, "total": 2, "lastupdated": "2025-10-29"})

    def test_versi_dan_tanggal(self):
        v = wdi.urai_konsep(VERSI, "version")
        self.assertEqual([x["id"] for x in v], ["198904", "199309", "202607"])
        self.assertEqual(wdi.tanggal_versi("202607", "2026 Jul"), ("2026-07-01", ""))
        tgl, cat = wdi.tanggal_versi("199309", "1994 Sep")
        self.assertEqual(tgl, "1993-09-01")
        self.assertIn("tidak cocok", cat)
        with self.assertRaises(ValueError):
            wdi.tanggal_versi("2026")
        ids = [x["id"] for x in v]
        self.assertEqual(wdi.pilih_versi(ids, {"maks_versi": "2"}), ["199309", "202607"])
        self.assertEqual(wdi.pilih_versi(ids, {"dari": "199001", "sampai": "200001"}), ["199309"])
        self.assertEqual(wdi.pilih_versi(ids, {"versi": "202607,198904"}), ["198904", "202607"])
        with self.assertRaises(ValueError):
            wdi.pilih_versi(ids, {"versi": "200101"})

    def test_daftar_indikator(self):
        rows = wdi.urai_daftar_indikator(INDIKATOR)
        self.assertEqual(rows[0]["id"], "AG.LND.FRST.K2")
        self.assertEqual(rows[0]["source_id"], "46")
        self.assertEqual(rows[0]["topics"], "Agriculture; Environment")

    def test_kelompok_menghormati_batas_url_dan_jumlah(self):
        kode = [f"AB.CDE.{i:04d}" for i in range(100)]  # 11 karakter per kode
        kel = wdi.kelompokkan(kode, "x" * 100, "y" * 100, maks_url=500, maks_n=60)
        self.assertEqual(sum(len(k) for k in kel), 100)
        self.assertEqual([c for k in kel for c in k], kode)
        for k in kel:
            self.assertLessEqual(200 + len(";".join(k)), 500)
        self.assertEqual(max(len(k) for k in wdi.kelompokkan(kode, "", "", maks_url=10_000, maks_n=60)), 60)

    def test_tar_deterministik_dan_dapat_dibaca(self):
        a = wdi.tar_deterministik([("k1.json", b'{"a":1}'), ("k2.json", b"[]")])
        b = wdi.tar_deterministik([("k1.json", b'{"a":1}'), ("k2.json", b"[]")])
        self.assertEqual(inti.sha256_bita(a), inti.sha256_bita(b))
        self.assertEqual(wdi.baca_tar(a), {"k1.json": b'{"a":1}', "k2.json": b"[]"})

    def test_pulihkan_snapshot_hari_yang_sama(self):
        with tempfile.TemporaryDirectory() as d:
            kw = {"raw": Path(d) / "raw", "manifest_dir": Path(d) / "man", "bronze": Path(d) / "bronze"}
            s = inti.Snapshot("wdi_arsip", tanggal="2026-10-20", **kw)
            s.simpan("versi/202607.tar.gz", b"isi")
            rid = s.tambah_rilis(inti.Rilis("wdi_arsip", "202607", "rilis_resmi", "2026-07-01"))
            s.tulis_bronze("nilai", [{"value": 1}], rid, "versi/202607.tar.gz")
            s.berkas["versi/202607.tar.gz"]["baris_bronze"] = 1
            s.selesai()
            s2 = inti.Snapshot("wdi_arsip", tanggal="2026-10-20", **kw)
            self.assertTrue(wdi.pulihkan(s2))
            self.assertTrue(wdi._versi_selesai(s2, "202607"))
            self.assertFalse(wdi._versi_selesai(s2, "202507"))
            self.assertEqual({k: s2.bronze_tabel["nilai"][k] for k in ("baris", "bagian")}, {"baris": 1, "bagian": 1})
            (kw["raw"] / "wdi_arsip" / "2026-10-20" / "versi" / "202607.tar.gz").write_bytes(b"rusak")
            self.assertFalse(wdi._versi_selesai(s2, "202607"))


if __name__ == "__main__":
    unittest.main()
