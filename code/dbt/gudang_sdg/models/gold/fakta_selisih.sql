-- Pasangan rilis x rilis dan sumber x sumber dengan status K0 dan kelas sebab K1-K9 (M3).
select
    to_hex(sha256(to_utf8(concat_ws('|', jenis_pasangan, konsep_id, wilayah_kode, periode, rincian, rilis_a, seri_a,
                                    rilis_b, seri_b)))) as selisih_id,
    jenis_pasangan, konsep_id, cast(wilayah_kode as integer) as wilayah_kode, periode, rincian,
    keluarga_a, sumber_a, rilis_a, seri_a, nilai_a, keluarga_b, sumber_b, rilis_b, seri_b, nilai_b,
    status, selisih_mutlak, nullif(selisih_relatif, '') as selisih_relatif,
    nullif(kelas_sebab, '') as kelas_sebab, nullif(aturan, '') as aturan, nullif(tingkat_bukti, '') as tingkat_bukti,
    nullif(alasan, '') as alasan, try_cast(nullif(jeda_hari, '') as integer) as jeda_hari
from {{ source('silver', 'fakta_selisih') }}
