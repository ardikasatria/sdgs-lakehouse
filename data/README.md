# Data

Ringkasan hasil terukur yang menjadi dasar angka di bukti dan laporan. Semua berkas disalin dari repositori penelitian Ardika; peta salinan ke asalnya ada di [`asal.tsv`](asal.tsv), dan sidik sha256 setiap berkas di [`SIDIK.txt`](SIDIK.txt).

| Folder | Isi | Dipakai di langkah |
| --- | --- | --- |
| `gudang/` | volume, kualitas, rekonsiliasi, ringkasan Silver, sidik Gold, lineage, ringkasan graf | 05, 06, 07, 08, 09, 10 |
| `produk/` | lima pengujian pemakaian gudang dan latensi produksi | 05, 07, 09, 10 |
| `serkom/` | inventaris aset data, RACI, kualitas per sumber, prioritas perbaikan | 01, 02, 08 |
| `uji/` | uji SLA antarlapis, uji API, ingest GDELT, pembanding Spark | 10 |

Angka gudang mengacu pada Gold acuan `657df68e…`, dan angka produk pada paket evaluasi `afbcbeef…`.

## Memperbarui

```bash
make data && make periksa
```

Bila `make periksa` gagal, berkas di repositori penelitian Ardika sudah berubah sejak sidik dicatat. Periksa perubahannya dulu, baru jalankan `make sidik` dan catat tanggalnya di README utama.
