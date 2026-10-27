# 10. Big data dan operasi

**Unit:** J.62DMS00.007.1 Merancangbangun Big Data

**Pertanyaan yang dijawab:** Pemrosesan apa yang benar-benar dibutuhkan pada volume ini, dan apakah memenuhi SLA?

**Yang saya kerjakan:** Saya mengukur dulu, baru memilih alat. Data yang disimpan ternyata kecil (Raw 142,5 MB, Bronze 1,6 juta baris, rebuild penuh dari Raw sekitar 3,5 menit), sedangkan data yang besar, yaitu arsip global dan GDELT berukuran terabita, dibatasi oleh jaringan dan bukan oleh CPU. Karena itu Spark tidak dipakai: statistik resmi diproses batch dengan rebuild penuh, sumber besar diproses dalam mode alir dengan utas paralel, dan keputusan itu diuji dengan pembanding Spark nyata pada data yang sama. Ambang SLA setiap lapis ditulis lebih dulu, lalu diuji dari tumpukan kosong: 45 dari 46 pemeriksaan lulus, dan satu kegagalan pada API produksi ditelusuri sampai akarnya tanpa mengubah ambang.

| Elemen | Yang saya kerjakan | Bukti | Jenis | Status |
| --- | --- | --- | --- | --- |
| 1. Mengidentifikasi tipe data processing | mengelompokkan 15 sumber menurut kecepatan terbit dan ukuran satuan terbitnya, lalu menetapkan tipe pemrosesan per kelompok dengan alasan | tabel pada Elemen 1; `data/gudang/volume.json` | T, TL | lengkap |
| 2. Mengidentifikasi layer big data | menguraikan lapis ingestion, processing, dan presentation beserta artefak yang mewujudkannya | Elemen 2; langkah 06, 07, 09 | T | lengkap |
| 3. Membuat arsitektur big data | membandingkan opsi teknologi per lapis dengan pengukuran, menetapkan SLA per lapis, mendaftar risiko dan mitigasinya | `data/uji/banding-spark.json`; tabel pada Elemen 3 | TL, T | lengkap |
| 4. Melakukan implementasi arsitektur big data | memasang tumpukan, menjalankan konektor, menguji ketersambungan antarlapis terhadap SLA dari tumpukan kosong, dan mendokumentasikan hasilnya | `data/uji/uji-sla.json`, `uji-sla-api.json`, `uji-sla-gdelt.json`; `data/produk/latensi-produksi-*.json` | L, TL | lengkap, tanpa klaster terdistribusi |

Jenis bukti: **L** langsung (artefak yang berjalan), **TL** tidak langsung (hasil terukur, laporan), **T** tambahan (dokumen tata kelola, surat).

## Kedudukan langkah ini

Bukti ini disusun 21 Oktober 2026 setelah jalan ulang M3–M5 di Mac dan dilengkapi 24 Oktober dengan uji SLA antarlapis, jalan GDELT seminggu, dan uji pembanding Spark. Keputusan pokoknya adalah Spark tidak dipakai, padahal rencana kerja semula memakainya untuk arsip WDI dan korpus berita. Keputusan itu saya ambil pada 21 Oktober setelah pengukuran, dan diuji ulang pada 24 Oktober dengan beban nyata. Klaim pada langkah ini sengaja dibatasi pada volume yang benar-benar diuji; tidak ada klaim tentang klaster terdistribusi.

## Elemen 1. Tipe data processing

**KUK 1.1 Sumber data sesuai arsitektur data.** Ada dua kelompok sumber, dan keduanya masuk lewat lapis Raw yang sama dengan manifest sha256 dan registri rilis `dim_rilis`. Statistik resmi (12 sumber: BPS, BRS, ILOSTAT, WDI dan arsip 142 versi, basis data SDG PBB dan arsip 48 rilis, WHO, BNPB, SIPSN, SIGN-SMART, KKP) menjadi Bronze, Silver, lalu Gold bitemporal (langkah 09). Berita (3 sumber: GDELT GKG 2.1, CC-NEWS, dan RSS Antara, CNN Indonesia, Detik) hanya disimpan metadata dan URL-nya, menjadi Bronze `artikel` sebagai masukan alur klaim.

**KUK 1.2 Jenis sumber menurut kecepatan transaksi.**

| Sumber | Kecepatan terbit | Ukuran satu satuan terbit |
| --- | --- | --- |
| BPS, BRS | bulanan sampai tahunan; BRS sekitar 90 rilis per tahun | kurang dari 10 MB |
| Arsip WDI, arsip SDG PBB | 5–10 versi per tahun | 0,2–0,3 MB tersimpan per versi; unduhan sementara sampai 68 MB |
| Sumber sektoral | 1–4 snapshot per tahun | kurang dari 5 MB |
| RSS | menit sampai jam | puluhan KB per pengambilan |
| GDELT GKG | satu berkas per 15 menit per aliran | rata-rata 8,8 MB zip (2016–2026) |
| CC-NEWS | beberapa berkas WARC per hari | sekitar 1 GB per berkas |

**KUK 1.3 Tipe processing berdasarkan sumber.** Tipe dipilih per kelompok, bukan satu tipe untuk semua.

| Sumber | Tipe | Alasan |
| --- | --- | --- |
| Statistik resmi | batch, dibangun ulang penuh dari Raw | volume kecil; rebuild penuh lebih sederhana dan dapat dibuktikan lewat sidik Gold yang sama |
| Arsip global (WDI, SDG PBB) | batch alir: payload dibaca bertahap, hanya ekstrak Indonesia yang disimpan | payload 2,63 GB, ekstrak puluhan MB |
| GDELT, CC-NEWS | batch alir per hari, paralel per berkas, unduhan dibuang setelah disaring | sumber berukuran TB, keluaran kurang dari 1,5 % baris |
| RSS | mikro-batch berkala (inkremental) | aliran kecil; payload yang sudah dikenal dilewati lewat sha256 |

Streaming sejati seperti Kafka atau Flink tidak dipakai, karena tidak ada konsumen yang membutuhkan latensi di bawah satu jam: klaim berita diperiksa terhadap vintage yang berlaku pada tanggal terbit, bukan seketika.

## Elemen 2. Layer big data

**KUK 2.1 Data ingestion layer.** Konektor per sumber di `src/sdg_gudang/akuisisi/konektor/` menulis Raw di `data/raw/gudang/<sumber>/<tanggal>/` dengan manifest sha256 dan baris `dim_rilis` berjenis bukti tanggal. Untuk sumber besar yang dialirkan, manifest mencatat sha256 payload asli walaupun payloadnya tidak disimpan, sehingga asal setiap ekstrak tetap dapat diverifikasi dengan `make m2-verifikasi`. Pada uji SLA, integritas 907 berkas Raw terhadap manifest bernilai 1,0.

**KUK 2.2 Data processing layer.** Raw diurai menjadi Bronze apa adanya, lalu dipetakan ke Silver dengan karantina dan rekonsiliasi multisumber (langkah 07). Berikutnya dbt-trino membangun Gold bitemporal dan data product (langkah 09), semuanya diorkestrasi job Dagster `gudang_penuh`. Jalur berita berhenti di Bronze `artikel`, lalu masuk alur klaim.

**KUK 2.3 Data presentation layer.** Sembilan data product berkontrak (langkah 03), TPB-KG yang lulus SHACL (langkah 05), indeks klaim berita, dan artefak beku untuk game: paket level dan SQLite Bravais di server DSW.

## Elemen 3. Arsitektur big data

**KUK 3.1 Opsi teknologi per layer.**

| Layer | Opsi yang dipertimbangkan | Dipilih | Dasar pilihan |
| --- | --- | --- | --- |
| Ingestion | Python dengan `requests`; Spark membaca HTTP; BigQuery untuk GDELT | Python mode alir; BigQuery tetap tersedia sebagai `jalur=bq` | pengukuran di bawah |
| Penyimpanan | MinIO, SeaweedFS (S3), Iceberg REST, Nessie | SeaweedFS dan Iceberg REST, tanpa Nessie | langkah 06, keputusan M4 |
| Processing indikator | Spark, Trino dengan dbt, Python | Python untuk Bronze dan Silver, PyIceberg untuk memuat, dbt-trino untuk Gold | 1,49 juta baris fakta; muat ke Iceberg 4 detik |
| Processing berita | Spark local, Spark klaster, Python dengan utas | Python dengan utas (`pekerja=N`) | penyempitnya jaringan, bukan CPU |
| Presentation | Trino, SQLite, Oxigraph | turunan SQLite, Oxigraph | Trino p95 31–64 ms per data product; SQLite di bawah 1 ms per pemeriksaan jawaban |

Pengukuran yang menjadi dasar menolak Spark dilakukan 21 Oktober 2026 di Mac. Raw 12 sumber 142,5 MB; Bronze 32,7 MB dengan 1,6 juta baris; rebuild penuh 215–228 detik. Di sisi lain, GDELT GKG 2016 sampai 20 Oktober 2026 berukuran 2,61 TB (371.730 berkas Inggris) ditambah 3,88 TB terjemahan, dengan hanya 0,48–1,32 % baris dari media Indonesia. Pada sampel 8 berkas, membuka zip dan menyaring di satu inti berjalan sekitar 95 MB zip per detik, sedangkan unduh dan saring dengan 1, 4, 8, dan 16 utas memberi 5,7, 9,7, 18,1, dan 19,5 MB per detik. Tiga simpulan mengikuti: saringan hanya memakai sekitar 0,2 inti pada laju jaringan itu; tambahan utas di atas 8 tidak menaikkan laju, jadi batasnya sambungan jaringan; dan Spark, yang membagi kerja CPU antarinti atau antarnode, tidak menambah bandwidth di satu mesin tetapi menambah JVM 2 GB dan satu layanan untuk dirawat. Mengunduh seluruh GKG 6,5 TB pada 18 MB per detik butuh sekitar 4 hari, dan ruang kosong Mac 6,2 GiB membuat mode alir wajib apa pun mesin pemrosesnya.

Agar alasan itu tidak hanya taksiran, pada 24 Oktober dua beban kerja nyata dijalankan dengan Spark 3.5.3 lokal (`local[8]`, Java 17) dan dengan cara yang dipakai sekarang, pada data yang sama (`data/uji/banding-spark.json`). Ketiga jalur memberi hasil identik.

| Beban | Cara sekarang | Spark lokal | Pembacaan |
| --- | --- | --- | --- |
| Window `lead()` bitemporal atas 1.486.490 observasi Silver | Trino 1,77 s | 0,95 s, ditambah 2,5 s menyalakan JVM | Spark lebih cepat sekitar 0,8 s; keduanya di bawah 2 s, sedangkan job penuh 207 s dan 104 s di antaranya habis di parser Python Bronze dan Silver |
| Agregasi per konsep | Trino 0,66 s | 0,22 s | selisih di bawah 1 s |
| Saring GKG GDELT ke media Indonesia, 12 zip (53 MB) | Python 1 inti 91–139 MB zip/s | 8 inti termasuk ekstrak zip, 95 MB zip/s | Spark tidak lebih cepat daripada Python satu inti |
| Laju jaringan pada saat yang sama | 5,7 MB/s (8 utas, sampel); 11,6 MB/s (jalan seminggu) | – | kapasitas pemrosesan 8–24 kali laju unduhan |

Dengan angka itu Spark tidak dipasang: pada volume ini keuntungannya di bawah satu detik per langkah, biayanya satu mesin pemroses kedua beserta JVM. Trino tetap dibutuhkan untuk dbt, kontrak, dan sajian. Bila volume tumbuh sampai puluhan juta observasi, bagian yang paling layak dipindahkan ke pemrosesan paralel adalah parser Bronze dan Silver, bukan transformasi Gold.

**KUK 3.2 SLA sesuai tipe processing.** Batasan variabel unit menyebut SLA sebagai toleransi atas kualitas data yang diproses, misalnya kapan terakhir diperbarui. SLA ditulis per lapis dan alur, dan masing-masing punya tempat dinyatakan yang dapat diperiksa mesin.

| Lapis dan alur | SLA | Tempat dinyatakan | Status 24 Okt 2026 |
| --- | --- | --- | --- |
| Data product (Gold) | kesegaran per produk, misalnya 400 hari untuk produk ekonomi, 31 hari untuk registri rilis | `config/mesh/*.yaml`, `sla.kesegaran_hari`; uji dbt tingkat warn | diuji setiap rebuild; terburuk 109 dari 400 hari |
| Rebuild penuh indikator | selesai di bawah 10 menit; sidik Gold sama di setiap jalan | `config/sla/lapis.yaml`; `m4_sidik_gold.json` | tercapai: 207 s, sidik sama |
| Ingest berkas GDELT | setiap hari UTC lengkap 96 berkas per aliran; md5 cocok dengan `masterfilelist`; laju ≥ 10 MB/s; satu hari ≤ 60 menit | manifest GDELT (`asal`, `gagal`) | lulus pada jendela 14–20 Oktober |
| RSS | satu pengambilan per hari; payload baru menjadi rilis baru | manifest `rss-<tanggal>.json` | berjalan |
| API produksi | p95 panggilan dari luar ≤ 3 s, 0 galat | `config/sla/lapis.yaml` | lulus dengan gzip, gagal tanpa kompresi (KUK 4.3) |

**KUK 3.3 Daftar risiko per opsi teknologi.**

| Risiko | Opsi terdampak | Mitigasi |
| --- | --- | --- |
| Unduhan GKG penuh memakan hari dan dapat terputus | ingest GDELT | manifest per hari; jalan dilanjutkan dari hari terakhir (`lanjut`); jendela dibatasi `maks_berkas` dan `maks_gb` |
| Disk lokal habis | ingest alir | zip dibuang setelah disaring; hanya ekstrak disimpan |
| GDELT mengganti alamat; `http://` dialihkan ke `https://` sejak Oktober 2026 | ingest GDELT | konstanta HTTPS; URL `masterfilelist` dinormalkan; diuji unit |
| Terlalu banyak permintaan paralel ke satu host | ingest GDELT | `pekerja` paling banyak 16, jeda per utas `jeda_s` |
| Hasil paralel berbeda dari hasil berurutan | ingest GDELT | hasil digabung menurut cap waktu; uji `test_gdelt_berkas_paralel_sama_dengan_berurutan` |
| Biaya BigQuery tak terkendali | `jalur=bq` | dry run dan `maximum_bytes_billed` (`maks_gb`) |
| Data pribadi masuk dari berita | semua alur berita | kolom nama orang dan kutipan GKG tidak diambil; pagar panjang kolom (langkah 11) |
| Volume tumbuh melewati satu mesin | seluruh tumpukan | Iceberg dan S3 tidak terikat pada mesin pemroses, sehingga Spark atau Trino klaster dapat dipasang tanpa memindahkan data |

**KUK 3.4 Rancangan arsitektur.** Arsitektur gudang berlapis diuraikan pada langkah 09. Jalur berita menambahkan satu cabang: GDELT, CC-NEWS, dan RSS masuk ke Raw sebagai ekstrak bermanifest, menjadi Bronze `artikel`, lalu masuk alur klaim, yaitu ekstraksi tupel, penautan ke SDG KG, serta pemeriksaan as-of dan terkini terhadap Gold.

## Elemen 4. Implementasi arsitektur big data

**KUK 4.1 Tools implementasi.** Python 3.13, `requests`, `zipfile`, `concurrent.futures`, PyIceberg 0.12.0, SeaweedFS, Iceberg REST, Trino 476, dbt-trino, Dagster, Oxigraph, pySHACL, dan Docker lewat Colima (4 vCPU, 8 GiB). Sisi produksi: API Python di Lightsail 4 GB dengan SQLite turunan.

**KUK 4.2 Deploy teknologi per layer.** Tumpukan dinaikkan dengan `make m4-naik` dari `infra/gudang/compose.yml`. Konektor dijalankan dengan `make m2-jalan-<sumber>` dan `make m5-jalan-<sumber>`; contoh jalur GDELT berkas dengan 8 utas:

```bash
make m5-jalan-gdelt OPSI="jalur=berkas mulai=2026-10-01 sampai=2026-10-07 pekerja=8"
```

**KUK 4.3 Uji ketersambungan antarlayer sesuai SLA.** Ambang setiap lapis ditulis lebih dulu di `config/sla/lapis.yaml` pada 24 Oktober 2026, sebelum uji pertama, mengambil target yang sudah tercatat di langkah 02, 06, 08, dan 09. Uji dijalankan dengan `make m4-uji-sla`: tumpukan beserta volumenya dihapus, gudang dibangun dari Raw tanpa jaringan, lalu setiap perpindahan antarlapis diperiksa (`data/uji/uji-sla.json`, commit `dcaa55e`).

| Lapis | Yang diuji | Hasil 24 Okt 2026 |
| --- | --- | --- |
| Ingest | sha256 seluruh berkas Raw terhadap manifest; umur snapshot terakhir per sumber ≤ 7 hari | integritas 1,0 pada 907 berkas; umur terburuk 4 hari |
| Proses | waktu tiap langkah job `gudang_penuh` dan total ≤ 600 s; uji dbt gagal 0; keterlacakan Silver 1,0 | total 207,3 s (Bronze 43,8; Silver 60,4; rekonsiliasi 42,9; kualitas 14,8; muat Iceberg 3,8; dbt 40,7); 139 node dbt, 0 gagal; keterlacakan 1,0 |
| Sajian, data product | baris minimum, kesegaran terhadap `sla.kesegaran_hari` tiap YAML, p95 query titik lewat Trino ≤ 2 s | 12 data product lulus; kesegaran terburuk 109 dari 400 hari; p95 terburuk 63,6 ms |
| Sajian, ke paket level | ekspor Gold ke masukan paket identik byte dengan versi ter-commit, ≤ 120 s | identik 4 dari 4 berkas, 50,5 s |
| Sajian, API produksi | p95 panggilan dari luar ≤ 3 s, 0 galat | gagal tanpa kompresi (p95 8,4 s, jawaban 513 KB); lulus dengan gzip seperti peramban (p95 2,2 s, 38,5 KB) |
| Keterulangan | sidik Gold sama dengan acuan | `657df68e…` sama |
| Ingest berita GDELT | 14–20 Oktober 2026, dua aliran, `pekerja=8`: 96 berkas per aliran-hari, 0 gagal md5 atau unduh, laju ≥ 10 MB/s, satu hari ≤ 60 menit | 14 dari 14 aliran-hari lengkap, 0 gagal, 11,6 MB/s (8,42 GB zip dalam 726 s), satu hari sekitar 1,5 menit |

Dari 46 pemeriksaan uji gudang, 45 lulus. Satu kegagalan, API tanpa kompresi, berasal dari cara uji memanggil API: klien Python tidak meminta gzip, sedangkan peramban selalu meminta. Ambang tidak diubah. Kedua cara diukur ulang (`data/uji/uji-sla-api.json`): tanpa kompresi p50 4,7 s dan p95 6,5 s untuk jawaban 513 KB; dengan gzip p50 1,5 s dan p95 2,2 s untuk 38,5 KB. Latensi dari luar terutama ditentukan oleh jaringan dari Mac ke server di Sydney, sedangkan waktu proses di server sendiri tetap di bawah satu milidetik: pada tiga pengukuran 2.000 kiriman di produksi, p95 pemeriksaan jawaban 0,714–0,751 ms (`data/produk/latensi-produksi-*.json`).

**KUK 4.4 Dokumentasi hasil uji SLA.** Log yang dibangkitkan otomatis (`log-uji-sla.md` di repositori penelitian Ardika) memuat tabel semua pemeriksaan dengan nilai, ambang, dan hasil, ditambah diagnosis API dan ingest GDELT per aliran-hari. Hasil mentahnya disalin ke repositori ini sebagai `data/uji/uji-sla.json`, `uji-sla-api.json`, `uji-sla-gdelt.json`, dan `banding-spark.json`; manifest jalan GDELT dengan sha256 setiap zip asal ada di repositori penelitian Ardika.

**Data pendukung** (sudah ada di repositori):

- [`data/gudang/volume.json`](../../data/gudang/volume.json): volume Raw, Bronze, dan manifest per sumber, dasar pemilihan tipe pemrosesan.
- [`data/uji/uji-sla.json`](../../data/uji/uji-sla.json): hasil 46 pemeriksaan antarlapis, waktu per langkah job, p95 per data product, sidik Gold.
- [`data/uji/uji-sla-api.json`](../../data/uji/uji-sla-api.json): pengukuran ulang API produksi tanpa kompresi dan dengan gzip.
- [`data/uji/uji-sla-gdelt.json`](../../data/uji/uji-sla-gdelt.json): ingest GDELT 14 aliran-hari, laju, durasi, kegagalan.
- [`data/uji/banding-spark.json`](../../data/uji/banding-spark.json): dua beban kerja pada Trino, Python, dan Spark lokal.
- [`data/produk/latensi-produksi-1.json`](../../data/produk/latensi-produksi-1.json), [`-2`](../../data/produk/latensi-produksi-2.json), [`-3`](../../data/produk/latensi-produksi-3.json): latensi proses dan memori pekerja API di produksi.

## Catatan terbuka

- **Tidak ada klaster terdistribusi.** Semua pengukuran di satu mesin (Mac 8 inti) dan satu server produksi 4 GB. Klaim "big data" di sini terbatas pada sumber berukuran terabita yang dialirkan dan disaring, bukan pada pemrosesan terdistribusi; bila ditanya, jawabannya adalah volume dan laju diukur dulu, alat dipilih sesudahnya.
- **Satu pemeriksaan SLA gagal pada cara panggil pertama** (API tanpa kompresi). Kegagalan ini dicatat sebagai perubahan dari rencana uji, bukan dihapus, dan ambang 3 s tetap.
- **Uji GDELT baru satu jendela seminggu** (14–20 Oktober). Perilaku pada jendela yang memuat interval tidak terbit atau alamat berubah baru dilindungi uji unit, belum oleh jalan nyata.
- **CC-NEWS dan RSS belum punya uji SLA tersendiri**; keduanya baru diperiksa lewat umur snapshot pada lapis ingest.
- **Berkas uji memuat alamat API produksi** (`sditera.cloud`). Itu alamat publik layanan, bukan rahasia, tetapi perlu diketahui sebelum repositori dipublikasikan.
- **Kode yang dirujuk tersalin di [`code/`](../../code/README.md)** dari repositori penelitian Ardika pada commit `dcaa55e` (22 Oktober 2026), termasuk jalur berkasnya yang disebut di atas.

## Catatan untuk wawancara asesor

Dokumen di repositori ini disusun dengan bantuan asisten AI (Claude). Keputusan tetap tanggung jawab saya. Pertanyaan yang harus bisa saya jawab tanpa membaca: ini big data tanpa Spark (jawaban intinya: volume dan laju diukur dulu, penyempitnya jaringan, pembanding Spark nyata di bawah satu detik), bagaimana SLA ditetapkan dan diuji dari tumpukan kosong, dan mengapa satu kegagalan uji API tidak membuat ambang diubah.
