import unittest

from sdg_gudang.gudang import kontrak


class UjiKontrak(unittest.TestCase):
    def test_keluaran_mutakhir(self):
        """Model, kontrak dbt, dan DCAT yang di-commit sama dengan hasil bangkitan dari config/mesh."""
        self.assertEqual(kontrak.main(["--cek"]), 0)

    def test_pilar_ditegakkan(self):
        for p, isi in kontrak.semua().items():
            if p.suffix == ".yml" and "jenis" not in isi and "_referensi" not in p.name and "_rilis" not in p.name:
                self.assertIn("enforced: true", isi, p.name)
                self.assertIn("hanya_tayang", isi, p.name)


if __name__ == "__main__":
    unittest.main()
