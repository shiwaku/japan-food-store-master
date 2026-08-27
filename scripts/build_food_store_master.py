#!/usr/bin/env python3
"""
食料品店マスター構築（Phase 1）  ― 設計_食料品店マスター構築.md 準拠
カテゴリ: supermarket / convenience / drugstore / fresh_food
列 src_cat にソース側の生カテゴリ（Overture の category / OSM の shop）を残す。
supermarket は Overture `supermarket` と浄化 `grocery_store` の合成で、
**業態が違うので分母も違う**（前者はセンサス561+581、後者は589系）。issue #33 /
docs/master/検証_supermarket分解と分母の確定.md
入力: data/overture_food_deduped_jp.parquet, data/osm_food_stores_japan.tsv,
      data/japan_pref.geojson（無ければ dataofjapan/land から自動取得）
出力: data/food_store_master.parquet (GeoParquet), data/food_store_master.csv
"""
import duckdb, os, sys, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from food_store_rules import dispensing_only_sql, grocery_noise_sql  # noqa: E402

PREF_GEOJSON = "data/japan_pref.geojson"
PREF_URL = "https://raw.githubusercontent.com/dataofjapan/land/master/japan.geojson"
OV = "read_parquet('data/overture_food_deduped_jp.parquet')"
OSM = "read_csv_auto('data/osm_food_stores_japan.tsv', sep='\t', all_varchar=true)"

# grocery のノイズ判定（飲食サービス系＋雑貨）は food_store_rules に置いて分解検証と共有する。
GROCERY_NOISE = grocery_noise_sql("name", "category_alt")
DEDUP_DEG = 0.0011  # ≒100m（緯度）

con = duckdb.connect()
con.execute("INSTALL spatial; LOAD spatial;")
if not os.path.exists(PREF_GEOJSON):
    os.makedirs(os.path.dirname(PREF_GEOJSON), exist_ok=True)
    print(f"取得: {PREF_URL} -> {PREF_GEOJSON}")
    urllib.request.urlretrieve(PREF_URL, PREF_GEOJSON)
con.execute(f"create table pref as select nam_ja as pref, geom from ST_Read('{PREF_GEOJSON}')")

# ---- 各カテゴリの候補点（cat, name, brand, source, geom）----
# supermarket: Overture supermarket ∪ 浄化grocery（groceryはsupermarket近接を除外して二重排除）
con.execute(f"""create table sm_ov as
  select 'supermarket' cat, 'supermarket' src_cat, name, brand_name brand, 'overture' src,
    ST_Point(lon,lat) geom
  from {OV} where category='supermarket'""")
con.execute(f"""create table gc as
  select name, brand_name brand, ST_Point(lon,lat) geom
  from {OV} where category='grocery_store' and not {GROCERY_NOISE}""")
con.execute("create index sm_ov_ix on sm_ov using rtree(geom)")
con.execute(f"""create table gc_uniq as
  select 'supermarket' cat, 'grocery_store' src_cat, name, brand, 'overture' src, geom from gc c
  where not exists (select 1 from sm_ov s where ST_DWithin(c.geom, s.geom, {DEDUP_DEG}))""")

# convenience: Overture単独
con.execute(f"""create table cv as
  select 'convenience' cat, 'convenience_store' src_cat, name, brand_name brand, 'overture' src,
    ST_Point(lon,lat) geom
  from {OV} where category='convenience_store'""")

# drugstore: Overture drugstore（pharmacy除外）
con.execute(f"""create table dg as
  select 'drugstore' cat, 'drugstore' src_cat, name, brand_name brand, 'overture' src,
    ST_Point(lon,lat) geom
  from {OV} where category='drugstore'""")

# fresh_food: Overture(butcher/seafood) ∪ OSM(greengrocer/butcher/seafood)。OSMはOverture近接を除外
con.execute(f"""create table fr_ov as
  select 'fresh_food' cat, category src_cat, name, brand_name brand, 'overture' src,
    ST_Point(lon,lat) geom
  from {OV} where category in ('butcher_shop','seafood_market')""")
con.execute(f"""create table fr_osm_all as
  select 'fresh_food' cat, shop src_cat, name, null brand, 'osm' src,
    ST_Point(TRY_CAST(\"@lon\" as double), TRY_CAST(\"@lat\" as double)) geom
  from {OSM} where shop in ('greengrocer','butcher','seafood')""")
con.execute("create index fr_ov_ix on fr_ov using rtree(geom)")
con.execute(f"""create table fr_osm as
  select * from fr_osm_all o
  where not exists (select 1 from fr_ov v where ST_DWithin(o.geom, v.geom, {DEDUP_DEG}))""")

# ---- 統合 → 調剤専業の除外 → 都道府県割当 → マスター出力 ----
con.execute("""create table cand_all as
  select * from sm_ov union all select * from gc_uniq
  union all select * from cv union all select * from dg
  union all select * from fr_ov union all select * from fr_osm""")

# 調剤薬局を除外（設計7章）。Overture は調剤薬局を drugstore に紛れ込ませており
# カテゴリでは分離できないため名称で判定する。判定条件は scripts/food_store_rules.py
# （検証スクリプトと共有。食品を扱うドラッグストアチェーンは巻き添えにしない）。
PHARM = dispensing_only_sql("name")
con.execute(f"create table cand as select * from cand_all where not {PHARM}")
excluded = con.execute(f"select count(*) from cand_all where {PHARM}").fetchone()[0]
print(f"調剤専業として除外: {excluded:,} 件")
for cat, cnt in con.execute(
        f"select cat, count(*) from cand_all where {PHARM} group by 1 order by 2 desc").fetchall():
    print(f"  {cat:12s} {cnt:,}")

con.execute(f"""create table master as
  select row_number() over () as store_id, c.cat, c.src_cat, c.name, c.brand, c.src,
    p.pref as prefecture, ST_Y(c.geom) as lat, ST_X(c.geom) as lng, c.geom
  from cand c join pref p on ST_Contains(p.geom, c.geom)""")

n = con.execute("select count(*) from master").fetchone()[0]
dropped = con.execute("select count(*) from cand").fetchone()[0] - n
print(f"マスター件数={n:,}  （都道府県外の取りこぼし {dropped:,}）")
print("=== カテゴリ別 ===")
for cat, cnt in con.execute("select cat, count(*) from master group by 1 order by 2 desc").fetchall():
    print(f"  {cat:12s} {cnt:,}")
print("=== cat × src_cat（分母が違うので分けて数える。issue #33）===")
for cat, sc, cnt in con.execute(
        "select cat, src_cat, count(*) from master group by 1,2 order by 1, 3 desc").fetchall():
    print(f"  {cat:12s} {sc:18s} {cnt:,}")

con.execute("copy (select store_id,cat,src_cat,name,brand,src,prefecture,lat,lng,geom from master) to 'data/food_store_master.parquet' (FORMAT parquet)")
con.execute("copy (select store_id,cat,src_cat,name,brand,src,prefecture,lat,lng from master) to 'data/food_store_master.csv' (header, delimiter ',')")
print("出力: data/food_store_master.parquet / .csv")
