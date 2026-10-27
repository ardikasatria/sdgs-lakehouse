"""S09: agregasi kabupaten/kota ke provinsi (tambahan praregistrasi M3, 20 Oktober 2026).

Pemeta menandai sel kabupaten/kota sebagai ``DiLuar("kabkota", komponen=...)``; ``komponen`` adalah observasi
dengan ``wilayah_kode`` provinsi induknya, ``nilai`` (atau ``None`` bila kosong), dan kunci ``kabkota``. Modul ini
menjumlahkan komponen per (rilis, seri, provinsi, periode, rincian):

- satuan berjenis jumlah, laju massa, atau mata uang berlaku dijumlahkan;
- persentase yang dinyatakan di ``bobot`` (seri persen -> seri penyebut) dihitung ulang sebagai rata-rata
  berbobot penyebut, yaitu Sigma(penyebut x persen) / Sigma penyebut;
- ukuran lain tidak diagregasi;
- bila ``ambang`` diberikan, cakupan = kabupaten/kota bernilai / kabupaten/kota tercantum untuk provinsi itu di
  tabel yang sama; di bawah ambang -> karantina ``cakupan_agregasi_kurang``.
"""
from collections import defaultdict
from decimal import Decimal
from functools import lru_cache

from sdg_gudang import referensi as R

from . import inti as S

JENIS_ADITIF = {"jumlah", "laju_massa", "mata_uang_berlaku", "massa", "massa_setara", "luas"}


@lru_cache(maxsize=1)
def jenis_satuan() -> dict[str, str]:
    return {s.satuan_id: s.jenis for s in R.SATUAN}


def _teks(d: Decimal) -> str:
    return format(d.normalize(), "f") if d != 0 else "0"


def agregasikan(komponen: list[dict], bobot: dict[str, str] | None = None,
                ambang: float | None = None) -> tuple[list[dict], list[dict]]:
    """Kembalikan (observasi provinsi, karantina) dari komponen kabupaten/kota."""
    bobot = bobot or {}
    jenis = jenis_satuan()
    tercantum = defaultdict(set)  # (rilis, provinsi) -> kabkota
    per_kunci = defaultdict(dict)  # (rilis, seri, provinsi, periode, rincian) -> {kabkota: komponen}
    for k in komponen:
        tercantum[(k["rilis_id"], k["wilayah_kode"])].add(k["kabkota"])
        per_kunci[(k["rilis_id"], k["seri_kode"], k["wilayah_kode"], k["periode"], k["rincian"])][k["kabkota"]] = k
    obs, kar = [], []
    for (rilis, seri, prov, periode, rincian), per_kab in sorted(per_kunci.items(), key=lambda x: str(x[0])):
        contoh = next(iter(per_kab.values()))
        satuan = contoh["satuan_id"]
        if seri in bobot:
            penyebut = per_kunci.get((rilis, bobot[seri], prov, periode, rincian), {})
            pasang = [(Decimal(k["nilai"]), Decimal(penyebut[kab]["nilai"])) for kab, k in per_kab.items()
                      if k["nilai"] is not None and kab in penyebut and penyebut[kab]["nilai"] is not None]
            n = len(pasang)
            total_bobot = sum((w for _, w in pasang), Decimal(0))
            nilai = None if total_bobot == 0 else sum((v * w for v, w in pasang), Decimal(0)) / total_bobot
            cara = f"rata-rata berbobot {bobot[seri]}"
        elif jenis.get(satuan) in JENIS_ADITIF:
            isi = [Decimal(k["nilai"]) for k in per_kab.values() if k["nilai"] is not None]
            n = len(isi)
            nilai = sum(isi, Decimal(0)) if isi else None
            cara = "jumlah"
        else:
            continue
        if nilai is None:
            continue
        N = len(tercantum[(rilis, prov)])
        tanda = f"{cara} kabkota {n}/{N}" if ambang is not None else f"{cara} kabkota {n}"
        desimal = max(int(k["desimal"] or 0) for k in per_kab.values() if k["nilai"] is not None)
        dasar = {kk: contoh.get(kk) for kk in ("sumber", "keluarga", "tabel_bronze", "_berkas_raw", "_sha256_raw",
                                               "_snapshot")}
        if ambang is not None and n / N < ambang:
            kar.append(dasar | {"rilis_id": rilis, "seri_kode": seri, "alasan": "cakupan_agregasi_kurang", "aturan": "S09",
                                "rincian_galat": f"{n}/{N} kabupaten/kota bernilai (< {ambang:.0%})",
                                "teks_wilayah": str(prov), "teks_periode": periode, "teks_nilai": "",
                                "teks_satuan": satuan, "baris_bronze": f"S09:{n}/{N}"})
            continue
        if seri in bobot:
            nilai = nilai.quantize(Decimal(1).scaleb(-max(desimal, 2)))
        o = {kk: v for kk, v in contoh.items() if kk not in ("kabkota",)}
        o |= {"wilayah_kode": prov, "tingkat": "provinsi", "sistem_wilayah": "agregasi_kabkota", "nilai": _teks(nilai),
              "desimal": desimal, "agregasi": tanda, "aturan_silver": (contoh["aturan_silver"] or "") + ";S09",
              "baris_bronze": f"S09:{n}"}
        obs.append(o)
    return obs, kar


def komponen_dari(o: dict, kabkota: str) -> dict:
    """Bungkus observasi kab/kota (sudah berprovinsi induk) sebagai komponen S09."""
    return o | {"kabkota": kabkota}


def kosong_ke_none(fungsi):
    """Jalankan urai nilai; ``Kosong`` -> (None, 0) agar kab/kota tanpa nilai tetap terhitung tercantum."""
    try:
        return fungsi()
    except S.Kosong:
        return None, 0

