-- Produsen data: keluarga, kelas lisensi dan kelas tayang (brief 4 Bagian 2.5), prioritas nilai pilihan.
select sumber, keluarga, nama_keluarga, kelas_lisensi, lisensi,
       cast(boleh_tayang as boolean) as boleh_tayang, cast(prioritas_keluarga as integer) as prioritas_keluarga
from {{ ref('sumber') }}
