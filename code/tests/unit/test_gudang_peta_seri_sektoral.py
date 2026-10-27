"""Kurasi steward seri sektoral ke kode indikator global (config/referensi/peta_seri_sektoral.csv)."""
import csv
import re
import unittest
from pathlib import Path

from sdg_gudang.silver import inti as S

PETA = S.AKAR / "config" / "referensi" / "peta_seri_sektoral.csv"
KODE = re.compile(r"^\d{1,2}\.[0-9a-z]{1,2}\.\d{1,2}$")


class UjiPetaSeri(unittest.TestCase):
    def setUp(self):
        with PETA.open(encoding="utf-8") as f:
            self.rows = list(csv.DictReader(f))

    def test_kode_dan_hubungan(self):
        for r in self.rows:
            self.assertIn(r["hubungan"], {"sama", "komponen", "proksi", "tidak_dipetakan"}, r["seri_kode"])
            kode = [k for k in r["kode_global"].split("|") if k]
            self.assertEqual(not kode, r["hubungan"] == "tidak_dipetakan", r["seri_kode"])
            for k in kode:
                self.assertRegex(k, KODE)
            self.assertTrue(r["alasan"], r["seri_kode"])

    def test_tujuan_pertama_lingkungan(self):
        """Kode pertama menentukan pilar; semua seri bencana BNPB harus jatuh ke Pilar Lingkungan (tujuan 11/13)."""
        for r in self.rows:
            if r["kode_global"]:
                self.assertIn(r["kode_global"].split(".")[0], {"11", "13"}, r["seri_kode"])

    def test_seri_silver_tercakup(self):
        """Setiap seri BNPB di Silver mempunyai keputusan steward (dipetakan atau tidak)."""
        p = Path(S.SILVER) / "observasi" / "bnpb"
        if not p.exists():
            self.skipTest("Silver BNPB belum dibangun")
        import pyarrow.parquet as pq

        seri = set()
        for f in p.glob("*.parquet"):
            seri |= set(pq.read_table(f, columns=["seri_kode"]).column("seri_kode").to_pylist())
        self.assertEqual(seri - {r["seri_kode"] for r in self.rows}, set())


if __name__ == "__main__":
    unittest.main()
