"""Uji fungsi penilaian SLA antarlapis (sdg_gudang.gudang.uji_sla) tanpa tumpukan gudang."""
import json
import tempfile
import unittest
from pathlib import Path

from sdg_gudang.gudang import uji_sla as U

SLA_GDELT = {"berkas_per_hari_per_aliran": 96, "md5_gagal_maks": 0, "laju_min_mb_s": 10, "hari_maks_menit": 60}


def manifest(folder: Path, hari: dict) -> Path:
    berkas = {}
    for i, (nama, (n_asal, n_gagal)) in enumerate(sorted(hari.items())):
        berkas[nama] = {"asal": [f"2026101{i}0000{j:02d} sha 1000000" for j in range(n_asal)],
                        "gagal": [f"x{j}" for j in range(n_gagal)],
                        "diunduh_pada": f"2026-10-24T14:{10 + i:02d}:00+07:00"}
    p = folder / "gdelt.json"
    p.write_text(json.dumps({"berkas": berkas}), "utf-8")
    return p


class UjiSla(unittest.TestCase):
    def test_p95_dan_cek(self):
        self.assertEqual(U.p95(list(range(1, 101))), 95)
        self.assertTrue(U.cek(5, 10, 5 <= 10)["lulus"])
        self.assertFalse(U.cek(15, 10, 15 <= 10)["lulus"])

    def test_kumpulkan_cek_bersarang(self):
        h = {"a": {"x": U.cek(1, 2, True), "b": {"y": U.cek(3, 2, False)}}, "c": 7}
        jalur = dict(U.kumpulkan_cek(h))
        self.assertEqual(set(jalur), {"a.x", "a.b.y"})

    def test_gdelt_lengkap_lulus(self):
        with tempfile.TemporaryDirectory() as d:
            akar = U.AKAR
            U.AKAR = Path(d)
            try:
                p = manifest(Path(d), {"gkg/english/20261014.jsonl": (96, 0), "gkg/translation/20261014.jsonl": (96, 0)})
                g = U.uji_gdelt(p, SLA_GDELT, durasi_s=10.0)
            finally:
                U.AKAR = akar
        self.assertTrue(g["berkas_lengkap"]["lulus"])
        self.assertTrue(g["md5_dan_unduh_gagal"]["lulus"])
        self.assertAlmostEqual(g["laju_mb_s"]["nilai"], 19.2)
        self.assertTrue(g["satu_hari_menit"]["lulus"])

    def test_gdelt_berkas_gagal_tertangkap(self):
        with tempfile.TemporaryDirectory() as d:
            akar = U.AKAR
            U.AKAR = Path(d)
            try:
                p = manifest(Path(d), {"gkg/english/20261014.jsonl": (95, 1)})
                g = U.uji_gdelt(p, SLA_GDELT, durasi_s=100.0)
            finally:
                U.AKAR = akar
        self.assertFalse(g["berkas_lengkap"]["lulus"])
        self.assertFalse(g["md5_dan_unduh_gagal"]["lulus"])
        self.assertFalse(g["laju_mb_s"]["lulus"])


if __name__ == "__main__":
    unittest.main()
