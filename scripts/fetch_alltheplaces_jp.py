#!/usr/bin/env python3
"""All The Places（ATP）の週次ランから日本の食料品店を抽出する。

ATP はチェーン公式サイトのスクレイパー集で、出力は **CC-0**（コード側は MIT）。
OSM の ODbL 継承を持ち込まないので、公開物のライセンス律速に効く第3ソース候補。

入力: ATP の run 出力 zip（既定は data/atp/output.zip。無ければ RUN から取得）
出力: data/atp_food_stores_japan.parquet（列 cat, name, brand, src, lat, lng, spider, ref）

注意:
- **チェーン店しか載らない**。個人経営の青果・鮮魚・精肉店は原理的に入らないので、
  fresh_food の穴（センサス比 不足 23,890 店）はこのソースでは埋まらない。
- スパイダーは壊れることがある（2026-08-01 ラン時点で ministop_jp は 0 件）。
  件数が前回ランと大きく違うときは ATP 側の失敗を疑う。
"""
import io
import json
import os
import sys
import urllib.request
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from food_store_rules import DRUGSTORE_CHAINS, DRUGSTORE_TOKENS  # noqa: E402

RUN = "2026-08-01-13-32-15"
ZIP_URL = f"https://alltheplaces-data.openaddresses.io/runs/{RUN}/output.zip"
ZIP_PATH = "data/atp/output.zip"
OUT = "data/atp_food_stores_japan.parquet"

# 日本の bbox（addr:country が欠けている地物のフォールバック）。
# Overture と同じく国外を含みうるので、マスター投入時は都道府県ポリゴンで再度絞る。
JP_BBOX = (122.0, 20.0, 154.0, 46.0)

# ATP は OSM 互換タグ（shop=…）を持つ。マスターの4カテゴリへ写す。
# wholesale は日本では全件コストコ（37件）。マスターは既に Overture 由来のコストコを
# supermarket として 10 件持っているので、同じ扱いに揃える。
SHOP_TO_CAT = {
    "supermarket": "supermarket",
    "convenience": "convenience",
    "wholesale": "supermarket",
    "chemist": "drugstore",
    "greengrocer": "fresh_food",
    "butcher": "fresh_food",
    "seafood": "fresh_food",
    "fishmonger": "fresh_food",
}

# ---- amenity=pharmacy の扱い（取りこぼしと汚染の両方があるので要注意）----
#
# ドラッグストア系スパイダーは**調剤併設の自社店舗を amenity=pharmacy で出す**。
# これを落とすと matsukiyo_jp の ココカラファイン 489・マツモトキヨシ 393 等、
# 約 1,290 件のドラッグストアを取りこぼす。
#
# 一方 amenity=pharmacy を素通しすると otsuka_jp（大塚製薬の薬局・医療機関検索、
# 24,906 件）が丸ごと入る。中身は「くどう薬局」等の調剤専業と、
# 「調剤薬局ツルハドラッグ赤平店（保険調剤窓口）」のような**調剤窓口**で、
# いずれも食料品店ではない。
#
# 両者を分けるのは **brand の有無**。チェーン自社店舗には brand が入り、
# otsuka_jp は 20,764 件すべて brand が空、tomods_jp / seims_jp の提携調剤薬局
# （「あいあい薬局」等）も brand が空。よって brand 付きのみ drugstore として採る。
PHARMACY_NEEDS_BRAND = True


def download_zip() -> str:
    if not os.path.exists(ZIP_PATH):
        os.makedirs(os.path.dirname(ZIP_PATH), exist_ok=True)
        print(f"取得: {ZIP_URL} -> {ZIP_PATH}（約 2.75GB）")
        urllib.request.urlretrieve(ZIP_URL, ZIP_PATH)
    return ZIP_PATH


def is_japan(props: dict, lon: float, lat: float) -> bool:
    country = props.get("addr:country")
    if country:
        return country.upper() == "JP"
    x0, y0, x1, y1 = JP_BBOX
    return x0 <= lon <= x1 and y0 <= lat <= y1


def store_name(props: dict) -> str | None:
    """ATP は name を持たないことが多く、brand + branch で店舗名を組む。"""
    if props.get("name"):
        return props["name"]
    brand, branch = props.get("brand"), props.get("branch")
    if brand and branch:
        return f"{brand} {branch}"
    return brand or branch


def is_dispensing_only(name: str | None) -> bool:
    """調剤専業の疑い。food_store_rules.py の SQL 版と同じ判定を Python で行う。"""
    if not name:
        return False
    low = name.lower()
    if not ("薬局" in name or "調剤" in name):
        return False
    return not any(w.lower() in low for w in DRUGSTORE_CHAINS + DRUGSTORE_TOKENS)


def classify(props: dict) -> str | None:
    """ATP のタグをマスターの4カテゴリへ写す。対象外なら None。"""
    shop = props.get("shop")
    if shop:
        return SHOP_TO_CAT.get(shop)
    if props.get("amenity") == "pharmacy":
        # brand 付き＝チェーンの自社店舗（調剤併設ドラッグストア）だけを採る。
        return "drugstore" if props.get("brand") else None
    return None


def extract(zip_path: str) -> list[dict]:
    rows, spiders_seen, skipped_pharmacy = [], 0, 0
    with zipfile.ZipFile(zip_path) as zf:
        names = [n for n in zf.namelist() if n.endswith(".geojson")]
        print(f"spider 出力: {len(names):,} ファイル")
        for i, member in enumerate(names, 1):
            if i % 500 == 0:
                print(f"  {i:,}/{len(names):,} 走査済み  抽出 {len(rows):,} 件")
            with zf.open(member) as fh:
                raw = fh.read()
            if not raw.strip():
                continue  # 失敗したスパイダー（空ファイル）
            try:
                fc = json.loads(raw)
            except json.JSONDecodeError:
                print(f"  ! JSON 解析失敗: {member}")
                continue
            hit = False
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
                    skipped_pharmacy += 1
                    continue
                rows.append({
                    "cat": cat,
                    "name": name,
                    "brand": props.get("brand"),
                    "src": "atp",
                    "lat": lat,
                    "lng": lon,
                    "spider": props.get("@spider") or os.path.basename(member)[:-8],
                    "ref": props.get("ref"),
                })
                hit = True
            spiders_seen += 1 if hit else 0
    print(f"日本の食料品店を含む spider: {spiders_seen} / 走査 {len(names):,}")
    print(f"調剤専業として除外: {skipped_pharmacy:,} 件")
    return rows


def main() -> None:
    zip_path = sys.argv[1] if len(sys.argv) > 1 else download_zip()
    rows = extract(zip_path)
    if not rows:
        sys.exit("抽出 0 件。zip の中身か shop タグの対応表を疑うこと。")

    import duckdb
    con = duckdb.connect()
    con.execute("create table atp as select * from (select unnest($rows, recursive := true))",
                {"rows": rows})
    os.makedirs("data", exist_ok=True)
    con.execute(f"copy atp to '{OUT}' (FORMAT parquet)")

    print(f"\n出力: {OUT}  計 {len(rows):,} 件")
    print("=== カテゴリ別 ===")
    for cat, cnt in con.execute(
            "select cat, count(*) from atp group by 1 order by 2 desc").fetchall():
        print(f"  {cat:12s} {cnt:,}")
    print("=== spider 別 上位20 ===")
    for sp, cat, cnt in con.execute(
            "select spider, any_value(cat), count(*) from atp group by 1 order by 3 desc limit 20").fetchall():
        print(f"  {sp:28s} {cat:12s} {cnt:,}")


if __name__ == "__main__":
    main()
