# sdgs-lakehouse: portofolio serkom Insinyur Data
#
#   make data      salin ringkasan hasil dari DSIC-SDG sesuai data/asal.tsv
#   make sidik     catat sha256 setiap berkas data ke data/SIDIK.txt
#   make periksa   pastikan data belum berubah sejak sidik dicatat
#   make laporan   gabungkan report/*.md menjadi report/_build/laporan.docx

DSIC_SDG ?= $(HOME)/penelitian-kk
DATA     ?= data

.PHONY: bantuan data sidik periksa laporan

bantuan:
	@sed -n '3,6p' Makefile | sed 's/^#   //'

data:
	@grep -v '^#' data/asal.tsv | while IFS="$$(printf '\t')" read -r salinan asal; do \
	  mkdir -p "$(DATA)/$$(dirname "$$salinan")"; \
	  cp "$(DSIC_SDG)/$$asal" "$(DATA)/$$salinan" && echo "  $$salinan"; \
	done

sidik:
	@cd $(DATA) && find gudang produk serkom uji -type f ! -name .DS_Store | sort | xargs shasum -a 256 > SIDIK.txt
	@echo "$(DATA)/SIDIK.txt: $$(wc -l < $(DATA)/SIDIK.txt | tr -d ' ') berkas"

periksa:
	@cd $(DATA) && shasum -a 256 -c --quiet SIDIK.txt && echo "data sama dengan SIDIK.txt"

laporan:
	@mkdir -p report/_build
	pandoc $(sort $(wildcard report/[0-9]*.md)) -o report/_build/laporan.docx
