# 02. Rencana manajemen data

**Unit:** J.62DMS00.002.1 Merencanakan Manajemen Data

**Pertanyaan yang dijawab:** Siapa memutuskan apa, dengan prinsip apa, dan kapan?

**Yang saya kerjakan:** Saya menulis piagam tata kelola data Liga Lakehouse pada 20 Oktober 2026, sebelum gudang dibangun, yang memuat enam faktor penggerak terukur, visi, lima misi, tujuh prinsip, dan delapan kriteria keberhasilan yang dibekukan sampai 31 Desember 2026. Tanggung jawabnya saya tuangkan dalam matriks RACI (Responsible, Accountable, Consulted, Informed) 24 kegiatan × 10 peran dengan aturan satu penanggung gugat (A) per kegiatan, supaya pada setiap kegiatan selalu jelas siapa yang memutuskan. Kerangka waktunya adalah sepuluh fase M0–M9 dari 20 Oktober sampai 31 Desember 2026, dan status delapan faktor keberhasilan ditinjau di akhir fase.

| Elemen | Yang saya kerjakan | Bukti | Jenis | Status |
| --- | --- | --- | --- | --- |
| 1. Menetapkan faktor penggerak, visi, misi, dan prinsip tata kelola data | menurunkan enam faktor penggerak dari pengukuran dan dokumen yang ada, merumuskan visi dan lima misi, menetapkan tujuh prinsip dari DAMA-DMBOK beserta penerapannya, menilai kesiapan sepuluh proses internal, dan menetapkan delapan kriteria keberhasilan | tabel pada Elemen 1 di bawah; angka ketidaksesuaian dari naskah terpadu | T, TL | lengkap |
| 2. Menetapkan struktur dan tanggung jawab kegiatan tata kelola data | menyusun struktur tujuh peran internal dan empat pihak luar, lalu matriks RACI 24 kegiatan × 10 peran | `data/serkom/raci.csv`; bagan struktur di bawah | T | lengkap, pemilik domain masih simulasi |
| 3. Menetapkan kerangka waktu | menetapkan empat periode sasaran, aturan pembekuan kriteria, dan tata waktu M0–M9 | tabel pada Elemen 3 di bawah | T | lengkap, jadwal kelas evaluasi belum diputuskan |
| 4. Menetapkan faktor penentu keberhasilan operasional | menetapkan delapan faktor dengan ukuran dan target, lalu mencatat statusnya pada 20 Oktober dan setelah fase M4 | tabel pada Elemen 4; `data/gudang/m4_sidik_gold.json`, `m4_lineage.json`, `data/produk/uji-keterulangan.json` | T, TL | lengkap |

Jenis bukti: **L** langsung (artefak yang berjalan), **TL** tidak langsung (hasil terukur, laporan), **T** tambahan (dokumen tata kelola, surat).

## Kedudukan piagam

Piagam ini ditulis pada fase M0 (tata kelola dan izin) dan menjadi rujukan bagi langkah 01 (inventaris aset dengan steward) dan langkah 03 (arsitektur federasi). Statusnya masih draf karena menunggu dua keputusan penanggung jawab: pengisi peran pemilik domain dan jadwal kelas evaluasi. Bagian yang bergantung pada keputusan itu ditandai **[KEPUTUSAN]**, dan keadaannya per 24 Oktober 2026 dirangkum pada catatan terbuka.

## Elemen 1. Faktor penggerak, visi, misi, dan prinsip tata kelola data

**KUK 1.1 Faktor penggerak, visi, dan misi menurut domain bisnis.** Domain bisnis organisasi ini adalah statistik resmi untuk pendidikan: indikator SDG Indonesia dari produsen resmi disajikan sebagai bahan belajar dan penelitian. Faktor penggeraknya saya ambil dari hal yang sudah terukur atau terdokumentasi, bukan dari asumsi umum tentang pentingnya data.

| Faktor penggerak | Bukti | Respons tata kelola |
| --- | --- | --- |
| Statistik resmi direvisi dan nilai lama ditimpa di kanal daring | 33 dari 1.435 sel beririsan berbeda antara WebAPI dan publikasi TPB; 78,05 % ketidaksesuaian terjelaskan oleh vintage, metodologi, atau granularitas (naskah terpadu) | vintage menjadi dimensi data, bukan galat |
| Sumber bertambah dari satu produsen menjadi lebih dari sepuluh | rencana kerja gudang, Bagian 2 | model operasional federasi (langkah 03) |
| Tiga tujuan SDG tidak ada pada tingkat provinsi di BPS | katalog TPB: tujuan 12, 13, 14 tanpa indikator provinsi | sumber sektoral dengan kelas lisensi |
| Lisensi sumber berbeda-beda | rencana kerja gudang, Bagian 2.5 | kelas tayang A, A-SA, B, C |
| Asisten AI dapat menyebut angka tanpa sumber | kondisi tanpa tool pada harness keterikatan | guardrail "tanpa angka tanpa tool" dan provenans di setiap jawaban |
| Literasi data mahasiswa terbatas | survei Putra dan Kuncoro (2025): 23 % mahasiswa akrab dengan SDGs | kegunaan produk diukur lewat evaluasi pengguna |

**Visi.** Setiap angka indikator SDG resmi Indonesia yang pernah terbit dapat dipanggil ulang, ditelusuri sampai rilisnya, dan dijelaskan kepada pembelajar.

**Misi.**

1. Menyimpan setiap rilis dari setiap sumber tanpa menimpa.
2. Merekonsiliasi sumber yang berbeda dengan aturan yang dibekukan sebelum data dibandingkan, dan menyimpan alasannya.
3. Menerbitkan data product per pilar TPB dengan kontrak yang diuji.
4. Menyajikan data kepada pemain dan pemandu AI hanya dengan provenans.
5. Mengukur kualitas, ongkos, dan kegunaan setiap lapis secara terbuka.

**Prinsip tata kelola data.** Tujuh prinsip berikut diturunkan dari DAMA-DMBOK. Setiap prinsip dipasangkan dengan penerapannya, karena prinsip yang tidak punya bentuk teknis tidak akan ditegakkan.

| Prinsip | Penerapan |
| --- | --- |
| Data adalah aset dengan pemilik | setiap aset di inventaris langkah 01 mempunyai steward |
| Riwayat tidak dihapus | raw hanya bertambah; vintage bitemporal |
| Aturan sebelum data | aturan klasifikasi dan rekonsiliasi dibekukan sebelum perbandingan |
| Kepatuhan ditegakkan mesin | uji kontrak, pemeriksa server, guardrail |
| Hak produsen dihormati | kelas tayang menurut lisensi; izin tertulis untuk kelas B |
| Data pribadi seminimal mungkin | telemetri tanpa isi jawaban; hash untuk analisis; nama orang dibuang dari klaim berita |
| Dapat dibangun ulang | satu perintah dari raw; hash sama |

**KUK 1.2 Kesiapan proses internal.** Kesiapan dinilai per proses pada 20 Oktober 2026, dan celahnya dipetakan ke fase yang akan menutupnya.

| Proses | Kesiapan 20 Okt 2026 | Celah |
| --- | --- | --- |
| Akuisisi BPS dengan manifest | siap (H1, F1, snapshot 17 dan 20 Okt) | – |
| Store vintage dan kebijakan B0–B3 | siap (H6–H15) | baru dua kanal BPS |
| Kompilasi level dan uji kelayakan | siap (paket v1–v3) | – |
| Sajian produksi dan pemandu AI | siap (DSW rilis 0.4.13, Gelombang 1) | paket v3 belum dipasang |
| Lakehouse Iceberg dan Trino | teruji di satu simpul (H5, benchmark F5) | belum menjadi jalur utama kompilasi |
| Data rujukan wilayah dan indikator | sebagian (GeoJSON 38 provinsi, katalog TPB) | tanpa riwayat pemekaran dan padanan kode |
| Repositori metadata | belum (OpenMetadata ada di `infra/` tetapi belum dipakai) | M4 |
| Orkestrasi | belum (Makefile) | M4 |
| Izin lisensi sumber sektoral dan internasional | belum | M0 |
| Persetujuan etik evaluasi | belum | M0 |

**KUK 1.3 Kriteria masalah saat ini dan kriteria keberhasilan.** Setiap masalah ditulis sebagai keadaan yang terukur pada 20 Oktober, dan kriteria keberhasilannya sebagai keadaan yang dapat diperiksa pada 31 Desember 2026.

| Masalah saat ini (diukur) | Kriteria keberhasilan pada 31 Des 2026 |
| --- | --- |
| Gudang hanya memuat satu produsen | ≥ 8 sumber terunduh ulang dengan satu perintah, masing-masing dengan jenis bukti tanggal rilis |
| Tujuan 12, 13, 14 tanpa data provinsi | 17 tujuan mempunyai sedikitnya satu data product provinsi; cakupan jenis level dilaporkan per tujuan |
| Store vintage hanya 10,1 % sel Gold | setiap observasi Gold mempunyai `rilis_id` dan jenis bukti tanggal |
| Kode wilayah tidak berpadanan | dimensi wilayah tipe 2 lulus uji pada tiga kasus Papua dan SIGN-SMART |
| Tidak ada repositori metadata | setiap data product terdaftar dengan pemilik, kontrak, dan lineage |
| Kualitas dinilai ad hoc | kelulusan uji kontrak 100 % pada setiap rilis paket; laporan kualitas per sumber |
| Lisensi sumber kelas B tidak jelas | jawaban tertulis (izin atau tolak) dari setiap produsen kelas B, atau keputusan tercatat untuk tidak menayangkan |
| Evaluasi pengguna belum ada | n ≥ 60 pasangan pra–pasca lengkap pada produk v4 |

## Elemen 2. Struktur dan tanggung jawab kegiatan tata kelola data

**KUK 2.1 Struktur.** Struktur mengikuti model federasi yang dipilih pada langkah 01: aturan global di tim platform, isi data di pemilik domain, dan sistem produksi di operator DSW.

```
                     Koordinator Prodi Sains Data (sponsor)
                                   │
              Penanggung jawab penelitian dan pemilik produk
                         (Ardika Satria)
        ┌──────────────┬───────────┴────────┬───────────────────┐
   Tim platform    Pemilik domain ×4    Operator DSW     Penanggung jawab evaluasi
   (aturan global,  (Sosial, Ekonomi,   (server, akses,    (sesi, etik, anonimisasi)
    referensi,       Lingkungan,         cadangan)              │
    metadata,        Hukum dan                             Fasilitator sesi
    orkestrasi)      Tata Kelola)
                         │
                Steward sumber: nasional, internasional, sektoral, berita
```

Pihak luar: produsen data (BPS, Bank Dunia, ILO, UNSD, KLH/BPLH, BNPB, KKP, media) dikonsultasikan dan diberi tahu; komite etik menyetujui evaluasi; peserta diberi tahu.

**[KEPUTUSAN]** Pengisi peran pemilik domain. Pilihan (a): penanggung jawab sendiri, dan prinsip kepemilikan domain dinyatakan sebagai simulasi. Pilihan (b): empat kelompok mahasiswa Pergudangan Data, satu domain per kelompok, sebagai proyek kelas; kelompok itu dikeluarkan dari peserta evaluasi pengguna. Tim platform dan operator DSW dipegang penanggung jawab pada kedua pilihan.

**KUK 2.2 Tanggung jawab.** Matriks lengkap 24 kegiatan × 10 peran ada di `data/serkom/raci.csv` dengan kode R mengerjakan, A bertanggung gugat, C dikonsultasikan, dan I diberi tahu. Aturannya satu A per kegiatan; bila pengerja dan penanggung gugatnya sama, ditulis A/R. Ringkasan per peran:

| Peran | Tanggung jawab pokok |
| --- | --- |
| Penanggung jawab penelitian | bertanggung gugat atas semua kegiatan kecuali kontrak dan kualitas domain; izin, etik, anonimisasi, garam pseudonim, publikasi, pemusnahan data setelah lima tahun |
| Pemilik domain | kontrak dan ambang kualitas data product pilarnya; aturan rekonsiliasi lokal; menerima laporan kesalahan angka |
| Tim platform | aturan global, data rujukan, konektor, gudang, metadata, orkestrasi, kompilasi paket |
| Steward sumber | konektor, pemetaan Silver, dan hubungan dengan produsen untuk kelompok sumbernya |
| Operator DSW | pemasangan produksi, akses, cadangan, ekspor telemetri |
| Fasilitator sesi | sesi evaluasi dan pengumpulan persetujuan |

Tiga kegiatan terakhir pada matriks (22–24: garam pseudonim dan ekspor penelitian, pembayaran hadiah dan pengosongan nomor dompet, pemusnahan data peserta dan raw berita pada 2031) ditambahkan 26 Oktober 2026 mengikuti program pelindungan data pribadi pada langkah 11.

## Elemen 3. Kerangka waktu

**KUK 3.1 Jangka waktu menjalankan penggerak, visi, misi, dan membudayakan prinsip.**

| Periode | Sasaran |
| --- | --- |
| 20 Okt–3 Nov 2026 | prinsip, aturan global, dan data rujukan berlaku; setiap aset mempunyai steward |
| 3 Nov–30 Nov 2026 | semua sumber masuk lewat konektor; kontrak diuji otomatis; produk v4 terpasang |
| 1–31 Des 2026 | evaluasi pengguna; naskah dikirim; portofolio lengkap |
| 2027 | pemeliharaan: snapshot berkala SIPSN dan sumber tanpa cap tanggal; peninjauan prinsip setiap semester |

**KUK 3.2 Jangka waktu menentukan kriteria keberhasilan.** Kriteria pada KUK 1.3 ditetapkan pada M0 (20–25 Oktober) dan dibekukan bersama praregistrasi M3. Ambang yang menyangkut hasil penelitian, yaitu κ antaranotator, kelengkapan lineage, dan SUS, tidak boleh diubah setelah data terkait dilihat. Aturan ini sejalan dengan prinsip "aturan sebelum data" pada Elemen 1.

**KUK 3.3 Tata waktu pelaksanaan.**

| Fase | Tanggal | Keluaran tata kelola |
| --- | --- | --- |
| M0 | 20–25 Okt | piagam ini, RACI, inventaris, surat izin, surat etik |
| M1 | 21 Okt–3 Nov | data rujukan dan induk; standar metadata |
| M2 | 27 Okt–10 Nov | konektor dan registri rilis; rencana kapasitas |
| M3 | 3–17 Nov | aturan rekonsiliasi beku; laporan kualitas awal |
| M4 | 10–24 Nov | gudang, data product berkontrak, repositori metadata |
| M5 | 3–28 Nov | SDG KG dan alur berita |
| M6 | 17–30 Nov | produk v4 di produksi |
| M7 | 24 Nov–14 Des | wawancara kognitif dan evaluasi pengguna **[KEPUTUSAN jadwal kelas]** |
| M8 | 8–31 Des | naskah |
| M9 | sepanjang, ditutup 31 Des | portofolio |

Tanggal di atas adalah rencana pada 20 Oktober. Pelaksanaannya berjalan jauh lebih cepat: fase M1–M5 pada sisi gudang selesai 20–21 Oktober dan pengujiannya 21–23 Oktober (lihat langkah 04–10), sehingga tata waktu ini kini terutama mengikat fase M6–M9.

## Elemen 4. Faktor penentu keberhasilan operasional

**KUK 4.1 Faktor target yang berkelanjutan.** Delapan faktor berikut masing-masing punya ukuran yang dapat dihitung dari gudang atau produk, bukan dari penilaian subjektif.

| Faktor | Ukuran | Target |
| --- | --- | --- |
| Kelengkapan riwayat | proporsi observasi Gold dengan `rilis_id` dan jenis bukti tanggal | 100 % |
| Kepatuhan kontrak | uji kontrak lulus per rilis paket | 100 % |
| Ketertelusuran | kelengkapan lineage dari level atau klaim sampai payload mentah | ≥ 0,99 |
| Keterbangunan ulang | hash Gold dan paket sama pada rebuild dari raw | sama |
| Kesegaran | jeda antara rilis sumber dan masuk Bronze, per sumber berjadwal | ≤ 7 hari setelah M2 |
| Kepatuhan lisensi | sumber kelas B dan C yang tampil di game | 0 |
| Pelindungan data pribadi | kolom nama orang di catatan klaim; username dalam berkas analisis | 0 |
| Kemudahan menambah sumber | waktu dan baris kode untuk satu sumber baru lewat platform | diukur, tanpa target awal |

**KUK 4.2 Status target.** Status dicatat dua kali: saat piagam ditulis (20 Oktober) dan setelah gudang dibangun dan diuji (24 Oktober). Kolom kedua hanya memuat angka yang ada di `data/`.

| Faktor | Status 20 Okt 2026 | Status 24 Okt 2026 |
| --- | --- | --- |
| Kelengkapan riwayat | belum tercapai: 10,1 % sel Gold v2 bervintage, sisanya hanya tanggal snapshot | setiap fakta Gold berkunci (sumber, rilis, seri, wilayah, periode, rincian), lihat langkah 09; proporsi belum dihitung ulang sebagai angka tersendiri |
| Kepatuhan kontrak | tercapai untuk paket v1–v3: pemeriksa server menerima 871 dari 871 jawaban acuan v3 | 139 node dbt lulus pada rebuild (`m4_sidik_gold.json`) |
| Ketertelusuran | tercapai pada sel bervintage paket v2: 446 dari 446 | lineage 166 simpul dan 320 sisi, tidak ada data product tanpa jalur ke raw (`m4_lineage.json`) |
| Keterbangunan ulang | tercapai pada store vintage dan paket: H15b, hash paket sama pada dua kompilasi | sidik Gold `657df68e…` identik pada empat rebuild dari raw, 21 Oktober (`m4_sidik_gold.json`, `uji-keterulangan.json`) |
| Kesegaran | belum diukur: konektor terjadwal belum ada | belum diukur; konektor ada tetapi belum berjadwal |
| Kepatuhan lisensi | tercapai: game hanya memakai BPS | tercapai; kelas tayang ditegakkan saat paket dibangun (langkah 03) |
| Pelindungan data pribadi | tercapai untuk telemetri; alur berita belum ada | pseudonim ekspor berjalan di produksi, nama orang dibuang dari klaim berita (langkah 11) |
| Kemudahan menambah sumber | belum diukur: platform belum ada | belum diukur sebagai angka |

**Data pendukung** (sudah ada di repositori):

- [`data/serkom/raci.csv`](../../data/serkom/raci.csv): matriks RACI 24 kegiatan × 10 peran, dengan kolom fase per kegiatan. Identik dengan sumbernya di repositori penelitian Ardika (`docs/serkom/J.62DMS00.002.1/`); sidiknya tercatat di `data/SIDIK.txt`.
- [`data/gudang/m4_sidik_gold.json`](../../data/gudang/m4_sidik_gold.json), [`data/gudang/m4_lineage.json`](../../data/gudang/m4_lineage.json), [`data/produk/uji-keterulangan.json`](../../data/produk/uji-keterulangan.json): dasar kolom status 24 Oktober pada KUK 4.2.

## Catatan terbuka

- **Pemilik domain belum diputuskan secara resmi.** Sampai 24 Oktober keempat domain pilar saya pegang sendiri, yang berarti pilihan (a) berjalan de facto. Pilihan (b) masih terbuka bila kelas Pergudangan Data dapat dijadwalkan; bila dipilih, kelompok itu harus dikeluarkan dari peserta evaluasi.
- **Jadwal kelas evaluasi (M7) belum ditetapkan**, dan bergantung pada persetujuan etik yang suratnya masih draf (langkah 11).
- **Dua faktor belum pernah diukur:** kesegaran, karena konektor belum berjadwal, dan kemudahan menambah sumber, karena belum ada sumber baru yang ditambahkan setelah platform berdiri.
- **Kelengkapan riwayat belum dihitung ulang** sebagai proporsi setelah gudang dibangun. Yang tersedia baru bukti struktural dari skema fakta pada langkah 09.
- **Baris kesiapan 20 Oktober tidak disegarkan.** Tabel KUK 1.2 dan kolom status pertama KUK 4.2 sengaja dibiarkan sebagai potret awal, supaya kemajuan dapat dibaca dari selisihnya.
