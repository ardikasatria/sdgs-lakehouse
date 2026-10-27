// Susun laporan portofolio (naskah report/) di atas templat WP8 (A4, InDesign 2026).
// Salinan skrip versi 1 dengan dua gaya tambahan dari blok custom-style pandoc: "Kotak" (ringkasan bab
// berlatar biru muda) dan "Label Unit" (kode unit, standar, asal bukti, status di bawah judul unit).
// Dipanggil oleh skrip/buat_laporan_v2.sh dengan satu argumen: berkas konfig.jsx yang mendefinisikan
// TEMPLAT, ICML, KELUAR_INDD, KELUAR_PDF, PRATINJAU, LOG, LOGO.
//
// Urutan: buka templat -> simpan sebagai dokumen baru -> petakan huruf "(TT)" ke huruf terpasang ->
// isi sampul, daftar isi, dan halaman belakang -> hapus halaman contoh -> alirkan ICML ke halaman ber-master A ->
// turunkan gaya pandoc dari gaya templat -> rapikan gambar dan tabel -> daftar isi -> ekspor PDF.

$.evalFile(File(arguments[0]));

var log = [];
function catat(s) { log.push(s); }

var d = null;
function utama() {
    app.scriptPreferences.userInteractionLevel = UserInteractionLevels.NEVER_INTERACT;
    app.scriptPreferences.enableRedraw = false;

    for (var i = app.documents.length - 1; i >= 0; i--) {
        if (/laporan-serkom/.test(app.documents[i].name)) app.documents[i].close(SaveOptions.NO);
    }
    d = app.open(File(TEMPLAT), false);
    d.save(File(KELUAR_INDD));
    d.viewPreferences.rulerOrigin = RulerOrigin.PAGE_ORIGIN;
    d.viewPreferences.horizontalMeasurementUnits = MeasurementUnits.MILLIMETERS;
    d.viewPreferences.verticalMeasurementUnits = MeasurementUnits.MILLIMETERS;
    d.textPreferences.smartTextReflow = false;

    var LEBAR = 170, KIRI = 20, ATAS = 30, BAWAH = 268;
    var BIRU = d.swatches.itemByName("C=100 M=70 Y=0 K=0");
    var MERAH = d.swatches.itemByName("C=0 M=90 Y=80 K=0");
    var ABU = d.swatches.itemByName("C=0 M=0 Y=0 K=20");
    var HITAM = d.swatches.itemByName("Black");
    var KERTAS = d.swatches.itemByName("Paper");
    var BIRU_MUDA = d.colors.add({name: "biru muda serkom", model: ColorModel.PROCESS, space: ColorSpace.CMYK,
                                  colorValue: [12, 4, 0, 0]});
    var ABU_TUA = d.swatches.itemByName("C=0 M=0 Y=0 K=80");

    // ------------------------------------------------------------------ huruf: "Poppins (TT)" -> "Poppins"
    function namaHuruf(f) { return (typeof f == "string") ? f : f.name; }
    function petakanHuruf(objek) {
        var n = namaHuruf(objek.appliedFont);
        if (n.indexOf(" (TT)") < 0 && n.indexOf(" (OTF)") < 0) return false;
        var baru = n.replace(" (TT)", "").replace(" (OTF)", "");
        if (baru.indexOf("\t") < 0) baru += "\t" + objek.fontStyle;
        var f = app.fonts.itemByName(baru);
        if (f.isValid) objek.appliedFont = f; else catat("huruf tidak ada: " + baru.replace("\t", " "));
        return true;
    }
    var nGaya = 0;
    for (var i = 0; i < d.allParagraphStyles.length; i++) if (petakanHuruf(d.allParagraphStyles[i])) nGaya++;
    for (var i = 0; i < d.allCharacterStyles.length; i++) {
        try { if (d.allCharacterStyles[i].appliedFont != "") petakanHuruf(d.allCharacterStyles[i]); } catch (e) {}
    }
    for (var i = 0; i < d.stories.length; i++) {
        var rs = d.stories[i].textStyleRanges;
        for (var j = 0; j < rs.length; j++) petakanHuruf(rs[j]);
    }
    catat("gaya paragraf dipetakan ke huruf terpasang: " + nGaya);

    // bingkai gambar mewarisi isian dan garis merah dari gaya objek bawaan templat
    function bersihkanBingkai(r) {
        try { r.appliedObjectStyle = d.objectStyles.itemByName("$ID/[None]"); } catch (e) {}
        // mengeset ketebalan 0 pada bingkai yang sudah 0 membuat InDesign memasang lagi garis bawaan
        if (r.fillColor.name != "None") r.fillColor = d.swatches.itemByName("None");
        if (r.strokeWeight != 0) r.strokeWeight = 0;
    }

    // ------------------------------------------------------------------ logo ITERA, Fakultas Sains, Sains Data
    function pasangLogo(halaman, atas, kiri, tinggi) {
        // rasio lebar/tinggi berkas logo yang sudah dipotong (gambar/logo/)
        var berkas = [["logo-itera.png", 970 / 1178], ["logo-fakultas-sains.png", 498 / 356],
                      ["logo-sains-data.png", 618 / 810]];
        var x = kiri;
        for (var k = 0; k < berkas.length; k++) {
            var w = tinggi * berkas[k][1];
            var r = halaman.rectangles.add({geometricBounds: [atas, x, atas + tinggi, x + w], strokeWeight: 0});
            r.place(File(LOGO + "/" + berkas[k][0]));
            bersihkanBingkai(r);
            r.fit(FitOptions.PROPORTIONALLY);
            r.fit(FitOptions.CENTER_CONTENT);
            try { r.allGraphics[0].itemLink.unlink(); } catch (e) {}
            x += w + 6;
        }
    }

    // ------------------------------------------------------------------ sampul (halaman 1)
    function bingkaiBerisi(halaman, potongan) {
        var tf = halaman.allPageItems;
        for (var i = 0; i < tf.length; i++) {
            if (tf[i].constructor.name == "TextFrame" && tf[i].contents.indexOf(potongan) >= 0) return tf[i];
        }
        return null;
    }
    function ganti(halaman, potongan, isi, lebar) {
        var f = bingkaiBerisi(halaman, potongan);
        if (!f) { catat("tidak ketemu: " + potongan); return null; }
        f.contents = isi;
        if (lebar) { var b = f.geometricBounds; f.geometricBounds = [b[0], b[1], b[2], b[1] + lebar]; }
        return f;
    }
    var sampul = d.pages[0];
    // logo institusi menggantikan titik merah dan teks "Company"
    var logoTeks = bingkaiBerisi(sampul, "Company");
    if (logoTeks) logoTeks.remove();
    var ov = sampul.ovals;
    for (var j = ov.length - 1; j >= 0; j--) if (ov[j].geometricBounds[0] < 60) ov[j].remove();
    pasangLogo(sampul, 30, 42, 15);
    var judul = ganti(sampul, "Reporting", "Portofolio\rInsinyur Data", 150);
    ganti(sampul, "White Paper", "Laporan Sertifikasi Kompetensi", 150);
    var ket = ganti(sampul, "Tur rerepudae", "Ardika Satria, S.Si., M.Si.\rProgram Studi Sains Data, Institut Teknologi Sumatera\r" +
        "Skema Insinyur Data (Data Engineer) \u00B7 LSP Digital Kreatif Solusi\rDraf 4 \u00B7 27 Oktober 2026 \u00B7 Edisi untuk LSP DKS", 130);
    if (ket) { var b = ket.geometricBounds; ket.geometricBounds = [b[0] - 8, b[1], b[2] + 6, b[3]]; }

    // ------------------------------------------------------------------ master A: teks kepala halaman
    for (var m = 0; m < d.masterSpreads.length; m++) {
        var item = d.masterSpreads[m].allPageItems;
        for (var j = 0; j < item.length; j++) {
            var e = item[j].getElements()[0];
            if (e.constructor.name == "TextFrame") {
                petakanHuruf(e.texts[0]);
                if (/Company|Reporting|White Paper/i.test(e.contents)) e.contents = "Portofolio Insinyur Data";
            }
        }
    }

    // ------------------------------------------------------------------ halaman belakang (halaman 12)
    var akhir = d.pages[d.pages.length - 1];
    var kontak = ganti(akhir, "+65", "(0721) 8030188 \u00B7 Fakultas Sains\rardika.satria@sd.itera.ac.id\rITERA, Lampung Selatan", 110);
    if (kontak) { var bk = kontak.geometricBounds; kontak.geometricBounds = [bk[0], bk[1], bk[0] + 24, bk[3]]; }
    ganti(akhir, "Contact Info", "Kontak");
    pasangLogo(akhir, 172, 49, 13);
    ganti(akhir, "Company", "Insinyur Data");
    ganti(akhir, "Oratis plab", "Portofolio ini disusun dari proyek gudang indikator SDG multisumber dan Liga Lakehouse " +
          "Kelompok Keahlian Program Studi Sains Data ITERA. Kode, data, dan bukti per unit dapat diperiksa ulang di " +
          "repositori sdgs-lakehouse; kode dan data asalnya di repositori penelitian Ardika.");
    // kode QR contoh templat tidak menunjuk ke mana pun: dihapus
    var gb = akhir.groups;
    for (var j = gb.length - 1; j >= 0; j--) {
        var b = gb[j].geometricBounds;
        if (b[2] - b[0] > 10 && b[3] - b[1] > 10) gb[j].remove();
    }
    var rk = akhir.rectangles;
    for (var j = rk.length - 1; j >= 0; j--) {
        var b = rk[j].geometricBounds;
        if (b[2] - b[0] > 10 && b[3] - b[1] > 10 && b[0] > 200) rk[j].remove();
    }
    var pg = akhir.polygons;
    for (var j = pg.length - 1; j >= 0; j--) {
        var b = pg[j].geometricBounds;
        if (b[0] > 205 && b[2] < 226 && b[1] > 45 && b[3] < 70) pg[j].remove();
    }

    // ------------------------------------------------------------------ hapus halaman contoh 3-11
    for (var i = d.pages.length - 2; i >= 2; i--) d.pages[i].remove();

    // ------------------------------------------------------------------ alirkan ICML
    var masterA = d.masterSpreads.itemByName("A-Master");
    function halamanBaru(sesudah) {
        var p = d.pages.add(LocationOptions.AFTER, sesudah);
        p.appliedMaster = masterA;
        return p.textFrames.add({geometricBounds: [ATAS, KIRI, BAWAH, KIRI + LEBAR]});
    }
    var bingkai = halamanBaru(d.pages[1]);
    bingkai.place(File(ICML));
    var cerita = bingkai.parentStory;
    try { cerita.itemLink.unlink(); } catch (e) { catat("ICML tidak tertaut: " + e); }

    // ------------------------------------------------------------------ gaya: turunkan gaya pandoc dari gaya templat
    function gp(nama) { return d.paragraphStyles.itemByName(nama); }
    var body = gp("body text");
    body.pointSize = 10; body.leading = 15; body.spaceAfter = 2.5; body.hyphenation = false;
    body.fillColor = HITAM;
    body.justification = Justification.LEFT_JUSTIFIED;

    function turunkan(nama, induk, sifat) {
        var s = gp(nama);
        if (!s.isValid) return;
        s.basedOn = induk;
        for (var k in sifat) s[k] = sifat[k];
    }
    var semua = d.paragraphStyles;
    for (var i = 0; i < semua.length; i++) {
        var n = semua[i].name;
        if (n == "Header1") turunkan(n, gp("Headline"), {pointSize: 26, leading: 32, spaceAfter: 8,
            startParagraph: StartParagraph.NEXT_PAGE, keepWithNext: 2, keepAllLinesTogether: true});
        else if (n == "Header2") turunkan(n, gp("Sub Title"), {pointSize: 14, leading: 19, spaceBefore: 5, spaceAfter: 2.5,
            keepWithNext: 2, keepAllLinesTogether: true});
        else if (n == "Header3") turunkan(n, gp("Sub sub tittle"), {spaceBefore: 3, spaceAfter: 1.5, keepWithNext: 2});
        else if (n == "Paragraph" || n.indexOf("Blockquote") == 0) turunkan(n, body, {});
        else if (n.indexOf("Kotak") == 0) turunkan(n, body, {pointSize: 9.5, leading: 14, leftIndent: 5, rightIndent: 5,
            spaceBefore: 4, spaceAfter: 9, paragraphShadingOn: true, paragraphShadingColor: BIRU_MUDA, paragraphShadingTint: 100,
            paragraphShadingTopOffset: 4, paragraphShadingBottomOffset: 4, paragraphShadingLeftOffset: 5, paragraphShadingRightOffset: 5});
        else if (n.indexOf("Label Unit") == 0) turunkan(n, body, {pointSize: 8.5, leading: 12, spaceBefore: 0, spaceAfter: 5,
            fontStyle: "SemiBold", fillColor: ABU_TUA, keepWithNext: 1, ruleBelow: true, ruleBelowColor: BIRU,
            ruleBelowLineWeight: 0.75, ruleBelowOffset: 1.8, ruleBelowWidth: RuleWidth.COLUMN_WIDTH});
        else if (n.indexOf("BulList") == 0 || n.indexOf("NumList") == 0)
            turunkan(n, body, {leftIndent: 6, firstLineIndent: -6, spaceAfter: 1.5});
        else if (n == "CodeBlock") turunkan(n, body, {appliedFont: "Menlo", fontStyle: "Regular", pointSize: 7.5,
        justification: Justification.LEFT_ALIGN,
            leading: 10.5, spaceBefore: 1, spaceAfter: 3});
        else if (n.indexOf("TablePar") == 0 && n.indexOf("RightAlign") < 0) turunkan(n, body, {pointSize: 7.6, leading: 10, spaceAfter: 0,
            justification: Justification.LEFT_ALIGN});
        else if (n.indexOf("TablePar") == 0) turunkan(n, body, {pointSize: 7.6, leading: 10, spaceAfter: 0,
            justification: Justification.RIGHT_ALIGN});
    }
    var bq = gp("Blockquote > Paragraph");
    if (bq.isValid) { bq.leftIndent = 6; bq.fillColor = d.swatches.itemByName("C=0 M=0 Y=0 K=80"); }
    var hdr = d.paragraphStyles;
    for (var i = 0; i < hdr.length; i++) if (hdr[i].name.indexOf("TableHeader") >= 0) {
        hdr[i].fontStyle = "SemiBold"; hdr[i].fillColor = KERTAS;
    }
    var kode = d.characterStyles.itemByName("Code");
    if (kode.isValid) { kode.appliedFont = "Menlo"; kode.fontStyle = "Regular"; kode.horizontalScale = 92; }
    var kodeTebal = d.characterStyles.itemByName("Bold Code");
    if (kodeTebal.isValid) { kodeTebal.appliedFont = "Menlo"; kodeTebal.fontStyle = "Bold"; }
    var tebal = d.characterStyles.itemByName("Bold");
    if (tebal.isValid) tebal.fontStyle = "SemiBold";

    // keterangan "Gambar n." dan "Tabel n."
    var keterangan = d.paragraphStyles.add({name: "keterangan serkom", basedOn: body, pointSize: 8.5, leading: 12,
        justification: Justification.LEFT_ALIGN,
        spaceBefore: 1, spaceAfter: 4, fillColor: d.swatches.itemByName("C=0 M=0 Y=0 K=80")});
    var keteranganTabel = d.paragraphStyles.add({name: "keterangan tabel serkom", basedOn: keterangan, spaceBefore: 3,
        spaceAfter: 1.5, keepWithNext: 2});
    function gayakan(pola, gaya) {
        app.findGrepPreferences = NothingEnum.NOTHING; app.changeGrepPreferences = NothingEnum.NOTHING;
        app.findGrepPreferences.findWhat = pola;
        var hasil = cerita.findGrep();
        for (var i = 0; i < hasil.length; i++) hasil[i].paragraphs[0].appliedParagraphStyle = gaya;
        return hasil.length;
    }
    catat("keterangan gambar: " + gayakan("^Gambar \\d+\\.", keterangan));
    catat("keterangan tabel: " + gayakan("^Tabel \\d+\\.\\d*\\.", keteranganTabel));

    // paragraf TableCaption kosong dari pandoc dikecilkan; menghapus returnnya akan menggabungkan paragraf
    // sesudahnya (misalnya judul bab) ke gaya TableCaption
    var kap = gp("TableCaption");
    if (kap.isValid) { kap.basedOn = body; kap.pointSize = 1; kap.leading = 1; kap.spaceBefore = 0; kap.spaceAfter = 0; }

    // ------------------------------------------------------------------ gambar: paragraf di tengah (lebar 170 mm dari Markdown)
    var grafik = cerita.allGraphics;
    for (var i = 0; i < grafik.length; i++) {
        var r = grafik[i].parent;
        bersihkanBingkai(r);
        // gambar inline: paragrafnya memakai spasi baris otomatis 100 %, sehingga tinggi baris = tinggi gambar
        // (spasi tetap 15 pt membuat gambar naik menutupi baris sebelumnya)
        var ao = r.anchoredObjectSettings;
        ao.anchoredPosition = AnchorPosition.INLINE_POSITION;
        ao.anchorYoffset = 0;
        var par = r.parent.paragraphs[0];
        par.appliedParagraphStyle = body;
        par.justification = Justification.CENTER_ALIGN;
        par.leading = Leading.AUTO; par.autoLeading = 100;
        par.spaceBefore = 3; par.spaceAfter = 1.5; par.keepWithNext = 1;
    }
    catat("gambar: " + grafik.length);

    // ------------------------------------------------------------------ tabel: selebar kolom, lebar kolom menurut isi
    var tabel = cerita.tables;
    for (var t = 0; t < tabel.length; t++) {
        var tb = tabel[t], kol = tb.columns, bobot = [], total = 0;
        for (var c = 0; c < kol.length; c++) {
            var sel = kol[c].cells, pj = 0;
            for (var k = 0; k < sel.length; k++) pj = Math.max(pj, Math.min(sel[k].contents.length, 70));
            var w = Math.max(9, Math.sqrt(pj) * 6);
            bobot.push(w); total += w;
        }
        for (var c = 0; c < kol.length; c++) kol[c].width = LEBAR * bobot[c] / total;
        var semuaSel = tb.cells.everyItem();
        semuaSel.topInset = 1.1; semuaSel.bottomInset = 1.1; semuaSel.leftInset = 1.6; semuaSel.rightInset = 1.6;
        semuaSel.topEdgeStrokeWeight = 0; semuaSel.leftEdgeStrokeWeight = 0; semuaSel.rightEdgeStrokeWeight = 0;
        semuaSel.bottomEdgeStrokeWeight = 0.4; semuaSel.bottomEdgeStrokeColor = ABU;
        semuaSel.verticalJustification = VerticalJustification.TOP_ALIGN;
        if (tb.headerRowCount > 0) {
            var kepala = tb.rows[0].cells.everyItem();
            kepala.fillColor = BIRU; kepala.fillTint = 100;
        }
        for (var rr = tb.headerRowCount; rr < tb.rows.length; rr++)
            if ((rr - tb.headerRowCount) % 2 == 1) { var s2 = tb.rows[rr].cells.everyItem(); s2.fillColor = BIRU_MUDA; }
        tb.spaceBefore = 1; tb.spaceAfter = 3;
    }
    catat("tabel: " + tabel.length);

    // ------------------------------------------------------------------ alirkan sampai habis
    var n = 0;
    d.recompose();
    while (bingkai.overflows && n < 120) {
        var nb = halamanBaru(bingkai.parentPage);
        bingkai.nextTextFrame = nb;
        bingkai = nb; n++;
        nb.recompose();
    }
    catat("halaman isi: " + (n + 1) + (bingkai.overflows ? " (MASIH MELUAP)" : ""));

    // gambar ditanam agar dokumen tidak bergantung pada jalur PNG
    var tautan = d.links, nTanam = 0;
    for (var i = tautan.length - 1; i >= 0; i--) {
        try { tautan[i].unlink(); nTanam++; } catch (e) { catat("gagal menanam " + tautan[i].name + ": " + e); }
    }
    catat("gambar ditanam: " + nTanam);
    var gr = cerita.allGraphics;
    for (var i = 0; i < gr.length; i++) bersihkanBingkai(gr[i].parent);

    // halaman kosong di akhir (sisa pindah halaman Header1) dibuang
    while (d.pages.length > 3) {
        var p = d.pages[d.pages.length - 2];
        if (p.textFrames.length == 1 && p.textFrames[0].contents.length == 0) p.remove(); else break;
    }

    // ------------------------------------------------------------------ daftar isi (halaman 2)
    var isiDaftar = [];
    var paragraf = cerita.paragraphs;
    for (var i = 0; i < paragraf.length; i++) {
        var p = paragraf[i];
        if (p.appliedParagraphStyle.name == "Header1") {
            var tf = p.parentTextFrames[0];
            isiDaftar.push(p.contents.replace(/\r$/, "").replace(/\uFEFF/g, "") + "\t\u2002" + tf.parentPage.name);
        }
    }
    // bingkai templat berakhir di x 164 dengan tab di 108 mm sehingga judul panjang menabrak nomor halaman;
    // bingkai dilebarkan sampai margin kanan, nomor halaman rata kanan di tepi bingkai dengan titik penuntun
    var KIRI_DAFTAR = 52, KANAN_DAFTAR = 190;
    var daftar = bingkaiBerisi(d.pages[1], "20 Years");
    if (daftar) {
        var bd = daftar.geometricBounds;
        daftar.geometricBounds = [bd[0], KIRI_DAFTAR, bd[0] + 110, KANAN_DAFTAR];
        daftar.contents = isiDaftar.join("\r");
        var sisip = daftar.textFramePreferences.insetSpacing;
        var lebarTeks = KANAN_DAFTAR - KIRI_DAFTAR - sisip[1] - sisip[3];
        var ps = daftar.paragraphs;
        for (var k = 0; k < ps.length; k++) {
            ps[k].tabStops.everyItem().remove();
            ps[k].tabStops.add({alignment: TabStopAlignment.RIGHT_ALIGN, position: lebarTeks, leader: ".  "});
            ps[k].rightIndent = 0;
            ps[k].spaceAfter = 3;
            // nomor halaman tebal dan biru agar mudah dipindai
            var t = ps[k].contents.lastIndexOf("\t");
            var nomor = ps[k].characters.itemByRange(t + 1, ps[k].characters.length - 1);
            if (k < ps.length - 1) nomor = ps[k].characters.itemByRange(t + 1, ps[k].characters.length - 2);
            nomor.fillColor = BIRU;
        }
    }
    ganti(d.pages[1], "Table Of Contents", "Daftar Isi");
    // garis merah templat dari tepi kiri halaman disejajarkan dengan blok daftar isi
    var gl = d.pages[1].allPageItems;
    for (var k = 0; k < gl.length; k++) {
        var gb = gl[k].geometricBounds;
        if (gl[k].constructor.name != "TextFrame" && gb[0] > 90 && gb[0] < 110 && gb[2] - gb[0] < 2) {
            // garis setinggi nol tidak bisa diberi geometricBounds; titik lintasannya diganti langsung
            var yg = (gb[0] + gb[2]) / 2;
            gl[k].paths[0].entirePath = [[KIRI_DAFTAR, yg], [KANAN_DAFTAR, yg]];
        }
    }
    catat("daftar isi: " + isiDaftar.join(" | ").replace(/\t/g, " "));

    // ------------------------------------------------------------------ simpan, ekspor
    d.save(File(KELUAR_INDD));
    var preset = app.pdfExportPresets.itemByName("[High Quality Print]");
    app.pdfExportPreferences.pageRange = PageRange.ALL_PAGES;
    d.exportFile(ExportFormat.PDF_TYPE, File(KELUAR_PDF), false, preset);
    if (PRATINJAU) {
        app.jpegExportPreferences.jpegExportRange = ExportRangeOrAllPages.EXPORT_ALL;
        app.jpegExportPreferences.exportResolution = 72;
        app.jpegExportPreferences.jpegQuality = JPEGOptionsQuality.MEDIUM;
        d.exportFile(ExportFormat.JPG, File(PRATINJAU + "/hal.jpg"));
    }
    catat("halaman total: " + d.pages.length);
    var hilang = [];
    for (var i = 0; i < d.fonts.length; i++) if (d.fonts[i].status != FontStatus.INSTALLED) hilang.push(d.fonts[i].name);
    catat("huruf hilang: " + (hilang.length ? hilang.join("; ") : "tidak ada"));

}
try {
    utama();
    d.close(SaveOptions.YES);
} catch (e) {
    catat("GALAT baris " + e.line + ": " + e.message);
    try { if (d && d.isValid) d.close(SaveOptions.NO); } catch (e2) {}
}

var fl = File(LOG); fl.encoding = "UTF-8"; fl.open("w"); fl.write(log.join("\n") + "\n"); fl.close();
log.join("\n");
