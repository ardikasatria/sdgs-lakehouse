"""Konektor SIPSN KLH/BPLH (``sampahnasional.kemenlh.go.id``): statistik pengelolaan sampah per
kabupaten/kota dengan kolom provinsi (proksi SDG 12.5.1 dan 11.6.1).

Payload (diperiksa 20 Okt 2026):

- ``/export/statistik-pengelolaan-sampah`` mengembalikan berkas ``.xls`` yang sebenarnya dokumen HTML:
  label tercetak (``Data Terverifikasi Update <tahun>``), waktu ekspor, filter, tabel *Ringkasan
  Indikator*, *Ringkasan Wilayah & Fasilitas*, dan *Detil Informasi* (satu baris per kabupaten/kota;
  519 baris pada 20 Okt 2026, termasuk 8 baris tanpa provinsi dan kabupaten).
- Beranda memuat ``var rawData = [...]`` (nilai peta per kabupaten/kota tanpa pembulatan tampilan).
- Parameter ``tahun`` hanya mengubah label dan nama berkas; isi tabel tetap. Konektor menguji ini pada
  setiap jalan: ekspor diminta untuk setiap tahun uji dan sidik (sha256) tabelnya dibandingkan dengan
  ekspor bawaan. Tahun yang isinya berbeda dicatat sebagai rilis tersendiri; yang sama hanya dicatat.

Rilis: tidak ada nomor rilis atau tanggal pembaruan, sehingga jenis bukti ``tanggal_unduh``; kode =
slug label tercetak + 12 karakter awal sidik tabel, misalnya ``data-terverifikasi-update-2026@0123abcd4567``.
Label tahun tercetak dicatat di ``cakupan`` dan bukan bukti tanggal rilis.

Bronze: ``detil_kabkota`` (tabel Detil Informasi apa adanya, kolom ``_urutan``), ``ringkasan_indikator`` dan
``ringkasan_wilayah_fasilitas`` (satu tabel Bronze per tabel ringkasan, kolom ``_tabel``), ``peta_kabkota`` (``rawData`` beranda). Kelas B: hanya untuk rekonsiliasi.

Opsi: ``tahun_uji=2018,2019,...`` (bawaan 2018 sampai tahun berjalan).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from urllib.parse import urlencode

from .. import inti

SUMBER = "sipsn"

DASAR = "https://sampahnasional.kemenlh.go.id"
EKSPOR = f"{DASAR}/export/statistik-pengelolaan-sampah"
AGEN_PERAMBAN = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
                 "Chrome/126.0 Safari/537.36 LigaLakehouse-penelitian/0.2 (+https://sd.itera.ac.id)")
JUDUL_DETIL = "Detil Informasi"
KOLOM_PROV = "Provinsi"
KOLOM_KAB = "Kota/Kabupaten"


# ---------------------------------------------------------------------------------------------------
# Fungsi murni (diuji luring)
# ---------------------------------------------------------------------------------------------------

def _teks(el) -> str:
    return re.sub(r"\s+", " ", el.text_content()).strip()


def urai_ekspor(html: str) -> dict:
    """Label, waktu ekspor, filter, dan semua tabel (judul h3 terdekat sebelumnya, header, baris)."""
    import lxml.html

    doc = lxml.html.fromstring(html)
    strong = doc.xpath("//p/strong")
    em = doc.xpath("//p/em")
    diekspor = next((_teks(p) for p in doc.xpath("//p") if _teks(p).startswith("Diekspor")), "")
    tabel = []
    for t in doc.xpath("//table"):
        h3 = t.xpath("preceding::h3[1]")
        baris = t.xpath(".//tr")
        if not baris:
            continue
        header = [_teks(c) for c in baris[0].xpath("./th|./td")]
        isi = [[_teks(c) for c in tr.xpath("./th|./td")] for tr in baris[1:]]
        tabel.append({"judul": _teks(h3[0]) if h3 else "", "header": header, "baris": isi})
    return {"label": _teks(strong[0]) if strong else "", "diekspor": diekspor,
            "filter": _teks(em[0]) if em else "", "tabel": tabel}


def sidik_tabel(urai: dict) -> str:
    """sha256 atas isi tabel saja (label dan waktu ekspor tidak ikut), untuk membandingkan unduhan."""
    isi = json.dumps([[t["judul"], t["header"], t["baris"]] for t in urai["tabel"]], ensure_ascii=False)
    return hashlib.sha256(isi.encode("utf-8")).hexdigest()


def tahun_label(label: str) -> str | None:
    m = re.search(r"(19|20)\d{2}", label or "")
    return m.group(0) if m else None


def slug(teks: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (teks or "").lower()).strip("-") or "tanpa-label"


def kode_rilis(label: str, sidik: str, awalan: str = "") -> str:
    return f"{awalan}{slug(label)}@{sidik[:12]}"


def tabel_judul(urai: dict, judul: str) -> dict | None:
    return next((t for t in urai["tabel"] if t["judul"] == judul), None)


def baris_tabel(t: dict, **tambahan) -> list[dict]:
    """Baris tabel sebagai dict dengan header apa adanya; header ganda diberi akhiran ``__2``."""
    nama, lihat = [], {}
    for h in t["header"]:
        lihat[h] = lihat.get(h, 0) + 1
        nama.append(h if lihat[h] == 1 else f"{h}__{lihat[h]}")
    out = []
    for i, b in enumerate(t["baris"], start=1):
        d = {nama[j] if j < len(nama) else f"_kolom_{j + 1}": v for j, v in enumerate(b)}
        out.append(d | {"_urutan": i} | tambahan)
    return out


def nama_tabel_ringkasan(judul: str) -> str:
    """Satu tabel Bronze per tabel ringkasan agar skema setiap tabel Bronze seragam."""
    s = slug(judul).replace("-", "_")
    return s if s.startswith("ringkasan") else f"ringkasan_{s}"


def urai_rawdata(html: str) -> list[dict] | None:
    m = re.search(r"var\s+rawData\s*=\s*(\[.*?\]);", html, flags=re.S)
    return json.loads(m.group(1)) if m else None


def label_beranda(html: str) -> str:
    m = re.search(r"(Data Terverifikasi[^<]{0,60})<", html)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def ringkas_periksa(hasil: dict, nama_wilayah: dict[int, str]) -> dict:
    return {"cocok": len(hasil["cocok"]), "duplikat": hasil["duplikat"], "tidak_dikenal": hasil["tidak_dikenal"],
            "ambigu": hasil["ambigu"], "hilang": [f"{k} {nama_wilayah.get(k, '')}".strip() for k in hasil["hilang"]]}


def periksa_detil(ruj, baris: list[dict]) -> dict:
    """Kunci provinsi tabel Detil: nama provinsi unik diperiksa (tabel bertingkat kab/kota, sehingga satu
    provinsi memang muncul berkali-kali), ditambah hitungan baris tanpa provinsi atau kabupaten."""
    nama_w = {w["wilayah_kode"]: w["nama"] for w in ruj.wilayah if w["terkini"]}
    prov = [b.get(KOLOM_PROV, "").strip() for b in baris]
    kab = [(b.get(KOLOM_PROV, "").strip(), b.get(KOLOM_KAB, "").strip()) for b in baris]
    kab_isi = [k for k in kab if k[1]]
    dup_kab = sorted({f"{p} / {k}" for p, k in kab_isi if kab_isi.count((p, k)) > 1})
    return {"baris": len(baris), "provinsi_kosong": sum(not p for p in prov),
            "kabupaten_kosong": sum(not k for _, k in kab), "provinsi_unik": len({p for p in prov if p}),
            "kabkota_unik": len(set(kab_isi)), "kabkota_ganda": dup_kab,
            "nama": ringkas_periksa(ruj.periksa_batch("nama", sorted({p for p in prov if p})), nama_w)}


# ---------------------------------------------------------------------------------------------------
# Jaringan
# ---------------------------------------------------------------------------------------------------

def _rujukan():
    from sdg_gudang import referensi as R

    w, p = R.bangun_wilayah(), R.bangun_padanan()
    return R.Rujukan(w, p, R.bangun_alias(w, p))


def _tahun_uji(opsi: dict) -> list[str]:
    if opsi.get("tahun_uji"):
        return [x.strip() for x in opsi["tahun_uji"].split(",") if x.strip()]
    return [str(y) for y in range(2018, dt.date.today().year + 1)]


def jalankan(snap: inti.Snapshot, opsi: dict) -> dict:
    http = inti.Http(agen=AGEN_PERAMBAN, jeda_s=float(opsi.get("jeda_s", 1.0)))
    ruj = _rujukan()
    ringkas: dict = {}

    # Beranda: label tercetak dan rawData peta.
    r = http.get(DASAR + "/")
    snap.simpan("beranda.html", r.content, DASAR + "/")
    beranda = r.content.decode("utf-8", errors="replace")
    lab_beranda = label_beranda(beranda)

    # Ekspor bawaan.
    r = http.get(EKSPOR)
    nama_ekspor = "ekspor/statistik-pengelolaan-sampah.xls"
    snap.simpan(nama_ekspor, r.content, EKSPOR, content_disposition=r.headers.get("content-disposition", ""),
                content_type=r.headers.get("content-type", ""), jenis="dokumen HTML berekstensi .xls")
    u = urai_ekspor(r.content.decode("utf-8", errors="replace"))
    sidik = sidik_tabel(u)
    rilis = inti.Rilis(SUMBER, kode_rilis(u["label"], sidik), "tanggal_unduh", snap.tanggal,
                       f"tanpa tanggal rilis; label tercetak {u['label']!r}; {u['diekspor']}; sidik tabel {sidik}",
                       cakupan=f"ekspor statistik pengelolaan sampah, {u['filter']}; label tahun tercetak "
                               f"{tahun_label(u['label']) or '-'} (bukan tanggal rilis)")
    rid = snap.tambah_rilis(rilis)
    detil = tabel_judul(u, JUDUL_DETIL)
    if detil is None:
        snap.tambah_galat("urai ekspor", f"tabel {JUDUL_DETIL!r} tidak ditemukan")
        baris = []
    else:
        baris = baris_tabel(detil)
        ringkas["detil_kabkota"] = snap.tulis_bronze("detil_kabkota", baris, rid, nama_ekspor)
        snap.catatan.append({"apa": "periksa_batch provinsi tabel Detil", **periksa_detil(ruj, baris)})
    for t in u["tabel"]:
        if t["judul"] != JUDUL_DETIL:
            tab = nama_tabel_ringkasan(t["judul"])
            ringkas[tab] = snap.tulis_bronze(tab, baris_tabel(t, _tabel=t["judul"]), rid, nama_ekspor)

    # rawData beranda sebagai rilis tersendiri (sidik dari isi rawData).
    raw = urai_rawdata(beranda)
    if raw is None:
        snap.tambah_galat("urai beranda", "rawData tidak ditemukan")
    else:
        s_raw = hashlib.sha256(json.dumps(raw, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        rid_b = snap.tambah_rilis(inti.Rilis(
            SUMBER, kode_rilis(lab_beranda, s_raw, "beranda-"), "tanggal_unduh", snap.tanggal,
            f"tanpa tanggal rilis; label beranda {lab_beranda!r}; sidik rawData {s_raw}",
            cakupan=f"rawData peta beranda per kabupaten/kota; label tahun tercetak {tahun_label(lab_beranda) or '-'}"))
        ringkas["peta_kabkota"] = snap.tulis_bronze(
            "peta_kabkota", [d | {"_urutan": i} for i, d in enumerate(raw, start=1)], rid_b, "beranda.html")

    # Uji parameter tahun: apakah ada tahun yang isinya berbeda?
    uji = []
    for th in _tahun_uji(opsi):
        try:
            r = http.get(EKSPOR, params={"tahun": th})
        except Exception as e:  # noqa: BLE001
            snap.tambah_galat(f"ekspor tahun={th}", e)
            continue
        nama = f"ekspor/tahun={th}.xls"
        snap.simpan(nama, r.content, f"{EKSPOR}?{urlencode({'tahun': th})}",
                    content_disposition=r.headers.get("content-disposition", ""))
        ut = urai_ekspor(r.content.decode("utf-8", errors="replace"))
        st = sidik_tabel(ut)
        sama = st == sidik
        uji.append({"tahun": th, "label": ut["label"], "sidik_tabel": st[:16], "isi_sama_dengan_bawaan": sama,
                    "berkas": nama})
        if not sama:
            rid_t = snap.tambah_rilis(inti.Rilis(
                SUMBER, kode_rilis(ut["label"], st, f"tahun-{th}-"), "tanggal_unduh", snap.tanggal,
                f"ekspor dengan tahun={th}; label {ut['label']!r}; sidik tabel {st}",
                cakupan=f"ekspor tahun={th}; label tahun tercetak {tahun_label(ut['label']) or '-'}"))
            dt_ = tabel_judul(ut, JUDUL_DETIL)
            if dt_:
                ringkas[f"detil_kabkota_tahun_{th}"] = snap.tulis_bronze(
                    "detil_kabkota", baris_tabel(dt_, _tahun_diminta=th), rid_t, nama)
    beda = [x["tahun"] for x in uji if not x["isi_sama_dengan_bawaan"]]
    snap.catatan.append({"apa": "uji parameter tahun ekspor", "bawaan_label": u["label"],
                         "bawaan_sidik_tabel": sidik[:16], "hasil": uji,
                         "kesimpulan": ("semua tahun uji mengembalikan tabel yang identik dengan ekspor bawaan; "
                                        "parameter tahun hanya mengubah label dan nama berkas, sehingga deret "
                                        "historis tidak dapat diambil") if not beda else
                                       f"tahun dengan isi berbeda: {beda}"})
    return {"rilis": len(snap.rilis), "label": u["label"], "tahun_berbeda": beda} | ringkas
