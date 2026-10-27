# 04. Data rujukan dan master

**Unit:** J.62DMS00.008.1 Mengelola Reference and Master Data

**Pertanyaan yang dijawab:** Kode wilayah, indikator, dan satuan mana yang menjadi acuan bersama semua sumber?

**Yang saya kerjakan:** Saya menetapkan lima kebutuhan data rujukan dan master dari masalah yang benar-benar terjadi saat menggabungkan lebih dari sepuluh sumber: kode Papua yang tertukar antara BPS dan Kemendagri, kode provinsi GeoJSON yang tidak unik, dan satuan "per 1.000" yang terbaca sebagai nilai. Dari kebutuhan itu saya membangun dimensi wilayah tipe 2 yang tahan pemekaran, tabel padanan kode BPS, Kemendagri, dan ISO per periode, dimensi indikator TPB berpadanan kode global, satuan kanonik, dan tulang punggung graf pengetahuan yang divalidasi SHACL. Semua konsumen memakai satu resolver, dan 11 uji unit membuktikan bahwa perubahan kode dan pemekaran ditangani tanpa menebak.

| Elemen | Yang saya kerjakan | Bukti | Jenis | Status |
| --- | --- | --- | --- | --- |
| 1. Mendefinisikan kebutuhan reference and master data | menurunkan lima kebutuhan dari kesalahan nyata, menganalisis delapan sumber rujukan, dan menetapkan definisi data yang dipakai semua tabel | tabel pada Elemen 1; `raw/referensi/2026-10-20/SUMBER.md` di DSIC-SDG | T | lengkap |
| 2. Membangun reference and master data | membangun lima tabel rujukan, dimensi wilayah tipe 2 (42 baris), dua tabel pemetaan, dan ontologi SDG dengan validasi SHACL | `data/gudang/m4_sidik_gold.json` (tabel `dp_referensi_*`); `src/sdg_gudang/referensi.py` di DSIC-SDG | TL, L | lengkap, kode belum disalin ke `code/` |
| 3. Menggunakan reference and master data | menyediakan satu resolver untuk semua konsumen dan mengelola lima jenis perubahan, dibuktikan 11 uji unit | `tests/unit/test_sdg_gudang_referensi.py` di DSIC-SDG; `data/gudang/m5_kg_ringkasan.json` | L, TL | lengkap, kode belum disalin ke `code/` |

Jenis bukti: **L** langsung (artefak yang berjalan), **TL** tidak langsung (hasil terukur, laporan), **T** tambahan (dokumen tata kelola, surat).

## Kedudukan langkah ini

Pekerjaan ini dikerjakan 20 Oktober 2026 pada fase M1 (data rujukan dan metadata), sebelum konektor sumber dan gudang dibangun. Urutannya disengaja: kunci bersama harus ada lebih dulu, karena pemetaan Silver (langkah 07), gudang (langkah 09), dan graf pengetahuan (langkah 05) semuanya merujuk ke kunci yang sama. Artefaknya dibangun dengan satu perintah `make m1-referensi` dan diuji dengan `make m1-test` di repositori DSIC-SDG.

## Elemen 1. Kebutuhan reference and master data

**KUK 1.1 Kebutuhan sesuai organisasi.** Setiap sumber menamai wilayah, indikator, dan satuan dengan caranya sendiri, padahal level lintas tujuan, peta, Kartu Keterkaitan, dan rekonsiliasi memerlukan kunci bersama. Lima kebutuhan berikut dibedakan menurut jenisnya: master data untuk entitas inti yang dirujuk banyak tabel, reference data untuk daftar kode yang dipakai bersama.

| Kebutuhan | Jenis | Alasan |
| --- | --- | --- |
| Kunci wilayah tunggal yang tahan pemekaran | master data | data Gold berentang 1977–2026; provinsi dimekarkan pada 2012 dan 2022 |
| Padanan kode BPS, Kemendagri, ISO 3166-2, dan nama | reference data | BPS memakai kode BPS; SIGN-SMART memakai ISO; dokumen pemerintah daerah memakai kode Kemendagri; GeoJSON memakai nama |
| Kode indikator TPB nasional dan padanan globalnya | reference data, ontologi | sumber internasional memakai kode global; BPS memakai kode TPB nasional bertanda `*` atau `(a)` |
| Pilar TPB | reference data | domain data mesh (langkah 03) |
| Satuan kanonik dengan penyebut rasio | reference data | penilai harness v3 salah membaca "per 1.000" sebagai nilai |

**KUK 1.2 Analisis sumber.** Delapan sumber rujukan diunduh pada 20 Oktober 2026 dan dicatat di `raw/referensi/2026-10-20/SUMBER.md`. Temuan analisisnya menentukan bentuk tabel pada Elemen 2.

| Sumber | Temuan analisis |
| --- | --- |
| Bridging kode BPS (`sig.bps.go.id/rest-bridging`) | laman hanya mencantumkan periode sampai 2020 Semester 2 (34 provinsi). Periode 38 provinsi tersedia lewat `periode_merge` 2023_1.2022, 2024_1.2022, 2025_1.2025, 2025_2.2025. Pada dua periode pertama, Papua Barat Daya berkode dan bernama Kemendagri sama dengan Papua Barat (92, "PAPUA BARAT"); mulai 2025 berkode 96 |
| ISO 3166-2:ID (pycountry 26.2.16) | 36 provinsi, ID-JK, ID-YO; nama ID-PE tertulis "Papua Pengunungan" |
| GeoJSON 38 provinsi (dipakai game) | `KODE_PROV` tidak unik: empat provinsi Papua berkode 91, dua berkode 92 |
| Skema konsep SDG PBB (LOD4Stats) | terakhir diperbarui 12 Mei 2020, diarsipkan 8 Juli 2024; tidak memuat 4.1.2 dan 13.2.2 yang berubah atau ditambahkan setelahnya |
| API UNSD (pohon tujuan) | memuat semua kode global dari katalog TPB; lisensi belum jelas (kelas B, internal) |
| Katalog TPB (`config/tpb/`) | 105 indikator, 14 tujuan; satu variabel BPS dapat dipadankan dengan beberapa kode (contoh var 1584 dengan 3.2.1* dan 3.2.2*) |
| Permen PPN/Bappenas 1/2024 | Pasal 4 ayat (3) sampai (6) membagi 17 tujuan ke empat pilar |
| Metadata Indikator TPB Bappenas | belum dapat diunduh otomatis (HTTP 403); definisi rinci indikator menunggu unduhan tangan |

**KUK 1.3 Definisi data.** Definisi berikut ditetapkan sekali dan dipakai di semua tabel.

- **`wilayah_kode`** adalah kunci wilayah tahan lama: kode BPS dua digit dikali 100, sama dengan Gold; 9999 berarti nasional. Kunci ini tidak pernah dipakai ulang untuk daerah lain.
- **`wilayah_sk`** adalah kunci pengganti per versi wilayah.
- **Masa berlaku versi wilayah** adalah `[berlaku_dari, berlaku_sebelum)`. Batas bawah kosong berarti sejak awal data; batas atas kosong berarti masih berlaku.
- **Dua observasi wilayah yang sama sebanding** hanya bila keduanya jatuh pada versi yang sama.
- **`padanan_global`** mengikuti legenda klasifikasi pada halaman Metadata SDGs Bappenas (`sdgs.bappenas.go.id/metadata-sdgs`, diperiksa 20 Oktober 2026): `nasional_global` untuk kode bertanda `*` (indikator nasional sama dengan global, diterbitkan di KG sebagai `skos:exactMatch`); `proksi` untuk kode berakhiran `(a)`, `(b)`, dan seterusnya; `tanpa_tanda` untuk kode tanpa tanda yang tidak dijelaskan legenda, sehingga hanya dinyatakan kodenya sama; dan `proksi_sektoral` untuk rencana dari sumber sektoral.
- **Satuan rasio "per N"** menyimpan N sebagai `penyebut`. Angka N pada teks bukan nilai indikator.

**Aspek kritis.** Aspek kritis unit ini adalah ketepatan mengidentifikasi definisi data. Tiga definisi di atas lahir dari kesalahan yang benar-benar terjadi, bukan dari teori: kode Papua tertukar antara BPS (94) dan Kemendagri (91); `KODE_PROV` GeoJSON tidak unik sehingga tidak dapat dipakai sebagai kunci; dan satuan "per 1.000" terbaca sebagai nilai oleh penilai harness keterikatan v3. Definisi yang tepat adalah definisi yang menutup kesalahan semacam itu, dan itulah yang diuji pada Elemen 3.

## Elemen 2. Membangun reference and master data

**KUK 2.1 Definisi ke reference data termasuk ontologi.** Jumlah baris di bawah adalah keadaan 20 Oktober 2026 pada `artefak/referensi/`. Setelah dimuat ke gudang pada M4, tabel yang sama muncul sebagai `dp_referensi_*` dengan jumlah baris yang tercatat di `data/gudang/m4_sidik_gold.json`.

| Tabel | Baris | Isi |
| --- | ---: | --- |
| `dim_pilar` | 4 | pilar dan tujuannya, dengan dasar Permen 1/2024 |
| `dim_indikator` | 109 | 105 indikator TPB katalog dan 4 rencana sektoral (12.5.1, 13.1.1, 13.2.2, 14.5.1); 56 `nasional_global`, 48 `proksi`, 1 `tanpa_tanda`, 4 `proksi_sektoral`; di gudang `dp_referensi_indikator` 109 baris |
| `dim_satuan` | 18 | satuan kanonik; semua 19 teks satuan pada Gold v3 dan katalog BPS terpetakan tepat satu; di gudang `dp_referensi_satuan` 91 baris setelah satuan lokal tiap sumber ditambahkan pada M3 |
| `alias_wilayah` | 82 | 43 nama ternormalisasi dan 39 kode ISO ke `wilayah_kode` |
| `kg/sdg_spine.ttl` | 3.305 tripel | ontologi: tujuan, target, indikator global ber-IRI PBB; pilar; indikator TPB; versi wilayah dengan `lk:pecahanDari` dan `lk:menggantikan`; di gudang `dp_referensi_konsep` 1.126 baris |

Graf divalidasi SHACL (`kg/bentuk.ttl`) di setiap pembangunan. Contoh aturannya: setiap indikator TPB mempunyai tepat satu tujuan dan satu pilar, dan setiap versi wilayah mempunyai tepat satu kode BPS dan satu kode ISO. Pembangunan gagal bila ada pelanggaran. Graf penuh TPB-KG yang dibangun di atas tulang punggung ini (langkah 05) memuat 85.734 tripel dan lulus SHACL tanpa pelanggaran (`data/gudang/m5_kg_ringkasan.json`).

**KUK 2.2 Data ke master data.** `dim_wilayah` memuat 42 baris: 38 provinsi terkini, tiga versi sebelum pemekaran (Kalimantan Timur, Papua, Papua Barat), dan satu baris nasional. Jumlah yang sama tercatat pada `dp_referensi_wilayah` di gudang. Ini dimensi tipe 2: versi lama ditutup dengan tanggal, bukan ditimpa, sehingga angka lama tetap terpasang ke wilayah yang benar pada waktunya.

| Wilayah | Versi | Hubungan | Dasar |
| --- | --- | --- | --- |
| Kalimantan Timur | v1 sampai 16 Nov 2012; v2 sejak 17 Nov 2012 | – | UU 20/2012 |
| Kalimantan Utara | v1 sejak 17 Nov 2012 | pecahan Kalimantan Timur | UU 20/2012 |
| Papua | v1 sampai 24 Jul 2022; v2 sejak 25 Jul 2022 | – | UU 14, 15, 16/2022 |
| Papua Selatan, Papua Tengah, Papua Pegunungan | v1 sejak 25 Jul 2022 | pecahan Papua | UU 14, 15, 16/2022 |
| Papua Barat | v1 sampai 7 Des 2022; v2 sejak 8 Des 2022 | – | UU 29/2022 |
| Papua Barat Daya | v1 sejak 8 Des 2022 | pecahan Papua Barat | UU 29/2022 |

Pemekaran sebelum 2012 belum dimodelkan. Batas ini tercatat di `manifest.json` dan `metadata.jsonld` sebagai `catatan_cakupan`, supaya pemakai tahu sampai mana dimensi ini dapat dipercaya.

**KUK 2.3 Pemetaan data bersama.**

| Tabel | Isi |
| --- | --- |
| `padanan_kode_wilayah` | 186 baris: setiap periode bridging × provinsi, dengan penanda `ambigu_kemendagri`; empat baris ambigu pada 2023_1.2022 dan 2024_1.2022 |
| `peta_tabel_indikator` | 76 tabel Gold v3 ke indikator: 41 lewat kode di nama tabel, 13 lewat variabel katalog, 22 lewat keputusan steward |

Keputusan steward atas 22 tabel yang tidak terpetakan otomatis atau ambigu dicatat di `config/referensi/peta_tabel_kurasi.csv` dengan tanggal dan alasan: 11 tabel berhubungan "kode sama", 6 "berkaitan", 3 "bukan indikator TPB", 1 "proksi", dan 1 "sebagian". Pembangun menolak tabel Gold yang tidak terpetakan atau terpetakan ke lebih dari satu kode tanpa keputusan steward, sehingga pemetaan tidak pernah dibiarkan menggantung diam-diam.

## Elemen 3. Menggunakan reference and master data

**KUK 3.1 Penyebaran data bersama.** Konsumen tidak membuat tabel padanan masing-masing, tetapi memakai satu resolver `Rujukan` di `src/sdg_gudang/referensi.py`.

| Fungsi | Kegunaan |
| --- | --- |
| `dari_bps`, `dari_kemendagri(kode, periode)`, `dari_iso`, `dari_nama` | memetakan kunci sumber ke `wilayah_kode`; kode Kemendagri ambigu menimbulkan galat `KodeAmbigu`, bukan tebakan |
| `periksa_batch(sistem, kode)` | memeriksa satu batch kunci dari sumber; kunci ganda dikarantina seluruhnya; provinsi yang tidak muncul dilaporkan |
| `versi_asof(kode, tanggal)` dan `sebanding(kode, t1, t2)` | memilih versi wilayah yang berlaku dan menandai deret yang melintasi pemekaran |

Konsumen yang sudah memakainya: pemetaan Silver dan karantina (langkah 07), model dbt gudang (langkah 09), dan TPB-KG (langkah 05). Tabel rujukan dimuat ke Iceberg sebagai `dp_referensi` milik tim platform (langkah 03).

**KUK 3.2 Pengelolaan perubahan.** Lima jenis perubahan diantisipasi, dan masing-masing punya cara penanganan yang tidak menghapus keadaan lama.

| Perubahan | Cara dikelola |
| --- | --- |
| Pemekaran wilayah | versi baru di `dim_wilayah` dengan tanggal dan dasar hukum; versi lama ditutup, tidak dihapus |
| Kode Kemendagri berubah (Papua Barat Daya 92 ke 96) | `padanan_kode_wilayah` per periode bridging; resolver meminta periode bila kode ambigu |
| Sumber rujukan baru | snapshot bertanggal baru di `raw/referensi/<tanggal>/` dengan manifest; snapshot lama tidak ditimpa |
| Keputusan steward baru | baris baru di `peta_tabel_kurasi.csv` dengan tanggal dan alasan; tinjauan lewat commit git |
| Pembangunan ulang | deterministik; uji membangun dua kali dan membandingkan sha256 setiap berkas |

Sebelas uji unit di `tests/unit/test_sdg_gudang_referensi.py` membuktikan penanganan itu. Lima yang paling menentukan:

| Uji | Yang dibuktikan |
| --- | --- |
| `test_kode_kemendagri_papua_barat_daya_berubah_antarperiode` | kode 92 ambigu pada 2024 dan kode 96 berlaku mulai 2025 |
| `test_versi_asof_dan_kesebandingan` | Papua 2021 tidak sebanding dengan Papua 2023; Lampung 2000 sebanding dengan 2025 |
| `test_signsmart_kode_id_ac_ganda_dikarantina` | lima baris berkode ID-AC dikarantina; Aceh dan empat provinsi Papua baru dilaporkan hilang |
| `test_kode_prov_geojson_tidak_unik_tetapi_nama_terpetakan` | 38 fitur GeoJSON terpetakan ke 38 kode berbeda lewat nama |
| `test_bangun_deterministik` | hash sama pada dua pembangunan |

**Data pendukung** (sudah ada di repositori):

- [`data/gudang/m4_sidik_gold.json`](../../data/gudang/m4_sidik_gold.json): jumlah baris dan sidik `dp_referensi_wilayah` (42), `dp_referensi_indikator` (109), `dp_referensi_satuan` (91), `dp_referensi_konsep` (1.126), dan `dp_rilis` (2.678) setelah dimuat ke gudang.
- [`data/gudang/m5_kg_ringkasan.json`](../../data/gudang/m5_kg_ringkasan.json): graf TPB-KG 85.734 tripel, 0 pelanggaran SHACL, 103 dari 105 indikator berpadanan kode global.

## Catatan terbuka

- **Nama tabel v3 `sdg3_3_2_1_v1584` menyesatkan.** Namanya memuat kode 3.2.1, padahal isinya angka kematian bayi, yang bukan 3.2.1 (kematian balita) maupun 3.2.2 (kematian neonatal). Isi level tidak terpengaruh. Kode TPB nasional yang benar diperiksa setelah buku Metadata Indikator TPB diunduh tangan.
- **Arti tanda `*` dan `()` baru dipastikan dari legenda halaman Metadata SDGs Bappenas**, belum dari buku metadata 2024. Buku itu diunduh tangan (`docs/gudang/unduh-tangan.md` di DSIC-SDG) untuk memeriksa definisi per indikator.
- **Pemekaran sebelum 2012 belum dimodelkan**, sehingga deret 1977–2011 pada provinsi hasil pemekaran lama belum ditandai ketidaksebandingannya.
- **Ruang nama KG `https://sd.itera.ac.id/kg/` masih sementara.** IRI tidak dipakai di luar repositori sebelum ruang nama yang stabil diputuskan.
- **Kode belum disalin ke `code/`.** `src/sdg_gudang/referensi.py`, `config/referensi/`, dan uji unitnya masih di DSIC-SDG; akan disalin sesuai daftar di `code/README.md`.

## Catatan untuk wawancara asesor

Dokumen di repositori ini disusun dengan bantuan asisten AI (Claude). Keputusan tetap tanggung jawab saya. Pertanyaan yang harus bisa saya jawab tanpa membaca: apa beda reference data dan master data pada proyek ini, apa yang terjadi pada angka Papua 2021 setelah pemekaran 2022, dan mengapa resolver menolak menebak kode Kemendagri yang ambigu.
