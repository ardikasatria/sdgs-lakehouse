"""Bentuk SHACL M5 menolak graf yang melanggar (seri tanpa sumber, klaim tanpa rilis atau status)."""
import unittest

import rdflib
from pyshacl import validate

from sdg_gudang import referensi as R
from sdg_gudang.gudang.kg import BENTUK_M5

LK = rdflib.Namespace(R.NS_KG + "ontologi#")
BENTUK = rdflib.Graph().parse(data=BENTUK_M5, format="turtle")


def sah(g):
    return validate(g, shacl_graph=BENTUK, advanced=True)[0]


class UjiBentukM5(unittest.TestCase):
    def test_klaim(self):
        g = rdflib.Graph()
        k = rdflib.URIRef("urn:klaim")
        g.add((k, rdflib.RDF.type, LK.Klaim))
        g.add((k, LK.merujukIndikator, rdflib.URIRef("urn:i")))
        self.assertFalse(sah(g))
        g.add((k, LK.statusVerifikasi, rdflib.Literal("tidak_terverifikasi")))
        self.assertTrue(sah(g))

    def test_seri_dan_sumber(self):
        g = rdflib.Graph()
        s, b = rdflib.URIRef("urn:seri"), rdflib.URIRef("urn:sumber")
        g.add((s, rdflib.RDF.type, LK.Seri))
        g.add((s, LK.satuan, rdflib.Literal("persen")))
        self.assertFalse(sah(g))
        g.add((b, rdflib.RDF.type, LK.Sumber))
        g.add((b, LK.kelasLisensi, rdflib.Literal("Z")))
        g.add((s, LK.diterbitkanOleh, b))
        self.assertFalse(sah(g))  # kelas lisensi di luar A/A-SA/B/C
        g.set((b, LK.kelasLisensi, rdflib.Literal("A")))
        self.assertTrue(sah(g))


if __name__ == "__main__":
    unittest.main()
