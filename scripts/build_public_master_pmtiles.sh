#!/usr/bin/env bash
# 公開できる店舗マスター（Overture＋食品営業許可）を PMTiles にする。
#
#   出力: data/food_store_master_public_v1.pmtiles   レイヤ名 = stores
#   属性: cat（supermarket / convenience / drugstore / fresh_food）
#         name / src（overture | permit）/ sources（許可データの公開元）/ license
#
# **出典表示に使うので sources と license は落とさないこと。** 許可データは公開元が
# 自治体ごとに違い、CC BY 系は帰属表示が条件。
#
# タイル設定は scripts/build_pmtiles.sh（比較ビューワ用）と同じ:
#   -z12   maxzoom 12（z13 以上はオーバーズーム）
#   -r1    droprate 1 ＝ レートによる間引きを無効化
#   --drop-densest-as-needed  タイルがサイズ上限を超えたときだけ密な点を落とす
#
# R2 へは版を上げて置く（同じキーに上書きしない。Range の新旧断片が混ざるため）:
#   aws s3 cp data/food_store_master_public_v1.pmtiles \
#     s3://shi-works/pmtiles/japan-food-store-master/food_store_master_public_v1.pmtiles \
#     --profile r2-shiworks
#
# 使い方: bash scripts/build_public_master_pmtiles.sh [入力parquet] [出力pmtiles]
set -euo pipefail
cd "$(dirname "$0")/.."

SRC="${1:-data/food_store_master_public_noosm.parquet}"
OUT="${2:-data/food_store_master_public_v1.pmtiles}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
GEOJSONL="$TMP/stores.geojsonl"
# DuckDB CLI は PATH に無いことがある（WSL 側の既定パスは CLAUDE.md 参照）。
DUCKDB="${DUCKDB:-$(command -v duckdb || echo /home/shi-works/.duckdb/cli/latest/duckdb)}"
[ -x "$DUCKDB" ] || { echo "duckdb が無い: $DUCKDB（DUCKDB= で指定する）" >&2; exit 1; }

echo "[1/2] GeoJSONL 生成 (DuckDB) ← $SRC"
"$DUCKDB" -c "
COPY (
  SELECT to_json({
    'type':'Feature',
    'geometry':{'type':'Point','coordinates':[lng,lat]},
    'properties':{
      'cat': cat,
      'name': name,
      'src': src,
      'sources': sources,
      'license': license
    }
  }) AS j
  FROM '$SRC'
  WHERE lat IS NOT NULL AND lng IS NOT NULL
) TO '$GEOJSONL' (FORMAT csv, HEADER false, QUOTE '', DELIMITER E'\t');
"
echo "  行数: $(wc -l < "$GEOJSONL")"

echo "[2/2] tippecanoe → $OUT"
tippecanoe -o "$OUT" -l stores -n 'Japan food store master (public)' \
  -z12 -B6 -r1 --drop-densest-as-needed --extend-zooms-if-still-dropping --force \
  "$GEOJSONL"

ls -la "$OUT"
