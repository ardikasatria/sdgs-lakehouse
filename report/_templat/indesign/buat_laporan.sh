#!/usr/bin/env bash
# Bangun laporan dari report/0*.md: Markdown -> ICML (pandoc) -> templat WP8 di InDesign -> report/laporan-serkom.indd + .pdf
#   TEMPLAT_INDD=/jalur/WP8.indd bash report/_templat/indesign/buat_laporan.sh
# Templat tidak diubah: dokumen dibuka lalu disimpan sebagai report/laporan-serkom.indd.
set -euo pipefail
DIR=$(cd "$(dirname "$0")/../../.." && pwd)          # akar repositori
LAPORAN="$DIR/report"
[ -n "${TEMPLAT_INDD:-}" ] && [ -f "$TEMPLAT_INDD" ] || { echo "setel TEMPLAT_INDD=/jalur/WP8.indd" >&2; exit 1; }
INDESIGN=${INDESIGN:-Adobe InDesign 2026}
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

python3 "$LAPORAN/_templat/indesign/siapkan_md.py" "$TMP/laporan.md" >/dev/null
(cd "$LAPORAN" && pandoc "$TMP/laporan.md" -s -t icml -o "$TMP/laporan.icml")
# jalur gambar relatif terhadap report/ menjadi jalur mutlak agar InDesign menemukannya
sed -i '' "s#file:gambar/#file:$LAPORAN/gambar/#g" "$TMP/laporan.icml"

cat > "$TMP/konfig.jsx" <<KONF
var TEMPLAT = "$TEMPLAT_INDD";
var ICML = "$TMP/laporan.icml";
var KELUAR_INDD = "$LAPORAN/laporan-serkom.indd";
var KELUAR_PDF = "$LAPORAN/laporan-serkom.pdf";
var PRATINJAU = "${PRATINJAU:-}";
var LOG = "$TMP/susun.log";
var LOGO = "$LAPORAN/gambar/logo";
KONF
osascript -e 'with timeout of 3600 seconds' \
  -e "tell application \"$INDESIGN\" to do script (POSIX file \"$LAPORAN/_templat/indesign/susun_laporan.jsx\") language javascript with arguments {\"$TMP/konfig.jsx\"}" \
  -e 'end timeout'
cat "$TMP/susun.log"
echo "report/laporan-serkom.pdf, report/laporan-serkom.indd"
