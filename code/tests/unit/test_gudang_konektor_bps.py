"""Uji luring konektor BPS (brief 4 M2): rilis tabel, pendaftaran snapshot asal, dan daftar BRS."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from sdg_gudang.akuisisi import inti
from sdg_gudang.akuisisi.konektor import bps

CSV_DINAMIS = (b"var_id,wilayah_id,wilayah,turvar_id,turvar,tahun_id,tahun,periode_id,periode,nilai,satuan\n"
               b"303,1100,ACEH,539,SD/sederajat,103,2003,0,Tahun,107.6,\n"
               b"303,1100,ACEH,539,SD/sederajat,104,2004,0,Tahun,108.84,\n")
CSV_STATIS = b'wilayah,tahun,bahan_bakar,nilai,catatan,cek\nACEH,2001,"Gas/Elpiji",,"elpiji 3, 5,5 kg",\n'

DAFTAR_BRS = {
    "status": "OK", "data-availability": "available",
    "data": [{"page": 1, "pages": 215, "per_page": 10, "count": 2, "total": 2142},
             [{"brs_id": 2623, "subj_id": 536, "subj": "Harga-Harga", "title": "Inflasi September 2026",
               "abstract": "<ul><li>x</li></ul>", "rl_date": "2026-10-01", "updt_date": None,
               "pdf": "https://webapi.bps.go.id/download.php?f=abc", "size": "3.8 MB"},
              {"brs_id": 2622, "subj_id": 536, "subj": "Harga-Harga", "title": "IHPB", "abstract": "",
               "rl_date": "2026-10-01", "updt_date": None, "pdf": "", "size": ""}]],
}


class TestMurni(unittest.TestCase):
    def test_rilis_tabel(self):
        self.assertEqual(bps.rilis_tabel("sdg4_apk", {"var": 303, "last_update": ["2025-12-01 14:07:15"]}),
                         [("303@2025-12-01T14:07:15", "2025-12-01T14:07:15")])
        self.assertEqual(bps.rilis_tabel("s", {"table_id": 1609, "last_update": ["2025-12-16 08:57:49.103415"]}),
                         [("tabel1609@2025-12-16T08:57:49", "2025-12-16T08:57:49")])
        self.assertEqual(bps.rilis_tabel("s", {"var": 1, "last_update": []}), [])

    def test_daftar_brs(self):
        meta, rows = bps.urai_daftar_brs(DAFTAR_BRS)
        self.assertEqual((meta["pages"], len(rows)), (215, 2))
        r = bps.rilis_brs(rows[0])
        self.assertEqual((r.rilis_id, r.tanggal_rilis, r.jenis_bukti_tanggal),
                         ("bps_brs:brs-2623", "2026-10-01", "rilis_resmi"))
        with self.assertRaises(ValueError):
            bps.urai_daftar_brs({"status": "Error", "message": "Invalid key"})
        self.assertEqual(bps.urai_daftar_brs({"status": "OK", "data-availability": "list-not-available"})[1], [])


class TestDaftarkanSnapshot(unittest.TestCase):
    def test_salin_verifikasi_rilis_dan_bronze(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            asal = d / "asal"
            (asal / "json").mkdir(parents=True)
            js_dinamis, js_statis = b'[{"var":303}]', b'{"tabel":1364}'
            (asal / "json" / "sdg4_apk.json").write_bytes(js_dinamis)
            (asal / "json" / "sdg7_bb.json").write_bytes(js_statis)
            (asal / "sdg4_apk.csv").write_bytes(CSV_DINAMIS)
            (asal / "sdg7_bb.csv").write_bytes(CSV_STATIS)
            m = {"diunduh": "2026-10-17T17:44:26+07:00", "tabel": {
                "sdg4_apk": {"jenis": "dinamis", "var": 303, "judul": "APK", "last_update": ["2025-12-01 14:07:15"],
                             "sha256_json": hashlib.sha256(js_dinamis).hexdigest()},
                "sdg7_bb": {"jenis": "statis", "table_id": 1364, "judul": "BB", "last_update": ["2022-10-04 10:34:23"],
                            "sha256_json": "salah", "diunduh": "2026-10-17T18:00:00+07:00"}}}
            (asal / "manifest.json").write_text(json.dumps(m))
            s = inti.Snapshot("bps", tanggal="2026-10-17", raw=d / "raw", manifest_dir=d / "man", bronze=d / "br")
            # konektor memakai AKAR untuk path relatif; uji memakai folder sementara di bawah AKAR palsu
            asli = inti.AKAR
            try:
                bps.inti.AKAR = d
                hasil = bps.jalankan_tabel(s, {"asal_dir": str(asal)})
            finally:
                bps.inti.AKAR = asli
            self.assertEqual(hasil["baris_bronze"], 3)
            self.assertIn("bps:303@2025-12-01T14:07:15", s.rilis)
            self.assertIn("bps:tabel1364@2022-10-04T10:34:23", s.rilis)
            self.assertEqual(s.rilis["bps:303@2025-12-01T14:07:15"]["jenis_bukti_tanggal"], "pembaruan_sumber")
            self.assertEqual(s.berkas["json/sdg4_apk.json"]["diunduh_pada"], "2026-10-17T17:44:26+07:00")
            self.assertEqual(s.berkas["sdg7_bb.csv"]["diunduh_pada"], "2026-10-17T18:00:00+07:00")
            self.assertEqual([g["apa"] for g in s.galat], ["tabel sdg7_bb"])  # sha256 salah tercatat
            self.assertEqual(set(s.bronze_tabel), {"dinamis", "statis_sdg7_bb", "katalog_tabel"})
            s.selesai()
            self.assertEqual(inti.verifikasi(d / "man" / "bps-2026-10-17.json", d / "raw"), [])
            import pyarrow.parquet as pq
            t = pq.read_table(d / "br" / "bps" / "dinamis" / "snapshot=2026-10-17")
            self.assertEqual(t.column("nilai").to_pylist(), ["107.6", "108.84"])
            self.assertEqual(set(t.column("tabel").to_pylist()), {"sdg4_apk"})


if __name__ == "__main__":
    unittest.main()
