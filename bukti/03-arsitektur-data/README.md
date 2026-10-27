# 03. Arsitektur data

**Unit:** J.62DMS00.003.1 Merencanakan Arsitektur Data

**Pertanyaan yang dijawab:** Model tata kelola apa yang cocok dengan budaya dan peraturan organisasi?

**Yang saya kerjakan:** Saya memilih model operasional federasi (data mesh) dengan menguraikan arah tarikan setiap faktor penggerak dari langkah 02: yang menuntut pengetahuan domain ditarik ke desentralisasi, yang menuntut kode dan lisensi yang sama ditarik ke sentralisasi. Hasilnya empat domain pilar TPB memiliki data product masing-masing, sedangkan tim platform menegakkan empat aturan global secara otomatis. Pilihan itu saya uji terhadap budaya organisasi, terutama siklus semester yang membuat pengisi peran domain dapat berganti, dan terhadap tujuh peraturan yang membentuk cara data diperlakukan.

| Elemen | Yang saya kerjakan | Bukti | Jenis | Status |
| --- | --- | --- | --- | --- |
| 1. Menyusun model operasional tata kelola data | memetakan lima unsur tata kelola ke strategi TI, arsitektur data, dan integrasi aplikasi; menganalisis arah tarikan lima penggerak; merancang model federasi dan mewujudkannya sebagai sembilan data product berkontrak | tabel dan bagan pada Elemen 1; `config/mesh/*.yaml` di DSIC-SDG; 12 tabel `dp` pada `data/gudang/m4_sidik_gold.json` | T, L, TL | lengkap, kode belum disalin ke `code/` |
| 2. Menganalisis pengaruh faktor budaya organisasi | menilai lima faktor penerimaan kedisiplinan dan lima faktor kemampuan beradaptasi, lalu menetapkan siklus semester sebagai faktor penentu | tabel pada Elemen 2 | T | lengkap, pemilik domain masih simulasi |
| 3. Menganalisis pengaruh faktor peraturan | memetakan tujuh peraturan dan ketentuan ke pola pikir yang dibentuknya, dan menetapkan lima penanda dini bila model tidak tepat | tabel pada Elemen 3 | T | lengkap, Perpres 39/2019 belum dicocokkan dengan teks resmi |

Jenis bukti: **L** langsung (artefak yang berjalan), **TL** tidak langsung (hasil terukur, laporan), **T** tambahan (dokumen tata kelola, surat).

## Lingkup unit

Unit ini menilai model operasional tata kelola beserta pengaruh budaya dan peraturannya, bukan arsitektur teknis. Arsitektur teknis gudang (lapis raw sampai Gold, Iceberg, Trino, dbt, Dagster) dibuktikan pada langkah 09 dan 10. Dokumen ini ditulis 20 Oktober 2026 pada fase M0, dan bagian yang berubah saat gudang benar-benar dibangun dicatat pada akhir Elemen 1.

## Elemen 1. Model operasional tata kelola data

**KUK 1.1 Unsur tata kelola terhadap strategi TI, arsitektur data, dan integrasi aplikasi.** Lima unsur yang harus dikelola dipetakan ke tiga lapis keputusan, supaya terlihat bahwa satu unsur tata kelola dapat berwujud berbeda di tiap lapis.

| Unsur | Strategi TI | Arsitektur data | Integrasi aplikasi |
| --- | --- | --- | --- |
| Penyimpanan | server game tetap kecil (Lightsail 4 GB, sudah menanggung DSW); beban analitik di simpul terpisah | lakehouse bermedali: raw, Bronze, Silver, Gold di Iceberg atas penyimpanan objek | hanya artefak beku (paket level, SQLite) yang dikirim ke server game |
| Pemrosesan | perangkat sumber terbuka, satu simpul, tanpa biaya lisensi | Spark direncanakan untuk Bronze dan korpus berita; Trino dan dbt untuk Silver dan Gold | Dagster menjalankan aset sepadan dengan data product |
| Waktu | – | tiga sumbu: periode, rilis, catat; kueri as-of memakai waktu rilis | API pemeriksa dan tool Bravais membaca SQLite turunan as-of satu tanggal acuan |
| Makna | – | data rujukan bersama: wilayah tipe 2, indikator TPB berpadanan IRI PBB, satuan | SDG KG dipakai Bravais, Kartu Keterkaitan, dan penaut klaim berita |
| Kepercayaan | guardrail di lapis aplikasi | provenans per sel sampai sha256 payload mentah | setiap jawaban Bravais membawa pengenal tabel, rilis, dan sumber |

**KUK 1.2 Model desentralisasi dan sentralisasi menurut faktor penggerak.** Penggerak bisnis pada langkah 02 tidak menarik ke satu arah. Alih-alih memilih satu kutub, saya memisahkan keputusan menurut arah tarikannya.

| Penggerak | Menarik ke | Keputusan yang mengikutinya |
| --- | --- | --- |
| Sumber bertambah dengan pengetahuan domain berbeda (sampah, bencana, kelautan, ketenagakerjaan) | desentralisasi | pemetaan Silver, kontrak, ambang kualitas, dan aturan rekonsiliasi lokal dipegang pemilik domain |
| Level lintas tujuan, Kartu Keterkaitan, dan peta memerlukan kode yang sama | sentralisasi | kode wilayah, kode indikator, satuan kanonik, dan format provenans dipegang tim platform |
| Lisensi berbeda per sumber | sentralisasi | kelas tayang ditetapkan pusat dan ditegakkan otomatis saat paket dibangun |
| Revisi terjadi pada waktu yang berbeda per sumber | desentralisasi | setiap domain memperbarui produknya sendiri; registri rilis dipegang pusat |
| Satu orang memegang sebagian besar peran saat ini | sentralisasi sementara | pilihan (a) atau (b) pada langkah 02 |

Hasilnya adalah model federasi: empat domain pilar memiliki data product, sedangkan platform menyediakan alat swalayan dan menegakkan aturan global.

```
   Aturan global (tim platform, ditegakkan otomatis)
   kode wilayah · kode indikator · satuan · kelas lisensi · format provenans
   ───────────────────────────────────────────────────────────────────────
   │ Domain Sosial │ Domain Ekonomi │ Domain Lingkungan │ Domain Hukum dan │
   │ SDG 1–5       │ SDG 7–10, 17   │ SDG 6, 11–15      │ Tata Kelola SDG 16│
   │ kontrak lokal │ kontrak lokal  │ kontrak lokal     │ kontrak lokal     │
   ───────────────────────────────────────────────────────────────────────
   Platform swalayan: konektor · templat Silver · pembangkit kontrak ·
   registri rilis · katalog metadata · Dagster · Iceberg/Trino
   ───────────────────────────────────────────────────────────────────────
   Konsumen: dp_liga (paket level) · Bravais · pemeriksa klaim berita · naskah
```

Pembagian tujuan per pilar mengikuti Permen PPN/Kepala Bappenas Nomor 1 Tahun 2024 Pasal 4 ayat (3) sampai (6), yang juga menjadi struktur Metadata Indikator TPB per pilar. Padanannya diperiksa pada M1 dan disimpan sebagai `artefak/referensi/dim_pilar.csv` di DSIC-SDG. Struktur ini dipilih karena sudah dikenal pemangku kepentingan, sehingga pemilik domain tidak perlu mempelajari pembagian baru.

**Wujud model setelah gudang dibangun (21–24 Oktober 2026).** Federasi tidak berhenti sebagai bagan. Setiap data product dinyatakan sebagai satu berkas YAML sepanjang 19–26 baris di `config/mesh/` yang memuat pemilik, kanal pelaporan masalah, SLA kesegaran, dan aturan kualitas. Pembangkit kontrak menurunkan dari setiap YAML sebuah model dbt, kontrak skema, uji aturan global federasi, uji SLA, dan rekaman DCAT, sehingga kontrak tidak dapat tertinggal dari konfigurasi.

| Pemilik | Tujuan | Data product |
| --- | --- | --- |
| Domain Sosial | 1–5 | `dp_sosial_provinsi`, `dp_sosial_nasional` |
| Domain Ekonomi | 7–10, 17 | `dp_ekonomi_provinsi`, `dp_ekonomi_nasional` |
| Domain Lingkungan | 6, 11–15 | `dp_lingkungan_provinsi`, `dp_lingkungan_nasional` |
| Domain Hukum dan Tata Kelola | 16 | `dp_tatakelola_provinsi` |
| Tim platform | – | `dp_referensi` (wilayah, indikator, satuan, konsep), `dp_rilis` (registri rilis) |

Sembilan data product itu terwujud sebagai 12 tabel `dp` di Gold yang sidiknya tercatat di `data/gudang/m4_sidik_gold.json`, dan uji aturan global lulus pada setiap rebuild bersama 139 node dbt lainnya. Tiga keputusan teknis berubah dari rencana 20 Oktober saat dibangun, dan masing-masing dibuktikan pada langkah lain:

- **Spark tidak dipakai.** Pengukuran pada volume gudang ini menunjukkan Spark lokal hanya lebih cepat kurang dari satu detik per langkah dibanding Trino (`data/uji/banding-spark.json`), dan pada jalur berita batasnya jaringan, bukan komputasi. Rinciannya di langkah 10.
- **Orkestrator ditetapkan Dagster** pada 20 Oktober, karena asetnya dapat dibuat sepadan dengan data product dan membaca lineage dbt. Rinciannya di langkah 09.
- **Katalog metadata memakai versi ringan** (DCAT per data product, dokumentasi dbt, katalog Iceberg REST) sebagai ganti OpenMetadata. Rinciannya di langkah 05.

## Elemen 2. Pengaruh faktor budaya organisasi

**KUK 2.1 Faktor penerimaan kedisiplinan.** Kedisiplinan yang dituntut model federasi adalah menaati aturan global dan kontrak. Lima faktor berikut menentukan apakah kedisiplinan itu akan diterima, dan masing-masing mengubah bentuk modelnya.

| Faktor | Keadaan | Implikasi pada model |
| --- | --- | --- |
| Kebiasaan riset: hasil diulang dengan satu perintah dan praregistrasi | kuat; sudah dijalankan pada uji hipotesis penelitian sebelumnya dan uji keterikatan jawaban Bravais | aturan global ditegakkan sebagai uji otomatis, bukan dokumen yang harus dibaca |
| Kebiasaan kelas: tugas dinilai per individu, tenggat semester | kuat pada mahasiswa | bila pilihan (b) diambil, kontrak domain menjadi bagian rubrik proyek agar disiplin kontrak diterima |
| Ruang kerja bersama satu repositori git | ada | aturan global dan kontrak berversi; perubahan lewat commit yang dapat ditinjau |
| Rasa memiliki data | rendah pada mahasiswa, tinggi pada peneliti | kepemilikan domain dinyatakan eksplisit di berkas `config/mesh/<produk>.yaml` beserta kanal masalah |
| Toleransi terhadap pekerjaan dokumentasi | rendah | dokumentasi dibangkitkan dari kontrak dan katalog, bukan ditulis tangan |

**KUK 2.2 Faktor kemampuan beradaptasi terhadap perubahan.**

| Faktor | Penilaian | Penguat |
| --- | --- | --- |
| Ukuran tim | satu peneliti inti; dapat ditambah empat kelompok mahasiswa | keputusan cepat; risiko beban kerja tinggi |
| Siklus semester | kelas berganti setiap semester | pengetahuan domain hilang bila tidak tertulis di kontrak dan metadata |
| Jejak perubahan sebelumnya | baik: dua kali arah penelitian berubah dalam seminggu (penggabungan dua naskah menjadi satu dan peniadaan pilot) tanpa kehilangan artefak | raw tidak pernah ditimpa; paket berversi; keputusan dicatat bertanggal di dokumen rencana |
| Ketergantungan pada pihak luar | tinggi: izin produsen, situs yang menolak unduhan otomatis, layanan yang dihentikan | kelas tayang; jenis bukti tanggal; urutan prioritas pemotongan lingkup pada rencana kerja gudang |
| Kemampuan teknis | tinggi pada stack yang sudah dipakai (Python, SQLite, Iceberg, Trino); baru pada dbt, Dagster, RDF | perangkat baru dipilih yang dapat berjalan di satu simpul dan diuji dulu pada satu sumber |

**Aspek kritis unit ini** adalah faktor yang memengaruhi kemampuan beradaptasi. Pada organisasi ini faktor penentunya adalah siklus semester. Bila peran domain diisi mahasiswa, orangnya berganti setiap semester, sehingga model federasi hanya bertahan bila pengetahuan domain tersimpan di kontrak, metadata, dan uji yang berjalan sendiri. Karena itu model ini menempatkan aturan yang dapat dieksekusi di atas dokumen yang harus dibaca, dan wujudnya terlihat pada fase gudang: kontrak dbt dibangkitkan dari YAML, bukan ditulis tangan.

## Elemen 3. Pengaruh faktor peraturan

**KUK 3.1 Unsur peraturan yang membentuk pola pikir.** Tujuh peraturan dan ketentuan berikut menentukan bagaimana data diperlakukan pada model ini. Kolom terakhir menyatakan pola pikir yang dibentuknya, bukan sekadar kutipan pasal.

| Peraturan atau ketentuan | Pokok yang relevan | Pola pikir yang dibentuk |
| --- | --- | --- |
| UU 16/1997 tentang Statistik | membedakan statistik dasar oleh BPS dan statistik sektoral oleh instansi | BPS bukan satu-satunya sumber resmi; data KLH, KKP, dan BNPB adalah statistik sektoral yang sah dengan pemilik berbeda |
| Perpres 39/2019 tentang Satu Data Indonesia **[periksa teks resmi]** | standar data, metadata, interoperabilitas, kode referensi dan data induk | data rujukan dan metadata adalah kewajiban, bukan pelengkap; selaras dengan langkah 04 dan 05 |
| UU 14/2008 tentang Keterbukaan Informasi Publik | informasi publik dapat diakses | data pemerintah dapat dipakai, tetapi syarat pemakaian dan redistribusi tetap ditanyakan kepada pemiliknya |
| UU 28/2014 tentang Hak Cipta, Pasal 41 huruf b, 43 huruf c, 44 ayat (1) huruf a | data tidak dilindungi; berita aktual boleh diambil dengan sumber; pemakaian untuk pendidikan dan penelitian dengan syarat | ekstrak angka dan simpan cuplikan pendek; teks penuh berita dibuang |
| UU 27/2022 tentang Pelindungan Data Pribadi | dasar pemrosesan, minimisasi, hak subjek data | telemetri tanpa isi jawaban; hash untuk analisis; hak tarik data peserta |
| Lisensi sumber (term of use BPS, CC BY 4.0, ODbL, CC BY-SA, nonkomersial) | atribusi, share-alike, larangan redistribusi | kelas tayang A, A-SA, B, C yang ditegakkan saat paket dibangun |
| Kode etik penelitian dengan manusia (komite etik institusi) | persetujuan berdasar informasi, kesukarelaan | evaluasi pengguna tidak memengaruhi nilai; persetujuan tertulis |

**KUK 3.2 Faktor dampak ketepatan model operasional.** Setiap kemungkinan model yang keliru dipasangkan dengan dampaknya dan penanda dini yang dapat dipantau, supaya ketidaktepatan terdeteksi sebelum menjadi insiden.

| Bila model tidak tepat | Dampak | Penanda dini yang dipantau |
| --- | --- | --- |
| Terlalu terpusat | satu orang menjadi hambatan; sumber sektoral tertunda; jadwal M2–M4 tergelincir | jumlah sumber yang tertunda lebih dari lima hari dari jadwal fase |
| Terlalu terdesentralisasi | kode wilayah atau satuan berbeda antardomain; level lintas tujuan dan peta rusak | pelanggaran aturan global per pembaruan lebih dari nol |
| Aturan lisensi tidak ditegakkan pusat | sumber kelas B atau C tampil di game; risiko hukum dan relasi dengan produsen | uji kelas tayang pada pembangunan paket |
| Aturan privasi tidak ditegakkan pusat | nama orang atau username masuk berkas analisis | uji kolom terlarang pada ekspor |
| Pemilik domain tidak jelas | laporan kesalahan angka tidak ditangani | laporan terbuka lebih dari tujuh hari |

Penanda ini ditinjau di akhir setiap fase bersama status faktor keberhasilan pada langkah 02 Elemen 4. Sampai 24 Oktober, penanda kedua (pelanggaran aturan global) bernilai nol pada setiap rebuild; penanda lainnya belum pernah terpicu, tetapi juga belum diuji pada keadaan dengan pemilik domain yang berbeda orang.

**Data pendukung** (sudah ada di repositori):

- [`data/gudang/m4_sidik_gold.json`](../../data/gudang/m4_sidik_gold.json): 12 tabel `dp` beserta jumlah baris dan sidiknya, bukti bahwa data product federasi benar-benar terbentuk.
- [`data/gudang/m4_lineage.json`](../../data/gudang/m4_lineage.json): jalur setiap data product ke berkas raw, tanpa data product yang terputus.
- [`data/uji/banding-spark.json`](../../data/uji/banding-spark.json): dasar keputusan tidak memakai Spark pada volume gudang ini.

## Catatan terbuka

- **Pemilik domain masih simulasi.** Keempat domain pilar saya pegang sendiri, sehingga sisi organisasi federasi (dua orang berbeda memegang domain yang berbeda dan harus menaati aturan global yang sama) belum pernah diuji. Sisi teknisnya sudah terbukti lewat uji aturan global yang berjalan tanpa pelanggaran.
- **Perpres 39/2019 belum dicocokkan pasal demi pasal** dengan teks resmi. Baris itu pada KUK 3.1 bertumpu pada pemahaman umum tentang Satu Data Indonesia dan harus diperiksa sebelum dipakai di hadapan asesor.
- **Tiga keputusan teknis menyimpang dari bagan 20 Oktober** (tanpa Spark, Dagster, katalog ringan). Bagan di Elemen 1 sudah disesuaikan pada baris katalog metadata; tabel KUK 1.1 dibiarkan memuat rencana semula dengan keterangan "direncanakan", agar perubahan keputusan tetap terbaca.
- **Kode belum disalin ke `code/`.** Berkas `config/mesh/*.yaml` dan pembangkit kontrak masih di DSIC-SDG; akan disalin sesuai daftar di `code/README.md`.

## Catatan untuk wawancara asesor

Dokumen di repositori ini disusun dengan bantuan asisten AI (Claude). Keputusan tetap tanggung jawab saya. Pertanyaan yang harus bisa saya jawab tanpa membaca: mengapa federasi dan bukan terpusat, apa saja empat aturan global dan mengapa hanya empat, serta budaya dan peraturan mana yang paling mengubah bentuk modelnya.
