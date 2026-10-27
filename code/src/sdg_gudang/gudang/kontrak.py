"""Pembangkit kontrak data product (brief 4 Bagian 3.4, prinsip platform swalayan).

Dari setiap ``config/mesh/<produk>.yaml`` dibangkitkan:

- ``dbt/gudang_sdg/models/dp/<produk>*.sql``: model dbt menurut ``jenis`` (pilar, referensi, rilis);
- ``dbt/gudang_sdg/models/dp/<produk>.yml``: kontrak skema yang ditegakkan dbt (nama dan tipe kolom),
  uji kunci, uji aturan global federasi (wilayah, satuan, konsep, kelas tayang), dan uji SLA kesegaran;
- ``artefak/mesh/<produk>.jsonld``: rekaman DCAT dataset untuk repositori metadata (unit 009).

Menambah data product baru cukup dengan satu berkas YAML. Berkas keluaran di-commit; ``--cek`` gagal bila
keluaran tidak sama dengan hasil bangkitan (uji di CI).

    python3 -m sdg_gudang.gudang.kontrak [--cek]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

AKAR = Path(__file__).resolve().parents[3]
MESH = AKAR / "config" / "mesh"
DP = AKAR / "dbt" / "gudang_sdg" / "models" / "dp"
DCAT = AKAR / "artefak" / "mesh"
BASIS_IRI = "https://sd.itera.ac.id/kg/gudang/"

KOLOM_PILAR = [
    ("konsep_id", "varchar", "konsep observasi (S06)"),
    ("indikator_id", "varchar", "indikator TPB nasional bila konsep terpetakan"),
    ("kode_global", "varchar", "kode indikator SDG global"),
    ("tujuan", "integer", "tujuan TPB"),
    ("wilayah_kode", "integer", "kode wilayah dp_referensi"),
    ("nama_wilayah", "varchar", "nama wilayah versi terkini"),
    ("periode", "varchar", "periode kanonik"),
    ("rincian", "varchar", "rincian kanonik; total = semua total"),
    ("nilai", "varchar", "nilai desimal kanonik dalam satuan_id"),
    ("nilai_angka", "double", "nilai sebagai bilangan"),
    ("satuan_id", "varchar", "satuan kanonik"),
    ("sumber", "varchar", "sumber nilai pilihan"),
    ("rilis_id", "varchar", "rilis asal"),
    ("berlaku_sejak", "date", "tanggal efektif rilis asal"),
    ("sifat", "varchar", "resmi, disesuaikan, estimasi, model, tidak_diketahui"),
    ("prioritas", "integer", "prioritas aturan nilai pilihan"),
    ("jumlah_calon", "bigint", "jumlah observasi calon"),
    ("alasan_pilihan", "varchar", "alasan pilihan"),
    ("tanggal_acuan", "date", "tanggal acuan as-of"),
]


def sql_pilar(p: dict) -> str:
    tujuan = ", ".join(str(t) for t in p["tujuan"])
    tingkat = "= 9999" if p["tingkat"] == "nasional" else "<> 9999"
    kolom = ",\n       ".join(f"n.{k}" if k not in ("indikator_id", "kode_global", "tujuan", "nama_wilayah") else
                              {"indikator_id": "k.indikator_id", "kode_global": "k.kode_global", "tujuan": "k.tujuan",
                               "nama_wilayah": "w.nama as nama_wilayah"}[k] for k, _, _ in KOLOM_PILAR)
    return (f"-- Dibangkitkan dari config/mesh/{p['nama']}.yaml oleh sdg_gudang.gudang.kontrak; jangan disunting.\n"
            f"-- {p['judul']}\n"
            f"select {kolom}\n"
            "from {{ ref('nilai_pilihan_tayang') }} n\n"
            "join {{ ref('dim_konsep') }} k on k.konsep_id = n.konsep_id\n"
            "left join {{ ref('dim_wilayah') }} w on w.wilayah_kode = n.wilayah_kode and w.terkini\n"
            f"where k.tujuan in ({tujuan}) and n.wilayah_kode {tingkat}\n")


SQL_REFERENSI = {
    "wilayah": "select * from {{ ref('dim_wilayah') }}",
    "indikator": "select * from {{ ref('dim_indikator') }}",
    "satuan": "select * from {{ ref('dim_satuan') }}",
    "konsep": "select * from {{ ref('dim_konsep') }}",
}
SQL_RILIS = ("select r.*, s.keluarga, s.boleh_tayang\nfrom {{ ref('dim_rilis') }} r\n"
             "join {{ ref('dim_sumber') }} s on s.sumber = r.sumber")


def model_pilar(p: dict) -> dict:
    uji_kolom = {"wilayah_kode": [{"relationships": {"arguments": {"to": "ref('dim_wilayah')", "field": "wilayah_kode"}}}],
                 "satuan_id": [{"relationships": {"arguments": {"to": "ref('dim_satuan')", "field": "satuan_id"}}}],
                 "konsep_id": [{"relationships": {"arguments": {"to": "ref('dim_konsep')", "field": "konsep_id"}}}],
                 "nilai_angka": ["not_null"], "sumber": ["not_null"], "rilis_id": ["not_null"]}
    kolom = []
    for k, tipe, ket in KOLOM_PILAR:
        c = {"name": k, "data_type": tipe, "description": ket}
        if k in uji_kolom:
            c["data_tests"] = uji_kolom[k]
        kolom.append(c)
    uji = [{"kunci_unik": {"arguments": {"kolom": "konsep_id, wilayah_kode, periode, rincian"}}},
           {"hanya_tayang": {}},
           {"baris_minimum": {"arguments": {"n": p["kualitas"]["baris_minimum"]}}}]
    if p["sla"].get("kesegaran_hari"):
        uji.append({"segar": {"arguments": {"kolom": "berlaku_sejak", "hari": p["sla"]["kesegaran_hari"]},
                              "config": {"severity": "warn"}}})
    return {"name": p["nama"], "description": p["deskripsi"],
            "config": {"contract": {"enforced": True}, "meta": meta(p)}, "data_tests": uji, "columns": kolom}


def meta(p: dict) -> dict:
    return {"domain": p["domain"], "pemilik": p["pemilik"]["nama"], "peran_pemilik": p["pemilik"]["peran"],
            "kanal_masalah": p["kanal_masalah"], "sla_kesegaran_hari": p["sla"].get("kesegaran_hari"),
            "berkas_konfigurasi": f"config/mesh/{p['nama']}.yaml"}


def bangkitkan(p: dict) -> dict[Path, str]:
    out: dict[Path, str] = {}
    if p["jenis"] == "pilar":
        out[DP / f"{p['nama']}.sql"] = sql_pilar(p)
        models = [model_pilar(p)]
    elif p["jenis"] == "referensi":
        models = []
        for bagian, sql in SQL_REFERENSI.items():
            nama = f"{p['nama']}_{bagian}"
            out[DP / f"{nama}.sql"] = (f"-- Dibangkitkan dari config/mesh/{p['nama']}.yaml; jangan disunting.\n{sql}\n")
            models.append({"name": nama, "description": f"{p['judul']}: {bagian}",
                           "config": {"meta": meta(p)},
                           "data_tests": [{"baris_minimum": {"arguments": {"n": p["kualitas"]["baris_minimum"]}}}]})
    elif p["jenis"] == "rilis":
        out[DP / f"{p['nama']}.sql"] = f"-- Dibangkitkan dari config/mesh/{p['nama']}.yaml; jangan disunting.\n{SQL_RILIS}\n"
        uji = [{"baris_minimum": {"arguments": {"n": p["kualitas"]["baris_minimum"]}}}]
        if p["sla"].get("kesegaran_hari"):
            uji.append({"segar": {"arguments": {"kolom": "snapshot_pertama", "hari": p["sla"]["kesegaran_hari"]},
                                  "config": {"severity": "warn"}}})
        models = [{"name": p["nama"], "description": p["deskripsi"], "config": {"meta": meta(p)}, "data_tests": uji,
                   "columns": [{"name": "rilis_id", "data_tests": ["unique", "not_null"]}]}]
    else:
        raise ValueError(f"jenis data product tidak dikenal: {p['jenis']}")
    kepala = f"# Dibangkitkan dari config/mesh/{p['nama']}.yaml oleh sdg_gudang.gudang.kontrak; jangan disunting.\n"
    out[DP / f"{p['nama']}.yml"] = kepala + yaml.safe_dump({"version": 2, "models": models}, sort_keys=False,
                                                           allow_unicode=True, width=110)
    out[DCAT / f"{p['nama']}.jsonld"] = json.dumps(dcat(p, [m["name"] for m in models]), indent=1,
                                                   ensure_ascii=False) + "\n"
    return out


def dcat(p: dict, tabel: list[str]) -> dict:
    """Rekaman DCAT 3 untuk satu data product; distribusi = tabel Iceberg ``dp.<tabel>``."""
    return {
        "@context": {"dcat": "http://www.w3.org/ns/dcat#", "dct": "http://purl.org/dc/terms/",
                     "foaf": "http://xmlns.com/foaf/0.1/", "dqv": "http://www.w3.org/ns/dqv#"},
        "@id": f"{BASIS_IRI}{p['nama']}", "@type": "dcat:Dataset",
        "dct:title": p["judul"], "dct:description": p["deskripsi"], "dct:identifier": p["nama"],
        "dcat:theme": f"pilar:{p['domain']}" if p["jenis"] == "pilar" else "platform",
        "dcat:keyword": ["SDG", "TPB", p["domain"]] + [f"tujuan {t}" for t in p.get("tujuan", [])],
        "dct:publisher": {"@type": "foaf:Agent", "foaf:name": "Institut Teknologi Sumatera, Sains Data"},
        "dcat:contactPoint": {"@type": "foaf:Agent", "foaf:name": p["pemilik"]["nama"],
                              "dct:description": p["pemilik"]["peran"]},
        "dct:license": p["lisensi_keluaran"],
        "dct:accrualPeriodicity": (f"SLA kesegaran {p['sla']['kesegaran_hari']} hari"
                                   if p["sla"].get("kesegaran_hari") else "tidak terjadwal"),
        "dcat:distribution": [{"@type": "dcat:Distribution", "dct:title": t,
                               "dcat:accessURL": f"trino://iceberg/dp/{t}", "dct:format": "Apache Iceberg"}
                              for t in tabel],
        "dqv:hasQualityAnnotation": {"dct:description": f"uji kontrak dbt di dbt/gudang_sdg/models/dp/{p['nama']}.yml"},
    }


def semua() -> dict[Path, str]:
    out: dict[Path, str] = {}
    for f in sorted(MESH.glob("*.yaml")):
        out |= bangkitkan(yaml.safe_load(f.read_text("utf-8")))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Bangkitkan kontrak data product")
    ap.add_argument("--cek", action="store_true", help="gagal bila keluaran yang ada berbeda dari bangkitan")
    a = ap.parse_args(argv)
    out = semua()
    if a.cek:
        beda = [str(p.relative_to(AKAR)) for p, isi in out.items() if not p.exists() or p.read_text("utf-8") != isi]
        print("\n".join(beda) or "kontrak mutakhir")
        return 1 if beda else 0
    for p, isi in out.items():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(isi, "utf-8")
    print(f"{len(out)} berkas dibangkitkan dari {len(list(MESH.glob('*.yaml')))} data product")
    return 0


if __name__ == "__main__":
    sys.exit(main())
