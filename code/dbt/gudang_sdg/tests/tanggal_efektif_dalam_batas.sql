-- Tanggal efektif rilis tidak boleh sesudah batas atas tanggal rilisnya atau sesudah snapshot pertamanya
-- (penyimpangan 2 laporan M3: rilis tanpa tanggal tidak boleh terurut sebagai rilis terbaru).
select rilis_id, tanggal_efektif, batas_atas, snapshot_pertama
from {{ ref('dim_rilis') }}
where (batas_atas is not null and tanggal_efektif > cast(substr(batas_atas, 1, 10) as date))
   or tanggal_efektif > snapshot_pertama
