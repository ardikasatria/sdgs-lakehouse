# 6. Lampiran

::: {custom-style="Kotak"}
Lampiran ini merangkum keputusan rancangan beserta alternatif yang dipertimbangkan dan alasannya, mencantumkan perintah untuk membangun ulang bukti dari Raw, dan mendaftar berkas bukti per langkah beserta data dan kode yang menjadi dasarnya.
:::

## 6.1 Keputusan rancangan dan alasannya

**Tabel 6.1.** Keputusan rancangan pokok, alternatif yang dipertimbangkan, alasan, dan langkah yang terkait. Setiap keputusan tercatat bertanggal pada dokumen rencana kerja atau catatan rencana uji di repositori penelitian.

| Keputusan | Alternatif yang dipertimbangkan | Alasan | Langkah |
| --- | --- | --- | --- |
| Model operasional federasi (data mesh) dengan aturan global yang ditegakkan pusat | model terpusat; model tereplikasi | lebih dari sepuluh produsen dengan pengetahuan domain berbeda membuat satu tim pusat menjadi hambatan, sedangkan kode wilayah, indikator, dan satuan harus sama di semua pilar agar level lintas tujuan dapat dibentuk | 01, 03 |
| Pemisahan tata kelola data dari tata kelola TI | satu tatanan untuk keduanya | tata kelola data memutuskan kelas tayang, aturan rekonsiliasi, toleransi, dan retensi; tata kelola TI memutuskan ukuran server, cadangan, versi Iceberg dan Trino, serta akses SSH | 01, 02 |
| Aturan rekonsiliasi dan ambang kualitas di-commit sebelum data dinilai | menetapkan ambang setelah melihat hasil | hasil yang buruk tidak dapat mengubah ambang; commit `89e0387` mendahului penilaian pertama | 02, 08 |
| Pengetahuan domain disimpan di kontrak, metadata, dan uji yang dibangkitkan dari YAML | dokumen panduan yang dibaca pemilik domain | siklus semester membuat pengisi peran domain berganti; aturan yang dapat dieksekusi bertahan lebih lama daripada dokumen | 03, 05 |
| Setiap sel Bronze berakhir di tepat satu dari lima tempat, dengan karantina beralasan | membuang baris yang gagal dipetakan | identitas hitungan sel diuji per tabel sehingga tidak ada nilai yang hilang tanpa jejak; kode wilayah ambigu (`ID-AC`) dikarantina, bukan ditebak | 07, 08 |
| Raw disimpan selamanya; payload global yang hanya diekstrak disimpan sebagai sha256, ukuran, dan URL | mengunduh ulang bila perlu; menyimpan semua payload utuh | produsen menimpa nilai lama di kanal daring sehingga Raw menjadi satu-satunya bukti angka yang pernah terbit; payload 2,63 GB dapat diunduh ulang dan diverifikasi dari manifest | 06 |
| Pemrosesan streaming dengan Python, tanpa Spark | Spark untuk arsip WDI dan korpus berita | Silver hanya sekitar 1,5 juta baris; pada window gudang Spark lokal lebih cepat sekitar 0,8 s dari job 207 s, dan pada berita Python satu inti (91–139 MB/s) sudah 8–24 kali laju jaringan (5,7–11,6 MB/s) | 10 |
| Ambang SLA per lapis ditulis lebih dulu, lalu diuji dari stack kosong | mengukur lalu menetapkan ambang | 45 dari 46 pemeriksaan lulus; kegagalan API tanpa gzip dicatat dan ambangnya tidak diubah | 10 |
| Dimensi wilayah tipe 2 dengan versi yang ditutup, bukan dihapus | kode wilayah tunggal terkini | pemekaran 2012 dan 2022 membuat Papua 2021 dan Papua 2023 bukan wilayah yang sama; deret lintas pemekaran ditandai tidak sebanding | 04 |
| Resolver menimbulkan galat `KodeAmbigu` bila periode tidak diberikan | memilih kode yang paling mungkin | kode Kemendagri Papua Barat Daya sama dengan Papua Barat pada periode bridging 2023–2024, sehingga tebakan dapat salah | 04 |
| Repositori metadata versi ringan (DCAT, dbt docs, katalog Iceberg REST) | OpenMetadata | OpenMetadata memerlukan sekitar 40 GiB RAM dan tidak muat pada node 16 GB; batasan variabel unit membolehkan repositori di alat lain | 05 |
| Nilai negatif emisi SIGN-SMART tidak dikoreksi | mengoreksi data agar lolos validitas | emisi bersih kehutanan sah bernilai negatif karena serapan; yang belum membedakannya adalah kerangka validitas, dan perbaikannya dicatat untuk praregistrasi berikutnya | 08 |
| Skema bintang bitemporal: waktu rilis untuk query as-of, waktu catat untuk time travel | satu kolom waktu | angka yang benar pada hari terbitnya (TPT 5,28 %) dan nilai terkini (5,23 %) harus sama-sama tersimpan dan dapat dipanggil | 09 |
| Nilai pilihan dihitung aturan prioritas tercatat, bukan skor kepercayaan beku | fusi data dengan skor kepercayaan | semua observasi tetap tersimpan dan alasan pilihan tersaji pada setiap baris; sumber yang tidak boleh tayang dikeluarkan sebelum pemilihan | 09 |
| Sidik Gold dihitung dari baris terurut melalui Trino | hash berkas Parquet atau snapshot Iceberg | sidik tidak bergantung pada bita Parquet maupun snapshot, sehingga empat jalan dari nol dapat dibandingkan langsung | 09 |
| Pseudonim peserta dijalankan server dengan HMAC bergaram, ekspor ditolak bila garam belum diset | pseudonim saat mengolah berkas oleh peneliti | janji lembar persetujuan ditepati oleh kode yang berjalan di produksi, bukan oleh kehati-hatian perorangan; tidak ada kunci bawaan di kode | 11 |
| Teks penuh berita dibuang; yang disimpan tupel angka dan cuplikan paling banyak dua kalimat | menyimpan artikel utuh | UU 28/2014 tidak melindungi angka; kolom nama dan kutipan GDELT tidak pernah dipilih, dan tupel klaim tidak mempunyai bidang nama | 03, 11 |

## 6.2 Perintah untuk verifikasi ulang

Perintah berikut dijalankan dari akar repositori penelitian Ardika di Mac dengan venv Python dan Colima aktif. Salinan kode yang sama tersedia di folder `code/` repositori portofolio (commit `dcaa55e`), dan target `make` yang disebut adalah target Makefile repositori penelitian.

```bash
# data rujukan dan ujinya (langkah 04)
make m1-referensi
make m1-test

# Bronze dari Raw tanpa jaringan, Silver, rekonsiliasi, kualitas (langkah 07, 08)
make m3-bronze m3-silver m3-rekonsiliasi m3-kualitas

# stack gudang lalu job penuh dari Raw (langkah 09)
make m4-naik
make m4-jalan

# sidik Gold dan lineage (langkah 05, 09)
make m4-sidik
make m4-lineage

# uji SLA antarlapis terhadap config/sla/lapis.yaml (langkah 10)
make m4-uji-sla

# bangun ulang TPB-KG dengan validasi SHACL (uji graf)
make m5-kg
```

Verifikasi singkat tanpa membangun ulang gudang dapat dilakukan dengan `make m1-test` (beberapa detik), lalu membandingkan sidik `657df68e…` pada `data/gudang/m4_sidik_gold.json` dan `data/produk/uji-keterulangan.json` di repositori portofolio, serta membuka halaman Liga Lakehouse di `sd.itera.ac.id` sebagai produk yang berjalan. Di repositori portofolio sendiri, `make periksa` memastikan berkas `data/` masih sama dengan sidik di `data/SIDIK.txt`.

## 6.3 Daftar berkas bukti, data, dan kode per langkah

**Tabel 6.2.** Folder bukti, berkas data, dan kode yang menjadi dasarnya. Jalur `bukti/`, `data/`, dan `code/` relatif terhadap akar repositori portofolio.

| Langkah | Unit | Berkas data di `data/` | Kode di `code/` |
| --- | --- | --- | --- |
| `bukti/01-kebutuhan-data/` | J.62DMS00.001.1 | `serkom/inventaris-aset-data.csv` | `config/mesh/` |
| `bukti/02-rencana-manajemen-data/` | J.62DMS00.002.1 | `serkom/raci.csv`, `gudang/m4_sidik_gold.json`, `gudang/m4_lineage.json`, `produk/uji-keterulangan.json` | `config/mesh/`, `tests/unit/test_gudang_kontrak.py` |
| `bukti/03-arsitektur-data/` | J.62DMS00.003.1 | `gudang/m4_sidik_gold.json`, `gudang/m4_lineage.json`, `uji/banding-spark.json` | `config/mesh/`, `src/sdg_gudang/gudang/kontrak.py` |
| `bukti/04-rujukan-dan-master/` | J.62DMS00.008.1 | `gudang/m4_sidik_gold.json`, `gudang/m5_kg_ringkasan.json` | `src/sdg_gudang/referensi.py`, `config/referensi/`, `tests/unit/test_sdg_gudang_referensi.py` |
| `bukti/05-metadata/` | J.62DMS00.009.1 | `gudang/m4_lineage.json`, `gudang/m5_kg_ringkasan.json`, `produk/uji-graf.json`, `produk/uji-keterikatan.json` | `src/sdg_gudang/gudang/kontrak.py`, `kg.py`, `lineage.py` |
| `bukti/06-penyimpanan/` | J.62DMS00.005.1 | `gudang/volume.json`, `produk/uji-keterulangan.json`, `produk/latensi-produksi-*.json` | `src/sdg_gudang/akuisisi/inti.py`, `infra/gudang/compose.yml` |
| `bukti/07-integrasi/` | J.62DMS00.004.1 | `gudang/silver_ringkasan.json`, `gudang/m3_rekonsiliasi_ringkasan.json`, `gudang/m3_kualitas.json`, `gudang/m4_lineage.json`, `produk/uji-integrasi.json` | `src/sdg_gudang/silver/`, `config/rekonsiliasi/`, `src/sdg_gudang/gudang/lineage.py` |
| `bukti/08-kualitas/` | J.62DMS00.012.1 | `serkom/kualitas-per-sumber.csv`, `serkom/prioritas-perbaikan.csv`, `gudang/m3_kualitas.json`, `gudang/silver_ringkasan.json`, `produk/uji-integrasi.json` | `src/sdg_gudang/silver/kualitas.py`, `tests/unit/test_gudang_silver_inti.py`, `test_gudang_rekonsiliasi.py` |
| `bukti/09-gudang-data/` | J.62DMS00.014.1 | `gudang/m4_sidik_gold.json`, `produk/sidik-gold.json`, `produk/uji-kompilasi.json`, `produk/uji-keterulangan.json` | `dbt/gudang_sdg/`, `src/sdg_gudang/gudang/muat.py`, `orkestrasi.py`, `sidik.py`, `infra/gudang/` |
| `bukti/10-big-data/` | J.62DMS00.007.1 | `gudang/volume.json`, `uji/uji-sla.json`, `uji/uji-sla-api.json`, `uji/uji-sla-gdelt.json`, `uji/banding-spark.json`, `produk/latensi-produksi-*.json` | `src/sdg_gudang/akuisisi/konektor/`, `config/sla/lapis.yaml`, `src/sdg_gudang/gudang/uji_sla.py`, `eval/serkom/banding_spark.py` |
| `bukti/11-data-pribadi/` | J.62PDP00.011.1 | `serkom/raci.csv` | `src/sdg_gudang/akuisisi/konektor/berita_umum.py`, `tests/unit/test_gudang_konektor_berita.py`; di repositori DSW (privat): modul survei, masuk dengan Google, ekspor penelitian |

Peta salinan `data/` ke berkas asalnya ada di `data/asal.tsv`, dan sidik sha256 setiap berkas di `data/SIDIK.txt`; sidik setiap berkas kode di `code/SIDIK.txt`. Isian FR.APL.01 dan asesmen mandiri FR.APL.02 berada di `berkas-asesmen/`, yang tidak ikut dipublikasikan karena memuat data pribadi asesi.
