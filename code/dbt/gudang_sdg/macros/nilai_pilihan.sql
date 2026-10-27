{#
  Nilai pilihan as-of (praregistrasi M3 Bagian 5) per (konsep, wilayah, periode, rincian) pada konsep yang
  dinormalkan padanan. Prioritas: 1 BPS; 2 kementerian/lembaga sektoral; 3 kustodian internasional dengan sifat
  resmi atau disesuaikan; 4 Bank Dunia dan kustodian bersifat tidak diketahui (klarifikasi M4); 5 estimasi atau
  model dari sumber mana pun. Dalam satu prioritas: observasi resmi sebelum agregat S09 (tambahan praregistrasi
  M3 butir 7), lalu rilis terbaru, lalu rilis_id leksikal, lalu obs_id
  (pemutus terakhir agar deterministik; klarifikasi M4).
  hanya_tayang = true mengeluarkan sumber kelas lisensi B dan C sebelum memilih.
#}
{% macro nilai_pilihan(hanya_tayang) %}
with calon as (
    select f.*, s.boleh_tayang,
           case when f.sifat in ('estimasi', 'model') then 5
                when f.keluarga = 'bps' then 1
                when f.keluarga in ('bnpb', 'sipsn', 'signsmart', 'kkp') then 2
                when f.keluarga in ('unsd', 'ilostat', 'who_gho') and f.sifat in ('resmi', 'disesuaikan') then 3
                else 4 end as prioritas
    from {{ ref('fakta_observasi') }} f
    join {{ ref('dim_sumber') }} s on s.sumber = f.sumber
    where f.berlaku_sejak <= date '{{ var("tanggal_acuan") }}'
      {% if hanya_tayang %}and s.boleh_tayang{% endif %}
),
urut as (
    select *,
           row_number() over (partition by konsep_id, wilayah_kode, periode_konsep, rincian_konsep
                              order by prioritas, case when agregasi is null then 0 else 1 end, berlaku_sejak desc,
                                       rilis_id, obs_id) as peringkat,
           count(*) over (partition by konsep_id, wilayah_kode, periode_konsep, rincian_konsep) as jumlah_calon
    from calon
)
select konsep_id, wilayah_kode, periode_konsep as periode, rincian_konsep as rincian, obs_id, sumber, keluarga,
       rilis_id, seri_kode, nilai, nilai_angka, satuan_konsep as satuan_id, sifat, berlaku_sejak, prioritas,
       jumlah_calon, date '{{ var("tanggal_acuan") }}' as tanggal_acuan,
       'prioritas ' || cast(prioritas as varchar) || ' (' || keluarga || ', sifat ' || sifat || '); rilis '
           || rilis_id || ' berlaku sejak ' || cast(berlaku_sejak as varchar) || '; '
           || cast(jumlah_calon as varchar) || ' calon' as alasan_pilihan
from urut
where peringkat = 1
{% endmacro %}
