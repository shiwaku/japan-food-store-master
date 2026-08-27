#!/usr/bin/env python3
"""マスターの supermarket を業態別に分解し、分母を確定する（issue #33）。

**マスターを書き換えない**（読むだけ）。「supermarket が実数の137%」の中身を割る。

マスターの supermarket は2系統の合成で、**業態が違うので分母も違う**:
  ① src_cat='supermarket'    Overture supermarket → スーパー・GMS 本体
     → 分母は経済センサス 561（百貨店・総合スーパー）+ 581（各種食料品小売業）= 23,401
  ② src_cat='grocery_store'  浄化 grocery_store（①の100m近傍は構築時に除外済み）
     → 各種食料品店（小規模）。センサス 589系（その他の飲食料品小売業）相当で、
        **分母が手元に無い**（e-Stat getStatsData の appId が必要。リポジトリには無い）

入力: data/food_store_master.parquet（`src_cat` 列。無ければ build を回し直す）
      docs/sources/検証_スーパーコンビニ網羅性_都道府県別.csv（センサス561+581 の県別）
出力: docs/master/検証_supermarket分解_都道府県別.csv
"""
import csv
import os
import sys

import duckdb

MASTER = os.environ.get("FOOD_MASTER", "data/food_store_master.parquet")
CENSUS_CSV = "docs/sources/検証_スーパーコンビニ網羅性_都道府県別.csv"
OUT_CSV = os.environ.get("OUT_CSV", "docs/master/検証_supermarket分解_都道府県別.csv")

con = duckdb.connect()
cols = [r[0] for r in con.execute(
    f"describe select * from read_parquet('{MASTER}')").fetchall()]
if "src_cat" not in cols:
    sys.exit(f"{MASTER} に src_cat 列が無い。python3 scripts/build_food_store_master.py "
             "を回し直すこと（issue #33 で追加した列）。")

con.execute(f"""create table sm as
  select prefecture, src_cat from read_parquet('{MASTER}') where cat='supermarket'""")
n_sm, n_gc = con.execute("""select count(*) filter (where src_cat='supermarket'),
  count(*) filter (where src_cat='grocery_store') from sm""").fetchone()
print("マスター supermarket の内訳")
print(f"  ① Overture supermarket   {n_sm:8,}")
print(f"  ② 浄化 grocery_store     {n_gc:8,}")
print(f"  合計                     {n_sm + n_gc:8,}\n")

census = {}
with open(CENSUS_CSV, encoding="utf-8-sig") as fh:
    for r in csv.DictReader(fh):
        census[r["都道府県"]] = int(r["センサス_スーパー561+581"])
tot_c = sum(census.values())

print("=== 分母をセンサス561+581 に取り直したカバー率 ===")
print(f"  ① だけ: {n_sm:,} / {tot_c:,} = {n_sm / tot_c * 100:.1f}%   ← 本来のスーパーのカバー率")
print(f"  ①+②   : {n_sm + n_gc:,} / {tot_c:,} = {(n_sm + n_gc) / tot_c * 100:.1f}%"
      f"   ← 従来の『137%』の正体\n")

rows = con.execute("""
  select prefecture,
         count(*) filter (where src_cat='supermarket') sm,
         count(*) filter (where src_cat='grocery_store') gc
  from sm group by 1 order by 1""").fetchall()

os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
under = []
with open(OUT_CSV, "w", encoding="utf-8", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["都道府県", "①Overture_supermarket", "②浄化grocery_store", "合計",
                "センサス561+581", "①のカバー率(%)", "①+②のカバー率(%)"])
    for pref, s, g in rows:
        c = census.get(pref, 0)
        r1 = s / c * 100 if c else 0.0
        r2 = (s + g) / c * 100 if c else 0.0
        if c and r1 < 100:
            under.append((pref, r1, r2))
        w.writerow([pref, s, g, s + g, c, f"{r1:.1f}", f"{r2:.1f}"])

print(f"① が実数を下回る県: {len(under)} / {len(rows)}")
for pref, r1, r2 in sorted(under, key=lambda x: x[1])[:12]:
    print(f"  {pref:6s} ①{r1:5.1f}%  （①+② {r2:5.1f}%）")
print(f"\n出力: {OUT_CSV}")
