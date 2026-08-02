#!/usr/bin/env bash
# 比較ビューワー用 PMTiles を再生成する（出力は viewer/public/）。
#
#   overture_food.pmtiles  レイヤ名=overture / name, addr, cat(バケット), cat_raw(元カテゴリ), confidence
#   osm_food.pmtiles       レイヤ名=osm      / name, cat(バケット), cat_raw(元タグ)
#          ※ OSM 側は元TSV(data/osm_food_stores_japan.tsv)が @id/@lat/@lon/shop/amenity/name しか
#            持たないため住所を出せない。出したければ addr:* タグを含めて Overpass から取り直すこと。
#
# cat のバケット定義は scripts/compare_sources_by_category.sql と同一。
# ここを変えたら向こうも変えること（viewer の COUNTS はあの SQL の出力をハードコードして
# いるので、定義がズレると「表示件数」と「タイルの中身」が食い違う）。
#
# タイル設定は両ソース共通:
#   -z12   maxzoom 12（z13 以上は z12 タイルをオーバーズームする）
#   -r1    droprate 1 ＝ レートによる間引きを無効化
#   --drop-densest-as-needed  タイルがサイズ上限を超えたときだけ密な点を落とす
#          （実績: Overture は z8 以下でのみ発動、OSM は全ズームで未発動＝z9 以上は全点保持）
#
# 使い方: bash scripts/build_pmtiles.sh [overture|osm|all]   （既定 all）
set -euo pipefail
cd "$(dirname "$0")/.."

TARGET="${1:-all}"
OUT_DIR="viewer/public"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

TIPPECANOE_OPTS=(-z12 -B6 -r1 --drop-densest-as-needed --extend-zooms-if-still-dropping --force)

build_overture() {
  local geojsonl="$TMP/ovt_dedup.geojsonl"
  echo "[Overture 1/2] GeoJSONL生成 (DuckDB)…"
  duckdb -c "
COPY (
  SELECT to_json({
    'type':'Feature',
    'geometry':{'type':'Point','coordinates':[lon,lat]},
    'properties':{
      'name': name,
      'cat': CASE category
               WHEN 'supermarket' THEN 'super'
               WHEN 'convenience_store' THEN 'conv'
               WHEN 'drugstore' THEN 'drug'
               WHEN 'grocery_store' THEN 'grocery'
               ELSE 'fresh' END,        -- butcher_shop / farmers_market / seafood_market
      'cat_raw': category,
      'confidence': confidence,
      -- 住所は表記が2系統ある。都道府県込みの完全住所（'沖縄県石垣市字新川2363-2'）と、
      -- 市区町村以下だけで region/locality が別列のもの（'金城5-2-6' + 那覇市 + 沖縄県）。
      -- 既に含まれている要素は足さずに連結する（合成後 109,575/109,602 件＝100%、平均16字）。
      'addr': nullif(concat(
        CASE WHEN region   IS NOT NULL AND NOT coalesce(contains(address, region),   false)
             THEN region   ELSE '' END,
        CASE WHEN locality IS NOT NULL AND NOT coalesce(contains(address, locality), false)
             THEN locality ELSE '' END,
        coalesce(address, '')
      ), '')
    }
  }) AS j
  FROM 'data/overture_food_deduped_jp.parquet'
  WHERE lon IS NOT NULL AND lat IS NOT NULL
) TO '$geojsonl' (FORMAT csv, HEADER false, QUOTE '', DELIMITER E'\t');
"
  echo "  行数: $(wc -l < "$geojsonl")"
  echo "[Overture 2/2] tippecanoe…"
  tippecanoe -o "$OUT_DIR/overture_food.pmtiles" -l overture -n 'Overture food JP (deduped)' \
    "${TIPPECANOE_OPTS[@]}" "$geojsonl"
}

build_osm() {
  local geojsonl="$TMP/osm_food.geojsonl"
  echo "[OSM 1/2] GeoJSONL生成 (DuckDB)…"
  # cat_raw は shop の値。shop で判定できず amenity=marketplace で拾ったものは 'marketplace'。
  duckdb -c "
COPY (
  WITH raw AS (
    SELECT name,
           lower(shop) AS shop, lower(amenity) AS amenity,
           TRY_CAST(\"@lon\" AS DOUBLE) AS lon, TRY_CAST(\"@lat\" AS DOUBLE) AS lat
    FROM read_csv('data/osm_food_stores_japan.tsv', delim='\t', all_varchar=true)
  ),
  tagged AS (
    SELECT *,
      CASE
        WHEN shop='supermarket' THEN 'super'
        WHEN shop='convenience' THEN 'conv'
        WHEN shop IN ('chemist','drugstore','drug store','drugs','dragstore','cosmetics') THEN 'drug'
        WHEN shop IN ('grocery','food','general','deli','confectionery') THEN 'grocery'
        WHEN shop IN ('greengrocer','seafood','butcher','farm') OR amenity='marketplace' THEN 'fresh'
      END AS cat,
      CASE
        WHEN shop IN ('supermarket','convenience',
                      'chemist','drugstore','drug store','drugs','dragstore','cosmetics',
                      'grocery','food','general','deli','confectionery',
                      'greengrocer','seafood','butcher','farm') THEN shop
        ELSE 'marketplace' END AS cat_raw
    FROM raw
  )
  SELECT to_json({
    'type':'Feature',
    'geometry':{'type':'Point','coordinates':[lon,lat]},
    'properties':{'name': name, 'cat': cat, 'cat_raw': cat_raw}
  }) AS j
  FROM tagged
  WHERE cat IS NOT NULL AND lon IS NOT NULL AND lat IS NOT NULL
) TO '$geojsonl' (FORMAT csv, HEADER false, QUOTE '', DELIMITER E'\t');
"
  echo "  行数: $(wc -l < "$geojsonl")"
  echo "[OSM 2/2] tippecanoe…"
  tippecanoe -o "$OUT_DIR/osm_food.pmtiles" -l osm -n 'OSM food JP' \
    "${TIPPECANOE_OPTS[@]}" "$geojsonl"
}

case "$TARGET" in
  overture) build_overture ;;
  osm)      build_osm ;;
  all)      build_overture; build_osm ;;
  *) echo "使い方: bash scripts/build_pmtiles.sh [overture|osm|all]" >&2; exit 1 ;;
esac

echo "完了: $OUT_DIR/"
echo "※ 件数が変わったら scripts/compare_sources_by_category.sql を回して"
echo "  viewer/src/layers.ts の COUNTS を更新すること。"
