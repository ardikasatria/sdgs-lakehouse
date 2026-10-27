# 08. Kualitas data

**Unit:** J.62DMS00.012.1 Mengelola Kualitas Data

**Pertanyaan yang dijawab:** Bagaimana masalah kualitas ditemukan, diurutkan, diperbaiki, dan dipantau?

**Yang saya kerjakan:** Saya menyusun kerangka tujuh dimensi kualitas dengan parameter, standar minimum, dan alasan yang menunjuk pemakainya, lalu membekukannya di git sebelum data multisumber dinilai, sehingga hasil yang buruk tidak dapat mengubah ambang. Penilaian awal atas 1.602.998 baris Bronze dari 12 sumber menemukan lima pelanggaran di empat sumber, masing-masing dengan akar masalah yang dapat ditunjuk, dan masalah diurutkan menurut baris terdampak dikali bobot dampak bisnis. Perbaikan ditempatkan di aturan dan kode, bukan di data: pola satuan diperbaiki di hulu, nilai sumber tidak pernah diubah, hasil sebelum perbaikan diarsip, dan uji dbt baru ditambahkan setiap kali insiden menunjukkan celah yang tidak tertangkap uji lama.

| Elemen | Yang saya kerjakan | Bukti | Jenis | Status |
| --- | --- | --- | --- | --- |
| 1. Menyusun kerangka kualitas data | menetapkan tujuh dimensi dengan parameter, standar minimum, dan alasan per pemakai; membekukannya pada commit `89e0387` sebelum penilaian | tabel pada Elemen 1; `standar` di `data/gudang/m3_kualitas.json` | T, TL | lengkap |
| 2. Menilai kualitas awal dan menemukan akar masalah | menilai 12 sumber pada tujuh dimensi, menelusuri akar setiap pelanggaran sampai ke payload atau ke kerangka | `data/serkom/kualitas-per-sumber.csv`, `data/gudang/m3_kualitas.json` | TL | lengkap |
| 3. Menetapkan prioritas perbaikan | memberi skor setiap masalah (baris × bobot dampak), menetapkan tindakan dan pemilik per masalah | `data/serkom/prioritas-perbaikan.csv`; tabel pada Elemen 3 | TL, T | lengkap, dua tindakan menunggu jawaban produsen |
| 4. Menjalankan operasi koreksi, mengukur, dan memantau | koreksi di aturan, ukur ulang dari Raw, pantau lewat 139 node dbt di setiap jalan; lima insiden ditangani dengan pola yang sama | `data/gudang/m4_sidik_gold.json` (139 node lulus); `data/gudang/silver_ringkasan.json`; `src/sdg_gudang/silver/kualitas.py` di DSIC-SDG | L, TL | lengkap, kode belum disalin ke `code/` |

Jenis bukti: **L** langsung (artefak yang berjalan), **TL** tidak langsung (hasil terukur, laporan), **T** tambahan (dokumen tata kelola, surat).

## Kedudukan langkah ini

Kerangka kualitas ditetapkan pada fase M3 (Silver, rekonsiliasi, dan kualitas) pada 20 Oktober 2026, dan pengukurannya dijalankan ulang pada rebuild 21 Oktober yang menjadi acuan semua angka di `data/`. Elemen dan KUK mengikuti teks resmi lampiran Kepmenaker 268/2020 yang dicocokkan 24 Oktober 2026. Aspek kritis resminya adalah ketepatan mengidentifikasi parameter kualitas sesuai kebutuhan pengguna, dan karena itu setiap parameter pada Elemen 1 diberi alasan yang menunjuk pemakai: level game, rekonsiliasi, atau ketertelusuran angka.

| KUK resmi | Bunyi ringkas | Tempat bukti |
| --- | --- | --- |
| 1.1 | parameter kualitas diidentifikasi sesuai kebutuhan pengguna | Elemen 1, kolom Parameter dan Alasan |
| 1.2 | strategi pencapaian standar minimal didefinisikan | Elemen 1, kolom Standar minimum; aturan S01–S08 menolak ke karantina |
| 1.3 | cakupan penilaian awal didefinisikan | Elemen 1 (tujuh dimensi); Elemen 2 (1.602.998 baris Bronze, 12 sumber) |
| 2.1 | masalah kualitas prioritas diidentifikasi | Elemen 2, tabel sumber dan dimensi gagal |
| 2.2 | analisis akar penyebab | Elemen 2, kolom Akar masalah |
| 3.1 | prioritas tindakan berdasarkan dampak bisnis | Elemen 3, skor = baris × bobot |
| 3.2 | tindakan pencegahan dan korektif | Elemen 3 kolom Tindakan; Elemen 4 uji dbt baru setelah insiden |
| 3.3 | rencana tindakan dikonfirmasi | Elemen 3 kolom Pemilik (RACI langkah 02); keputusan tercatat bertanggal |
| 4.1 | operasi kualitas dilakukan | Elemen 4; aset Dagster `kualitas` pada setiap jalan `gudang_penuh` |
| 4.2 | kualitas dikoreksi | Elemen 4, pembaruan 20 Oktober (73 satuan, S09) |
| 4.3 | kualitas diukur | `m3_kualitas.json`, `kualitas-per-sumber.csv` |
| 4.4 | kualitas dipantau | Elemen 4; 115 uji data dbt di setiap jalan (139 node), sidik per tabel |

## Elemen 1. Kerangka kualitas data

Kerangka ini dibekukan dan di-commit sebelum data multisumber dinilai (commit `89e0387`, 20 Oktober 2026). Lima standar yang berupa ambang tersimpan di `m3_kualitas.json` sebagai bidang `standar`, sehingga pengukur membaca ambang dari berkas yang sama yang dibekukan.

| Dimensi | Parameter | Standar minimum | Alasan (pemakai) |
| --- | --- | --- | --- |
| Keterpetakan | Silver ÷ (Silver + karantina) per tabel | ≥ 0,95 | data yang tidak dapat dipetakan ke kunci kanonik tidak dapat dipakai level atau rekonsiliasi |
| Keunikan | kunci ganda dengan nilai berbeda dalam satu rilis | 0 | satu kunci yang bernilai dua membuat jawaban level tidak tunggal |
| Validitas | nilai di dalam domain satuan (proporsi 0–100; jumlah, massa, luas tidak negatif) | ≥ 0,99 | menangkap salah satuan dan salah urai sebelum masuk rekonsiliasi |
| Kelengkapan | provinsi berdata ÷ provinsi yang berlaku as-of tahun periode | ≥ 0,90 | level Peta dan Peringkat memerlukan cakupan provinsi |
| Ketepatan waktu | median jeda akhir periode ke tanggal rilis; proporsi rilis dengan bukti tanggal lemah | dilaporkan | bahan kebijakan kesegaran (SLA) pada langkah 10 |
| Konsistensi | proporsi pasangan sumber × sumber yang sama atau berbeda pembulatan | dilaporkan | diukur oleh rekonsiliasi pada langkah 07 |
| Keterlacakan | baris dengan `_sha256_raw` yang cocok dengan manifest | 1,00 | setiap angka harus dapat ditelusuri ke berkas sumbernya |

Kualitas ditegakkan di dua tempat. Aturan pemetaan S01–S08 menolak data yang tidak memenuhi syarat ke karantina dengan kode alasan; tidak ada yang dibuang diam-diam, dan identitas hitungan per tabel diuji (langkah 07). Pengukur kualitas kemudian menghitung ketujuh dimensi atas Silver dan karantina.

## Elemen 2. Penilaian kualitas awal dan akar masalah

Penilaian awal mencakup 1.602.998 baris Bronze dari 12 sumber. Tujuh dari sebelas profil sumber memenuhi semua standar; lima pelanggaran ada di empat sumber. Keterlacakan bernilai 1,00 pada semua sumber: 1.487.727 dari 1.487.727 baris cocok dengan manifest, tanpa berkas yang gagal.

| Sumber | Dimensi gagal | Nilai | Akar masalah |
| --- | --- | ---: | --- |
| SIGN-SMART (emisi GRK provinsi) | keterpetakan | 0,870 | payload memberi kode ISO `ID-AC` pada lima entri setiap tahun per sektor: Aceh dan empat provinsi Papua hasil pemekaran 2022; kodenya tidak dapat dibedakan, sehingga 650 sel dikarantina. Sumber belum memperbarui tabel kode ISO setelah pemekaran |
| SIGN-SMART | validitas | 0,880 | emisi bersih sektor kehutanan bernilai negatif (serapan); sah secara substansi, tetapi melanggar aturan "massa tidak negatif". Akar masalahnya ada pada kerangka, yang tidak membedakan emisi bersih dari massa biasa |
| SIPSN | keterpetakan | 0,155 | delapan baris akhir ekspor tanpa provinsi berisi 0, 100, atau teks bebas tentang TPA (136 sel dikarantina); penyebut kecil karena data berada di tingkat kabupaten/kota (8.687 sel di luar tingkat) |
| WHO GHO | keunikan | 2 | `NUTRITION_WH_2` tahun 2008, laki-laki 24–35 bulan, muncul dua kali dengan nilai 15,7 dan 16,3 tanpa kolom pembeda: duplikat di sumber |
| BNPB | kelengkapan | 0,653 | tabel kejadian hanya memuat provinsi yang terdampak bencana, sehingga ukuran kelengkapan tidak cocok untuk jenis tabel ini (lihat Elemen 4) |

Empat temuan lain lulus standar tetapi tetap ditelusuri akarnya, karena karantina kecil pun harus punya alasan yang dapat dijelaskan.

| Sumber | Sel | Akar masalah |
| --- | ---: | --- |
| BNPB (keterpetakan 0,995) | 84 | berkas 2000 untuk enam provinsi kehilangan nama kolom saat diimpor CKAN; hanya nomor kolom `(3)` sampai `(16)` yang tersisa |
| KKP (keterpetakan 0,997) | 12 | pada `nelayan_per_prov` 2023, kode Kemendagri lama provinsi induk (91, 92) dipakai untuk provinsi pecahan, sehingga kode dan nama menunjuk provinsi berbeda |
| SDG PBB | 336 | nilai batas `<0.5` dan `<5` (FIES berat, bahan bakar bersih) bukan angka; dikarantina sebagai `nilai_batas` |
| BPS (validitas 0,9997) | 9 | persentase bahan bakar memasak 2020 berjumlah 100,01 karena pembulatan komponen; contohnya tersimpan di `contoh_pelanggaran_validitas` |

Dua temuan selama pemetaan diperbaiki di hulu, bukan dikarantina. Pola satuan `dim_satuan` M1 tidak menangkap teks "Rupiah/Jam" pada upah BPS, sehingga 393 sel sempat dikarantina; polanya diperbaiki di `referensi.py`. Pola `gg co2e` memetakan Gg CO2e ke ton CO2e dengan faktor 1, padahal seharusnya 1.000; pola itu dihapus dan konversi dinyatakan per sumber.

## Elemen 3. Prioritas perbaikan

Skor prioritas = baris terdampak × bobot dampak. Bobotnya 3 bila seri dipakai paket level, 2 bila terpetakan ke katalog TPB, dan 1 selain itu, sehingga masalah pada data yang dilihat pemain naik lebih dulu. Daftar lengkap 47 masalah ada di `prioritas-perbaikan.csv`; lima teratas setelah masalah sejenis digabung:

| Urutan | Masalah | Skor | Tindakan | Pemilik |
| --- | --- | ---: | --- | --- |
| 1 | SIGN-SMART `ID-AC` ambigu | 1.300 | tanyakan tabel kode ke KLH/BPLH (sudah masuk draf surat izin KLH); sementara itu jangan menebak dari urutan | steward Pilar Lingkungan |
| 2 | SIGN-SMART emisi bersih negatif | 378 | ubah kerangka validitas untuk `massa_setara` pada praregistrasi berikutnya; nilai tidak dikoreksi | steward platform |
| 3 | SDG PBB nilai batas `<0.5`, `<5` | 336 | pertahankan di karantina; sajikan sebagai teks "di bawah 0,5" bila level memerlukannya | steward Pilar Sosial |
| 4 | SIPSN baris tanpa wilayah dan data tingkat kabupaten/kota | 136 | aturan agregasi kabupaten ke provinsi (S09); buang baris tanpa wilayah dengan alasan tercatat | steward Pilar Lingkungan |
| 5 | BNPB kolom tanpa nama (2000) | 84 | minta berkas asli XLSX lewat unduh tangan; peta kolom dari berkas 2001 hanya petunjuk, bukan bukti | steward Pilar Lingkungan |

## Elemen 4. Operasi koreksi, pengukuran, dan pemantauan

**Koreksi.** Koreksi dilakukan di aturan, bukan di data: pola satuan diperbaiki di `dp_referensi`, nilai sumber tidak diubah, dan setiap koreksi tercatat sebagai commit. Pembaruan 20 Oktober 2026 menerapkan tiga koreksi.

- **Satuan di hulu.** 73 satuan didaftarkan di `dp_referensi` dan 74 id lokal `x_` diberi alias, sehingga observasi bersatuan jumlah dari sumber internasional ikut uji validitas tanpa pelanggaran baru.
- **Agregasi S09.** Prioritas 4 ditangani lewat agregasi kabupaten/kota ke provinsi dengan ambang cakupan 80 %. Kelengkapan provinsi SIPSN kini 0,953, dan 16 sel fasilitas di empat provinsi Papua dikarantina sebagai `cakupan_agregasi_kurang` (cakupan 50–71 %).
- **Temuan baru dari agregasi.** Pada 616 dari 10.466 kunci BNPB (6 %), tabel provinsi resmi tidak sama dengan jumlah tabel kabupatennya; 610 di antaranya terklasifikasi granularitas pada rekonsiliasi.

**Ukur.** `make m3-bronze m3-silver m3-kualitas` menghitung ulang semua ukuran dari Raw dalam kurang dari sepuluh menit tanpa jaringan. Hasilnya `m3_kualitas.json` (ukuran per sumber per dimensi, dibangun 21 Oktober 2026) dan `kualitas-per-sumber.csv` (satu baris per sumber per dimensi beserta status memenuhi standar).

**Pantau.** `silver_ringkasan.json` menyimpan sidik isi per tabel Silver, dan setiap jalan job `gudang_penuh` menjalankan 139 node dbt, 115 di antaranya uji data; uji yang gagal menghentikan job. Pada rebuild acuan 21 Oktober seluruh 139 node lulus (`m4_sidik_gold.json`).

**Insiden sebagai bagian operasi kualitas.** Lima insiden terjadi selama fase gudang dan graf, dan semuanya ditangani dengan pola yang sama: akar dicari, perbaikan ditempatkan di aturan atau kode, uji ditambahkan, hasil sebelum perbaikan disimpan. Yang paling menentukan adalah insiden tanggal rilis: satu rilis PBB tanpa tanggal rilis terurut sebagai rilis terbaru karena aturan pengganti tanggal hanya mengenal tanggal snapshot, padahal registri mencatat batas atas 29 Maret 2019. Akibatnya 3.771 pasangan rilis salah urut dan 3.099 nilai pilihan terdampak. Kesalahan ini lolos dari 137 uji kontrak yang lulus sebelum perbaikan, karena kontrak memeriksa skema, kunci, dan rujukan, bukan kewajaran urutan waktu; ia baru terlihat saat data divisualisasikan. Perbaikannya (commit `06cf95e`) menetapkan tanggal efektif = tanggal rilis, lalu batas atas, lalu snapshot pertama, dan menambahkan uji unit serta dua uji dbt kewajaran tanggal. Proporsi selisih terjelaskan bergeser dari 0,383 ke 0,406, dan angka sebelum perbaikan tetap dilaporkan. Tiga insiden lain: Trino terbunuh OOM saat membangun `fakta_observasi` (heap JVM dibatasi 65 % dalam kontainer 6 GB), rebuild pertama memberi sidik `nilai_pilihan` berbeda karena satu konsep menyatukan seri berbeda ukuran (konsep diganti, dua uji ditambahkan), dan jalan dari nol di Mac gagal pada Bronze SIPSN karena `lxml` tidak tercantum di berkas kebutuhan (ditambahkan).

**Keterbatasan kerangka yang ditemukan dan tidak ditambal diam-diam.** Kelengkapan BNPB 0,653 karena agregat hanya memuat provinsi yang terdampak bencana; ukuran kelengkapan tidak cocok untuk tabel kejadian. Standarnya tidak diubah setelah hasil terlihat, tetapi pembacaannya dicatat untuk praregistrasi berikutnya, sama seperti validitas emisi bersih SIGN-SMART.

**Data pendukung** (sudah ada di repositori):

- [`data/serkom/kualitas-per-sumber.csv`](../../data/serkom/kualitas-per-sumber.csv): 66 baris, satu per sumber per dimensi, dengan nilai, standar, dan status memenuhi.
- [`data/serkom/prioritas-perbaikan.csv`](../../data/serkom/prioritas-perbaikan.csv): 47 masalah dengan baris terdampak, bobot, dan skor.
- [`data/gudang/m3_kualitas.json`](../../data/gudang/m3_kualitas.json): ambang yang dibekukan, ukuran per sumber, keterlacakan 1.487.727 dari 1.487.727 baris, dan contoh pelanggaran validitas.
- [`data/gudang/silver_ringkasan.json`](../../data/gudang/silver_ringkasan.json): karantina per tabel beserta alasan, termasuk 650 sel `wilayah_ambigu` SIGN-SMART dan 16 sel `cakupan_agregasi_kurang` SIPSN.
- [`data/produk/uji-integrasi.json`](../../data/produk/uji-integrasi.json): konsistensi antarsumber dan kelas sebab selisih setelah perbaikan insiden tanggal rilis.

## Catatan terbuka

- **Dua tindakan prioritas menunggu pihak luar.** Tabel kode SIGN-SMART menunggu jawaban KLH/BPLH (surat izin masih draf), dan berkas asli BNPB 2000 menunggu unduhan tangan. Sampai itu terjadi, 650 dan 84 sel tetap di karantina.
- **Dua keterbatasan kerangka belum masuk praregistrasi berikutnya:** validitas untuk `massa_setara` (emisi bersih boleh negatif) dan kelengkapan untuk tabel kejadian. Keduanya sengaja tidak diterapkan surut.
- **Duplikat WHO GHO** belum dilaporkan ke sumbernya; kedua nilai disimpan dan kuncinya ditandai, tidak dipilih salah satu.
- **Pemantauan baru bersifat per jalan**, belum berjadwal, karena konektor belum berjadwal (langkah 02, faktor kesegaran).
- **Kode belum disalin ke `code/`.** `src/sdg_gudang/silver/kualitas.py`, aturan S01–S09, dan uji unitnya masih di DSIC-SDG.

## Catatan untuk wawancara asesor

Dokumen di repositori ini disusun dengan bantuan asisten AI (Claude). Keputusan tetap tanggung jawab saya. Pertanyaan yang harus bisa saya jawab tanpa membaca: ceritakan satu masalah kualitas yang ditemukan dan diperbaiki (insiden tanggal rilis PBB, dari gejala sampai uji baru), mengapa ambang tidak boleh diubah setelah hasil terlihat, dan mengapa nilai negatif SIGN-SMART tidak dikoreksi padahal melanggar standar.
