{# Uji generik tanpa paket luar: baris yang melanggar ekspresi, dan kunci gabungan ganda. #}
{% test ekspresi_benar(model, ekspresi) %}
select * from {{ model }} where not ({{ ekspresi }})
{% endtest %}

{% test kunci_unik(model, kolom) %}
select {{ kolom }}, count(*) as n from {{ model }} group by {{ kolom }} having count(*) > 1
{% endtest %}

{# Aturan global federasi: data product sajian hanya memuat sumber kelas lisensi A atau A-SA. #}
{% test hanya_tayang(model) %}
select m.sumber from {{ model }} m join {{ ref('dim_sumber') }} s on s.sumber = m.sumber where not s.boleh_tayang
{% endtest %}

{% test baris_minimum(model, n) %}
select count(*) as baris from {{ model }} having count(*) < {{ n }}
{% endtest %}

{# SLA kesegaran: rilis terbaru tidak lebih tua dari `hari` terhadap tanggal acuan. #}
{% test segar(model, kolom, hari) %}
select max({{ kolom }}) as terbaru from {{ model }}
having max({{ kolom }}) < date_add('day', -{{ hari }}, date '{{ var("tanggal_acuan") }}')
{% endtest %}
