"""Uji kerangka akuisisi (brief 4 M2): manifest, rilis, Bronze, registri, dan penyamaran kunci."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sdg_gudang.akuisisi import inti


class TestInti(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        self.kw = {"raw": d / "raw", "manifest_dir": d / "man", "bronze": d / "bronze"}

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_url_aman_menyamarkan_kunci(self):
        u = inti.url_aman("https://webapi.bps.go.id/v1/api/list?model=pressrelease&key=RAHASIA&page=2")
        self.assertNotIn("RAHASIA", u)
        self.assertIn("key=REDACTED", u)
        self.assertIn("page=2", u)

    def test_snapshot_manifest_rilis_bronze_dan_verifikasi(self):
        s = inti.Snapshot("wdi", tanggal="2026-10-20", **self.kw)
        h = s.simpan("a.json", b'{"x":1}', url="https://api.worldbank.org/v2/x?api_key=Z")
        rid = s.tambah_rilis(inti.Rilis("wdi", "202607", "rilis_resmi", "2026-07-01", "versi arsip"))
        n = s.tulis_bronze("seri", [{"nilai": 1.5, "tahun": 2020}, {"nilai": None, "tahun": 2021}], rid, "a.json")
        self.assertEqual(n, 2)
        m = json.loads(s.selesai().read_text("utf-8"))
        self.assertEqual(m["berkas"]["a.json"]["sha256"], h)
        self.assertNotIn("Z", m["berkas"]["a.json"]["url"].split("api_key=")[1])
        self.assertEqual(m["kelas_lisensi"], "A")
        self.assertEqual(inti.verifikasi(s.manifest_dir / "wdi-2026-10-20.json", self.kw["raw"]), [])
        (self.kw["raw"] / "wdi" / "2026-10-20" / "a.json").write_bytes(b"ubah")
        self.assertEqual(inti.verifikasi(s.manifest_dir / "wdi-2026-10-20.json", self.kw["raw"]), ["sha256 beda: a.json"])
        import pyarrow.parquet as pq
        t = pq.read_table(self.kw["bronze"] / "wdi" / "seri" / "snapshot=2026-10-20")
        self.assertEqual(t.num_rows, 2)
        self.assertEqual(set(t.column("_rilis_id").to_pylist()), {"wdi:202607"})
        self.assertEqual(t.column("nilai").to_pylist(), ["1.5", None])

    def test_rilis_menolak_jenis_bukti_asing_dan_bronze_tanpa_rilis(self):
        with self.assertRaises(ValueError):
            inti.Rilis("wdi", "x", "kira_kira")
        s = inti.Snapshot("wdi", tanggal="2026-10-20", **self.kw)
        s.simpan("a.json", b"{}")
        with self.assertRaises(ValueError):
            s.tulis_bronze("seri", [{"a": 1}], "wdi:tidak_ada", "a.json")
        with self.assertRaises(ValueError):
            s.path("../luar.json")

    def test_registri_memilih_bukti_terkuat_dan_snapshot_pertama(self):
        for tgl, bukti in (("2026-10-20", "tanggal_unduh"), ("2026-10-27", "pembaruan_sumber")):
            s = inti.Snapshot("sipsn", tanggal=tgl, **self.kw)
            s.tambah_rilis(inti.Rilis("sipsn", "2023", bukti))
            s.selesai()
        rows = inti.bangun_registri(self.kw["manifest_dir"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["jenis_bukti_tanggal"], "pembaruan_sumber")
        self.assertEqual(rows[0]["snapshot_pertama"], "2026-10-20")
        self.assertEqual(rows[0]["kelas_lisensi"], "B")
        self.assertFalse(inti.boleh_tayang("sipsn"))
        self.assertTrue(inti.boleh_tayang("bnpb"))




class TestBronzeSkema(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        self.kw = {"raw": d / "raw", "manifest_dir": d / "man", "bronze": d / "bronze"}

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _snap(self):
        s = inti.Snapshot("unsd", tanggal="2026-10-20", **self.kw)
        s.simpan("a.csv", b"x")
        s.tambah_rilis(inti.Rilis("unsd", "2026.Q3.G.01", "rilis_resmi"))
        s.tambah_rilis(inti.Rilis("unsd", "2026.Q2.G.01", "rilis_resmi"))
        return s

    def test_skema_beda_dan_kolom_kosong_terbaca_utuh(self):
        s = self._snap()
        s.tulis_bronze("data", [{"a": None, "b": "1"}], "unsd:2026.Q3.G.01", "a.csv")
        s.tulis_bronze("data", [{"a": "x", "c": 2}], "unsd:2026.Q3.G.01", "a.csv")
        t = inti.baca_bronze("unsd", "data", bronze=self.kw["bronze"])
        self.assertEqual(t.num_rows, 2)
        for k in ("a", "b", "c", "_snapshot"):
            self.assertIn(k, t.column_names)
        self.assertEqual(t.column("c").to_pylist(), [None, "2"])

    def test_rilis_per_baris_dan_bagian_basi_dihapus(self):
        s = self._snap()
        s.tulis_bronze("data", [{"v": 1}, {"v": 2}, {"v": 3}], "unsd:2026.Q3.G.01", "a.csv")
        s.tulis_bronze("data", [{"v": 4}], "unsd:2026.Q3.G.01", "a.csv")
        # jalan baru pada tanggal yang sama hanya menulis satu bagian: bagian-0001 lama harus hilang
        s2 = self._snap()
        s2.tulis_bronze("data", [{"v": 9, "_rilis_id": "unsd:2026.Q2.G.01"}, {"v": 8}], "unsd:2026.Q3.G.01", "a.csv")
        t = inti.baca_bronze("unsd", "data", bronze=self.kw["bronze"])
        self.assertEqual(t.column("v").to_pylist(), ["9", "8"])
        self.assertEqual(t.column("_rilis_id").to_pylist(), ["unsd:2026.Q2.G.01", "unsd:2026.Q3.G.01"])
        with self.assertRaises(ValueError):
            s2.tulis_bronze("data", [{"v": 1, "_rilis_id": "unsd:tidak_ada"}], "unsd:2026.Q3.G.01", "a.csv")

if __name__ == "__main__":
    unittest.main()
