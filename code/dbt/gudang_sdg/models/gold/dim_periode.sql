-- Periode kanonik S02 dengan awal dan akhir kalender.
with p as (select distinct periode, jenis_periode from {{ source('silver', 'observasi') }})
select periode, jenis_periode, cast(substr(periode, 1, 4) as integer) as tahun,
       case jenis_periode
           when 'tahun' then date(periode || '-01-01')
           when 'bulan' then date(periode || '-01')
           when 'semester' then date(substr(periode, 1, 4) || (case substr(periode, 7, 1) when '1' then '-01-01' else '-07-01' end))
           when 'triwulan' then date_add('month', 3 * (cast(substr(periode, 7, 1) as integer) - 1), date(substr(periode, 1, 4) || '-01-01'))
       end as awal
from p
