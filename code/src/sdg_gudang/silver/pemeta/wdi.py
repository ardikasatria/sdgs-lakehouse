"""Pemeta Silver keluarga WDI: API terkini (``wdi``) dan arsip versi DataBank (``wdi_arsip``).

- S01: sumber hanya Indonesia; ``country_id`` ID/IDN -> nasional 9999 (``iso3166_1``). Negara lain -> di luar.
- S02: ``date`` (API) atau ``time_value`` (arsip) adalah tahun.
- S03: ``value`` kosong (None) -> kosong.
- S04: WDI tidak mengisi kolom ``unit``; satuan tersirat pada nama seri baris itu sendiri (``indicator_value``
  atau ``series_value`` per versi), biasanya di kurung terakhir: ``(% of GDP)``, ``(constant 2015 US$)``.
  Kurung dibaca dari belakang; kurung yang bukan satuan (``modeled ILO estimate``, ``cumulative``) dilewati.
  Tahun dasar harga konstan menjadi bagian ``satuan_id`` karena nilai dengan tahun dasar berbeda tidak
  sebanding. Satuan yang belum ada di ``dim_satuan`` memakai id lokal berawalan ``x_``.
- S05: WDI tidak punya dimensi rincian; rincian (jenis kelamin, umur) melekat pada seri -> ``total``.
- S06: metadata sumber 46 (``seri_sdg46``) hanya daftar seri tanpa kode indikator SDG terstruktur, jadi
  ``kode_global`` kosong dan konsep jatuh ke ``seri:wdi:<kode>`` kecuali ada padanan seri.
- S07: ``obs_status`` kosong di semua baris dan tidak ada catatan kaki per baris -> ``tidak_diketahui``. Penanda
  ``modeled ILO estimate`` pada nama seri adalah sifat seri, bukan baris, dan tidak dipakai.
"""
from __future__ import annotations

import re

from sdg_gudang import referensi as R

from .. import inti as S

METADATA = {"indikator", "seri_sdg46"}
INDONESIA = {"ID", "IDN"}
K = S.SatuanKanonik

#: Pola teks satuan di dalam kurung (huruf kecil) -> satuan kanonik; ``{1}`` diisi tahun dasar.
POLA_KURUNG: list[tuple[str, str, str]] = [
    (r".*%.*", "persen", "1"),
    (r"constant (\d{4}) us\$", "x_usd_konstan_{1}", "1"),
    (r"constant (\d{4}) (?:ppp|international) \$", "x_ppp_konstan_{1}", "1"),
    (r"(?:bop, )?current us\$", "x_usd_berlaku", "1"),
    (r"current international \$", "x_ppp_berlaku", "1"),
    (r"current lcu", "x_lcu_berlaku", "1"),
    (r"constant lcu", "x_lcu_konstan", "1"),
    (r"lcu per us\$", "x_lcu_per_usd", "1"),
    (r"lcu per international \$", "x_lcu_per_ppp", "1"),
    (r"mj/\$(\d{4}) ppp gdp", "x_mj_per_ppp_konstan_{1}", "1"),
    (r"kg per (\d{4}) us\$ of gdp", "x_kg_per_usd_konstan_{1}", "1"),
    (r"kg per (\d{4}) ppp \$ of gdp", "x_kg_per_ppp_konstan_{1}", "1"),
    (r"kg per ppp \$ of gdp", "x_kg_per_ppp_konstan", "1"),  # tahun dasar tidak dinyatakan
    (r"kg per hectare", "x_kg_per_hektar", "1"),
    (r"constant (\d{4}) us\$ gdp per cubic meter of total freshwater withdrawal", "x_usd_konstan_{1}_per_m3", "1"),
    (r"billion cubic meters", "x_meter_kubik", "1000000000"),
    (r"cubic meters", "x_meter_kubik", "1"),
    (r"metric tons", "kilogram", "1000"),
    (r"metric tons per capita", "x_ton_per_kapita", "1"),
    (r"micrograms per cubic meter", "x_mikrogram_per_m3", "1"),
    (r"million passenger-km", "x_penumpang_km", "1000000"),
    (r"million ton-km", "x_ton_km", "1000000"),
    (r"modeled estimate, per 100,000 live births", "x_per_100000_kelahiran_hidup", "1"),
    (r"per 1,000 live births?s?", "per_1000_kelahiran_hidup", "1"),  # termasuk salah ketik sumber "birthsS"
    (r"per 1,000 people", "per_1000_penduduk", "1"),
    (r"births per 1,000 women ages 15-19", "per_1000_perempuan_15_19", "1"),
    (r"per 1,000 population at risk", "x_per_1000_penduduk_berisiko", "1"),
    (r"per 1,000 uninfected population ages 15-49", "x_per_1000_penduduk_tidak_terinfeksi", "1"),
    (r"new registrations per 1,000 people ages 15-64", "x_per_1000_penduduk_15_64", "1"),
    (r"per 100,000 adults", "x_per_100000_dewasa", "1"),
    (r"per 100,000 female(?: population)?", "x_per_100000_perempuan", "1"),
    (r"per 100,000 male(?: population)?", "x_per_100000_laki_laki", "1"),
    (r"per 100,000 (?:people|population)", "x_per_100000_penduduk", "1"),
    (r"per million people", "x_per_1000000_penduduk", "1"),
    (r"scale 0 - 100", "x_skala_0_100", "1"),
    (r"scale 1-100", "x_skala_1_100", "1"),
    (r"1-5 scale; 5=best", "x_skala_1_5", "1"),
    (r"1=yes; 0=no", "x_biner", "1"),
    (r"gpi", "indeks", "1"),  # indeks paritas gender
    (r"years", "tahun", "1"),
    (r"liters of pure alcohol, projected estimates, (?:fe)?(?:male )?15\+ years of age",
     "x_liter_alkohol_murni_per_kapita", "1"),
    (r"number of people", "jiwa", "1"),
    (r"sq\. km", "hektar", "100"),  # 1 km2 = 100 ha
]

#: Nama seri tanpa kurung satuan -> satuan kanonik (pola atas nama lengkap, huruf kecil).
POLA_NAMA: list[tuple[str, str]] = [
    (r"air transport, passengers carried", "x_jumlah"),
    (r"(?:bird|fish|mammal|plant) species.*, threatened", "x_jumlah"),
    (r"patent applications, (?:non)?residents", "x_jumlah"),
    (r"children out of school, primary.*", "jiwa"),
    (r"number of people spending more than \d+% of household .*", "jiwa"),
    (r"urban population", "jiwa"),
    (r"broad money to total reserves ratio", "x_rasio"),
    (r"pupil-teacher ratio, .*", "x_rasio"),
    (r"total reserves in months of imports", "x_bulan"),
    # ER.H2O.FWST.ZS: nama tidak memuat satuan; akhiran kode WDI ``.ZS`` berarti persen.
    (r"level of water stress: freshwater withdrawal as a proportion of available freshwater resources", "persen"),
]


def satuan(nama: str) -> tuple[S.SatuanKanonik, str]:
    """S04: nama seri -> (satuan kanonik, teks satuan sumber)."""
    for kurung in reversed(re.findall(r"\(([^()]*)\)", nama or "")):
        t = re.sub(r"\s+", " ", kurung.strip().lower())
        for pola, sid, faktor in POLA_KURUNG:
            m = re.fullmatch(pola, t)
            if m:
                return K(sid.replace("{1}", m.group(1) if m.groups() else ""), faktor), kurung.strip()
    t = re.sub(r"\s+", " ", (nama or "").strip().lower())
    for pola, sid in POLA_NAMA:
        if re.fullmatch(pola, t):
            return K(sid), nama
    raise S.Karantina("satuan_tidak_dikenal", "S04", repr(nama))


def _sel(seri: str, nama: str, negara: str, tahun: str, nilai_teks, ctx: S.Konteks):
    teks = {"wilayah": negara, "periode": tahun, "nilai": nilai_teks, "satuan": nama}

    def isi():
        if negara not in INDONESIA:
            raise S.DiLuar("bukan_indonesia")
        nilai, desimal = S.urai_nilai(nilai_teks)
        periode = S.periode_tahun(tahun)
        st, teks_satuan = satuan(nama)
        return S.obs(seri_kode=seri, **ctx.konsep("wdi", seri), wilayah_kode=R.NAS, tingkat="nasional",
                     sistem_wilayah="iso3166_1", periode=periode, rincian="total",
                     nilai=S.kali(nilai, st.faktor), desimal=desimal, satuan_id=st.satuan_id,
                     satuan_sumber=teks_satuan, faktor_satuan=st.faktor, sifat="tidak_diketahui",
                     aturan_silver="S01;S02;S03;S04;S05;S06;S07")

    return S.sel(seri, teks, isi)


def nilai_api(b: dict, ctx: S.Konteks):
    yield _sel(b["indicator_id"], b["indicator_value"], (b["country_id"] or "").strip(), b["date"], b["value"], ctx)


def nilai_arsip(b: dict, ctx: S.Konteks):
    yield _sel(b["series_id"], b["series_value"], (b["country_id"] or "").strip(), b["time_value"], b["value"], ctx)


def nilai(b: dict, ctx: S.Konteks):
    return nilai_arsip(b, ctx) if "series_id" in b else nilai_api(b, ctx)


TABEL = {"nilai": nilai}
