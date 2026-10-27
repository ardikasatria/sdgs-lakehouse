"""Uji aturan Silver bersama: S02 periode, S03 nilai, S05 rincian, S08 kunci ganda, kasus wilayah M1."""
import unittest

from sdg_gudang.silver import inti as S
from sdg_gudang.silver.jalan import s08
from sdg_gudang.silver.pemeta import bps


class UjiNilai(unittest.TestCase):
    def test_urai(self):
        self.assertEqual(S.urai_nilai("88.96"), ("88.96", 2))
        self.assertEqual(S.urai_nilai("1,234,567"), ("1234567", 0))
        self.assertEqual(S.urai_nilai("12,5", desimal_koma=True), ("12.5", 1))
        self.assertEqual(S.urai_nilai("10.50"), ("10.5", 2))
        self.assertEqual(S.urai_nilai("0.0"), ("0", 1))

    def test_kosong_dan_karantina(self):
        for t in ("", "-", "...", "NA", None):
            with self.assertRaises(S.Kosong):
                S.urai_nilai(t)
        for t in ("12,5", "<5", "abc"):
            with self.assertRaises(S.Karantina):
                S.urai_nilai(t)


class UjiPeriodeRincian(unittest.TestCase):
    def test_periode_bps(self):
        self.assertEqual(bps.periode("2023", "Agustus")["periode"], "2023-08")
        self.assertEqual(bps.periode("2023", "Semester 1 (Maret)"),
                         {"periode": "2023-S1", "jenis_periode": "semester", "bulan_acuan": "3"})
        with self.assertRaises(S.Karantina):
            bps.periode("23", "Tahun")

    def test_rincian(self):
        self.assertEqual(S.rincian({"turvar": "Tidak ada"}), "total")
        self.assertEqual(S.rincian({"b": "Perempuan", "a": "Total"}), "b=Perempuan")
        self.assertEqual(S.rincian({"x": "Perkotaan+Perdesaan"}, {"x": {"Perkotaan+Perdesaan"}}), "total")


class UjiS08(unittest.TestCase):
    def test_gabung_dan_karantina(self):
        dasar = {"rilis_id": "r", "seri_kode": "s", "wilayah_kode": 1100, "periode": "2020", "rincian": "total"}
        obs = [dasar | {"nilai": "1"}, dasar | {"nilai": "1"}, dasar | {"periode": "2021", "nilai": "1"},
               dasar | {"periode": "2021", "nilai": "2"}]
        tetap, kar, gabung = s08(obs)
        self.assertEqual((len(tetap), len(kar), gabung), (1, 2, 1))


class UjiWilayah(unittest.TestCase):
    """Kasus uji dimensi wilayah M1: kode BPS dan ISO Papua, kode ambigu tidak ditebak."""

    @classmethod
    def setUpClass(cls):
        cls.r = S.Rujukan()

    def test_papua(self):
        self.assertEqual(self.r.wilayah("bps", "94"), 9400)
        self.assertEqual(self.r.wilayah("bps", "9999"), 9999)

    def test_tidak_dikenal(self):
        with self.assertRaises(S.Karantina):
            self.r.wilayah("iso3166_2", "ID-XX")


if __name__ == "__main__":
    unittest.main()
