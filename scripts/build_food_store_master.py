#!/usr/bin/env python3
"""
食料品店マスター構築（Phase 1）  ― 設計_食料品店マスター構築.md 準拠
カテゴリ: supermarket / convenience / drugstore / fresh_food
入力: data/overture_food_deduped_jp.parquet, data/osm_food_stores_japan.tsv, <scratch>/japan_pref.geojson
出力: data/food_store_master.parquet (GeoParquet), data/food_store_master.csv
"""
import duckdb, sys, csv

SCRATCH = "/tmp/claude-1000/-mnt-c-Users-yshiw-Documents-GIS-japan-mobility-ease-diagnosis/5112583e-1e0a-42bb-be9e-67e744cf6fbf/scratchpad"
OV = "read_parquet('data/overture_food_deduped_jp.parquet')"
OSM = "read_csv_auto('data/osm_food_stores_japan.tsv', sep='\t', all_varchar=true)"

# grocery のノイズ判定（飲食サービス系＋雑貨）＝食物retail altを持たず飲食/雑貨altのみ、or 名称ノイズ
NOISE = "['restaurant','cafe','bar','eat_and_drink','japanese_restaurant','smoothie_juice_bar','food_beverage_service_distribution','home_goods_store','shopping']"
FOOD  = "['supermarket','grocery_store','health_food_store','bakery','liquor_store','delicatessen','specialty_grocery_store','fishmonger','fruits_and_vegetables','butcher','convenience_store','farm']"
NAME_NOISE = ("(name ilike '%カフェ%' or name ilike '%coffee%' or name ilike '%cafe%' or name ilike '%食堂%' "
              "or name ilike '%ZAKKA%' or name ilike '%雑貨%' or name ilike '%セレクトショップ%' or name ilike '%レストラン%')")
DEDUP_DEG = 0.0011  # ≒100m（緯度）

con = duckdb.connect()
con.execute("INSTALL spatial; LOAD spatial;")
con.execute(f"create table pref as select nam_ja as pref, geom from ST_Read('{SCRATCH}/japan_pref.geojson')")

# ---- 各カテゴリの候補点（cat, name, brand, source, geom）----
# supermarket: Overture supermarket ∪ 浄化grocery（groceryはsupermarket近接を除外して二重排除）
con.execute(f"""create table sm_ov as
  select 'supermarket' cat, name, brand_name brand, 'overture' src, ST_Point(lon,lat) geom
  from {OV} where category='supermarket'""")
con.execute(f"""create table gc as
  select name, brand_name brand, ST_Point(lon,lat) geom
  from {OV} where category='grocery_store'
  and not ((category_alt is not null and len(list_intersect(category_alt,{NOISE}))>0
            and len(list_intersect(category_alt,{FOOD}))=0) or {NAME_NOISE})""")
con.execute("create index sm_ov_ix on sm_ov using rtree(geom)")
con.execute(f"""create table gc_uniq as
  select 'supermarket' cat, name, brand, 'overture' src, geom from gc c
  where not exists (select 1 from sm_ov s where ST_DWithin(c.geom, s.geom, {DEDUP_DEG}))""")

# convenience: Overture単独
con.execute(f"""create table cv as
  select 'convenience' cat, name, brand_name brand, 'overture' src, ST_Point(lon,lat) geom
  from {OV} where category='convenience_store'""")

# drugstore: Overture drugstore（pharmacy除外）
con.execute(f"""create table dg as
  select 'drugstore' cat, name, brand_name brand, 'overture' src, ST_Point(lon,lat) geom
  from {OV} where category='drugstore'""")

# fresh_food: Overture(butcher/seafood) ∪ OSM(greengrocer/butcher/seafood)。OSMはOverture近接を除外
con.execute(f"""create table fr_ov as
  select 'fresh_food' cat, name, brand_name brand, 'overture' src, ST_Point(lon,lat) geom
  from {OV} where category in ('butcher_shop','seafood_market')""")
con.execute(f"""create table fr_osm_all as
  select 'fresh_food' cat, name, null brand, 'osm' src,
    ST_Point(TRY_CAST(\"@lon\" as double), TRY_CAST(\"@lat\" as double)) geom
  from {OSM} where shop in ('greengrocer','butcher','seafood')""")
con.execute("create index fr_ov_ix on fr_ov using rtree(geom)")
con.execute(f"""create table fr_osm as
  select * from fr_osm_all o
  where not exists (select 1 from fr_ov v where ST_DWithin(o.geom, v.geom, {DEDUP_DEG}))""")

# ---- 統合 → 都道府県割当 → マスター出力 ----
con.execute("""create table cand as
  select * from sm_ov union all select * from gc_uniq
  union all select * from cv union all select * from dg
  union all select * from fr_ov union all select * from fr_osm""")
con.execute(f"""create table master as
  select row_number() over () as store_id, c.cat, c.name, c.brand, c.src,
    p.pref as prefecture, ST_Y(c.geom) as lat, ST_X(c.geom) as lng, c.geom
  from cand c join pref p on ST_Contains(p.geom, c.geom)""")

n = con.execute("select count(*) from master").fetchone()[0]
dropped = con.execute("select count(*) from cand").fetchone()[0] - n
print(f"マスター件数={n:,}  （都道府県外の取りこぼし {dropped:,}）")
print("=== カテゴリ別 ===")
for cat, cnt in con.execute("select cat, count(*) from master group by 1 order by 2 desc").fetchall():
    print(f"  {cat:12s} {cnt:,}")

con.execute("copy (select store_id,cat,name,brand,src,prefecture,lat,lng,geom from master) to 'data/food_store_master.parquet' (FORMAT parquet)")
con.execute("copy (select store_id,cat,name,brand,src,prefecture,lat,lng from master) to 'data/food_store_master.csv' (header, delimiter ',')")
print("出力: data/food_store_master.parquet / .csv")
