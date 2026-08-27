#!/usr/bin/env python3
"""食品営業届出の「⑪ 百貨店、総合スーパー」から、マスターに無いスーパーを拾う（issue #26）。

**このスクリプトはマスターを書き換えない**（読むだけ）。採否の材料を出すのが役目。
ATP（チェーン公式サイトのクロール）は supermarket 46.6% で頭打ちで、残っているのは
地場スーパー・JA の生活センターなど公式サイトが無い層。届出データはその層を含む。

入力: data/facilities-all.csv（japan-facilities-address の統合出力。1,437,799行）
      data/food_store_master.parquet（FOOD_MASTER で差し替え可）
出力: data/permit_supermarket_candidates.parquet（判定フラグ付きの全候補）
      docs/sources/検証_許可データ_総合スーパー_都道府県別.csv

注意点:
 - **区分番号は衝突する**。「⑪」は許可業種の「⑪ 菓子製造業」(37,032行)にも使われる。
   区分名まで含めた完全一致で抽出すること。
 - **⑪ 行に license_date / expire_date は無い**（届出には許可期限が無く、全件空）。
   したがって**廃業の除外はこのデータでは不可能**。閉店が混じる方向の偽陽性が残る。
 - 距離は等距円筒近似（この環境の DuckDB は ST_Distance_Spheroid が -nan。CLAUDE.md）。
"""
import csv
import os
import sys

import duckdb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from food_store_rules import match_key_sql, permit_excluded_sql  # noqa: E402

PERMIT_CSV = os.environ.get("PERMIT_CSV", "data/facilities-all.csv")
MASTER = os.environ.get("FOOD_MASTER", "data/food_store_master.parquet")
OUT_PARQUET = os.environ.get("OUT_PARQUET", "data/permit_supermarket_candidates.parquet")
OUT_CSV = os.environ.get(
    "OUT_CSV", "docs/sources/検証_許可データ_総合スーパー_都道府県別.csv")
PREF_STATS_CSV = "docs/master/検証_マスターPhase1_都道府県別.csv"

BUSINESS_TYPE = "⑪ 百貨店、総合スーパー"
RADIUS_M = float(os.environ.get("RADIUS_M", "100"))
BRAND_RADIUS_M = 500.0   # 同ブランドがこの距離内にあれば同一店（座標ズレ対策）
DEDUP_M = 50.0           # 同名がこの距離内にある行は同一施設として畳む
BKEY_LEN = 5             # ブランド突合キーの文字数

DIST = ("111320.0 * sqrt(pow(a.lat - m.lat, 2) + "
        "pow((a.lng - m.lng) * cos(radians(a.lat)), 2))")

for path in (PERMIT_CSV, MASTER):
    if not os.path.exists(path):
        sys.exit(f"入力が無い: {path}")

con = duckdb.connect()
NN = match_key_sql("name")

# ---- 1. ⑪ を施設単位に畳む ----
con.execute(f"""create table raw as
  select prefecture, city, name, address,
         try_cast(lat as double) lat, try_cast(lng as double) lng,
         geocoding_level glv, sources,
         {NN} nname
  from read_csv('{PERMIT_CSV}', header=true, all_varchar=true)
  where business_type = '{BUSINESS_TYPE}'""")
n_raw = con.execute("select count(*) from raw").fetchone()[0]

# any_value は行の選び方が実行ごとに変わり、境界上の店の距離判定が ±1 件ぶれる。
# 再現性のため min で固定する（同一施設の複数行なので値はほぼ同じ）。
con.execute("""create table fac as
  select prefecture, city, nname, address,
         min(name) as name, min(lat) lat, min(lng) lng,
         min(glv) glv, min(sources) sources,
         prefecture || '|' || city || '|' || nname || '|' || address as fkey
  from raw group by 1,2,3,4""")
n_fac = con.execute("select count(*) from fac").fetchone()[0]

# 同名が DEDUP_M 内に複数ある（住所表記だけ違う同一施設）ものを畳む。
# 代表はキー順で最小の行。**rowid は使わない**（並列実行で順序が変わり再現しない）。
con.execute(f"""create table fac2 as
  with pairs as (
    select a.fkey ra, min(b.fkey) keep
    from fac a join fac b
      on a.nname = b.nname and a.prefecture = b.prefecture
     and b.lat between a.lat - 0.0005 and a.lat + 0.0005
     and b.lng between a.lng - 0.0007 and a.lng + 0.0007
     and 111320.0 * sqrt(pow(a.lat - b.lat, 2) +
         pow((a.lng - b.lng) * cos(radians(a.lat)), 2)) <= {DEDUP_M}
    group by a.fkey)
  select f.* from fac f join pairs p on f.fkey = p.ra and p.ra = p.keep""")
n_fac2 = con.execute("select count(*) from fac2").fetchone()[0]

# ---- 2. 業態フィルタと座標欠損 ----
EXCL = permit_excluded_sql("name")
con.execute(f"""create table cand as
  select *, substr(nname, 1, {BKEY_LEN}) bkey from fac2
  where not {EXCL} and name is not null and trim(name) <> ''
    and lat is not null and lng is not null""")
n_cand = con.execute("select count(*) from cand").fetchone()[0]
n_excl = con.execute(f"select count(*) from fac2 where {EXCL}").fetchone()[0]
n_nocoord = con.execute(
    "select count(*) from fac2 where lat is null or lng is null").fetchone()[0]

print(f"⑪『{BUSINESS_TYPE}』 生行数 {n_raw:,}")
print(f"  → 施設単位（県・市・正規化名・住所）  {n_fac:,}")
print(f"  → 同名 {DEDUP_M:.0f}m 内の重複を畳む      {n_fac2:,}")
print(f"  → 業態フィルタで除外 {n_excl:,} / 座標欠損 {n_nocoord:,}")
print(f"  → 候補                                {n_cand:,}\n")

# ---- 3. マスターとの突合 ----
con.execute(f"""create table master as
  select store_id, cat, name, brand, prefecture, lat, lng,
         {match_key_sql('name')} nname, substr({match_key_sql('name')}, 1, {BKEY_LEN}) bkey
  from read_parquet('{MASTER}')""")
n_ms = con.execute("select count(*) from master").fetchone()[0]
print(f"マスター {MASTER}: {n_ms:,} 件 / 突合半径 {RADIUS_M:.0f}m"
      f"（同ブランドは {BRAND_RADIUS_M:.0f}m）\n")

BDEG = BRAND_RADIUS_M / 111320.0
# ブランド突合は**両方向**見る。片方向（許可の先頭5文字がマスター名に含まれる）だけだと
# 「イオンリテール株式会社イオン小松店」の突合キーが「イオンリテル」始まりになって
# マスターの「イオン小松店」に当たらない。逆方向（マスターの先頭5文字が許可名に含まれる）で救う。
# 5文字未満のキーは総称（「スーパー」等）に当たって過剰一致するので使わない。
BRAND_MATCH = ("((length(a.bkey) >= 5 and m.nname like '%' || a.bkey || '%') or "
               "(length(m.bkey) >= 5 and a.nname like '%' || m.bkey || '%'))")


def near_expr(radius: float) -> str:
    deg = radius / 111320.0
    return f"""exists (
      select 1 from master m
      where m.lat between a.lat - {deg} * 1.1 and a.lat + {deg} * 1.1
        and m.lng between a.lng - {deg} * 1.6 and a.lng + {deg} * 1.6
        and {DIST} <= {radius})"""


BRAND_EXPR = f"""exists (
      select 1 from master m
      where {BRAND_MATCH}
        and m.lat between a.lat - {BDEG} * 1.1 and a.lat + {BDEG} * 1.1
        and m.lng between a.lng - {BDEG} * 1.6 and a.lng + {BDEG} * 1.6
        and {DIST} <= {BRAND_RADIUS_M})"""

RADII = [50, 100, 200, 300, 500]
cols = ",\n    ".join(f"{near_expr(r)} near_{r}" for r in RADII)
con.execute(f"""create table matched as
  select a.*,
    {cols},
    {BRAND_EXPR} brand_hit
  from cand a""")

print("=== ① 突合半径の感度（純増＝マスターに対応が無い候補）===")
print(f"{'半径':>6s} {'距離のみで一致':>14s} {'同ブランド500mも':>16s} {'純増':>8s} {'純増率':>7s}")
sens = {}
for r in RADII:
    hit, both, newn = con.execute(f"""
      select count(*) filter (where near_{r}),
             count(*) filter (where near_{r} or brand_hit),
             count(*) filter (where not (near_{r} or brand_hit)) from matched""").fetchone()
    sens[r] = newn
    print(f"{r:5d}m {hit:14,} {both:16,} {newn:8,} {newn / n_cand * 100:6.1f}%")

# ---- 4. 座標精度: 同ブランドの既存店までの距離分布 ----
print("\n=== ② 許可データの座標精度（同ブランドの既存マスター店舗までの距離）===")
print("  この分布が 100m を大きく超えるなら、100m 判定の『純増』は座標ズレを拾っている。")
row = con.execute(f"""
  with nearest as (
    select a.fkey rid, a.glv,
      min(111320.0 * sqrt(pow(a.lat - m.lat, 2) +
          pow((a.lng - m.lng) * cos(radians(a.lat)), 2))) d
    from cand a join master m
      on {BRAND_MATCH}
     and m.lat between a.lat - 0.005 and a.lat + 0.005
     and m.lng between a.lng - 0.007 and a.lng + 0.007
    group by a.fkey, a.glv)
  select count(*), median(d), quantile_cont(d, 0.75), quantile_cont(d, 0.9),
         count(*) filter (where d <= 50), count(*) filter (where d <= 100)
  from nearest""").fetchone()
pairs, med, p75, p90, le50, le100 = row
print(f"  対応が取れた候補 {pairs:,} 件 / 中央値 {med:.0f}m / p75 {p75:.0f}m / p90 {p90:.0f}m")
print(f"  50m以内 {le50:,} 件（{le50 / pairs * 100:.1f}%）/ 100m以内 {le100:,} 件"
      f"（{le100 / pairs * 100:.1f}%）")

# ---- 5. 県別カバー率（実数統計＝経済センサス 581 を分母に、純増投入後を並べる）----
#
# 許可データは新潟・茨城・宮崎等に既知の穴があるので、増え方が県で偏らないかを見る。
# 分母は既存の検証で使っている実数統計（docs/master/検証_マスターPhase1_都道府県別.csv）。
print("\n=== ③ 県別: supermarket のカバー率が実数統計を超えないか ===")
stats = {}
if os.path.exists(PREF_STATS_CSV):
    with open(PREF_STATS_CSV, encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            if r["cat"] == "supermarket":
                stats[r["都道府県"]] = (int(r["マスター件数"]), int(r["実数統計"]))
else:
    print(f"  （分母 CSV が無い: {PREF_STATS_CSV}）")

rows = con.execute(f"""
  select prefecture, count(*) cand,
         count(*) filter (where near_{int(RADIUS_M)} or brand_hit) hit,
         count(*) filter (where not (near_{int(RADIUS_M)} or brand_hit)) newn
  from matched group by 1 order by 1""").fetchall()

os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
over = []
with open(OUT_CSV, "w", encoding="utf-8", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["都道府県", "⑪候補", "既存と一致", "純増", "純増率(%)",
                "マスターsupermarket", "実数統計(センサス581)", "現状率(%)", "投入後率(%)"])
    for pref, c, h, nn in rows:
        ms, real = stats.get(pref, (0, 0))
        cur = ms / real * 100 if real else 0.0
        aft = (ms + nn) / real * 100 if real else 0.0
        if real and aft > 100:
            over.append((pref, cur, aft))
        w.writerow([pref, c, h, nn, f"{nn / c * 100:.1f}", ms, real,
                    f"{cur:.1f}", f"{aft:.1f}"])
tot_ms = sum(v[0] for v in stats.values())
tot_real = sum(v[1] for v in stats.values())
tot_new = sum(r[3] for r in rows)
if tot_real:
    print(f"  全国: マスター {tot_ms:,} / 実数統計 {tot_real:,} = {tot_ms / tot_real * 100:.1f}%"
          f" → 純増 {tot_new:,} 投入後 {(tot_ms + tot_new) / tot_real * 100:.1f}%")
print(f"  投入後に 100% を超える県: {len(over)} / {len(rows)}")
for pref, cur, aft in sorted(over, key=lambda x: -x[2])[:12]:
    print(f"    {pref:6s} {cur:5.1f}% → {aft:5.1f}%")
print(f"\n県別: {OUT_CSV}")

con.execute(f"""copy (select prefecture, city, name, nname, address, lat, lng, glv, sources,
    near_{int(RADIUS_M)} as near_hit, brand_hit,
    not (near_{int(RADIUS_M)} or brand_hit) as net_new
  from matched) to '{OUT_PARQUET}' (format parquet)""")
print(f"候補（フラグ付き）: {OUT_PARQUET}")
