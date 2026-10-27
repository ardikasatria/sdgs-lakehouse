"""Uji luring konektor ILOSTAT SDMX dengan cuplikan payload kecil."""
from __future__ import annotations

import unittest

from sdg_gudang.akuisisi.konektor import ilostat

DATAFLOW = {"data": {"dataflows": [
    {"id": "DF_SDG_0852_SEX_AGE_RT", "version": "1.0", "agencyID": "ILO", "name": "SDG indicator 8.5.2",
     "annotations": [{"title": "14/10/2026 07:01:04", "type": "LAST_UPDATE"}, {"title": "x", "type": "ORDER"}],
     "structure": "urn:sdmx:org.sdmx.infomodel.datastructure.DataStructure=ILO:SDG_0852_SEX_AGE_RT(1.0)"},
    {"id": "DF_UNE_DEAP_SEX_AGE_RT", "version": "1.0", "agencyID": "ILO", "name": "Unemployment rate",
     "annotations": [{"title": "15/10/2026 07:05:05", "type": "LAST_UPDATE"}],
     "structure": "urn:sdmx:org.sdmx.infomodel.datastructure.DataStructure=ILO:UNE_DEAP_SEX_AGE_RT(1.0)"},
    {"id": "DF_CCF_XOXR_CUR_RT", "version": "1.0", "agencyID": "ILO", "name": "Exchange rate", "annotations": [],
     "structure": "urn:sdmx:org.sdmx.infomodel.datastructure.DataStructure=ILO:CCF_XOXR_CUR_RT(1.0)"}]}}

DSD = {"data": {"dataStructures": [{"id": "SDG_0852_SEX_AGE_RT", "dataStructureComponents": {"dimensionList": {
    "dimensions": [{"id": "FREQ", "position": 1}, {"id": "REF_AREA", "position": 0}, {"id": "MEASURE", "position": 2},
                   {"id": "SEX", "position": 3}, {"id": "AGE", "position": 4}],
    "timeDimensions": [{"id": "TIME_PERIOD", "position": 5}]}}}]}}

CSV = ("﻿DATAFLOW,REF_AREA,FREQ,MEASURE,SEX,AGE,TIME_PERIOD,OBS_VALUE,OBS_STATUS,NOTE_SOURCE\n"
       "ILO:DF_SDG_0852_SEX_AGE_RT(1.0),IDN,A,SDG_0852_RT,SEX_T,AGE_YTHADULT_YGE15,2000,6.078,,\"LFS, nasional\"\n"
       "ILO:DF_SDG_0852_SEX_AGE_RT(1.0),IDN,A,SDG_0852_RT,SEX_M,AGE_YTHADULT_YGE15,2000,5.683,B,\n").encode()


class TestIlostatMurni(unittest.TestCase):
    def test_urai_dan_pilih_dataflow(self):
        d = ilostat.urai_dataflow(DATAFLOW)
        self.assertEqual(d[0]["last_update"], "14/10/2026 07:01:04")
        self.assertEqual((d[0]["dsd_agensi"], d[0]["dsd_id"], d[0]["dsd_versi"]), ("ILO", "SDG_0852_SEX_AGE_RT", "1.0"))
        self.assertEqual(d[2]["last_update"], "")
        self.assertEqual([x["id"] for x in ilostat.pilih_dataflow(d)], ["DF_SDG_0852_SEX_AGE_RT", "DF_UNE_DEAP_SEX_AGE_RT"])
        self.assertEqual([x["id"] for x in ilostat.pilih_dataflow(d, batas=["DF_UNE_DEAP_SEX_AGE_RT"])],
                         ["DF_UNE_DEAP_SEX_AGE_RT"])

    def test_last_update_hari_bulan_tahun(self):
        self.assertEqual(ilostat.iso_last_update("20/02/2026 18:50:06"), "2026-02-20T18:50:06")
        with self.assertRaises(ValueError):
            ilostat.iso_last_update("2026-02-20")

    def test_kunci_seri_mengikuti_posisi_dimensi(self):
        dim = ilostat.dimensi_dsd(DSD)
        self.assertEqual(dim, ["REF_AREA", "FREQ", "MEASURE", "SEX", "AGE"])
        self.assertEqual(ilostat.kunci_seri(dim), "IDN....")
        self.assertEqual(ilostat.kunci_seri(["FREQ", "REF_AREA"]), ".IDN")
        with self.assertRaises(ValueError):
            ilostat.kunci_seri(["FREQ"])

    def test_baris_csv_apa_adanya(self):
        rows = ilostat.baris_csv(CSV)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["DATAFLOW"], "ILO:DF_SDG_0852_SEX_AGE_RT(1.0)")
        self.assertEqual(rows[0]["OBS_VALUE"], "6.078")
        self.assertIsNone(rows[0]["OBS_STATUS"])
        self.assertEqual(rows[0]["NOTE_SOURCE"], "LFS, nasional")
        self.assertEqual(rows[1]["OBS_STATUS"], "B")

    def test_rilis(self):
        d = ilostat.urai_dataflow(DATAFLOW)
        r = ilostat.rilis_dari(d[0])
        self.assertEqual(r.rilis_id, "ilostat:DF_SDG_0852_SEX_AGE_RT@2026-10-14T07:01:04")
        self.assertEqual(r.jenis_bukti_tanggal, "pembaruan_sumber")
        self.assertIn("14/10/2026 07:01:04", r.bukti)
        self.assertEqual(ilostat.rilis_dari(d[2]).jenis_bukti_tanggal, "tanggal_unduh")


if __name__ == "__main__":
    unittest.main()
