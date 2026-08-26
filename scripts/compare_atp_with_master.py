#!/usr/bin/env python3
"""ATP（All The Places）を第3ソースとして採るべきか、既存マスターと突合して判断する。

**このスクリプトはマスターを書き換えない**（読むだけ）。採否の材料を出すのが役目。
結果の解釈は docs/sources/検証_AllThePlaces_網羅性と採用可否.md。

入力: data/atp_food_stores_japan.parquet（scripts/fetch_alltheplaces_jp.py の出力）
      data/food_store_master.parquet
      docs/master/検証_マスターPhase1_都道府県別.csv（分母＝実数統計）
出力: docs/sources/検証_AllThePlaces_都道府県別.csv
      data/atp_net_new.parquet（純増分の点。目視確認用）

出す数字:
 1. **純増**: ATP 側に対応するマスター店舗が無い点（＝マスターの穴）
 2. **座標精度**: 同一ブランドの既存店までの距離分布（spider 別）。距離指標に使う
    マスターなので、ジオコーディング品質の悪い spider は採ってはいけない
 3. **都道府県別カバー率**: 実数統計を分母に、現行と「ATP 投入後」を並べる
 4. **消滅疑い**: ATP が扱うブランドなのに ATP 側に無いマスター店舗（閉店の候補）

距離は等距円筒近似（緯度補正した平面距離）。この環境の DuckDB は
ST_Distance_Spheroid が -nan を返して使えない（CLAUDE.md 参照）。
"""
import csv
import os
import sys

import duckdb

ATP = "data/atp_food_stores_japan.parquet"
MASTER = "data/food_store_master.parquet"
PREF_GEOJSON = "data/japan_pref.geojson"
PREF_CSV = "docs/master/検証_マスターPhase1_都道府県別.csv"
# 出力先は差し替え可能にしておく（既定は 2026-08-09 の ATP 公式ラン検証で使ったファイル）。
# データセットを入れ替えて回すときは、既存の検証結果を上書きしないよう別名を渡すこと。
OUT_CSV = os.environ.get("OUT_CSV", "docs/sources/検証_AllThePlaces_都道府県別.csv")
OUT_NEW = "data/atp_net_new.parquet"

RADIUS_M = float(sys.argv[1]) if len(sys.argv) > 1 else 100.0
# 同カテゴリ 100m だけで判定すると、同じファミリーマートが座標ズレで「純増」に化ける
# （100m 純増 7,301 → 500m 純増 2,139 と激減する＝ズレであって穴ではない）。
# 同ブランドが 500m 以内にあれば同一店舗とみなす条件を併用する。
BRAND_RADIUS_M = 500.0

DEG = RADIUS_M / 111320.0
BDEG = BRAND_RADIUS_M / 111320.0
# 等距円筒近似。lon 側は cos(lat) で縮める。1度 ≒ 111,320m。
DIST = ("111320.0 * sqrt(pow(a.lat - m.lat, 2) + "
        "pow((a.lng - m.lng) * cos(radians(a.lat)), 2))")
# ブランド一致は brand 同士を先に見る。**name だけを見てはいけない**：
# ATP の brand "FamilyMart" は Overture の name「ファミリーマート」と一致しない
# （マスター側にも brand 列があり、そこには "FamilyMart" が入っている）。
BRAND_MATCH = ("(m.brand = a.brand or (m.name is not null and m.name like '%' || a.brand || '%'))")

for path in (ATP, MASTER):
    if not os.path.exists(path):
        sys.exit(f"入力が無い: {path}")

con = duckdb.connect()
con.execute("INSTALL spatial; LOAD spatial;")
con.execute(f"create table atp_raw as select * from read_parquet('{ATP}')")
con.execute(f"""create table master as
  select store_id, cat, name, brand, src, prefecture, lat, lng from read_parquet('{MASTER}')""")
con.execute(f"create table pref as select nam_ja as pref, geom from ST_Read('{PREF_GEOJSON}')")
con.execute("""create table atp as
  select a.*, p.pref from atp_raw a join pref p on ST_Contains(p.geom, ST_Point(a.lng, a.lat))""")

n_atp = con.execute("select count(*) from atp").fetchone()[0]
n_out = con.execute("select count(*) from atp_raw").fetchone()[0] - n_atp
n_ms = con.execute("select count(*) from master").fetchone()[0]
print(f"ATP {n_atp:,} 件（都道府県外 {n_out:,} 件は除外）/ マスター {n_ms:,} 件 / "
      f"突合半径 {RADIUS_M:.0f}m（同ブランドは {BRAND_RADIUS_M:.0f}m）\n")

# ---- 1. ATP の各点に対応するマスター店舗があるか ----
con.execute(f"""create table atp_matched as
  select a.*,
    (exists (
      select 1 from master m
      where m.cat = a.cat
        and m.lat between a.lat - {DEG} * 1.1 and a.lat + {DEG} * 1.1
        and m.lng between a.lng - {DEG} * 1.6 and a.lng + {DEG} * 1.6
        and {DIST} <= {RADIUS_M}
    ) or exists (
      select 1 from master m
      where a.brand is not null and length(a.brand) >= 2 and {BRAND_MATCH}
        and m.lat between a.lat - {BDEG} * 1.1 and a.lat + {BDEG} * 1.1
        and m.lng between a.lng - {BDEG} * 1.6 and a.lng + {BDEG} * 1.6
        and {DIST} <= {BRAND_RADIUS_M}
    )) as in_master from atp a""")

print("=== ① カテゴリ別: ATP がマスターに対して何を足せるか ===")
print(f"{'cat':12s} {'ATP':>8s} {'既存と一致':>10s} {'純増':>8s} {'純増率':>7s}  マスター現状")
rows = con.execute("""
  select a.cat, count(*) atp_n, count(*) filter (where in_master) hit,
         count(*) filter (where not in_master) newn,
         (select count(*) from master m where m.cat = a.cat) ms_n
  from atp_matched a group by 1 order by 2 desc""").fetchall()
for cat, atp_n, hit, newn, ms_n in rows:
    print(f"{cat:12s} {atp_n:8,} {hit:10,} {newn:8,} {newn/atp_n*100:6.1f}% {ms_n:12,}")
tot_new = sum(r[3] for r in rows)
print(f"{'合計':12s} {sum(r[1] for r in rows):8,} {sum(r[2] for r in rows):10,} {tot_new:8,}")

print("\n=== ② spider 別: 純増と座標精度 ===")
print("  座標精度＝同ブランドの既存マスター店舗までの距離。中央値が大きい spider は")
print("  住所ジオコーディング品質で、500m 判定に使うマスターには入れられない。")
con.execute(f"""create table nearest as
  select a.spider, a.rowid rid,
         min(111320.0 * sqrt(pow(a.lat - m.lat, 2) +
             pow((a.lng - m.lng) * cos(radians(a.lat)), 2))) d
  from atp a join master m
    on a.brand is not null and length(a.brand) >= 2 and {BRAND_MATCH}
   and m.lat between a.lat - 0.005 and a.lat + 0.005
   and m.lng between a.lng - 0.006 and a.lng + 0.006
  group by a.spider, a.rowid""")
print(f"  {'spider':28s}{'ATP':>7s}{'純増':>7s}{'対応':>7s}{'中央値':>8s}{'p90':>7s}")
for sp, atp_n, newn, pairs, med, p90 in con.execute("""
    select s.spider, s.atp_n, s.newn, n.pairs, n.med, n.p90 from
      (select spider, count(*) atp_n, count(*) filter (where not in_master) newn
       from atp_matched group by 1) s
    left join
      (select spider, count(*) pairs, median(d) med, quantile_cont(d, 0.9) p90
       from nearest group by 1) n using (spider)
    order by s.newn desc""").fetchall():
    m_s = f"{med:.0f}m" if med is not None else "-"
    p_s = f"{p90:.0f}m" if p90 is not None else "-"
    print(f"  {sp:28s}{atp_n:>7,}{newn:>7,}{(pairs or 0):>7,}{m_s:>8s}{p_s:>7s}")

# ---- 3. 都道府県別カバー率（実数統計が分母）----
actual = {}
if os.path.exists(PREF_CSV):
    with open(PREF_CSV, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            actual[(row["cat"], row["都道府県"])] = int(row["実数統計"])
else:
    print(f"\n※ {PREF_CSV} が無いので都道府県別カバー率はスキップ")

if actual:
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    stats = con.execute("""
      select m.cat, m.prefecture pref, count(*) ms_n,
             coalesce(a.atp_n, 0) atp_n, coalesce(a.newn, 0) newn
      from master m left join
        (select cat, pref, count(*) atp_n, count(*) filter (where not in_master) newn
         from atp_matched group by 1, 2) a
        on a.cat = m.cat and a.pref = m.prefecture
      group by 1, 2, 4, 5 order by 1, 2""").fetchall()
    with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["cat", "都道府県", "マスター件数", "ATP件数", "ATP純増",
                    "投入後件数", "実数統計", "カバー率_現行", "カバー率_ATP単独",
                    "カバー率_投入後"])
        for cat, pref, ms_n, atp_n, newn in stats:
            act = actual.get((cat, pref))
            after = ms_n + newn
            w.writerow([cat, pref, ms_n, atp_n, newn, after, act or "",
                        f"{ms_n/act:.3f}" if act else "",
                        f"{atp_n/act:.3f}" if act else "",
                        f"{after/act:.3f}" if act else ""])
    print(f"\n=== ③ 都道府県別カバー率 → {OUT_CSV} ===")
    print("  ATP単独＝ATP だけを実数統計と比べた率。マスターと足し合わせていないので、")
    print("  「そのカテゴリを ATP がどれだけ持っているか」を素で表す。")
    print(f"  {'cat':13s}{'現行':>9s}{'ATP':>8s}{'純増':>8s}{'投入後':>9s}{'実数':>9s}"
          f"{'現行率':>9s}{'ATP単独':>9s}{'投入後率':>10s}")
    for cat, ms_n, _, _ in con.execute("""
        select cat, count(*) ms_n, 0, 0 from master group by 1""").fetchall():
        act = sum(v for (c, _), v in actual.items() if c == cat)
        newn = sum(r[4] for r in stats if r[0] == cat)
        atp_n = sum(r[3] for r in stats if r[0] == cat)
        after = ms_n + newn
        print(f"  {cat:13s}{ms_n:>9,}{atp_n:>8,}{newn:>8,}{after:>9,}{act:>9,}"
              f"{ms_n/act*100:>8.1f}%{atp_n/act*100:>8.1f}%{after/act*100:>9.1f}%")

# ---- 4. 消滅疑い ----
# ATP が spider を持つブランドだけを対象にしないと、単に「ATP が知らない店」を
# 閉店と誤認する。さらに **都道府県でスコープを切る** ことが必須。
# 例: aeon_hokkaido_jp は北海道のイオンしか持たないので、全国のイオンと比べると
# 全件が「ATP に無い」になり、閉店ではなく ATP のカバー範囲外を数えてしまう。
con.execute("""create table brand_pref as
  select distinct brand, pref from atp where brand is not null and length(brand) >= 2""")
con.execute("""create table ms_target as
  select m.*, b.brand atp_brand from master m join brand_pref b
    on (m.brand = b.brand or (m.name is not null and m.name like '%' || b.brand || '%'))
   and m.prefecture = b.pref""")
con.execute(f"""create table ms_checked as
  select t.*, exists (
    select 1 from atp a
    where a.cat = t.cat and a.brand = t.atp_brand
      and a.lat between t.lat - {DEG} * 1.1 and a.lat + {DEG} * 1.1
      and a.lng between t.lng - {DEG} * 1.6 and a.lng + {DEG} * 1.6
      and 111320.0 * sqrt(pow(a.lat - t.lat, 2) +
          pow((a.lng - t.lng) * cos(radians(a.lat)), 2)) <= {RADIUS_M}
  ) as in_atp from ms_target t""")

print("\n=== ④ 消滅疑い: ATP が扱うブランドなのに ATP 側に対応点が無いマスター店舗 ===")
print("（ATP のスパイダー失敗・取りこぼしも混ざるので、そのまま削除してはいけない）")
for brand, ms_n, missing in con.execute("""
    select atp_brand, count(*), count(*) filter (where not in_atp)
    from ms_checked group by 1 having count(*) >= 50 order by 3 desc limit 15""").fetchall():
    print(f"  {brand:24s} マスター {ms_n:6,}  ATP に無い {missing:6,} ({missing/ms_n*100:5.1f}%)")

con.execute(f"copy (select * from atp_matched where not in_master) to '{OUT_NEW}' (FORMAT parquet)")
print(f"\n純増分を {OUT_NEW} に出力（{tot_new:,} 件）")
