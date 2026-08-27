#!/usr/bin/env python3
"""ATP 単独の網羅率を都道府県ポリゴンに載せた GeoParquet を作る（QGIS で図化する用）。

入力: docs/sources/検証_ATP単独_実数統計突合_都道府県別.csv
        `scripts/compare_atp_only_with_stats.py` の出力。ATP件数 / 実数統計 /
        マスター件数を cat × 都道府県の long 形式で持つ。
      data/japan_pref.geojson   都道府県ポリゴン（join キーは nam_ja）

出力: data/atp_coverage_by_pref.parquet   GeoParquet 1.1.0 / EPSG:4326 / 47 features

**wide 形式**にしてある（1県1行・カテゴリは列）。QGIS で1回読めば属性を切り替えるだけで
4カテゴリを塗り分けられるため。long（188行）だと同じポリゴンが4枚重なる。

スタイルは data/atp_coverage_by_pref.qml（supermarket 率の段階区分）。
QGIS はレイヤと同名の .qml を自動で読むので、parquet と同じ場所に置くこと。
"""
import io
import json
import os

import geopandas as gpd
import pandas as pd

CSV = "docs/sources/検証_ATP単独_実数統計突合_都道府県別.csv"
PREF_GEOJSON = "data/japan_pref.geojson"
OUT = "data/atp_coverage_by_pref.parquet"

# 列名は ASCII に寄せる（QGIS の式・ラベルで扱いやすい）。
SHORT = {"convenience": "conv", "supermarket": "super",
         "drugstore": "drug", "fresh_food": "fresh"}


def main() -> None:
    df = pd.read_csv(CSV)
    pref = gpd.read_file(PREF_GEOJSON)[["nam_ja", "nam", "geometry"]]
    pref = pref.rename(columns={"nam_ja": "pref", "nam": "pref_en"})

    missing = set(df["都道府県"]) - set(pref["pref"])
    if missing:
        raise SystemExit(f"ポリゴンに無い県名がある（表記ゆれ）: {sorted(missing)}")

    out = pref.copy()
    for cat, s in SHORT.items():
        sub = df[df["cat"] == cat].set_index("都道府県")
        # reindex で県の順序をポリゴン側に合わせる（CSV は cat ごとに県名ソート）。
        sub = sub.reindex(out["pref"].values)
        out[f"{s}_atp"] = sub["ATP件数"].to_numpy()
        out[f"{s}_real"] = sub["実数統計"].to_numpy()
        out[f"{s}_master"] = sub["マスター件数"].to_numpy()
        # 率は CSV の値を使わず引き直す（丸めの由来を1か所にする）。
        out[f"{s}_rate"] = (100.0 * out[f"{s}_atp"] / out[f"{s}_real"]).round(1)
        out[f"{s}_mrate"] = (100.0 * out[f"{s}_master"] / out[f"{s}_real"]).round(1)
        # 不足数。マイナス＝実数を超えている（超過）。
        out[f"{s}_gap"] = out[f"{s}_atp"] - out[f"{s}_real"]

    cats = list(SHORT.values())
    out["all_atp"] = sum(out[f"{s}_atp"] for s in cats)
    out["all_real"] = sum(out[f"{s}_real"] for s in cats)
    out["all_rate"] = (100.0 * out["all_atp"] / out["all_real"]).round(1)
    out["all_gap"] = out["all_atp"] - out["all_real"]

    cols = ["pref", "pref_en"] + [c for c in out.columns
                                  if c not in ("pref", "pref_en", "geometry")]
    out = out[cols + ["geometry"]].set_crs("EPSG:4326", allow_override=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    out.to_parquet(OUT, index=False, geometry_encoding="WKB",
                   write_covering_bbox=False, schema_version="1.1.0")

    print(f"出力: {OUT}  {len(out)} features / {len(cols)} 属性")
    print("\n=== 全国計（ATP 単独 / 分母は実数統計）===")
    for s, cat in [(v, k) for k, v in SHORT.items()]:
        a, r = int(out[f"{s}_atp"].sum()), int(out[f"{s}_real"].sum())
        print(f"  {cat:12s} {a:>7,} / {r:>7,} = {100.0*a/r:5.1f}%  不足 {a-r:>+8,}")
    a, r = int(out["all_atp"].sum()), int(out["all_real"].sum())
    print(f"  {'計':12s} {a:>7,} / {r:>7,} = {100.0*a/r:5.1f}%  不足 {a-r:>+8,}")

    worst = out.nsmallest(5, "super_rate")[["pref", "super_atp", "super_real", "super_rate"]]
    print("\n=== supermarket 率が低い県 ===")
    for _, row in worst.iterrows():
        print(f"  {row['pref']:6s} {int(row['super_atp']):>5,} / "
              f"{int(row['super_real']):>5,} = {row['super_rate']:5.1f}%")


if __name__ == "__main__":
    main()
