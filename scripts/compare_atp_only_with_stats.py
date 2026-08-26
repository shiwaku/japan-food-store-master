#!/usr/bin/env python3
"""ATP **単独**（マスターと足さない）で実数統計をどれだけ埋められるかを都道府県別に出す。

`compare_atp_with_master.py` が「マスターに投入したらどうなるか」を見るのに対し、
こちらは **ATP がそのカテゴリを素でどれだけ持っているか**だけを見る。新しい spider を
1本書くたびに走らせて、伸びた分と伸びなかった県を確認するのが用途。

入力: data/atp/*.geojson        自前で回した spider の出力（1チェーン1ファイル）
      data/atp_food_stores_japan.parquet   週次ランの抽出（上の geojson に無い spider の補完）
      data/japan_pref.geojson              都道府県ポリゴン
      docs/master/検証_マスターPhase1_都道府県別.csv   分母（実数統計）とマスター件数
出力: docs/sources/検証_ATP単独_実数統計突合_都道府県別.csv

同じ spider が geojson と週次 parquet の両方にあるときは **geojson を採る**。
自前クロールのほうが新しく、grid を詰め直した修正が入っているため。

カテゴリ判定と調剤専業の除外は `fetch_alltheplaces_jp.py` から import する。
ここで書き直すと、週次ラン側と判定がずれて件数が比較できなくなる。
"""
import csv
import glob
import json
import os
import sys

import duckdb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_alltheplaces_jp import (  # noqa: E402
    classify, is_dispensing_only, is_japan, store_name,
)

LOCAL_DIR = "data/atp"
WEEKLY = "data/atp_food_stores_japan.parquet"
PREF_GEOJSON = "data/japan_pref.geojson"
PREF_CSV = "docs/master/検証_マスターPhase1_都道府県別.csv"
OUT_CSV = "docs/sources/検証_ATP単独_実数統計突合_都道府県別.csv"

CATS = ["convenience", "supermarket", "drugstore", "fresh_food"]


def read_local() -> tuple[list[dict], set[str]]:
    """data/atp/*.geojson を読み、採用した spider 名の集合とともに返す。"""
    rows, spiders = [], set()
    for path in sorted(glob.glob(os.path.join(LOCAL_DIR, "*.geojson"))):
        spider = os.path.basename(path)[: -len(".geojson")]
        with open(path, encoding="utf-8") as fh:
            fc = json.load(fh)
        kept = 0
        for feat in fc.get("features", []):
            geom = feat.get("geometry") or {}
            if geom.get("type") != "Point":
                continue
            props = feat.get("properties", {})
            cat = classify(props)
            if cat is None:
                continue
            lon, lat = geom["coordinates"][0], geom["coordinates"][1]
            if lon is None or lat is None or not is_japan(props, lon, lat):
                continue
            name = store_name(props)
            if cat == "drugstore" and is_dispensing_only(name):
                continue
            rows.append({"cat": cat, "lat": lat, "lng": lon,
                         "spider": props.get("@spider") or spider})
            kept += 1
        spiders.add(spider)
        print(f"  {spider:24s} {len(fc.get('features', [])):>6,} 件中 {kept:>6,} 件を採用")
    return rows, spiders


def main() -> None:
    for path in (PREF_GEOJSON, PREF_CSV):
        if not os.path.exists(path):
            sys.exit(f"入力が無い: {path}")

    print(f"=== ローカルクロール（{LOCAL_DIR}）===")
    local_rows, local_spiders = read_local()
    if not local_rows:
        sys.exit(f"{LOCAL_DIR} から 0 件。geojson の中身を疑うこと。")

    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    con.execute("create table atp_raw as select * from (select unnest($rows, recursive := true))",
                {"rows": local_rows})

    # 週次ランのうち、ローカルに geojson が無い spider だけ足す。
    if os.path.exists(WEEKLY):
        placeholders = ", ".join(f"'{s}'" for s in sorted(local_spiders))
        n_before = con.execute("select count(*) from atp_raw").fetchone()[0]
        con.execute(f"""insert into atp_raw
            select cat, lat, lng, spider from read_parquet('{WEEKLY}')
            where spider not in ({placeholders})""")
        n_add = con.execute("select count(*) from atp_raw").fetchone()[0] - n_before
        skipped = con.execute(f"""select distinct spider from read_parquet('{WEEKLY}')
            where spider in ({placeholders}) order by 1""").fetchall()
        print(f"\n週次ラン: ローカルに無い spider から {n_add:,} 件を追加"
              f"（ローカル優先で除外した spider {len(skipped)} 本）")
    else:
        print(f"\n週次ラン {WEEKLY} が無いので、ローカルクロールのみで集計する")

    con.execute(f"create table pref as select nam_ja as pref, geom from ST_Read('{PREF_GEOJSON}')")
    con.execute("""create table atp as
        select a.*, p.pref from atp_raw a
        join pref p on ST_Contains(p.geom, ST_Point(a.lng, a.lat))""")
    n_all = con.execute("select count(*) from atp_raw").fetchone()[0]
    n_in = con.execute("select count(*) from atp").fetchone()[0]
    print(f"計 {n_all:,} 件（都道府県ポリゴン外 {n_all - n_in:,} 件は除外）")

    counts = {(c, p): n for c, p, n in con.execute(
        "select cat, pref, count(*) from atp group by 1, 2").fetchall()}

    # 分母（実数統計）とマスター件数は Phase1 検証の県別表から引く。
    with open(PREF_CSV, encoding="utf-8-sig") as fh:
        base = list(csv.DictReader(fh))

    out, totals = [], {c: [0, 0, 0] for c in CATS}
    for row in base:
        cat, pref = row["cat"], row["都道府県"]
        atp = counts.get((cat, pref), 0)
        real = int(row["実数統計"])
        master = int(row["マスター件数"])
        out.append({
            "cat": cat, "都道府県": pref, "ATP件数": atp, "実数統計": real,
            "ATP率": round(100.0 * atp / real, 3) if real else "",
            "マスター件数": master,
            "マスター率": round(100.0 * master / real, 3) if real else "",
        })
        t = totals.setdefault(cat, [0, 0, 0])
        t[0] += atp
        t[1] += real
        t[2] += master

    out.sort(key=lambda r: (r["cat"], r["都道府県"]))
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    with open(OUT_CSV, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    print(f"\n出力: {OUT_CSV}  {len(out)} 行")

    print("\n=== 全国計（ATP 単独 / 分母は実数統計）===")
    print(f"{'cat':13s}{'ATP':>9s}{'実数統計':>11s}{'ATP率':>9s}{'マスター':>10s}{'マスター率':>11s}")
    for cat in CATS:
        atp, real, master = totals[cat]
        if not real:
            continue
        print(f"{cat:13s}{atp:>9,}{real:>11,}{100.0 * atp / real:>8.1f}%"
              f"{master:>10,}{100.0 * master / real:>10.1f}%")

    # 県別の穴。spider を足しても埋まらない県はここに残り続ける。
    print("\n=== ATP 率が低い県 上位10（cat 別）===")
    for cat in CATS:
        rows = sorted((r for r in out if r["cat"] == cat and r["実数統計"]),
                      key=lambda r: r["ATP率"])[:10]
        if not rows or all(r["ATP率"] == 0 for r in rows) and totals[cat][0] == 0:
            continue
        joined = "  ".join(f"{r['都道府県']} {r['ATP率']:.0f}%" for r in rows)
        print(f"  {cat:12s} {joined}")


if __name__ == "__main__":
    main()
