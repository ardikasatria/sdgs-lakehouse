# 07. Integrasi data

**Unit:** J.62DMS00.004.1 Merencanakan Integrasi Data

**Pertanyaan yang dijawab:** Bagaimana sebelas sumber digabung tanpa ada angka yang hilang atau ditebak?

**Yang saya kerjakan:** Saya menetapkan bahwa integrasi tidak menggabungkan nilai di Silver: setiap angka yang pernah terbit dari setiap sumber tetap tersimpan dengan kunci bersama, dan penggabungan hanya terjadi saat memilih `nilai_pilihan` di Gold dengan alasan yang ikut tersaji. Aturan pemetaan, kelas sebab selisih, dan prioritas pemilihan nilai saya bekukan dalam praregistrasi yang di-commit sebelum data dibandingkan, lalu 11 sumber dari 9 keluarga dimuat dan direkonsiliasi: 1.376.297 pasangan rilis × rilis dan 1.276 pasangan sumber × sumber, dengan 40,6 % selisih antarsumber terjelaskan oleh aturan yang ditetapkan lebih dulu. Baris yang gagal dipetakan masuk karantina dengan kode alasan, dan setiap baris membawa sha256 berkas Raw asalnya sehingga satu angka di data product dapat ditelusuri ke berkas unduhannya.

| Elemen | Yang saya kerjakan | Bukti | Jenis | Status |
| --- | --- | --- | --- | --- |
| 1. Mendefinisikan kebutuhan akan integrasi data | merumuskan kebutuhan konsumen (satu nilai pilihan, semua nilai tetap dapat dipanggil), kunci relasi antardata, tabel padanan 105 seri dalam 36 konsep, dan tiga kelompok business rule yang dibekukan sebelum perbandingan | `data/gudang/m3_rekonsiliasi_ringkasan.json` (sha256 dan commit berkas beku); praregistrasi dan `config/rekonsiliasi/` di repositori penelitian Ardika | T, TL | lengkap |
| 2. Melakukan data discovery | mengatalogkan 12 sumber, memprofilkan kualitas tujuh dimensi per sumber sebagai syarat integrasi, dan mengukur konsistensi antarsumber lewat rekonsiliasi | `data/gudang/m3_kualitas.json`, `data/produk/uji-integrasi.json` | TL | lengkap |
| 3. Mendokumentasikan data lineage | mencatat lineage pada tingkat baris (sha256 Raw di setiap baris) dan tingkat aset (166 simpul, 320 sisi), menguji ekspor ke paket level identik byte, dan mendokumentasikan lima usulan perbaikan aliran | `data/gudang/m4_lineage.json`, `data/produk/uji-keterulangan.json` | TL, L | lengkap, dua usulan belum diterapkan |
| 4. Membuat profil data | menguji identitas lima tempat untuk setiap sel Bronze pada 54 tabel, dan menerapkan kelas lisensi serta pagar privasi secara mekanis | `data/gudang/silver_ringkasan.json`; `src/sdg_gudang/silver/` di repositori penelitian Ardika | TL, L | lengkap |

Jenis bukti: **L** langsung (artefak yang berjalan), **TL** tidak langsung (hasil terukur, laporan), **T** tambahan (dokumen tata kelola, surat).

## Kedudukan langkah ini

Bukti ini berasal dari fase M2 sampai M4 (akuisisi, Silver, gudang) dan uji integrasi Tahap II, yang semuanya sudah berjalan dan ter-commit sebelum dokumen bukti ditulis pada 24 Oktober 2026. Keadaan acuannya adalah Gold bersidik `657df68e…` dari jalan C dan D di Mac pada 21 Oktober 2026, yang juga menjadi dasar kelima pengujian Tahap II. Gold untuk Laga (`1b8c95e3…`, keputusan 22 Oktober) hanya mengubah kelas lisensi empat sumber dan tidak mengubah aturan integrasi. Elemen dan KUK mengikuti teks resmi lampiran Kepmenaker 268/2020, yang dicocokkan pada 24 Oktober.

## Elemen 1. Kebutuhan integrasi data

**KUK 1.1 Kebutuhan integrasi sesuai kebutuhan organisasi.** Satu indikator SDG Indonesia dapat terbit di BPS, basis data SDG PBB, WDI, ILOSTAT atau WHO, dan kementerian sektoral, dengan nilai yang tidak selalu sama. Konsumen organisasi (paket level Liga Lakehouse, TPB-KG, Bravais, dasbor) memerlukan satu nilai per indikator, wilayah, dan periode, tetapi tetap harus dapat menunjukkan semua nilai yang pernah terbit beserta sumbernya. Dua tuntutan itu tidak dapat dipenuhi bila integrasi meleburkan nilai lebih awal. Karena itu Silver menyimpan semua nilai berdampingan, dan penggabungan hanya terjadi di Gold saat `nilai_pilihan` dipilih, dengan `alasan_pilihan` yang ikut sampai ke konsumen.

**KUK 1.2 Relasi antardata.** Setiap observasi Silver dikunci oleh (konsep, wilayah, periode, rincian) ditambah (sumber, rilis, seri). Relasi lintas sumber dibentuk oleh dua hal: data rujukan dari langkah 04 (kode wilayah BPS dengan versi tipe 2, kode indikator TPB ke kode global, satuan kanonik dengan faktor konversi) dan tabel padanan seri. Seri dari keluarga berbeda dianggap konsep yang sama hanya bila metadata sumbernya menyatakan definisi yang sama atau perbedaan yang tercatat pada kolom `hubungan`, bukan karena namanya mirip. Hasilnya 105 seri dalam 36 konsep; 32 konsep di antaranya membentuk pasangan sumber × sumber, dan 15 konsep dimuat dari tiga keluarga sekaligus.

**KUK 1.3 Business rule.** Tiga kelompok aturan ditulis sebagai praregistrasi dan di-commit sebelum data dibandingkan. Sha256 dan commit ketiga berkas beku tercatat di `m3_rekonsiliasi_ringkasan.json`, sehingga dapat dibuktikan bahwa aturan tidak berubah setelah hasilnya terlihat.

| Aturan | Isi | Berkas |
| --- | --- | --- |
| S01–S09 | pemetaan Bronze ke Silver: kode wilayah, periode, satuan, rincian, penyatuan kunci ganda bernilai sama (S08), agregasi kabupaten/kota ke provinsi (S09) | praregistrasi M3 Bagian 3, Tambahan 1 (commit `3f9cf7b`) |
| K0a–K9 | 11 kelas sebab selisih: sama, pembulatan, satuan atau skala, periode acuan, granularitas, definisi, metodologi, vintage, tidak terjelaskan | `aturan_rekonsiliasi.csv` (commit `89e0387`) |
| prioritas nilai pilihan | BPS, lalu sektoral nasional, kustodian internasional resmi, Bank Dunia, estimasi; calon yang tidak boleh tayang dikeluarkan sebelum memilih | `dbt/gudang_sdg/models/gold/nilai_pilihan*.sql` |

Aturan S09 menunjukkan bagaimana aturan dibuat sebelum dijalankan: ukuran jumlah dijumlahkan, persentase dihitung ulang berbobot penyebut, ambang cakupan 80 % untuk SIPSN, dan BNPB tanpa ambang karena kabupaten yang tidak tercantum berarti tidak ada kejadian. Aturan ini ditambahkan ke praregistrasi sebagai Tambahan 1, lalu menghasilkan 7.502 sel provinsi baru (BNPB 7.176, SIPSN 326).

## Elemen 2. Data discovery

**KUK 2.1 Sumber data diidentifikasi.** Dua belas sumber (sebelas statistik dan berita) dikatalogkan dengan tingkat wilayah, jumlah rilis, jenis bukti tanggal rilis, dan kelas lisensi; registri `dim_rilis` memuat 2.662 rilis data statistik (langkah 06). Uji integrasi Tahap II memuat 11 sumber dari 9 keluarga ke gudang: 1.486.490 observasi, 1.126 konsep, 105 dari 109 indikator katalog berdata, dan ke-17 tujuan berdata.

**KUK 2.2 Kualitas data dianalisis sesuai standar integrasi.** Profil tujuh dimensi per sumber (langkah 08) dipakai sebagai syarat integrasi: sumber dengan keterpetakan rendah tidak dipaksa masuk, tetapi akar masalahnya dicatat dan diselesaikan dengan aturan, bukan dengan tebakan.

| Sumber | Keterpetakan | Akar masalah | Penyelesaian |
| --- | ---: | --- | --- |
| SIPSN | 0,155 | data tingkat kabupaten/kota, bukan provinsi | aturan S09 agregasi ke provinsi dengan ambang cakupan 80 % |
| SIGN-SMART | 0,870 | kode `ID-AC` dipakai untuk Aceh dan empat provinsi Papua baru | 650 sel dikarantina, tidak ditebak |
| BNPB, KKP, UNSD, WHO | 0,995–0,999 | sisa kecil: kode tak dikenal, ukuran tanpa nama | karantina dengan alasan |
| BPS, ILOSTAT, WDI, arsip WDI | 1,000 | – | – |

Rekonsiliasi kemudian mengukur konsistensi antarsumber pada dua tingkat (`m3_rekonsiliasi_ringkasan.json`, `uji-integrasi.json`).

| Tingkat | Pasangan | Sama | Pembulatan | Selisih | Selisih terjelaskan |
| --- | ---: | ---: | ---: | ---: | --- |
| Rilis × rilis (dalam satu keluarga) | 1.376.297 | 1.242.574 (90,3 %) | 48.874 (3,6 %) | 84.849 (6,2 %) | seluruhnya; 81.090 di antaranya kelas vintage |
| Sumber × sumber (antarkeluarga) | 1.276 | 213 | 366 | 697 | 283 (0,406; Wilson 95 % 0,370–0,443): definisi 175, periode acuan 57, metodologi 49, satuan 2 |

Dua angka itu dibaca berbeda. Pada tingkat rilis × rilis, hampir semua selisih adalah revisi antarvintage dari produsen yang sama, dan itulah alasan gudang ini menyimpan setiap rilis. Pada tingkat sumber × sumber, 414 selisih belum terjelaskan oleh aturan yang dibekukan; angka 0,406 sengaja tidak dinaikkan dengan menambah kelas setelah data dilihat.

## Elemen 3. Data lineage

**KUK 3.1 Aliran data dianalisis.** Lineage dicatat pada dua tingkat dan diteruskan sampai konsumen.

- **Baris.** Setiap baris Silver membawa `_sha256_raw` dan `_berkas_raw` dari manifest Raw, dan kolom ini diteruskan ke `fakta_observasi` sebagai `sha256_raw` dan `berkas_raw`. Satu angka di data product dapat ditelusuri ke berkas unduhan aslinya tanpa melewati sistem lain.
- **Aset.** `m4_lineage.json` menyusun graf 166 simpul dan 320 sisi: manifest Raw, tabel Bronze, Silver, model dbt `gold.*`, lalu data product `dp.*`. Kelengkapan lineage 12 dari 12 tabel data product, sama dengan ambang praregistrasi 1,00.
- **Ke konsumen.** Jembatan `src/sdg_game/jembatan.py` mengekspor `gudang_tayang.csv`, `gudang_pasangan.csv`, dan berkas keterkaitan ke masukan paket v4. Uji keterulangan membuktikan keempat ekspor ini identik byte pada dua rebuild dari Raw (`uji-keterulangan.json`, `ekspor_sama_dengan_commit`), sehingga rantai Raw, Gold, paket level dapat diulang sampai bita.

**KUK 3.2 Usulan perbaikan aliran data.**

| Temuan pada aliran | Usulan atau perbaikan | Status |
| --- | --- | --- |
| rilis tanpa tanggal rilis terurut sebagai rilis terbaru (insiden pada langkah 08) | tanggal efektif = tanggal rilis, lalu batas atas, lalu snapshot pertama; dua uji dbt kewajaran tanggal | diterapkan, commit `06cf95e` |
| lineage berhenti di data product; paket level di repositori lain | sha256 masukan jembatan dicatat di manifes paket dan diuji identik pada uji keterulangan | diterapkan |
| OpenMetadata tidak muat di simpul 16 GB | repositori versi ringan (langkah 05); panen OpenMetadata bila tersedia simpul lebih besar | usulan |
| vintage antarkustodian (WDI × WHO menyalin ronde UN IGME berbeda) tidak punya kelas sebab | kelas sebab baru untuk praregistrasi berikutnya, tidak diterapkan surut | usulan |
| ekspor data peserta Laga memuat `user_id` | pseudonim bergaram `hash_peserta` (langkah 11) | diterapkan di kode 24 Oktober, pemasangan di produksi lihat langkah 11 |

## Elemen 4. Profil data

**KUK 4.1 Isi dan struktur data dianalisis.** Setiap sel kandidat dari Bronze berakhir di tepat satu dari lima tempat, dan identitas berikut diuji pada setiap tabel sumber:

```
n_sel = n_Silver + n_karantina + n_kosong + n_di_luar_tingkat + n_gabung_S08
```

`silver_ringkasan.json` mencatat nasib sel untuk 54 tabel sumber beserta alasan per kategori. Contohnya tabel `bnpb/kabupaten`: 9.966 baris Bronze, 98.622 sel di luar tingkat provinsi (98.566 sel kabupaten/kota, 56 baris kepala), 135 sel Silver langsung, dan 7.176 sel agregat provinsi hasil S09. Seluruh 1.487.727 baris Silver dan karantina membawa sha256 berkas Raw yang cocok dengan manifest. Alasan karantina tercatat per baris, misalnya `ukuran_tidak_bernama` pada 84 sel BNPB dan kode ambigu pada 650 sel SIGN-SMART.

**KUK 4.2 Faktor security dan privacy.** Kelas lisensi melekat pada sumber (`dim_sumber.kelas_lisensi`, `boleh_tayang`) dan diuji dbt pada setiap jalan. Pada jalan acuan, dari 109.289 sel pilihan hanya 81.249 yang boleh tayang; 25,7 % sisanya dikeluarkan secara mekanis, bukan lewat penyaringan tangan. Sejak 22 Oktober 2026 saya memutuskan SDG PBB, SIPSN, SIGN-SMART, dan KKP masuk kelas A dengan atribusi wajib; aturan integrasinya tetap, hanya seed lisensi yang berubah. Data statistik resmi tidak memuat data pribadi. Alur berita yang dapat membawa nama orang diprofilkan dengan pagar di kode: kolom nama dan kutipan GDELT tidak pernah dipilih, teks penuh RSS dibuang, dan panjang kolom Bronze diuji tidak melebihi 600 karakter (langkah 11). Kunci API dan token tidak pernah ditulis ke manifest; pembangun manifest memeriksanya dengan pola rahasia.

## Aspek kritis: ketepatan analisis aliran data sesuai kebutuhan integrasi

Dua sikap menjadi inti aspek kritis ini. Pertama, **tidak membuang**: baris yang gagal dipetakan masuk karantina dengan kode alasan, dan identitas hitungan sel membuktikan tidak ada sel yang hilang di antara Bronze dan Silver. Kedua, **tidak menebak**: kode wilayah yang ambigu (SIGN-SMART `ID-AC`, kode Kemendagri Papua Barat Daya pada periode bridging 2023–2024) ditolak, bukan dipetakan ke tebakan terbaik. Kelas sebab yang baru ditemukan setelah data dilihat, yaitu vintage antarkustodian WDI × WHO, dicatat sebagai usulan untuk praregistrasi berikutnya dan tidak diterapkan surut, supaya angka 0,406 tetap hasil aturan yang ditetapkan sebelum data dilihat.

**Data pendukung** (sudah ada di repositori):

- [`data/gudang/silver_ringkasan.json`](../../data/gudang/silver_ringkasan.json): nasib setiap sel Bronze per tabel sumber (54 tabel) dengan alasan dan sidik observasi.
- [`data/gudang/m3_rekonsiliasi_ringkasan.json`](../../data/gudang/m3_rekonsiliasi_ringkasan.json): sha256 dan commit tiga berkas beku; ringkasan rilis × rilis dan sumber × sumber per pasangan keluarga.
- [`data/gudang/m3_kualitas.json`](../../data/gudang/m3_kualitas.json): keterpetakan, validitas, kelengkapan, ketepatan waktu, dan konsistensi per sumber.
- [`data/gudang/m4_lineage.json`](../../data/gudang/m4_lineage.json): graf lineage dan jalur setiap data product ke berkas Raw.
- [`data/produk/uji-integrasi.json`](../../data/produk/uji-integrasi.json): 11 sumber, 9 keluarga, cakupan konsep dan indikator, kelas sebab selisih, dan pasangan yang kedua sumbernya boleh tayang.

## Catatan terbuka

- **414 dari 697 selisih antarsumber belum terjelaskan.** Dari empat hipotesis praregistrasi, satu terbukti (TPT BPS dan ILOSTAT berselisih pada 19 dari 19 tahun). Kelas sebab vintage antarkustodian baru akan masuk pada praregistrasi berikutnya.
- **Konsistensi hanya diukur pada 32 konsep berpasangan**; 4 konsep hanya punya satu keluarga, dan sumber sektoral (BNPB, SIPSN, SIGN-SMART, KKP) belum punya pembanding antarkeluarga.
- **Satu padanan seri dilewati**: seri triwulanan ILOSTAT `UNE_DEAP_SEX_AGE_RT` (32 observasi) tidak dibandingkan karena periodenya tidak sepadan dengan tahunan.
- **Pseudonim ekspor peserta** diterapkan di kode pada 24 Oktober; keadaan di produksi dicatat pada langkah 11.
- **Kode yang dirujuk tersalin di [`code/`](../../code/README.md)** dari repositori penelitian Ardika pada commit `dcaa55e` (22 Oktober 2026), termasuk jalur berkasnya yang disebut di atas.
