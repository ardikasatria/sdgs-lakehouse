-- Konsep nilai pilihan: konsep padanan seri atau seri sumber (lihat fakta_observasi); tujuan dan pilar TPB dari
-- indikator TPB, lalu dari kode indikator global pertama.
with k as (
    select konsep_id, max(indikator_id) as indikator_id, max(kode_global) as kode_global,
           count(distinct keluarga) as jumlah_keluarga
    from {{ ref('fakta_observasi') }}
    group by konsep_id
),
p as (
    select pilar, cast(t.tujuan as integer) as tujuan
    from {{ source('rujukan', 'dim_pilar') }}
    cross join unnest(split(tujuan, ';')) as t (tujuan)
),
k2 as (
    select k.*,
           case when konsep_id like 'tpb:%' then regexp_extract(konsep_id, '^(tpb:[^:]+)', 1) else indikator_id end
               as indikator_tpb,
           try_cast(regexp_extract(coalesce(kode_global, regexp_extract(konsep_id, '^global:([^:]+)', 1), ''),
                                   '^(\d+)\.', 1) as integer) as tujuan_global
    from k
)
select k2.konsep_id, k2.indikator_tpb as indikator_id, k2.kode_global,
       case when k2.konsep_id like 'seri:%' then 'seri' else 'padanan' end as jenis_konsep,
       k2.jumlah_keluarga,
       coalesce(i.tujuan, k2.tujuan_global) as tujuan,
       coalesce(i.pilar, p.pilar) as pilar,
       i.nama as nama_indikator
from k2
left join {{ ref('dim_indikator') }} i on i.indikator_id = k2.indikator_tpb
left join p on p.tujuan = coalesce(i.tujuan, k2.tujuan_global)
