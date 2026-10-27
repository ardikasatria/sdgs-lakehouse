"""Pemeta Silver keluarga BNPB: tabel kompilasi kejadian dan dampak bencana (DataStore CKAN dan unduhan tangan).

Satu tabel Bronze memuat banyak resource berbeda tata letak; tata letak dibaca per (rilis, lembar) dari kolom yang
terisi di resource itu (``_info``):

- ``jenis``: satu ukuran per resource (dari nama resource, contoh "Jumlah Korban Meninggal ... Menurut Provinsi
  2024"), kolom per jenis bencana (``BANJIR`` ... ``TSUNAMI``), baris per provinsi/kab-kota plus ``INDONESIA``.
- ``tahun``: satu ukuran per resource, kolom per tahun (``2010.0`` ...), baris per provinsi, kab/kota, atau
  jenis bencana (nasional).
- ``rekap``: rekap 2021/2022 (unduhan tangan), baris per (provinsi, jenis bencana), dua baris kepala; nama
  ukuran kolom ``kolom_N`` dibaca dari baris kepala resource itu sendiri; sel Provinsi tergabung (merged)
  diteruskan ke baris di bawahnya dalam urutan Bronze.
- ``rekap_nasional``: rekap 2025 nasional, baris per jenis bencana plus ``Total``.
- ``stat``: ``stat_by_wil_<kode>_<tahun>`` (DIBI 2000/2001): baris kab/kota plus ``Jumlah`` (total provinsi).
  Impor DataStore hanya menyisakan nomor kolom ``(3)``...``(16)`` sebagai kepala, sehingga ukurannya tidak
  bernama -> karantina ``ukuran_tidak_bernama`` (S04).
- ``nilai``: nilai kerusakan dan kerugian RRRP per kab/kota.
- Lembar ``Keterangan`` (definisi, ambang kejadian) bukan observasi -> di luar (``bukan_observasi``); baris kepala
  -> di luar (``baris_kepala``). Keduanya tetap satu sel agar setiap baris Bronze terhitung.

Aturan:

- S01: ``Kode Wilayah Provinsi`` adalah kode Kemendagri (keterangan BNPB; 94/95/96 = Papua Tengah/Pegunungan/
  Barat Daya), dibaca dengan periode bridging terkini, dan nama provinsi harus menunjuk wilayah yang sama; bila
  tidak -> karantina ``wilayah_ambigu``. ``INDONESIA`` -> 9999. Baris kab/kota (termasuk seluruh tabel
  ``kabupaten`` kecuali baris ``INDONESIA``) -> di luar tingkat ``kabkota``.
- S02: tahun dari nama resource (satu tahun) atau dari kolom tahun; tanpa tahun -> karantina.
- S03: angka bertitik desimal dari DataStore. Pada ukuran cacah, ``.0`` buatan impor CKAN dan galat titik
  mengambang rumus Excel rekap 2021/2022 (``11.000000000000002``) dibulatkan (``urai_cacah``); pecahan
  sungguhan pada ukuran cacah -> karantina.
- S04: korban -> ``jiwa``; bangunan/rumah -> ``x_unit``; kejadian -> ``x_kejadian``; per 100.000 orang ->
  ``x_per_100rb_penduduk``; nilai rupiah -> ``x_rupiah``; luas sawah/lahan tidak menyatakan satuan ->
  ``tidak_ada``.
- S05: ``jenis_bencana`` (label dinormalkan: Gempa Bumi = GEMPABUMI, Letusan = Erupsi Gunung Api, Gelombang
  Pasang / Abrasi = ... DAN ABRASI) dan ``tingkat_kerusakan`` rumah (berat/sedang/ringan); baris ``Total`` dan
  resource tanpa rincian jenis -> ``total``.
- S06: ``seri_kode`` = ukuran (sama lintas resource agar rilis x rilis berpasangan). Kode indikator global per
  ukuran dari kurasi steward ``config/referensi/peta_seri_sektoral.csv`` (korban -> 13.1.1|1.5.1|11.5.1, kerusakan
  dan kerugian -> 11.5.2|1.5.2, infrastruktur kritis -> 11.5.2); korban meninggal dan hilang per 100.000 orang
  juga terpetakan ke indikator katalog ``global:13.1.1``. S07: ``resmi``.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache

from sdg_gudang import referensi as R
from sdg_gudang.akuisisi import inti as A

from .. import agregasi
from .. import inti as S

METADATA: set[str] = set()
INDIKATOR = "global:13.1.1"
JIWA = S.SatuanKanonik("jiwa")
UNIT = S.SatuanKanonik("x_unit")
KEJADIAN = S.SatuanKanonik("x_kejadian")
PER100RB = S.SatuanKanonik("x_per_100rb_penduduk")
RUPIAH = S.SatuanKanonik("x_rupiah")
TANPA = S.SatuanKanonik("tidak_ada")
CACAH = {"jiwa", "x_unit", "x_kejadian"}
ATURAN = "S01;S02;S03;S04;S05;S06;S07"

KOLOM_JENIS = ("BANJIR", "CUACA EKSTREM", "ERUPSI GUNUNG API", "GELOMBANG PASANG DAN ABRASI", "GEMPABUMI",
               "KEBAKARAN HUTAN DAN LAHAN", "KEKERINGAN", "TANAH LONGSOR", "TSUNAMI")
JENIS_SAMA = {"gempa_bumi": "gempabumi", "letusan_gunung_api": "erupsi_gunung_api",
              "gelombang_pasang_abrasi": "gelombang_pasang_dan_abrasi"}
POLA_TAHUN = re.compile(r"^(19|20)\d\d(\.0)?$")
KOLOM_KAB = ("Nama Kabupaten/Kota", "Kabupaten/Kota", "Kabupaten")
KOLOM_STAT = tuple(f"({i})" for i in range(3, 17))

#: nama resource (huruf kecil) -> (ukuran, satuan); urutan penting (yang lebih khusus dulu)
UKURAN_RESOURCE = (
    ("meninggal dan hilang per 100", "korban_meninggal_hilang_per_100rb", PER100RB),
    ("mengungsi per 100", "korban_mengungsi_per_100rb", PER100RB),
    ("kejadian bencana", "kejadian", KEJADIAN),
    ("korban meninggal", "korban_meninggal", JIWA),
    ("korban hilang", "korban_hilang", JIWA),
    ("korban luka", "korban_luka_sakit", JIWA),
    ("korban mengungsi", "korban_mengungsi", JIWA),
    ("korban terdampak", "korban_terdampak", JIWA),
    ("rumah ibadat", "rumah_ibadat_rusak", UNIT),
    ("rumah rusak", "rumah_rusak", UNIT),
    ("kantor", "kantor_rusak", UNIT),
    ("jembatan", "jembatan_rusak", UNIT),
    ("fasilitas pelayanan kesehatan", "fasyankes_rusak", UNIT),
    ("kios", "kios_toko_rusak", UNIT),
    ("pabrik", "pabrik_rusak", UNIT),
    ("satuan pendidikan", "satuan_pendidikan_rusak", UNIT),
    ("luas sawah", "luas_sawah_rusak", TANPA),
    ("luas lahan", "luas_lahan_kebun_hutan_rusak", TANPA),
)
#: label kolom (kepala rekap, huruf kecil) -> (ukuran, satuan, dimensi tambahan)
UKURAN_LABEL = {
    "jumlah kejadian": ("kejadian", KEJADIAN, {}),
    "meninggal": ("korban_meninggal", JIWA, {}),
    "hilang": ("korban_hilang", JIWA, {}),
    "luka-luka": ("korban_luka_sakit", JIWA, {}),
    "luka": ("korban_luka_sakit", JIWA, {}),
    "terdampak - mengungsi": ("korban_terdampak_mengungsi", JIWA, {}),
    "terdampak": ("korban_terdampak", JIWA, {}),
    "mengungsi": ("korban_mengungsi", JIWA, {}),
    "rumah rusak berat": ("rumah_rusak", UNIT, {"tingkat_kerusakan": "berat"}),
    "rumah rusak sedang": ("rumah_rusak", UNIT, {"tingkat_kerusakan": "sedang"}),
    "rumah rusak ringan": ("rumah_rusak", UNIT, {"tingkat_kerusakan": "ringan"}),
    "rumah terendam": ("rumah_terendam", UNIT, {}),
    "sarana pendidikan": ("satuan_pendidikan_rusak", UNIT, {}),
    "satuan pendidikan rusak": ("satuan_pendidikan_rusak", UNIT, {}),
    "sarana peribadatan": ("rumah_ibadat_rusak", UNIT, {}),
    "rumah ibadat rusak": ("rumah_ibadat_rusak", UNIT, {}),
    "sarana kesehatan": ("fasyankes_rusak", UNIT, {}),
    "fasilitas pelayanan kesehatan rusak": ("fasyankes_rusak", UNIT, {}),
    "perkantoran": ("kantor_rusak", UNIT, {}),
    "kantor rusak": ("kantor_rusak", UNIT, {}),
    "jembatan": ("jembatan_rusak", UNIT, {}),
    "jembatan rusak": ("jembatan_rusak", UNIT, {}),
    "nilai kerusakan": ("nilai_kerusakan", RUPIAH, {}),
    "nilai kerugian": ("nilai_kerugian", RUPIAH, {}),
}


@dataclass(frozen=True)
class Info:
    """Tata letak satu (rilis, lembar): kolom terisi, jenis tata letak, dan kepala kolom rekap."""

    kolom: frozenset
    tata: str
    kepala: tuple = ()  # ((kolom, label), ...) untuk rekap


def _isi(v) -> bool:
    return v is not None and str(v).strip() != ""


@lru_cache(maxsize=None)
def _info(tabel: str) -> dict[tuple, Info]:
    rows = A.baca_bronze("bnpb", tabel).to_pylist()
    kolom: dict[tuple, set] = {}
    kepala: dict[tuple, dict] = {}
    for r in rows:
        k = (r["_rilis_id"], r.get("_lembar"))
        kolom.setdefault(k, set()).update(c for c, v in r.items() if not c.startswith("_") and _isi(v))
        if k not in kepala and any(str(v).strip() == "Meninggal" for v in r.values() if isinstance(v, str)):
            kepala[k] = {c: str(v).strip() for c, v in r.items()
                         if not c.startswith("_") and _isi(v) and str(v).strip().lower() in UKURAN_LABEL}
    out = {}
    for k, ks in kolom.items():
        if k[1] == "Keterangan" or ":" in ks:
            tata = "keterangan"
        elif ks & set(KOLOM_STAT) or "Wilayah" in ks:
            tata = "stat"
        elif k in kepala:
            tata = "rekap"
        elif "Kode Bencana" in ks:
            tata = "rekap_nasional"
        elif any(POLA_TAHUN.match(c) for c in ks):
            tata = "tahun"
        elif ks & set(KOLOM_JENIS):
            tata = "jenis"
        elif "Nilai Kerusakan" in ks or "Nilai Kerugian" in ks:
            tata = "nilai"
        else:
            tata = "tak_dikenal"
        kp = {"Jumlah Kejadian": "Jumlah Kejadian"} | kepala.get(k, {}) if tata == "rekap" else {}
        out[k] = Info(frozenset(ks), tata, tuple(sorted(kp.items())))
    return out


def ukuran_resource(nama: str) -> tuple[str, S.SatuanKanonik] | None:
    n = nama.lower()
    return next(((u, s) for pola, u, s in UKURAN_RESOURCE if pola in n), None)


def tahun_resource(nama: str) -> str:
    th = set(re.findall(r"(?<!\d)((?:19|20)\d\d)(?!\d)", nama or ""))
    if len(th) != 1:
        raise S.Karantina("periode_tidak_terurai", "S02", f"tahun nama resource {nama!r}")
    return th.pop()


def jenis(teks) -> str:
    j = re.sub(r"[^a-z0-9]+", "_", str(teks or "").lower()).strip("_")
    return JENIS_SAMA.get(j, j)


def urai_cacah(teks, satuan_id: str) -> tuple[str, int]:
    """S03 untuk BNPB. Pada ukuran cacah, ``.0`` buatan impor CKAN dan galat titik mengambang hasil rumus Excel
    (``11.000000000000002``, ``9.999999999999996``; selisih < 1e-6 dari bilangan bulat) dibulatkan ke bilangan
    bulat dengan ``desimal`` 0; pecahan sungguhan pada ukuran cacah -> karantina."""
    nilai, desimal = S.urai_nilai(teks)
    if satuan_id not in CACAH or desimal == 0:
        return nilai, desimal
    d = Decimal(nilai)
    bulat = d.to_integral_value()
    if abs(d - bulat) < Decimal("1e-6"):
        return (format(bulat, "f") if bulat != 0 else "0"), 0
    raise S.Karantina("nilai_tidak_terurai", "S03", f"pecahan pada ukuran cacah {teks!r}")


# ---------------------------------------------------------------------------------------------------
# S01 wilayah
# ---------------------------------------------------------------------------------------------------

_PROV_TERAKHIR: dict[tuple, str] = {}


def provinsi(ctx: S.Konteks, kode, nama) -> tuple[int, str]:
    """Kode Kemendagri dan nama harus sepakat; ``INDONESIA`` -> 9999."""
    k = str(kode or "").strip().removesuffix(".0")
    n = str(nama or "").strip()
    if n.upper() == "INDONESIA" and not k:
        return R.NAS, "nama"
    w_kode = ctx.rujukan.wilayah("kemendagri", k) if k else None
    w_nama = ctx.rujukan.wilayah("nama", n) if n else None
    if w_kode and w_nama and w_kode != w_nama:
        raise S.Karantina("wilayah_ambigu", "S01", f"kode Kemendagri {k} -> {w_kode}, nama {n!r} -> {w_nama}")
    if not (w_kode or w_nama):
        raise S.Karantina("wilayah_tidak_dikenal", "S01", "tanpa kode dan nama provinsi")
    return (w_kode or w_nama), ("kemendagri+nama" if w_kode and w_nama else "kemendagri" if w_kode else "nama")


def penentu_wilayah(b: dict, tabel: str, info: Info, ctx: S.Konteks):
    """Kembalikan (teks wilayah, fungsi tanpa argumen -> (wilayah_kode, sistem)) untuk baris ini."""
    kab = next((b.get(c) for c in KOLOM_KAB if c in info.kolom), None)
    if info.tata == "stat":
        teks = str(b.get("(2)") or b.get("Wilayah") or "").strip()
        if teks.lower() == "jumlah":
            m = re.search(r"stat_by_wil_(\d+)_", b.get("_resource_nama") or "")

            def f():
                if not m:
                    raise S.Karantina("wilayah_tidak_dikenal", "S01", f"kode di nama {b.get('_resource_nama')!r}")
                return ctx.rujukan.wilayah("kemendagri", m.group(1)), "kemendagri"
            return f"Jumlah {b.get('_resource_nama')}", f
        return teks, _diluar("kabkota")
    if info.tata in ("rekap_nasional",) or (tabel == "lain" and info.tata == "tahun"):
        return "nasional", lambda: (R.NAS, "nasional")
    if tabel == "kabupaten" or info.tata == "nilai":
        if str(kab or "").strip().upper() == "INDONESIA":
            return "INDONESIA", lambda: (R.NAS, "nama")
        return str(kab or ""), _diluar("kabkota")
    kode = b.get("Kode Wilayah Provinsi")
    nama = b.get("Nama Provinsi") if "Nama Provinsi" in info.kolom else b.get("Provinsi")
    if info.tata == "rekap":
        kunci = (b["_rilis_id"], b.get("_lembar"))
        if _isi(nama):
            _PROV_TERAKHIR[kunci] = str(nama).strip()
        else:
            nama = _PROV_TERAKHIR.get(kunci)
    return f"{kode or ''} {nama or ''}".strip(), lambda: provinsi(ctx, kode, nama)


def _diluar(alasan: str):
    def f():
        raise S.DiLuar(alasan)
    return f


# ---------------------------------------------------------------------------------------------------
# Sel per tata letak
# ---------------------------------------------------------------------------------------------------

def daftar_ukuran(b: dict, info: Info) -> list[tuple]:
    """(kolom, ukuran, satuan, dimensi, teks periode) untuk setiap kolom ukuran baris ini."""
    nama = b.get("_resource_nama") or ""
    ur = ukuran_resource(nama)
    u, st = ur if ur else (None, None)
    out = []
    if info.tata == "jenis":
        for c in KOLOM_JENIS:
            if c in info.kolom:
                out.append((c, u, st, {"jenis_bencana": jenis(c)}, None))
        if "Jumlah Penduduk" in info.kolom:
            out.append(("Jumlah Penduduk", "jumlah_penduduk", JIWA, {}, None))
    elif info.tata == "tahun":
        dim = {"jenis_bencana": jenis(b.get("JENIS BENCANA"))} if "JENIS BENCANA" in info.kolom else {}
        for c in sorted(c for c in info.kolom if POLA_TAHUN.match(c)):
            out.append((c, u, st, dim, c))
    elif info.tata == "rekap":
        for c, label in info.kepala:
            uu, ss, ext = UKURAN_LABEL[label.lower()]
            out.append((c, uu, ss, {"jenis_bencana": jenis(b.get("Jenis Bencana"))} | ext, None))
    elif info.tata == "rekap_nasional":
        j = str(b.get("Jenis Bencana") or "").strip()
        dim = {} if j.lower() == "total" else {"jenis_bencana": jenis(j)}
        for c in sorted(info.kolom):
            if c.lower() in UKURAN_LABEL:
                uu, ss, ext = UKURAN_LABEL[c.lower()]
                out.append((c, uu, ss, dim | ext, None))
    elif info.tata == "stat":
        for c in KOLOM_STAT + ("Jumlah Kejadian", "Korban", "Kerusakan"):
            if c in info.kolom:
                out.append((c, None, None, {}, None))
    elif info.tata == "nilai":
        for c in ("Nilai Kerusakan", "Nilai Kerugian"):
            if c in info.kolom:
                uu, ss, _ = UKURAN_LABEL[c.lower()]
                out.append((c, uu, ss, {}, b.get("Tahun Kejadian")))
    return out


def baris_kepala(b: dict, info: Info) -> bool:
    if info.tata == "rekap":
        return not _isi(b.get("Jenis Bencana")) and not _isi(b.get("Jumlah Kejadian"))
    if info.tata == "stat":  # kepala bertingkat: teks kosong atau nomor kolom "(2)"
        w = str(b.get("(2)") or b.get("Wilayah") or "").strip()
        return not re.sub(r"^\(\d+\)$", "", w)
    return False


def petakan(tabel: str):
    def f(b: dict, ctx: S.Konteks):
        info = _info(tabel)[(b["_rilis_id"], b.get("_lembar"))]
        nama = b.get("_resource_nama") or ""
        if info.tata in ("keterangan", "tak_dikenal"):
            yield S.sel("", {"wilayah": "", "periode": nama, "nilai": "", "satuan": ""},
                        _diluar("bukan_observasi" if info.tata == "keterangan" else "tata_letak_tak_dikenal"))
            return
        ukuran = daftar_ukuran(b, info)
        if baris_kepala(b, info):
            for c, u, *_ in ukuran:
                yield S.sel(u or c, {"wilayah": "", "periode": nama, "nilai": b.get(c), "satuan": ""},
                            _diluar("baris_kepala"))
            return
        teks_w, wilayah = penentu_wilayah(b, tabel, info, ctx)
        for c, u, st, dim, teks_p in ukuran:
            seri = u or f"{tabel}:{c}"
            teks = {"wilayah": teks_w, "periode": teks_p or nama, "nilai": b.get(c),
                    "satuan": st.satuan_id if st else ""}

            def isi(c=c, u=u, st=st, dim=dim, teks_p=teks_p, seri=seri):
                try:
                    w, sistem = wilayah()
                except S.DiLuar as e:
                    if e.alasan != "kabkota" or tabel != "kabupaten":
                        raise
                    raise S.DiLuar("kabkota", komponen_kabkota(b, ctx, teks_w, lambda w_, s_: obs_sel(
                        c, u, st, dim, teks_p, seri, w_, s_))) from None
                return obs_sel(c, u, st, dim, teks_p, seri, w, sistem)

            def obs_sel(c, u, st, dim, teks_p, seri, w, sistem):
                periode = S.periode_tahun(teks_p) if teks_p else tahun_resource(nama)
                if u is None:
                    sebab = ("kepala hilang pada impor DataStore" if info.tata == "stat"
                             else f"nama resource {nama!r} tidak dikenali")
                    raise S.Karantina("ukuran_tidak_bernama", "S04", f"kolom {c!r} tanpa nama ukuran: {sebab}")
                nilai, desimal = urai_cacah(b.get(c), st.satuan_id)
                k = konsep(ctx, seri)
                return S.obs(seri_kode=seri, **k, wilayah_kode=w, tingkat=ctx.rujukan.tingkat(w),
                             sistem_wilayah=sistem, periode=periode, rincian=S.rincian(dim), nilai=nilai,
                             desimal=desimal, satuan_id=st.satuan_id, satuan_sumber="", sifat="resmi",
                             aturan_silver=ATURAN)

            yield S.sel(seri, teks, isi)
    return f


@lru_cache(maxsize=1)
def peta_seri() -> dict[str, dict]:
    """Kurasi steward seri BNPB -> kode indikator global (``config/referensi/peta_seri_sektoral.csv``)."""
    with (S.AKAR / "config" / "referensi" / "peta_seri_sektoral.csv").open(encoding="utf-8") as f:
        return {r["seri_kode"]: r for r in csv.DictReader(f) if r["keluarga"] == "bnpb"}


def konsep(ctx: S.Konteks, seri: str) -> dict:
    """S06: kode global dari kurasi steward; kode pertama menentukan tujuan dan pilar (13 atau 11 = Lingkungan).
    Hanya korban meninggal dan hilang per 100.000 yang terpetakan ke indikator katalog ``global:13.1.1``."""
    p = peta_seri().get(seri, {})
    kode = p.get("kode_global", "")
    if seri == "korban_meninggal_hilang_per_100rb":
        return ctx.konsep("bnpb", seri, kode, INDIKATOR)
    return ctx.konsep("bnpb", seri, kode)


def provinsi_kabkota(b: dict, ctx: S.Konteks) -> tuple[int, str] | None:
    """S09: provinsi induk baris kab/kota dari dua digit awal kode Kemendagri kab/kota, atau dari kolom Provinsi."""
    kode = str(b.get("Kode Wilayah Kabupaten / Kota") or "").strip().removesuffix(".0")
    try:
        if len(kode) >= 4 and kode[:2].isdigit():
            return ctx.rujukan.wilayah("kemendagri", kode[:2]), "kemendagri_kabkota"
        if _isi(b.get("Provinsi")):
            return ctx.rujukan.wilayah("nama", str(b.get("Provinsi")).strip()), "nama"
    except S.Karantina:
        return None
    return None


def komponen_kabkota(b: dict, ctx: S.Konteks, teks_w: str, buat) -> dict | None:
    """Komponen S09 untuk satu sel kab/kota BNPB; None bila provinsi tidak diketahui atau sel tidak terurai."""
    prov = provinsi_kabkota(b, ctx)
    if prov is None:
        return None
    try:
        o = buat(*prov)
    except S.Kosong:
        return None
    except S.Karantina:
        return None
    kab = str(b.get("Kode Wilayah Kabupaten / Kota") or "").strip().removesuffix(".0") or teks_w
    return agregasi.komponen_dari(o, kab)


#: S09: kabupaten tidak tercantum = tidak ada kejadian, sehingga ambang cakupan tidak diterapkan.
AGREGASI = {"kabupaten": {"bobot": {}, "ambang": None}}

TABEL = {"provinsi": petakan("provinsi"), "kabupaten": petakan("kabupaten"), "lain": petakan("lain")}
