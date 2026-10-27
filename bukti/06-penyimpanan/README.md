# 06. Media penyimpanan

**Unit:** J.62DMS00.005.1 Merencanakan Media Penyimpanan Data

**Pertanyaan yang dijawab:** Seberapa besar datanya, akan tumbuh berapa, dan disimpan di mana?

**Yang saya kerjakan:** Saya mengukur volume setiap lapis per sumber setelah akuisisi 12 sumber selesai pada 20 Oktober 2026 (Raw 142,5 MB dalam 889 berkas, Bronze 32,7 MB dengan 1,6 juta baris, 2.662 rilis tercatat), lalu menaksir pertumbuhannya dari frekuensi rilis yang terukur di registri 2021–2026. Karena volumenya kecil, yang menentukan pilihan media bukan kapasitas simpan melainkan jenis data dan memori komputasi: penyimpanan objek untuk Raw, Iceberg untuk Bronze sampai Gold, SQLite untuk sajian berlatensi rendah, RDF untuk graf. Masa simpan ditetapkan per jenis data, dan lima opsi tempat lakehouse dibandingkan biayanya sampai 31 Desember 2026 sebelum ada yang dibeli.

| Elemen | Yang saya kerjakan | Bukti | Jenis | Status |
| --- | --- | --- | --- | --- |
| 1. Menganalisis jumlah data | mengukur Raw, Bronze, manifest, dan rilis per sumber dengan `make m2-volume`; menaksir pertumbuhan dari frekuensi rilis terukur | `data/gudang/volume.json`; tabel pada Elemen 1 | TL | lengkap |
| 2. Merencanakan volume data | merinci volume per lapis arsitektur, memeriksa kecukupan tiga tahun, dan menulis model pertumbuhan V(t) | tabel dan rumus pada Elemen 2 | T, TL | lengkap, volume berita belum ditaksir |
| 3. Membuat opsi penyimpanan | menetapkan opsi per jenis data, masa simpan per jenis, biaya lima opsi tempat lakehouse, dan rencana lima langkah | tabel pada Elemen 3; `perbandingan-biaya-m4.md` di DSIC-SDG; `data/produk/latensi-produksi-*.json` | T, TL | lengkap, kompatibilitas S3 bucket Lightsail belum diperiksa |

Jenis bukti: **L** langsung (artefak yang berjalan), **TL** tidak langsung (hasil terukur, laporan), **T** tambahan (dokumen tata kelola, surat).

## Kedudukan langkah ini

Analisis ini disusun 20 Oktober 2026 setelah fase akuisisi M2 selesai, sebelum lakehouse M4 dibangun. Angka volume diukur dengan `make m2-volume` dan tersimpan di `data/gudang/volume.json`; jumlah rilis dari registri `dim_rilis` (`make m2-registri`). Keputusan tempat lakehouse sengaja ditunda sampai perbandingan biaya selesai, dan tidak ada instance atau bucket yang dibuat sebelum biayanya disetujui.

## Elemen 1. Jumlah data

**KUK 1.1 Jumlah data.** Snapshot 20 Oktober 2026 mencakup 12 sumber. Setiap berkas raw diverifikasi cocok dengan sha256 di manifest sebelum diukur.

| Sumber | Raw (MB) | Berkas raw | Bronze (MB) | Rilis tercatat | Jenis bukti tanggal |
| --- | ---: | ---: | ---: | ---: | --- |
| BPS (snapshot 17 dan 20 Okt, publikasi TPB) | 58,1 | 160 | 0,7 | 73 | pembaruan sumber, rilis resmi |
| BPS Berita Resmi Statistik | 8,2 | 215 | 6,0 | 2.143 | rilis resmi |
| ILOSTAT | 5,5 | 45 | 0,2 | 26 | pembaruan sumber |
| Bank Dunia WDI | 8,2 | 10 | 0,3 | 1 | pembaruan sumber |
| Arsip WDI (142 versi) | 26,0 | 145 | 9,1 | 142 | rilis resmi |
| Basis data SDG PBB | 13,2 | 19 | 0,4 | 1 | rilis resmi |
| Arsip basis data SDG PBB (48 rilis) | 14,9 | 49 | 14,0 | 48 | rilis resmi |
| WHO | 1,6 | 45 | 0,3 | 42 | pembaruan sumber |
| BNPB | 3,9 | 116 | 1,4 | 113 | pembaruan sumber |
| SIPSN | 2,6 | 11 | 0,1 | 2 | tanggal unduh |
| SIGN-SMART | 0,2 | 29 | 0,1 | 28 | tanggal unduh |
| KKP | 0,2 | 45 | 0,3 | 43 | tanggal unduh |
| **Jumlah** | **142,5** | **889** | **32,7** | **2.662** | |

Bronze memuat 1.607.907 baris dalam 780 berkas Parquet; dua sumber arsip menyumbang paling banyak (arsip WDI 848.794 baris, arsip SDG PBB 628.035 baris). Manifest yang di-commit berukuran 3,7 MB dalam 16 berkas. Angka di atas belum termasuk tiga hal.

- **Payload asli yang tidak disimpan utuh: 2,63 GB.** Ini 91 berkas arsip global PBB dan Bank Dunia yang hanya disimpan ekstrak Indonesianya. Arsip WDI juga disimpan termampatkan: 1,17 GB JSON menjadi 26 MB.
- **Data rujukan M1** (`artefak/referensi`, 0,7 MB) dan Gold paket v3 (17 MB).
- **Berkas unduhan tangan BNPB dan Bappenas** yang belum terkumpul (`docs/gudang/unduh-tangan.md` di DSIC-SDG).

**KUK 1.2 Perkiraan pertumbuhan.** Frekuensi rilis tidak ditebak, tetapi diukur dari registri rilis 2021–2026.

| Sumber | Rilis per tahun (terukur) | Tambahan per rilis | Perkiraan per tahun |
| --- | --- | --- | --- |
| Arsip WDI | 5–8 versi | 0,18 MB raw, 0,06 MB Bronze | sekitar 2 MB |
| Arsip SDG PBB | 5–10 rilis | 0,3 MB raw, 0,3 MB Bronze; unduhan sementara sekitar 68 MB per rilis | sekitar 6 MB disimpan, 0,7 GB lalu lintas |
| BPS (snapshot bulanan 76 tabel) | 12 snapshot | sekitar 8 MB bila disalin utuh | sekitar 100 MB tanpa deduplikasi |
| BRS | sekitar 90 rilis | daftar ditarik ulang 8 MB, atau hanya halaman baru | 10–100 MB |
| Sumber sektoral | 1–4 snapshot | kurang dari 5 MB | kurang dari 20 MB |
| Berita (M5) | harian | belum diukur | ditaksir pada M5 sebelum jalan |

Tanpa berita, pertumbuhan diperkirakan 150–250 MB per tahun. Pengurang terbesar adalah deduplikasi isi pada snapshot BPS (rencana langkah 2 pada KUK 3.4).

## Elemen 2. Rencana volume data

**KUK 2.1 Volume menurut arsitektur.**

| Lapis | Format | Volume 20 Okt | Catatan |
| --- | --- | ---: | --- |
| Raw | berkas asli (JSON, CSV, XLSX, PDF, tar.gz, csv.gz) | 142,5 MB | hanya bertambah; tidak di-commit; diverifikasi terhadap manifest |
| Manifest dan registri rilis | JSON, CSV | 3,7 MB | di-commit |
| Bronze | Parquet zstd, serba teks | 32,7 MB | dapat dibangun ulang dari raw |
| Silver dan Gold (M3–M4) | Iceberg | ditaksir 30–60 MB | Bronze dikurangi baris kosong dan duplikat, ditambah kunci kanonik |
| Sajian (SQLite, paket level, KG) | SQLite, JSON, Turtle | sekitar 25 MB | per versi paket |

**KUK 2.2 Kesesuaian dengan pertumbuhan.** Volume tiga tahun ke depan, termasuk pertumbuhan pada KUK 1.2, ditaksir di bawah 1 GB tanpa berita. Media mana pun pada opsi di Elemen 3 cukup menampungnya. Batas yang perlu diawasi bukan ukuran data, melainkan ruang kosong Mac tempat pengembangan (sekitar 7–10 GB pada 20 Oktober, 6,2 GiB saat uji operasi) dan memori komputasi.

**KUK 2.3 Perhitungan pertumbuhan.** Model linear sederhana cukup, karena setiap sumber punya laju rilis dan ukuran per rilis yang terukur.

```
V(t) = V0 + t × Σ (rilis_per_tahun_i × ukuran_per_rilis_i)
V0 ≈ 0,18 GB (raw + Bronze + manifest)
ΔV ≈ 0,15–0,25 GB/tahun tanpa berita; ≈ 0,05 GB/tahun dengan deduplikasi BPS
V(3 tahun) ≈ 0,6–0,9 GB
```

Lalu lintas unduhan lebih besar daripada volume simpan: sekitar 0,7 GB per tahun untuk arsip PBB saja. Ini relevan untuk kuota transfer instance di wilayah Sydney, yang hanya separuh kuota wilayah lain.

## Elemen 3. Opsi penyimpanan

**KUK 3.1 Opsi menurut jenis data.** Satu basis data untuk semuanya ditolak, karena jenis datanya menuntut sifat yang berbeda: Raw harus tidak pernah berubah, tabel analitik harus bervintage, sajian harus berlatensi rendah di server 4 GB.

| Jenis data | Opsi | Dipakai |
| --- | --- | --- |
| Payload mentah (dokumen JSON, XLSX, PDF) | penyimpanan objek (lokal berantarmuka S3, atau bucket Lightsail) | raw |
| Tabel analitik besar dan bervintage | format tabel terbuka di atas penyimpanan objek (Iceberg) | Bronze sampai Gold |
| Tabel kecil untuk sajian berlatensi rendah | RDBMS tertanam (SQLite) | pemeriksa level dan tool Bravais |
| Data operasional pemain | RDBMS server DSW (SQLite yang sudah ada) | tetap di server DSW |
| Graf pengetahuan | berkas RDF dan penyimpanan graf tertanam (Oxigraph) | SDG KG |
| Metadata dan manifest | berkas JSON di git; repositori metadata ringan (langkah 05) | manifest, `metadata.jsonld` |

Pilihan sajian diuji di produksi: memuat paket v4 (1.650 level) menambah memori 17,6 MB per pekerja API di Lightsail 4 GB, dari 44,2 MB menjadi 61,9 MB, dalam 0,13–0,14 detik pada tiga pengukuran (`data/produk/latensi-produksi-*.json`). Angka ini jauh di bawah ambang 150 MB yang ditetapkan untuk server yang sudah melayani DSW.

**KUK 3.2 Masa simpan.** Masa simpan mengikuti alasan, bukan ukuran.

| Data | Masa simpan | Alasan |
| --- | --- | --- |
| Raw | selamanya | syarat vintage: angka yang pernah terbit harus dapat dipanggil ulang |
| Payload global yang hanya diekstrak | tidak disimpan; sha256, ukuran, dan URL disimpan selamanya | ruang disk; dapat diunduh ulang dan diverifikasi |
| Manifest dan registri rilis | selamanya, di git | bukti asal |
| Bronze | snapshot terkini dan snapshot yang dirujuk Gold terbit | dapat dibangun ulang |
| Silver dan Gold | per versi paket yang pernah terbit | kesetaraan paket dan reproduksi artikel |
| Teks penuh berita | dibuang setelah ekstraksi | UU 28/2014; hanya metadata dan cuplikan disimpan |
| Data evaluasi pengguna | lima tahun lalu dimusnahkan | lembar persetujuan peserta (langkah 11) |

**KUK 3.3 Biaya.** Harga Lightsail diperiksa 20 Oktober 2026 dari halaman harga dan FAQ resminya. Lima opsi tempat lakehouse dihitung untuk masa 20 Oktober sampai 31 Desember 2026 (penyimpanan sekitar 2,4 bulan; komputasi M4–M8 52 hari, ditagih per jam).

| Opsi | Isi | Biaya sampai 31 Des | Kekurangan utama |
| --- | --- | ---: | --- |
| A. Mac saja | semua lapis di Mac | USD 0 | ruang kosong sekitar 10 GB; tidak ada salinan di luar Mac; tidak dapat dipakai bersama |
| B. Mac dan bucket | komputasi di Mac; raw, Bronze, manifest disalin ke bucket USD 1 | sekitar USD 2,4 | bucket hanya cadangan sampai kompatibilitas S3 diperiksa |
| C. Instance 8 GB dan bucket | lakehouse tanpa OpenMetadata selama M4–M8 | sekitar USD 75 + 2,4 | memori mungkin sempit untuk Trino dan komponen lain bersamaan |
| D. Instance 16 GB dan bucket | lakehouse tanpa OpenMetadata produksi selama M4–M8 | sekitar USD 144 + 2,4 | biaya sedang |
| E. Instance 32 GB dan bucket | lakehouse dan OpenMetadata produksi | sekitar USD 281 + 2,4 | paling mahal; melampaui kebutuhan data yang kecil |

Dua kesimpulan dari perhitungan ini. Pertama, biaya simpan dapat diabaikan: kurang dari 1 GB selama tiga tahun muat di bucket USD 1 per bulan, dan penyimpanan blok USD 0,10 per GB-bulan menjadi kurang dari USD 0,10 per bulan. Yang mahal adalah memori komputasi. Kedua, OpenMetadata menurut spesifikasi produksinya (sekitar 40 GiB untuk server, basis data, dan Elasticsearch) tidak muat pada instance 16 GB, sehingga opsi E hanya masuk akal bila OpenMetadata dipertahankan; keputusan menggantinya dengan repositori ringan (langkah 05) membuat opsi E tidak diperlukan. Server DSW yang ada (Lightsail 4 GB) tidak termasuk opsi karena memorinya tinggal sekitar 2,1 GB dan ia melayani produksi.

**KUK 3.4 Rencana penyimpanan.**

1. **Sampai M3.** Semua lapis di Mac. Salinan raw, manifest, dan Bronze ke bucket Lightsail USD 1 per bulan setelah biaya disetujui.
2. **Deduplikasi isi.** Snapshot BPS berikutnya menyimpan payload yang sha256-nya sama dengan snapshot sebelumnya sebagai rujukan, bukan salinan, sehingga pertumbuhan BPS turun dari sekitar 100 MB menjadi beberapa MB per tahun.
3. **M4.** Iceberg di atas penyimpanan objek pada simpul yang dipilih penanggung jawab (opsi C atau D). SQLite sajian tetap dikirim ke server DSW sebagai artefak.
4. **Pemantauan.** `make m2-volume` dijalankan setiap akhir fase. Peringatan bila ruang kosong Mac di bawah 5 GB atau volume melampaui taksiran KUK 2.3.
5. **Setelah M8.** Instance dimatikan; snapshot terakhir disimpan sebagai arsip, raw dan manifest tetap di bucket.

**Yang benar-benar terjadi pada M4 (21 Oktober 2026).** Pengembangan awal berjalan di lingkungan cloud pada 20 Oktober, lalu seluruh fase Silver, gudang, dan graf dijalankan ulang dari Raw di Mac (Apple Silicon 16 GB, Docker lewat Colima dengan VM 4 vCPU dan 8 GiB). Penyimpanan objeknya SeaweedFS berantarmuka S3 dengan katalog Iceberg REST, tanpa Nessie. Instance 8 atau 16 GB tidak dibuat. Rebuild penuh dari Raw memakan 338–366 detik dan kompilasi paket 15–16 detik dengan hash identik (`data/produk/uji-keterulangan.json`), sehingga lakehouse pada volume ini terbukti cukup dijalankan di satu mesin pengembangan.

**Data pendukung** (sudah ada di repositori):

- [`data/gudang/volume.json`](../../data/gudang/volume.json): bita dan jumlah berkas Raw, Bronze, dan manifest per sumber, serta baris Bronze per tabel, diukur 20 Oktober 2026 pukul 19:42 WIB.
- [`data/produk/uji-keterulangan.json`](../../data/produk/uji-keterulangan.json): waktu dan sidik dua rebuild gudang dan dua kompilasi paket di Mac.
- [`data/produk/latensi-produksi-1.json`](../../data/produk/latensi-produksi-1.json), [`-2`](../../data/produk/latensi-produksi-2.json), [`-3`](../../data/produk/latensi-produksi-3.json): memori pekerja API sebelum dan sesudah memuat paket v4 di server DSW.

## Catatan terbuka

- **Kompatibilitas S3 bucket Lightsail belum diperiksa.** FAQ Lightsail tidak menyatakan bucket memakai API S3, sehingga bucket baru boleh dianggap cadangan, belum gudang Iceberg. Salinan ke bucket juga belum dikonfirmasi dibuat.
- **Volume berita belum ditaksir** pada tabel pertumbuhan; ukuran alirannya baru diukur pada langkah 10 (GDELT seminggu 8,42 GB zip, tersimpan 18 MB).
- **Deduplikasi isi snapshot BPS belum dijalankan**, karena snapshot BPS kedua setelah 20 Oktober belum diambil.
- **Memori komponen lakehouse belum diukur dengan `docker stats`** seperti direncanakan; yang ada adalah bukti tidak langsung bahwa semuanya berjalan pada VM 8 GiB.
- **Pemantauan ruang kosong masih manual.** Ruang kosong Mac 6,2 GiB saat uji operasi sudah di bawah ambang peringatan 5 GB yang direncanakan bila dihitung dalam GB desimal; ini alasan mode alir wajib pada langkah 10.

## Catatan untuk wawancara asesor

Dokumen di repositori ini disusun dengan bantuan asisten AI (Claude). Keputusan tetap tanggung jawab saya. Pertanyaan yang harus bisa saya jawab tanpa membaca: mengapa tidak semua di satu database, mengapa Raw disimpan selamanya padahal payload global dibuang, dan mengapa biaya komputasi, bukan biaya simpan, yang menentukan pilihan.
