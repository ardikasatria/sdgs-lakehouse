"""Uji S09 agregasi kabupaten/kota ke provinsi dengan komponen sintetis."""
import unittest

from sdg_gudang.silver.agregasi import agregasikan


def k(kab, seri, nilai, satuan="ton_per_hari", prov=1100, rilis="r"):
    return {"rilis_id": rilis, "seri_kode": seri, "wilayah_kode": prov, "periode": "2026", "rincian": "total",
            "nilai": nilai, "desimal": 0, "satuan_id": satuan, "aturan_silver": "S01", "kabkota": kab,
            "sumber": "sipsn", "keluarga": "sipsn", "tabel_bronze": "t", "_berkas_raw": "b", "_sha256_raw": "h",
            "_snapshot": "2026-10-20"}


class UjiAgregasi(unittest.TestCase):
    def test_jumlah_dan_bobot(self):
        kom = [k("a", "timbulan", "100"), k("b", "timbulan", "300"),
               k("a", "pct", "10", "persen"), k("b", "pct", "50", "persen")]
        obs, kar = agregasikan(kom, {"pct": "timbulan"}, 0.8)
        hasil = {o["seri_kode"]: o for o in obs}
        self.assertEqual(hasil["timbulan"]["nilai"], "400")
        self.assertEqual(hasil["pct"]["nilai"], "40")  # (100x10 + 300x50) / 400, bukan rata-rata 30
        self.assertIn("2/2", hasil["pct"]["agregasi"])
        self.assertTrue(hasil["timbulan"]["aturan_silver"].endswith("S09"))
        self.assertEqual(kar, [])

    def test_ambang(self):
        kom = [k(c, "timbulan", "1" if c in "ab" else None) for c in "abcde"]
        obs, kar = agregasikan(kom, {}, 0.8)
        self.assertEqual(obs, [])
        self.assertEqual(kar[0]["alasan"], "cakupan_agregasi_kurang")

    def test_tanpa_ambang_dan_tidak_aditif(self):
        kom = [k("a", "kejadian", "2", "kejadian"), k("b", "kejadian", "3", "kejadian"),
               k("a", "indeks", "70", "indeks")]
        obs, _ = agregasikan(kom, {}, None)
        self.assertEqual([(o["seri_kode"], o["nilai"]) for o in obs], [("kejadian", "5")])
        self.assertEqual(obs[0]["agregasi"], "jumlah kabkota 2")


if __name__ == "__main__":
    unittest.main()
