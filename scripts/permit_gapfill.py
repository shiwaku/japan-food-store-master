#!/usr/bin/env python3
"""食品営業許可・届出データからマスターの穴を埋める候補を出す共通処理。

`extract_permit_supermarkets.py`（届出⑪ 総合スーパー）と
`extract_permit_fresh_food.py`（生鮮3業種）が共有する。**マスターは書き換えない**。

やること:
 1. `business_type` で対象業種を抽出し、施設単位（県・市・正規化名・住所）に畳む
 2. 同名が近距離に複数ある行（住所表記だけ違う同一施設）を畳む
 3. 名称による業態フィルタと座標・精度の足切り
 4. マスターと突合（距離一致＋同ブランド 500m 一致）して純増を出す
 5. 突合半径の感度・座標精度・県別カバー率を表示し、候補 parquet と県別 CSV を書く

落とし穴（CLAUDE.md にも記載）:
 - 区分番号は許可業種と届出業種で衝突する（`⑪ 菓子製造業` と `⑪ 百貨店、総合スーパー`）。
 - 届出行には `license_date` / `expire_date` が無く、**廃業の除外はできない**。
 - `any_value` と `rowid` は実行ごとに結果がぶれるので使わない（決定的にする）。
 - 距離は等距円筒近似（この環境の DuckDB は ST_Distance_Spheroid が -nan）。
"""
import csv
import os
import sys

import duckdb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from food_store_rules import match_key_sql  # noqa: E402

PERMIT_CSV = os.environ.get("PERMIT_CSV", "data/facilities-all.csv")
PREF_STATS_CSV = "docs/master/検証_マスターPhase1_都道府県別.csv"

BRAND_RADIUS_M = 500.0   # 同ブランドがこの距離内にあれば同一店（座標ズレ対策）
DEDUP_M = 50.0           # 同名がこの距離内にある行は同一施設として畳む
BKEY_LEN = 5             # ブランド突合キーの文字数
RADII = [50, 100, 200, 300, 500]

DIST = ("111320.0 * sqrt(pow(a.lat - m.lat, 2) + "
        "pow((a.lng - m.lng) * cos(radians(a.lat)), 2))")
# ブランド突合は**両方向**見る。片方向だけだと「イオンリテール株式会社イオン小松店」の
# 突合キーが「イオンリテル…」始まりになってマスターの「イオン小松店」に当たらない。
# 5文字未満のキーは総称（「スーパー」等）に当たって過剰一致するので使わない。
BRAND_MATCH = ("((length(a.bkey) >= 5 and m.nname like '%' || a.bkey || '%') or "
               "(length(m.bkey) >= 5 and a.nname like '%' || m.bkey || '%'))")


def _near(radius):
    deg = radius / 111320.0
    return """exists (
      select 1 from master m
      where m.lat between a.lat - {d} * 1.1 and a.lat + {d} * 1.1
        and m.lng between a.lng - {d} * 1.6 and a.lng + {d} * 1.6
        and {dist} <= {r})""".format(d=deg, dist=DIST, r=radius)


def run(label, type_sql, exclude_sql, out_parquet, out_csv, master,
        radius_m=100.0, stats_cat=None, level_sql=None, chain_filter=False,
        chain_prefix=3, chain_min=10):
    """候補を抽出してマスターと突合し、結果を表示・出力する。

    label: 表示名 / type_sql: business_type の抽出条件 / exclude_sql: 名称除外の述語
    stats_cat: 県別カバー率の分母に使う cat（None なら分母なしで出す）
    level_sql: geocoding_level の足切り条件（None なら足切りしない）
    chain_filter: True なら「マスターに同じ先頭 chain_prefix 文字の店が全国 chain_min 件以上ある」
      候補を落とす。スーパー／コンビニ／ドラッグの**売場**（鮮魚・精肉コーナーの届出）を、
      チェーン名を列挙し切らずに落とすためのデータ駆動フィルタ。生鮮3業種で必要になる。
    """
    for path in (PERMIT_CSV, master):
        if not os.path.exists(path):
            sys.exit("入力が無い: " + path)

    con = duckdb.connect()
    nn = match_key_sql("name")
    con.execute("""create table raw as
      select prefecture, city, name, address,
             try_cast(lat as double) lat, try_cast(lng as double) lng,
             geocoding_level glv, sources, business_type, {nn} nname
      from read_csv('{csv}', header=true, all_varchar=true)
      where {t}""".format(nn=nn, csv=PERMIT_CSV, t=type_sql))
    n_raw = con.execute("select count(*) from raw").fetchone()[0]

    # any_value は行の選び方が実行ごとに変わり、境界上の店の距離判定がぶれる。min で固定する。
    con.execute("""create table fac as
      select prefecture, city, nname, address,
             min(name) as name, min(lat) lat, min(lng) lng,
             min(glv) glv, min(sources) sources,
             prefecture || '|' || city || '|' || nname || '|' || address as fkey
      from raw group by 1,2,3,4""")
    n_fac = con.execute("select count(*) from fac").fetchone()[0]

    # 代表はキー順で最小の行。**rowid は使わない**（並列実行で順序が変わり再現しない）。
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
      select f.* from fac f join pairs p on f.fkey = p.ra and p.ra = p.keep""".format(m=DEDUP_M))
    n_fac2 = con.execute("select count(*) from fac2").fetchone()[0]

    level_cond = " and (" + level_sql + ")" if level_sql else ""
    con.execute("""create table cand as
      select *, substr(nname, 1, {k}) bkey from fac2
      where not {ex} and name is not null and trim(name) <> ''
        and lat is not null and lng is not null{lv}""".format(
        k=BKEY_LEN, ex=exclude_sql, lv=level_cond))
    n_cand = con.execute("select count(*) from cand").fetchone()[0]
    n_excl = con.execute("select count(*) from fac2 where " + exclude_sql).fetchone()[0]
    n_nocoord = con.execute(
        "select count(*) from fac2 where lat is null or lng is null").fetchone()[0]
    n_lowlv = 0
    if level_sql:
        n_lowlv = con.execute(
            "select count(*) from fac2 where lat is not null and not (" + level_sql + ")"
        ).fetchone()[0]

    print("{l} 生行数 {n:,}".format(l=label, n=n_raw))
    print("  → 施設単位（県・市・正規化名・住所）  {n:,}".format(n=n_fac))
    print("  → 同名 {m:.0f}m 内の重複を畳む      {n:,}".format(m=DEDUP_M, n=n_fac2))
    print("  → 業態フィルタで除外 {a:,} / 座標欠損 {b:,}".format(a=n_excl, b=n_nocoord)
          + ("  / 座標精度で除外 {c:,}".format(c=n_lowlv) if level_sql else ""))
    print("  → 候補                                {n:,}\n".format(n=n_cand))

    con.execute("""create table master as
      select cat, name, brand, prefecture, lat, lng, {nn} nname, substr({nn}, 1, {k}) bkey
      from read_parquet('{p}')""".format(nn=match_key_sql("name"), k=BKEY_LEN, p=master))
    n_ms = con.execute("select count(*) from master").fetchone()[0]
    print("マスター {p}: {n:,} 件 / 突合半径 {r:.0f}m（同ブランドは {b:.0f}m）\n".format(
        p=master, n=n_ms, r=radius_m, b=BRAND_RADIUS_M))

    if chain_filter:
        # マスター側で「同じ先頭 chain_prefix 文字で始まる店が全国に chain_min 件以上」ある
        # 接頭辞をチェーン名とみなし、その名前で出ている届出はチェーン店の売場と判断する。
        #
        # **接頭辞は短くしないと効かない**。ブランドキー（先頭5文字）で突合すると、
        # 「ローソン」は正規化で長音が落ちて3文字（ロソン）になり、キーに店名が食い込んで
        # 店ごとに変わるため一件も当たらない（コンビニの売場が丸ごと漏れる）。
        # 実測（生鮮3業種）: 先頭3文字・10件以上で 4,953件、先頭4文字だと 1,894件しか当たらない。
        con.execute(
            "create table chain_keys as select substr(nname, 1, {k}) as ckey from master "
            "where cat in ('supermarket','convenience','drugstore') and length(nname) >= {k} + 2 "
            "group by 1 having count(*) >= {n}".format(k=chain_prefix, n=chain_min))
        n_before = n_cand
        con.execute("create table cand2 as select * from cand a where not exists ("
                    "select 1 from chain_keys k where a.nname like k.ckey || '%')")
        con.execute("drop table cand")
        con.execute("alter table cand2 rename to cand")
        n_cand = con.execute("select count(*) from cand").fetchone()[0]
        print("チェーン売場フィルタ（先頭{k}文字が一致する店がマスターに全国{n}件以上）: "
              "{a:,} → {b:,}（-{c:,}）\n".format(
                  k=chain_prefix, n=chain_min, a=n_before, b=n_cand, c=n_before - n_cand))

    bdeg = BRAND_RADIUS_M / 111320.0
    brand_expr = """exists (
      select 1 from master m
      where {bm}
        and m.lat between a.lat - {d} * 1.1 and a.lat + {d} * 1.1
        and m.lng between a.lng - {d} * 1.6 and a.lng + {d} * 1.6
        and {dist} <= {r})""".format(bm=BRAND_MATCH, d=bdeg, dist=DIST, r=BRAND_RADIUS_M)
    cols = ",\n    ".join(_near(r) + " near_" + str(r) for r in RADII)
    con.execute("create table matched as select a.*, {c}, {b} brand_hit from cand a".format(
        c=cols, b=brand_expr))

    print("=== ① 突合半径の感度（純増＝マスターに対応が無い候補）===")
    print("{a:>6s} {b:>14s} {c:>16s} {d:>8s} {e:>7s}".format(
        a="半径", b="距離のみで一致", c="同ブランド500mも", d="純増", e="純増率"))
    for r in RADII:
        hit, both, newn = con.execute("""
          select count(*) filter (where near_{r}),
                 count(*) filter (where near_{r} or brand_hit),
                 count(*) filter (where not (near_{r} or brand_hit)) from matched""".format(
            r=r)).fetchone()
        print("{r:5d}m {h:14,} {o:16,} {n:8,} {p:6.1f}%".format(
            r=r, h=hit, o=both, n=newn, p=newn / n_cand * 100))

    print("\n=== ② 許可データの座標精度（同ブランドの既存マスター店舗までの距離）===")
    print("  この分布が 100m を大きく超えるなら、100m 判定の『純増』は座標ズレを拾っている。")
    pairs, med, p75, p90, le50, le100 = con.execute("""
      with nearest as (
        select a.fkey rid,
          min(111320.0 * sqrt(pow(a.lat - m.lat, 2) +
              pow((a.lng - m.lng) * cos(radians(a.lat)), 2))) d
        from cand a join master m
          on {bm}
         and m.lat between a.lat - 0.005 and a.lat + 0.005
         and m.lng between a.lng - 0.007 and a.lng + 0.007
        group by a.fkey)
      select count(*), median(d), quantile_cont(d, 0.75), quantile_cont(d, 0.9),
             count(*) filter (where d <= 50), count(*) filter (where d <= 100)
      from nearest""".format(bm=BRAND_MATCH)).fetchone()
    if pairs:
        print("  対応が取れた候補 {n:,} 件 / 中央値 {m:.0f}m / p75 {a:.0f}m / p90 {b:.0f}m".format(
            n=pairs, m=med, a=p75, b=p90))
        print("  50m以内 {a:,} 件（{ap:.1f}%）/ 100m以内 {b:,} 件（{bp:.1f}%）".format(
            a=le50, ap=le50 / pairs * 100, b=le100, bp=le100 / pairs * 100))
    else:
        print("  同ブランドで対応が取れた候補が無い（個人商店中心の業種では起こりうる）")

    print("\n=== ③ 県別: カバー率が実数統計を超えないか ===")
    stats = {}
    if stats_cat and os.path.exists(PREF_STATS_CSV):
        with open(PREF_STATS_CSV, encoding="utf-8-sig") as fh:
            for r in csv.DictReader(fh):
                if r["cat"] == stats_cat:
                    stats[r["都道府県"]] = (int(r["マスター件数"]), int(r["実数統計"]))
    elif stats_cat:
        print("  （分母 CSV が無い: " + PREF_STATS_CSV + "）")

    rows = con.execute("""
      select prefecture, count(*) cand,
             count(*) filter (where near_{r} or brand_hit) hit,
             count(*) filter (where not (near_{r} or brand_hit)) newn
      from matched group by 1 order by 1""".format(r=int(radius_m))).fetchall()

    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    over = []
    with open(out_csv, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["都道府県", "候補", "既存と一致", "純増", "純増率(%)",
                    "マスター" + (stats_cat or ""), "実数統計", "現状率(%)", "投入後率(%)"])
        for pref, c, h, nn2 in rows:
            ms, real = stats.get(pref, (0, 0))
            cur = ms / real * 100 if real else 0.0
            aft = (ms + nn2) / real * 100 if real else 0.0
            if real and aft > 100:
                over.append((pref, cur, aft))
            w.writerow([pref, c, h, nn2, "{:.1f}".format(nn2 / c * 100), ms, real,
                        "{:.1f}".format(cur), "{:.1f}".format(aft)])
    tot_new = sum(r[3] for r in rows)
    if stats:
        tot_ms = sum(v[0] for v in stats.values())
        tot_real = sum(v[1] for v in stats.values())
        print("  全国: マスター {a:,} / 実数統計 {b:,} = {c:.1f}% → 純増 {d:,} 投入後 {e:.1f}%".format(
            a=tot_ms, b=tot_real, c=tot_ms / tot_real * 100, d=tot_new,
            e=(tot_ms + tot_new) / tot_real * 100))
        print("  投入後に 100% を超える県: {a} / {b}".format(a=len(over), b=len(rows)))
        for pref, cur, aft in sorted(over, key=lambda x: -x[2])[:12]:
            print("    {p:6s} {a:5.1f}% → {b:5.1f}%".format(p=pref, a=cur, b=aft))
    print("\n県別: " + out_csv)

    con.execute("""copy (select prefecture, city, name, nname, address, lat, lng, glv, sources,
        near_{r} as near_hit, brand_hit, not (near_{r} or brand_hit) as net_new
      from matched) to '{o}' (format parquet)""".format(r=int(radius_m), o=out_parquet))
    print("候補（フラグ付き）: " + out_parquet)
