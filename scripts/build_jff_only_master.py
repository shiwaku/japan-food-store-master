#!/usr/bin/env python3
"""Japan Food Facilities（食品営業許可・届出の統合オープンデータ）**だけ**から
食料品店レイヤを組む。Overture / OSM / ATP を一切使わない。

目的は「このソース単独でマスターの代わりになるか」を検証器で測れる形にすること。
**マスターは書き換えない。** 出力は japan-food-access-analysis の `FOOD_STORES` に渡す。

なぜ業種コードで cat を振らないか
---------------------------------
届出の区分は業態と一対一に対応しない。実測（2026-09-21）:

 - コンビニの多くは店内調理があるため `① 飲食店営業` で届け出ており、
   `⑩ コンビニエンスストア` だけで拾うと大手3社の再現率が 28.5% にしかならない。
   店名でチェーン照合すると 66.7% まで上がる。
 - `⑪ 百貨店、総合スーパー` は受け皿区分で、100m以内の最寄りマスタ店舗の業態は
   supermarket 49.9% / **drugstore 34.1%** / convenience 5.8%。
 - `⑬ その他の食料・飲料販売業` は 8割が飲食店・菓子・雑貨（2026-08-27 に見送り判定）。

→ **店名によるチェーン判定を主、業種を従**にする。判定順は
   ドラッグ → コンビニ → スーパー → 生鮮。先に確定したものを後段で上書きしない
   （ウエルシアが ⑪ で届け出ていても drugstore に落ちる）。

使い方
------
  python scripts/build_jff_only_master.py
  PERMIT_CSV=data/facilities-all.csv MASTER=data/food_store_master_atp_super.parquet \
      OUT_PARQUET=data/food_store_jff_only.parquet python scripts/build_jff_only_master.py
"""
import os
import sys

import duckdb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from food_store_rules import (  # noqa: E402
    dispensing_only_sql, fresh_excluded_sql, match_key_sql, permit_excluded_sql,
    DRUGSTORE_CHAINS, DRUGSTORE_TOKENS, FRESH_TYPE_SQL,
)

PERMIT_CSV = os.environ.get("PERMIT_CSV", "data/facilities-all.csv")
MASTER = os.environ.get("MASTER", "data/food_store_master_atp_super.parquet")
OUT = os.environ.get("OUT_PARQUET", "data/food_store_jff_only.parquet")
MIN_LEVEL = int(os.environ.get("MIN_LEVEL", "8"))
BRAND_MIN = int(os.environ.get("BRAND_MIN", "10"))   # 辞書に採るブランドの最低店舗数
BRAND_MIN_LEN = int(os.environ.get("BRAND_MIN_LEN", "4"))  # 総称への過剰一致を避ける
DEDUP_M = 50.0


def brand_keys(con, cat):
    """マスターの brand 列から、そのカテゴリのチェーン名キーを作る。

    brand は全件には入っていない（supermarket は 42%）。チェーンでない独立店は
    そもそも名前で突合できないので、ここで拾えないのは織り込み済み。
    """
    rows = con.execute("""
      select {k} bkey, count(*) n from master_all
      where cat = ? and brand is not null and trim(brand) <> ''
      group by 1 having count(*) >= ? and length({k}) >= ?
      order by 2 desc""".format(k=match_key_sql("brand")),
      [cat, BRAND_MIN, BRAND_MIN_LEN]).fetchall()
    return [r[0] for r in rows]


def like_any(col, keys):
    if not keys:
        return "false"
    esc = [k.replace("'", "''") for k in keys]
    return "(" + " or ".join(f"{col} like '%{k}%'" for k in esc) + ")"


def main():
    for p in (PERMIT_CSV, MASTER):
        if not os.path.exists(p):
            sys.exit("入力が無い: " + p)
    con = duckdb.connect()
    con.execute(f"create view master_all as select * from '{MASTER}'")

    keys = {c: brand_keys(con, c) for c in
            ("convenience", "supermarket", "drugstore", "fresh_food")}
    for c, v in keys.items():
        print(f"  ブランド辞書 {c}: {len(v)} 件  例 {', '.join(v[:6])}")

    nn = match_key_sql("name")
    # 座標があり、町丁目代表点（level 3）より粗いものは落とす。
    con.execute("""create table raw as
      select prefecture, city, name, address, business_type,
             try_cast(lat as double) lat, try_cast(lng as double) lng,
             try_cast(geocoding_level as int) glv, {nn} nname
      from read_csv('{csv}', header=true, all_varchar=true)
      where lat is not null and name is not null and trim(name) <> ''
        and (geocoding_level is null or trim(geocoding_level) = ''
             or try_cast(geocoding_level as int) >= {lv})""".format(
        nn=nn, csv=PERMIT_CSV, lv=MIN_LEVEL))
    print("生行数 {:,}".format(con.execute("select count(*) from raw").fetchone()[0]))

    # 施設単位に畳む。**業種は全部残す**（1施設が複数業種で複数行あるため、
    # 業種を先に絞ると「コンビニだが飲食店営業でしか届け出ていない店」を落とす）。
    con.execute("""create table fac as
      select prefecture, city, nname, address,
             min(name) as "name", min(lat) lat, min(lng) lng, min(glv) glv,
             string_agg(distinct business_type, '|') bts,
             prefecture || '|' || city || '|' || nname || '|' || address fkey
      from raw group by 1,2,3,4""")
    # 同名が 50m 以内にある行（住所表記だけ違う同一施設）を畳む。permit_gapfill と同じ規則。
    con.execute("""create table fac2 as
      with pairs as (
        select a.fkey ra, min(b.fkey) keep
        from fac a join fac b
          on a.nname = b.nname and a.prefecture = b.prefecture
         and b.lat between a.lat - 0.0005 and a.lat + 0.0005
         and b.lng between a.lng - 0.0007 and a.lng + 0.0007
         and 111320.0 * sqrt(pow(a.lat - b.lat, 2) +
             pow((a.lng - b.lng) * cos(radians(a.lat)), 2)) <= {m}
        group by a.fkey)
      select f.* from fac f join pairs p on f.fkey = p.ra and p.ra = p.keep""".format(
        m=DEDUP_M))
    n_fac = con.execute("select count(*) from fac").fetchone()[0]
    n_fac2 = con.execute("select count(*) from fac2").fetchone()[0]
    print("施設に畳む {:,} → 同名50m を畳む {:,}".format(n_fac, n_fac2))

    drug_words = " or ".join(
        f"name ilike '%{w}%'" for w in DRUGSTORE_CHAINS + DRUGSTORE_TOKENS)
    conv_bt = "bts like '%コンビニエンスストア%'"
    super_bt = "bts like '%百貨店、総合スーパー%'"
    fresh_bt = FRESH_TYPE_SQL.replace("business_type", "bts")

    # 判定順が意味を持つ。先に決まったものを後段は見ない。
    con.execute("""create table cls as
      select *, case
        when ({drug} or {dk}) and not {disp} then 'drugstore'
        when {ck} or {cbt} then 'convenience'
        when {sk} then 'supermarket'
        when {sbt} and not {pex} then 'supermarket'
        when ({fbt}) and not {fex} then 'fresh_food'
        else null end cat
      from fac2""".format(
        drug=drug_words, dk=like_any("nname", keys["drugstore"]),
        disp=dispensing_only_sql("name"),
        ck=like_any("nname", keys["convenience"]), cbt=conv_bt,
        sk=like_any("nname", keys["supermarket"]),
        sbt=super_bt, pex=permit_excluded_sql("name"),
        fbt=fresh_bt, fex=fresh_excluded_sql("name")))

    print()
    print(con.execute("""select coalesce(cat,'（対象外）') cat, count(*) n
      from cls group by 1 order by 2 desc""").df().to_string(index=False))

    con.execute(f"""copy (
      select row_number() over (order by prefecture, city, nname) store_id,
             cat, name, prefecture, city, bts business_type,
             'japan-food-facilities' src, true redistributable, lat, lng
      from cls where cat is not null
    ) to '{OUT}' (format parquet)""")
    n = con.execute(f"select count(*) from '{OUT}'").fetchone()[0]
    print("\n出力: {}（{:,} 店）".format(OUT, n))

    print("\n=== 参考: 現行マスタとの件数比 ===")
    print(con.execute(f"""
      with a as (select cat, count(*) n from '{OUT}' group by 1),
           b as (select cat, count(*) n from master_all group by 1)
      select b.cat, b.n master, coalesce(a.n,0) jff_only,
             round(100.0*coalesce(a.n,0)/b.n,1) pct
      from b left join a on a.cat=b.cat order by b.n desc""").df().to_string(index=False))


if __name__ == "__main__":
    main()
