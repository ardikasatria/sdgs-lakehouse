"""Data rujukan dan induk ``dp_referensi`` (brief 4, fase M1; bukti unit J.62DMS00.008.1).

Dibangun dari snapshot ``raw/referensi/2026-10-20`` dan konfigurasi yang sudah ada di repositori:

- ``dim_wilayah``: dimensi berubah perlahan tipe 2 untuk 38 provinsi dan satu baris nasional. Provinsi
  induk pemekaran (Kalimantan Timur 2012, Papua dan Papua Barat 2022) mempunyai dua versi; provinsi
  pecahan berlaku sejak tanggal undang-undangnya.
- ``padanan_kode_wilayah``: kode BPS dan Kemendagri per periode bridging BPS, dengan penanda ambigu bila
  satu kode Kemendagri dipakai lebih dari satu provinsi pada periode itu.
- ``alias_wilayah``: nama dan kode dari sistem lain (BPS, Kemendagri, ISO 3166-2, GeoJSON) ke ``wilayah_kode``.
- ``dim_pilar``: empat pilar TPB menurut Permen PPN/Bappenas 1/2024 Pasal 4.
- ``dim_indikator``: indikator TPB nasional dari ``config/tpb/katalog_indikator_tpb.csv`` dipadankan dengan
  kode indikator global (skema konsep SDG PBB 2020 dan API UNSD terkini), ditambah rencana indikator
  sektoral untuk tujuan 12, 13, 14.
- ``peta_tabel_indikator``: tabel Gold paket v3 ke kode indikator TPB.
- ``dim_satuan``: satuan kanonik beserta pola teks dan penanda penyebut (contoh "per 1.000").
- ``kg/sdg_spine.ttl`` dan ``kg/bentuk.ttl``: tulang punggung SDG KG dan bentuk SHACL-nya.

    python3 -m sdg_gudang.referensi             # bangun ke artefak/referensi
    python3 -m sdg_gudang.referensi --cek       # bangun lalu validasi SHACL dan cetak ringkasan
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

AKAR = Path(__file__).resolve().parents[2]
SNAPSHOT = AKAR / "raw" / "referensi" / "2026-10-20"
KELUAR = AKAR / "artefak" / "referensi"
KATALOG_TPB = AKAR / "config" / "tpb" / "katalog_indikator_tpb.csv"
TABEL_TPB = AKAR / "config" / "tpb" / "tabel_bps_tpb.csv"
GOLD_V3 = AKAR / "artefak" / "v3" / "gold_sdg.sqlite"
GEOJSON = AKAR / "config" / "sdg_game" / "geo" / "provinsi38.geojson"
KONTRAK_V3 = AKAR / "config" / "sdg_game" / "contract_v3.json"
KURASI_TABEL = AKAR / "config" / "referensi" / "peta_tabel_kurasi.csv"
KODE_DI_NAMA = re.compile(r"\((\d{1,2}\.[0-9a-z]{1,2}\.\d{1,2}(?:\*|\.\([a-z]\))?)\)")

NAS = 9999  # wilayah_kode nasional, sama dengan Gold

#: Permen PPN/Kepala Bappenas Nomor 1 Tahun 2024, Pasal 4 ayat (3)-(6).
PILAR = {
    "sosial": ("Pilar Pembangunan Sosial", (1, 2, 3, 4, 5)),
    "ekonomi": ("Pilar Pembangunan Ekonomi", (7, 8, 9, 10, 17)),
    "lingkungan": ("Pilar Pembangunan Lingkungan", (6, 11, 12, 13, 14, 15)),
    "hukum_tata_kelola": ("Pilar Pembangunan Hukum dan Tata Kelola", (16,)),
}
DASAR_PILAR = "Permen PPN/Kepala Bappenas No. 1 Tahun 2024 Pasal 4 ayat (3)-(6)"
PILAR_TUJUAN = {t: p for p, (_, ts) in PILAR.items() for t in ts}


@dataclass(frozen=True)
class Pemekaran:
    kode_bps: str
    induk_bps: str
    berlaku: str  # tanggal mulai berlaku (inklusif), ISO
    dasar: str


#: Perubahan wilayah provinsi yang menyentuh rentang data Gold (1977-2026). Pemekaran sebelum 2012
#: (Banten, Babel, Gorontalo 2000; Maluku Utara 1999; Kep. Riau 2002; Papua Barat 2003; Sulbar 2004)
#: belum dimodelkan; lihat ``CATATAN_CAKUPAN``.
PEMEKARAN = (
    Pemekaran("65", "64", "2012-11-17", "UU 20/2012 tentang Pembentukan Provinsi Kalimantan Utara"),
    Pemekaran("95", "94", "2022-07-25", "UU 14/2022 tentang Pembentukan Provinsi Papua Selatan"),
    Pemekaran("96", "94", "2022-07-25", "UU 15/2022 tentang Pembentukan Provinsi Papua Tengah"),
    Pemekaran("97", "94", "2022-07-25", "UU 16/2022 tentang Pembentukan Provinsi Papua Pegunungan"),
    Pemekaran("92", "91", "2022-12-08", "UU 29/2022 tentang Pembentukan Provinsi Papua Barat Daya"),
)
CATATAN_CAKUPAN = (
    "Pemekaran sebelum 2012 belum dimodelkan; versi pertama setiap provinsi berlaku sejak awal data "
    "tanpa batas bawah. Observasi sebelum tahun pembentukan provinsi diperlakukan sebagai tidak sebanding."
)

#: Periode bridging BPS yang tersimpan, urut waktu. ``default`` adalah periode bawaan laman (34 provinsi).
PERIODE_BRIDGING = ("default", "2023_1.2022", "2024_1.2022", "2025_1.2025", "2025_2.2025")
PERIODE_TERKINI = PERIODE_BRIDGING[-1]

#: Nama ISO (pycountry) yang tidak sama dengan nama BPS setelah normalisasi.
ISO_KE_BPS = {"JAKARTA RAYA": "31", "YOGYAKARTA": "34", "PAPUA PENGUNUNGAN": "97"}


def normal(teks: str) -> str:
    t = re.sub(r"\s+", " ", teks.upper().replace(".", ". ")).strip()
    t = re.sub(r"^PROVINSI ", "", t)
    t = t.replace("KEP. ", "KEPULAUAN ").replace("DAERAH ISTIMEWA ", "DI ").replace("D. I. ", "DI ")
    t = re.sub(r"^DKI ", "", t)
    return re.sub(r"\s+", " ", t).strip()


def _baca_json(p: Path):
    return json.loads(p.read_text("utf-8"))


def _baca_csv(p: Path) -> list[dict]:
    with p.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _kurang_satu_hari(tgl: str) -> str:
    return (dt.date.fromisoformat(tgl) - dt.timedelta(days=1)).isoformat()


# ---------------------------------------------------------------------------------------------------
# Wilayah
# ---------------------------------------------------------------------------------------------------

def bangun_padanan(snapshot: Path = SNAPSHOT) -> list[dict]:
    baris = []
    for periode in PERIODE_BRIDGING:
        data = _baca_json(snapshot / "bps_bridging" / f"provinsi_{periode}.json")
        dipakai = Counter(x["kode_dagri"] for x in data)
        for x in sorted(data, key=lambda x: x["kode_bps"]):
            baris.append({
                "periode": periode,
                "kode_bps": x["kode_bps"],
                "nama_bps": x["nama_bps"],
                "kode_kemendagri": x["kode_dagri"],
                "nama_kemendagri": x["nama_dagri"],
                "wilayah_kode": int(x["kode_bps"]) * 100,
                "ambigu_kemendagri": dipakai[x["kode_dagri"]] > 1,
            })
    return baris


def _peta_iso(snapshot: Path, nama_bps: dict[str, str]) -> dict[str, tuple[str, str]]:
    """kode_bps -> (kode ISO, nama ISO). Gagal keras bila tidak satu-satu."""
    iso = _baca_json(snapshot / "iso3166_2_id_pycountry.json")["subdivisi"]
    prov = [s for s in iso if s["type"] in ("Province", "Capital district", "Special region")]
    per_nama = {normal(n): k for k, n in nama_bps.items()}
    hasil: dict[str, tuple[str, str]] = {}
    for s in prov:
        n = normal(s["name"])
        kode = ISO_KE_BPS.get(n) or per_nama.get(n)
        if kode is None:
            raise ValueError(f"ISO {s['code']} {s['name']!r} tidak terpetakan ke kode BPS")
        if kode in hasil:
            raise ValueError(f"kode BPS {kode} mendapat dua kode ISO: {hasil[kode][0]} dan {s['code']}")
        hasil[kode] = (s["code"], s["name"])
    hilang = set(nama_bps) - set(hasil)
    if hilang:
        raise ValueError(f"provinsi tanpa kode ISO: {sorted(hilang)}")
    return hasil


def bangun_wilayah(snapshot: Path = SNAPSHOT) -> list[dict]:
    terkini = _baca_json(snapshot / "bps_bridging" / f"provinsi_{PERIODE_TERKINI}.json")
    nama_bps = {x["kode_bps"]: x["nama_bps"] for x in terkini}
    dagri = {x["kode_bps"]: x["kode_dagri"] for x in terkini}
    iso = _peta_iso(snapshot, nama_bps)
    anak = {p.kode_bps: p for p in PEMEKARAN}
    induk: dict[str, list[Pemekaran]] = defaultdict(list)
    for p in PEMEKARAN:
        induk[p.induk_bps].append(p)

    rows: list[dict] = []
    for kode in sorted(nama_bps):
        dasar = {"wilayah_kode": int(kode) * 100, "kode_bps": kode, "nama": nama_bps[kode],
                 "kode_kemendagri": dagri[kode], "kode_iso": iso[kode][0], "nama_iso": iso[kode][1],
                 "tingkat": "provinsi"}
        if kode in anak:
            p = anak[kode]
            rows.append(dasar | {"versi": 1, "berlaku_dari": p.berlaku, "berlaku_sebelum": "",
                                 "induk_kode": int(p.induk_bps) * 100, "dasar_perubahan": p.dasar,
                                 "catatan": f"pecahan {nama_bps[p.induk_bps]}"})
        elif kode in induk:
            ps = induk[kode]
            tgl = {p.berlaku for p in ps}
            if len(tgl) != 1:
                raise ValueError(f"induk {kode} dimekarkan pada beberapa tanggal: {sorted(tgl)}")
            t = tgl.pop()
            nama_anak = ", ".join(nama_bps[p.kode_bps] for p in ps)
            dasar_teks = "; ".join(p.dasar for p in ps)
            rows.append(dasar | {"versi": 1, "berlaku_dari": "", "berlaku_sebelum": t, "induk_kode": "",
                                 "dasar_perubahan": "",
                                 "catatan": f"termasuk wilayah {nama_anak} sampai {_kurang_satu_hari(t)}"})
            rows.append(dasar | {"versi": 2, "berlaku_dari": t, "berlaku_sebelum": "", "induk_kode": "",
                                 "dasar_perubahan": dasar_teks, "catatan": f"setelah pemekaran {nama_anak}"})
        else:
            rows.append(dasar | {"versi": 1, "berlaku_dari": "", "berlaku_sebelum": "", "induk_kode": "",
                                 "dasar_perubahan": "", "catatan": ""})
    rows.append({"wilayah_kode": NAS, "kode_bps": "00", "nama": "INDONESIA", "kode_kemendagri": "",
                 "kode_iso": "ID", "nama_iso": "Indonesia", "tingkat": "nasional", "versi": 1,
                 "berlaku_dari": "", "berlaku_sebelum": "", "induk_kode": "", "dasar_perubahan": "",
                 "catatan": ""})
    for i, r in enumerate(rows, start=1):
        r["wilayah_sk"] = i
        r["terkini"] = r["berlaku_sebelum"] == ""
    kolom = ["wilayah_sk", "wilayah_kode", "versi", "kode_bps", "nama", "kode_kemendagri", "kode_iso",
             "nama_iso", "tingkat", "berlaku_dari", "berlaku_sebelum", "terkini", "induk_kode",
             "dasar_perubahan", "catatan"]
    return [{k: r[k] for k in kolom} for r in rows]


def bangun_alias(wilayah: list[dict], padanan: list[dict]) -> list[dict]:
    """Nama dan kode dari sistem lain ke wilayah_kode. Nama yang sama pada dua wilayah adalah galat."""
    alias: dict[tuple[str, str], int] = {}

    def tambah(sistem: str, teks: str, kode: int) -> None:
        kunci = (sistem, teks)
        if kunci in alias and alias[kunci] != kode:
            raise ValueError(f"alias {sistem}:{teks!r} menunjuk dua wilayah: {alias[kunci]} dan {kode}")
        alias[kunci] = kode

    for w in wilayah:
        if not w["terkini"]:
            continue
        tambah("nama", normal(w["nama"]), w["wilayah_kode"])
        tambah("nama", normal(w["nama_iso"]), w["wilayah_kode"])
        tambah("iso3166_2", w["kode_iso"], w["wilayah_kode"])
    for p in padanan:
        # Pada periode 2023_1.2022 dan 2024_1.2022 baris Papua Barat Daya membawa kode dan nama
        # Kemendagri milik Papua Barat; baris ambigu tidak boleh menjadi alias.
        if not p["ambigu_kemendagri"]:
            tambah("nama", normal(p["nama_kemendagri"]), p["wilayah_kode"])
    geo = _baca_json(GEOJSON)
    alias_geo = _baca_json(KONTRAK_V3).get("wilayah_geojson", {})
    per_nama = {normal(w["nama"]): w["wilayah_kode"] for w in wilayah if w["terkini"]}
    for f in geo["features"]:
        n = normal(f["properties"]["PROVINSI"])
        n = normal(alias_geo.get(n, n))
        if n not in per_nama:
            raise ValueError(f"nama GeoJSON {f['properties']['PROVINSI']!r} tidak dikenal")
        tambah("nama", n, per_nama[n])
    return [{"sistem": s, "teks": t, "wilayah_kode": k} for (s, t), k in sorted(alias.items())]


# ---------------------------------------------------------------------------------------------------
# Resolver: dipakai konektor Silver dan uji
# ---------------------------------------------------------------------------------------------------

class KodeAmbigu(ValueError):
    pass


class KodeTidakDikenal(KeyError):
    pass


@dataclass
class Rujukan:
    wilayah: list[dict]
    padanan: list[dict]
    alias: list[dict]
    _alias: dict[tuple[str, str], int] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._alias = {(a["sistem"], a["teks"]): int(a["wilayah_kode"]) for a in self.alias}

    # -- kode dan nama -------------------------------------------------------------------------------
    def dari_bps(self, kode: str) -> int:
        teks = str(kode).strip()
        if not teks.isdigit():
            raise KodeTidakDikenal(f"kode BPS bukan angka: {kode!r}")
        k = int(teks) * 100 if len(teks) <= 2 else int(teks)
        if not any(w["wilayah_kode"] == k for w in self.wilayah):
            raise KodeTidakDikenal(f"kode BPS {kode}")
        return k

    def dari_kemendagri(self, kode: str, periode: str = PERIODE_TERKINI) -> int:
        cocok = [p for p in self.padanan if p["periode"] == periode and p["kode_kemendagri"] == str(kode)]
        if not cocok:
            raise KodeTidakDikenal(f"kode Kemendagri {kode} pada periode {periode}")
        if len(cocok) > 1:
            nama = ", ".join(p["nama_bps"] for p in cocok)
            raise KodeAmbigu(f"kode Kemendagri {kode} pada periode {periode} dipakai {len(cocok)} provinsi: {nama}")
        return int(cocok[0]["wilayah_kode"])

    def dari_iso(self, kode: str) -> int:
        try:
            return self._alias[("iso3166_2", kode)]
        except KeyError:
            raise KodeTidakDikenal(f"kode ISO {kode}") from None

    def dari_nama(self, teks: str) -> int:
        try:
            return self._alias[("nama", normal(teks))]
        except KeyError:
            raise KodeTidakDikenal(f"nama wilayah {teks!r}") from None

    # -- waktu ---------------------------------------------------------------------------------------
    def versi_asof(self, wilayah_kode: int, tanggal: str) -> dict:
        """Versi wilayah yang berlaku pada tanggal (ISO). Galat bila wilayah belum ada."""
        for w in self.wilayah:
            if w["wilayah_kode"] != wilayah_kode:
                continue
            if (not w["berlaku_dari"] or w["berlaku_dari"] <= tanggal) and \
               (not w["berlaku_sebelum"] or tanggal < w["berlaku_sebelum"]):
                return w
        raise KodeTidakDikenal(f"wilayah {wilayah_kode} belum ada pada {tanggal}")

    def sebanding(self, wilayah_kode: int, tanggal_a: str, tanggal_b: str) -> bool:
        """Apakah wilayah yang sama mencakup daerah yang sama pada kedua tanggal."""
        try:
            return self.versi_asof(wilayah_kode, tanggal_a)["wilayah_sk"] == \
                self.versi_asof(wilayah_kode, tanggal_b)["wilayah_sk"]
        except KodeTidakDikenal:
            return False

    # -- mutu batch dari sumber ----------------------------------------------------------------------
    def periksa_batch(self, sistem: str, kode: list[str], periode: str = PERIODE_TERKINI) -> dict:
        """Petakan satu batch kunci wilayah dari sumber. Hasil: ``cocok`` (kunci unik yang terpetakan),
        ``duplikat`` (kunci yang muncul lebih dari sekali, seluruh barisnya dikarantina),
        ``tidak_dikenal``, ``ambigu``, dan ``hilang`` (provinsi terkini yang tidak muncul)."""
        hitung = Counter(kode)
        fungsi = {"bps": self.dari_bps, "iso3166_2": self.dari_iso, "nama": self.dari_nama,
                  "kemendagri": lambda k: self.dari_kemendagri(k, periode)}[sistem]
        cocok, tidak, ambigu = {}, [], []
        for k, n in hitung.items():
            if n > 1:
                continue
            try:
                cocok[k] = fungsi(k)
            except KodeAmbigu:
                ambigu.append(k)
            except KodeTidakDikenal:
                tidak.append(k)
        terkini = {w["wilayah_kode"] for w in self.wilayah if w["terkini"] and w["tingkat"] == "provinsi"}
        return {"cocok": cocok, "duplikat": {k: n for k, n in hitung.items() if n > 1},
                "tidak_dikenal": sorted(tidak), "ambigu": sorted(ambigu),
                "hilang": sorted(terkini - set(cocok.values()))}


# ---------------------------------------------------------------------------------------------------
# Indikator, pilar, satuan
# ---------------------------------------------------------------------------------------------------

#: Legenda klasifikasi kode TPB pada halaman Metadata SDGs Bappenas (sdgs.bappenas.go.id/metadata-sdgs,
#: diperiksa 20 Oktober 2026): "* = Nasional/Global", "() = Proxy", "[] = Pengayaan". Kode tanpa tanda
#: belum dijelaskan legenda itu.
PADANAN_TANDA = {"*": "nasional_global", "()": "proksi", "[]": "pengayaan", "": "tanpa_tanda"}

POLA_KODE = re.compile(r"^(?P<global>\d{1,2}\.[0-9a-z]{1,2}\.\d{1,2})(?P<penanda>\*|\.\([a-z]\))?$")

#: Rencana indikator untuk tujuan tanpa data provinsi di BPS (brief 4 Bagian 2.3).
RENCANA_SEKTORAL = (
    ("12.5.1", 12, "Proksi: persentase sampah terkelola per provinsi", "SIPSN KLH/BPLH"),
    ("13.1.1", 13, "Korban meninggal, hilang, dan terdampak bencana per provinsi", "BNPB"),
    ("13.2.2", 13, "Emisi gas rumah kaca per provinsi per sektor", "SIGN-SMART KLH/BPLH"),
    ("14.5.1", 14, "Luas kawasan konservasi perairan per provinsi", "portal data KKP"),
)


def _indikator_global(snapshot: Path) -> tuple[dict[str, str], set[str]]:
    """(kode -> IRI pada skema konsep 2020, kode yang ada di API UNSD terkini)."""
    import rdflib
    from rdflib.namespace import RDF, SKOS

    g = rdflib.Graph()
    g.parse(snapshot / "un_sdg_kos" / "sdg-kos-goals-targets-indicators.ttl")
    ind = rdflib.URIRef("http://metadata.un.org/sdg/ontology#Indicator")
    kos = {}
    for s in g.subjects(RDF.type, ind):
        for n in g.objects(s, SKOS.notation):
            if re.fullmatch(r"\d{1,2}\.[0-9a-z]{1,2}\.\d{1,2}", str(n)):
                kos[str(n)] = str(s)
    api = {i["code"] for t in _baca_json(snapshot / "unsd_api" / "goal_list_includechildren.json")
           for tg in t["targets"] for i in tg["indicators"]}
    return kos, api


def bangun_indikator(snapshot: Path = SNAPSHOT) -> list[dict]:
    kos, api = _indikator_global(snapshot)
    rows = []
    for r in _baca_csv(KATALOG_TPB):
        if not r["kode"]:
            continue
        m = POLA_KODE.match(r["kode"])
        if not m:
            raise ValueError(f"kode TPB tidak dikenal polanya: {r['kode']!r}")
        g, penanda = m["global"], (m["penanda"] or "").lstrip(".")
        tujuan = int(r["tujuan"])
        rows.append({
            "indikator_id": f"tpb:{r['kode']}", "kode_tpb": r["kode"], "tujuan": tujuan,
            "pilar": PILAR_TUJUAN[tujuan], "nama": r["nama_indikator"], "penanda": penanda,
            "kode_global": g,
            "padanan_global": PADANAN_TANDA["()" if penanda.startswith("(") else penanda],
            "ada_di_kos_2020": g in kos, "ada_di_unsd_terkini": g in api, "iri_global": kos.get(g, ""),
            "status_katalog": r["status"], "sumber_rencana": "BPS",
        })
    for kode, tujuan, nama, sumber in RENCANA_SEKTORAL:
        rows.append({
            "indikator_id": f"global:{kode}", "kode_tpb": "", "tujuan": tujuan, "pilar": PILAR_TUJUAN[tujuan],
            "nama": nama, "penanda": "", "kode_global": kode, "padanan_global": "proksi_sektoral",
            "ada_di_kos_2020": kode in kos, "ada_di_unsd_terkini": kode in api, "iri_global": kos.get(kode, ""),
            "status_katalog": "rencana_sumber_sektoral", "sumber_rencana": sumber,
        })
    ids = Counter(r["indikator_id"] for r in rows)
    ganda = [k for k, n in ids.items() if n > 1]
    if ganda:
        raise ValueError(f"indikator_id ganda: {ganda}")
    return rows


def bangun_pilar() -> list[dict]:
    return [{"pilar": p, "nama": n, "tujuan": ";".join(map(str, ts)), "dasar": DASAR_PILAR}
            for p, (n, ts) in PILAR.items()]


def bangun_peta_tabel(gold: Path = GOLD_V3) -> list[dict]:
    """Tabel Gold paket v3 ke kode TPB lewat var_id BPS di katalog tabel TPB."""
    var_ke_kode: dict[str, set[str]] = defaultdict(set)
    for r in _baca_csv(TABEL_TPB):
        for k in r["kode_indikator"].split(";"):
            if k.strip():
                var_ke_kode[r["var_id"]].add(k.strip())
    kode_sah = {r["kode"] for r in _baca_csv(KATALOG_TPB) if r["kode"]}
    kurasi = {r["tabel"]: r for r in _baca_csv(KURASI_TABEL)}
    con = sqlite3.connect(f"file:{gold}?mode=ro", uri=True)
    rows = []
    for tabel, tujuan, sumber, sumber_id, nama in con.execute(
            "select tabel, tujuan, sumber, sumber_id, nama from tabel_meta order by tabel"):
        # Satu variabel WebAPI dapat dipadankan katalog dengan beberapa kode; kode pada nama tabel Gold
        # (hasil kurasi v3) lebih spesifik dan didahulukan.
        kode_var = sorted(k for k in var_ke_kode.get(str(sumber_id), ()) if k in kode_sah) \
            if sumber.startswith("BPS") else []
        kode_nama = sorted(k for k in KODE_DI_NAMA.findall(nama) if k in kode_sah)
        hubungan, alasan = "kode_sama", ""
        if kode_nama:
            kode, cara = kode_nama, "kode_di_nama_tabel"
        else:
            kode, cara = kode_var, "var_id_katalog_tpb"
        if len(kode) > 1 and tabel not in kurasi:
            raise ValueError(f"tabel Gold {tabel} ambigu {kode}; putuskan di {KURASI_TABEL.name}")
        if tabel in kurasi:  # keputusan steward selalu didahulukan
            k = kurasi[tabel]
            if k["kode_tpb"] and k["kode_tpb"] not in kode_sah:
                raise ValueError(f"kurasi {tabel}: kode TPB {k['kode_tpb']} tidak ada di katalog")
            kode = [k["kode_tpb"]] if k["kode_tpb"] else []
            cara, hubungan, alasan = "kurasi_steward", k["hubungan"], k["alasan"]
            kode_global = k["kode_global"]
        else:
            kode_global = ";".join(sorted({POLA_KODE.match(x)["global"] for x in kode}))
        if not kode and not kode_global and hubungan != "bukan_indikator_tpb":
            raise ValueError(f"tabel Gold {tabel} belum terpetakan; tambahkan ke {KURASI_TABEL.name}")
        rows.append({"tabel": tabel, "tujuan": tujuan, "sumber": sumber, "sumber_id": sumber_id, "nama": nama,
                     "kode_tpb": ";".join(kode), "kode_global": kode_global, "hubungan": hubungan,
                     "cara": cara, "alasan": alasan})
    con.close()
    return rows


@dataclass(frozen=True)
class Satuan:
    satuan_id: str
    label: str
    jenis: str
    penyebut: int | None = None  # untuk rasio "per N": N adalah penyebut, bukan nilai
    pola: str = ""
    catatan: str = ""


SATUAN = (
    Satuan("persen", "persen", "persen", pola=r"^persen$"),
    Satuan("per_1000_kelahiran_hidup", "per 1.000 kelahiran hidup", "rasio_per", 1000,
           r"^per 1\.000 kelahiran hidup$", "angka 1.000 pada teks adalah penyebut"),
    Satuan("per_1000_penduduk", "per 1.000 penduduk", "rasio_per", 1000, r"^per 1\.000 penduduk$",
           "angka 1.000 pada teks adalah penyebut"),
    Satuan("per_1000_perempuan_15_19", "per 1.000 perempuan 15-19 tahun", "rasio_per", 1000,
           r"^per 1\.000 perempuan 15-19 tahun$", "angka 1.000 dan 15-19 pada teks bukan nilai"),
    Satuan("indeks", "indeks", "indeks", pola=r"^indeks$"),
    Satuan("tahun", "tahun", "durasi", pola=r"^tahun$"),
    Satuan("rupiah_per_jam", "rupiah per jam", "mata_uang_per", pola=r"^rupiah per jam$|^rupiah/jam$"),
    Satuan("rupiah_per_tenaga_kerja", "rupiah per tenaga kerja", "mata_uang_per",
           pola=r"^rupiah per tenaga kerja$|^rupiah/tenaga kerja$"),
    Satuan("kilogram", "kilogram", "massa", pola=r"^kilogram$|^kg$"),
    Satuan("hektar", "hektar", "luas", pola=r"^hektar$"),
    Satuan("ribu_hektar", "ribu hektar", "luas", pola=r"^ribu hektar$", catatan="1 ribu hektar = 1.000 hektar"),
    Satuan("desa", "desa", "jumlah", pola=r"^desa$"),
    Satuan("sbm_per_miliar_rupiah", "SBM per miliar rupiah", "intensitas", pola=r"^sbm per miliar rupiah$",
           catatan="setara barel minyak per miliar rupiah PDB"),
    Satuan("campuran_ribu_hektar_persen", "ribu hektar atau persen", "campuran",
           pola=r"^ribu hektar atau persen$", catatan="masalah mutu: satu tabel memakai dua satuan"),
    Satuan("tidak_ada", "tidak ada satuan", "tidak_ada", pola=r"^tidak ada satuan$",
           catatan="masalah mutu: satuan tidak dinyatakan sumber"),
    # rencana sumber sektoral (brief 4 Bagian 2.3)
    Satuan("ton_per_hari", "ton per hari", "laju_massa", pola=r"^ton/hari$|^ton per hari$|^tpd$"),
    Satuan("jiwa", "jiwa", "jumlah", pola=r"^jiwa$|^orang$"),
    Satuan("ton_co2e", "ton CO2e", "massa_setara", pola=r"^ton co2e?$",
           catatan="Gg CO2e = 1.000 ton CO2e; konversi dinyatakan pada aturan Silver per sumber"),
)


#: Satuan sumber internasional dan sektoral yang dipakai pemeta Silver M3 (sebelumnya satuan lokal ``x_``),
#: didaftarkan 20 Oktober 2026 (brief 4 Bagian 12). Tanpa pola teks: pemeta menetapkannya dari kode satuan
#: sumber, bukan dari teks bebas. Jenis menentukan uji validitas (jumlah tidak negatif).
_SATUAN_GLOBAL = (
    ("biner", "biner (0 atau 1)", "biner", None, "1 = ya, 0 = tidak"),
    ("bulan", "bulan", "durasi", None, "contoh cadangan devisa dalam bulan impor"),
    ("item_per_100m2", "item per 100 m2", "kepadatan", None, "sampah laut per 100 m2"),
    ("jumlah", "jumlah (cacah)", "jumlah", None, "cacah tanpa satuan fisik; faktor _M/_TH diterapkan pemeta"),
    ("kejadian", "kejadian", "jumlah", None, "kejadian bencana BNPB"),
    ("kg_per_hektar", "kilogram per hektar", "intensitas", None, "ton per hektar dikonversi faktor 1000"),
    ("kg_per_kapita_per_tahun", "kilogram per kapita per tahun", "intensitas", None, "angka konsumsi ikan KKP"),
    ("kg_per_ppp_konstan", "kg per dolar PPP konstan (tahun dasar tidak dinyatakan)", "intensitas", None,
     "tahun dasar tidak dinyatakan sumber; tidak sebanding dengan tahun dasar lain"),
    ("rumah_tangga", "rumah tangga", "jumlah", None, "rumah tangga perikanan KKP"),
    ("unit", "unit", "jumlah", None, "bangunan, fasilitas, TPA"),
    ("wilayah", "wilayah administratif", "jumlah", None, "cacah kabupaten/kota atau provinsi"),
    ("lcu_berlaku", "mata uang lokal harga berlaku", "mata_uang_berlaku", None, "rupiah harga berlaku"),
    ("rupiah", "rupiah", "mata_uang_berlaku", None, "nilai kerusakan dan kerugian BNPB"),
    ("proporsi", "proporsi (0-1)", "proporsi", None, "bagian dari satu; persen = proporsi x 100"),
    ("lcu_konstan", "mata uang lokal harga konstan", "mata_uang_konstan", None, "tahun dasar menurut seri WDI"),
    ("lcu_per_ppp", "mata uang lokal per dolar internasional", "kurs", None, "faktor konversi PPP"),
    ("lcu_per_usd", "mata uang lokal per dolar AS", "kurs", None, "kurs resmi"),
    ("ppp_berlaku", "dolar internasional harga berlaku", "mata_uang_berlaku", None, ""),
    ("usd_berlaku", "dolar AS harga berlaku", "mata_uang_berlaku", None, ""),
    ("usd_per_kapita", "dolar AS per kapita", "mata_uang_berlaku", None, ""),
    ("usd_per_m3", "dolar AS per meter kubik", "intensitas", None, "produktivitas air"),
    ("liter_alkohol_murni_per_kapita", "liter alkohol murni per kapita", "intensitas", None, "15 tahun ke atas"),
    ("m3_per_detik", "meter kubik per detik", "laju_volume", None, ""),
    ("meter_kubik", "meter kubik", "volume", None, "miliar meter kubik dikonversi faktor 1e9"),
    ("mikrogram_per_m3", "mikrogram per meter kubik", "konsentrasi", None, "PM2,5"),
    ("penumpang_km", "penumpang-kilometer", "jumlah", None, "juta penumpang-km dikonversi faktor 1e6"),
    ("ton_km", "ton-kilometer", "jumlah", None, "juta ton-km dikonversi faktor 1e6"),
    ("teu", "TEU", "jumlah", None, "satuan setara kontainer 20 kaki"),
    ("ton_per_kapita", "ton per kapita", "intensitas", None, "emisi CO2"),
    ("watt_per_kapita", "watt per kapita", "intensitas", None, "kapasitas energi terbarukan"),
    ("rasio", "rasio", "rasio", None, "termasuk indeks paritas"),
    ("skor", "skor", "indeks", None, "skor komposit sumber"),
    ("skala_0_100", "skala 0-100", "indeks", None, ""),
    ("skala_1_100", "skala 1-100", "indeks", None, ""),
    ("skala_1_5", "skala 1-5", "indeks", None, "5 = terbaik"),
    ("per_100_penduduk", "per 100 penduduk", "rasio_per", 100, ""),
    ("per_10000_penduduk", "per 10.000 penduduk", "rasio_per", 10000, ""),
    ("per_100000_penduduk", "per 100.000 penduduk", "rasio_per", 100000, ""),
    ("per_1000000_penduduk", "per 1.000.000 penduduk", "rasio_per", 1000000, ""),
    ("per_100000_dewasa", "per 100.000 penduduk dewasa", "rasio_per", 100000, ""),
    ("per_100000_laki_laki", "per 100.000 penduduk laki-laki", "rasio_per", 100000, ""),
    ("per_100000_perempuan", "per 100.000 penduduk perempuan", "rasio_per", 100000, ""),
    ("per_100000_kelahiran_hidup", "per 100.000 kelahiran hidup", "rasio_per", 100000, "angka kematian ibu"),
    ("per_1000_penduduk_15_64", "per 1.000 penduduk 15-64 tahun", "rasio_per", 1000, ""),
    ("per_1000_penduduk_berisiko", "per 1.000 penduduk berisiko", "rasio_per", 1000, "insiden malaria"),
    ("per_1000_penduduk_tidak_terinfeksi", "per 1.000 penduduk tidak terinfeksi", "rasio_per", 1000, "insiden HIV"),
    ("per_1000_perempuan_10_14", "per 1.000 perempuan 10-14 tahun", "rasio_per", 1000, ""),
    ("kg_per_ppp_konstan_2011", "kg per dolar PPP konstan 2011", "intensitas", None, ""),
    ("mj_per_ppp_konstan_2011", "megajoule per dolar PPP konstan 2011", "intensitas", None, "intensitas energi"),
    ("mj_per_ppp_konstan_2017", "megajoule per dolar PPP konstan 2017", "intensitas", None, "intensitas energi"),
    ("mj_per_ppp_konstan_2021", "megajoule per dolar PPP konstan 2021", "intensitas", None, "intensitas energi"),
    ("ppp_konstan_2011", "dolar internasional konstan 2011", "mata_uang_konstan", None, ""),
    ("ppp_konstan_2017", "dolar internasional konstan 2017", "mata_uang_konstan", None, ""),
    ("ppp_konstan_2021", "dolar internasional konstan 2021", "mata_uang_konstan", None, ""),
    ("usd_konstan_2010_per_m3", "dolar AS konstan 2010 per meter kubik", "intensitas", None, ""),
    ("usd_konstan_2015_per_m3", "dolar AS konstan 2015 per meter kubik", "intensitas", None, ""),
)
SATUAN_GLOBAL = (tuple(Satuan(i, label, j, n, "", c) for i, label, j, n, c in _SATUAN_GLOBAL)
                 + tuple(Satuan(f"kg_per_usd_konstan_{t}", f"kg per dolar AS konstan {t}", "intensitas", None, "", "")
                         for t in (2010, 2015, 2017, 2020, 2021))
                 + tuple(Satuan(f"usd_konstan_{t}", f"dolar AS konstan {t}", "mata_uang_konstan", None, "", "")
                         for t in range(2010, 2025) if t not in (2011, 2012, 2013)))

#: Satuan lokal ``x_`` pemeta Silver ke satuan terdaftar; BNPB ``x_per_100rb_penduduk`` = per 100.000 penduduk.
ALIAS_SATUAN_LOKAL = {f"x_{s.satuan_id}": s.satuan_id for s in SATUAN_GLOBAL} | {
    "x_per_100rb_penduduk": "per_100000_penduduk"}
SATUAN = SATUAN + SATUAN_GLOBAL


def bangun_alias_satuan() -> list[dict]:
    return [{"satuan_lokal": k, "satuan_id": v} for k, v in sorted(ALIAS_SATUAN_LOKAL.items())]


def satuan_dari_teks(teks: str) -> Satuan:
    t = re.sub(r"\s+", " ", teks.strip().lower())
    cocok = [s for s in SATUAN if s.pola and re.search(s.pola, t)]
    if len(cocok) != 1:
        raise KodeTidakDikenal(f"satuan {teks!r}: {len(cocok)} kecocokan")
    return cocok[0]


def bangun_satuan(gold: Path = GOLD_V3) -> tuple[list[dict], list[dict]]:
    """(dim_satuan, pemakaian satuan pada Gold v3 dan katalog BPS)."""
    dim = [{"satuan_id": s.satuan_id, "label": s.label, "jenis": s.jenis,
            "penyebut": s.penyebut if s.penyebut is not None else "", "pola": s.pola, "catatan": s.catatan}
           for s in SATUAN]
    con = sqlite3.connect(f"file:{gold}?mode=ro", uri=True)
    pakai = Counter(("gold_v3.satuan_tampil", r[0]) for r in con.execute("select satuan_tampil from tabel_meta"))
    con.close()
    for r in _baca_csv(TABEL_TPB):
        if r["unduh"] == "ya":
            pakai[("katalog_bps.satuan", r["satuan"])] += 1
    rows = [{"asal": a, "teks": t, "jumlah_tabel": n, "satuan_id": satuan_dari_teks(t).satuan_id}
            for (a, t), n in sorted(pakai.items())]
    return dim, rows


# ---------------------------------------------------------------------------------------------------
# SDG KG: tulang punggung
# ---------------------------------------------------------------------------------------------------

#: Ruang nama sementara; keputusan pemilik di brief 4 (stabilitas IRI). Jangan dipakai di luar repositori
#: sebelum diputuskan.
NS_KG = "https://sd.itera.ac.id/kg/"


def bangun_kg(wilayah: list[dict], indikator: list[dict], snapshot: Path = SNAPSHOT):
    import rdflib
    from rdflib.namespace import DCTERMS, RDF, RDFS, SKOS, XSD

    LK = rdflib.Namespace(NS_KG + "ontologi#")
    TPB = rdflib.Namespace(NS_KG + "tpb/")
    WIL = rdflib.Namespace(NS_KG + "wilayah/")
    PIL = rdflib.Namespace(NS_KG + "pilar/")
    SDG = rdflib.Namespace("http://metadata.un.org/sdg/")
    SDGO = rdflib.Namespace("http://metadata.un.org/sdg/ontology#")

    kos = rdflib.Graph()
    kos.parse(snapshot / "un_sdg_kos" / "sdg-kos-goals-targets-indicators.ttl")
    g = rdflib.Graph()
    for p, ns in (("lk", LK), ("tpb", TPB), ("wil", WIL), ("pilar", PIL), ("sdg", SDG), ("sdgo", SDGO),
                  ("skos", SKOS), ("dct", DCTERMS)):
        g.bind(p, ns)

    # Tujuan, target, indikator global: salin tipe, notasi bertitik, label Inggris, broader.
    for kelas in (SDGO.Goal, SDGO.Target, SDGO.Indicator):
        for s in kos.subjects(RDF.type, kelas):
            g.add((s, RDF.type, kelas))
            for n in kos.objects(s, SKOS.notation):
                if re.fullmatch(r"\d{1,2}(\.[0-9a-z]{1,2}){0,2}", str(n)):
                    g.add((s, SKOS.notation, rdflib.Literal(str(n))))
            for lab in kos.objects(s, SKOS.prefLabel):
                if getattr(lab, "language", None) == "en":
                    g.add((s, SKOS.prefLabel, lab))
            for b in kos.objects(s, SKOS.broader):
                g.add((s, SKOS.broader, b))

    for p, (nama, ts) in PILAR.items():
        g.add((PIL[p], RDF.type, LK.Pilar))
        g.add((PIL[p], SKOS.prefLabel, rdflib.Literal(nama, lang="id")))
        g.add((PIL[p], DCTERMS.source, rdflib.Literal(DASAR_PILAR)))
        for t in ts:
            g.add((SDG[str(t)], LK.pilar, PIL[p]))

    for r in indikator:
        node = TPB[r["kode_tpb"]] if r["kode_tpb"] else TPB["rencana/" + r["kode_global"]]
        g.add((node, RDF.type, LK.IndikatorTPB if r["kode_tpb"] else LK.RencanaIndikator))
        if r["kode_tpb"]:
            g.add((node, SKOS.notation, rdflib.Literal(r["kode_tpb"])))
        g.add((node, SKOS.prefLabel, rdflib.Literal(r["nama"], lang="id")))
        g.add((node, LK.tujuan, SDG[str(r["tujuan"])]))
        g.add((node, LK.pilar, PIL[r["pilar"]]))
        g.add((node, LK.kodeGlobal, rdflib.Literal(r["kode_global"])))
        if r["iri_global"]:
            # "*" (Nasional/Global) menurut legenda Bappenas berarti indikator nasional sama dengan global.
            prop = {"nasional_global": SKOS.exactMatch, "proksi": LK.proksiUntuk, "pengayaan": LK.pengayaanUntuk,
                    "tanpa_tanda": LK.kodeSamaDengan, "proksi_sektoral": LK.proksiUntuk}[r["padanan_global"]]
            g.add((node, prop, rdflib.URIRef(r["iri_global"])))
        g.add((node, LK.statusKatalog, rdflib.Literal(r["status_katalog"])))

    sk_ke_node = {}
    for w in wilayah:
        node = WIL[f"{w['wilayah_kode']}/v{w['versi']}"]
        sk_ke_node[w["wilayah_sk"]] = node
        g.add((node, RDF.type, LK.VersiWilayah))
        g.add((node, SKOS.prefLabel, rdflib.Literal(w["nama"], lang="id")))
        g.add((node, LK.wilayahKode, rdflib.Literal(w["wilayah_kode"], datatype=XSD.integer)))
        g.add((node, LK.kodeBPS, rdflib.Literal(w["kode_bps"])))
        g.add((node, LK.kodeISO, rdflib.Literal(w["kode_iso"])))
        if w["kode_kemendagri"]:
            g.add((node, LK.kodeKemendagri, rdflib.Literal(w["kode_kemendagri"])))
        if w["berlaku_dari"]:
            g.add((node, LK.berlakuDari, rdflib.Literal(w["berlaku_dari"], datatype=XSD.date)))
        if w["berlaku_sebelum"]:
            g.add((node, LK.berlakuSebelum, rdflib.Literal(w["berlaku_sebelum"], datatype=XSD.date)))
        if w["dasar_perubahan"]:
            g.add((node, DCTERMS.source, rdflib.Literal(w["dasar_perubahan"])))
    per_kode = defaultdict(list)
    for w in wilayah:
        per_kode[w["wilayah_kode"]].append(w)
    for vs in per_kode.values():
        vs.sort(key=lambda w: w["versi"])
        for a, b in zip(vs, vs[1:]):
            g.add((sk_ke_node[b["wilayah_sk"]], LK.menggantikan, sk_ke_node[a["wilayah_sk"]]))
        for w in vs:
            if w["induk_kode"]:
                induk_lama = [x for x in per_kode[w["induk_kode"]] if x["berlaku_sebelum"] == w["berlaku_dari"]]
                for x in induk_lama:
                    g.add((sk_ke_node[w["wilayah_sk"]], LK.pecahanDari, sk_ke_node[x["wilayah_sk"]]))
            if w["tingkat"] == "provinsi":
                g.add((sk_ke_node[w["wilayah_sk"]], LK.bagianDari, WIL[f"{NAS}/v1"]))
    g.add((LK.pecahanDari, RDFS.comment, rdflib.Literal(
        "versi wilayah baru yang dibentuk dari versi induk sebelum pemekaran", lang="id")))
    return g


BENTUK_TTL = """@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix lk: <https://sd.itera.ac.id/kg/ontologi#> .
@prefix sdgo: <http://metadata.un.org/sdg/ontology#> .

lk:BentukIndikatorTPB a sh:NodeShape ;
  sh:targetClass lk:IndikatorTPB ;
  sh:property [ sh:path lk:tujuan ; sh:minCount 1 ; sh:maxCount 1 ; sh:class sdgo:Goal ] ;
  sh:property [ sh:path lk:pilar ; sh:minCount 1 ; sh:maxCount 1 ; sh:class lk:Pilar ] ;
  sh:property [ sh:path skos:notation ; sh:minCount 1 ; sh:maxCount 1 ] ;
  sh:property [ sh:path lk:kodeGlobal ; sh:minCount 1 ; sh:maxCount 1 ; sh:pattern "^[0-9]{1,2}\\\\.[0-9a-z]{1,2}\\\\.[0-9]{1,2}$" ] ;
  sh:property [ sh:path skos:prefLabel ; sh:minCount 1 ] .

lk:BentukRencanaIndikator a sh:NodeShape ;
  sh:targetClass lk:RencanaIndikator ;
  sh:property [ sh:path lk:tujuan ; sh:minCount 1 ; sh:maxCount 1 ; sh:class sdgo:Goal ] ;
  sh:property [ sh:path lk:pilar ; sh:minCount 1 ; sh:maxCount 1 ; sh:class lk:Pilar ] .

lk:BentukVersiWilayah a sh:NodeShape ;
  sh:targetClass lk:VersiWilayah ;
  sh:property [ sh:path lk:wilayahKode ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:integer ] ;
  sh:property [ sh:path lk:kodeBPS ; sh:minCount 1 ; sh:maxCount 1 ] ;
  sh:property [ sh:path lk:kodeISO ; sh:minCount 1 ; sh:maxCount 1 ] ;
  sh:property [ sh:path lk:kodeKemendagri ; sh:maxCount 1 ] ;
  sh:property [ sh:path lk:berlakuDari ; sh:maxCount 1 ; sh:datatype xsd:date ] ;
  sh:property [ sh:path lk:berlakuSebelum ; sh:maxCount 1 ; sh:datatype xsd:date ] ;
  sh:property [ sh:path lk:pecahanDari ; sh:class lk:VersiWilayah ] ;
  sh:property [ sh:path lk:menggantikan ; sh:maxCount 1 ; sh:class lk:VersiWilayah ] .

lk:BentukPilar a sh:NodeShape ;
  sh:targetClass lk:Pilar ;
  sh:property [ sh:path skos:prefLabel ; sh:minCount 1 ] .
"""


def validasi_kg(g) -> tuple[bool, str]:
    import rdflib
    from pyshacl import validate

    bentuk = rdflib.Graph().parse(data=BENTUK_TTL, format="turtle")
    ok, _, teks = validate(g, shacl_graph=bentuk, inference="none", advanced=False)
    return bool(ok), teks


# ---------------------------------------------------------------------------------------------------
# Tulis
# ---------------------------------------------------------------------------------------------------

def _tulis_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("true" if v is True else "false" if v is False else v) for k, v in r.items()})


#: Metadata per tabel (standar metadata brief 4 unit 009): judul, deskripsi, kunci, dan arti kolom kunci.
METADATA_TABEL = {
    "dim_wilayah": ("Dimensi wilayah tipe 2",
                    "Satu baris per versi wilayah; provinsi induk pemekaran mempunyai versi sebelum dan sesudah.",
                    ["wilayah_sk"], {"wilayah_kode": "kode BPS dua digit x 100, sama dengan Gold; 9999 nasional",
                                     "berlaku_dari": "tanggal mulai berlaku (inklusif); kosong = sejak awal data",
                                     "berlaku_sebelum": "tanggal akhir (eksklusif); kosong = masih berlaku"}),
    "padanan_kode_wilayah": ("Padanan kode BPS dan Kemendagri per periode bridging",
                             "Salinan ternormalisasi bridging BPS; ambigu_kemendagri = satu kode Kemendagri dipakai >1 provinsi.",
                             ["periode", "kode_bps"], {"periode": "periode_merge bridging BPS; default = 34 provinsi"}),
    "alias_wilayah": ("Alias wilayah", "Nama ternormalisasi dan kode ISO 3166-2 ke wilayah_kode.",
                      ["sistem", "teks"], {}),
    "dim_pilar": ("Pilar TPB", DASAR_PILAR, ["pilar"], {}),
    "dim_indikator": ("Dimensi indikator TPB",
                      "Indikator TPB nasional dari katalog dan rencana indikator sektoral, dipadankan dengan kode global.",
                      ["indikator_id"], {"padanan_global": "nasional_global (tanda *) | proksi (tanda ()) | "
                                                           "tanpa_tanda | proksi_sektoral; legenda Bappenas /metadata-sdgs",
                                         "iri_global": "IRI skema konsep SDG PBB 2020; kosong bila indikator ditambahkan setelah 2020"}),
    "peta_tabel_indikator": ("Peta tabel Gold v3 ke indikator",
                             "Setiap tabel Gold paket v3 dengan kode TPB atau kode global dan cara pemetaannya.",
                             ["tabel"], {"hubungan": "kode_sama | sebagian | proksi | berkaitan | bukan_indikator_tpb"}),
    "dim_satuan": ("Dimensi satuan", "Satuan kanonik, jenis, penyebut rasio, dan pola teks pengenal.",
                   ["satuan_id"], {"penyebut": "N pada rasio per N; angka N pada teks bukan nilai indikator"}),
    "pemakaian_satuan": ("Pemakaian satuan", "Teks satuan pada Gold v3 dan katalog BPS beserta satuan kanoniknya.",
                         ["asal", "teks"], {}),
    "alias_satuan": ("Alias satuan lokal", "Satuan lokal x_ pemeta Silver M3 ke satuan terdaftar dim_satuan.",
                     ["satuan_lokal"], {}),
}

#: Padanan kolom dp_referensi dengan konsep lintas sektor SDMX (dipakai basis data SDG global).
KONSEP_SDMX = {"wilayah_kode": "REF_AREA", "kode_global": "SERIES/INDICATOR (SDG)", "satuan_id": "UNIT_MEASURE",
               "tujuan": "GOAL (SDG DSD)", "berlaku_dari": "VALID_FROM", "berlaku_sebelum": "VALID_TO"}


def tulis_metadata(keluar: Path, tabel: dict[str, list[dict]], ringkas: dict) -> dict:
    """Rekaman metadata JSON-LD berkosakata DCAT dan PROV untuk dp_referensi."""
    sumber = [{"@id": f"raw/referensi/2026-10-20/{k}", "sha256": v["sha256"]}
              for k, v in _baca_json(SNAPSHOT / "manifest.json")["berkas"].items()]
    sumber += [{"@id": str(p.relative_to(AKAR)), "sha256": _sha256(p)} for p in (KATALOG_TPB, TABEL_TPB, KURASI_TABEL, GOLD_V3)]
    md = {
        "@context": {"dcat": "http://www.w3.org/ns/dcat#", "dct": "http://purl.org/dc/terms/",
                     "prov": "http://www.w3.org/ns/prov#"},
        "@id": "dp_referensi", "@type": "dcat:Dataset",
        "dct:title": "dp_referensi: data rujukan dan induk Gudang SDG",
        "dct:description": "Wilayah tipe 2, padanan kode, indikator, pilar, satuan, dan tulang punggung SDG KG.",
        "dct:publisher": "Kelompok Keahlian Program Studi Sains Data, Institut Teknologi Sumatera",
        "dcat:contactPoint": "tim platform (brief 4 unit 002)",
        "dct:license": "kelas A untuk turunan BPS dan aturan internal; berkas UNSD dipakai internal (kelas B)",
        "dct:issued": "2026-10-20", "dct:conformsTo": "brief 4 Bagian 3.3 dan docs/serkom/J.62DMS00.009.1",
        "prov:wasDerivedFrom": sumber,
        "catatan_cakupan": CATATAN_CAKUPAN,
        "padanan_konsep_sdmx": KONSEP_SDMX,
        "dcat:distribution": [],
    }
    for nama, rows in tabel.items():
        judul, desk, kunci, arti = METADATA_TABEL[nama]
        md["dcat:distribution"].append({
            "@id": f"{nama}.csv", "@type": "dcat:Distribution", "dct:title": judul, "dct:description": desk,
            "dcat:mediaType": "text/csv", "kunci": kunci, "jumlah_baris": len(rows),
            "kolom": [{"nama": k, "arti": arti.get(k, "")} for k in rows[0]],
            "sha256": ringkas["berkas"][f"{nama}.csv"],
        })
    md["dcat:distribution"].append({"@id": "kg/sdg_spine.nt", "@type": "dcat:Distribution",
                                    "dct:title": "Tulang punggung SDG KG (N-Triples terurut)",
                                    "dcat:mediaType": "application/n-triples",
                                    "dct:conformsTo": "kg/bentuk.ttl (SHACL)",
                                    "sha256": ringkas["berkas"]["kg/sdg_spine.nt"]})
    (keluar / "metadata.jsonld").write_text(json.dumps(md, indent=1, ensure_ascii=False) + "\n", "utf-8")
    return md


def bangun(keluar: Path = KELUAR, snapshot: Path = SNAPSHOT) -> dict:
    wilayah = bangun_wilayah(snapshot)
    padanan = bangun_padanan(snapshot)
    alias = bangun_alias(wilayah, padanan)
    indikator = bangun_indikator(snapshot)
    pilar = bangun_pilar()
    peta = bangun_peta_tabel()
    satuan, pakai_satuan = bangun_satuan()
    tabel = {"dim_wilayah": wilayah, "padanan_kode_wilayah": padanan, "alias_wilayah": alias,
             "dim_pilar": pilar, "dim_indikator": indikator, "peta_tabel_indikator": peta,
             "dim_satuan": satuan, "pemakaian_satuan": pakai_satuan, "alias_satuan": bangun_alias_satuan()}
    for nama, rows in tabel.items():
        _tulis_csv(keluar / f"{nama}.csv", rows)

    g = bangun_kg(wilayah, indikator, snapshot)
    ok, laporan = validasi_kg(g)
    (keluar / "kg").mkdir(parents=True, exist_ok=True)
    nt = sorted(set(g.serialize(format="nt").splitlines()) - {""})
    (keluar / "kg" / "sdg_spine.nt").write_text("\n".join(nt) + "\n", "utf-8")
    g.serialize(keluar / "kg" / "sdg_spine.ttl", format="turtle")
    (keluar / "kg" / "bentuk.ttl").write_text(BENTUK_TTL, "utf-8")
    if not ok:
        (keluar / "kg" / "laporan_shacl.txt").write_text(laporan, "utf-8")
        raise ValueError("SHACL gagal; lihat kg/laporan_shacl.txt")

    berkas = sorted(p for p in keluar.rglob("*") if p.is_file() and p.suffix in (".csv", ".nt"))
    ringkas = {
        "dibangun_dari": {"snapshot": str(snapshot.relative_to(AKAR)),
                          "manifest_sha256": _sha256(snapshot / "manifest.json"),
                          "katalog_tpb_sha256": _sha256(KATALOG_TPB), "tabel_tpb_sha256": _sha256(TABEL_TPB),
                          "gold_v3_sha256": _sha256(GOLD_V3)},
        "berkas": {str(p.relative_to(keluar)): _sha256(p) for p in berkas},
        "jumlah": {k: len(v) for k, v in tabel.items()} | {"kg_tripel": len(nt)},
        "shacl_lulus": ok,
        "catatan_cakupan": CATATAN_CAKUPAN,
    }
    (keluar / "manifest.json").write_text(json.dumps(ringkas, indent=1, ensure_ascii=False) + "\n", "utf-8")
    tulis_metadata(keluar, tabel, ringkas)
    return ringkas


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--keluar", type=Path, default=KELUAR)
    ap.add_argument("--cek", action="store_true", help="cetak ringkasan cakupan")
    a = ap.parse_args(argv)
    r = bangun(a.keluar)
    print(json.dumps(r["jumlah"], ensure_ascii=False))
    if a.cek:
        ind = _baca_csv(a.keluar / "dim_indikator.csv")
        peta = _baca_csv(a.keluar / "peta_tabel_indikator.csv")
        print("indikator per pilar:", dict(Counter(x["pilar"] for x in ind)))
        print("padanan global:", dict(Counter(x["padanan_global"] for x in ind)))
        print("kode global tidak ada di KOS 2020:", sorted({x["kode_global"] for x in ind if x["ada_di_kos_2020"] == "false"}))
        print("kode global tidak ada di UNSD terkini:", sorted({x["kode_global"] for x in ind if x["ada_di_unsd_terkini"] == "false"}))
        print("tabel Gold v3 terpetakan ke kode TPB:", sum(1 for x in peta if x["kode_tpb"]), "dari", len(peta))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
