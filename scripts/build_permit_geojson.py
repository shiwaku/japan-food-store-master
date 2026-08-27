#!/usr/bin/env python3
"""viewer の確認用レイヤ（許可データの純増）を GeoJSON で書き出す。

viewer の他の2ソース（Overture / OSM）は PMTiles だが、**これは GeoJSON**。
理由: 純増は 20,400点しかなく GeoJSON 1本（約3MB）で足りる。tippecanoe を要求せずに
「投入した点が変な場所に落ちていないか」を目視できるようにするのが目的。
点数が10万件規模になったら `scripts/build_pmtiles.sh` 側に移すこと。

入力: data/permit_fresh_food_candidates_atp.parquet   （生鮮3業種の純増）
      data/permit_supermarket_candidates_atp.parquet  （届出⑪ 総合スーパーの純増）
      ＝ scripts/extract_permit_*.py が出した純増候補。issue #46 の 47県再評価後は
      **⑪ は採用（atp_super に投入済み）／生鮮は保留**なので、両方を1本に入れて
      viewer のカテゴリチップで切り替えて見る（保留分の質を目視するのが主用途）。
出力: viewer/public/permit_gapfill.json

拡張子は **.json**（.geojson だと GitHub Pages が gzip しない content-type で配信され、
数MB がそのまま落ちてくる）。中身は GeoJSON で MapLibre は拡張子を見ない。

`cat` は **viewer のバケットキー**（super / fresh）で入れる。マスターの cat 名
（supermarket / fresh_food）ではないので注意。viewer/src/layers.ts の CATEGORIES と
一致していないと色もピンも絞り込みも効かない。
出力の最後に viewer/src/layers.ts の COUNTS に入れる件数を表示する。
"""
import json
import os
import sys

import duckdb

# 候補ファイル → viewer のカテゴリキー
SRCS = [
    ("data/permit_fresh_food_candidates_atp.parquet", "fresh"),
    ("data/permit_supermarket_candidates_atp.parquet", "super"),
]
OUT = os.environ.get("OUT", "viewer/public/permit_gapfill.json")


def main() -> None:
    con = duckdb.connect()
    feats = []
    counts = {}
    for path, cat in SRCS:
        if not os.path.exists(path):
            sys.exit("候補が無い: " + path + "（extract_permit_*.py を先に回す）")
        rows = con.execute("""
          select name, prefecture, city, address, lat, lng
          from read_parquet('{p}') where net_new
          order by prefecture, city, name""".format(p=path)).fetchall()
        counts[cat] = len(rows)
        for name, pref, city, addr, lat, lng in rows:
            addr = addr or ""
            pref = pref or ""
            city = city or ""
            # 許可データの address は「都道府県＋市区町村込み」「市区町村込み」「町名から」の
            # 3通りが混ざる。素朴に連結すると「三重県亀山市三重県亀山市…」になる。
            if pref and addr.startswith(pref):
                full = addr
            elif city and addr.startswith(city):
                full = pref + addr
            else:
                full = pref + city + addr
            feats.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [round(lng, 6), round(lat, 6)]},
                # cat_raw は入れない（全点で同じ文字列になり 1MB 以上ふくらむ）。
                # 業種はポップアップのソース名とカテゴリで足りる。
                "properties": {"name": name, "addr": full, "cat": cat},
            })

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({"type": "FeatureCollection", "features": feats}, fh,
                  ensure_ascii=False, separators=(",", ":"))

    size = os.path.getsize(OUT) / 1024 / 1024
    print("出力: {o}  {n:,}点  {s:.1f}MB".format(o=OUT, n=len(feats), s=size))
    print("\nviewer/src/layers.ts の COUNTS に入れる値:")
    print("  all:     {n:,}".format(n=len(feats)))
    for cat, n in counts.items():
        print("  {c:8s} {n:,}".format(c=cat + ":", n=n))
    print("  conv / drug / grocery: 0（許可データからは入れていない）")


if __name__ == "__main__":
    main()
