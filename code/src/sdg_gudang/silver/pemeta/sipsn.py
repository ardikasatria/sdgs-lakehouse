"""Pemeta Silver keluarga SIPSN: ekspor statistik pengelolaan sampah dan ``rawData`` peta beranda.

- S01: ``detil_kabkota`` dan ``peta_kabkota`` bertingkat kabupaten/kota -> di luar tingkat (``kabkota``).
  ``detil_kabkota`` berkolom Provinsi, sehingga selnya membawa komponen untuk S09 (agregasi ke provinsi, ambang
  cakupan 80 %); ``peta_kabkota`` tidak berkolom provinsi dan tidak diagregasi.
  Baris tanpa Provinsi dan Kota/Kabupaten (8 baris di ujung tabel, nilainya 0/100/``-``) -> karantina
  ``wilayah_tidak_dikenal``. Tabel ringkasan berfilter "Nasional (semua wilayah)" -> 9999.
- S02: tidak ada kolom tahun. Periode = tahun pada label tercetak ("Data Terverifikasi Update 2026") yang dicatat
  konektor di ``cakupan`` rilis (``dim_rilis``: "label tahun tercetak <tahun>"); label itu tahun pembaruan,
  bukan tanggal rilis. Tanpa tahun label -> karantina ``periode_tidak_terurai``.
- S03: tabel ekspor memakai koma desimal dan titik ribuan (``0,48``; ``276.091.351``; ``144.265`` tpd =
  ``35.697`` + ``108.567``) -> ``desimal_koma``. ``rawData`` beranda memakai titik desimal. Catatan mutu: kolom
  ``Progress SA`` tabel Detil bertitik desimal (``54.15``) di tengah kolom lain bertitik ribuan (``2.784``).
- S04: tpd -> ``ton_per_hari``; cacah fasilitas -> ``x_unit``; cacah wilayah -> ``x_wilayah``; ``Koefisien`` dan
  ``Nilai Kinerja PS`` tanpa satuan -> ``tidak_ada``; persentase ``rawData`` berupa proporsi 0-1 -> ``x_proporsi``.
- S05: kategori wilayah (``Kota - Metropolitan`` ...) -> ``kategori=...``; ``Kota/Kabupaten`` = total.
- S06: persentase sampah terkelola -> ``global:12.5.1`` (proksi). S07: ``resmi`` (data kementerian).
"""
from __future__ import annotations

import csv
import re
from functools import lru_cache

from sdg_gudang import referensi as R
from sdg_gudang.akuisisi import inti as A

from .. import agregasi
from .. import inti as S

METADATA: set[str] = set()
INDIKATOR = "global:12.5.1"
TPD = S.SatuanKanonik("ton_per_hari")
UNIT = S.SatuanKanonik("x_unit")
WILAYAH = S.SatuanKanonik("x_wilayah")
PERSEN = S.SatuanKanonik("persen")
TANPA = S.SatuanKanonik("tidak_ada")

#: Indikator ringkasan -> (ukuran, satuan, padan 12.5.1)
RINGKASAN_INDIKATOR = {
    "Jumlah TPA": ("jumlah_tpa", UNIT, False),
    "Koefisien": ("koefisien", TANPA, False),
    "Rasio APBD (%)": ("rasio_apbd", PERSEN, False),
    "Jumlah Penduduk": ("jumlah_penduduk", S.SatuanKanonik("jiwa"), False),
    "Progress Sanksi Administrasi (%)": ("progres_sanksi_administrasi", PERSEN, False),
    "Sudah Verifikasi Lapangan": ("kabkota_terverifikasi_lapangan", WILAYAH, False),
    "Persentase Verifikasi (%)": ("persentase_verifikasi", PERSEN, False),
    "Sampah Terkelola (%)": ("sampah_terkelola_persen", PERSEN, True),
    "Sampah Terkelola (tpd)": ("sampah_terkelola_tpd", TPD, False),
    "Sampah Belum Terkelola (%)": ("sampah_belum_terkelola_persen", PERSEN, False),
    "Sampah Belum Terkelola (tpd)": ("sampah_belum_terkelola_tpd", TPD, False),
}
#: Kategori ringkasan wilayah & fasilitas -> (ukuran, satuan, rincian)
RINGKASAN_WILAYAH = {
    "Kota/Kabupaten": ("jumlah_kabkota", WILAYAH, "total"),
    "Provinsi": ("jumlah_provinsi", WILAYAH, "total"),
    "Timbulan (tpd)": ("timbulan", TPD, "total"),
    "BSU Aktif": ("bsu_aktif", UNIT, "total"),
    "BSI Aktif": ("bsi_aktif", UNIT, "total"),
    "TPS 3R Aktif": ("tps3r_aktif", UNIT, "total"),
}
#: Kolom ukuran tabel bertingkat kab/kota -> (satuan, padan 12.5.1)
DETIL = {"% S. Belum Terkelola": (PERSEN, False), "% S. Terkelola": (PERSEN, True), "BSI Aktif": (UNIT, False),
         "BSI Tidak Aktif": (UNIT, False), "BSU Aktif": (UNIT, False), "BSU Tidak Aktif": (UNIT, False),
         "Nilai Kinerja PS": (TANPA, False), "Progress SA": (PERSEN, False), "Sampah Terkelola BSI": (TPD, False),
         "Sampah Terkelola BSU": (TPD, False), "Timbulan (tpd)": (TPD, False)}
PETA = {"bsi_aktif": (UNIT, False), "bsu_aktif": (UNIT, False), "mrf_10_tpd_aktif": (UNIT, False),
        "persentase_sampah_terkelola": (S.SatuanKanonik("x_proporsi"), True), "sampah_terkelola": (TPD, False),
        "timbulan": (TPD, False)}
ATURAN = "S01;S02;S03;S04;S05;S06;S07"


@lru_cache(maxsize=1)
def _cakupan() -> dict[str, str]:
    with (A.MANIFEST / "dim_rilis.csv").open(encoding="utf-8") as f:
        return {r["rilis_id"]: r["cakupan"] for r in csv.DictReader(f) if r["sumber"] == "sipsn"}


def periode(rilis_id: str) -> str:
    """S02: tahun label tercetak dari ``cakupan`` rilis."""
    c = _cakupan().get(rilis_id, "")
    m = re.search(r"label tahun tercetak ((?:19|20)\d\d)", c)
    if not m:
        raise S.Karantina("periode_tidak_terurai", "S02", f"tanpa tahun label pada cakupan rilis {c!r}")
    return m.group(1)


def slug(teks: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", teks.lower()).strip("_")


def _konsep(ctx: S.Konteks, seri: str, padan: bool) -> dict:
    return ctx.konsep("sipsn", seri, "12.5.1", INDIKATOR) if padan else ctx.konsep("sipsn", seri)


def _nasional(ctx, b, seri, teks_nilai, st: S.SatuanKanonik, padan: bool, rincian: str, teks_satuan: str):
    nilai, desimal = S.urai_nilai(teks_nilai, desimal_koma=True)
    return S.obs(seri_kode=seri, **_konsep(ctx, seri, padan), wilayah_kode=R.NAS, tingkat="nasional",
                 sistem_wilayah="nasional", periode=periode(b["_rilis_id"]), rincian=rincian,
                 nilai=S.kali(nilai, st.faktor), desimal=desimal, satuan_id=st.satuan_id,
                 satuan_sumber=teks_satuan, faktor_satuan=st.faktor, sifat="resmi", aturan_silver=ATURAN)


def ringkasan_indikator(b: dict, ctx: S.Konteks):
    label = (b.get("Indikator") or "").strip()
    ukuran, st, padan = RINGKASAN_INDIKATOR.get(label, (slug(label), None, False))
    seri = f"ringkasan_indikator:{ukuran}"
    teks = {"wilayah": "nasional", "periode": b["_rilis_id"], "nilai": b.get("Nilai"), "satuan": label}

    def isi():
        if st is None:
            raise S.Karantina("satuan_tidak_dikenal", "S04", f"indikator ringkasan tidak dikenal {label!r}")
        return _nasional(ctx, b, seri, b.get("Nilai"), st, padan, "total", label)

    yield S.sel(seri, teks, isi)


def ringkasan_wilayah_fasilitas(b: dict, ctx: S.Konteks):
    label = (b.get("Kategori") or "").strip()
    m = re.fullmatch(r"(Kota|Kab) - (\w+)", label)
    if m:
        ukuran, st, rinci = "jumlah_kabkota", WILAYAH, f"kategori={slug(label)}"
    else:
        ukuran, st, rinci = RINGKASAN_WILAYAH.get(label, (slug(label), None, "total"))
    seri = f"ringkasan_wilayah_fasilitas:{ukuran}"
    teks = {"wilayah": "nasional", "periode": b["_rilis_id"], "nilai": b.get("Jumlah"), "satuan": label}

    def isi():
        if st is None:
            raise S.Karantina("satuan_tidak_dikenal", "S04", f"kategori ringkasan tidak dikenal {label!r}")
        return _nasional(ctx, b, seri, b.get("Jumlah"), st, False, rinci, label)

    yield S.sel(seri, teks, isi)


def _komponen(ctx, b, seri, kolom: str, st: S.SatuanKanonik, padan: bool, prov: str, kab: str) -> dict | None:
    """Komponen S09: observasi kab/kota dengan provinsi induknya; None bila provinsi tidak dikenali atau nilainya
    tidak dapat diurai (sel tetap di luar tingkat, tidak menyumbang agregat)."""
    if not prov or kolom == "Progress SA":  # Progress SA bertitik desimal dan tidak aditif
        return None
    try:
        w = ctx.rujukan.wilayah("nama", prov)
        nilai, desimal = agregasi.kosong_ke_none(lambda: S.urai_nilai(b.get(kolom), desimal_koma=True))
        return agregasi.komponen_dari(S.obs(
            seri_kode=seri, **_konsep(ctx, seri, padan), wilayah_kode=w, tingkat="provinsi", sistem_wilayah="nama",
            periode=periode(b["_rilis_id"]), nilai=None if nilai is None else S.kali(nilai, st.faktor),
            desimal=desimal, satuan_id=st.satuan_id, satuan_sumber=kolom, faktor_satuan=st.faktor, sifat="resmi",
            aturan_silver=ATURAN), kab)
    except S.Karantina:
        return None


def _kabkota(b: dict, tabel: str, kolom: dict, nama_kab: str, nama_prov: str | None, ctx=None):
    """Tabel bertingkat kab/kota: setiap kolom ukuran menjadi sel di luar tingkat (atau karantina S01 bila baris
    tidak berwilayah sama sekali). Bila provinsi diketahui, sel membawa komponen untuk agregasi S09."""
    kab = (b.get(nama_kab) or "").strip()
    prov = (b.get(nama_prov) or "").strip() if nama_prov else ""
    for k, (st, padan) in kolom.items():
        seri = f"{tabel}:{slug(k)}"
        teks = {"wilayah": f"{prov} / {kab}".strip(" /"), "periode": b["_rilis_id"], "nilai": b.get(k),
                "satuan": st.satuan_id}

        def isi(k=k, st=st, padan=padan, seri=seri):
            if not kab and not prov:
                raise S.Karantina("wilayah_tidak_dikenal", "S01",
                                  f"baris tanpa provinsi dan kabupaten/kota (urutan {b.get('_urutan')})")
            raise S.DiLuar("kabkota", _komponen(ctx, b, seri, k, st, padan, prov, kab) if ctx else None)

        yield S.sel(seri, teks, isi)


def detil_kabkota(b: dict, ctx: S.Konteks):
    yield from _kabkota(b, "detil_kabkota", DETIL, "Kota/Kabupaten", "Provinsi", ctx)


def peta_kabkota(b: dict, ctx: S.Konteks):
    yield from _kabkota(b, "peta_kabkota", PETA, "kota_kabupaten", None)


#: S09: persen sampah terkelola dan belum terkelola dibobot timbulan; ambang cakupan 80 % (tambahan praregistrasi M3).
AGREGASI = {"detil_kabkota": {"bobot": {"detil_kabkota:s_terkelola": "detil_kabkota:timbulan_tpd",
                                        "detil_kabkota:s_belum_terkelola": "detil_kabkota:timbulan_tpd"},
                              "ambang": 0.8}}

TABEL = {"ringkasan_indikator": ringkasan_indikator, "ringkasan_wilayah_fasilitas": ringkasan_wilayah_fasilitas,
         "detil_kabkota": detil_kabkota, "peta_kabkota": peta_kabkota}
