"""Lapis Silver Gudang SDG (brief 4 M3): Bronze dipetakan ke kode kanonik dengan aturan bernomor.

Aturan S01-S08 dibekukan di ``docs/gudang/m3-praregistrasi-rekonsiliasi.md`` Bagian 2. Setiap sel kandidat
dari Bronze berakhir di tepat satu tempat: ``observasi`` (Silver), ``karantina``, ``kosong``, atau
``di_luar`` (wilayah di luar Indonesia atau tingkat yang tidak dimuat). Tabel Bronze yang memuat sel
lebar (beberapa ukuran per baris) menghasilkan beberapa sel kandidat per baris.

Keluaran (tidak di-commit): ``data/silver/gudang/{observasi,karantina}/<sumber>/<tabel>.parquet``.
Ringkasan hitungan dan sidik isi (di-commit): ``data/manifests/gudang/silver_ringkasan.json``.
"""
