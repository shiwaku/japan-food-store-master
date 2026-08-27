#!/usr/bin/env python3
"""許可データの純増候補をマスターに足して、推計用マスターを作る。

`extract_permit_fresh_food.py` / `extract_permit_supermarkets.py` は候補を出すだけで
マスターを書き換えない。**足すのはこのスクリプトの仕事**。候補は「どのマスターに対して
純増か」で変わるので、**候補を出したときの FOOD_MASTER と同じものをここにも渡すこと**。

    # 3段構え（ATP 基準の場合）
    python3 scripts/build_atp_based_master.py          # ① 土台（突合の基準）
    FOOD_MASTER=data/food_store_master_atp_based.parquet \
        OUT_PARQUET=data/permit_fresh_food_candidates_atp.parquet \
        python3 scripts/extract_permit_fresh_food.py   # ② 候補
    FOOD_MASTER=data/food_store_master_atp_based.parquet \
        OUT_PARQUET=data/permit_supermarket_candidates_atp.parquet \
        python3 scripts/extract_permit_supermarkets.py
    python3 scripts/merge_permit_gapfill.py            # ③ 投入

出力は GeoParquet。`src='permit'` / `source_class='permit'` / `redistributable=true` で
行単位に区別できる（許可データは CC BY 4.0・政府標準利用規約で**再配布可**）。

環境変数:
  FOOD_MASTER    土台のマスター（既定 data/food_store_master_atp_based.parquet）
  PERMIT_FRESH   生鮮の候補（既定 data/permit_fresh_food_candidates_atp.parquet）
  PERMIT_SUPER   ⑪ の候補（既定 data/permit_supermarket_candidates_atp.parquet）
  OUT            出力（既定 data/food_store_master_atp_permit.parquet）
"""
import os
import sys

import duckdb

MASTER = os.environ.get("FOOD_MASTER", "data/food_store_master_atp_based.parquet")
FRESH = os.environ.get("PERMIT_FRESH", "data/permit_fresh_food_candidates_atp.parquet")
SUPER = os.environ.get("PERMIT_SUPER", "data/permit_supermarket_candidates_atp.parquet")
OUT = os.environ.get("OUT", "data/food_store_master_atp_permit.parquet")

# 実数統計（build_atp_based_master.py と同じ）。supermarket の分母は 561+581 に取り直す
# 必要があるが（issue #33）、ここは既存の表示と揃えるため 581 のままにしてある。
ACTUAL = {"convenience": 56352, "supermarket": 22378, "drugstore": 17622, "fresh_food": 33960}

CATS = {FRESH: "fresh_food", SUPER: "supermarket"}


def main() -> None:
    if not os.path.exists(MASTER):
        sys.exit("土台のマスターが無い: " + MASTER)
    con = duckdb.connect()
    cols = [r[0] for r in con.execute(
        "describe select * from read_parquet('{p}')".format(p=MASTER)).fetchall()]
    has_spider = "spider" in cols

    parts = ["""select cat, name, brand, prefecture, src,
                {sp} spider, source_class, redistributable, lat, lng
              from read_parquet('{p}')""".format(p=MASTER, sp="" if has_spider else "null as")]
    if not has_spider:
        # Phase1 マスターには spider / source_class / redistributable が無い
        parts = ["""select cat, name, brand, prefecture, src, null as spider,
                    'overture_osm' as source_class, true as redistributable, lat, lng
                  from read_parquet('{p}')""".format(p=MASTER)]

    added = {}
    for path, cat in CATS.items():
        if not os.path.exists(path):
            print("候補が無いので飛ばす: " + path)
            continue
        n = con.execute("select count(*) from read_parquet('{p}') where net_new".format(
            p=path)).fetchone()[0]
        added[cat] = added.get(cat, 0) + n
        parts.append("""select '{c}' as cat, name, null as brand, prefecture, 'permit' as src,
            null as spider, 'permit' as source_class, true as redistributable, lat, lng
          from read_parquet('{p}') where net_new""".format(c=cat, p=path))

    con.execute("create table out as " + " union all ".join(parts))
    df = con.execute("select row_number() over () as store_id, * from out").df()

    import geopandas as gpd
    from shapely.geometry import Point
    gdf = gpd.GeoDataFrame(df, geometry=[Point(x, y) for x, y in zip(df["lng"], df["lat"])],
                           crs="EPSG:4326")
    gdf.to_parquet(OUT, index=False, compression="zstd", geometry_encoding="WKB",
                   schema_version="1.1.0", write_covering_bbox=True)

    n_base = con.execute("select count(*) from read_parquet('{p}')".format(p=MASTER)).fetchone()[0]
    print("土台 {m}: {n:,} 件".format(m=MASTER, n=n_base))
    for cat, n in sorted(added.items()):
        print("  ＋許可データ {c:12s} {n:,}".format(c=cat, n=n))
    print("\n出力: " + OUT)
    print("{a:12s}{b:>10s}{c:>10s}{d:>10s}{e:>10s}{f:>8s}".format(
        a="cat", b="土台", c="許可", d="計", e="実数統計", f="率"))
    total = 0
    for cat, base, permit in con.execute("""select cat,
            count(*) filter (where src <> 'permit'), count(*) filter (where src = 'permit')
          from out group by 1 order by 3 desc""").fetchall():
        n = base + permit
        total += n
        act = ACTUAL.get(cat, 0)
        rate = "{:.1f}%".format(n / act * 100) if act else "-"
        print("{a:12s}{b:10,}{c:10,}{d:10,}{e:10,}{f:>8s}".format(
            a=cat, b=base, c=permit, d=n, e=act, f=rate))
    print("{a:12s}{b:10s}{c:10s}{d:10,}".format(a="合計", b="", c="", d=total))
    print("\n=== 再配布可否 ===")
    for sc, n in con.execute(
            "select source_class, count(*) from out group by 1 order by 2 desc").fetchall():
        print("  {a:20s} {b:,}".format(a=sc, b=n))


if __name__ == "__main__":
    main()
