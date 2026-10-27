"""Pemeta Silver keluarga KKP: kawasan konservasi, statistik per provinsi, dan seri nasional tahunan.

- S01: kolom kode (``id_prov``, ``kode_provinsi``) adalah kode Kemendagri (93 Papua Selatan, 94 Papua Tengah,
  96 Papua Barat Daya), dibaca dengan periode bridging terkini; kolom nama (``provinsi``, ``upper``) ikut
  dipetakan. Kode dan nama harus menunjuk wilayah yang sama; bila tidak -> karantina ``wilayah_ambigu``
  (contoh ``nelayan_per_prov`` 2023: ``91 PAPUA SELATAN``, ``91 PAPUA TENGAH``, ``92 PAPUA BARAT DAYA``).
  ``NASIONAL`` (kode ``-``) dan tabel ``nasional_*`` -> 9999. ``rhl_mangrove`` per desa -> di luar tingkat.
- S02: kolom ``tahun``; tanda ``*`` (angka sementara, contoh ``2026*`` pada NTN/NTPI nasional) dibuang dari
  periode dan dicatat di ``status_angka = "sementara"``: nilainya belum final atau belum setahun penuh.
  ``kode_bulan`` NTN/NTPI per provinsi (selalu 9) dicatat apa adanya sebagai ``bulan_acuan``; maknanya tidak
  dinyatakan sumber.
- S03: angka bertitik desimal; ``luas`` kawasan dapat bernotasi ilmiah dari sumber (``3.3553528e+06``).
- S04 (payload tidak menyatakan satuan; satuan diambil dari definisi ukurannya): nelayan dan pembudidaya ->
  ``jiwa`` (orang); rumah tangga perikanan -> ``x_rumah_tangga``; NTN/NTPI -> ``indeks``; luas kawasan ->
  ``hektar`` (``luas (ha)`` portal); AKI -> ``x_kg_per_kapita_per_tahun`` (definisi Angka Konsumsi Ikan);
  ``serapan`` tanpa definisi satuan -> ``tidak_ada``.
- S05: nelayan ``laut``/``darat`` -> ``perairan=...``, ``total`` = total; kawasan -> ``kawasan=<nama>``;
  AKI jenis ikan utama -> ``jenis_ikan=<jenis>``.
- S06: luas kawasan konservasi -> ``global:14.5.1``; ukuran lain tanpa indikator. S07: ``resmi``.
"""
from __future__ import annotations

import re

from sdg_gudang import referensi as R

from .. import inti as S

METADATA: set[str] = set()
INDIKATOR = "global:14.5.1"
JIWA = S.SatuanKanonik("jiwa")
RT = S.SatuanKanonik("x_rumah_tangga")
INDEKS = S.SatuanKanonik("indeks")
AKI = S.SatuanKanonik("x_kg_per_kapita_per_tahun")
TANPA = S.SatuanKanonik("tidak_ada")
NASIONAL = {"NASIONAL", "INDONESIA"}
ATURAN = "S01;S02;S03;S04;S05;S06;S07"

#: tabel -> daftar (kolom nilai, ukuran, satuan, rincian tetap atau None, kolom rincian dinamis)
UKURAN = {
    "nelayan": [("laut", "jumlah_nelayan", JIWA, "perairan=laut"), ("darat", "jumlah_nelayan", JIWA, "perairan=darat"),
                ("total", "jumlah_nelayan", JIWA, "total"), ("jumlah_rtp", "jumlah_rtp", RT, "total")],
    "pembudidaya": [("total", "jumlah_pembudidaya", JIWA, "total"), ("jumlah_rtp", "jumlah_rtp", RT, "total")],
    "kirt": [("aki_rt", "aki_rt", AKI, "total"), ("serapan", "serapan", TANPA, "total"),
             ("aki_rt_jenis_ikan", "aki_rt_jenis_ikan_utama", AKI, "jenis_ikan_aki"),
             ("serapan_jenis_ikan", "serapan_jenis_ikan_utama", TANPA, "jenis_ikan_serapan")],
    "ntn": [("rata_rata", "ntn", INDEKS, "total")],
    "ntpi": [("rata_rata", "ntpi", INDEKS, "total")],
}


def periode(teks) -> dict:
    """S02: tahun, dengan ``*`` sebagai tanda angka sementara."""
    t = str(teks or "").strip()
    sementara = t.endswith("*")
    return {"periode": S.periode_tahun(t.rstrip("*").strip()), "status_angka": "sementara" if sementara else ""}


def wilayah(ctx: S.Konteks, kode, nama) -> tuple[int, str]:
    """S01: kode Kemendagri dan nama harus sepakat. Kembalikan (wilayah_kode, sistem)."""
    k, n = str(kode or "").strip(), str(nama or "").strip()
    if n.upper() in NASIONAL and k in ("", "-"):
        return R.NAS, "nama"
    w_kode = ctx.rujukan.wilayah("kemendagri", k) if k else None
    w_nama = ctx.rujukan.wilayah("nama", n) if n else None
    if w_kode and w_nama and w_kode != w_nama:
        raise S.Karantina("wilayah_ambigu", "S01",
                          f"kode Kemendagri {k} -> {w_kode}, nama {n!r} -> {w_nama}")
    if not (w_kode or w_nama):
        raise S.Karantina("wilayah_tidak_dikenal", "S01", "tanpa kode dan nama wilayah")
    return (w_kode or w_nama), ("kemendagri+nama" if w_kode and w_nama else "kemendagri" if w_kode else "nama")


def _rincian(b: dict, r: str) -> str:
    if r == "total" or "=" in r:
        return r
    v = (b.get(r) or "").strip()
    return S.rincian({"jenis_ikan": v}) if v else "total"


def _sel(ctx, b, seri, kolom, st, rinci, w_isi, bulan=""):
    teks = {"wilayah": w_isi[0], "periode": b.get("tahun"), "nilai": b.get(kolom), "satuan": st.satuan_id}

    def isi():
        w, sistem = w_isi[1]()
        nilai, desimal = S.urai_nilai(b.get(kolom))
        return S.obs(seri_kode=seri, **ctx.konsep("kkp", seri), wilayah_kode=w, tingkat=ctx.rujukan.tingkat(w),
                     sistem_wilayah=sistem, **periode(b.get("tahun")), bulan_acuan=bulan,
                     rincian=_rincian(b, rinci), nilai=nilai, desimal=desimal, satuan_id=st.satuan_id,
                     satuan_sumber="", sifat="resmi", aturan_silver=ATURAN)

    return S.sel(seri, teks, isi)


def per_prov(b: dict, ctx: S.Konteks):
    x = b["_endpoint"].removesuffix("_per_prov")
    kode = b.get("id_prov") if b.get("id_prov") is not None else b.get("kode_provinsi")
    nama = b.get("provinsi") if b.get("provinsi") is not None else b.get("upper")
    w_isi = (f"{kode} {nama}", lambda: wilayah(ctx, kode, nama))
    for kolom, ukuran, st, rinci in UKURAN[x]:
        yield _sel(ctx, b, f"{x}:{ukuran}", kolom, st, rinci, w_isi, str(b.get("kode_bulan") or ""))


def nasional(b: dict, ctx: S.Konteks):
    x = b["_endpoint"].removesuffix("_tahunan")
    w_isi = ("nasional", lambda: (R.NAS, "nasional"))
    for kolom, ukuran, st, rinci in UKURAN[x]:
        if kolom in b:
            yield _sel(ctx, b, f"{x}:{ukuran}", kolom, st, rinci, w_isi)


def kawasan_konservasi(b: dict, ctx: S.Konteks):
    seri = "kawasan_konservasi:luas"
    teks = {"wilayah": b.get("provinsi"), "periode": b.get("tahun"), "nilai": b.get("luas"), "satuan": "ha"}

    def isi():
        w = ctx.rujukan.wilayah("nama", b.get("provinsi"))
        nilai, desimal = S.urai_nilai(b.get("luas"))
        nama = re.sub(r"\s+", " ", b.get("nama_kawasan") or "").strip()
        return S.obs(seri_kode=seri, **ctx.konsep("kkp", seri, "14.5.1", INDIKATOR), wilayah_kode=w,
                     tingkat=ctx.rujukan.tingkat(w), sistem_wilayah="nama", **periode(b.get("tahun")),
                     rincian=S.rincian({"kawasan": nama}), nilai=nilai, desimal=desimal, satuan_id="hektar",
                     satuan_sumber="ha", sifat="resmi", aturan_silver=ATURAN)

    yield S.sel(seri, teks, isi)


def rhl_mangrove(b: dict, ctx: S.Konteks):
    for kolom in ("jml_bibit", "luas"):
        seri = f"rhl_mangrove:{kolom}"
        teks = {"wilayah": f"{b.get('provinsi')} / {b.get('kabupaten')} / {b.get('desa')}", "periode": "",
                "nilai": b.get(kolom), "satuan": ""}

        def isi():
            raise S.DiLuar("desa")

        yield S.sel(seri, teks, isi)


TABEL = {"kawasan_konservasi": kawasan_konservasi, "rhl_mangrove": rhl_mangrove,
         **{f"{x}_per_prov": per_prov for x in UKURAN}, **{f"nasional_{x}_tahunan": nasional for x in UKURAN}}
