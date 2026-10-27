# 5. Keterbatasan Bukti dan Tindak Lanjut

::: {custom-style="Kotak"}
Delapan keterbatasan bukti dinyatakan di bab ini agar penilaian didasarkan pada keadaan yang sebenarnya: kepemilikan domain yang masih simulasi, big data tanpa klaster terdistribusi, nomor persetujuan etik yang belum terbit, surat izin yang belum dikirim, repositori metadata versi ringan, cakupan pemeriksaan klaim berita, dua Gold dengan sidik berbeda, dan kode asal yang berada di repositori privat. Bagian 5.2 memuat pekerjaan yang tersisa per langkah sampai penutupan portofolio pada 31 Desember 2026.
:::

## 5.1 Keterbatasan bukti

1. **Kepemilikan domain masih simulasi.** Keempat domain pilar dipegang oleh asesi sendiri. Sisi teknis federasi sudah terbukti, karena aturan global ditegakkan otomatis tanpa pelanggaran. Namun, sisi organisasinya, yang menurut literatur data mesh justru paling sulit, belum mempunyai bukti. Keterbatasan ini relevan untuk langkah 01–03.
2. **Big data tanpa klaster terdistribusi.** Pemrosesan bervolume besar dilakukan secara streaming dengan Python, dan keputusan tidak memakai Spark didukung uji pembanding: pada skala gudang ini Spark lokal hanya lebih cepat kurang dari satu detik per langkah, sedangkan pada jalur berita batasnya jaringan. Laporan ini tidak mengklaim skalabilitas di atas volume yang diuji, yaitu sekitar 1,5 juta observasi dan 8,42 GB berita per minggu (langkah 10).
3. **Nomor persetujuan etik resmi belum terbit.** Laga sudah mengumpulkan data peserta sejak 23 Oktober 2026, sedangkan lembar persetujuan menampilkan nomor sementara. Pseudonim ekspor sudah berjalan di produksi dan DPIA ringkas sudah ditulis, tetapi data peserta belum boleh dianalisis sampai nomor resmi terbit (langkah 11, risiko R1 di DPIA).
4. **Surat izin dan berkas etik belum dikirim.** Empat surat izin (UNSD, KLH/BPLH, KKP, ANTARA) dan tiga berkas etik masih berupa draf di repositori penelitian, dan folder `bukti/surat/` di portofolio masih kosong sampai surat ditulis ulang tanpa data pribadi. Status tayang basis data SDG PBB, SIPSN, SIGN-SMART, dan KKP ditetapkan pada 22 Oktober 2026 sebagai data publik dengan atribusi wajib.
5. **Repositori metadata versi ringan.** OpenMetadata tidak dipasang karena kebutuhan memorinya, dan digantikan oleh DCAT, dbt docs, serta katalog Iceberg REST (langkah 05).
6. **Pemeriksaan klaim berita baru mencakup dua indikator.** Akurasi ekstraksi (κ antaranotator dan F1) belum diukur karena dua anotator belum ditetapkan.
7. **Ada dua Gold dengan sidik berbeda.** Angka laporan memakai Gold acuan `657df68e…`, yaitu dasar kelima pengujian Tahap II. Gold yang dipakai paket Laga (`1b8c95e3…`) hanya berbeda pada kelas lisensi empat sumber. Perbedaan ini relevan apabila angka laporan dibandingkan dengan layanan produksi (langkah 09).
8. **Kode asal berada di repositori privat.** Repositori penelitian Ardika dan repositori layanan Data Science Workbench bersifat privat. Kode gudang yang dirujuk bukti sudah disalin ke folder `code/` repositori portofolio dari commit `dcaa55e`, dengan dua penyesuaian untuk publikasi yang dicatat di `code/README.md` (kredensial bawaan stack lokal diganti placeholder, alamat pelacak isu repositori privat dihapus), sehingga dapat dibaca tanpa akses tambahan. Empat berkas uji SLA yang belum ter-commit disalin dari salinan kerja dengan sidiknya dicatat. Kode layanan DSW, yaitu modul Laga, masuk dengan Google, dan ekspor penelitian, tidak disalin dan tersedia untuk ditunjukkan pada saat asesmen.

## 5.2 Pekerjaan yang tersisa per langkah

**Tabel 5.1.** Pekerjaan yang tersisa sampai penutupan portofolio (31 Desember 2026).

| Langkah | Yang tersisa | Waktu |
| --- | --- | --- |
| 11 Pelindungan data pribadi | nomor persetujuan etik resmi sebelum analisis Laga; salinan garam di pengelola kata sandi; penyaringan nama pada judul RSS; pemusnahan terjadwal | segera (etik) |
| 01–03 Perencanaan | keputusan pemilik domain; bila kelompok mahasiswa dipilih, menambahkan bukti organisasi nyata (kontrak domain sebagai rubrik proyek, laporan masalah per domain); mencocokkan Perpres 39/2019 dengan teks resmi; menyegarkan inventaris aset | November |
| 04 Data rujukan dan master | mengunduh buku Metadata Indikator TPB Bappenas untuk memastikan kode kematian bayi dan arti tanda; menetapkan ruang nama IRI graf; memodelkan pemekaran sebelum 2012 | Desember |
| 05 Metadata | mengurasi 72 satuan lokal; melengkapi metadata DCAT untuk Bronze dan Silver | Desember |
| 06 Media penyimpanan | memeriksa kompatibilitas S3 bucket Lightsail; memperbarui volume setelah unduhan manual BNPB dan Bappenas; menjalankan deduplikasi snapshot BPS | Desember |
| 07–08 Integrasi dan kualitas | kelas sebab vintage antarkustodian pada praregistrasi berikutnya; tabel kode SIGN-SMART dari KLH/BPLH; berkas asli BNPB 2000; log jalan terjadwal dan tren kualitas antarjalan | Desember |
| 09 Gudang data | menguji query time travel Iceberg sebagai bagian pengujian resmi | Desember |
| 10 Big data dan operasi | menjalankan uji SLA secara terjadwal; uji SLA tersendiri untuk CC-NEWS dan RSS | Desember |
| Portofolio | mengisi FR.APL.02 per elemen; menulis ulang surat tanpa data pribadi ke `bukti/surat/`; memastikan jumlah unit dan format kepada LSP DKS | November |

## 5.3 Penutup

Berdasarkan bukti yang terkumpul sampai 27 Oktober 2026, kesepuluh unit dari SKKNI 268/2020 pada skema Insinyur Data LSP DKS sudah mempunyai berkas bukti per elemen yang lengkap, dan unit kesebelas, PDP, juga lengkap dengan satu catatan terbuka, yaitu nomor persetujuan etik resmi yang belum terbit. Setiap angka di laporan ini dapat ditelusuri ke berkas di `data/`, dan kode yang menghasilkannya dapat dibaca di `code/`.

Bukti terkuat terdapat pada langkah yang berkaitan dengan pembangunan gudang (04, 07, 08, 09). Artefaknya dapat dijalankan ulang dan menghasilkan sidik yang sama sampai ke paket level, dengan perintah yang tercantum pada Lampiran 6.2. Sebaliknya, bukti yang paling bergantung pada keputusan organisasi terdapat pada sisi perencanaan (01–03), yaitu pengisi peran pemilik domain. Oleh karena itu, tindak lanjut yang didahulukan adalah menuntaskan persetujuan etik sebelum data Laga dianalisis, kemudian menetapkan pemilik domain agar bukti organisasi federasi dapat ditambahkan.
