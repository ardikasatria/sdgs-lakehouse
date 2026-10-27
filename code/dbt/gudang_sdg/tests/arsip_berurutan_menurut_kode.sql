-- Dalam arsip berkode rilis berurutan (basis data SDG PBB, arsip WDI), urutan tanggal efektif harus sama dengan
-- urutan kode rilis. Satu rilis yang tanggalnya jatuh ke snapshot akan melompat ke ujung dan tertangkap di sini.
with r as (
    select sumber, kode_rilis, tanggal_efektif,
           lag(tanggal_efektif) over (partition by sumber order by kode_rilis) as sebelumnya
    from {{ ref('dim_rilis') }}
    where sumber in ('unsd_arsip', 'wdi_arsip')
)
select * from r where sebelumnya is not null and tanggal_efektif < sebelumnya
