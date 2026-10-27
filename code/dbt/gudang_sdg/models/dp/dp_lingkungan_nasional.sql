-- Dibangkitkan dari config/mesh/dp_lingkungan_nasional.yaml oleh sdg_gudang.gudang.kontrak; jangan disunting.
-- Nilai pilihan indikator Pilar Pembangunan Lingkungan, tingkat nasional
select n.konsep_id,
       k.indikator_id,
       k.kode_global,
       k.tujuan,
       n.wilayah_kode,
       w.nama as nama_wilayah,
       n.periode,
       n.rincian,
       n.nilai,
       n.nilai_angka,
       n.satuan_id,
       n.sumber,
       n.rilis_id,
       n.berlaku_sejak,
       n.sifat,
       n.prioritas,
       n.jumlah_calon,
       n.alasan_pilihan,
       n.tanggal_acuan
from {{ ref('nilai_pilihan_tayang') }} n
join {{ ref('dim_konsep') }} k on k.konsep_id = n.konsep_id
left join {{ ref('dim_wilayah') }} w on w.wilayah_kode = n.wilayah_kode and w.terkini
where k.tujuan in (6, 11, 12, 13, 14, 15) and n.wilayah_kode = 9999
