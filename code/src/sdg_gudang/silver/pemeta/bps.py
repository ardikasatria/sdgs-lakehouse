"""Pemeta Silver keluarga BPS: tabel WebAPI dinamis dan statis.

- S01: ``wilayah_id`` dinamis adalah kode BPS empat digit; kode kabupaten/kota (dua digit akhir bukan 00)
  berada di luar tingkat yang dimuat. Tabel statis memakai nama provinsi.
- S02: kolom ``periode`` WebAPI: Tahun/Tahunan -> tahun; Februari/Agustus -> bulan; Semester 1 (Maret) dan
  Semester 2 (September) -> semester dengan bulan acuan.
- S04: kolom ``satuan`` baris, lalu satuan katalog tabel; keduanya kosong -> ``tidak_ada`` (satuan tidak
  dinyatakan sumber). Tabel statis: satuan per tabel di ``SATUAN_STATIS``.
- S05: ``turvar`` (dinamis) atau kolom rincian tabel statis; Tidak ada, Jumlah, dan Perkotaan+Perdesaan = total.
- S06: tabel -> indikator TPB lewat ``peta_tabel_indikator`` M1. S07: sifat ``resmi``.
"""
from __future__ import annotations

import csv
import re
from functools import lru_cache

from sdg_gudang import referensi as R
from sdg_gudang.akuisisi import inti as A

from .. import inti as S

METADATA = {"katalog_tabel", "publikasi"}
TOTAL = {"turvar": {"Perkotaan+Perdesaan"}, "daerah": {"Perkotaan + Perdesaan"},
         "jenis_kelamin": {"Laki-laki+Perempuan"}, "tutupan": {"jumlah"}, "bahan_bakar": {"Jumlah"}}
SATUAN_STATIS = {
    ("sdg15_tutupan_hutan", "luas_ribu_ha"): "ribu hektar", ("sdg15_tutupan_hutan", "persen"): "persen",
    ("sdg4_amh_rinci", ""): "persen", ("sdg7_bahan_bakar", ""): "persen",
}
KOLOM_STATIS_BUKAN_RINCIAN = {"nilai", "tabel", "tahun", "wilayah", "catatan", "cek", "ukuran"}


@lru_cache(maxsize=1)
def peta_tabel() -> dict[str, dict]:
    with (R.KELUAR / "peta_tabel_indikator.csv").open(encoding="utf-8") as f:
        return {r["tabel"]: r for r in csv.DictReader(f)}


@lru_cache(maxsize=1)
def satuan_katalog() -> dict[str, str]:
    t = A.baca_bronze("bps", "katalog_tabel")
    return {r["tabel"]: r["satuan"] or "" for r in t.select(["tabel", "satuan"]).to_pylist()}


def periode(tahun: str, teks: str) -> dict:
    th = S.periode_tahun(tahun)
    t = (teks or "").strip()
    if t in ("Tahun", "Tahunan", ""):
        return {"periode": th, "jenis_periode": "tahun"}
    if t.lower() in S.BULAN:
        b = S.BULAN[t.lower()]
        return {"periode": f"{th}-{b:02d}", "jenis_periode": "bulan", "bulan_acuan": str(b)}
    m = re.fullmatch(r"Semester ([12]) \((\w+)\)", t)
    if m and m.group(2).lower() in S.BULAN:
        return {"periode": f"{th}-S{m.group(1)}", "jenis_periode": "semester",
                "bulan_acuan": str(S.BULAN[m.group(2).lower()])}
    raise S.Karantina("periode_tidak_terurai", "S02", f"{tahun!r} {teks!r}")


def konsep(ctx: S.Konteks, tabel: str, seri_kode: str) -> dict:
    p = peta_tabel().get(tabel, {})
    ind = f"tpb:{p['kode_tpb']}" if p.get("kode_tpb") else ""
    return ctx.konsep("bps", seri_kode, p.get("kode_global", ""), ind)


def satuan(teks: str) -> S.SatuanKanonik:
    return S.SatuanKanonik("tidak_ada") if not (teks or "").strip() else S.satuan_teks(teks)


def dinamis(b: dict, ctx: S.Konteks):
    seri = f"var{b['var_id']}"
    teks = {"wilayah": b["wilayah_id"], "periode": f"{b['tahun']} {b['periode']}", "nilai": b["nilai"],
            "satuan": b["satuan"]}

    def isi():
        kode = b["wilayah_id"].strip()
        if len(kode) == 4 and kode != "9999" and not kode.endswith("00"):
            raise S.DiLuar("kabkota")
        w = ctx.rujukan.wilayah("bps", kode)
        nilai, desimal = S.urai_nilai(b["nilai"])
        st = satuan(b["satuan"] or satuan_katalog().get(b["tabel"], ""))
        return S.obs(seri_kode=seri, **konsep(ctx, b["tabel"], seri), wilayah_kode=w,
                     tingkat=ctx.rujukan.tingkat(w), sistem_wilayah="bps", **periode(b["tahun"], b["periode"]),
                     rincian=S.rincian({"turvar": b["turvar"]}, TOTAL), nilai=S.kali(nilai, st.faktor),
                     desimal=desimal, satuan_id=st.satuan_id, satuan_sumber=b["satuan"], faktor_satuan=st.faktor,
                     sifat="resmi", aturan_silver="S01;S02;S03;S04;S05;S06;S07")

    yield S.sel(seri, teks, isi)


def statis(b: dict, ctx: S.Konteks):
    tabel = b["tabel"]
    seri = f"tabel:{tabel}" + (f":{b['ukuran']}" if b.get("ukuran") else "")
    teks = {"wilayah": b["wilayah"], "periode": b["tahun"], "nilai": b["nilai"], "satuan": b.get("ukuran", "")}

    def isi():
        w = ctx.rujukan.wilayah("nama", b["wilayah"])
        nilai, desimal = S.urai_nilai(b["nilai"])
        teks_satuan = SATUAN_STATIS.get((tabel, b.get("ukuran") or ""))
        if teks_satuan is None:
            raise S.Karantina("satuan_tidak_dikenal", "S04", f"{tabel} ukuran {b.get('ukuran')!r}")
        st = S.satuan_teks(teks_satuan)
        dim = {k: v for k, v in b.items() if k not in KOLOM_STATIS_BUKAN_RINCIAN and not k.startswith("_")}
        return S.obs(seri_kode=seri, **konsep(ctx, tabel, seri), wilayah_kode=w, tingkat=ctx.rujukan.tingkat(w),
                     sistem_wilayah="nama", periode=S.periode_tahun(b["tahun"]),
                     rincian=S.rincian(dim, TOTAL), nilai=nilai, desimal=desimal, satuan_id=st.satuan_id,
                     satuan_sumber=teks_satuan, sifat="resmi",
                     cakupan_parsial=b.get("catatan", "") if "gabungan" in (b.get("catatan") or "") else "",
                     aturan_silver="S01;S02;S03;S04;S05;S06;S07")

    yield S.sel(seri, teks, isi)


TABEL = {"dinamis": dinamis, "*": statis}
