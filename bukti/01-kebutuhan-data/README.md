# 01. Kebutuhan data

**Unit:** J.62DMS00.001.1 Mengidentifikasi Kebutuhan Pengelolaan Data untuk Proses Bisnis

**Pertanyaan yang dijawab:** Data apa saja yang dimiliki dan dipakai organisasi, dan mengapa harus dikelola?

**Yang saya kerjakan:** Saya menginventarisasi 38 aset data yang dimiliki dan dipakai pengelola Liga Lakehouse pada 20 Oktober 2026, yaitu 24 aset yang sudah ada dan 14 yang masih direncanakan, lalu menempatkan setiap aset pada tatanan kerja organisasi lengkap dengan steward, kelas lisensi, sensitivitas, dan masa retensinya. Dari inventaris itu saya menurunkan empat aturan penanganan aset dan memilih model operasional tata kelola federasi, karena sumber data bertambah dari satu produsen menjadi lebih dari sepuluh dengan pengetahuan domain yang berbeda, sedangkan kode wilayah, kode indikator, dan satuan harus tetap sama di semua domain.

| Elemen | Yang saya kerjakan | Bukti | Jenis | Status |
| --- | --- | --- | --- | --- |
| 1. Menentukan bentuk aset data organisasi dan aspek pengelolaannya | menguraikan tiga fungsi organisasi yang memakai data, mengelompokkan 38 aset ke delapan kelompok menurut aktivitas pemakainya, menetapkan empat aturan penanganan, dan menyelaraskannya dengan sasaran 2026 | `data/serkom/inventaris-aset-data.csv`; dua insiden yang menjadi aturan kontrak (KUK 1.5) | TL, L | lengkap |
| 2. Menentukan aspek tata kelola aset data organisasi | memetakan setiap aset ke tujuh tatanan kerja lewat kolom `pilar` dan `steward`, memisahkan ranah keputusan data dari TI lewat kolom `ranah_tata_kelola` | kolom `pilar`, `steward`, `ranah_tata_kelola` pada inventaris; matriks RACI (Responsible, Accountable, Consulted, Informed) di langkah 02 | TL, T | lengkap, pemilik domain masih simulasi |
| 3. Mengidentifikasi tipe model operasional tata kelola data | membandingkan model terpusat, tereplikasi, dan terdistribusi pada keadaan organisasi ini, lalu memilih federasi | tabel perbandingan di bawah; rincian di langkah 03 | T | lengkap |
| 4. Mengidentifikasi unsur pengelolaan aset data (data stewardship) | menetapkan tanggung jawab steward atas metadata, mendaftar aturan yang sudah berversi di git, mencatat enam isu kualitas yang sudah teridentifikasi, dan menjadikan kepatuhan sebagai pemeriksaan otomatis | kolom `steward` pada inventaris; aturan di DSIC-SDG; tabel isu kualitas di bawah | TL, T, L | lengkap, kode belum disalin ke `code/` |

Jenis bukti: **L** langsung (artefak yang berjalan), **TL** tidak langsung (hasil terukur, laporan), **T** tambahan (dokumen tata kelola, surat).

## Organisasi yang dinilai

Organisasi pada unit ini adalah Kelompok Keahlian Program Studi Sains Data, Institut Teknologi Sumatera, dalam perannya sebagai pengelola Liga Lakehouse. Liga Lakehouse adalah game edukasi indikator SDG yang berjalan di Data Science Workbench (DSW, `sd.itera.ac.id`, sekitar 300 pengguna) dan dipasok oleh lakehouse riset yang dibangun pada proyek ini. "Tatanan kerja organisasi" yang dimaksud unit ini saya artikan sebagai empat domain pilar TPB, satu tim platform, dan operator DSW; pembagian tanggung jawabnya dirinci pada langkah 02.

Inventaris disusun pada 20 Oktober 2026, pada fase M0 (tata kelola dan izin), sebelum gudang dibangun. Karena itu inventaris memuat dua jenis baris: aset yang benar-benar ada pada tanggal itu (kode A01–A24) dan aset yang baru direncanakan pada rencana kerja gudang (kode B01–B14), masing-masing dengan fase pengerjaannya. Pemisahan ini disengaja agar asesor dapat membedakan apa yang sudah dikerjakan dari apa yang baru direncanakan.

## Elemen 1. Bentuk aset data organisasi dan aspek pengelolaannya

**KUK 1.1 Latar belakang dan aktivitas organisasi.** Kelompok keahlian menjalankan tiga fungsi yang memakai data. Fungsi penelitian menghasilkan rekonsiliasi statistik resmi yang sadar vintage dan naskah terpadu Liga Lakehouse. Fungsi layanan pembelajaran menjalankan Liga Lakehouse beserta pemandu AI Bravais di DSW. Fungsi pengajaran memakai game itu sebagai bahan mata kuliah Pergudangan Data dan Data Wrangling. Aktivitas pokok yang mengikat ketiganya sama: mengunduh rilis resmi, merekonsiliasi dan menyimpan setiap vintage, mengompilasi paket level, menyajikannya kepada pemain, dan mengevaluasi kegunaannya.

**KUK 1.2 Data yang harus dikelola sebagai aset.** Aset dikelompokkan menurut aktivitas yang memakainya, bukan menurut format atau lokasinya, sehingga setiap kelompok dapat dihubungkan ke fungsi organisasi pada KUK 1.1.

| Kelompok | Jumlah | Aktivitas pemakai | Contoh |
| --- | ---: | --- | --- |
| sumber_mentah | 15 | penelitian, kompilasi | A01 snapshot BPS, B02 arsip WDI |
| harmonisasi | 2 | kompilasi | A07 harmonisasi 5E |
| gudang | 4 | penelitian, kompilasi | A12 Gold v3, A15 store vintage |
| sajian | 3 | layanan pembelajaran | A13 paket level v1 di produksi |
| metadata | 4 | semua | A09 kontrak data product, A10 katalog TPB |
| referensi | 2 | semua | B10 kode wilayah, B11 skema konsep SDG |
| operasional | 6 | layanan pembelajaran, evaluasi | A18 telemetri kiriman |
| penelitian | 2 | evaluasi, publikasi | A16 hasil harness, A24 data evaluasi pengguna |

**KUK 1.3 Penanganan aset sesuai praktik terbaik.** Rujukan yang saya pakai adalah DAMA-DMBOK, yang disebut pada pendahuluan SKKNI 268/2020. Dari kerangka itu saya turunkan empat aturan penanganan yang benar-benar dijalankan, bukan sekadar dinyatakan.

- **Raw hanya bertambah.** Setiap unduhan disimpan apa adanya dengan manifest sha256 dan tidak pernah ditimpa. Aturan ini syarat agar setiap angka yang pernah terbit dapat dipanggil ulang, dan sudah diuji pada rebuild dari raw (H15b).
- **Turunan dapat dibangun ulang.** Harmonisasi, Gold, dan paket level dibangun dari raw dengan satu perintah. Hash paket diuji sama pada dua kompilasi yang terpisah.
- **Data pribadi dipisah.** Aset operasional yang menyangkut pemain (A17–A22) hanya ada di server DSW. Yang keluar untuk analisis adalah ekspor ber-hash.
- **Lisensi menentukan tayang.** Setiap sumber diberi kelas A, A-SA, B, atau C menurut rencana kerja gudang Bagian 2.5. Kelas B dan C tidak tampil di game sampai izinnya jelas.

**KUK 1.4 Strategi kelola selaras rencana strategis.** Strategi pengelolaan mengikuti tiga sasaran kelompok keahlian untuk 2026: publikasi naskah terpadu dan artikel gudang multisumber pada akhir Desember, produk Liga Lakehouse yang mencakup 17 tujuan, dan portofolio sertifikasi Data Engineering. Ketiganya bertemu pada satu prinsip: setiap angka resmi yang pernah terbit harus dapat dipanggil ulang, ditelusuri, dan dijelaskan kepada pembelajar. Prinsip ini dirinci pada piagam tata kelola di langkah 02.

**KUK 1.5 Peningkatan berkesinambungan.** Setiap rilis paket level dan setiap pembaruan gudang melewati tiga pemeriksaan otomatis: uji kontrak, uji kelayakan level, dan kesamaan hash. Kegagalan dicatat sebagai temuan kualitas (langkah 08) beserta akar masalahnya, dan perbaikannya dijadikan aturan agar kesalahan yang sama tidak terulang. Dua insiden yang sudah terjadi menunjukkan siklus itu berjalan.

- **Paket v3 mengocok ulang level lama** karena benih acak memuat label versi. Perbaikannya, parameter `versi_benih`, kini menjadi aturan kontrak.
- **Penilai harness membaca satuan "per 1.000" sebagai angka**, sehingga jawaban yang benar dinilai salah. Perbaikannya dijadwalkan sebagai versi penilai baru, bukan diterapkan diam-diam, supaya hasil lama dan baru tetap dapat dibandingkan.

## Elemen 2. Aspek tata kelola aset data organisasi

**KUK 2.1 Aset pada tatanan kerja.** Kolom `pilar` dan `steward` pada inventaris menempatkan setiap aset pada tatanan kerjanya.

| Tatanan kerja | Aset utama |
| --- | --- |
| Domain Pilar Sosial (SDG 1–5) | bagian A02, A07, A08, A12, B04 yang menyangkut tujuan 1–5 |
| Domain Pilar Ekonomi (SDG 7–10, 17) | A03, A04, A06, B02, bagian A07–A08 |
| Domain Pilar Lingkungan (SDG 6, 11–15) | B05–B08, bagian A07–A08 |
| Domain Pilar Hukum dan Tata Kelola (SDG 16) | bagian A02 dan A08 |
| Tim platform | A09–A15, B09–B11, B13, B14 |
| Operator DSW | A17–A23 |
| Penanggung jawab penelitian | A16, A24, B12 |

**KUK 2.2 Unsur tanggung jawab tata kelola data dan TI.** Kolom `ranah_tata_kelola` memisahkan aset yang keputusannya menyangkut isi dan makna data (`data`) dari aset yang keputusannya menyangkut sistem yang menjalankannya (`TI`). Sebagian aset bersentuhan dengan keduanya dan ditandai `TI dan data`, misalnya telemetri kiriman A18: isi dan retensinya adalah keputusan tata kelola data, sedangkan ketersediaan dan cadangan basis data DSW adalah keputusan tata kelola TI. Siapa yang memutuskan apa pada tiap kegiatan ada di matriks RACI langkah 02.

**KUK 2.3 Perbedaan tata kelola data dan tata kelola TI.**

| Aspek | Tata kelola data | Tata kelola TI |
| --- | --- | --- |
| Pertanyaan pokok | data apa yang dikelola, apa artinya, siapa boleh memakai, seberapa benar | sistem apa yang menyimpan dan menjalankan, seberapa tersedia dan aman |
| Contoh keputusan pada proyek ini | kelas tayang per sumber; aturan rekonsiliasi; toleransi jawaban level; retensi teks berita | ukuran server Lightsail; penjadwalan cadangan SQLite DSW; versi Iceberg dan Trino; akses SSH |
| Pemilik keputusan | pemilik domain dan steward, dalam aturan global tim platform | operator DSW dan tim platform |
| Ukuran keberhasilan | kelulusan kontrak, skor kualitas, kelengkapan lineage | latensi p95, ketersediaan, keberhasilan pemulihan |
| Rujukan | DAMA-DMBOK | praktik operasi DSW (ADR di repositori DSW) |

## Elemen 3. Tipe model operasional tata kelola data

Ketiga model dinilai pada keadaan organisasi yang sama, lalu dipilih satu. Alasan lengkap beserta pengaruh budaya dan peraturannya ada di langkah 03.

| Model | Ciri | Penerapan pada organisasi ini | Dipilih? |
| --- | --- | --- | --- |
| **KUK 3.1 Terpusat** | satu tim memutuskan semua aturan data dan mengerjakan semua alur | keadaan sampai 19 Oktober 2026: satu peneliti memegang semua tabel, kontrak, dan paket | tidak, karena sumber bertambah dari satu produsen menjadi lebih dari sepuluh dengan pengetahuan domain yang berbeda |
| **KUK 3.2 Tereplikasi** | setiap unit menjalankan salinan model tata kelola yang sama secara mandiri | setiap pilar membangun gudangnya sendiri dengan aturan sendiri | tidak, karena kode wilayah, kode indikator, dan satuan harus sama di semua pilar agar level lintas tujuan dan Kartu Keterkaitan dapat dibentuk |
| **KUK 3.3 Terdistribusi (federasi)** | aturan global sedikit dan ditegakkan pusat; unit domain memiliki dan mengelola datanya sendiri | data mesh: empat domain pilar memiliki data product; tim platform menegakkan aturan global (kode wilayah, indikator, satuan, kelas lisensi) secara otomatis | **ya** |

## Elemen 4. Unsur pengelolaan aset data (data stewardship)

**KUK 4.1 Membuat dan mengelola metadata.** Steward setiap aset menulis deskripsi, pemilik, kontrak, dan kelas lisensi produknya. Tim platform menetapkan standar metadatanya, yaitu DCAT dan konsep SDMX dengan Metadata Indikator TPB Bappenas sebagai sumber definisi. Repositori metadata yang akhirnya dipakai adalah versi ringan (DCAT per data product, dokumentasi dbt, katalog Iceberg REST), bukan OpenMetadata seperti yang direncanakan pada inventaris; alasannya dijelaskan pada langkah 05.

**KUK 4.2 Mendokumentasikan aturan dan standar.** Aturan berikut sudah terdokumentasi dan berversi di git pada repositori penelitian DSIC-SDG.

- Kontrak data product `config/sdg_game/contract*.json`: skema, toleransi, dan kelayakan level.
- Aturan klasifikasi ketidaksesuaian H3: delapan aturan, dibekukan sebelum data diperiksa.
- Praregistrasi uji dua kanal BPS pada `docs/terpadu/e2-praregistrasi.md`.
- Aturan rekonsiliasi multisumber: dibekukan pada M3 sebelum perbandingan pertama.

**KUK 4.3 Isu manajemen kualitas data yang sudah teridentifikasi.** Enam isu berikut sudah diketahui pada saat inventaris disusun dan dicatat pada kolom `catatan`. Penanganannya dibahas pada langkah 04 (kode wilayah) dan langkah 08 (kualitas).

| Isu | Aset | Dampak |
| --- | --- | --- |
| Kode Papua berbeda antara BPS (94) dan Kemendagri (91) | B10 | sel salah wilayah bila kode tidak dipetakan |
| SIGN-SMART memberi kode `ID-AC` pada empat provinsi Papua baru | B07 | emisi tertukar ke Aceh |
| SIPSN hanya menyediakan snapshot terkini | B05 | SDG 12 tanpa deret waktu |
| 560 kunci Gold banyak-ke-satu (contoh `sd` dan `sd.total`) | A11 | pemetaan ke store vintage ambigu |
| Satuan "per 1.000" terbaca sebagai nilai oleh penilai | A16 | jawaban benar dinilai salah |
| WHO GHO OData mungkin dihentikan | B04 | konektor rusak |

**KUK 4.4 Menjalankan kegiatan tata kelola operasional.** Kepatuhan dipastikan oleh pemeriksaan yang berjalan sendiri, bukan oleh imbauan.

- Uji kontrak dan uji kelayakan berjalan pada setiap kompilasi.
- Pemeriksa di server menolak paket yang jawabannya tidak cocok.
- Guardrail Bravais menolak menyebut angka tanpa memanggil tool.
- Daftar tugas pemilik diperbarui mengikuti keadaan (`docs/game/tugas-manual-pemilik.md` di DSIC-SDG).
- Satu aturan pemasangan: produksi hanya berubah atas izin penanggung jawab.

## Aspek kritis: ketepatan mengidentifikasi aset data pada tatanan kerja

Inventaris diturunkan dari folder dan tabel yang nyata pada 20 Oktober 2026, bukan dari rancangan. Ukuran diukur dengan `du`, dan nama tabel DSW diambil dari skema `sdg_check._SCHEMA` di repositori DSW. Aset yang belum ada diberi status `rencana` beserta fasenya. Setiap baris dapat saya jelaskan asalnya, dan itulah yang saya anggap sebagai ukuran ketepatan pada aspek kritis ini.

**Data pendukung** (sudah ada di repositori):

- [`data/serkom/inventaris-aset-data.csv`](../../data/serkom/inventaris-aset-data.csv): 38 aset dengan kolom lokasi, format, ukuran, produsen, steward, kelas lisensi, sensitivitas, retensi, status, dan ranah tata kelola. Salinan identik dengan sumbernya di DSIC-SDG (`docs/serkom/J.62DMS00.001.1/`), sidiknya tercatat di `data/SIDIK.txt`.

## Catatan terbuka

- **Pemilik domain masih simulasi.** Keempat domain pilar pada tatanan kerja masih saya pegang sendiri; kolom `steward` pada inventaris menyebut peran, bukan orang yang sudah ditunjuk. Sisi teknis federasi sudah terbukti, sisi organisasinya belum.
- **Inventaris adalah potret 20 Oktober 2026.** Sebagian aset berstatus `rencana` sudah dikerjakan pada fase M1–M5 dan dibuktikan pada langkah 04–10, dan keputusan repositori metadata (B14) berubah dari OpenMetadata menjadi versi ringan. Kolom `status` dan baris B14 belum disegarkan; saya biarkan apa adanya agar sidik berkas tetap cocok, dan perubahannya dicatat di sini.
- **Surat izin masih draf.** Izin untuk sumber kelas B (B03 UNSD, B05 SIPSN, B07 SIGN-SMART, B08 KKP) dan izin cuplikan berita ANTARA (B12) belum dikirim. Sampai izin terbit, sumber-sumber itu tidak tampil di game.
- **Kode belum disalin.** Kontrak, uji kelayakan, dan pemeriksa server yang dirujuk pada KUK 1.5 dan 4.4 masih berada di repositori DSIC-SDG yang privat. Bagian yang dirujuk akan disalin ke `code/` sesuai daftar di `code/README.md`; sebelum itu, kode ditunjukkan langsung saat demonstrasi.