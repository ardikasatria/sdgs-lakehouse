-- Indikator TPB nasional dan padanan globalnya (M1).
select indikator_id, kode_tpb, cast(tujuan as integer) as tujuan, pilar, nama, nullif(penanda, '') as penanda,
       nullif(kode_global, '') as kode_global, padanan_global, nullif(iri_global, '') as iri_global, status_katalog,
       sumber_rencana
from {{ source('rujukan', 'dim_indikator') }}
