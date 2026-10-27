-- Konsep nilai pilihan tidak boleh menyatukan dua seri berbeda dari keluarga yang sama.
select konsep_id, keluarga, count(distinct seri_kode) as seri
from {{ ref('fakta_observasi') }}
group by konsep_id, keluarga
having count(distinct seri_kode) > 1
