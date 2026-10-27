-- Setiap observasi Silver menjadi tepat satu fakta Gold (tidak ada yang hilang atau berlipat saat join rilis).
select (select count(*) from {{ source('silver', 'observasi') }}) as silver,
       (select count(*) from {{ ref('fakta_observasi') }}) as gold
where (select count(*) from {{ source('silver', 'observasi') }}) <> (select count(*) from {{ ref('fakta_observasi') }})
