"""SDG KG M5 (brief 4 Bagian 5.1; RQ-B): tulang punggung M1 diperluas dengan sumber, seri, rilis, klaim, data
product, dan keterkaitan korelasi.

Simpul dan sisi baru (ontologi ``lk:``):

- ``lk:Sumber`` (kelas lisensi, keluarga), ``lk:Seri`` (``lk:diterbitkanOleh`` sumber, ``lk:mengukur`` indikator
  global dan indikator TPB, ``lk:satuan``), ``lk:Rilis`` (``dct:issued``, ``lk:jenisBuktiTanggal``,
  ``lk:menerbitkan`` seri, ``lk:merevisi`` rilis sebelumnya dalam keluarga yang sama);
- ``lk:Klaim`` (``lk:merujukIndikator``, ``lk:cocokDengan`` rilis, atau ``lk:statusVerifikasi``) dan ``lk:Dokumen``
  (``lk:menyebut`` klaim) dari korpus K-BRS M5;
- ``lk:DataProduct`` (``dcat:Dataset`` M4, ``lk:pilar``);
- ``lk:Keterkaitan``: korelasi Spearman antarindikator TPB pada nilai pilihan provinsi (n >= 30, |rho| >= 0,6),
  dengan ``lk:jenisBukti "korelasi_data_sendiri"`` dan komentar "korelasi, bukan sebab".

Graf divalidasi SHACL (bentuk M1 ditambah bentuk M5). Keluaran: ``artefak/kg/dp_kg.nt.gz`` (N-Triples terurut,
gzip mtime 0), ``artefak/kg/bentuk_m5.ttl``, dan ``data/manifests/gudang/m5_kg_ringkasan.json``.

    python3 -m sdg_gudang.gudang.kg
"""
import csv
import gzip
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from sdg_gudang import referensi as R
from sdg_gudang.akuisisi import inti as A

KELUAR = A.AKAR / "artefak" / "kg"
RINGKASAN = A.MANIFEST / "m5_kg_ringkasan.json"
KLAIM = A.MANIFEST / "m5_klaim_brs.csv"
MESH = A.AKAR / "config" / "mesh"

BENTUK_M5 = """@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix dct: <http://purl.org/dc/terms/> .
@prefix lk: <https://sd.itera.ac.id/kg/ontologi#> .

lk:BentukSumber a sh:NodeShape ;
  sh:targetClass lk:Sumber ;
  sh:property [ sh:path lk:kelasLisensi ; sh:minCount 1 ; sh:maxCount 1 ; sh:in ( "A" "A-SA" "B" "C" ) ] .

lk:BentukSeri a sh:NodeShape ;
  sh:targetClass lk:Seri ;
  sh:property [ sh:path lk:diterbitkanOleh ; sh:minCount 1 ; sh:maxCount 1 ; sh:class lk:Sumber ] ;
  sh:property [ sh:path lk:satuan ; sh:minCount 1 ] .

lk:BentukRilis a sh:NodeShape ;
  sh:targetClass lk:Rilis ;
  sh:property [ sh:path dct:issued ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:date ] ;
  sh:property [ sh:path lk:jenisBuktiTanggal ; sh:minCount 1 ; sh:maxCount 1 ;
                sh:in ( "rilis_resmi" "pembaruan_sumber" "tanggal_unduh_berubah" "tanggal_unduh" "tidak_diketahui" ) ] ;
  sh:property [ sh:path lk:dariSumber ; sh:minCount 1 ; sh:maxCount 1 ; sh:class lk:Sumber ] ;
  sh:property [ sh:path lk:merevisi ; sh:class lk:Rilis ] .

lk:BentukKlaim a sh:NodeShape ;
  sh:targetClass lk:Klaim ;
  sh:property [ sh:path lk:merujukIndikator ; sh:minCount 1 ; sh:maxCount 1 ] ;
  sh:or ( [ sh:property [ sh:path lk:cocokDengan ; sh:minCount 1 ; sh:maxCount 1 ; sh:class lk:Rilis ] ]
          [ sh:property [ sh:path lk:statusVerifikasi ; sh:minCount 1 ; sh:in ( "tidak_terverifikasi" ) ] ] ) .

lk:BentukKeterkaitan a sh:NodeShape ;
  sh:targetClass lk:Keterkaitan ;
  sh:property [ sh:path lk:antara ; sh:minCount 2 ; sh:maxCount 2 ] ;
  sh:property [ sh:path lk:jenisBukti ; sh:minCount 1 ; sh:in ( "korelasi_data_sendiri" "literatur" ) ] ;
  sh:property [ sh:path rdfs:comment ; sh:minCount 1 ] .

lk:BentukDataProduct a sh:NodeShape ;
  sh:targetClass lk:DataProduct ;
  sh:property [ sh:path lk:pemilik ; sh:minCount 1 ] .
"""


def slug(t: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.:-]+", "_", t)


def ambil(cur, sql: str) -> list[tuple]:
    cur.execute(sql)
    return cur.fetchall()


def deret_indikator(cur, tabel: str = "nilai_pilihan") -> tuple[dict, dict]:
    """Satu deret {(wilayah, periode): nilai} per indikator TPB pada nilai pilihan provinsi (rincian total, periode
    tahunan): konsep padanan bila ada, selain itu konsep dengan titik terbanyak. Kembalikan (deret, konsep terpilih)."""
    rows = ambil(cur, f"""
        select k.indikator_id, n.konsep_id, n.wilayah_kode, n.periode, n.nilai_angka
        from gold.{tabel} n join gold.dim_konsep k on k.konsep_id = n.konsep_id
        where n.wilayah_kode <> 9999 and n.rincian = 'total' and regexp_like(n.periode, '^[0-9]{{4}}$')
          and k.indikator_id like 'tpb:%' and k.indikator_id not like 'tpb:rencana%'""")
    per_konsep = defaultdict(dict)
    ind_konsep = defaultdict(set)
    for ind, konsep, w, p, v in rows:
        per_konsep[konsep][(w, p)] = v
        ind_konsep[ind].add(konsep)
    pilih = {ind: max(ks, key=lambda k: (k == ind, len(per_konsep[k]), k)) for ind, ks in ind_konsep.items()}
    return {ind: per_konsep[k] for ind, k in pilih.items()}, pilih


def korelasi(cur, ambang: float = 0.6, n_min: int = 30, tabel: str = "nilai_pilihan") -> list[dict]:
    """Spearman antarindikator TPB pada deret ``deret_indikator``; pasangan indikator yang sama dibuang.
    ``tabel="nilai_pilihan_tayang"`` membatasi ke sumber yang boleh tayang (brief 5, praregistrasi Bagian 3)."""
    seri, _ = deret_indikator(cur, tabel)

    def peringkat(xs):
        urut = sorted(range(len(xs)), key=lambda i: xs[i])
        r = [0.0] * len(xs)
        i = 0
        while i < len(urut):
            j = i
            while j + 1 < len(urut) and xs[urut[j + 1]] == xs[urut[i]]:
                j += 1
            for k in range(i, j + 1):
                r[urut[k]] = (i + j) / 2
            i = j + 1
        return r

    out = []
    konsep = sorted(seri)
    for i, a in enumerate(konsep):
        for b in konsep[i + 1:]:
            kunci = sorted(seri[a].keys() & seri[b].keys())
            if len(kunci) < n_min:
                continue
            ra, rb = peringkat([seri[a][k] for k in kunci]), peringkat([seri[b][k] for k in kunci])
            ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
            cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
            va, vb = sum((x - ma) ** 2 for x in ra), sum((y - mb) ** 2 for y in rb)
            if va == 0 or vb == 0:
                continue
            rho = cov / (va * vb) ** 0.5
            if abs(rho) >= ambang:
                out.append({"a": a, "b": b, "rho": round(rho, 4), "n": len(kunci)})
    return out


def bangun(cur) -> tuple:
    import rdflib
    from rdflib.namespace import DCAT, DCTERMS, RDF, RDFS, SKOS, XSD

    LK = rdflib.Namespace(R.NS_KG + "ontologi#")
    TPB = rdflib.Namespace(R.NS_KG + "tpb/")
    SB = rdflib.Namespace(R.NS_KG + "sumber/")
    SR = rdflib.Namespace(R.NS_KG + "seri/")
    RL = rdflib.Namespace(R.NS_KG + "rilis/")
    KL = rdflib.Namespace(R.NS_KG + "klaim/")
    DK = rdflib.Namespace(R.NS_KG + "dokumen/")
    KT = rdflib.Namespace(R.NS_KG + "keterkaitan/")
    PIL = rdflib.Namespace(R.NS_KG + "pilar/")
    SDGO = rdflib.Namespace("http://metadata.un.org/sdg/ontology#")

    g = rdflib.Graph()
    g.parse(R.KELUAR / "kg" / "sdg_spine.nt", format="nt")
    for p, ns in (("lk", LK), ("tpb", TPB), ("sumber", SB), ("seri", SR), ("rilis", RL), ("klaim", KL),
                  ("dokumen", DK), ("keterkaitan", KT), ("dcat", DCAT)):
        g.bind(p, ns)
    indikator_iri = {str(n): s for s in g.subjects(RDF.type, SDGO.Indicator) for n in g.objects(s, SKOS.notation)}

    for sumber, keluarga, kelas in ambil(cur, "select sumber, keluarga, kelas_lisensi from gold.dim_sumber"):
        g.add((SB[sumber], RDF.type, LK.Sumber))
        g.add((SB[sumber], LK.keluarga, rdflib.Literal(keluarga)))
        g.add((SB[sumber], LK.kelasLisensi, rdflib.Literal(kelas)))

    seri_rows = ambil(cur, """select sumber, seri_kode, max(indikator_id), max(kode_global), max(satuan_id)
                              from gold.fakta_observasi group by sumber, seri_kode""")
    for sumber, seri, ind, kode, satuan in seri_rows:
        node = SR[slug(f"{sumber}/{seri}")]
        g.add((node, RDF.type, LK.Seri))
        g.add((node, SKOS.notation, rdflib.Literal(seri)))
        g.add((node, LK.diterbitkanOleh, SB[sumber]))
        g.add((node, LK.satuan, rdflib.Literal(satuan)))
        for k in (kode or "").split("|"):
            if k in indikator_iri:
                g.add((node, LK.mengukur, indikator_iri[k]))
        if ind and ind.startswith("tpb:") and ind[4:] and not ind.startswith("tpb:rencana"):
            g.add((node, LK.mengukur, TPB[ind[4:]]))

    for rid, sumber, tgl, bukti in ambil(cur, """select r.rilis_id, r.sumber, cast(r.tanggal_efektif as varchar),
                                                 r.jenis_bukti_tanggal from gold.dim_rilis r"""):
        node = RL[slug(rid)]
        g.add((node, RDF.type, LK.Rilis))
        g.add((node, SKOS.notation, rdflib.Literal(rid)))
        g.add((node, DCTERMS.issued, rdflib.Literal(tgl, datatype=XSD.date)))
        g.add((node, LK.jenisBuktiTanggal, rdflib.Literal(bukti)))
        g.add((node, LK.dariSumber, SB[sumber]))
    for rid, sumber, seri in ambil(cur, "select distinct rilis_id, sumber, seri_kode from gold.fakta_observasi"):
        g.add((RL[slug(rid)], LK.menerbitkan, SR[slug(f"{sumber}/{seri}")]))
    for lama, baru in ambil(cur, """select distinct rilis_id, digantikan_oleh_rilis from gold.fakta_observasi
                                     where digantikan_oleh_rilis is not null and digantikan_oleh_rilis <> rilis_id"""):
        g.add((RL[slug(baru)], LK.merevisi, RL[slug(lama)]))

    if KLAIM.exists():
        with KLAIM.open(encoding="utf-8") as f:
            for i, r in enumerate(csv.DictReader(f)):
                node = KL[f"{r['dokumen_id']}/{i}"]
                g.add((node, RDF.type, LK.Klaim))
                g.add((DK[r["dokumen_id"]], RDF.type, LK.Dokumen))
                g.add((DK[r["dokumen_id"]], LK.menyebut, node))
                g.add((DK[r["dokumen_id"]], DCTERMS.issued, rdflib.Literal(r["tanggal_terbit"], datatype=XSD.date)))
                g.add((node, LK.merujukIndikator, TPB[r["konsep_id"][4:]]))
                g.add((node, LK.nilai, rdflib.Literal(r["nilai"])))
                g.add((node, LK.periode, rdflib.Literal(r["periode"])))
                g.add((node, LK.labelAsof, rdflib.Literal(r["label_asof"])))
                if r["label_asof"].startswith("cocok") and r["rilis_asof"]:
                    g.add((node, LK.cocokDengan, RL[slug(r["rilis_asof"])]))
                else:
                    g.add((node, LK.statusVerifikasi, rdflib.Literal("tidak_terverifikasi")))

    for p in sorted(MESH.glob("*.yaml")):
        import yaml

        y = yaml.safe_load(p.read_text("utf-8"))
        node = rdflib.URIRef(f"https://sd.itera.ac.id/kg/gudang/{y['nama']}")
        g.add((node, RDF.type, LK.DataProduct))
        g.add((node, RDF.type, DCAT.Dataset))
        g.add((node, DCTERMS.title, rdflib.Literal(y["judul"], lang="id")))
        g.add((node, LK.pemilik, rdflib.Literal(y["pemilik"]["nama"])))
        if y.get("pilar"):
            g.add((node, LK.pilar, PIL[y["pilar"]]))

    kor = korelasi(cur)
    for k in kor:
        node = KT[hashlib.sha256(f"{k['a']}|{k['b']}".encode()).hexdigest()[:16]]
        g.add((node, RDF.type, LK.Keterkaitan))
        for x in (k["a"], k["b"]):
            g.add((node, LK.antara, TPB[x[4:]]))
        g.add((node, LK.rho, rdflib.Literal(k["rho"], datatype=XSD.decimal)))
        g.add((node, LK.n, rdflib.Literal(k["n"], datatype=XSD.integer)))
        g.add((node, LK.arah, rdflib.Literal("positif" if k["rho"] > 0 else "negatif")))
        g.add((node, LK.jenisBukti, rdflib.Literal("korelasi_data_sendiri")))
        g.add((node, RDFS.comment, rdflib.Literal(
            "korelasi Spearman antarprovinsi dan antartahun pada nilai pilihan; korelasi, bukan sebab", lang="id")))
    return g, kor


def cakupan(g) -> dict:
    """RQ-B: per tujuan, proporsi indikator TPB katalog yang tertaut ke indikator global, seri, dan rilis."""
    import rdflib
    from rdflib.namespace import RDF, SKOS

    LK = rdflib.Namespace(R.NS_KG + "ontologi#")
    global_ke_seri = defaultdict(set)
    tpb_ke_seri = defaultdict(set)
    for s, o in g.subject_objects(LK.mengukur):
        (tpb_ke_seri if "/tpb/" in str(o) else global_ke_seri)[o].add(s)
    seri_berrilis = set(g.objects(None, LK.menerbitkan))
    per = defaultdict(lambda: {"indikator": 0, "global": 0, "seri_langsung": 0, "seri": 0, "rilis": 0})
    for ind in g.subjects(RDF.type, LK.IndikatorTPB):
        tujuan = str(next(g.objects(ind, LK.tujuan))).rsplit("/", 1)[-1]
        glob = set()
        for p in (SKOS.exactMatch, LK.proksiUntuk, LK.pengayaanUntuk, LK.kodeSamaDengan):
            glob |= set(g.objects(ind, p))
        langsung = tpb_ke_seri.get(ind, set())
        seri = langsung | set().union(*(global_ke_seri.get(x, set()) for x in glob)) if glob else langsung
        c = per[int(tujuan)]
        c["indikator"] += 1
        c["global"] += bool(glob)
        c["seri_langsung"] += bool(langsung)
        c["seri"] += bool(seri)
        c["rilis"] += bool(seri & seri_berrilis)
    return dict(sorted(per.items()))


def jalankan() -> dict:
    import rdflib
    from pyshacl import validate

    from sdg_gudang.gudang.sidik import koneksi

    g, kor = bangun(koneksi().cursor())
    bentuk = rdflib.Graph().parse(data=R.BENTUK_TTL, format="turtle")
    bentuk.parse(data=BENTUK_M5, format="turtle")
    ok, laporan, teks = validate(g, shacl_graph=bentuk, inference="none", advanced=True)
    from rdflib.namespace import SH

    pelanggaran = len(list(laporan.subjects(predicate=SH.resultSeverity)))
    KELUAR.mkdir(parents=True, exist_ok=True)
    nt = sorted(set(g.serialize(format="nt").splitlines()) - {""})
    isi = gzip.compress(("\n".join(nt) + "\n").encode("utf-8"), compresslevel=9, mtime=0)
    (KELUAR / "dp_kg.nt.gz").write_bytes(isi)
    (KELUAR / "bentuk_m5.ttl").write_text(BENTUK_M5, "utf-8")
    if not ok:
        (KELUAR / "laporan_shacl.txt").write_text(teks, "utf-8")
    cak = cakupan(g)
    jumlah = {k: sum(v[k] for v in cak.values()) for k in ("indikator", "global", "seri_langsung", "seri", "rilis")}
    out = {"dibangun_pada": A.sekarang(), "tripel": len(nt), "sha256_nt_gz": hashlib.sha256(isi).hexdigest(),
           "shacl_lulus": bool(ok), "pelanggaran_shacl": pelanggaran, "keterkaitan_korelasi": len(kor),
           "cakupan_jumlah": jumlah, "cakupan_per_tujuan": cak,
           "keterkaitan": sorted(kor, key=lambda k: -abs(k["rho"]))[:50]}
    RINGKASAN.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", "utf-8")
    return out


def get_related(g, indikator_iri: str) -> list[dict]:
    """Untuk tool Bravais ``get_related``: indikator sasaran yang sepadan, setujuan, atau berkorelasi."""
    q = """
    PREFIX lk: <https://sd.itera.ac.id/kg/ontologi#>
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    SELECT ?lain ?hubungan ?rho WHERE {
      { ?k a lk:Keterkaitan ; lk:antara ?ind, ?lain ; lk:rho ?rho . FILTER(?lain != ?ind) BIND("korelasi" AS ?hubungan) }
      UNION { ?ind lk:tujuan ?t . ?lain lk:tujuan ?t . FILTER(?lain != ?ind) BIND("setujuan" AS ?hubungan) }
    }"""
    return [{"lain": str(r.lain), "hubungan": str(r.hubungan), "rho": float(r.rho) if r.rho else None}
            for r in g.query(q, initBindings={"ind": __import__("rdflib").URIRef(indikator_iri)})]


def main() -> int:
    out = jalankan()
    print(json.dumps({k: out[k] for k in ("tripel", "shacl_lulus", "pelanggaran_shacl", "keterkaitan_korelasi",
                                          "cakupan_jumlah")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
