-- Gaya khusus laporan: div custom-style Kotak dan "Label Unit", serta lebar kolom tabel
-- yang dihitung dari panjang isi agar tabel lebar tidak meluap.
local function teks(el) return pandoc.utils.stringify(el) end

function Div(el)
  local gaya = el.attributes["custom-style"]
  if FORMAT:match("latex") then
    if gaya == "Kotak" then
      return { pandoc.RawBlock("latex", "\\begin{kotak}"), el, pandoc.RawBlock("latex", "\\end{kotak}") }
    elseif gaya == "Label Unit" then
      return { pandoc.RawBlock("latex", "\\begin{labelunit}"), el, pandoc.RawBlock("latex", "\\end{labelunit}") }
    end
  end
  return el
end

function Table(tbl)
  if not FORMAT:match("latex") then return tbl end
  local n = #tbl.colspecs
  if n < 2 then return tbl end
  local maks = {}
  for i = 1, n do maks[i] = 0 end
  local function ukur(baris)
    for _, r in ipairs(baris) do
      for i, sel in ipairs(r.cells) do
        local p = #teks(sel.contents)
        if p > maks[i] then maks[i] = p end
      end
    end
  end
  ukur(tbl.head.rows)
  for _, b in ipairs(tbl.bodies) do ukur(b.body) end
  local total, ada_panjang = 0, false
  for i = 1, n do
    -- kolom pendek tetap diberi ruang minimum; kolom panjang dibatasi agar tidak mendominasi
    maks[i] = math.max(6, math.min(maks[i], 70)); total = total + maks[i]
    if maks[i] > 24 then ada_panjang = true end
  end
  if not ada_panjang then return tbl end  -- tabel pendek: biarkan pandoc memakai lebar alami
  for i = 1, n do
    local cs = tbl.colspecs[i]
    tbl.colspecs[i] = { cs[1], maks[i] / total * 0.98 }
  end
  return tbl
end
