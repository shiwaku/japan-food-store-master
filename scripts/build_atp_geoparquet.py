#!/usr/bin/env python3
"""data/atp/*.geojson（52チェーン）を1つの GeoParquet にまとめる。

`fetch_alltheplaces_jp.py` と**同じ分類規則**（`classify` / 調剤専業の除外）を使うので、
出力は `data/atp_food_stores_japan.parquet` と同じ母集団に geometry と付帯情報を足したもの。

付ける情報:
- `prefecture`: 都道府県ポリゴン（data/japan_pref.geojson）との空間結合。県外は None
- `source_class` / `redistributable`: **再配布の可否**。ATP 公式ラン由来（CC-0）だけが再配布可で、
  自前クロール分は各社規約で再配布不可（docs/sources/調査_自前クロールソースの利用規約と再配布可否.md）。
  下流でうっかり公開物に混ぜないよう、行単位で判別できるようにしておく。

使い方:
    python3 scripts/build_atp_geoparquet.py [出力パス]
"""
import os
import sys

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_alltheplaces_jp import extract  # noqa: E402

SRC_DIR = "data/atp"
PREF_GEOJSON = "data/japan_pref.geojson"
# 拡張子は .parquet にする（QGIS/GDAL の Parquet ドライバは .geoparquet を認識しないことがある）
OUT = sys.argv[1] if len(sys.argv) > 1 else "data/atp_food_stores_japan_geo.parquet"

# ATP 公式ラン 2026-08-01-13-32-15 に spider がある14本。出力は CC-0。
# これ以外は自前クロールで、取得は規約・robots.txt とも禁じられていないが再配布は不可。
ATP_OFFICIAL = {
    "familymart_jp", "lawson_jp", "aeon_hokkaido_jp", "matsukiyo_jp", "tsuruhadrug",
    "seims_jp", "tomods_jp", "life_jp", "valor_jp", "seijoishii_jp", "heiwado_jp",
    "beisia_jp", "itoyokado_jp", "costco_jp",
}


def drop_near_duplicates(gdf):
    """同一チェーン・同一ブランドで 50m 以内にある重複レコードを1件に畳む。

    併設調剤が別レコードで出てくるチェーンがある（「カワチ薬品○○店」と「カワチ薬局○○調剤」、
    「ツルハドラッグ○○店」と「調剤薬局ツルハドラッグ○○店」）。大半は調剤特化業態の除外
    （`is_dispensing_format`）で落ちるが、ウエルシアのように併設を注記で書くチェーンは
    残るので、空間的にも畳む。issue #28-2。
    """
    from food_store_rules import normalize_brand
    key_brand = gdf["brand"].map(normalize_brand)
    # 50m ≒ 緯度 0.00045度。格子でバケット化して、同じバケットは1件だけ残す
    # （厳密な距離クラスタリングまでは要らない。同一店舗の重複を落とすのが目的）。
    cell_lat = (gdf["lat"] / 0.00045).round().astype("int64")
    cell_lng = (gdf["lng"] / 0.00055).round().astype("int64")
    before = len(gdf)
    gdf = gdf[~gdf.assign(_k=gdf["spider"] + "|" + key_brand + "|" +
                          cell_lat.astype(str) + "|" + cell_lng.astype(str))
              .duplicated(subset="_k", keep="first")]
    print(f"同一チェーン・同一ブランドで 50m 以内の重複を除去: {before - len(gdf):,} 件")
    return gdf


def main() -> None:
    rows = extract(SRC_DIR)
    df = pd.DataFrame(rows)
    df["source_class"] = df["spider"].map(
        lambda s: "atp_official_cc0" if s in ATP_OFFICIAL else "self_crawl")
    df["redistributable"] = df["source_class"] == "atp_official_cc0"

    gdf = gpd.GeoDataFrame(
        df, geometry=[Point(x, y) for x, y in zip(df["lng"], df["lat"])], crs="EPSG:4326")

    pref = gpd.read_file(PREF_GEOJSON)[["nam_ja", "geometry"]].rename(
        columns={"nam_ja": "prefecture"})
    gdf = gpd.sjoin(gdf, pref.to_crs(gdf.crs), how="left", predicate="within").drop(
        columns=["index_right"])
    # ポリゴン境界にまたがると同じ点が複数県にヒットしうるので落とす
    gdf = gdf[~gdf.index.duplicated(keep="first")]

    cols = ["cat", "name", "brand", "prefecture", "spider", "ref", "src",
            "source_class", "redistributable", "geocode_source", "lat", "lng", "geometry"]
    gdf = gdf[cols]
    gdf = drop_near_duplicates(gdf)
    # covering bbox は GeoParquet 1.1 の機能。DuckDB 等の空間フィルタが効くように付ける。
    gdf.to_parquet(OUT, index=False, compression="zstd", geometry_encoding="WKB",
                   schema_version="1.1.0", write_covering_bbox=True)

    print(f"\n出力: {OUT}  {len(gdf):,} 行")
    print("=== カテゴリ別 ===")
    print(gdf.groupby("cat").size().sort_values(ascending=False).to_string())
    print("=== 再配布可否別 ===")
    print(gdf.groupby("source_class").size().to_string())
    print(f"=== 都道府県外（prefecture が空）: {gdf['prefecture'].isna().sum():,} 行 ===")


if __name__ == "__main__":
    main()
