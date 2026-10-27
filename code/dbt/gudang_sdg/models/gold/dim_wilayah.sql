-- Dimensi wilayah berubah perlahan tipe 2 (M1): satu baris per versi provinsi; 9999 = nasional.
select cast(wilayah_sk as integer) as wilayah_sk, cast(wilayah_kode as integer) as wilayah_kode,
       cast(versi as integer) as versi, kode_bps, nama, nullif(kode_kemendagri, '') as kode_kemendagri,
       nullif(kode_iso, '') as kode_iso, tingkat,
       cast(nullif(berlaku_dari, '') as date) as berlaku_dari, cast(nullif(berlaku_sebelum, '') as date) as berlaku_sebelum,
       cast(terkini as boolean) as terkini, cast(nullif(induk_kode, '') as integer) as induk_kode,
       nullif(dasar_perubahan, '') as dasar_perubahan
from {{ source('rujukan', 'dim_wilayah') }}
