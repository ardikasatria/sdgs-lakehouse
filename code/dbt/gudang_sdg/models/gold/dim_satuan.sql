-- Satuan kanonik dp_referensi ditambah satuan yang dipakai Silver tetapi belum terdaftar (seharusnya kosong sejak
-- satuan lokal x_ didaftarkan 20 Okt 2026); terdaftar_m1 = false menandai utang metadata.
with m1 as (
    select satuan_id, label, jenis, try_cast(nullif(penyebut, '') as integer) as penyebut, true as terdaftar_m1
    from {{ source('rujukan', 'dim_satuan') }}
),
lokal as (
    select distinct satuan_id from {{ source('silver', 'observasi') }}
    where satuan_id not in (select satuan_id from m1)
)
select * from m1
union all
select satuan_id, replace(substr(satuan_id, 3), '_', ' ') as label, 'lokal' as jenis, cast(null as integer),
       false
from lokal
