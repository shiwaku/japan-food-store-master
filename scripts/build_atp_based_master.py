#!/usr/bin/env python3
"""ATP を土台にしたマスターを組む（issue #30）。

**座標の出所を「その店自身の公表値」に揃える**のが狙い。ATP（チェーン公式サイト由来）を土台に置き、
ATP が持たない部分だけを既存マスター（Overture / OSM）から補う。現行の主従を逆転させる。

手順:
  1. 土台 = data/atp_food_stores_japan_geo.parquet
  2. ATP が spider を持つブランドは ATP を正とし、既存マスター側の同ブランド店を落とす
     （**ブランド名は正規化してから突合する**。「セブンイレブン」と「セブン-イレブン」が一致しないと
       同じ店が二重に残る。issue #28-3）
  3. 残った既存マスターのうち、同カテゴリの ATP 点が RADIUS_M 以内にあるものを落とす
     （name/brand が欠損していて 2 を素通りしたもの）
  4. 残りを ATP に足す

fresh_food は ATP がゼロなので、そのまま既存マスター（OSM 由来）が残る。許可データでの補完は #26。

使い方:
    python3 scripts/build_atp_based_master.py [半径m] [出力パス]
"""
import os
import sys

import duckdb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from food_store_rules import normalize_brand_sql  # noqa: E402

ATP = "data/atp_food_stores_japan_geo.parquet"
MASTER = "data/food_store_master.parquet"
RADIUS_M = float(sys.argv[1]) if len(sys.argv) > 1 else 200.0
# GeoParquet で出す（QGIS でも DuckDB でもそのまま開ける）
OUT = sys.argv[2] if len(sys.argv) > 2 else "data/food_store_master_atp_based.parquet"

ACTUAL = {"convenience": 56352, "supermarket": 22378, "drugstore": 17622, "fresh_food": 33960}


def main() -> None:
    for p in (ATP, MASTER):
        if not os.path.exists(p):
            sys.exit(f"入力が無い: {p}")
    con = duckdb.connect()
    nb = normalize_brand_sql
    d = RADIUS_M / 111320.0

    con.execute(f"""create table atp as
      select cat, name, brand, prefecture, 'atp' as src, spider, source_class, redistributable,
             lat, lng, {nb('brand')} as nb
      from read_parquet('{ATP}')""")
    con.execute(f"""create table ms as
      select cat, name, brand, prefecture, src, null as spider,
             'overture_osm' as source_class, true as redistributable, lat, lng,
             {nb('name')} as nn, {nb('brand')} as nbm
      from read_parquet('{MASTER}')""")
    con.execute("""create table brands as
      select distinct cat, nb from atp where length(nb) >= 2""")

    # 2. ブランド一致で置き換え
    con.execute("""create table ms_step2 as
      select * from ms m where not exists (
        select 1 from brands b where b.cat = m.cat
          and (m.nn like '%' || b.nb || '%' or m.nbm like '%' || b.nb || '%'))""")
    # 3. 空間デデュープ
    con.execute(f"""create table ms_keep as
      select * from ms_step2 m where not exists (
        select 1 from atp a where a.cat = m.cat
          and a.lat between m.lat - {d} * 1.1 and m.lat + {d} * 1.1
          and a.lng between m.lng - {d} * 1.6 and m.lng + {d} * 1.6
          and 111320.0 * sqrt(pow(m.lat - a.lat, 2) +
              pow((m.lng - a.lng) * cos(radians(m.lat)), 2)) <= {RADIUS_M})""")

    n_ms, n_s2, n_keep = (con.execute(f"select count(*) from {t}").fetchone()[0]
                          for t in ("ms", "ms_step2", "ms_keep"))
    print(f"既存マスター {n_ms:,} → ブランド一致で落とす {n_ms - n_s2:,} → "
          f"{RADIUS_M:.0f}m 以内で落とす {n_s2 - n_keep:,} → 残す {n_keep:,}")

    con.execute("""create table out as
      select cat, name, brand, prefecture, src, spider, source_class, redistributable, lat, lng
      from atp
      union all
      select cat, name, brand, prefecture, src, spider, source_class, redistributable, lat, lng
      from ms_keep""")
    df = con.execute("select row_number() over () as store_id, * from out").df()
    import geopandas as gpd
    from shapely.geometry import Point
    gdf = gpd.GeoDataFrame(df, geometry=[Point(x, y) for x, y in zip(df["lng"], df["lat"])],
                           crs="EPSG:4326")
    gdf.to_parquet(OUT, index=False, compression="zstd", geometry_encoding="WKB",
                   schema_version="1.1.0", write_covering_bbox=True)

    print(f"\n出力: {OUT}")
    print(f"{'cat':12s}{'ATP':>9s}{'補完':>8s}{'計':>9s}{'実数統計':>10s}{'率':>8s}")
    total = 0
    for cat, a, k in con.execute("""select cat, count(*) filter (where src = 'atp'),
        count(*) filter (where src <> 'atp') from out group by 1 order by 3 desc""").fetchall():
        n = a + k
        total += n
        act = ACTUAL[cat]
        print(f"{cat:12s}{a:9,}{k:8,}{n:9,}{act:10,}{n / act * 100:7.1f}%")
    print(f"{'合計':12s}{'':9s}{'':8s}{total:9,}")
    print("\n=== 再配布可否 ===")
    for sc, n in con.execute("select source_class, count(*) from out group by 1 order by 2 desc").fetchall():
        print(f"  {sc:20s} {n:,}")


if __name__ == "__main__":
    main()
