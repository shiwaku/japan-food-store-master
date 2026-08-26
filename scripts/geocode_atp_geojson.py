#!/usr/bin/env python3
"""data/atp/*.geojson の geometry 欠損を国土地理院ジオコーダで埋める。

自前クロールのうちサイトに座標が無いチェーン(ヤオコー・ダイレックス・ロピア等)と、
座標抽出に失敗した少数の店舗が対象。GSI AddressSearch は番地〜大字レベルの精度で、
500mメッシュ用途には足りる。埋めた feature には "geocode_source": "gsi" を付けて
元データの座標と区別できるようにする。

使い方:
    python3 scripts/geocode_atp_geojson.py data/atp/yaoko_jp.geojson [...]
    python3 scripts/geocode_atp_geojson.py --replace data/atp/mandai_jp.geojson [...]

--replace は**既に座標がある地物も住所から取り直す**。クロール由来の座標が系統的にずれている
チェーン向け（万代・ヨークベニマル・原信ナルス・イズミ・ベルク・オーケーの6本は経度が一定量
（約 -0.00215度 = 約200m 西）ずれていた。緯度は合っており、地図の中心座標をピン位置として
拾った類の不具合。issue #28）。取り直しに失敗した地物は元の座標を残す。

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
        state, city, street = (props.get("addr:state"), props.get("addr:city"),
                               props.get("addr:street_address"))
        if not all((state, city, street)):
            return None
        # 市区町村名が street_address 側にも入っていることがある
        # （ヤオコー: addr:city「ふじみ野市」/ street「ふじみ野市駒林元町二丁目1番20号」）。
        # そのまま連結すると「埼玉県ふじみ野市ふじみ野市駒林元町…」となり、ジオコーダが
        # 番地まで解決できず市の代表点に落ちる（204件中146件が同一座標に潰れていた）。
        if street.startswith(city):
            street = street[len(city):]
        addr = "".join((state, city, street))
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


def main(argv: list[str]) -> None:
    replace = "--replace" in argv
    paths = [a for a in argv if not a.startswith("--")]
    cache = json.loads(CACHE_PATH.read_text(encoding="utf-8")) if CACHE_PATH.exists() else {}
    for path in map(Path, paths):
        data = json.loads(path.read_text(encoding="utf-8"))
        todo = data["features"] if replace else [f for f in data["features"] if not f.get("geometry")]
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
                skipped += 1  # --replace のときは元の座標をそのまま残す
        path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        verb = "replaced" if replace else "filled"
        print(f"{path.name}: {len(todo)} 対象 -> {filled} {verb}, {skipped} left")
        CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1:])
