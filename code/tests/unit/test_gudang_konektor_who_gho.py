"""Uji luring konektor WHO GHO (brief 4 M2): aturan cakupan, kode alternatif DATADOT, rilis, saring M49."""
from __future__ import annotations

import unittest

from sdg_gudang.akuisisi.konektor import who_gho

CSV_DATADOT = (
    "IND_ID,IND_CODE,IND_UUID,IND_PER_CODE,DIM_TIME,DIM_TIME_TYPE,DIM_GEO_CODE_M49,DIM_GEO_CODE_TYPE,"
    "DIM_PUBLISH_STATE_CODE,IND_NAME,GEO_NAME_SHORT,DIM_DEG_URB,PERCENT_POP_N\n"
    "1548EA3X,WSH_WATER_SAFELY_MANAGED,1548EA3,X,2000,YEAR,276,COUNTRY,PUBLISHED,Air,Germany,RURAL,99.8\n"
    "1548EA3X,WSH_WATER_SAFELY_MANAGED,1548EA3,X,2000,YEAR,360,COUNTRY,PUBLISHED,Air,Indonesia,RURAL,17.8\n"
    "1548EA3X,WSH_WATER_SAFELY_MANAGED,1548EA3,X,2002,YEAR,3600,COUNTRY,PUBLISHED,Air,Lain,RURAL,1\n"
).encode("utf-8")


class TestCakupan(unittest.TestCase):
    def test_calon_dan_klasifikasi(self):
        ind = [{"IndicatorCode": "SDGHIV", "IndicatorName": "New HIV infections"},
               {"IndicatorCode": "WSH_1", "IndicatorName": "SDG 3.9.2 WASH deaths"},
               {"IndicatorCode": "SDGPM25", "IndicatorName": "PM2.5"},
               {"IndicatorCode": "SDGBARU", "IndicatorName": "indikator baru"},
               {"IndicatorCode": "EMF", "IndicatorName": "Electric field"}]
        calon = who_gho.calon_dari_gho(ind)
        self.assertEqual(calon, {"SDGHIV", "WSH_1", "SDGPM25", "SDGBARU"})
        k = who_gho.klasifikasi(calon)
        self.assertIn("SDGHIV", k["ambil"])
        self.assertIn("WSH_WATER_SAFELY_MANAGED", k["ambil"])  # dari PETA_SDG walau bukan calon
        self.assertEqual(k["di_luar"], ["SDGPM25"])
        self.assertEqual(k["tak_terklasifikasi"], ["SDGBARU"])
        self.assertTrue(all(who_gho.PETA_SDG[x].split(".")[0] in ("2", "3", "6") for x in k["ambil"]))
        self.assertFalse(set(who_gho.PETA_SDG) & set(who_gho.DI_LUAR))

    def test_kode_alternatif_dan_peta_datadot(self):
        self.assertEqual(who_gho.kode_alternatif("MDG_0000000020,20,SDG Indicator 3.3.2,1426"), ["MDG_0000000020"])
        self.assertEqual(who_gho.kode_alternatif("AMR_INFECT_ECOLI, 5751"), ["AMR_INFECT_ECOLI"])
        self.assertEqual(who_gho.kode_alternatif("MALARIA_EST_INCIDENCE "), ["MALARIA_EST_INCIDENCE"])
        self.assertEqual(who_gho.kode_alternatif(None), [])
        p = who_gho.peta_datadot([{"AlternativeCodes": "MCV2", "DataExportUri": ""},
                                  {"AlternativeCodes": "MCV2", "DataExportUri": "https://x/a.csv", "UrlName": "BB"}])
        self.assertEqual(p["MCV2"]["UrlName"], "BB")


class TestRilisDanSaring(unittest.TestCase):
    def test_max_tanggal_dan_kode(self):
        f = [{"Date": "2024-01-08T20:00:00.123+01:00"}, {"Date": "2025-03-01T10:00:00+01:00"}, {"Date": None}]
        self.assertEqual(who_gho.max_tanggal(f), "2025-03-01T10:00:00+01:00")
        self.assertEqual(who_gho.kode_rilis("SDGHIV", "2024-01-08T20:00:00.123"), "SDGHIV@2024-01-08T20:00:00")
        self.assertEqual(who_gho.kode_rilis("SDGHIV", ""), "SDGHIV@tanpa_tanggal")

    def test_saring_m49_tepat(self):
        h, b = who_gho.saring_csv_m49(CSV_DATADOT)
        self.assertEqual(len(b), 1)
        self.assertEqual(b[0][10], "Indonesia")
        h2, b2 = who_gho.saring_csv_m49(who_gho.tulis_csv(h, b))
        self.assertEqual((h2, b2), (h, b))


if __name__ == "__main__":
    unittest.main()
