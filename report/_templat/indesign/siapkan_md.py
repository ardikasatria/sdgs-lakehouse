"""Gabungkan report/0*.md menjadi satu Markdown untuk ICML InDesign.

Sampul dan daftar isi dibuat oleh skrip InDesign; 00-identitas.md sudah berupa halaman "Identitas
Portofolio". Blok ``::: {custom-style="..."}`` dipertahankan: pandoc mengubahnya menjadi gaya paragraf
bernama (Kotak, Label Unit) yang kemudian diatur oleh susun_laporan.jsx.

    python3 report/_templat/indesign/siapkan_md.py <keluaran.md>
"""
import pathlib
import re
import sys

SUMBER = pathlib.Path(__file__).resolve().parents[2]  # report/


def main():
    keluar = pathlib.Path(sys.argv[1])
    bagian = []
    for f in sorted(SUMBER.glob("0*.md")):
        teks = f.read_text()
        # gambar selebar kolom teks (170 mm); InDesign tidak menskalakan gambar yang meluap
        teks = re.sub(r"^!\[([^\]]*)\]\(([^)]+)\)$", r"![\1](\2){width=170mm}", teks, flags=re.M)
        bagian.append(teks)
    keluar.write_text("\n\n".join(b.strip() for b in bagian) + "\n")
    print(keluar)


if __name__ == "__main__":
    main()
