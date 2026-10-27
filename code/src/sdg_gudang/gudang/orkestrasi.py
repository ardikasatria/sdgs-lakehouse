"""Orkestrasi Dagster Gudang SDG (brief 4 M4): satu graf aset dari raw sampai data product.

Aset Python membungkus perintah M2-M4 yang sama dengan target ``make``; aset dbt dibaca dari manifest
``dbt/gudang_sdg``. Sumber dbt ``silver.*`` dan ``rujukan.*`` adalah aset keluaran ``iceberg_silver``, sehingga
lineage tersambung dari manifest raw sampai tabel ``dp.*``.

    dagster dev -m sdg_gudang.gudang.orkestrasi                       # antarmuka
    dagster asset materialize -m sdg_gudang.gudang.orkestrasi --select '*'
"""
from collections.abc import Mapping
from typing import Any, Optional

from dagster import (AssetExecutionContext, AssetKey, AssetSpec, Definitions, MaterializeResult, asset,
                     define_asset_job, multi_asset)
from dagster_dbt import DagsterDbtTranslator, DbtCliResource, DbtProject, dbt_assets

from sdg_gudang.akuisisi import inti as A

PROYEK_DBT = DbtProject(project_dir=A.AKAR / "dbt" / "gudang_sdg", profiles_dir=A.AKAR / "dbt" / "gudang_sdg")
PROYEK_DBT.prepare_if_dev()


@asset(group_name="bronze", description="Bronze dibangun ulang dari raw dan manifest M2, tanpa jaringan.")
def bronze() -> MaterializeResult:
    from sdg_gudang.akuisisi import ulang

    hasil = [ulang.bangun_ulang(p) for p in ulang.manifest_semua()]
    beda = {h["manifest"]: h["beda"] for h in hasil if h["beda"]}
    if beda:
        raise RuntimeError(f"jumlah baris Bronze beda dari manifest: {beda}")
    return MaterializeResult(metadata={"manifest": len(hasil), "baris": sum(sum(h["tabel"].values()) for h in hasil)})


@asset(group_name="silver", deps=[bronze], description="Silver S01-S08 dengan karantina (M3).")
def silver() -> MaterializeResult:
    from sdg_gudang.silver import jalan

    r = jalan.jalankan()
    obs = [t for t in r["tabel"].values() if t.get("jenis") == "observasi"]
    return MaterializeResult(metadata={k: sum(t[k] for t in obs) for k in ("silver", "karantina", "kosong", "di_luar")})


@asset(group_name="silver", deps=[silver], description="Pasangan rilis x rilis dan sumber x sumber, K0-K9 (M3).")
def rekonsiliasi() -> MaterializeResult:
    from sdg_gudang.silver import rekonsiliasi as K

    r = K.jalankan()["ringkasan"]
    return MaterializeResult(metadata={j: r[j]["pasangan"] for j in r})


@asset(group_name="silver", deps=[rekonsiliasi], description="Laporan kualitas tujuh dimensi (unit 012).")
def kualitas() -> MaterializeResult:
    from sdg_gudang.silver import kualitas as Q

    r = Q.jalankan()["per_sumber"]
    return MaterializeResult(metadata={s: h["keterpetakan"] for s, h in r.items()})


def tabel_iceberg() -> list[str]:
    """Nama tabel yang ditulis ``muat`` (namespace.tabel), sama dengan kunci sumber dbt."""
    from sdg_gudang import referensi as R

    return (["silver.observasi", "silver.karantina", "silver.fakta_selisih", "rujukan.dim_rilis", "rujukan.padanan_seri"]
            + [f"rujukan.{p.stem}" for p in sorted(R.KELUAR.glob("*.csv"))])


@multi_asset(specs=[AssetSpec(AssetKey(t.split(".")), group_name="iceberg", deps=[silver, rekonsiliasi],
                              description=f"tabel Iceberg {t} dari sdg_gudang.gudang.muat")
                    for t in tabel_iceberg()])
def iceberg_silver():
    from sdg_gudang.gudang import muat

    r = muat.jalankan()
    for t in tabel_iceberg():
        yield MaterializeResult(asset_key=AssetKey(t.split(".")), metadata={"baris": r[t]["baris"]})


@asset(group_name="gudang", description="Model dan kontrak data product dibangkitkan dari config/mesh.")
def kontrak_mesh() -> MaterializeResult:
    from sdg_gudang.gudang import kontrak

    if kontrak.main(["--cek"]) != 0:
        raise RuntimeError("kontrak data product tidak mutakhir; jalankan make m4-kontrak lalu commit")
    return MaterializeResult(metadata={"berkas": len(kontrak.semua())})


class Penerjemah(DagsterDbtTranslator):
    """Sumber dbt memakai kunci bawaan [sumber, tabel] = kunci aset ``iceberg_silver``; model dikelompokkan
    menurut skema (gold, dp)."""

    def get_group_name(self, dbt_resource_props: Mapping[str, Any]) -> Optional[str]:
        return dbt_resource_props.get("config", {}).get("schema") or "gold"

    def get_asset_spec(self, manifest, unique_id, project):
        spec = super().get_asset_spec(manifest, unique_id, project)
        node = manifest["nodes"].get(unique_id, {})
        if node.get("resource_type") == "model" and node.get("config", {}).get("schema") == "dp":
            spec = spec.merge_attributes(deps=[AssetKey("kontrak_mesh")])
        return spec


@dbt_assets(manifest=PROYEK_DBT.manifest_path, dagster_dbt_translator=Penerjemah())
def gudang_dbt(context: AssetExecutionContext, dbt: DbtCliResource):
    yield from dbt.cli(["build"], context=context).stream()


semua = define_asset_job("gudang_penuh", selection="*", description="raw -> Bronze -> Silver -> Iceberg -> Gold -> dp")

defs = Definitions(
    assets=[bronze, silver, rekonsiliasi, kualitas, iceberg_silver, kontrak_mesh, gudang_dbt],
    jobs=[semua],
    resources={"dbt": DbtCliResource(project_dir=PROYEK_DBT)},
)
