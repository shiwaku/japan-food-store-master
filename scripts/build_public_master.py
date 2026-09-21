#!/usr/bin/env python3
"""**公開できる**食料品店マスターを Overture Places ＋ OpenStreetMap ＋
食品営業許可オープンデータ の3ソースだけで組む。**ATP は一切使わない。**

なぜ
----
ATP 基準マスター（`food_store_master_atp_super.parquet`・122,249店）は 47県・地方部の実測で
最良だが、**自前クロール38チェーン 47,005店（38%）が再配布不可**
（`docs/sources/調査_自前クロールソースの利用規約と再配布可否.md`。再配布を明示的に許諾する社はゼロ）。
推計に使うだけなら制約は無いが、**地図タイルや診断サービスのような公開物には載せられない**。

そこで再配布できる3ソースだけで組み直す。**実測では ATP 基準とほぼ同等**
（47県・地方部で r 0.244 対 0.2472、圏外率 55.7% 対 56.3%）。
→ `docs/sources/検証_公開可能マスター_Overture_OSM_許可.md`

構成
----
| 層 | ソース | ライセンス | 役割 |
|---|---|---|---|
| 土台 | Phase1 マスター（Overture 主・OSM 補完・102,984店） | CDLA-Permissive-2.0 / **ODbL-1.0** | 位置の主ソース |
| 補完 | 食品営業許可オープンデータ（Japan Food Facilities） | CC BY 系 / 公共データ利用規約 | 土台に無い店を足す |

許可データ側の cat は `build_jff_only_master.py` が**店名のチェーン判定**で振る。
**業種コードで振らないこと**（コンビニは `① 飲食店営業` で届け出るため ⑩ だけだと 28.5%）。

突合は「同カテゴリが 100m 以内」＋「同ブランドが 500m 以内」。後者は座標ズレ対策
（permit_gapfill.py と同じ考え方）。距離は等距円筒近似（この環境の DuckDB は spheroid が -nan）。

**店舗ごとに出所が追える**ように次の列を持たせる。公開時の出典表示に必要。

| 列 | 中身 |
|---|---|
| `src` | `overture` / `osm` / `permit` |
| `src_cat` | Overture の category / OSM の shop タグ（土台のみ） |
| `business_type` | 届出・許可の業種（許可のみ。複数を `|` 連結） |
| `sources` | 元データの公開元（許可のみ。例「大阪市食品営業許可施設一覧」） |
| `licenses` | 元データのライセンス（許可のみ。例「CC BY 4.0」） |
| `license` | 行単位のライセンス（土台は CDLA-Permissive-2.0 / ODbL-1.0） |
| `attribution` | 出典表示の文字列 |
| `redistributable` | 全行 true（このマスターの存在意義） |

⚠ **OSM 由来行が入るので派生物には ODbL の継承が掛かる**。
`license` 列で行を落とせるようにしてあるので、継承を避けたいときは
`OSM=0` で OSM を外して組む（fresh_food が 10,070 → 4,686 に減る）。

使い方
------
  python scripts/build_jff_only_master.py       # 先にこれ（許可データ側の cat 付け）
  python scripts/build_public_master.py
  OSM=0 python scripts/build_public_master.py   # ODbL を避ける版
  INCLUDE_FRESH=1 python scripts/build_public_master.py   # 許可の生鮮も入れる（⚠ 悪化する）
"""
import os
import sys

import duckdb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from food_store_rules import match_key_sql  # noqa: E402

BASE = os.environ.get("BASE_MASTER", "data/food_store_master.parquet")
PERMIT = os.environ.get("PERMIT_LAYER", "data/food_store_jff_only.parquet")
OUT = os.environ.get("OUT_PARQUET", "data/food_store_master_public.parquet")
USE_OSM = os.environ.get("OSM", "1") != "0"
# 許可データの生鮮3業種はセンサスの2倍あり、47県・地方部で指標が悪化する（issue #46）。
# 既定では入れない。
INCLUDE_FRESH = os.environ.get("INCLUDE_FRESH", "0") == "1"
NEAR_M = float(os.environ.get("NEAR_M", "100"))
BRAND_M = float(os.environ.get("BRAND_M", "500"))

DIST = ("111320.0 * sqrt(pow(a.lat - b.lat, 2) + "
        "pow((a.lng - b.lng) * cos(radians(a.lat)), 2))")

ATTR = {
    "overture": "© Overture Maps Foundation",
    "osm": "© OpenStreetMap contributors",
}
LIC = {
    "overture": "CDLA-Permissive-2.0",
    "osm": "ODbL-1.0",
}


def main():
    for p in (BASE, PERMIT):
        if not os.path.exists(p):
            sys.exit("入力が無い: " + p)
    con = duckdb.connect()
    nn = match_key_sql("name")

    osm_cond = "" if USE_OSM else " where src <> 'osm'"
    con.execute(f"""create table base as
      select cat, name, brand, prefecture, src, src_cat, lat, lng,
             {nn} nname, substr({nn}, 1, 5) bkey
      from '{BASE}'{osm_cond}""")
    con.execute(f"""create table cand as
      select cat, name, prefecture, business_type, sources, licenses,
             lat, lng, {nn} nname, substr({nn}, 1, 5) bkey
      from '{PERMIT}'{'' if INCLUDE_FRESH else " where cat <> 'fresh_food'"}""")

    n_base = con.execute("select count(*) from base").fetchone()[0]
    print("土台 {:,} 店（OSM {}）".format(n_base, "込み" if USE_OSM else "抜き"))

    dn = NEAR_M / 111320.0
    db = BRAND_M / 111320.0
    con.execute("""create table add_all as
      select a.* from cand a
      where not exists (
        select 1 from base b
        where b.cat = a.cat
          and b.lat between a.lat - {dn}*1.1 and a.lat + {dn}*1.1
          and b.lng between a.lng - {dn}*1.6 and a.lng + {dn}*1.6
          and {dist} <= {near})
        and not exists (
        select 1 from base b
        where b.lat between a.lat - {db}*1.1 and a.lat + {db}*1.1
          and b.lng between a.lng - {db}*1.6 and a.lng + {db}*1.6
          and {dist} <= {brand}
          and ((length(a.bkey) >= 5 and b.nname like '%' || a.bkey || '%')
            or (length(b.bkey) >= 5 and a.nname like '%' || b.bkey || '%')))
    """.format(dn=dn, db=db, dist=DIST, near=NEAR_M, brand=BRAND_M))
    print("許可データからの純増 {:,} 店".format(
        con.execute("select count(*) from add_all").fetchone()[0]))
    print(con.execute("""select cat, count(*) n from add_all
      group by 1 order by 2 desc""").df().to_string(index=False))

    ocase = " ".join(f"when src = '{k}' then '{v}'" for k, v in LIC.items())
    acase = " ".join(f"when src = '{k}' then '{v}'" for k, v in ATTR.items())
    con.execute(f"""copy (
      select row_number() over (order by prefecture, cat, name) store_id,
             cat, name, brand, prefecture, src,
             src_cat, null::varchar business_type, null::varchar sources,
             null::varchar licenses,
             case {ocase} end license,
             case {acase} end attribution,
             true redistributable, lat, lng
        from base
      union all
      select 900000000 + row_number() over (order by prefecture, cat, name) store_id,
             cat, name, null brand, prefecture, 'permit' src,
             null src_cat, business_type, sources, licenses,
             licenses license,
             '出典：Japan Food Facilities（' || coalesce(sources, '出典不明') || '）' attribution,
             true redistributable, lat, lng
        from add_all
    ) to '{OUT}' (format parquet)""")

    print("\n出力: {}".format(OUT))
    print(con.execute(f"""select src, count(*) n from '{OUT}'
      group by 1 order by 2 desc""").df().to_string(index=False))
    print()
    print(con.execute(f"""select cat, count(*) n,
        count(*) filter (where src='overture') overture,
        count(*) filter (where src='osm') osm,
        count(*) filter (where src='permit') permit
      from '{OUT}' group by 1 order by 2 desc""").df().to_string(index=False))
    print("\n=== ライセンス別（公開時の出典表示に使う）===")
    print(con.execute(f"""select license, count(*) n from '{OUT}'
      group by 1 order by 2 desc limit 15""").df().to_string(index=False))
    print("\n合計 {:,} 店".format(
        con.execute(f"select count(*) from '{OUT}'").fetchone()[0]))


if __name__ == "__main__":
    main()
