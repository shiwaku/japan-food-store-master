#!/usr/bin/env python3
"""**ATP（チェーン公式サイト由来）を正解データ**にして、店舗レイヤの網羅性と位置精度を測る。

ATP は自前クロール38本が再配布不可なので**公開マスターには入れられない**が、
**分析・検証に使うことに制約は無い**（`docs/sources/調査_自前クロールソースの利用規約と再配布可否.md`）。
チェーン店については各社の公表値そのものなので、**網羅性の基準**として最も確からしい。

測るもの
--------
- **再現率**: ATP の1店ごとに、評価対象レイヤの同カテゴリ店舗が `NEAR_M`（既定100m）以内にあるか。
  **チェーン店に限った網羅率**であって、独立店の網羅性は測れない（ATP に独立店が無いため）。
- **位置ずれ**: 当たった組の距離の中央値・p90。測地系ズレやジオコーディング品質の検知に使う。
- **県別再現率**: どこに穴があるか。

ATP 側の限界も込みで読むこと（`docs/master/定義対照_農水省_vs_ATP.md`）:
supermarket は実数の 46.6% しか無く（チェーン化率が低い業態）、fresh_food は 0。
**再現率が高い＝レイヤが良い、と言えるのは convenience と drugstore が中心。**

使い方
------
  python scripts/eval_master_against_atp.py                       # 既定の3レイヤを比較
  LAYERS=data/food_store_master_public.parquet python scripts/eval_master_against_atp.py
"""
import os
import sys

import duckdb

ATP = os.environ.get("ATP", "data/atp_food_stores_japan_geo.parquet")
NEAR_M = float(os.environ.get("NEAR_M", "100"))
DEFAULT_LAYERS = [
    # 先頭が比較の基準。ATP基準はATPを内包するので再現率100%は自明（基準としてのみ置く）。
    ("Phase1（Overture+OSM）", "data/food_store_master.parquet"),
    ("公開可能（Overture+許可・ODbL無し）", "data/food_store_master_public_noosm.parquet"),
    ("公開可能（Overture+OSM+許可）", "data/food_store_master_public.parquet"),
    ("ATP基準＋許可⑪（現行・非公開）", "data/food_store_master_atp_super.parquet"),
]
LAYERS = [(os.path.basename(p), p) for p in os.environ["LAYERS"].split(",")] \
    if os.environ.get("LAYERS") else DEFAULT_LAYERS

DIST = ("111320.0 * sqrt(pow(t.lat - m.lat, 2) + "
        "pow((t.lng - m.lng) * cos(radians(t.lat)), 2))")


def main():
    if not os.path.exists(ATP):
        sys.exit("ATP が無い: " + ATP)
    con = duckdb.connect()
    con.execute(f"""create table truth as
      select cat, name, brand, prefecture, lat, lng from '{ATP}'
      where lat is not null and cat <> 'fresh_food'""")
    n_t = con.execute("select count(*) from truth").fetchone()[0]
    print("正解データ ATP: {:,} 店（fresh_food は1件しか無いので除外）".format(n_t))
    print(con.execute("select cat, count(*) n from truth group by 1 order by 2 desc"
                      ).df().to_string(index=False))

    deg = NEAR_M / 111320.0
    results = {}
    for label, path in LAYERS:
        if not os.path.exists(path):
            print("\n(スキップ) 入力が無い: " + path)
            continue
        con.execute("drop table if exists layer")
        con.execute(f"create table layer as select cat, lat, lng from '{path}'")
        con.execute("drop table if exists hit")
        con.execute("""create table hit as
          select t.rowid rid, t.cat, t.prefecture,
                 min(case when {dist} <= {n} then {dist} end) nd
          from truth t left join layer m
            on m.cat = t.cat
           and m.lat between t.lat - {d}*1.1 and t.lat + {d}*1.1
           and m.lng between t.lng - {d}*1.6 and t.lng + {d}*1.6
          group by 1,2,3""".format(dist=DIST, n=NEAR_M, d=deg))
        n_l = con.execute(f"select count(*) from '{path}'").fetchone()[0]
        r = con.execute("""select cat, count(*) atp,
            count(nd) hit, round(100.0*count(nd)/count(*),1) recall,
            round(median(nd),1) 位置ずれ中央値, round(quantile_cont(nd,0.9),1) p90
          from hit group by 1 order by 2 desc""").df()
        tot = con.execute("""select round(100.0*count(nd)/count(*),1) from hit"""
                          ).fetchone()[0]
        print("\n=== {} （{:,} 店）  全体の再現率 {}% ===".format(label, n_l, tot))
        print(r.to_string(index=False))
        results[label] = con.execute("""select prefecture,
            round(100.0*count(nd)/count(*),1) recall from hit
          group by 1""").df().set_index("prefecture")["recall"]

    if len(results) > 1:
        import pandas as pd
        df = pd.DataFrame(results).dropna()
        base = df.columns[0]
        df["差"] = (df[df.columns[1]] - df[base]).round(1)
        print("\n=== 県別再現率（{} 基準との差）ワースト10 ===".format(base))
        print(df.sort_values("差").head(10).to_string())
        print("\n=== 同 ベスト5 ===")
        print(df.sort_values("差").tail(5).to_string())
        out = "docs/sources/検証_公開可能マスター_ATP突合_都道府県別.csv"
        df.to_csv(out, encoding="utf-8")
        print("\n出力: " + out)


if __name__ == "__main__":
    main()
