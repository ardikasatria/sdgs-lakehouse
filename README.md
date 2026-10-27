# sdgs-lakehouse

Portofolio sertifikasi kompetensi **Insinyur Data (Data Engineer)** atas nama Ardika Satria, Program Studi Sains Data ITERA, untuk asesmen di LSP Digital Kreatif Solusi (11 unit: sepuluh unit SKKNI 268/2020 dan J.62PDP00.011.1 dari SKKNI 103/2023).

Buktinya berasal dari satu proyek: gudang indikator SDG yang menyimpan setiap versi angka resmi dari banyak sumber, sehingga angka yang terbit pada tanggal tertentu dapat dipanggil ulang, ditelusuri asalnya, dan dibangun ulang sama persis. Gudang ini memasok game Liga Lakehouse di Data Science Workbench.

## Alur kerja dan unit

Folder bukti diurutkan mengikuti urutan pekerjaan, bukan urutan nomor unit. Setiap langkah membuktikan satu unit.

| Tahap | No | Langkah | Unit | Folder |
| --- | ---: | --- | --- | --- |
| Merencanakan | 1 | Kebutuhan data | J.62DMS00.001.1 | [`bukti/01-kebutuhan-data`](bukti/01-kebutuhan-data/README.md) |
| | 2 | Rencana manajemen data | J.62DMS00.002.1 | [`bukti/02-rencana-manajemen-data`](bukti/02-rencana-manajemen-data/README.md) |
| | 3 | Arsitektur data | J.62DMS00.003.1 | [`bukti/03-arsitektur-data`](bukti/03-arsitektur-data/README.md) |
| Menyiapkan acuan | 4 | Data rujukan dan master | J.62DMS00.008.1 | [`bukti/04-rujukan-dan-master`](bukti/04-rujukan-dan-master/README.md) |
| | 5 | Metadata | J.62DMS00.009.1 | [`bukti/05-metadata`](bukti/05-metadata/README.md) |
| Membangun | 6 | Media penyimpanan | J.62DMS00.005.1 | [`bukti/06-penyimpanan`](bukti/06-penyimpanan/README.md) |
| | 7 | Integrasi data | J.62DMS00.004.1 | [`bukti/07-integrasi`](bukti/07-integrasi/README.md) |
| | 8 | Kualitas data | J.62DMS00.012.1 | [`bukti/08-kualitas`](bukti/08-kualitas/README.md) |
| | 9 | Gudang data | J.62DMS00.014.1 | [`bukti/09-gudang-data`](bukti/09-gudang-data/README.md) |
| Menjalankan | 10 | Big data dan operasi | J.62DMS00.007.1 | [`bukti/10-big-data`](bukti/10-big-data/README.md) |
| | 11 | Pelindungan data pribadi | J.62PDP00.011.1 | [`bukti/11-data-pribadi`](bukti/11-data-pribadi/README.md) |

## Isi

| Folder | Isi |
| --- | --- |
| `bukti/` | satu folder per langkah: apa yang dikerjakan, bukti per elemen, catatan terbuka |
| `data/` | ringkasan hasil terukur yang menjadi dasar angka, dengan asal dan sidiknya |
| `code/` | salinan kode gudang yang dirujuk bukti |
| `report/` | laporan portofolio |
| `berkas-asesmen/` | FR.APL.01, FR.APL.02, persyaratan; `pribadi/` tidak pernah di-commit |

## Perintah

```bash
make data      # salin ringkasan dari DSIC-SDG (DSIC_SDG=/jalur/DSIC-SDG bila bukan ~/penelitian-kk)
make sidik     # catat sha256 data ke data/SIDIK.txt
make periksa   # pastikan data belum berubah
make laporan   # report/*.md -> report/_build/laporan.docx
```

## Keadaan

Kerangka disusun 26 Oktober 2026. Data di `data/` identik dengan salinan 24 Oktober 2026, kecuali `serkom/raci.csv` yang diperbarui 26 Oktober 2026 (tambah kegiatan 22–24 untuk data peserta, menjadi 24 kegiatan); sidik di `data/SIDIK.txt`. Isi bukti per langkah ditulis ulang dari awal.
