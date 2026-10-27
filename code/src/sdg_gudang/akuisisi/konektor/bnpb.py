"""Konektor BNPB (``data.bnpb.go.id``, CKAN): kejadian dan dampak bencana per provinsi dan kabupaten/kota
(SDG 13.1.1, juga 1.5.1 dan 11.5.1).

Jalur akses (diperiksa 20 Okt 2026):

- **Action API** ``/api/3/action/*`` menjawab 200 dengan User-Agent peramban (agen bawaan ditolak 403).
- **Unduhan berkas** ``/dataset/<id>/resource/<id>/download/*.xlsx``, halaman HTML, dan ``robots.txt``
  dijawab tantangan Cloudflare (403, ``cf-mitigated: challenge``). Tantangan tidak dilewati. Konektor
  mencoba satu unduhan sebagai penguji; bila ditantang, berkas XLSX asli tidak diunduh dan isi tabel
  diambil dari **DataStore CKAN** (``datastore_search``), yaitu hasil impor XLSX oleh CKAN sendiri yang
  disajikan lewat Action API resmi. Bila suatu hari unduhan tidak lagi ditantang, XLSX asli ikut disimpan.
- Dataset tahunan 2002–2023 (``jumlah-kejadian-dan-dampak-bencana-tahun-YYYY``) hanya berisi tautan folder
  Google Drive; tidak diambil (bukan berkas CKAN), dicatat di manifest.

Raw: ``ckan/package_search-<org>-<n>.json`` (metadata semua dataset organisasi), ``datastore/<dataset>/
<resource_id>.json`` (respons DataStore apa adanya, semua halaman digabung dalam satu objek ``halaman``),
dan ``xlsx/<dataset>/<berkas>`` bila unduhan terbuka.

Rilis: satu per resource, ``pembaruan_sumber``, kode ``<resource_id>@<metadata_modified>``, tanggal =
``last_modified`` resource (jatuh ke ``metadata_modified`` bila kosong).

Bronze (baris DataStore apa adanya; ``_id`` CKAN disimpan sebagai ``_id_ckan``): ``provinsi`` (tabel yang
mempunyai kolom kode/nama provinsi dan tidak mempunyai kolom kabupaten), ``kabupaten``, dan ``lain``
(rekap per jenis bencana, nasional per tahun). Kolom tambahan ``_dataset``, ``_resource_id``,
``_resource_nama``, ``_lisensi``.

Mutu kunci: setiap tabel ``provinsi`` diperiksa dengan ``Rujukan.periksa_batch`` terhadap sistem ``bps``,
``kemendagri``, dan ``nama``; ringkasannya masuk ``catatan``.

Opsi: ``org=pusdatinkom``, ``pola=<regex nama dataset>``, ``maks_resource=N`` (uji cepat).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from .. import inti

SUMBER = "bnpb"

CKAN = "https://data.bnpb.go.id"
API = f"{CKAN}/api/3/action"
DIBI = "https://dibi.bnpb.go.id/"
ORG = "pusdatinkom"
#: Agen peramban: Action API menolak agen bawaan (403). Tidak dipakai untuk melewati tantangan.
AGEN_PERAMBAN = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
                 "Chrome/126.0 Safari/537.36 LigaLakehouse-penelitian/0.2 (+https://sd.itera.ac.id)")
#: Dataset kompilasi kejadian dan dampak bencana milik Pusdatinkom.
POLA_DATASET = (r"^(kompilasi-data-(jumlah-dan-dampak-kejadian|kejadian-dan-dampak)-bencana-\d{4}"
                r"|data-bencana-indonesia|data-bencana|rekapr3p\d{4}-\d{4}"
                r"|jumlah-kejadian-dan-dampak-bencana-tahun-\d{4}|datakejadian\d{4})$")
BATAS_DATASTORE = 32000

POLA_KODE_PROV = re.compile(r"(?i)^kode\s*(wilayah\s*)?prov")
POLA_NAMA_PROV = re.compile(r"(?i)^(nama\s+)?provinsi$")
POLA_KAB = re.compile(r"(?i)kabupaten|kab\s*/\s*kota|kota")


# ---------------------------------------------------------------------------------------------------
# Fungsi murni (diuji luring)
# ---------------------------------------------------------------------------------------------------

def pilih_dataset(paket: list[dict], pola: str = POLA_DATASET) -> list[dict]:
    """Dataset yang namanya cocok pola, urut nama."""
    p = re.compile(pola)
    return sorted((d for d in paket if p.match(d.get("name", ""))), key=lambda d: d["name"])


def host_resource(res: dict) -> str:
    return urlsplit(res.get("url") or "").netloc


def kode_rilis(res: dict) -> str:
    return f"{res['id']}@{res.get('metadata_modified') or res.get('last_modified') or 'tanpa-tanggal'}"


def rilis_resource(pkg: dict, res: dict) -> inti.Rilis:
    tgl = res.get("last_modified") or res.get("metadata_modified") or ""
    bukti = (f"CKAN resource last_modified={res.get('last_modified') or '-'}; "
             f"metadata_modified={res.get('metadata_modified') or '-'}; "
             f"dataset {pkg['name']} metadata_modified={pkg.get('metadata_modified') or '-'}")
    cakupan = f"{pkg['name']}: {res.get('name') or res['id']} (lisensi {pkg.get('license_id') or 'tidak ada'})"
    return inti.Rilis(SUMBER, kode_rilis(res), "pembaruan_sumber" if tgl else "tidak_diketahui", tgl, bukti,
                      cakupan=cakupan)


def kolom_wilayah(fields: list[str]) -> dict:
    """Kolom kode provinsi, nama provinsi, dan apakah tabel bertingkat kabupaten/kota."""
    kode = next((f for f in fields if POLA_KODE_PROV.match(f.strip())), None)
    nama = next((f for f in fields if POLA_NAMA_PROV.match(f.strip())), None)
    kab = any(POLA_KAB.search(f) for f in fields if f not in (kode, nama))
    return {"kode": kode, "nama": nama, "kabupaten": kab}


def kelas_tabel(fields: list[str]) -> str:
    k = kolom_wilayah(fields)
    if k["kabupaten"]:
        return "kabupaten"
    if k["kode"] or k["nama"]:
        return "provinsi"
    return "lain"


def gabung_halaman(halaman: list[dict]) -> tuple[list[str], list[dict]]:
    """Nama kolom (urut DataStore) dan semua record dari beberapa halaman ``datastore_search``."""
    fields = [f["id"] for f in halaman[0]["result"]["fields"]] if halaman else []
    rec = [r for h in halaman for r in h["result"]["records"]]
    return fields, rec


def baris_bronze(records: list[dict], pkg: dict, res: dict) -> list[dict]:
    """Record DataStore apa adanya; ``_id`` CKAN menjadi ``_id_ckan`` agar tidak bentrok kolom baku."""
    out = []
    for r in records:
        b = {("_id_ckan" if k == "_id" else k): v for k, v in r.items()}
        b |= {"_dataset": pkg["name"], "_resource_id": res["id"], "_resource_nama": res.get("name") or "",
              "_lisensi": pkg.get("license_id") or ""}
        out.append(b)
    return out


def teks_kode(v) -> str | None:
    """Kode wilayah dari sel DataStore (11, 11.0, "11") menjadi teks tanpa desimal; kosong -> None."""
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v).strip()
    return str(int(f)) if f == int(f) else str(v)


def ringkas_periksa(hasil: dict, nama_wilayah: dict[int, str]) -> dict:
    """Ringkasan ``periksa_batch`` yang ringkas untuk manifest."""
    return {"cocok": len(hasil["cocok"]), "duplikat": hasil["duplikat"], "tidak_dikenal": hasil["tidak_dikenal"],
            "ambigu": hasil["ambigu"], "hilang": [f"{k} {nama_wilayah.get(k, '')}".strip() for k in hasil["hilang"]]}


def periksa_provinsi(ruj, fields: list[str], records: list[dict]) -> dict:
    """Periksa kunci provinsi satu tabel terhadap sistem bps, kemendagri, dan nama."""
    nama_w = {w["wilayah_kode"]: w["nama"] for w in ruj.wilayah if w["terkini"]}
    k = kolom_wilayah(fields)
    hasil: dict = {"kolom_kode": k["kode"], "kolom_nama": k["nama"], "baris": len(records)}
    if k["kode"]:
        kode = [teks_kode(r.get(k["kode"])) for r in records]
        hasil["kode_kosong"] = sum(x is None for x in kode)
        kode = [x for x in kode if x is not None]
        # Resolver mengandaikan kode angka; kode lain dicatat terpisah, tidak diperiksa.
        hasil["kode_bukan_angka"] = sorted({x for x in kode if not x.isdigit()})
        kode = [x for x in kode if x.isdigit()]
        for sistem in ("bps", "kemendagri"):
            hasil[sistem] = ringkas_periksa(ruj.periksa_batch(sistem, kode), nama_w)
    if k["nama"]:
        nama = [str(r.get(k["nama"]) or "").strip() for r in records]
        hasil["nama_kosong"] = sum(not x for x in nama)
        hasil["nama"] = ringkas_periksa(ruj.periksa_batch("nama", [x for x in nama if x]), nama_w)
    return hasil


def adalah_tantangan(status: int | None, header: dict, isi: bytes = b"") -> bool:
    """Respons tantangan bot (Cloudflare) yang tidak boleh dilewati."""
    h = {k.lower(): v for k, v in (header or {}).items()}
    return (h.get("cf-mitigated") == "challenge"
            or (status in (403, 503) and (b"Just a moment" in isi[:4000] or b"_cf_chl_opt" in isi)))


def nama_berkas_aman(teks: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", teks).strip("_")[:120] or "berkas"


# ---------------------------------------------------------------------------------------------------
# Jaringan
# ---------------------------------------------------------------------------------------------------

def _rujukan():
    from sdg_gudang import referensi as R

    w, p = R.bangun_wilayah(), R.bangun_padanan()
    return R.Rujukan(w, p, R.bangun_alias(w, p))


def _cari_paket(http: inti.Http, snap: inti.Snapshot, org: str) -> list[dict]:
    paket, mulai, n = [], 0, 0
    while True:
        params = {"fq": f"organization:{org}", "rows": 1000, "start": mulai}
        r = http.get(f"{API}/package_search", params=params)
        n += 1
        snap.simpan(f"ckan/package_search-{org}-{n:02d}.json", r.content, f"{API}/package_search?{urlencode(params)}")
        hasil = r.json()["result"]
        paket += hasil["results"]
        mulai += len(hasil["results"])
        if not hasil["results"] or mulai >= hasil["count"]:
            return paket


def _datastore(http: inti.Http, rid: str) -> tuple[list[dict], bytes, str]:
    halaman, offset = [], 0
    while True:
        params = {"resource_id": rid, "limit": BATAS_DATASTORE, "offset": offset}
        js = http.get_json(f"{API}/datastore_search", params=params)
        halaman.append(js)
        offset += len(js["result"]["records"])
        if not js["result"]["records"] or offset >= js["result"].get("total", 0):
            break
    isi = json.dumps({"resource_id": rid, "halaman": halaman}, ensure_ascii=False).encode("utf-8")
    return halaman, isi, f"{API}/datastore_search?{urlencode({'resource_id': rid})}"


def _uji_unduhan(http: inti.Http, url: str) -> tuple[bool, bytes | None, str]:
    """(terbuka, isi, keterangan). Tantangan Cloudflare berarti tertutup; tidak dicoba lewat cara lain."""
    import requests

    try:
        r = http.get(url)
    except requests.HTTPError as e:
        resp = e.response
        if resp is not None and adalah_tantangan(resp.status_code, dict(resp.headers), resp.content):
            return False, None, f"HTTP {resp.status_code} tantangan Cloudflare (cf-mitigated={resp.headers.get('cf-mitigated')})"
        return False, None, f"HTTP {getattr(resp, 'status_code', '?')}"
    except Exception as e:  # noqa: BLE001 - dicatat sebagai galat
        return False, None, str(e)[:200]
    if adalah_tantangan(r.status_code, dict(r.headers), r.content):
        return False, None, "tantangan Cloudflare pada respons 200"
    return True, r.content, f"HTTP {r.status_code}"


#: Folder berkas yang diunduh tangan oleh penanggung jawab lewat peramban (unduhan berkas CKAN dijawab
#: tantangan Cloudflare yang tidak dilewati konektor). Daftar dan cara unduh: docs/gudang/unduh-tangan.md.
TANGAN = inti.AKAR / "data" / "unduh-tangan" / "bnpb"


def nama_simpan(res: dict) -> str:
    """Nama berkas yang diharapkan bila resource diunduh lewat peramban (nama di ujung URL)."""
    from urllib.parse import unquote
    return unquote(urlsplit(res.get("url", "")).path.rsplit("/", 1)[-1]) or res["id"]


def cari_berkas_tangan(res: dict, berkas: list[Path], dataset: str = "") -> Path | None:
    """Berkas unduhan tangan untuk resource ini: nama sama dengan ujung URL, memuat id resource, atau
    (untuk tautan folder Google Drive) arsip zip di subfolder bernama dataset."""
    target = nama_simpan(res).lower()
    for f in berkas:
        n = f.name.lower()
        if n == target or res["id"] in n:
            return f
    if host_resource(res) == "drive.google.com" and dataset:
        for f in berkas:
            if f.parent.name == dataset and f.suffix.lower() in (".zip", ".xlsx"):
                return f
    return None


def baris_xlsx(isi: bytes, nama: str = "") -> list[tuple[str, list[str], list[dict]]]:
    """Baris dari XLSX (atau zip berisi XLSX): satu entri (lembar, kepala, baris) per lembar. Kepala adalah
    baris pertama dengan >= 2 sel teks; nilai disimpan apa adanya sebagai teks."""
    import io
    import zipfile

    import openpyxl

    def satu(b: bytes, awalan: str) -> list:
        wb = openpyxl.load_workbook(io.BytesIO(b), read_only=True, data_only=True)
        hasil = []
        for ws in wb.worksheets:
            semua = [list(r) for r in ws.iter_rows(values_only=True)]
            i_kepala = next((i for i, r in enumerate(semua)
                             if sum(isinstance(v, str) and v.strip() != "" for v in r) >= 2), None)
            if i_kepala is None:
                continue
            kepala, dipakai = [], set()
            for j, v in enumerate(semua[i_kepala]):
                k = str(v).strip() if v not in (None, "") else f"kolom_{j}"
                while k in dipakai:
                    k += "_"
                dipakai.add(k)
                kepala.append(k)
            baris = [{kepala[j]: (None if v is None else str(v)) for j, v in enumerate(r) if j < len(kepala)}
                     for r in semua[i_kepala + 1:] if any(v not in (None, "") for v in r)]
            hasil.append((f"{awalan}{ws.title}", kepala, baris))
        wb.close()
        return hasil

    if nama.lower().endswith(".zip") or isi[:2] == b"PK" and b"xl/workbook" not in isi[:4096]:
        try:
            with zipfile.ZipFile(io.BytesIO(isi)) as z:
                if not any(n.startswith("xl/") for n in z.namelist()):
                    out = []
                    for n in sorted(z.namelist()):
                        if n.lower().endswith(".xlsx"):
                            out += satu(z.read(n), f"{n}:")
                    return out
        except zipfile.BadZipFile:
            pass
    return satu(isi, "")


def jalankan(snap: inti.Snapshot, opsi: dict) -> dict:
    http = inti.Http(agen=AGEN_PERAMBAN, jeda_s=float(opsi.get("jeda_s", 1.0)))
    org = opsi.get("org", ORG)
    ruj = _rujukan()

    paket = _cari_paket(http, snap, org)
    dipilih = pilih_dataset(paket, opsi.get("pola", POLA_DATASET))
    snap.catatan.append({"apa": "dataset terpilih", "org": org, "jumlah_paket_org": len(paket),
                         "dataset": [{"nama": d["name"], "lisensi": d.get("license_id") or "",
                                      "resource": len(d.get("resources", [])),
                                      "metadata_modified": d.get("metadata_modified")} for d in dipilih]})
    lisensi = sorted({d.get("license_id") or "tidak ada" for d in dipilih})
    snap.catatan.append({"apa": "lisensi per dataset berbeda", "lisensi": lisensi,
                         "keterangan": "kelas A-SA di inti berlaku per sumber; lisensi per dataset ada di "
                                       "cakupan rilis dan kolom Bronze _lisensi"})

    # Uji satu unduhan berkas: menentukan apakah XLSX asli dapat disimpan.
    contoh = next((r for d in dipilih for r in d.get("resources", [])
                   if host_resource(r) == urlsplit(CKAN).netloc and r.get("url_type") == "upload"), None)
    unduh_terbuka = False
    if contoh is not None:
        unduh_terbuka, _, ket = _uji_unduhan(http, contoh["url"])
        snap.catatan.append({"apa": "uji unduhan berkas CKAN", "url": contoh["url"], "terbuka": unduh_terbuka,
                             "keterangan": ket})
        if not unduh_terbuka:
            snap.tambah_galat("unduhan XLSX", f"{ket}; berkas asli tidak diunduh, isi diambil dari DataStore API")

    tangan_dir = Path(opsi.get("tangan", TANGAN))
    berkas_tangan = sorted(f for f in tangan_dir.rglob("*") if f.is_file()) if tangan_dir.exists() else []
    tangan_dipakai: list[str] = []

    maks = int(opsi.get("maks_resource", 0)) or None
    hitung = {"datastore": 0, "xlsx": 0, "drive": 0, "lain_host": 0, "tanpa_datastore_tertutup": 0,
              "datastore_tidak_ada": 0}
    periksa, tanpa = [], []
    baris_total = 0
    n = 0
    for pkg in dipilih:
        for res in pkg.get("resources", []):
            if maks is not None and n >= maks:
                break
            host = host_resource(res)
            f_tangan = cari_berkas_tangan(res, berkas_tangan, pkg["name"])
            if f_tangan is not None:  # berkas tangan didahulukan; DataStore resource itu tidak diambil lagi
                rilis = rilis_resource(pkg, res)
                rid = snap.tambah_rilis(rilis)
                isi = f_tangan.read_bytes()
                nama = f"tangan/{pkg['name']}/{res['id']}-{nama_berkas_aman(f_tangan.name)}"
                snap.simpan(nama, isi, res.get("url", ""), resource_id=res["id"], rilis_id=rid,
                            diunduh_tangan=True, berkas_lokal=str(f_tangan.relative_to(inti.AKAR))
                            if inti.AKAR in f_tangan.parents else f_tangan.name)
                try:
                    for lembar, kepala, baris in baris_xlsx(isi, f_tangan.name):
                        tabel = kelas_tabel(kepala)
                        rows = [r | {"_lembar": lembar} for r in baris_bronze(baris, pkg, res)]
                        baris_total += snap.tulis_bronze(tabel, rows, rid, nama)
                        if tabel == "provinsi":
                            periksa.append({"dataset": pkg["name"], "resource": res["id"], "nama": res.get("name"),
                                            "lembar": lembar} | periksa_provinsi(ruj, kepala, baris))
                except Exception as e:  # noqa: BLE001
                    snap.tambah_galat(f"urai berkas tangan {f_tangan.name}", e)
                hitung["tangan"] = hitung.get("tangan", 0) + 1
                tangan_dipakai.append(f_tangan.name)
                continue
            if host == "drive.google.com":
                hitung["drive"] += 1
                tanpa.append({"dataset": pkg["name"], "resource": res["id"], "alasan": "tautan folder Google Drive"})
                continue
            if host and host != urlsplit(CKAN).netloc:
                hitung["lain_host"] += 1
                tanpa.append({"dataset": pkg["name"], "resource": res["id"], "alasan": f"host {host}"})
                continue
            n += 1
            rilis = rilis_resource(pkg, res)
            rid = rilis.rilis_id
            if unduh_terbuka and res.get("url"):
                ok, isi, ket = _uji_unduhan(http, res["url"])
                if ok and isi:
                    snap.tambah_rilis(rilis)
                    nama = f"xlsx/{pkg['name']}/{res['id']}-{nama_berkas_aman(res['url'].rsplit('/', 1)[-1])}"
                    snap.simpan(nama, isi, res["url"], resource_id=res["id"], rilis_id=rid)
                    hitung["xlsx"] += 1
                else:
                    snap.tambah_galat(f"unduh {res['id']}", ket)
            if not res.get("datastore_active"):
                if not unduh_terbuka:
                    hitung["tanpa_datastore_tertutup"] += 1
                    tanpa.append({"dataset": pkg["name"], "resource": res["id"], "nama": res.get("name"),
                                  "alasan": "tanpa DataStore dan unduhan berkas ditantang Cloudflare"})
                continue
            try:
                halaman, isi, url = _datastore(http, res["id"])
            except Exception as e:  # noqa: BLE001
                hitung["datastore_tidak_ada"] += 1
                snap.tambah_galat(f"datastore {pkg['name']}/{res['id']} ({res.get('name')})", e)
                continue
            snap.tambah_rilis(rilis)
            berkas_bronze = f"datastore/{pkg['name']}/{res['id']}.json"
            snap.simpan(berkas_bronze, isi, url, resource_id=res["id"], rilis_id=rid,
                        jenis="respons datastore_search CKAN (impor XLSX oleh CKAN)")
            hitung["datastore"] += 1
            fields, records = gabung_halaman(halaman)
            tabel = kelas_tabel([f for f in fields if f != "_id"])
            baris_total += snap.tulis_bronze(tabel, baris_bronze(records, pkg, res), rid, berkas_bronze)
            if tabel == "provinsi":
                periksa.append({"dataset": pkg["name"], "resource": res["id"], "nama": res.get("name")}
                               | periksa_provinsi(ruj, fields, records))

    snap.catatan.append({"apa": "resource tidak diambil", "hitung": {k: v for k, v in hitung.items()
                                                                     if k in ("drive", "lain_host",
                                                                              "tanpa_datastore_tertutup")},
                         "daftar": tanpa})
    snap.catatan.append({"apa": "periksa_batch tabel provinsi", "tabel": periksa})
    sisa = [f.name for f in berkas_tangan if f.name not in tangan_dipakai]
    snap.catatan.append({"apa": "berkas unduh tangan", "folder": str(tangan_dir), "dipakai": tangan_dipakai,
                         "tidak_cocok": sisa})

    # dibi.bnpb.go.id hanya diuji sekali dengan batas waktu pendek.
    try:
        r = inti.Http(agen=AGEN_PERAMBAN, coba=1, batas_waktu=20).get(DIBI)
        snap.catatan.append({"apa": "uji dibi.bnpb.go.id", "status": r.status_code, "bita": len(r.content)})
    except Exception as e:  # noqa: BLE001
        snap.catatan.append({"apa": "uji dibi.bnpb.go.id", "galat": str(e)[:200]})

    return {"dataset": len(dipilih), "rilis": len(snap.rilis), "bronze_baris": baris_total} | hitung
