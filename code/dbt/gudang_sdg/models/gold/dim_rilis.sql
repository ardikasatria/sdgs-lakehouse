-- Registri rilis M2. tanggal_efektif = tanggal rilis; bila kosong, batas atas tanggal rilis; bila kosong juga,
-- tanggal snapshot pertama (praregistrasi M3 Bagian 5; batas_atas sejak penyimpangan 2 laporan M3).
select rilis_id, sumber, kode_rilis,
       nullif(tanggal_rilis, '') as tanggal_rilis_teks,
       cast(substr(coalesce(nullif(tanggal_rilis, ''), nullif(batas_atas, ''), snapshot_pertama), 1, 10) as date)
           as tanggal_efektif,
       jenis_bukti_tanggal, bukti, nullif(batas_bawah, '') as batas_bawah, nullif(batas_atas, '') as batas_atas,
       cakupan, nullif(lisensi, '') as lisensi, cast(snapshot_pertama as date) as snapshot_pertama, kelas_lisensi
from {{ source('rujukan', 'dim_rilis') }}
where rilis_id <> ''
