"""Uji aturan K0-K9 dengan observasi sintetis (tanpa data sumber)."""
import unittest

from sdg_gudang.silver import rekonsiliasi as K


def o(**kw):
    dasar = {"keluarga": "bps", "sumber": "bps", "rilis_id": "bps:r1", "seri_kode": "s", "nilai": "10.5",
             "desimal": 1, "tanggal_rilis": "2024-01-01", "jenis_periode": "tahun", "bulan_acuan": "",
             "sifat": "resmi", "hubungan": "sama", "satuan": "persen", "tingkat": "nasional", "agregasi": "",
             "cakupan_parsial": "", "kunci_bps": None}
    return dasar | kw


class UjiStatus(unittest.TestCase):
    def test_sama_pembulatan_selisih(self):
        self.assertEqual(K.status(o(), o())[0], "sama")
        self.assertEqual(K.status(o(nilai="10.5", desimal=1), o(nilai="10.53", desimal=2))[0], "pembulatan")
        self.assertEqual(K.status(o(nilai="10.5", desimal=1), o(nilai="10.7", desimal=1))[0], "selisih")


class UjiKlasifikasi(unittest.TestCase):
    def k(self, jenis, a, b, wilayah=9999, riwayat=None):
        return K.klasifikasi(jenis, a, b, wilayah, K.wilayah_pemekaran(), riwayat or {})["aturan"]

    def test_urutan(self):
        self.assertEqual(self.k("sumber_x_sumber", o(nilai="0.105"), o(nilai="10.5")), "K1")
        self.assertEqual(self.k("rilis_x_rilis", o(tanggal_rilis="2022-01-01"), o(nilai="9", tanggal_rilis="2023-01-01"),
                                wilayah=9400), "K2")
        self.assertEqual(self.k("sumber_x_sumber", o(agregasi="jumlah kabkota"), o(nilai="9")), "K3")
        self.assertEqual(self.k("sumber_x_sumber", o(jenis_periode="bulan"), o(nilai="9")), "K4")
        self.assertEqual(self.k("sumber_x_sumber", o(hubungan="proksi"), o(nilai="9", keluarga="unsd")), "K5")
        self.assertEqual(self.k("rilis_x_rilis", o(), o(nilai="9")), "K6")
        self.assertEqual(self.k("sumber_x_sumber", o(sifat="model", keluarga="ilostat"), o(nilai="9")), "K8")
        self.assertEqual(self.k("sumber_x_sumber", o(), o(nilai="9", keluarga="unsd")), "K9")

    def test_turunan(self):
        bps = o(kunci_bps=("k",), rilis_id="bps:r2", tanggal_rilis="2024-06-01")
        lama = o(kunci_bps=("k",), rilis_id="bps:r1", nilai="9.0", tanggal_rilis="2023-01-01")
        intl = o(keluarga="unsd", nilai="9.0", tanggal_rilis="2023-03-02")
        h = K.klasifikasi("sumber_x_sumber", bps, intl, 9999, {}, {("k",): [bps, lama]})
        self.assertEqual((h["aturan"], h["jeda_hari"]), ("K7", 60))

    def test_skala_bukan_kebetulan(self):
        self.assertEqual(K.k1_skala(o(nilai="10"), o(nilai="12")), "")
        self.assertTrue(K.k1_skala(o(nilai="1000"), o(nilai="1")))


class UjiWilson(unittest.TestCase):
    def test_batas(self):
        lo, hi = K.wilson(78, 100)
        self.assertTrue(lo < 0.78 < hi)


class UjiTanggalEfektif(unittest.TestCase):
    def test_urutan_cadangan(self):
        self.assertEqual(K.tanggal_efektif({"tanggal_rilis": "2019-07-08", "batas_atas": "2019-03-29",
                                            "snapshot_pertama": "2026-10-20"}), "2019-07-08")
        # arsip PBB "prior to 29 March 2019": tanpa tanggal rilis, hanya batas atas
        self.assertEqual(K.tanggal_efektif({"tanggal_rilis": "", "batas_atas": "2019-03-29",
                                            "snapshot_pertama": "2026-10-20T00:00:00"}), "2019-03-29")
        self.assertEqual(K.tanggal_efektif({"tanggal_rilis": "", "batas_atas": "",
                                            "snapshot_pertama": "2026-10-20T00:00:00"}), "2026-10-20")

    def test_registri_tidak_melewati_batas(self):
        """Pada registri yang di-commit, tanggal efektif tidak pernah sesudah batas atas atau snapshot pertama."""
        import csv

        from sdg_gudang.akuisisi import inti as A
        p = A.MANIFEST / "dim_rilis.csv"
        if not p.exists():
            self.skipTest("dim_rilis.csv belum ada")
        with p.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                t = K.tanggal_efektif(r)
                if r["batas_atas"]:
                    self.assertLessEqual(t, r["batas_atas"][:10], r["rilis_id"])
                if r["snapshot_pertama"]:
                    self.assertLessEqual(t, r["snapshot_pertama"][:10], r["rilis_id"])


if __name__ == "__main__":
    unittest.main()
