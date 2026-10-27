# 09. Gudang data

**Unit:** J.62DMS00.014.1 Membuat Data Warehouse

**Pertanyaan yang dijawab:** Bagaimana setiap versi angka disimpan, dipanggil ulang, dan dibangun ulang sama persis?

**Yang saya kerjakan:** Saya membangun gudang berskema bintang bitemporal di lapis Gold: `fakta_observasi` menyimpan setiap nilai dari setiap rilis dengan interval berlaku, sehingga angka sebagaimana terbit pada tanggal tertentu dapat dipanggil ulang dengan kueri as-of, dan `nilai_pilihan` dihitung oleh aturan prioritas yang tercatat alih-alih membuang nilai. Tumpukannya Iceberg di atas penyimpanan objek S3, Trino sebagai mesin kueri, PyIceberg untuk memuat, dbt untuk transformasi dan 115 uji data, dan Dagster untuk menjalankan satu job `gudang_penuh` dari Raw sampai data product. Bukti bahwa sistem sesuai rancangan adalah uji dbt yang menegakkan rancangan itu dan sidik isi Gold `657df68e…` yang identik pada empat rebuild dari Raw.

| Elemen | Yang saya kerjakan | Bukti | Jenis | Status |
| --- | --- | --- | --- | --- |
| 1. Mengidentifikasi kebutuhan gudang data | menurunkan lima kebutuhan dari naskah vintage, rencana kerja, dan praktik praregistrasi, lalu memetakan wujudnya di gudang; mengidentifikasi 12 sumber lewat `dim_sumber` dan `dim_rilis` | tabel pada Elemen 1; `gold.dim_rilis` 2.678 baris di `data/gudang/m4_sidik_gold.json` | T, TL | lengkap |
| 2. Merancang skema dan memilih alat ETL | merancang struktur berlapis, skema bintang dua fakta tujuh dimensi dengan tiga sumbu waktu, dan memilih enam alat dengan alasan | tabel pada Elemen 2 | T | lengkap |
| 3. Membangun dan mendokumentasikan gudang data | 11 model `gold` dan 12 model `dp` dbt, 139 node lulus; dokumentasi dari `dbt docs` dan DCAT | 23 tabel di `data/gudang/m4_sidik_gold.json`; `dbt/gudang_sdg/` di repositori penelitian Ardika | TL, L | lengkap |
| 4. Memasang, menjalankan, dan memantau ETL | `make m4-naik` dengan versi dipatok; job Dagster `gudang_penuh`; metadata materialisasi per aset; empat rebuild bersidik sama; dua insiden ditangani | `data/produk/uji-keterulangan.json`, `data/produk/sidik-gold.json`, `data/produk/uji-kompilasi.json` | L, TL | lengkap |

Jenis bukti: **L** langsung (artefak yang berjalan), **TL** tidak langsung (hasil terukur, laporan), **T** tambahan (dokumen tata kelola, surat).

## Kedudukan langkah ini

Gudang dibangun pada fase M4 (gudang dan data mesh), 20–21 Oktober 2026, di atas Silver dari langkah 07 dan data rujukan dari langkah 04, dan menjadi sumber bagi data product federasi (langkah 03), TPB-KG (langkah 05), serta paket level dan Bravais yang diuji pada Tahap II. Elemen dan KUK mengikuti teks resmi lampiran Kepmenaker 268/2020 yang dicocokkan 24 Oktober 2026. Aspek kritis resminya adalah ketepatan membuat sistem data warehouse sesuai rancangan, dan karena itu bukti utamanya bukan diagram, melainkan uji yang menegakkan rancangan dan sidik yang membuktikan hasilnya sama setiap kali dibangun.

| KUK resmi | Bunyi ringkas | Tempat bukti |
| --- | --- | --- |
| 1.1 | kebutuhan data warehouse diidentifikasi sesuai kebutuhan organisasi | Elemen 1, tabel lima kebutuhan |
| 1.2 | sumber data warehouse diidentifikasi | Elemen 1; `dim_sumber` 15 baris, `dim_rilis` 2.678 rilis |
| 2.1 | struktur data warehouse dirancang | Elemen 2, lapis Raw, Bronze, Silver, Gold, data product |
| 2.2 | skema data warehouse dirancang | Elemen 2, skema bintang bitemporal |
| 2.3 | tools ETL diidentifikasi | Elemen 2, tabel alat dengan alasan |
| 3.1 | sistem data warehouse dibuat sesuai rancangan | Elemen 3, 11 model `gold` dan 12 model `dp` |
| 3.2 | proses dan hasil didokumentasikan | Elemen 3, `dbt docs`, DCAT, laporan M4 |
| 4.1 | sistem ETL di-install sesuai spesifikasi | Elemen 4, `make m4-naik`, versi dipatok |
| 4.2 | sistem ETL dioperasikan | Elemen 4, job `gudang_penuh`, empat jalan |
| 4.3 | berjalannya ETL dimonitor | Elemen 4, metadata materialisasi, uji dbt, SLA warn, sidik Gold |

## Elemen 1. Kebutuhan gudang data

Lima kebutuhan berikut masing-masing punya asal yang dapat ditunjuk dan wujud teknis yang dapat diuji.

| Kebutuhan | Asal | Wujud di gudang |
| --- | --- | --- |
| Angka yang pernah terbit tetap dapat dipanggil ulang | naskah vintage-aware; pedoman revisi statistik resmi | fakta bitemporal: setiap rilis disimpan, `berlaku_sejak` dan `berlaku_sampai` per rilis |
| Banyak sumber untuk indikator yang sama | rencana kerja gudang, Bagian 2 | satu fakta per sumber dan rilis; nilai pilihan dihitung aturan, bukan dengan membuang nilai |
| Konsumen game hanya boleh menampilkan sumber berlisensi terbuka | rencana kerja gudang, Bagian 2.5 | `nilai_pilihan_tayang` dan uji `hanya_tayang` pada setiap data product |
| Pemilik domain per pilar TPB | rencana kerja gudang, Bagian 3.4 | data product per pilar dengan kontrak (langkah 03) |
| Dapat dibangun ulang dan diaudit | praktik praregistrasi dan reproduksibilitas | rebuild dari Raw memberi sidik Gold yang sama |

Sumber gudang adalah lapis Silver dari 12 sumber statistik (langkah 06 dan 07). `dim_sumber` memuat 15 baris (12 sumber statistik beserta sumber berita dan rujukan), dan `dim_rilis` memuat 2.678 rilis dengan jenis bukti tanggalnya.

## Elemen 2. Rancangan skema dan alat ETL

**Struktur.** Gudang berlapis: Raw (berkas asli, hanya bertambah), Bronze (diurai menjadi baris apa adanya), Silver (kode kanonik, gagal ke karantina), Gold (skema bintang bitemporal), dan data product per pilar. Setiap lapis dapat dibangun ulang dari lapis di bawahnya.

**Skema.** Skema bintang dengan dua fakta dan tujuh dimensi.

| Tabel | Baris pada rebuild acuan | Isi |
| --- | ---: | --- |
| `fakta_observasi` | 1.486.490 | satu baris per (sumber, rilis, seri, wilayah, periode, rincian) dengan interval berlaku dan sha256 Raw |
| `fakta_selisih` | 1.377.573 | pasangan dua observasi berkunci konsep sama beserta kelas sebab selisih |
| `nilai_pilihan` | 109.289 | nilai terpilih per konsep, wilayah, periode menurut aturan prioritas, dengan `alasan_pilihan` |
| `nilai_pilihan_tayang` | 81.249 | subset `nilai_pilihan` yang calonnya hanya dari sumber boleh tayang |
| `dim_sumber`, `dim_rilis` | 15; 2.678 | sumber dengan kelas lisensi; rilis dengan tanggal efektif dan jenis bukti |
| `dim_wilayah` (tipe 2), `dim_indikator`, `dim_konsep`, `dim_satuan`, `dim_periode` | 42; 109; 1.126; 91; 181 | data rujukan dari langkah 04 |

Tiga sumbu waktu dipisahkan: **waktu periode** pada kolom `periode` (tahun yang diukur); **waktu rilis** pada `berlaku_sejak`, `berlaku_sampai`, dan `digantikan_oleh_rilis` (kapan produsen menerbitkan), yang dipakai kueri as-of; dan **waktu catat** pada `tercatat_pada` ditambah snapshot Iceberg (kapan baris ditulis). Observasi o berlaku pada tanggal acuan t bila `berlaku_sejak(o) ≤ t` dan `berlaku_sampai(o)` kosong atau `t < berlaku_sampai(o)`. Dengan aturan ini, TPT Agustus 2019 dapat dipanggil sebagaimana terbit pada 5 November 2019 maupun sebagaimana tertulis di tabel BPS sekarang, dan keduanya benar pada waktunya.

Gudang tidak memakai skor kepercayaan beku seperti fusi data. Semua observasi disimpan, dan nilai pilihan dihitung oleh aturan prioritas yang tercatat (BPS, lalu sektoral nasional, lalu kustodian internasional resmi, lalu Bank Dunia, lalu estimasi), dengan alasan pilihan ikut tersaji pada setiap baris. Untuk sajian, calon dari sumber yang tidak boleh tayang dikeluarkan sebelum pemilihan.

**Alat.** Setiap alat dipilih dengan alasan yang terukur atau teruji sebelumnya, bukan karena kebiasaan.

| Fungsi | Alat | Alasan pemilihan |
| --- | --- | --- |
| Format tabel | Apache Iceberg | snapshot dan time travel untuk waktu catat; sudah diuji pada H5 |
| Penyimpanan | S3 (SeaweedFS) | antarmuka S3 standar; citra tersedia untuk amd64 dan arm64 |
| Mesin kueri | Trino 476 | sudah diukur pada benchmark F5; dbt mempunyai adaptornya |
| Pemuatan | PyIceberg | Silver hanya 1,5 juta baris; Spark tidak diperlukan dan citranya 2,4 GB (diukur ulang pada langkah 10) |
| Transformasi dan uji | dbt | model, uji, kontrak, dan lineage dalam satu alat |
| Orkestrasi | Dagster | aset sepadan dengan data product; membaca lineage dbt (keputusan 20 Oktober 2026) |

## Elemen 3. Pembangunan dan dokumentasi gudang

**Model dbt.** 11 model `gold` dan 12 model `dp`. Model `dp` dibangkitkan dari YAML data product di `config/mesh/`, sehingga dokumentasi dan kontrak tidak dapat tertinggal dari konfigurasi; uji `test_gudang_kontrak` memastikannya (langkah 05). Pada rebuild acuan, 139 node dbt lulus: 23 model, 1 seed, dan 115 uji data.

**Uji yang menegakkan rancangan.** Jenisnya: kunci unik, not null, relasi ke dimensi, nilai yang diterima, identitas jumlah Silver–Gold, interval bitemporal tidak mundur, kewajaran tanggal rilis (ditambahkan setelah insiden pada langkah 08), satu seri per keluarga per konsep, tidak ada calon setara, hanya sumber kelas terbuka pada sajian, dan SLA kesegaran. Uji inilah yang menjadikan rancangan sesuatu yang ditegakkan mesin, bukan diagram yang harus dipatuhi secara manual.

**Dokumentasi.** `dbt docs generate` menghasilkan katalog dan lineage model; rekaman DCAT per data product ada di `artefak/mesh/`; laporan fase ada di `docs/gudang/m4-laporan.md` (semuanya di repositori penelitian Ardika). Sidik per tabel dan jumlah baris tersimpan di `data/gudang/m4_sidik_gold.json` sebagai dokumentasi hasil yang dapat diperiksa ulang.

## Elemen 4. Pemasangan, pengoperasian, dan pemantauan ETL

**Memasang.** `make m4-naik` menaikkan tumpukan (SeaweedFS, katalog Iceberg REST, Trino) dari `infra/gudang/compose.yml`, dan `pip install -r requirements-gudang.txt` memasang sisi Python. Versi semua paket dan citra dipatok, sehingga pemasangan di mesin lain memberi tumpukan yang sama.

**Menjalankan.** Job Dagster `gudang_penuh` menjalankan tujuh aset Python dan aset dbt berurutan menurut ketergantungannya. Jalan dari nol pada 20 Oktober 2026 berlangsung 5 menit 32 detik. Pada 21 Oktober gudang dijalankan ulang empat kali dari Raw di Mac, masing-masing setelah tumpukan dan volumenya dihapus.

| Jalan | Tanggal | Durasi | Sidik Gold | Sumber |
| --- | --- | ---: | --- | --- |
| C | 21 Okt 05:41 WIB | job 215 s | `657df68e…` | `m4_sidik_gold.json` |
| D | 21 Okt 05:46 WIB | job 228 s | `657df68e…` | `m4_sidik_gold.json` |
| Keterulangan 1 | 21 Okt 07:18 UTC | total 366 s (job 250 s) | `657df68e…` | `uji-keterulangan.json` |
| Keterulangan 2 | 21 Okt 07:25 UTC | total 338 s (job 239 s) | `657df68e…` | `uji-keterulangan.json` |

Sidik isi Gold dihitung sebagai sha256 atas baris terurut setiap tabel `gold.*` dan `dp.*` melalui Trino, sehingga tidak bergantung pada bita Parquet maupun snapshot Iceberg. Jalan A dan B sebelum perbaikan tanggal rilis memberi sidik lain (`f647dbae…`), dan jalan E dan F di cloud pada 20 Oktober memberi sidik lain lagi (`4183c5eb…`); riwayat ini sengaja disimpan di berkas yang sama. Sidik yang diukur Tahap II sebelum kelima pengujian (`data/produk/sidik-gold.json`) sama dengan `657df68e…`, sehingga semua angka produk berdiri di atas Gold yang sama.

Rantai ke produk ikut diuji. Kompilasi paket level v4 dari Gold acuan memberi hash paket, Gold Parquet, dan Gold SQLite yang identik pada dua kompilasi (`uji-kompilasi.json`; paket `afbcbeef…`), dan dua kompilasi pada uji keterulangan memberi hash yang sama dalam 15–16 detik. Dari 3.820 level kandidat, 1.570 lolos uji kelayakan; 836 level non-revisi identik dengan paket v3 kecuali label versinya, dan 73 dari 80 Dunia v3 tetap sama.

**Memantau.** Setiap aset mencatat metadata materialisasi di Dagster: jumlah baris per tabel, hitungan karantina, dan jumlah pasangan. Uji dbt yang gagal menghentikan job. Uji SLA kesegaran bertingkat warn, sehingga muncul di log tanpa menghentikan job (langkah 10).

**Insiden selama pemasangan dan perbaikannya.**

- **Trino terbunuh OOM** ketika membangun `fakta_observasi`, karena heap JVM bawaan 80 % tidak menyisakan memori native. Batas kontainer dinaikkan ke 6 GB dan heap diturunkan ke 65 %.
- **Rebuild pertama memberi sidik `nilai_pilihan` yang berbeda**, karena satu konsep menyatukan seri berbeda ukuran sehingga pemutus seri tidak deterministik. Konsep diganti dan dua uji ditambahkan (satu seri per keluarga per konsep, tidak ada calon setara); setelah itu dua jalan memberi sidik yang sama.

**Data pendukung** (sudah ada di repositori):

- [`data/gudang/m4_sidik_gold.json`](../../data/gudang/m4_sidik_gold.json): jumlah baris, kolom, dan sha256 untuk 23 tabel `gold.*` dan `dp.*`; jalan C dan D; riwayat sidik sebelumnya.
- [`data/produk/sidik-gold.json`](../../data/produk/sidik-gold.json): sidik Gold yang diukur Tahap II sebelum pengujian, 21 Oktober 2026 pukul 08:38 WIB.
- [`data/produk/uji-kompilasi.json`](../../data/produk/uji-kompilasi.json): hash paket v4, Gold Parquet, dan Gold SQLite pada dua kompilasi; kelayakan level; kesetaraan dengan v3.
- [`data/produk/uji-keterulangan.json`](../../data/produk/uji-keterulangan.json): dua rebuild gudang dan dua kompilasi paket dengan waktu per tahap dan sidiknya.

## Catatan terbuka

- **Dua Gold dengan sidik berbeda beredar:** Gold acuan `657df68e…` untuk laporan dan pengujian, dan Gold Laga `1b8c95e3…` (22 Oktober) yang hanya berbeda kelas lisensi empat sumber. Setiap angka harus disebut dengan Gold mana yang dipakainya.
- **Waktu catat baru ditandai, belum dipakai.** Snapshot Iceberg ada, tetapi belum ada kueri time travel yang diuji sebagai bagian pengujian resmi.
- **Pemekaran sebelum 2012** belum ada di `dim_wilayah` (langkah 04), sehingga kueri as-of pada deret lama provinsi hasil pemekaran lama belum menandai ketidaksebandingannya.
- **Gudang berjalan di satu simpul** (Mac, Colima 4 vCPU 8 GiB). Pemasangan di instance Lightsail yang direncanakan pada langkah 06 belum dilakukan.
- **Kode yang dirujuk tersalin di [`code/`](../../code/README.md)** dari repositori penelitian Ardika pada commit `dcaa55e` (22 Oktober 2026), termasuk jalur berkasnya yang disebut di atas.
