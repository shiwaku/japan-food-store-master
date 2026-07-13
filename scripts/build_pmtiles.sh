#!/usr/bin/env bash
# 名寄せ済み層(data/overture_food_deduped_jp.parquet)から比較ビューワー用PMTilesを再生成する。
# タイル仕様は既存 public/overture_food.pmtiles を踏襲:
#   レイヤ名=overture / フィールド= name, cat(バケット), cat_raw(元カテゴリ), confidence / z0-12
# 使い方: bash scripts/build_pmtiles.sh
set -euo pipefail
cd "$(dirname "$0")/.."

TMP="$(mktemp -d)"
GEOJSONL="$TMP/ovt_dedup.geojsonl"

echo "[1/2] GeoJSONL生成 (DuckDB)…"
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
      'confidence': confidence
    }
  }) AS j
  FROM 'data/overture_food_deduped_jp.parquet'
  WHERE lon IS NOT NULL AND lat IS NOT NULL
) TO '$GEOJSONL' (FORMAT csv, HEADER false, QUOTE '', DELIMITER E'\t');
"
echo "  行数: $(wc -l < "$GEOJSONL")"

echo "[2/2] tippecanoe…"
tippecanoe -o public/overture_food.pmtiles -l overture -n 'Overture food JP (deduped)' \
  -z12 -B6 -r1 --drop-densest-as-needed --extend-zooms-if-still-dropping --force "$GEOJSONL"

rm -rf "$TMP"
echo "完了: public/overture_food.pmtiles"
