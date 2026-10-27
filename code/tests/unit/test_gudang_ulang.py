import json
import tempfile
import unittest
from pathlib import Path

from sdg_gudang.akuisisi import inti
from sdg_gudang.akuisisi.ulang import RawBeda, baca_raw, snapshot_dari_manifest


class UjiBacaRaw(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        akar = Path(self.tmp.name)
        self.raw, self.man = akar / "raw", akar / "manifest"
        self.man.mkdir()
        (self.raw / "kkp" / "2026-01-01").mkdir(parents=True)
        (self.raw / "kkp" / "2026-01-01" / "a.json").write_bytes(b"{}")
        m = {"sumber": "kkp", "snapshot": "2026-01-01", "rilis": {},
             "berkas": {"a.json": {"sha256": inti.sha256_bita(b"{}"), "diunduh_pada": "x"},
                        "b.json": {"sha256": "0" * 64, "diunduh_pada": "x"}}}
        (self.man / "kkp-2026-01-01.json").write_text(json.dumps(m))
        self.snap, _ = snapshot_dari_manifest(self.man / "kkp-2026-01-01.json", akar / "bronze", self.raw)

    def tearDown(self):
        self.tmp.cleanup()

    def test_sha_cocok(self):
        self.assertEqual(baca_raw(self.snap, "a.json"), b"{}")

    def test_hilang_dan_tidak_tercatat(self):
        with self.assertRaises(RawBeda):
            baca_raw(self.snap, "b.json")
        with self.assertRaises(RawBeda):
            baca_raw(self.snap, "c.json")

    def test_sha_beda(self):
        (self.raw / "kkp" / "2026-01-01" / "a.json").write_bytes(b"[]")
        with self.assertRaises(RawBeda):
            baca_raw(self.snap, "a.json")


if __name__ == "__main__":
    unittest.main()
