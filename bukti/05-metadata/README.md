# 05. Metadata

**Unit:** J.62DMS00.009.1 Mengelola Metadata

**Pertanyaan yang dijawab:** Bagaimana orang lain tahu isi, asal, dan pemilik setiap data?

**Yang saya kerjakan:** Saya menetapkan kebutuhan metadata dari tiga kelompok konsumen yang pertanyaannya berbeda (pemain dan Bravais, pemilik domain, tim platform), lalu menyusun standar wajib per data product dengan kosakata DCAT dan PROV serta padanan konsep SDMX. Metadata tidak ditulis tangan: rekaman DCAT, manifest sha256, kontrak dbt, dan lineage dibangkitkan dari konfigurasi data product pada setiap jalan job, dan uji gagal bila berkas yang di-commit tertinggal dari konfigurasinya. Repositorinya saya putuskan versi ringan (DCAT, katalog Iceberg REST, dokumentasi dbt, lineage JSON) karena OpenMetadata tidak muat di simpul 16 GB, dan metadata provenans itu terbukti berguna: dengan alat ber-provenans, 86,2 % jawaban Bravais terikat ke angka gudang, tanpa alat 0,0 %.

| Elemen | Yang saya kerjakan | Bukti | Jenis | Status |
| --- | --- | --- | --- | --- |
| 1. Mendefinisikan kebutuhan metadata | memetakan tiga konsumen ke jenis metadata bisnis, tata kelola, dan teknis; merancang arsitektur empat lapis; menetapkan standar wajib per data product, distribusi, dan observasi | tabel pada Elemen 1 | T | lengkap |
| 2. Membangun metadata | membangkitkan `metadata.jsonld` dan manifest dari pembangun `dp_referensi`; 9 rekaman DCAT per data product; kontrak dbt dari YAML; lineage 166 simpul dan 320 sisi; TPB-KG 85.734 tripel sebagai metadata semantik | `data/gudang/m4_lineage.json`, `data/gudang/m5_kg_ringkasan.json`, `data/produk/uji-graf.json`; `artefak/mesh/*.jsonld` di repositori penelitian Ardika | TL, L | lengkap, repositori versi ringan atas keputusan sendiri |
| 3. Menggunakan metadata | mendistribusikan metadata di tempat yang sama dengan data (tabel `dp_referensi_*`, `dp_rilis`, kolom provenans per baris); analisis cakupan indikator dari metadata saja; tiga mekanisme pemeliharaan; provenans sebagai alat Bravais | `data/produk/uji-keterikatan.json`; `sdg_gudang.gudang.kontrak` dan uji `test_gudang_kontrak` di repositori penelitian Ardika | TL, L | lengkap |

Jenis bukti: **L** langsung (artefak yang berjalan), **TL** tidak langsung (hasil terukur, laporan), **T** tambahan (dokumen tata kelola, surat).

## Kedudukan langkah ini

Metadata dikerjakan dua kali. Pada fase M1 (20 Oktober 2026) kebutuhan dan standarnya ditetapkan dan diterapkan pada `dp_referensi`. Pada fase M4 (21 Oktober) repositori, distribusi, dan pemeliharaannya dibangun bersama gudang, dan pada Tahap II (21–23 Oktober) metadata provenans diuji sebagai alat pemandu AI. Batasan variabel unit ini membolehkan repositori metadata di alat lain, dan pilihan itulah yang dipakai.

## Elemen 1. Kebutuhan metadata

**KUK 1.1 Kebutuhan.** Tiga kelompok konsumen mengajukan pertanyaan yang berbeda kepada metadata, dan tiap pertanyaan menentukan jenis metadata yang harus ada.

| Konsumen | Pertanyaan yang harus terjawab | Jenis metadata |
| --- | --- | --- |
| Pemain dan Bravais | angka ini dari sumber mana, rilis mana, berlaku sejak kapan, dalam satuan apa | bisnis: sumber, rilis, satuan, definisi |
| Pemilik domain dan steward | siapa pemilik produk, apa kontraknya, apakah lulus uji, dari mana asalnya | tata kelola: pemilik, kontrak, kualitas, lineage |
| Tim platform dan peneliti | apakah keluaran dapat dibangun ulang dan berasal dari masukan yang mana | teknis: sha256, jumlah baris, skema, versi pembangun |

**KUK 1.2 Arsitektur.** Prinsipnya satu: metadata dihasilkan oleh pembangun data product, bukan ditulis tangan, supaya tidak pernah tertinggal dari datanya. Empat lapisnya sebagai berikut.

| Lapis | Tempat | Isi |
| --- | --- | --- |
| Metadata di samping data | `manifest.json`, `metadata.jsonld` di folder setiap data product | sha256, jumlah baris, kolom dan artinya, sumber turunan |
| Katalog dan lineage | repositori versi ringan (lihat KUK 2.3) | rekaman DCAT per data product, katalog Iceberg REST, lineage dari dbt dan Dagster |
| Kontrak | `config/mesh/<produk>.yaml` dan `config/sdg_game/contract*.json` | skema, toleransi, SLA, kelas lisensi |
| Semantik | SDG KG (`artefak/referensi/kg/`, lalu TPB-KG penuh) | arti indikator, pilar, wilayah, dan hubungan antarkonsep |

**KUK 1.3 Standar metadata.** Setiap data product wajib mempunyai rekaman berikut. Kosakatanya DCAT dan PROV; konsep dimensinya dipadankan dengan konsep lintas sektor SDMX yang dipakai basis data SDG global, supaya metadata ini dapat dibaca oleh orang yang terbiasa dengan statistik resmi.

| Tingkat | Bidang | Wajib | Kosakata |
| --- | --- | --- | --- |
| Data product | judul, deskripsi, penerbit, kontak (steward) | ya | `dct:title`, `dct:description`, `dct:publisher`, `dcat:contactPoint` |
| | lisensi dan kelas tayang (A, A-SA, B, C) | ya | `dct:license` |
| | tanggal terbit, standar yang diikuti | ya | `dct:issued`, `dct:conformsTo` |
| | sumber turunan dengan sha256 | ya | `prov:wasDerivedFrom` |
| | catatan cakupan dan batas | ya bila ada | bidang lokal `catatan_cakupan` |
| | padanan konsep SDMX | ya | bidang lokal `padanan_konsep_sdmx` (REF_AREA, UNIT_MEASURE, SERIES, VALID_FROM, VALID_TO) |
| Distribusi (tabel atau berkas) | judul, deskripsi, jenis media, kunci, jumlah baris, sha256 | ya | `dcat:Distribution`, `dcat:mediaType` |
| | daftar kolom dengan arti kolom kunci | ya | bidang lokal `kolom` |
| | standar validasi (contoh SHACL) | ya untuk graf | `dct:conformsTo` |
| Observasi (gudang) | sumber, rilis, jenis bukti tanggal, waktu rilis, waktu catat | ya | kolom `fakta_observasi` (langkah 09) |

Definisi indikator mengikuti Metadata Indikator TPB Bappenas (KEP.87/M.PPN/HK/10/2024), yang bukunya diunduh tangan karena unduhan otomatis ditolak (langkah 04).

## Elemen 2. Membangun metadata

**KUK 2.1 Standar diterapkan.** `artefak/referensi/metadata.jsonld` dihasilkan setiap kali `make m1-referensi` dijalankan. Isinya satu `dcat:Dataset` untuk `dp_referensi`, sembilan `dcat:Distribution` (delapan tabel CSV dan satu graf N-Triples), dan 16 rujukan `prov:wasDerivedFrom` dengan sha256: 12 berkas snapshot, katalog TPB, katalog tabel TPB, kurasi steward, dan Gold v3. Pada M4, pola yang sama diterapkan ke sembilan data product sebagai `artefak/mesh/*.jsonld`.

**KUK 2.2 Integrasi.** `manifest.json`, `metadata.jsonld`, dan bentuk SHACL `kg/bentuk.ttl` dihasilkan oleh satu fungsi pembangun yang sama, sehingga sha256 di metadata selalu cocok dengan berkas yang ditulis. Uji `test_bangun_deterministik` memastikan pembangunan ulang memberi sha256 yang sama. Pada gudang, kontrak dbt dan rekaman DCAT dibangkitkan dari YAML data product yang sama oleh `sdg_gudang.gudang.kontrak`, sehingga tiga artefak itu tidak dapat saling bertentangan.

**KUK 2.3 Repositori.** Rencana semula adalah OpenMetadata memanen rekaman DCAT dan lineage dari orkestrator pada M4. Spesifikasi produksinya memerlukan sekitar 40 GiB RAM dan tidak muat bersama Trino pada simpul 16 GB (perbandingan biaya di langkah 06). Atas keputusan saya pada 20 Oktober 2026, repositorinya versi ringan dengan empat lapis.

| Lapis | Isi | Berkas atau layanan |
| --- | --- | --- |
| Katalog dataset | satu rekaman DCAT 3 per data product: judul, deskripsi, kontak steward, lisensi, periodisitas (SLA), distribusi tabel Iceberg, anotasi kualitas | `artefak/mesh/*.jsonld` (9 berkas) |
| Katalog teknis | skema, snapshot, dan riwayat setiap tabel | katalog Iceberg REST (`iceberg.system` dan metadata tabel) |
| Kontrak dan uji | nama dan tipe kolom yang ditegakkan, uji aturan global, SLA | `dbt/gudang_sdg/models/dp/*.yml` |
| Lineage | 166 simpul, 320 sisi dari manifest raw sampai data product; 12 data product semuanya berjalur ke raw | `data/gudang/m4_lineage.json`, graf aset Dagster |

Lapis semantik dilengkapi TPB-KG: 85.734 tripel yang dibangun dari Gold, lulus SHACL tanpa pelanggaran, dan memadankan 103 dari 105 indikator TPB ke kode global (`data/gudang/m5_kg_ringkasan.json`). Uji graf pada Tahap II membangunnya ulang dari Gold dan memperoleh sha256 yang identik dengan graf M5 (`data/produk/uji-graf.json`).

## Elemen 3. Menggunakan metadata

**KUK 3.1 Distribusi.** Konsumen membaca metadata di tempat yang sama dengan datanya, bukan di sistem terpisah: tabel `dp.dp_referensi_*` (wilayah, indikator, satuan, konsep) dan `dp.dp_rilis` di Trino; rekaman DCAT di repositori git; dan kolom `alasan_pilihan`, `rilis_id`, serta `berlaku_sejak` pada setiap baris data product. Pada paket level v4, provenans ikut sampai ke setiap level, dan pada Bravais menjadi isi jawaban alat.

**KUK 3.2 Pemakaian untuk kueri, laporan, dan analisis.** Dua contoh, satu dari M1 dan satu dari Tahap II.

Contoh pertama menjawab pertanyaan "berapa indikator TPB per pilar yang sudah mempunyai tabel di Gold v3?" hanya dari metadata, yaitu `dim_indikator` dan `peta_tabel_indikator`, tanpa membaca nilai data.

| Pilar | Indikator katalog | Mempunyai tabel Gold v3 | Persen |
| --- | ---: | ---: | ---: |
| Sosial | 53 | 23 | 43,4 |
| Ekonomi | 30 | 15 | 50,0 |
| Lingkungan | 10 | 7 | 70,0 |
| Hukum dan Tata Kelola | 12 | 6 | 50,0 |
| **Jumlah** | **105** | **51** | **48,6** |

Hasil ini menjadi masukan prioritas akuisisi M2: pilar Sosial mempunyai celah terbesar dalam jumlah, dan pilar Lingkungan baru mempunyai 10 indikator katalog karena tujuan 12, 13, dan 14 belum ada di BPS tingkat provinsi.

Contoh kedua menguji apakah metadata provenans benar-benar mengubah perilaku pemandu AI. Pada uji keterikatan (`data/produk/uji-keterikatan.json`, penilai v2), 600 pertanyaan dijawab Bravais tanpa alat (kondisi B) dan 595 dengan alat ber-provenans (kondisi T).

| Kondisi | n | Terikat ke angka gudang | Menolak menjawab |
| --- | ---: | ---: | ---: |
| Tanpa alat (B) | 600 | 0 (0,0 %) | 597 |
| Alat ber-provenans (T) | 595 | 513 (86,2 %) | 28 |

Selisih proporsi terikat 0,862 dengan selang kepercayaan 0,831–0,888. Tanpa alat, guardrail membuat Bravais menolak hampir semua pertanyaan angka, yang memang dikehendaki; dengan alat, jawabannya terikat ke rilis dan sumber tertentu karena metadata itu ikut dibawa setiap pemanggilan alat.

**KUK 3.3 dan 3.4 Pemeliharaan.** Tiga mekanisme menjaga metadata tetap benar tanpa bergantung pada kedisiplinan menulis.

- **Metadata tidak ditulis tangan.** Metadata dibangkitkan dari `config/mesh/*.yaml` oleh `sdg_gudang.gudang.kontrak`. Aset Dagster `kontrak_mesh` dan uji `test_gudang_kontrak` gagal bila berkas yang di-commit tertinggal dari konfigurasinya.
- **Lineage dibangkitkan ulang** dengan `python3 -m sdg_gudang.gudang.lineage` setelah setiap job `gudang_penuh`.
- **Utang metadata terlihat.** `dim_satuan` memisahkan satuan M1 dari 72 satuan lokal `x_` (`terdaftar_m1 = false`), sehingga satuan yang belum dikurasi dapat dihitung, bukan tersembunyi.

**Data pendukung** (sudah ada di repositori):

- [`data/gudang/m4_lineage.json`](../../data/gudang/m4_lineage.json): 166 simpul, 320 sisi, jalur setiap data product ke berkas raw, dibangun 21 Oktober 2026.
- [`data/gudang/m5_kg_ringkasan.json`](../../data/gudang/m5_kg_ringkasan.json): TPB-KG 85.734 tripel, 0 pelanggaran SHACL, cakupan indikator per tujuan.
- [`data/produk/uji-graf.json`](../../data/produk/uji-graf.json): graf dibangun ulang dari Gold acuan dengan sha256 identik; pengelompokan 109 indikator; 46 keterkaitan tayang.
- [`data/produk/uji-keterikatan.json`](../../data/produk/uji-keterikatan.json): keterikatan jawaban Bravais per kondisi, jenis pertanyaan, dan biaya.

## Catatan terbuka

- **Repositori metadata versi ringan**, bukan OpenMetadata. Pencarian metadata lintas data product masih lewat berkas JSON-LD dan katalog Iceberg, belum lewat antarmuka katalog. Keputusan ini saya ambil sendiri dan harus dapat saya pertahankan di hadapan asesor.
- **Angka lineage di dokumen sumber 20 Oktober (161 simpul, 312 sisi) sudah tertinggal.** Yang berlaku adalah berkas di `data/`: 166 simpul dan 320 sisi setelah perbaikan tanggal rilis pada 21 Oktober.
- **Metadata hanya untuk 9 data product dan 12 tabel `dp`.** Tabel Bronze dan Silver baru punya metadata teknis dari katalog Iceberg, belum rekaman DCAT.
- **72 satuan lokal belum dikurasi** ke satuan kanonik; utangnya terukur tetapi belum dilunasi.
- **Pemeriksaan klaim berita baru menjangkau dua indikator**, sehingga lapis semantik untuk klaim belum teruji luas.
- **Kode yang dirujuk tersalin di [`code/`](../../code/README.md)** dari repositori penelitian Ardika pada commit `dcaa55e` (22 Oktober 2026), termasuk jalur berkasnya yang disebut di atas.
