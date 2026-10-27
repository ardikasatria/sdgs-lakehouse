# 11. Pelindungan data pribadi

**Unit:** J.62PDP00.011.1 Menerapkan Program Kerja Pelindungan Data Pribadi

**Pertanyaan yang dijawab:** Data pribadi siapa yang diproses, dengan dasar apa, dan bagaimana dilindungi?

**Yang saya kerjakan:** Dua alur memproses data pribadi pada proyek ini: korpus berita, yang dapat memuat nama orang yang diberitakan, dan Laga Liga Lakehouse daring, yang sejak 23 Oktober 2026 mengolah data peserta sungguhan (akun, persetujuan, jawaban tes, telemetri, nomor dompet hadiah). Untuk keduanya saya menerapkan prinsip UU 27/2022 sebagai pagar di kode, bukan sebagai imbauan: kolom nama dan kutipan berita tidak pernah diambil, email Google tidak disimpan, nomor dompet dipisah dan dikosongkan setelah dibayar, dan ekspor penelitian mengganti identitas akun dengan kode HMAC bergaram yang hanya memuat peserta yang setuju, terpasang di produksi sejak 24 Oktober 2026. Penilaian dampak ringkas menilai sembilan risiko, dan risiko tertingginya bukan teknis: nomor persetujuan etik resmi belum terbit, sehingga data peserta belum dianalisis.

| Elemen | Yang saya kerjakan | Bukti | Jenis | Status |
| --- | --- | --- | --- | --- |
| 1. Mengimplementasikan kebijakan PDP | menerapkan lima prinsip UU 27/2022 pada alur berita; menetapkan lingkup tujuan evaluasi, jenis data pribadi per aliran, dan mekanisme persetujuan, tes, hadiah; menulis DPIA ringkas sembilan risiko | tabel pada Elemen 1; `dpia-ringkas.md` di repositori penelitian Ardika | T | ada, nomor etik resmi belum terbit |
| 2. Mengimplementasikan kebijakan data terkait PDP | kebijakan simpan berita (metadata dan URL saja, raw lima tahun); masa simpan data peserta lima tahun; peran pemegang garam, pembayar hadiah, dan pemusnah data di RACI | `data/serkom/raci.csv` kegiatan 3, 18, 22–24; `m5-akuisisi-berita.md` dan lembar persetujuan di repositori penelitian Ardika | T | ada |
| 3. Mengimplementasikan prosedur pemrosesan data pribadi | persetujuan sebelum bermain, penarikan data sampai 7 hari sesudah Laga, verifikasi lima cek oleh admin, pengosongan nomor dompet | modul survei di repositori DSW (`sdg_survei.py`) | L | ada |
| 4. Mengimplementasikan ketentuan pengungkapan kepada pihak lain | ekspor penelitian memakai `hash_peserta` HMAC bergaram dan hanya peserta yang setuju; nomor dompet tidak ikut ekspor; hasil hanya agregat | `sdg_survei_http.py` dan 17 uji di repositori DSW, commit `632f206e` di produksi | L | ada |
| 5. Mengimplementasikan teknologi terkait PDP | hash nama akun Google, sesi berlingkup, tabel hadiah terpisah, penyamaran nomor, pagar kolom konektor berita dan uji unitnya; tanpa biaya tambahan | `masuk_google.py` (DSW), `test_gudang_konektor_berita.py` (tersalin di `code/`) | L | ada |

Jenis bukti: **L** langsung (artefak yang berjalan), **TL** tidak langsung (hasil terukur, laporan), **T** tambahan (dokumen tata kelola, surat).

## Kedudukan langkah ini

Unit ini berasal dari SKKNI 103/2023 dan termasuk dalam skema Insinyur Data LSP DKS. Berbeda dari sepuluh unit lain, unit ini menuntut program pelindungan data pribadi yang benar-benar diterapkan di organisasi, bukan dirancang. Karena itu bukti terkuatnya adalah Laga Liga Lakehouse daring (Bagian 3 dan 4 di bawah), yang memproses data peserta sungguhan di server produksi, sedangkan alur korpus berita menjadi bukti pendukung. Bagian berita disusun 20 Oktober 2026 pada fase M5, dan bagian Laga, pseudonim ekspor, serta DPIA dilengkapi 24 Oktober 2026. Elemen dan KUK dicocokkan dengan lampiran resmi SKKNI 103/2023 pada 24 Oktober. Aspek kritis resminya adalah ketepatan melaksanakan mekanisme pemrosesan data pribadi sesuai peraturan perundang-undangan; dasar hukumnya UU 27/2022 tentang Pelindungan Data Pribadi, serta UU 28/2014 Pasal 43 huruf c dan Pasal 44 ayat (1) huruf a untuk metadata berita.

Satu hal perlu ditegaskan sejak awal: repositori ini tidak memuat data pribadi peserta mana pun. Data peserta hanya ada di basis data DSW di server produksi, dan yang keluar dari sana hanya ekspor ber-pseudonim ke folder analisis peneliti, bukan ke repositori.

## Elemen 1. Kebijakan PDP

**KUK 1.1 Prinsip PDP.** Lima prinsip UU 27/2022 diterapkan pada alur berita, masing-masing dengan wujud yang dapat diperiksa di kode atau manifest.

| Prinsip | Penerapan |
| --- | --- |
| Pembatasan tujuan | korpus berita hanya dipakai untuk memeriksa klaim angka indikator; tidak untuk profil orang atau media |
| Minimisasi data | hanya metadata dan URL; teks artikel tidak pernah diambil; kolom nama dan kutipan GDELT tidak dipilih |
| Keamanan | kunci BigQuery di luar repositori dan tidak pernah di-commit; pola nama rahasia ditolak di manifest oleh pembangun manifest |
| Transparansi sumber | setiap rilis berita punya manifest dengan sha256, tanggal, dan URL asal; robots.txt yang terbaca disimpan |
| Tidak ditayangkan | ketiga sumber berita berstatus `boleh_tayang = false` di `dim_sumber`; nilai klaim hanya untuk riset internal |

**KUK 1.2 Lingkup tujuan.** Pemrosesan data peserta Laga terbatas pada evaluasi pengguna produk v4: mengukur hasil belajar (tes pra dan pasca), kegunaan (SUS), pengalaman bermain (MEEGA+), dan hubungannya dengan telemetri permainan. Tidak ada keputusan otomatis berakibat hukum dan tidak ada data spesifik, tetapi penskoran tes dan penggabungan telemetri dengan jawaban mendekati evaluasi sistematis atas peserta, sehingga penilaian dampak tetap ditulis walaupun skalanya kecil.

**KUK 1.3 Jenis data pribadi.** Inventaris disusun per aliran, baik untuk berita maupun Laga.

| Aliran | Data pribadi yang mungkin ada | Perlakuan |
| --- | --- | --- |
| GDELT GKG | nama orang (`V2Persons`, `AllNames`), kutipan (`Quotations`) | kolom tidak pernah dipilih dalam kueri BigQuery maupun saat menyaring berkas mentah; diuji |
| RSS | nama orang di judul dan ringkasan butir aliran | hanya judul dan ringkasan paling banyak dua kalimat (400 karakter); teks penuh dibuang sebelum ditulis ke raw |
| CC-NEWS | nama orang di halaman artikel | hanya `<title>` dan atribut `lang` dari 64 KB pertama; badan respons tidak ditulis ke disk |
| Klaim berita | nama pejabat atau narasumber di kalimat sumber | tupel klaim tidak memuat bidang nama; kalimat paling banyak dua dan dipotong 400 karakter |
| Lembar anotasi | identitas anotator | lembar diberi label A dan B, bukan nama |
| Akun Laga | nama pengguna situs atau akun Google | akun game terpisah; email Google tidak disimpan; nama pengguna `google-` ditambah sha256 dari pengenal Google sehingga tidak dapat ditebak dari email |
| Persetujuan, tes, kuesioner | keputusan, versi lembar, waktu, jawaban pra dan pasca, SUS, MEEGA+, jawaban terbuka | tabel `sdg_survei_*`; ekspor hanya untuk peserta yang setuju |
| Mode Kueri dan Bravais | teks pertanyaan dan SQL; percakapan dengan Bravais | teks pertanyaan disimpan untuk analisis dan peserta diminta tidak menulis data pribadi; percakapan Bravais tidak disimpan sebagai riwayat, permintaan ke penyedia model tanpa penyimpanan, tembolok jawaban paling lama 24 jam, diungkap di lembar persetujuan |
| Hadiah | nomor GoPay atau DANA | tabel terpisah; tampil disamarkan; dikosongkan saat klaim dibayar atau ditolak; tidak ikut ekspor |

**KUK 1.4 Mekanisme pemrosesan.** Urutannya persetujuan, lalu tes dan permainan, lalu hadiah: lembar informasi tampil sebelum bermain, keputusan beserta versi lembar dan waktunya tercatat, dan klaim hadiah diverifikasi admin dengan lima cek sebelum dibayar. Penilaian dampak ringkas (DPIA) mengikuti kerangka Pasal 34 UU 27/2022: pemrosesan dideskripsikan per alur dengan subjek, data, dasar, dan lokasinya; kebutuhan dan proporsinya diperiksa; lalu sembilan risiko dinilai kemungkinan dan dampaknya beserta pengurangan dan sisa risikonya.

| No | Risiko | Pengurangan yang sudah berjalan | Sisa |
| --- | --- | --- | --- |
| R1 | data peserta dikumpulkan sebelum persetujuan etik resmi terbit; lembar menampilkan nomor sementara | data hanya untuk evaluasi; belum ada analisis atau publikasi; peserta dapat menarik data sampai 7 hari sesudah Laga | **tinggi**: keputusan pemilik dibutuhkan |
| R2 | berkas analisis dapat dikaitkan kembali ke akun | HMAC-SHA256 bergaram; garam hanya di environment server; ekspor ditolak bila garam belum diset | rendah: garam diperlakukan setara kredensial |
| R3 | nomor dompet bocor | tabel terpisah; tampil disamarkan; izin khusus; dikosongkan saat dibayar atau ditolak; tidak ikut ekspor (diuji) | rendah |
| R4 | identitas Google terhubung dengan akun mahasiswa | akun game terpisah; email tidak disimpan; sesi berlingkup (403 di luar daftar rute) | rendah |
| R5 | peserta menulis data pribadi di Mode Kueri atau jawaban terbuka | peserta diminta tidak menulis data pribadi; jawaban terbuka dibaca peneliti sebelum dikutip | sedang: belum ada penyaring otomatis |
| R6 | percakapan Bravais tersimpan di penyedia model | permintaan tanpa penyimpanan; tanpa riwayat; tembolok paling lama 24 jam; diungkap di lembar | rendah |
| R7 | nama pejabat atau narasumber di judul dan ringkasan RSS | paling banyak dua kalimat; sumber berita tidak tayang; tupel klaim tanpa nama | rendah sampai sedang: penyaringan nama belum dipasang |
| R8 | data disimpan lebih lama dari tujuannya | masa simpan ditetapkan untuk data peserta dan raw berita | rendah, dengan syarat pemusnahan dijadwalkan |
| R9 | garam hilang sehingga unduhan lama dan baru tidak dapat digabung | runbook melarang mengganti garam selama analisis; cadangan environment di server | rendah: salinan garam di pengelola kata sandi peneliti masih harus dibuat |

## Elemen 2. Kebijakan data terkait PDP

**KUK 2.1 dan 2.2 Kebijakan dan komponennya.** Kebijakan simpan berita menetapkan apa yang disimpan (metadata, URL, sha256, judul dan ringkasan pendek), apa yang tidak (teks artikel, nama, kutipan), dan pagar di kode yang menegakkannya. Masa simpan ditetapkan per jenis data.

| Data | Masa simpan | Sesudahnya |
| --- | --- | --- |
| Data peserta (persetujuan, jawaban, telemetri, ekspor) | lima tahun untuk verifikasi publikasi, sesuai lembar persetujuan | dimusnahkan; yang tinggal hanya angka agregat di naskah |
| Nomor dompet | sampai klaim dibayar atau ditolak | dikosongkan otomatis |
| Raw berita (GDELT, RSS, CC-NEWS) | lima tahun sejak diambil (keputusan 24 Oktober 2026) | raw dimusnahkan; manifest (sha256, ukuran, URL asal, tanggal) tetap disimpan sebagai jejak |
| Garam pseudonim | selama masa simpan data peserta | dihapus bersama data peserta sehingga kode tidak dapat dihitung ulang |

**KUK 2.3 Peran dan tanggung jawab.** Lima kegiatan PDP ada di matriks RACI langkah 02, semuanya dengan penanggung jawab penelitian sebagai A/R: mengajukan persetujuan etik (kegiatan 3, komite etik dikonsultasikan), menangani permintaan penarikan data peserta (18, peserta dikonsultasikan, komite etik diberi tahu), memegang garam pseudonim dan mengunduh ekspor penelitian (22), membayar hadiah dan mengosongkan nomor dompet (23, peserta diberi tahu), serta memusnahkan data peserta dan raw berita setelah lima tahun (24, dijadwalkan 2031). Operator DSW dikonsultasikan pada keempat kegiatan yang menyentuh server.

## Elemen 3. Prosedur pemrosesan data pribadi

**KUK 3.1 sampai 3.3.** Prosedur berjalan di modul survei repositori DSW dan di produksi Lightsail.

- **Persetujuan sebelum bermain.** Lembar informasi dan persetujuan versi 4 tampil sebelum peserta dapat bermain; keputusan, versi lembar, dan waktu tercatat di `sdg_survei_persetujuan`.
- **Penarikan data.** Tombol "Tarik data saya" menghapus jawaban pra dan pasca serta klaim hadiah yang belum dibayar; persetujuan tinggal sebagai catatan penarikan. Penarikan boleh sampai 7 hari sesudah Laga selesai.
- **Verifikasi hadiah.** Klaim 30 peserta pertama yang lolos diverifikasi admin dengan lima cek sebelum dibayar; nomor dompet dikosongkan saat klaim dibayar atau ditolak.
- **Pelaksana.** Penanggung jawab penelitian memegang persetujuan etik, penarikan, garam, dan pembayaran; operator DSW memasang dan menjaga server; fasilitator sesi mengumpulkan persetujuan pada sesi luring bila ada.

## Elemen 4. Pengungkapan kepada pihak lain

**KUK 4.1 dan 4.2.** Data peserta tidak dibagikan ke luar tim, dan yang keluar dari server hanya ekspor penelitian dengan ketentuan berikut. Lembar persetujuan menjanjikan bahwa username diganti kode hash satu arah sebelum analisis. Janji ini dijalankan oleh server, bukan bergantung pada kehati-hatian peneliti: ekspor `peserta.csv`, `jawaban-pra.csv`, dan `jawaban-pasca.csv` mengganti `user_id` dan `username` dengan satu kolom `hash_peserta`, yaitu HMAC-SHA256 dengan garam dari environment server (minimal 32 karakter). Kode yang sama dipakai di semua berkas ekspor, dan ekspor ditolak bila garam belum diset, sehingga tidak ada kunci bawaan di kode. Saat meninjau kode sebelum pemasangan, `peserta.csv` ternyata masih memuat baris akun yang menolak atau menarik persetujuan; isinya hanya kode dan waktu, tetapi tetap tidak sesuai janji lembar, sehingga baris itu disaring dan jumlahnya hanya terbaca di ringkasan panel admin. Nomor dompet tidak pernah ikut ekspor (diuji). Hasil yang dipublikasikan hanya agregat di naskah.

**Pemasangan di produksi.** Setelah 17 uji modul survei lulus, DSW `632f206e` dipasang di Lightsail pada 24 Oktober 2026 pukul 08.58 UTC. Garam 64 heksadesimal dibuat langsung di server dan ditambahkan ke environment tanpa dicetak ke terminal; kedua pekerja API memuat garam, kode yang dihasilkan 16 heksadesimal, endpoint level tetap 200, dan ekspor tanpa login ditolak 401. Cadangan paket dan environment sebelumnya disimpan di server untuk kembali bila perlu.

## Elemen 5. Teknologi terkait PDP

**KUK 5.1 dan 5.2.** Teknologi yang dipakai semuanya berjalan di server yang sudah ada tanpa biaya tambahan, dan diprioritaskan menurut risiko di DPIA.

| Risiko yang ditangani | Teknologi | Tempat |
| --- | --- | --- |
| R4 identitas Google | akun game terpisah; nama pengguna `google-` + sha256 pengenal; email tidak disimpan; sesi berlingkup dengan daftar rute | `masuk_google.py` (DSW) |
| R2 berkas analisis dikaitkan ke akun | HMAC-SHA256 bergaram pada ekspor; garam di environment server; tolak ekspor tanpa garam | `sdg_survei_http.py` (DSW) |
| R3 nomor dompet | tabel `sdg_hadiah` terpisah; penyamaran di panel; pengosongan otomatis; izin khusus | `sdg_survei.py` (DSW) |
| R7 nama di berita | pemotong dua kalimat 400 karakter; pembuang HTML; pagar panjang kolom; kolom nama dan kutipan GDELT tidak dipilih | `berita_umum.py`, konektor `gdelt`, `rss`, `ccnews` (tersalin di `code/`) |
| R6 percakapan Bravais | permintaan ke penyedia model tanpa penyimpanan; tanpa riwayat; tembolok 24 jam | layanan Bravais (DSW) |
| keamanan rahasia | kunci API di luar repositori; pola rahasia ditolak di manifest | `akuisisi/inti.py` (tersalin di `code/`) |

Pagar di konektor berita diuji unit: nama orang dan kutipan GDELT tidak terbawa, teks penuh RSS dibuang dari raw, dan tidak ada kolom Bronze di atas 600 karakter.

**Data pendukung** (sudah ada di repositori):

- [`data/serkom/raci.csv`](../../data/serkom/raci.csv): kegiatan 3, 18, 22, 23, dan 24 beserta peran yang dikonsultasikan dan diberi tahu.

Berkas bukti lain untuk langkah ini sengaja tidak ada di repositori ini: kode modul survei dan masuk Google ada di repositori DSW yang privat, konektor berita tersalin di `code/`, dan lembar persetujuan serta DPIA ringkas di `docs/serkom/` repositori penelitian Ardika. Data peserta tidak pernah disalin ke mana pun selain server produksi.

## Catatan terbuka

- **Nomor persetujuan etik resmi belum terbit** (R1, risiko tertinggi). Lembar persetujuan menampilkan nomor sementara "001" dari konfigurasi `game.sdg.etik_nomor`. Data peserta belum dianalisis. Dua pilihan menunggu keputusan penanggung jawab penelitian bersama komite etik: mengganti teks status etik di lembar menjadi "sedang diajukan" dan menahan analisis sampai nomor terbit, atau menghentikan sementara pengumpulan survei.
- **Salinan garam di luar server belum dibuat** (R9). Garam hanya ada di environment server dan cadangannya; pemilik harus menyalinnya ke pengelola kata sandi, bukan ke repositori.
- **Penyaring nama di RSS belum dipasang** (R7); risikonya diterima karena sumber berita tidak ditayangkan.
- **Penyaring otomatis untuk data pribadi yang ditulis peserta** di Mode Kueri atau jawaban terbuka belum ada (R5).
- **Pemusnahan terjadwal belum dicatat di kalender**; tanggalnya ditetapkan saat analisis selesai.
- **Surat etik dan lembar persetujuan masih draf** di `docs/serkom/surat/` repositori penelitian Ardika dan belum diajukan; folder `bukti/surat/` di repositori ini masih kosong sampai surat ditulis ulang tanpa data pribadi.

## Catatan untuk wawancara asesor

Dokumen di repositori ini disusun dengan bantuan asisten AI (Claude). Keputusan tetap tanggung jawab saya. Pertanyaan yang harus bisa saya jawab tanpa membaca: data pribadi apa yang diproses dan siapa yang bisa melihatnya, mengapa pseudonim dijalankan server dan bukan oleh peneliti saat mengolah berkas, apa yang terjadi bila peserta menarik data, dan mengapa saya memilih tidak menganalisis data sebelum nomor etik terbit padahal datanya sudah ada.
