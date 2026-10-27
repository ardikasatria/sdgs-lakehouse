# Kode

Salinan kode gudang dari repositori penelitian DSIC-SDG (privat) pada satu commit yang dicatat di sini, agar asesor dapat membacanya tanpa akses ke repositori tersebut. Folder ini sengaja masih kosong; isi hanya bagian yang dirujuk bukti.

| Bagian | Asal di DSIC-SDG | Dirujuk langkah |
| --- | --- | --- |
| tata kelola data product | `config/mesh/` | 01, 02, 03 |
| data rujukan | `src/sdg_gudang/referensi.py`, `config/referensi/` | 04 |
| metadata dan graf | `src/sdg_gudang/gudang/kontrak.py`, `kg.py`, `lineage.py` | 05 |
| akuisisi dan Raw | `src/sdg_gudang/akuisisi/` | 06, 10 |
| Silver dan rekonsiliasi | `src/sdg_gudang/silver/`, `config/rekonsiliasi/` | 07, 08 |
| gudang | `dbt/gudang_sdg/`, `src/sdg_gudang/gudang/muat.py`, `orkestrasi.py`, `sidik.py` | 09 |
| tumpukan dan SLA | `infra/gudang/`, `config/sla/` | 06, 10 |
| uji unit | `tests/unit/test_gudang_*.py`, `test_sdg_gudang_referensi.py` | semua |

**Commit sumber:** _(isi saat menyalin)_

Kode layanan Data Science Workbench (modul Laga, masuk dengan Google, ekspor penelitian) berada di repositori DSW yang juga privat dan ditunjukkan langsung saat asesmen.
