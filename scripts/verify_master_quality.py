#!/usr/bin/env python3
"""
食料品店マスターの網羅性・正確性を検証する（用途: 125mメッシュ重心×道路距離500m判定・全国）。

なぜ件数カバー率だけでは足りないか
----------------------------------
判定が「最近隣の1店までの距離が500mを超えるか」という二値・距離閾値なので:
  - 過剰（同じ地域に店が多い）は無害。すでに圏内の地点に店を足しても判定は変わらない。
  - 欠落は「その店がその地点で唯一の店」だったときだけ効く。効いたときはその
    125mメッシュの住民全員が圏外に振り替わる。
→ 「不足数 × 単独店率」で欠落の影響を見積もり、偽陽性と位置ズレを実測する。

出力する指標
------------
  ① カテゴリ別 全国カバー率（分母の実数統計だけ 検証_マスターPhase1_都道府県別.csv から取り、
     マスター件数はその場で数える）
  ② 単独店率（500m直線以内に他の食料品店が無い店舗の割合）＝道路距離では上振れするので下限
  ③ 欠落の影響見積もり（不足数 × 単独店率）
  ④ 都道府県別 単独店率（欠落がどこで効くか）
  ⑤ 位置精度（同一コンビニの Overture 座標 vs OSM 座標のズレ分布）
  ⑥ 重複（名称一致・50m以内）
  ⑦ 偽陽性（調剤専業の取りこぼし・ノイズ名称・閉店の除外可否・confidence 分布）
  ⑧ 座標品質（代表点集積・粗座標・同一座標・名称欠損）

距離は等距円筒近似（緯度補正した平面距離）。この環境の DuckDB は
`ST_Distance_Spheroid` が -nan を返すため（CLAUDE.md 参照）。

使い方:
  python3 scripts/verify_master_quality.py
"""
import csv
import os
import sys
from collections import defaultdict

import duckdb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from food_store_rules import dispensing_only_sql  # noqa: E402

MASTER = "data/food_store_master.parquet"
OSM_TSV = "data/osm_food_stores_japan.tsv"
OVERTURE_DEDUP = "data/overture_food_deduped_jp.parquet"
PREF_CSV = "docs/検証_マスターPhase1_都道府県別.csv"

# 500m を緯度の度数に換算（経度側は cos(lat) で補正して使う）
DEG_500M = 0.0045
DEG_50M = 0.00045
DEG_200M = 0.0018

# 「500m以内に他店が無いか」を判定する述語。等距円筒近似。
NEAR = """abs(b.lat-a.lat) < {deg}
      and abs(b.lng-a.lng) < {deg}/cos(radians(a.lat))
      and 111320*sqrt(power(b.lat-a.lat,2)
                    + power((b.lng-a.lng)*cos(radians(a.lat)),2)) <= {m}"""

# 食料品店でない疑いの名称
NOISE_NAME = """(name ilike '%カフェ%' or name ilike '%cafe%' or name ilike '%coffee%'
   or name ilike '%食堂%' or name ilike '%レストラン%' or name ilike '%雑貨%'
   or name ilike '%100円%' or name ilike '%ダイソー%' or name ilike '%居酒屋%'
   or name ilike '%ラーメン%')"""

def h(title):
    print(f"\n{'=' * 68}\n{title}\n{'=' * 68}")


def coverage_from_csv(con):
    """① 全国カバー率。

    実数統計（分母＝業界実数・センサス等の外部数値）だけ県別検証CSVから読み、
    **マスター件数はその場でマスターから数える**。CSV のマスター件数は構築時点の
    スナップショットなので、除外ルールの追加などで再構築すると古くなる（実際、
    調剤専業の除外前の値のままだと ① と ② で drugstore の総数が食い違った）。
    """
    if not os.path.exists(PREF_CSV):
        print(f"  {PREF_CSV} が無いのでスキップ")
        return {}
    master, actual = defaultdict(int), defaultdict(int)
    for cat, n in con.execute("select cat, count(*) from m group by 1").fetchall():
        master[cat] = n
    with open(PREF_CSV, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            actual[row["cat"]] += int(row["実数統計"])
    print(f"  {'cat':13s}{'マスター':>10s}{'実数':>10s}{'カバー率':>10s}{'不足':>10s}")
    short = {}
    for cat in sorted(master, key=lambda c: -master[c]):
        rate = master[cat] / actual[cat]
        gap = actual[cat] - master[cat]
        short[cat] = gap
        note = "（広義）" if rate > 1.2 else ""
        print(f"  {cat:13s}{master[cat]:>10,}{actual[cat]:>10,}"
              f"{rate*100:>9.0f}%{gap:>10,}{note}")
    return short


def main():
    for f in (MASTER,):
        if not os.path.exists(f):
            sys.exit(f"入力が無い: {f}")

    con = duckdb.connect()
    con.execute(f"""create table m as
      select store_id rid, cat, name, brand, src, prefecture pref, lat, lng
      from read_parquet('{MASTER}')""")
    total = con.execute("select count(*) from m").fetchone()[0]
    print(f"マスター {total:,} 店")

    h("① カテゴリ別 全国カバー率")
    shortfall = coverage_from_csv(con)

    h("② 単独店率（500m直線以内に他の食料品店が1軒も無い店舗）")
    print("  ※道路距離は直線距離以上なので、これは単独店率の下限")
    near = NEAR.format(deg=DEG_500M, m=500)
    sole = con.execute(f"""
      select a.cat, count(*) n,
             sum(case when not exists (
               select 1 from m b where b.rid <> a.rid and {near}) then 1 else 0 end) solo
      from m a group by a.cat order by n desc""").fetchall()
    print(f"  {'cat':13s}{'総数':>9s}{'単独店':>9s}{'単独率':>9s}")
    sole_rate = {}
    for cat, n, solo in sole:
        sole_rate[cat] = solo / n
        print(f"  {cat:13s}{n:>9,}{solo:>9,}{solo/n*100:>8.1f}%")

    h("③ 欠落の影響見積もり（不足数 × 単独店率）")
    print("  ＝「実際は店があるのにマスターでは圏外と判定される地点」の概数")
    tot = 0
    for cat, gap in sorted(shortfall.items(), key=lambda kv: -kv[1]):
        if gap <= 0 or cat not in sole_rate:
            continue
        impact = gap * sole_rate[cat]
        tot += impact
        print(f"  {cat:13s} 不足 {gap:>7,} × 単独率 {sole_rate[cat]*100:4.1f}% "
              f"= 約 {impact:>7,.0f} 地点")
    print(f"  {'計':13s} {'':>21s}   約 {tot:>7,.0f} 地点（下限）")

    h("④ 都道府県別 単独店率（欠落がどこで効くか）top10")
    for pref, n, solo, rate in con.execute(f"""
      select a.pref, count(*) n,
             sum(case when not exists (select 1 from m b where b.rid<>a.rid and {near})
                 then 1 else 0 end) solo,
             sum(case when not exists (select 1 from m b where b.rid<>a.rid and {near})
                 then 1 else 0 end)*1.0/count(*) rate
      from m a group by 1 order by rate desc limit 10""").fetchall():
        print(f"  {pref:8s} 店舗 {n:>6,} / 単独 {solo:>5,} = {rate*100:5.1f}%")

    h("⑤ 位置精度（同一コンビニの Overture 座標 vs OSM 座標のズレ）")
    if not os.path.exists(OSM_TSV):
        print(f"  {OSM_TSV} が無いのでスキップ")
    else:
        con.execute(f"""create table osm_cv as
          select TRY_CAST("@lat" as double) lat, TRY_CAST("@lon" as double) lng
          from read_csv_auto('{OSM_TSV}', sep='\t', all_varchar=true)
          where shop='convenience' and TRY_CAST("@lat" as double) is not null""")
        con.execute(f"""create table pair as
          select o.rowid oid,
                 min(111320*sqrt(power(o.lat-c.lat,2)
                               + power((o.lng-c.lng)*cos(radians(o.lat)),2))) d
          from osm_cv o join (select lat,lng from m where cat='convenience') c
            on abs(o.lat-c.lat) < {DEG_200M}
           and abs(o.lng-c.lng) < {DEG_200M}/cos(radians(o.lat))
          group by o.rowid""")
        n, med, p90, p99, mx = con.execute("""
          select count(*), median(d), quantile_cont(d,0.9), quantile_cont(d,0.99), max(d)
          from pair""").fetchone()
        print(f"  対応 {n:,} 組  中央値 {med:.1f}m  p90 {p90:.1f}m  p99 {p99:.1f}m  最大 {mx:.1f}m")
        print("  ※200m以内でペアリングしているため裾は切断。片方にしか無い店が近くの別店と")
        print("    誤対応して裾を膨らませる。中央値は頑健、p90/p99 は上振れと読む。")
        print("  ※p90が125mメッシュのセル対角(約177m)と同オーダー＝500m境界付近で判定が反転しうる。")

    h("⑥ 重複（同カテゴリ・名称一致・50m以内）")
    near50 = NEAR.format(deg=DEG_50M, m=50)
    con.execute("""create table mn as
      select rid, cat, lower(regexp_replace(coalesce(name,''),'[[:space:]　]','','g')) nm,
             lat, lng from m""")
    dup = con.execute(f"""
      select a.cat, count(*) from mn a
      where a.nm <> '' and exists (
        select 1 from mn b where b.rid<>a.rid and b.cat=a.cat and b.nm=a.nm
          and {near50})
      group by 1 order by 2 desc""").fetchall()
    print(f"  計 {sum(c for _, c in dup):,} 件（{sum(c for _, c in dup)/total*100:.1f}%）"
          " ← 最近隣距離の判定には無害、件数集計にのみ影響")
    for cat, c in dup:
        print(f"    {cat:13s}{c:>6,}")

    h("⑦ 偽陽性（実在しない／食品を扱わない店）")
    yak, susp = con.execute(f"""
      select count(*), sum(case when {dispensing_only_sql('name')} then 1 else 0 end)
      from m where name ilike '%薬局%' or name ilike '%調剤%'""").fetchone()
    print(f"  名称に薬局/調剤を含む: {yak:,}")
    print(f"    うちドラッグストアと判定して残した分（食品を扱う正規店）: {yak - (susp or 0):,}")
    print(f"    残っている調剤専業の疑い: {susp or 0:,} "
          f"（マスターの {(susp or 0)/total*100:.2f}%。構築側で除外済みなら 0）")
    print("  ノイズ名称（カフェ/食堂/雑貨/100円 等）:")
    for cat, c in con.execute(
            f"select cat, count(*) from m where {NOISE_NAME} group by 1 order by 2 desc").fetchall():
        print(f"    {cat:13s}{c:>6,}")
    print("  閉店店舗: Overture の operating_status は deduped版・full版とも日本の全レコードが")
    print("            NULL のため除外不能（定量不能な偽陽性リスク）。別ソースが必要。")
    if os.path.exists(OVERTURE_DEDUP):
        print("  confidence（Overture信頼度・マスター構築では未使用＝偽陽性フィルタに使える）:")
        rows = con.execute(f"""
          select category, count(*), median(confidence),
                 sum(case when confidence < 0.5 then 1 else 0 end),
                 sum(case when confidence < 0.3 then 1 else 0 end)
          from read_parquet('{OVERTURE_DEDUP}')
          where category in ('supermarket','grocery_store','convenience_store',
                             'drugstore','butcher_shop','seafood_market')
          group by 1 order by 2 desc""").fetchall()
        print(f"    {'category':20s}{'件数':>9s}{'中央値':>8s}{'<0.5':>8s}{'<0.3':>7s}")
        for cat, n, med, c5, c3 in rows:
            print(f"    {cat:20s}{n:>9,}{med:>8.3f}{c5:>8,}{c3:>7,}")
        print(f"    {'計':20s}{'':>17s}{sum(r[3] for r in rows):>8,}{sum(r[4] for r in rows):>7,}")

    h("⑧ 座標品質")
    for label, q in [
        ("名称 NULL/空", "select count(*) from m where name is null or trim(name)=''"),
        ("座標が小数3桁以下（≒100m格子に丸め）",
         "select count(*) from m where abs(lat*1000-round(lat*1000))<1e-9 "
         "and abs(lng*1000-round(lng*1000))<1e-9"),
        ("完全同一座標に重なる組",
         "select count(*) from (select lat,lng from m group by 1,2 having count(*)>1)"),
    ]:
        print(f"  {label:38s}{con.execute(q).fetchone()[0]:>8,}")
    print("  ジオコーディング代表点への集積 top3（1点に大量に積まれていないか）:")
    for lat, lng, c in con.execute("""
          select round(lat,4), round(lng,4), count(*) c from m
          group by 1,2 order by c desc limit 3""").fetchall():
        print(f"    ({lat}, {lng}) {c} 件")


if __name__ == "__main__":
    main()
