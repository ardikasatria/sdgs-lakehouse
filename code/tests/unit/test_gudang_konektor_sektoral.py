"""Uji luring konektor sektoral brief 4 M2: BNPB, SIPSN, SIGN-SMART, dan KKP (fungsi murni, fikstur kecil)."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sdg_gudang import referensi as R
from sdg_gudang.akuisisi import inti
from sdg_gudang.akuisisi.konektor import bnpb, kkp, signsmart, sipsn


def _rujukan():
    w, p = R.bangun_wilayah(), R.bangun_padanan()
    return R.Rujukan(w, p, R.bangun_alias(w, p))


class _DenganRujukan(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ruj = _rujukan()
        cls.terkini = [w for w in cls.ruj.wilayah if w["terkini"] and w["tingkat"] == "provinsi"]


# ---------------------------------------------------------------------------------------------------
# BNPB
# ---------------------------------------------------------------------------------------------------

PKG = {"name": "kompilasi-data-jumlah-dan-dampak-kejadian-bencana-2024", "license_id": "odc-odbl",
       "metadata_modified": "2026-04-16T07:37:39.623402"}
RES = {"id": "f345ba43-99aa-428c-82d8-4b6a0bba380e", "name": "Jumlah Kejadian Bencana Menurut Provinsi 2024.xlsx",
       "last_modified": "2025-09-23T03:04:17.654670", "metadata_modified": "2025-09-23T03:37:44.852589",
       "url": "https://data.bnpb.go.id/dataset/x/resource/y/download/a.xlsx", "datastore_active": True}


class TestBnpb(_DenganRujukan):
    def test_pilih_dataset(self):
        paket = [{"name": n} for n in ("kompilasi-data-kejadian-dan-dampak-bencana-2025",
                                       "kompilasi-data-jumlah-dan-dampak-kejadian-bencana-2024",
                                       "kompilasi-data-kejadian-dan-dampak-bencana-bansor-sumatera-2025",
                                       "kompilasi-data-status-keadaan-darurat-bencana-seluruh-indonesia-tahun-2025",
                                       "data-bencana-indonesia", "jumlah-kejadian-dan-dampak-bencana-tahun-2013",
                                       "datakejadian2000", "rekapr3p2017-2024", "peta-risiko-bencana-indonesia")]
        nama = [d["name"] for d in bnpb.pilih_dataset(paket)]
        self.assertIn("kompilasi-data-jumlah-dan-dampak-kejadian-bencana-2024", nama)
        self.assertIn("rekapr3p2017-2024", nama)
        self.assertNotIn("kompilasi-data-kejadian-dan-dampak-bencana-bansor-sumatera-2025", nama)
        self.assertNotIn("peta-risiko-bencana-indonesia", nama)
        self.assertEqual(len(nama), 6)

    def test_rilis_resource_pembaruan_sumber(self):
        r = bnpb.rilis_resource(PKG, RES)
        self.assertEqual(r.jenis_bukti_tanggal, "pembaruan_sumber")
        self.assertEqual(r.kode_rilis, f"{RES['id']}@{RES['metadata_modified']}")
        self.assertEqual(r.tanggal_rilis, RES["last_modified"])
        self.assertIn("odc-odbl", r.cakupan)
        tanpa = bnpb.rilis_resource(PKG, {"id": "z"})
        self.assertEqual(tanpa.jenis_bukti_tanggal, "tidak_diketahui")

    def test_kelas_tabel(self):
        self.assertEqual(bnpb.kelas_tabel(["No", "Kode Wilayah Provinsi", "Provinsi", "BANJIR"]), "provinsi")
        self.assertEqual(bnpb.kelas_tabel(["No", "Kode Wilayah Provinsi", "Nama Provinsi", "2010.0"]), "provinsi")
        self.assertEqual(bnpb.kelas_tabel(["No", "Kode Wilayah Kabupaten / Kota", "Nama Kabupaten/Kota"]), "kabupaten")
        self.assertEqual(bnpb.kelas_tabel(["Tahun Kejadian", "Provinsi", "Kabupaten", "Nilai Kerusakan"]), "kabupaten")
        self.assertEqual(bnpb.kelas_tabel(["Kode Bencana", "Jenis Bencana", "Meninggal"]), "lain")

    def test_halaman_dan_baris_bronze(self):
        halaman = [{"result": {"fields": [{"id": "_id"}, {"id": "Kode Wilayah Provinsi"}, {"id": "Provinsi"}],
                               "records": [{"_id": 1, "Kode Wilayah Provinsi": 11, "Provinsi": "ACEH"}]}},
                   {"result": {"fields": [], "records": [{"_id": 2, "Kode Wilayah Provinsi": 12.0,
                                                          "Provinsi": "SUMATERA UTARA"}]}}]
        fields, rec = bnpb.gabung_halaman(halaman)
        self.assertEqual(fields, ["_id", "Kode Wilayah Provinsi", "Provinsi"])
        rows = bnpb.baris_bronze(rec, PKG, RES)
        self.assertEqual(rows[0]["_id_ckan"], 1)
        self.assertNotIn("_id", rows[0])
        self.assertEqual(rows[1]["Kode Wilayah Provinsi"], 12.0)  # nilai apa adanya
        self.assertEqual(rows[0]["_lisensi"], "odc-odbl")
        self.assertEqual([bnpb.teks_kode(x) for x in (11, 12.0, "13", None, "")], ["11", "12", "13", None, None])

    def test_periksa_provinsi_mencatat_duplikat_dan_total(self):
        fields = ["_id", "Kode Wilayah Provinsi", "Provinsi"]
        rec = [{"Kode Wilayah Provinsi": 11, "Provinsi": "ACEH"},
               {"Kode Wilayah Provinsi": 11, "Provinsi": "ACEH"},
               {"Kode Wilayah Provinsi": 94, "Provinsi": "PAPUA"},
               {"Kode Wilayah Provinsi": None, "Provinsi": "INDONESIA"}]
        h = bnpb.periksa_provinsi(self.ruj, fields, rec)
        self.assertEqual(h["kode_kosong"], 1)
        self.assertEqual(h["bps"]["duplikat"], {"11": 2})
        self.assertEqual(h["bps"]["cocok"], 1)
        self.assertEqual(h["nama"]["duplikat"], {"ACEH": 2})
        self.assertEqual(len(h["bps"]["hilang"]), 37)

    def test_tantangan_cloudflare(self):
        self.assertTrue(bnpb.adalah_tantangan(403, {"cf-mitigated": "challenge"}))
        self.assertTrue(bnpb.adalah_tantangan(403, {}, b"<title>Just a moment...</title>"))
        self.assertFalse(bnpb.adalah_tantangan(200, {"Content-Type": "application/json"}, b"{}"))

    def test_bronze_lewat_snapshot(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            s = inti.Snapshot("bnpb", tanggal="2026-10-20", raw=d / "raw", manifest_dir=d / "man", bronze=d / "br")
            s.simpan("datastore/x.json", b"{}")
            rid = s.tambah_rilis(bnpb.rilis_resource(PKG, RES))
            n = s.tulis_bronze("provinsi", bnpb.baris_bronze([{"_id": 1, "Provinsi": "ACEH", "BANJIR": 47}], PKG, RES),
                               rid, "datastore/x.json")
            self.assertEqual(n, 1)
            m = json.loads(s.selesai().read_text("utf-8"))
            self.assertEqual(m["kelas_lisensi"], "A-SA")
            self.assertEqual(m["rilis"][rid]["jenis_bukti_tanggal"], "pembaruan_sumber")


# ---------------------------------------------------------------------------------------------------
# SIPSN
# ---------------------------------------------------------------------------------------------------

def _ekspor(label: str, waktu: str, sel: str = "2.784") -> str:
    return ("<html><body><h2>Statistik Pengelolaan Sampah</h2>"
            f"<p><strong>{label}</strong></p><p>Diekspor: {waktu}</p><p><em>Filter: Nasional (semua wilayah)</em></p>"
            "<h3>Ringkasan Indikator</h3><table><tr><th>Indikator</th><th>Nilai</th></tr>"
            "<tr><td>Jumlah TPA</td><td>507</td></tr></table>"
            "<h3>Detil Informasi</h3><table><tr><th>No</th><th>Provinsi</th><th>Kota/Kabupaten</th>"
            "<th>Timbulan (tpd)</th><th>% S. Terkelola</th></tr>"
            f"<tr><td>1</td><td>Jawa Barat</td><td>Kabupaten Bogor</td><td>{sel}</td><td>22,10</td></tr>"
            "<tr><td>2</td><td>DI Yogyakarta</td><td>Kota Yogyakarta</td><td>300</td><td>50,00</td></tr>"
            "<tr><td>3</td><td></td><td></td><td>0</td><td>0,00</td></tr>"
            "<tr><td>4</td><td>Provinsi Antah</td><td>Kab X</td><td>1</td><td>0,00</td></tr>"
            "</table></body></html>")


class TestSipsn(_DenganRujukan):
    def test_urai_ekspor_dan_sidik(self):
        a = sipsn.urai_ekspor(_ekspor("Data Terverifikasi Update 2026", "20/10/2026 10:33"))
        b = sipsn.urai_ekspor(_ekspor("Data Terverifikasi Update 2019", "20/10/2026 10:34"))
        c = sipsn.urai_ekspor(_ekspor("Data Terverifikasi Update 2026", "20/10/2026 10:33", sel="2.785"))
        self.assertEqual(a["label"], "Data Terverifikasi Update 2026")
        self.assertEqual(sipsn.tahun_label(a["label"]), "2026")
        self.assertEqual(sipsn.sidik_tabel(a), sipsn.sidik_tabel(b))  # label tahun saja yang berubah
        self.assertNotEqual(sipsn.sidik_tabel(a), sipsn.sidik_tabel(c))
        s = sipsn.sidik_tabel(a)
        self.assertEqual(sipsn.kode_rilis(a["label"], s), f"data-terverifikasi-update-2026@{s[:12]}")

    def test_baris_detil_apa_adanya_dan_periksa(self):
        u = sipsn.urai_ekspor(_ekspor("Data Terverifikasi Update 2026", "x"))
        baris = sipsn.baris_tabel(sipsn.tabel_judul(u, "Detil Informasi"))
        self.assertEqual(baris[0]["Timbulan (tpd)"], "2.784")  # tidak diubah menjadi angka
        self.assertEqual(baris[0]["_urutan"], 1)
        h = sipsn.periksa_detil(self.ruj, baris)
        self.assertEqual(h["provinsi_kosong"], 1)
        self.assertEqual(h["kabupaten_kosong"], 1)
        self.assertEqual(h["nama"]["cocok"], 2)
        self.assertEqual(h["nama"]["tidak_dikenal"], ["Provinsi Antah"])

    def test_nama_tabel_ringkasan(self):
        self.assertEqual(sipsn.nama_tabel_ringkasan("Ringkasan Indikator"), "ringkasan_indikator")
        self.assertEqual(sipsn.nama_tabel_ringkasan("Ringkasan Wilayah & Fasilitas"), "ringkasan_wilayah_fasilitas")

    def test_rawdata_beranda(self):
        html = ('<span>Data Terverifikasi Update 2026</span><script>var rawData = [{"kota_kabupaten":"Kabupaten '
                'Bogor","timbulan":2784.33}]; var x = 1;</script>')
        self.assertEqual(sipsn.urai_rawdata(html)[0]["timbulan"], 2784.33)
        self.assertEqual(sipsn.label_beranda(html), "Data Terverifikasi Update 2026")


# ---------------------------------------------------------------------------------------------------
# SIGN-SMART
# ---------------------------------------------------------------------------------------------------

#: Empat provinsi pemekaran 2022 yang di SIGN-SMART muncul berkunci ID-AC.
PAPUA_BARU = ("ID-PD", "ID-PS", "ID-PT", "ID-PE")


class TestSignSmart(_DenganRujukan):
    def _payload_salah_kunci(self) -> dict:
        lama = [w["kode_iso"] for w in self.terkini if w["kode_iso"] not in PAPUA_BARU]
        ids = lama + ["ID-AC"] * 4
        return {s: [{"id": k, "value": float(i)} for i, k in enumerate(ids)] for s in ("energy", "waste")}

    def test_id_ac_ganda_ditandai_resolver(self):
        js = self._payload_salah_kunci()
        h = signsmart.periksa_tahun(self.ruj, js)
        self.assertTrue(h["urutan_kunci_sama_antarsektor"])
        p = h["per_urutan"][0]
        self.assertEqual(p["duplikat"], {"ID-AC": 5})
        self.assertEqual(p["posisi_kunci_ganda"]["ID-AC"], [0, 34, 35, 36, 37])
        hilang = {int(x.split()[0]) for x in p["hilang"]}
        pecahan = {self.ruj.dari_iso(k) for k in PAPUA_BARU}
        self.assertEqual(len(pecahan), 4)
        self.assertEqual(hilang, pecahan | {self.ruj.dari_iso("ID-AC")})
        self.assertEqual(p["cocok"], 33)

    def test_baris_provinsi_menyimpan_urutan(self):
        js = self._payload_salah_kunci()
        rows = signsmart.baris_provinsi(js, "2022")
        ac = [r for r in rows if r["sektor"] == "energy" and r["id"] == "ID-AC"]
        self.assertEqual([r["urutan"] for r in ac], [0, 34, 35, 36, 37])
        self.assertEqual(len({(r["sektor"], r["urutan"]) for r in rows}), len(rows))
        self.assertTrue(signsmart.ada_data(js))
        self.assertFalse(signsmart.ada_data({"energy": [{"id": "ID-AC", "value": 0}]}))

    def test_beranda_tahun_penafian_nasional(self):
        html = ('<h5 class="modal-title">Disclaimer</h5></div><div class="modal-body"><p> Data bersifat dinamis '
                'dan belum melalui tahap QC/QA. </p>'
                '<select class="x" name="year" id="year"><option value="2000">2000</option>'
                '<option value="2025" selected>2025</option></select>')
        self.assertEqual(signsmart.tahun_beranda(html), ["2000", "2025"])
        self.assertIn("QC/QA", signsmart.penafian(html))
        nas = signsmart.baris_nasional({"data": [{"name": "Energi", "data": [452.55, 0]}], "categories": [2010, 2011]})
        self.assertEqual(nas[1], {"sektor": "Energi", "tahun": 2011, "nilai": 0, "urutan": 1})
        self.assertEqual(signsmart.kode_rilis("2022", "abcdef0123456789"), "emisi_prov/2022@abcdef012345")


# ---------------------------------------------------------------------------------------------------
# KKP
# ---------------------------------------------------------------------------------------------------

class TestKkp(_DenganRujukan):
    def test_payload_dan_tahun(self):
        self.assertEqual(kkp.data_payload({"status": 200, "data": [{"a": 1}]}), [{"a": 1}])
        self.assertEqual(kkp.data_payload({"data": None}), [])
        self.assertEqual(kkp.tahun_dari_seri([{"tahun": "2025"}, {"tahun": "2026*"}, {"tahun": None}]),
                         ["2025", "2026"])
        self.assertEqual(kkp.kode_rilis("nelayan_per_prov", "0123456789abcdef", "2023"),
                         "nelayan_per_prov/2023@0123456789ab")

    def test_periksa_baris_kode_dan_nama(self):
        rows = [{"id_prov": "31", "provinsi": "DKI JAKARTA", "tahun": "2023", "total": "109019"},
                {"id_prov": "94", "provinsi": "PAPUA", "tahun": "2023", "total": "1"},
                {"id_prov": "99", "provinsi": "ANTAH", "tahun": "2023", "total": "1"},
                {"id_prov": "-", "provinsi": "-", "tahun": "2023", "total": "0"}]
        h = kkp.periksa_baris(self.ruj, rows)
        self.assertEqual(h["kolom_kode"], "id_prov")
        self.assertEqual(h["bps"]["cocok"], 2)
        self.assertEqual(h["bps"]["tidak_dikenal"], ["99"])
        self.assertEqual(h["kode_bukan_angka"], ["-"])
        self.assertEqual(h["nama"]["tidak_dikenal"], ["-", "ANTAH"])
        b = kkp.baris_bronze(rows, "nelayan_per_prov", "2023")
        self.assertEqual(b[0]["_endpoint"], "nelayan_per_prov")
        self.assertEqual(b[2]["_urutan"], 3)

    def test_kawasan_nama_unik(self):
        rows = [{"provinsi": "Sumatera Barat", "luas": "39920"}, {"provinsi": "Sumatera Barat", "luas": "1"}]
        h = kkp.periksa_baris(self.ruj, rows, unik_nama=True)
        self.assertEqual(h["nama"]["duplikat"], {})
        self.assertEqual(h["nama"]["cocok"], 1)




class TestBnpbUnduhTangan(unittest.TestCase):
    """Berkas yang diunduh tangan lewat peramban dicocokkan ke resource CKAN dan diurai ke baris."""

    @staticmethod
    def _xlsx(baris: list[list]) -> bytes:
        import io

        import openpyxl

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Sheet1"
        for r in baris:
            ws.append(r)
        b = io.BytesIO()
        wb.save(b)
        return b.getvalue()

    def test_cocok_nama_url_id_dan_folder_drive(self):
        from pathlib import Path

        from sdg_gudang.akuisisi.konektor import bnpb

        res = {"id": "aefe8331-5962-4610-8b0c-2de637a336cd",
               "url": "https://data.bnpb.go.id/dataset/x/resource/aefe8331/download/"
                      "Jumlah%20Korban%20Meninggal%202025.xlsx"}
        berkas = [Path("/t/bnpb/lain.xlsx"), Path("/t/bnpb/Jumlah Korban Meninggal 2025.xlsx")]
        self.assertEqual(bnpb.cari_berkas_tangan(res, berkas).name, "Jumlah Korban Meninggal 2025.xlsx")
        self.assertEqual(bnpb.cari_berkas_tangan(res, [Path(f"/t/{res['id']}.xlsx")]).name, f"{res['id']}.xlsx")
        drive = {"id": "d1", "url": "https://drive.google.com/drive/folders/abc"}
        zipf = Path("/t/bnpb/jumlah-kejadian-dan-dampak-bencana-tahun-2015/folder.zip")
        self.assertEqual(bnpb.cari_berkas_tangan(drive, [zipf], "jumlah-kejadian-dan-dampak-bencana-tahun-2015"), zipf)
        self.assertIsNone(bnpb.cari_berkas_tangan(drive, [zipf], "dataset-lain"))

    def test_urai_xlsx_dan_zip(self):
        import io
        import zipfile

        from sdg_gudang.akuisisi.konektor import bnpb

        isi = self._xlsx([["Judul tabel", None, None], [None, None, None],
                          ["Kode", "Provinsi", "Meninggal"], ["11", "ACEH", 3], ["91", "PAPUA", None]])
        (lembar, kepala, baris), = bnpb.baris_xlsx(isi, "a.xlsx")
        self.assertEqual(kepala, ["Kode", "Provinsi", "Meninggal"])
        self.assertEqual(baris[0], {"Kode": "11", "Provinsi": "ACEH", "Meninggal": "3"})
        self.assertIsNone(baris[1]["Meninggal"])
        z = io.BytesIO()
        with zipfile.ZipFile(z, "w") as f:
            f.writestr("2015/prov.xlsx", isi)
            f.writestr("2015/catatan.txt", "abaikan")
        hasil = bnpb.baris_xlsx(z.getvalue(), "folder.zip")
        self.assertEqual(len(hasil), 1)
        self.assertTrue(hasil[0][0].startswith("2015/prov.xlsx:"))

if __name__ == "__main__":
    unittest.main()
