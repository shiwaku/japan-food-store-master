-- 名寄せ済み食料品POI層の生成(単一提供元方式)
--
-- 背景: Overtureの日本コンビニは同一実店舗が提供元ごとに別レコードで残り、座標ズレ>500mのため
--       空間名寄せでは重複除去と別店舗保持を両立できない(検証_食品店データ_OSM_vs_Overture.md 3-1)。
--       各提供元は1店舗1レコードなので、チェーンごとに最網羅の単一提供元だけを採る=構造的に重複ゼロ。
--
-- 方式: 5大コンビニチェーンは「datasetsに最良提供元を含むレコードのみ」採用(重複ゼロ・座標良好・実数の約85-90%)。
--       その他コンビニ・スーパー・その他カテゴリ(重複軽微)は現状維持。pharmacy/discount/department は定義外で除外。
--
-- 入力: data/overture_food_full_jp.parquet   出力: data/overture_food_deduped_jp.parquet
-- 使い方: duckdb -c ".read scripts/build_deduped_layer.sql"

COPY (
  WITH base AS (
    SELECT *,
      CASE WHEN name LIKE '%セブン%イレブン%' THEN 'セブンイレブン'
           WHEN name LIKE '%ローソン%' THEN 'ローソン'
           WHEN name LIKE '%ファミリーマート%' OR name LIKE '%ファミマ%' THEN 'ファミリーマート'
           WHEN name LIKE '%ミニストップ%' THEN 'ミニストップ'
           WHEN name LIKE '%デイリーヤマザキ%' THEN 'デイリーヤマザキ' END AS chain
    FROM 'data/overture_food_full_jp.parquet'
    WHERE country = 'JP'
      AND category NOT IN ('pharmacy','discount_store','department_store')
  ),
  -- チェーン→最良提供元(実測の最網羅提供元)
  best AS (
    SELECT * FROM (VALUES
      ('セブンイレブン','Foursquare'),
      ('ローソン','AllThePlaces'),
      ('ファミリーマート','AllThePlaces'),
      ('ミニストップ','meta'),
      ('デイリーヤマザキ','AllThePlaces')
    ) AS t(chain, provider)
  )
  SELECT b.* EXCLUDE (chain, datasets),
    b.chain AS chain,
    CASE WHEN b.chain IS NOT NULL THEN 'best-provider' ELSE 'as-is' END AS dedup_method
  FROM base b
  LEFT JOIN best USING (chain)
  WHERE
    -- 5大チェーン: 最良提供元を含むレコードのみ
    (b.chain IS NOT NULL AND list_contains(b.datasets, best.provider))
    -- それ以外(その他コンビニ含む・スーパー等): 全件維持
    OR b.chain IS NULL
) TO 'data/overture_food_deduped_jp.parquet' (FORMAT parquet, COMPRESSION zstd);
