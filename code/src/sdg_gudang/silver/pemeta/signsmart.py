"""Pemeta Silver keluarga SIGN-SMART: emisi GRK per provinsi per sektor dan seri nasional per sektor.

- S01: ``id`` adalah kode ISO 3166-2. Pada setiap payload tahun, setiap sektor memuat ``ID-AC`` lima kali (urutan
  0 dan 34-37; empat provinsi Papua pemekaran 2022 salah kunci). Kunci yang muncul lebih dari sekali dalam satu
  (rilis, sektor) dikarantina **seluruhnya**, termasuk entri yang mungkin Aceh: memilih menurut urutan adalah
  tebakan. Seri ``emisi_nasional`` -> 9999.
- S02: provinsi: ``tahun_diminta`` (satu rilis per tahun); nasional: ``tahun``. Payload tahun yang semua nilainya
  nol (konektor mencatatnya "semua nilai nol") dan tahun nasional yang semua sektornya nol (kategori grafik
  sampai 2030) bukan data: dihitung **kosong** sebelum aturan lain, termasuk S01.
- S03: angka JSON bertitik desimal (``desimal_koma`` tidak dipakai).
- S04: peta provinsi bertooltip ``{value} Gg`` -> ``ton_co2e`` faktor 1000, dipetakan eksplisit di ``SATUAN``. Grafik nasional tidak menyatakan satuan
  (sumbu ``e/1e3 + " K"``) -> ``tidak_ada``; besarannya tidak dipakai untuk menebak satuan.
- S05: ``sektor=energi|ippu|pertanian|kehutanan|limbah``; sumber tidak memberi baris total sektor.
- S06: kedua seri -> ``global:13.2.2`` (rencana sumber sektoral). S07: ``tidak_diketahui``: penafian beranda
  menyatakan data dinamis dan belum melalui QA/QC, jadi belum dapat disebut data resmi.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal
from functools import lru_cache

from sdg_gudang import referensi as R
from sdg_gudang.akuisisi import inti as A

from .. import inti as S

METADATA: set[str] = set()
INDIKATOR = "global:13.2.2"
SIFAT = "tidak_diketahui"  # penafian beranda: dinamis, belum QA/QC
GG = S.SatuanKanonik("ton_co2e", "1000")
SEKTOR = {"energy": "energi", "ippu": "ippu", "agriculture": "pertanian", "forestry": "kehutanan",
          "waste": "limbah", "energi": "energi", "pertanian": "pertanian", "kehutanan": "kehutanan",
          "limbah": "limbah"}


def _nol(v) -> bool:
    try:
        return Decimal(str(v)) == 0
    except Exception:  # noqa: BLE001 - teks bukan angka bukan nol
        return False


@lru_cache(maxsize=1)
def _provinsi() -> tuple[dict, set]:
    """(hitungan kunci per (rilis, sektor, id) beserta urutannya, rilis yang semua nilainya nol)."""
    t = A.baca_bronze("signsmart", "emisi_provinsi").select(["_rilis_id", "sektor", "id", "urutan", "value"])
    urutan, nonnol = defaultdict(list), set()
    rilis = set()
    for r in t.to_pylist():
        urutan[(r["_rilis_id"], r["sektor"], r["id"])].append(r["urutan"])
        rilis.add(r["_rilis_id"])
        if not _nol(r["value"]):
            nonnol.add(r["_rilis_id"])
    return dict(urutan), rilis - nonnol


@lru_cache(maxsize=1)
def _tahun_nasional_nol() -> set:
    t = A.baca_bronze("signsmart", "emisi_nasional").select(["_rilis_id", "tahun", "nilai"])
    n, nonnol = Counter(), set()
    for r in t.to_pylist():
        k = (r["_rilis_id"], r["tahun"])
        n[k] += 1
        if not _nol(r["nilai"]):
            nonnol.add(k)
    return set(n) - nonnol


def sektor(teks: str) -> str:
    t = (teks or "").strip().lower()
    return f"sektor={SEKTOR.get(t, t)}"


def provinsi(b: dict, ctx: S.Konteks):
    seri = "emisi_provinsi:emisi_grk"
    teks = {"wilayah": b["id"], "periode": b["tahun_diminta"], "nilai": b["value"], "satuan": "Gg"}

    def isi():
        urutan, rilis_nol = _provinsi()
        if b["_rilis_id"] in rilis_nol:
            raise S.Kosong("payload tahun semua nilai nol")
        pos = urutan.get((b["_rilis_id"], b["sektor"], b["id"]), [])
        if len(pos) > 1:
            raise S.Karantina("wilayah_ambigu", "S01",
                              f"kode ISO {b['id']} muncul {len(pos)} kali pada sektor {b['sektor']} tahun "
                              f"{b['tahun_diminta']} (urutan {','.join(sorted(pos, key=int))})")
        w = ctx.rujukan.wilayah("iso3166_2", b["id"])
        nilai, desimal = S.urai_nilai(b["value"])
        return S.obs(seri_kode=seri, **ctx.konsep("signsmart", seri, "13.2.2", INDIKATOR), wilayah_kode=w,
                     tingkat=ctx.rujukan.tingkat(w), sistem_wilayah="iso3166_2",
                     periode=S.periode_tahun(b["tahun_diminta"]), rincian=sektor(b["sektor"]),
                     nilai=S.kali(nilai, GG.faktor), desimal=desimal, satuan_id=GG.satuan_id, satuan_sumber="Gg",
                     faktor_satuan=GG.faktor, sifat=SIFAT, aturan_silver="S01;S02;S03;S04;S05;S06;S07")

    yield S.sel(seri, teks, isi)


def nasional(b: dict, ctx: S.Konteks):
    seri = "emisi_nasional:emisi_grk"
    teks = {"wilayah": "nasional", "periode": b["tahun"], "nilai": b["nilai"], "satuan": ""}

    def isi():
        if (b["_rilis_id"], b["tahun"]) in _tahun_nasional_nol():
            raise S.Kosong("tahun grafik tanpa data: semua sektor nol")
        nilai, desimal = S.urai_nilai(b["nilai"])
        return S.obs(seri_kode=seri, **ctx.konsep("signsmart", seri, "13.2.2", INDIKATOR), wilayah_kode=R.NAS,
                     tingkat="nasional", sistem_wilayah="nasional", periode=S.periode_tahun(b["tahun"]),
                     rincian=sektor(b["sektor"]), nilai=nilai, desimal=desimal, satuan_id="tidak_ada",
                     satuan_sumber="", sifat=SIFAT, aturan_silver="S01;S02;S03;S04;S05;S06;S07")

    yield S.sel(seri, teks, isi)


TABEL = {"emisi_provinsi": provinsi, "emisi_nasional": nasional}
