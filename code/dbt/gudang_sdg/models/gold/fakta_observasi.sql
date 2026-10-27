-- Fakta observasi bitemporal (brief 4 Bagian 3.2-3.3): satu baris per (sumber, rilis, seri, wilayah, periode,
-- rincian). Waktu periode = periode; waktu rilis = berlaku_sejak (tanggal efektif rilis) sampai berlaku_sampai
-- (rilis berikutnya dalam keluarga yang memuat kunci sama); waktu catat = tercatat_pada (tanggal snapshot
-- akuisisi), ditambah snapshot Iceberg tabel ini.
-- konsep_id = konsep padanan seri bila seri ada di padanan, selain itu seri sumber sendiri
-- (seri:<keluarga>:<kode>); konsep S06 Silver disimpan di konsep_silver. Konsep global S06 dapat menyatukan seri
-- berbeda ukuran di bawah satu kode indikator, sehingga tidak dipakai untuk memilih nilai (klarifikasi M4).
-- Kolom *_konsep menormalkan rincian, periode, dan satuan menurut padanan seri (sama dengan pembentukan pasangan
-- sumber x sumber M3), agar nilai pilihan dapat memilih lintas keluarga pada kunci yang sama.
with o as (
    select o.*, r.tanggal_efektif, s.keluarga as keluarga_sumber,
           p.konsep_id as konsep_padanan, p.rincian as rincian_padanan, p.bulan_dipakai, coalesce(a.satuan_id, p.satuan_id) as satuan_padanan, p.hubungan
    from {{ source('silver', 'observasi') }} o
    join {{ ref('dim_rilis') }} r on r.rilis_id = o.rilis_id
    join {{ ref('dim_sumber') }} s on s.sumber = o.sumber
    left join {{ source('rujukan', 'padanan_seri') }} p on p.keluarga = o.keluarga and p.seri_kode = o.seri_kode
    -- satuan padanan beku M3 dapat memakai id lokal x_; dipetakan ke dim_satuan lewat alias_satuan
    left join {{ source('rujukan', 'alias_satuan') }} a on a.satuan_lokal = p.satuan_id
)
select
    to_hex(sha256(to_utf8(concat_ws('|', sumber, rilis_id, seri_kode, cast(wilayah_kode as varchar), periode, rincian))))
        as obs_id,
    sumber, keluarga, rilis_id, seri_kode,
    coalesce(konsep_padanan, 'seri:' || keluarga || ':' || seri_kode) as konsep_id, konsep_id as konsep_silver,
    nullif(indikator_id, '') as indikator_id,
    nullif(kode_global, '') as kode_global, wilayah_kode, tingkat, periode, jenis_periode,
    nullif(bulan_acuan, '') as bulan_acuan, rincian, nilai, nilai_angka, desimal, satuan_id,
    cast(faktor_satuan as varchar) as faktor_satuan, sifat, nullif(status_angka, '') as status_angka,
    nullif(agregasi, '') as agregasi, nullif(cakupan_parsial, '') as cakupan_parsial,
    case when rincian_padanan is not null and rincian = coalesce(nullif(rincian_padanan, ''), 'total') then 'total'
         -- rincian padanan bukan total (contoh sektor nonpertanian): total asli seri tidak boleh bertabrakan
         when coalesce(nullif(rincian_padanan, ''), 'total') <> 'total' and rincian = 'total' then 'total_seri'
         else rincian end as rincian_konsep,
    case when nullif(bulan_dipakai, '') is not null and bulan_acuan = bulan_dipakai then substr(periode, 1, 4)
         else periode end as periode_konsep,
    coalesce(nullif(satuan_padanan, ''), satuan_id) as satuan_konsep,
    hubungan as hubungan_padanan,
    tanggal_efektif as berlaku_sejak,
    lead(rilis_id) over (partition by keluarga, seri_kode, wilayah_kode, periode, rincian
                         order by tanggal_efektif, rilis_id) as digantikan_oleh_rilis,
    lead(tanggal_efektif) over (partition by keluarga, seri_kode, wilayah_kode, periode, rincian
                                order by tanggal_efektif, rilis_id) as berlaku_sampai,
    cast(_snapshot as date) as tercatat_pada,
    aturan_silver, _berkas_raw as berkas_raw, _sha256_raw as sha256_raw
from o
