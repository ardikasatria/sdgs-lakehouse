# Kode

Salinan kode gudang dari repositori penelitian Ardika (privat), agar asesor dapat membacanya tanpa akses ke repositori itu. Yang disalin hanya bagian yang dirujuk bukti, dan setiap berkas disalin dari satu commit yang dicatat di bawah, sehingga baris kode yang dibaca asesor sama dengan baris yang menghasilkan angka di `data/`, kecuali dua penyesuaian untuk publikasi yang dicatat pada bagian "Perubahan terhadap commit sumber".

**Commit sumber:** `dcaa55e` (22 Oktober 2026), commit yang juga tercatat pada `data/uji/uji-sla.json` dan `data/uji/banding-spark.json`. Salinan dibuat 27 Oktober 2026 dengan `git archive` dari commit itu, bukan dari salinan kerja, kecuali empat berkas yang dicatat pada bagian "Berkas yang belum ter-commit". Sidik sha256 setiap berkas ada di [`SIDIK.txt`](SIDIK.txt).

| Bagian | Jalur di repositori penelitian (sama dengan jalur di folder ini) | Dirujuk langkah |
| --- | --- | --- |
| tata kelola data product | `config/mesh/*.yaml` (9 data product), `src/sdg_gudang/gudang/kontrak.py` (pembangkit kontrak) | 01, 02, 03, 05 |
| data rujukan | `src/sdg_gudang/referensi.py`, `config/referensi/` | 04 |
| metadata dan graf | `src/sdg_gudang/gudang/kontrak.py`, `kg.py`, `lineage.py` | 05 |
| akuisisi dan Raw | `src/sdg_gudang/akuisisi/` (inti, 13 konektor, 12 pengulang) | 06, 10, 11 |
| Silver dan rekonsiliasi | `src/sdg_gudang/silver/` (inti, 9 pemeta, agregasi, rekonsiliasi, kualitas), `config/rekonsiliasi/` | 07, 08 |
| gudang | `dbt/gudang_sdg/` (model `gold` dan `dp`, macro, seed, 6 uji singular), `src/sdg_gudang/gudang/muat.py`, `orkestrasi.py`, `sidik.py` | 09 |
| tumpukan dan SLA | `infra/gudang/` (compose, konfigurasi S3 dan Trino), `config/sla/lapis.yaml`, `src/sdg_gudang/gudang/uji_sla.py`, `eval/serkom/banding_spark.py` | 06, 10 |
| uji unit | `tests/unit/test_gudang_*.py` (16 berkas), `test_sdg_gudang_referensi.py` | semua |

Jumlah: 141 berkas, sekitar 1 MB. Folder `target/` dan `logs/` dbt, `__pycache__`, dan modul yang tidak dirujuk bukti (misalnya alur klaim berita) tidak disalin.

## Berkas yang belum ter-commit

Empat berkas uji SLA dan pembanding Spark dibuat 24 Oktober 2026 dan pada saat disalin belum ter-commit di repositori penelitian. Keempatnya disalin dari salinan kerja, dan sidiknya dicatat di sini supaya dapat dicocokkan ketika commit-nya ada.

| Berkas | sha256 |
| --- | --- |
| `config/sla/lapis.yaml` | `6ee641566bb54ec855f0767d5fcd80b0d2972fdaf53e9a3a3ab82cbffe8d45ac` |
| `src/sdg_gudang/gudang/uji_sla.py` | `e98d967af7ba295c06565e571458192388bd1a0556ceaea658238437ac55b7d4` |
| `tests/unit/test_gudang_uji_sla.py` | `48810d10c86fbb1f16bd66ff856fa29cc52bf716c07fc2e646349bcd127586e6` |
| `eval/serkom/banding_spark.py` | `6dc4b99f70da9c3e7bb8811fd734e59d4292ce1d4e79cbc705d0e782d9ceb02b` |

## Cara membaca

Kode di sini tidak dimaksudkan untuk dijalankan dari folder ini; ia membutuhkan Raw, tumpukan Docker, dan paket Python dari repositori penelitian. Perintah yang disebut di bukti (`make m1-referensi`, `make m4-naik`, `make m4-uji-sla`, dan seterusnya) adalah target Makefile repositori penelitian, dan demonstrasinya dilakukan langsung saat asesmen. Titik masuk yang paling berguna untuk dibaca:

- `src/sdg_gudang/referensi.py`: resolver `Rujukan` dan pembangun data rujukan (langkah 04).
- `src/sdg_gudang/silver/inti.py` dan `pemeta/`: aturan S01–S09 dan karantina (langkah 07, 08).
- `src/sdg_gudang/silver/rekonsiliasi.py` dan `config/rekonsiliasi/`: kelas sebab K0a–K9 (langkah 07).
- `dbt/gudang_sdg/models/gold/` dan `macros/nilai_pilihan.sql`: skema bintang bitemporal dan aturan prioritas nilai pilihan (langkah 09).
- `src/sdg_gudang/gudang/kontrak.py` dan `config/mesh/`: dari YAML data product ke model dbt, kontrak, dan DCAT (langkah 03, 05).
- `src/sdg_gudang/gudang/uji_sla.py` dan `config/sla/lapis.yaml`: uji ketersambungan antarlapis (langkah 10).

## Perubahan terhadap commit sumber

Salinan ini berbeda dari commit `dcaa55e` pada dua hal, keduanya dilakukan 27 Oktober 2026 agar repositori ini dapat dipublikasikan. Selain itu tidak ada baris yang diubah.

| Berkas | Yang diubah | Alasan |
| --- | --- | --- |
| `infra/gudang/compose.yml`, `infra/gudang/s3.json`, `src/sdg_gudang/gudang/muat.py` | nilai bawaan kunci dan rahasia S3 tumpukan pengembangan lokal diganti placeholder `<kunci-s3-lokal>` dan `<rahasia-s3-lokal>`; nama variabel lingkungan `GUDANG_S3_KUNCI` dan `GUDANG_S3_RAHASIA` tetap | nilai aslinya hanya kredensial bawaan penyimpanan objek lokal yang terikat ke `127.0.0.1`, bukan rahasia layanan, tetapi pemindai rahasia akan menandainya; untuk menjalankan tumpukan, setel kedua variabel itu |
| `config/mesh/*.yaml` (9 berkas), `dbt/gudang_sdg/models/dp/*.yml` (9 berkas) | nilai `kanal_masalah` yang semula alamat pelacak isu repositori penelitian diganti placeholder `<pelacak isu repositori penelitian>`; kuncinya dipertahankan karena dibaca `kontrak.py` | alamat itu menyebut nama repositori privat |

`SIDIK.txt` mencatat sidik salinan yang sudah diubah ini. Sidik berkas aslinya dapat dihitung ulang dari commit sumber bila diperlukan asesor.

Kunci API sumber (misalnya BPS) dibaca dari variabel lingkungan dan tidak pernah ada di kode; pembangun manifest menolak menulis bidang bernama seperti kunci (`POLA_RAHASIA` di `src/sdg_gudang/akuisisi/inti.py`).

Kode layanan Data Science Workbench (modul Laga, masuk dengan Google, ekspor penelitian) berada di repositori DSW yang juga privat tidak ditunjukkan langsung saat asesmen.