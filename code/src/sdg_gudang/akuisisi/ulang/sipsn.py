"""Bangun ulang Bronze ``sipsn`` (ekspor statistik pengelolaan sampah dan rawData beranda) dari raw gudang."""
from __future__ import annotations

import hashlib
import json

from .. import inti
from ..konektor import sipsn as k
from . import baca_raw

EKSPOR = "ekspor/statistik-pengelolaan-sampah.xls"


def ulang(snap: inti.Snapshot, m: dict) -> None:
    # Ekspor bawaan: Detil Informasi dan tabel ringkasan.
    u = k.urai_ekspor(baca_raw(snap, EKSPOR).decode("utf-8", errors="replace"))
    sidik = k.sidik_tabel(u)
    rid = f"{k.SUMBER}:{k.kode_rilis(u['label'], sidik)}"
    detil = k.tabel_judul(u, k.JUDUL_DETIL)
    if detil is not None:
        snap.tulis_bronze("detil_kabkota", k.baris_tabel(detil), rid, EKSPOR)
    for t in u["tabel"]:
        if t["judul"] != k.JUDUL_DETIL:
            snap.tulis_bronze(k.nama_tabel_ringkasan(t["judul"]), k.baris_tabel(t, _tabel=t["judul"]), rid, EKSPOR)

    # rawData beranda (sidik dari isi rawData).
    beranda = baca_raw(snap, "beranda.html").decode("utf-8", errors="replace")
    raw = k.urai_rawdata(beranda)
    if raw is not None:
        s_raw = hashlib.sha256(json.dumps(raw, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        rid_b = f"{k.SUMBER}:{k.kode_rilis(k.label_beranda(beranda), s_raw, 'beranda-')}"
        snap.tulis_bronze("peta_kabkota", [d | {"_urutan": i} for i, d in enumerate(raw, start=1)], rid_b,
                          "beranda.html")

    # Ekspor per tahun: hanya yang isinya berbeda dari ekspor bawaan yang masuk Bronze.
    for nama in sorted(n for n in snap.berkas if n.startswith("ekspor/tahun=")):
        th = nama.removeprefix("ekspor/tahun=").removesuffix(".xls")
        ut = k.urai_ekspor(baca_raw(snap, nama).decode("utf-8", errors="replace"))
        st = k.sidik_tabel(ut)
        if st == sidik:
            continue
        dt_ = k.tabel_judul(ut, k.JUDUL_DETIL)
        if dt_:
            rid_t = f"{k.SUMBER}:{k.kode_rilis(ut['label'], st, f'tahun-{th}-')}"
            snap.tulis_bronze("detil_kabkota", k.baris_tabel(dt_, _tahun_diminta=th), rid_t, nama)
