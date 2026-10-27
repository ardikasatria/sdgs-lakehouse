# sdgs-lakehouse: portofolio serkom Insinyur Data
#
#   make data      salin ringkasan hasil dari repositori penelitian Ardika sesuai data/asal.tsv
#                  (setel PENELITIAN=/jalur/repositori-penelitian)
#   make sidik     catat sha256 setiap berkas data ke data/SIDIK.txt
#   make periksa   pastikan data belum berubah sejak sidik dicatat
#   make laporan   susun report/0*.md di InDesign (TEMPLAT_INDD=/jalur/WP8.indd) -> report/laporan-serkom.indd + .pdf
#   make laporan-pdf  bangun PDF tanpa InDesign (pandoc + XeLaTeX) -> report/laporan-serkom-xelatex.pdf

PENELITIAN ?=
DATA     ?= data

.PHONY: bantuan data sidik periksa laporan laporan-pdf

bantuan:
	@sed -n '3,8p' Makefile | sed 's/^#   //'

data:
	@test -n "$(PENELITIAN)" || { echo "setel PENELITIAN=/jalur/repositori-penelitian"; exit 1; }
	@grep -v '^#' data/asal.tsv | while IFS="$$(printf '\t')" read -r salinan asal; do \
	  mkdir -p "$(DATA)/$$(dirname "$$salinan")"; \
	  cp "$(PENELITIAN)/$$asal" "$(DATA)/$$salinan" && echo "  $$salinan"; \
	done

sidik:
	@cd $(DATA) && find gudang produk serkom uji -type f ! -name .DS_Store | sort | xargs shasum -a 256 > SIDIK.txt
	@echo "$(DATA)/SIDIK.txt: $$(wc -l < $(DATA)/SIDIK.txt | tr -d ' ') berkas"

periksa:
	@cd $(DATA) && shasum -a 256 -c --quiet SIDIK.txt && echo "data sama dengan SIDIK.txt"

laporan:
	bash report/_templat/indesign/buat_laporan.sh

laporan-pdf:
	cd report && pandoc 0*.md --from markdown --pdf-engine=xelatex --lua-filter=_templat/laporan.lua \
	  --include-in-header=_templat/header.tex --include-before-body=_templat/sampul.tex \
	  -V lang=id -V linkcolor=biru -o laporan-serkom-xelatex.pdf
