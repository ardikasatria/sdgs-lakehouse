-- Aturan global federasi (kelas lisensi): nilai pilihan untuk sajian hanya dari sumber kelas A atau A-SA.
select n.* from {{ ref('nilai_pilihan_tayang') }} n
join {{ ref('dim_sumber') }} s on s.sumber = n.sumber
where not s.boleh_tayang
