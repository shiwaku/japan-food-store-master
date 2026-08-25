#!/usr/bin/env python3
"""data/atp/*.geojson の geometry 欠損を国土地理院ジオコーダで埋める。

自前クロールのうちサイトに座標が無いチェーン(ヤオコー・ダイレックス・ロピア等)と、
座標抽出に失敗した少数の店舗が対象。GSI AddressSearch は番地〜大字レベルの精度で、
500mメッシュ用途には足りる。埋めた feature には "geocode_source": "gsi" を付けて
元データの座標と区別できるようにする。

使い方:
    python3 scripts/geocode_atp_geojson.py data/atp/yaoko_jp.geojson [...]

- 結果は in-place 上書き(元座標がある feature には触らない)
- クエリ結果は data/atp/_geocode_cache.json にキャッシュ(再実行安全)
- 日本国外(addr:country が JP 以外)はスキップ
"""

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://msearch.gsi.go.jp/address-search/AddressSearch?q={}"
CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "atp" / "_geocode_cache.json"
DELAY_S = 0.2

# 全角英数・記号を半角へ、番地表記のゆらぎを軽く正規化
Z2H = str.maketrans("０１２３４５６７８９－−―‐", "0123456789----")


def build_address(props: dict) -> str | None:
    if full := props.get("addr:full"):
        addr = full
    else:
        parts = [props.get("addr:state"), props.get("addr:city"), props.get("addr:street_address")]
        if not all(parts):
            return None
        addr = "".join(parts)
    addr = addr.translate(Z2H)
    # ビル名・階数・括弧書きはヒット率を下げるだけなので落とす
    addr = re.sub(r"[（(].*?[)）]", "", addr)
    addr = re.sub(r"\s+", "", addr)
    return addr or None


def geocode(addr: str, cache: dict) -> list | None:
    if addr in cache:
        return cache[addr]
    url = API.format(urllib.parse.quote(addr))
    req = urllib.request.Request(url, headers={"User-Agent": "japan-food-store-master/geocode (personal research)"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            results = json.load(resp)
    except Exception as exc:  # noqa: BLE001 - ネットワーク断はまとめて欠損扱い
        print(f"  ! {addr}: {exc}", file=sys.stderr)
        return None
    coords = results[0]["geometry"]["coordinates"] if results else None
    cache[addr] = coords
    time.sleep(DELAY_S)
    return coords


def main(paths: list[str]) -> None:
    cache = json.loads(CACHE_PATH.read_text(encoding="utf-8")) if CACHE_PATH.exists() else {}
    for path in map(Path, paths):
        data = json.loads(path.read_text(encoding="utf-8"))
        todo = [f for f in data["features"] if not f.get("geometry")]
        filled = skipped = 0
        for feat in todo:
            props = feat["properties"]
            if props.get("addr:country", "JP") != "JP":
                skipped += 1
                continue
            addr = build_address(props)
            if not addr:
                skipped += 1
                continue
            coords = geocode(addr, cache)
            if coords:
                feat["geometry"] = {"type": "Point", "coordinates": coords}
                props["geocode_source"] = "gsi"
                filled += 1
            else:
                skipped += 1
        path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"{path.name}: {len(todo)} missing -> {filled} filled, {skipped} left")
        CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1:])
