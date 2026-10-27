"""Lineage lengkap Gudang SDG (brief 4 M4; unit J.62DMS00.004.1 dan 009.1).

Tiga lapis disatukan menjadi satu graf tingkat tabel:

1. berkas manifest raw M2 -> tabel Bronze (``data/manifests/gudang/<sumber>-<tanggal>.json`` bagian ``bronze``);
2. tabel Bronze -> tabel Silver per sumber (``silver_ringkasan.json``) -> ``silver.*`` Iceberg;
3. graf aset Dagster, yang memuat lineage model dbt (``gold.*``, ``dp.*``) dari manifest dbt.

Keluaran: ``data/manifests/gudang/m4_lineage.json`` (simpul, sisi, dan jalur dari setiap data product ke
manifest raw) dan ringkasan Mermaid di ``docs/gudang/m4-lineage.md``.

    python3 -m sdg_gudang.gudang.lineage
"""
import json
import sys
from collections import defaultdict

from sdg_gudang.akuisisi import inti as A

KELUAR = A.MANIFEST / "m4_lineage.json"
MD = A.AKAR / "docs" / "gudang" / "m4-lineage.md"


def sisi_raw_bronze_silver() -> set[tuple[str, str]]:
    sisi = set()
    for p in sorted(A.MANIFEST.glob("*-????-??-??.json")):
        m = json.loads(p.read_text("utf-8"))
        for t in m.get("bronze", {}):
            sisi.add((f"raw:{p.name}", f"bronze:{m['sumber']}/{t}"))
    ring = json.loads((A.MANIFEST / "silver_ringkasan.json").read_text("utf-8"))
    for k, t in ring["tabel"].items():
        if t.get("jenis") == "observasi":
            sisi.add((f"bronze:{k}", f"silver_lokal:{k}"))
            sisi.add((f"silver_lokal:{k}", "silver/observasi"))
            sisi.add((f"silver_lokal:{k}", "silver/karantina"))
    sisi.add(("silver/observasi", "silver/fakta_selisih"))
    for p in sorted(A.MANIFEST.glob("*-????-??-??.json")):  # registri rilis dirakit dari semua manifest M2
        sisi.add((f"raw:{p.name}", "rujukan/dim_rilis"))
    from sdg_gudang import referensi as R

    m1 = f"raw:{R.SNAPSHOT.relative_to(A.AKAR)}/manifest.json"  # snapshot rujukan M1
    for p in sorted(R.KELUAR.glob("*.csv")):
        sisi.add((m1, f"rujukan/{p.stem}"))
    sisi.add(("raw:config/rekonsiliasi/padanan_seri.csv", "rujukan/padanan_seri"))
    return sisi


def sisi_dagster() -> set[tuple[str, str]]:
    from sdg_gudang.gudang.orkestrasi import defs

    g = defs.resolve_asset_graph()
    sisi = set()
    for k in g.get_all_asset_keys():
        for p in g.get(k).parent_keys:
            sisi.add(("/".join(p.path), "/".join(k.path)))
    return sisi


def jalur_ke_raw(sisi: set[tuple[str, str]], awal: str) -> set[str]:
    induk = defaultdict(set)
    for a, b in sisi:
        induk[b].add(a)
    lihat, tumpuk = set(), [awal]
    while tumpuk:
        n = tumpuk.pop()
        for p in induk[n] - lihat:
            lihat.add(p)
            tumpuk.append(p)
    return {n for n in lihat if n.startswith("raw:")}


def jalankan() -> dict:
    sisi = sisi_raw_bronze_silver() | sisi_dagster()
    simpul = sorted({n for e in sisi for n in e})
    dp = [n for n in simpul if n.startswith("dp/")]
    jalur = {d: sorted(jalur_ke_raw(sisi, d)) for d in dp}
    out = {"dibangun_pada": A.sekarang(), "simpul": len(simpul), "sisi": len(sisi),
           "data_product_tanpa_jalur_raw": [d for d, j in jalur.items() if not j],
           "jalur_data_product_ke_raw": jalur,
           "daftar_sisi": sorted([list(e) for e in sisi])}
    KELUAR.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", "utf-8")
    tulis_md(sisi)
    return out


def tulis_md(sisi: set[tuple[str, str]]) -> None:
    """Ringkasan Mermaid: simpul raw, Bronze, dan Silver lokal dikelompokkan per sumber."""
    def kelompok(n: str) -> str:
        if n.startswith("raw:"):
            if n.startswith("raw:raw/referensi"):
                return "raw rujukan M1"
            return "raw M2 (" + n[4:].rsplit("-", 3)[0] + ")" if n.endswith("-2026-10-20.json") or "-20" in n else n[4:]
        if n.startswith(("bronze:", "silver_lokal:")):
            return n.split(":", 1)[0].replace("silver_lokal", "Silver lokal") + " " + n.split(":", 1)[1].split("/")[0]
        return n
    ringkas = sorted({(kelompok(a), kelompok(b)) for a, b in sisi if kelompok(a) != kelompok(b)})
    ids = {n: f"n{i}" for i, n in enumerate(sorted({n for e in ringkas for n in e}))}
    baris = ["flowchart LR"] + [f'  {ids[n]}["{n}"]' for n in ids] + [f"  {ids[a]} --> {ids[b]}" for a, b in ringkas]
    MD.write_text("# Lineage Gudang SDG (M4)\n\nDibangkitkan oleh `python3 -m sdg_gudang.gudang.lineage` dari manifest "
                  "M2, ringkasan Silver M3, dan graf aset Dagster (termasuk model dbt). Simpul raw, Bronze, dan Silver "
                  "lokal diringkas per sumber; daftar sisi lengkap ada di `data/manifests/gudang/m4_lineage.json`.\n\n"
                  "```mermaid\n" + "\n".join(baris) + "\n```\n", "utf-8")


def main() -> int:
    out = jalankan()
    print(json.dumps({k: out[k] for k in ("simpul", "sisi", "data_product_tanpa_jalur_raw")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
