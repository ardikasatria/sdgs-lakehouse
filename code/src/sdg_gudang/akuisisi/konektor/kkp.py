"""Konektor portal data KKP (``portaldata.kkp.go.id``): kawasan konservasi perairan nasional dan statistik
kelautan-perikanan per provinsi (SDG 14).

Portal adalah aplikasi satu halaman dengan API tak terdokumentasi. Endpoint dan parameternya ditemukan
dengan membaca bundel JS publik (``/assets/index-2807ea35.js`` dan ``backend_helper_data_statistik-*.js``,
20 Okt 2026): instans axios ``/api`` (token pengguna kosong untuk tamu) dan ``/sttk`` (tanpa header).
Token Bearer tetap yang tertanam di bundel untuk instans lain **tidak dipakai**.

Yang dapat diambil tanpa masuk:

- ``/api/portal_local/prl_kawasan_konservasi``: 11 kawasan konservasi nasional (KKPN), provinsi, luas (ha),
  SK, ``tahun`` 2023. Parameter ``tahun`` ditolak ("Parameter {tahun} Tidak Didukung").
- ``/api/portal_local/rhl_mangrove``: rehabilitasi mangrove per desa (provinsi, kabupaten, bibit, luas).
- ``/sttk/api/statistik/<x>_tahunan`` (nasional per tahun) dan ``/sttk/api/statistik/<x>_per_prov?tahun=Y``
  untuk ``nelayan``, ``pembudidaya``, ``kirt`` (konsumsi ikan rumah tangga), ``ntn``, ``ntpi``.

Belum terpecahkan: ``/api/statistik/list/perikanan_tangkap_prov``, ``perikanan_budidaya_prov``,
``produksi_garam_prov`` (``/api`` menjawab "Parameter salah/kurang"; jalur ``/sttk`` yang dipakai bundel
menjawab HTTP 500 galat log Laravel). Konektor mencatat jawaban ``/api`` sekali per endpoint.

Rilis: ``tanggal_unduh``; kode ``<endpoint>@<sha256[:12]>`` atau ``<endpoint>/<tahun>@<sha256[:12]>``.
Bronze (satu tabel per endpoint agar skema setiap tabel seragam): ``kawasan_konservasi``, ``rhl_mangrove``,
``nasional_<x>_tahunan``, dan ``<x>_per_prov`` (kolom ``_endpoint``, ``_tahun_diminta``). Mutu kunci per endpoint-tahun lewat ``periksa_batch`` di ``catatan``. Kelas B.

Opsi: ``tahun=2019,2020`` (bawaan: tahun dari seri ``*_tahunan``, atau 2015 sampai tahun berjalan).
"""
from __future__ import annotations

import datetime as dt
import json
import re
from urllib.parse import urlencode

from .. import inti

SUMBER = "kkp"

DASAR = "https://portaldata.kkp.go.id"
API = f"{DASAR}/api"
STTK = f"{DASAR}/sttk/api/statistik"
AGEN_PERAMBAN = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
                 "Chrome/126.0 Safari/537.36 LigaLakehouse-penelitian/0.2 (+https://sd.itera.ac.id)")
PORTAL_LOCAL = {"prl_kawasan_konservasi": "kawasan_konservasi", "rhl_mangrove": "rhl_mangrove"}
#: endpoint per provinsi -> seri nasional tahunan yang memberi daftar tahun
PER_PROV = {"nelayan_per_prov": "nelayan_tahunan", "pembudidaya_per_prov": "pembudidaya_tahunan",
            "kirt_per_prov": "kirt_tahunan", "ntn_per_prov": "ntn_tahunan", "ntpi_per_prov": "ntpi_tahunan"}
BELUM_TERPECAHKAN = ("perikanan_tangkap_prov", "perikanan_budidaya_prov", "produksi_garam_prov",
                     "petambak_garam_prov")
KOLOM_KODE = ("id_prov", "kode_provinsi", "kode_prov")
KOLOM_NAMA = ("provinsi", "upper", "nama_provinsi")


# ---------------------------------------------------------------------------------------------------
# Fungsi murni (diuji luring)
# ---------------------------------------------------------------------------------------------------

def data_payload(js) -> list[dict]:
    """Daftar baris dari dua bentuk respons: ``{"status", "data": [...]}`` dan ``{"data": [...]}``."""
    if isinstance(js, dict) and isinstance(js.get("data"), list):
        return js["data"]
    if isinstance(js, list):
        return js
    return []


def tahun_dari_seri(rows: list[dict]) -> list[str]:
    """Tahun dari seri ``*_tahunan``; tanda sementara (``2026*``) dibuang untuk parameter permintaan."""
    out = set()
    for r in rows:
        m = re.match(r"^\s*(\d{4})", str(r.get("tahun") or ""))
        if m:
            out.add(m.group(1))
    return sorted(out)


def kode_rilis(endpoint: str, sha: str, tahun: str | None = None) -> str:
    return f"{endpoint}/{tahun}@{sha[:12]}" if tahun else f"{endpoint}@{sha[:12]}"


def baris_bronze(rows: list[dict], endpoint: str, tahun: str | None = None) -> list[dict]:
    tambah = {"_endpoint": endpoint} | ({"_tahun_diminta": tahun} if tahun else {})
    return [dict(r) | tambah | {"_urutan": i} for i, r in enumerate(rows, start=1)]


def ringkas_periksa(hasil: dict, nama_wilayah: dict[int, str]) -> dict:
    return {"cocok": len(hasil["cocok"]), "duplikat": hasil["duplikat"], "tidak_dikenal": hasil["tidak_dikenal"],
            "ambigu": hasil["ambigu"], "hilang": [f"{k} {nama_wilayah.get(k, '')}".strip() for k in hasil["hilang"]]}


def periksa_baris(ruj, rows: list[dict], unik_nama: bool = False) -> dict:
    """Periksa kunci provinsi: kolom kode (sistem bps dan kemendagri) dan kolom nama. Untuk tabel yang satu
    barisnya bukan satu provinsi (kawasan, desa), nama diperiksa sebagai himpunan (``unik_nama``)."""
    nama_w = {w["wilayah_kode"]: w["nama"] for w in ruj.wilayah if w["terkini"]}
    kunci = set().union(*(r.keys() for r in rows)) if rows else set()
    k_kode = next((k for k in KOLOM_KODE if k in kunci), None)
    k_nama = next((k for k in KOLOM_NAMA if k in kunci), None)
    hasil: dict = {"baris": len(rows), "kolom_kode": k_kode, "kolom_nama": k_nama}
    if k_kode:
        kode = [str(r.get(k_kode)).strip() for r in rows if r.get(k_kode) not in (None, "")]
        # Resolver mengandaikan kode angka; kode lain ("-") dicatat terpisah, tidak diperiksa.
        hasil["kode_bukan_angka"] = sorted({k for k in kode if not k.isdigit()})
        kode = [k for k in kode if k.isdigit()]
        for sistem in ("bps", "kemendagri"):
            hasil[sistem] = ringkas_periksa(ruj.periksa_batch(sistem, kode), nama_w)
    if k_nama:
        nama = [str(r.get(k_nama)).strip() for r in rows if r.get(k_nama)]
        hasil["nama"] = ringkas_periksa(ruj.periksa_batch("nama", sorted(set(nama)) if unik_nama else nama), nama_w)
    return hasil


# ---------------------------------------------------------------------------------------------------
# Jaringan
# ---------------------------------------------------------------------------------------------------

def _rujukan():
    from sdg_gudang import referensi as R

    w, p = R.bangun_wilayah(), R.bangun_padanan()
    return R.Rujukan(w, p, R.bangun_alias(w, p))


def _ambil(http: inti.Http, snap: inti.Snapshot, url: str, nama: str, params: dict | None = None):
    r = http.get(url, params=params)
    full = f"{url}?{urlencode(params)}" if params else url
    sha = snap.simpan(nama, r.content, full)
    return json.loads(r.content), sha


def jalankan(snap: inti.Snapshot, opsi: dict) -> dict:
    import requests

    http = inti.Http(agen=AGEN_PERAMBAN, jeda_s=float(opsi.get("jeda_s", 1.0)),
                     header={"Accept": "application/json"})
    ruj = _rujukan()
    ringkas: dict = {}
    periksa: dict = {}

    r = http.get(DASAR + "/")
    snap.simpan("index.html", r.content, DASAR + "/")
    bundel = re.findall(r'src="(/assets/index-[^"]+\.js)"', r.content.decode("utf-8", errors="replace"))
    snap.catatan.append({"apa": "bundel JS saat ini", "bundel": bundel,
                         "keterangan": "endpoint ditemukan dari index-2807ea35.js; bila nama bundel berubah, "
                                       "periksa ulang endpoint"})

    # portal_local tanpa parameter
    for ep, tabel in PORTAL_LOCAL.items():
        try:
            js, sha = _ambil(http, snap, f"{API}/portal_local/{ep}", f"portal_local/{ep}.json")
        except Exception as e:  # noqa: BLE001
            snap.tambah_galat(ep, e)
            continue
        rows = data_payload(js)
        th_data = sorted({str(x.get("tahun")) for x in rows if x.get("tahun")})
        rid = snap.tambah_rilis(inti.Rilis(SUMBER, kode_rilis(ep, sha), "tanggal_unduh", snap.tanggal,
                                           "tanpa tanggal rilis atau pembaruan pada payload",
                                           cakupan=f"{ep}; tahun data {','.join(th_data) or '-'}"))
        ringkas[tabel] = snap.tulis_bronze(tabel, baris_bronze(rows, ep), rid, f"portal_local/{ep}.json")
        periksa[ep] = periksa_baris(ruj, rows, unik_nama=True) | {"tahun_data": th_data}

    # seri nasional tahunan -> daftar tahun
    tahun_per_ep: dict[str, list[str]] = {}
    for ep_prov, ep_th in PER_PROV.items():
        try:
            js, sha = _ambil(http, snap, f"{STTK}/{ep_th}", f"sttk/{ep_th}.json")
        except Exception as e:  # noqa: BLE001
            snap.tambah_galat(ep_th, e)
            tahun_per_ep[ep_prov] = []
            continue
        rows = data_payload(js)
        rid = snap.tambah_rilis(inti.Rilis(SUMBER, kode_rilis(ep_th, sha), "tanggal_unduh", snap.tanggal,
                                           "tanpa tanggal rilis; tanda * pada tahun dibiarkan apa adanya",
                                           cakupan=f"{ep_th} nasional"))
        ringkas[f"nasional_{ep_th}"] = snap.tulis_bronze(f"nasional_{ep_th}", baris_bronze(rows, ep_th),
                                                         rid, f"sttk/{ep_th}.json")
        tahun_per_ep[ep_prov] = tahun_dari_seri(rows)

    bawaan = [str(y) for y in range(2015, dt.date.today().year + 1)]
    pilihan = [x.strip() for x in opsi["tahun"].split(",")] if opsi.get("tahun") else None
    tahun_berdata: dict[str, list[str]] = {}
    for ep in PER_PROV:
        daftar = pilihan or tahun_per_ep.get(ep) or bawaan
        tahun_berdata[ep] = []
        for th in daftar:
            nama = f"sttk/{ep}/tahun={th}.json"
            try:
                js, sha = _ambil(http, snap, f"{STTK}/{ep}", nama, {"tahun": th})
            except Exception as e:  # noqa: BLE001
                snap.tambah_galat(f"{ep}?tahun={th}", e)
                continue
            rows = data_payload(js)
            if not rows:
                continue
            tahun_berdata[ep].append(th)
            rid = snap.tambah_rilis(inti.Rilis(SUMBER, kode_rilis(ep, sha, th), "tanggal_unduh", snap.tanggal,
                                               "tanpa tanggal rilis pada payload",
                                               cakupan=f"{ep} tahun {th}"))
            ringkas[ep] = ringkas.get(ep, 0) + snap.tulis_bronze(ep, baris_bronze(rows, ep, th), rid, nama)
            periksa[f"{ep}?tahun={th}"] = periksa_baris(ruj, rows)
    snap.catatan.append({"apa": "tahun berdata per endpoint provinsi", "tahun": tahun_berdata})
    snap.catatan.append({"apa": "periksa_batch per endpoint", "hasil": periksa})

    # endpoint produksi yang parameternya belum ditemukan: catat jawaban /api sekali.
    belum = {}
    for ep in BELUM_TERPECAHKAN:
        url = f"{API}/statistik/list/{ep}"
        try:
            r = http.get(url)
            belum[ep] = {"status": r.status_code, "awal": r.text[:200]}
        except requests.HTTPError as e:
            resp = e.response
            belum[ep] = {"status": getattr(resp, "status_code", None), "awal": (resp.text[:200] if resp is not None else "")}
        except Exception as e:  # noqa: BLE001
            belum[ep] = {"galat": str(e)[:200]}
    snap.catatan.append({"apa": "endpoint produksi belum terpecahkan (tanpa parameter)", "jawaban": belum,
                         "keterangan": "jalur /sttk yang dipakai bundel menjawab HTTP 500 (galat log Laravel) "
                                       "pada uji 20 Okt 2026; parameter tidak ditemukan di potongan bundel "
                                       "yang dibaca"})
    try:
        js, _ = _ambil(http, snap, f"{STTK}/last_update_data", "sttk/last_update_data.json")
        snap.catatan.append({"apa": "last_update_data", "isi": js})
    except Exception as e:  # noqa: BLE001
        snap.tambah_galat("last_update_data", e)
    return ringkas | {"rilis": len(snap.rilis), "tahun_berdata": tahun_berdata}
