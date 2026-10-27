"""Uji luring konektor UNSD (brief 4 M2): halaman arsip, pemilihan berkas, saring Indonesia, perataan API."""
from __future__ import annotations

import gzip
import io
import unittest

from sdg_gudang.akuisisi.konektor import unsd

HTML = """
<table><thead><tr><th>Date</th><th>Description</th><th>Format</th></tr></thead><tbody>
 <tr>
  <td>30-Sep-26</td>
    <td>Global SDG Indicators Database prior to 30 Sep 2026</td>
    <td><a href="https://unstats.un.org/sdgs/indicators/database/archive/2026_Q2.2_AllData_Before_20260930_CSV.zip"><button>CSV</button></a>
    <a href="https://unstats.un.org/sdgs/indicators/database/archive/2026_Q2.2_AllData_Before_20260930_R.zip">R</a></td>
 </tr>
 <tr>
    <td>30-Sep-26</td>
    <td>Global SDG Indicators Database on 30 Sep 2026</td>
    <td><a href="https://unstats.un.org/sdgs/indicators/database/archive/2026_Q3.1_AllData_After_20260930_CSV.zip">CSV</a></td>
 </tr>
 <tr><td>05-Apr-21</td><td>Global SDG Indicators Database on 05 April 2021</td>
    <td><a href="/sdgs/indicators/database/archive/2021_Q1_AllData_After_20210405_CSV.zip">CSV</a></td></tr>
 <tr><td>29-Mar-19</td><td>Global SDG Indicators Database prior to 29 March 2019</td>
    <td><a href="https://unstats.un.org/sdgs/indicators/database/archive/AllData_Prior_20190329_CSV.zip">CSV</a></td></tr>
 <tr><td>29-Mar-19</td><td>Global SDG Indicators Database on 29 March 2019</td>
    <td><a href="https://unstats.un.org/sdgs/indicators/database/archive/AllData_Onward_20190329_CSV.zip">CSV</a></td></tr>
 <tr><td>x</td><td>tanpa tautan</td><td></td></tr>
</tbody></table>
"""

CSV_GLOBAL = (
    '"","ID","Goal","ReleaseName","SeriesCode","GeoAreaCode","GeoAreaName","TimePeriod","Value","FootNote",'
    '"ObservationID","Age","Sex","Nature","Units"\n'
    '"1","1","1","2026.Q3.G.01","SI_POV_DAY1","4","Afghanistan","2020","10","Indonesia disebut","9","ALLAGE","BOTHSEX","G","PERCENT"\n'
    '"2","2","1","2026.Q3.G.01","SI_POV_DAY1","360","Indonesia","2020","5.5","catatan\nmultibaris","10","ALLAGE","BOTHSEX","G","PERCENT"\n'
    '"3","3","1","2026.Q3.G.01","SI_POV_DAY1","360","Indonesia","2021","5.1","","11","ALLAGE","FEMALE","C","PERCENT"\n'
)


class TestArsip(unittest.TestCase):
    def test_tanggal_dan_kode_nama(self):
        self.assertEqual(unsd.tanggal_halaman("30-Sep-26"), "2026-09-30")
        self.assertEqual(unsd.tanggal_halaman("05-Apr-21"), "2021-04-05")
        self.assertEqual(unsd.kode_dari_nama("2026_Q3.1_AllData_After_20260930_CSV.zip"), "2026.Q3.G.01")
        self.assertEqual(unsd.kode_dari_nama("x/2021_Q1_AllData_After_20210405_CSV.zip"), "2021.Q1.G.01")
        self.assertEqual(unsd.kode_dari_nama("2022_Q3.3_AllData_Before_20221017_CSV.zip"), "2022.Q3.G.03")
        self.assertEqual(unsd.kode_dari_nama("AllData_Onward_20190329_CSV.zip"), "")
        with self.assertRaises(ValueError):
            unsd.tanggal_halaman("2026-09-30")

    def test_urai_halaman_dan_pilih_bawaan(self):
        d = unsd.urai_halaman_arsip(HTML)
        self.assertEqual(len(d), 5)
        self.assertEqual(d[0]["jenis"], "sebelum")
        self.assertEqual(d[1]["berkas"], "2026_Q3.1_AllData_After_20260930")
        self.assertTrue(d[2]["url"].startswith("https://unstats.un.org/sdgs/"))
        self.assertTrue(d[0]["url_r"].endswith("_R.zip"))
        p = unsd.pilih_berkas(d, {})
        # semua "on" + "prior to" tertua, urut dari tertua, prior sebelum on pada tanggal sama
        self.assertEqual([x["berkas"] for x in p], [
            "AllData_Prior_20190329", "AllData_Onward_20190329", "2021_Q1_AllData_After_20210405",
            "2026_Q3.1_AllData_After_20260930"])
        self.assertEqual(len(unsd.pilih_berkas(d, {"jenis": "semua"})), 5)
        self.assertEqual([x["berkas"] for x in unsd.pilih_berkas(d, {"rilis": "2021.Q1.G.01"})],
                         ["2021_Q1_AllData_After_20210405"])
        p = unsd.pilih_berkas(d, {"maks": "2"}, sudah={"AllData_Prior_20190329"})
        self.assertEqual([x["berkas"] for x in p], ["AllData_Onward_20190329", "2021_Q1_AllData_After_20210405"])
        self.assertEqual(len(unsd.pilih_berkas(d, {"dari": "2021-01-01", "sampai": "2021-12-31"})), 1)

    def test_saring_indonesia_menangani_sel_multibaris(self):
        header, baris = unsd.saring_indonesia(io.StringIO(CSV_GLOBAL, newline=""))
        self.assertEqual(len(baris), 2)  # baris Afganistan yang menyebut "Indonesia" di catatan tidak ikut
        self.assertEqual(baris[0][9], "catatan\nmultibaris")
        rows = unsd.baris_arsip_ke_dict(header, baris)
        self.assertIn("nomor_baris", rows[0])
        self.assertEqual(unsd.kode_terbanyak(rows), ("2026.Q3.G.01", {"2026.Q3.G.01": 2}))
        isi = gzip.decompress(unsd.tulis_csv_gz(header, baris)).decode()
        h2, b2 = unsd.saring_indonesia(io.StringIO(isi, newline=""))
        self.assertEqual((h2, b2), (header, baris))
        self.assertEqual(unsd.tulis_csv_gz(header, baris), unsd.tulis_csv_gz(header, baris))  # deterministik

    def test_sel_berubah(self):
        _, b = unsd.saring_indonesia(io.StringIO(CSV_GLOBAL, newline=""))
        h, _ = unsd.saring_indonesia(io.StringIO(CSV_GLOBAL, newline=""))
        lama = unsd.baris_arsip_ke_dict(h, b)
        baru = [dict(r) for r in lama]
        baru[0]["Value"] = "5.50"          # sama secara angka
        baru[1]["Value"] = "5.3"           # berubah
        baru[1]["Nature"] = "E"            # atribut tidak mengubah kunci
        baru.append(dict(baru[0], TimePeriod="2022", Value="4"))
        baru[0]["Type of speed"] = "NA"    # kolom baru bernilai NA tidak mengubah kunci
        baru[0]["_rilis_id"] = "unsd_arsip:x"  # kolom baku Bronze diabaikan
        r = unsd.sel_berubah(lama, baru)
        self.assertEqual((r["sel_sama_kunci"], r["nilai_berubah"], r["sel_muncul"], r["sel_hilang"]), (2, 1, 1, 0))


class TestApi(unittest.TestCase):
    def test_ratakan_dan_kunci(self):
        d = {"goal": ["1", "8"], "series": "SI_POV_DAY1", "timePeriodStart": 1984.0, "value": "86.2",
             "footnotes": ["a", None], "attributes": {"Nature": "G", "Units": "PERCENT"},
             "dimensions": {"Sex": "BOTHSEX"}, "upperBound": None}
        r = unsd.ratakan_baris_api(d)
        self.assertEqual(r["goal"], "1|8")
        self.assertEqual(r["timePeriodStart"], "1984")
        self.assertEqual(r["footnotes"], "a|")
        self.assertEqual((r["atr_Units"], r["dim_Sex"]), ("PERCENT", "BOTHSEX"))
        r2 = dict(r, goal="8")
        self.assertEqual(unsd.kunci_obs_api(r), unsd.kunci_obs_api(r2))

    def test_daftar_seri(self):
        rows, peta = unsd.urai_daftar_seri([{"goal": ["15"], "target": ["15.a"], "indicator": ["15.a.1"],
                                             "release": "2026.Q3.G.01", "code": "DC_X", "description": "d"}])
        self.assertEqual(peta, {"DC_X": "2026.Q3.G.01"})
        self.assertEqual(rows[0]["indicator"], "15.a.1")


if __name__ == "__main__":
    unittest.main()
