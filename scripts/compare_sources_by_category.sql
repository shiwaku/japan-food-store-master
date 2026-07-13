-- Overture(名寄せ済) vs OpenStreetMap をカテゴリ別に件数比較(農水省「食料品アクセス」定義準拠)
-- バケット: super=スーパー / conv=コンビニ / drug=ドラッグストア / grocery=食料品店 / fresh=生鮮専門店・直売所
-- 非食料品(調剤薬局pharmacy・100均/variety・百貨店department 等)は両ソースとも除外。
-- 入力: data/overture_food_deduped_jp.parquet, data/osm_food_stores_japan.tsv
-- 使い方: duckdb -c ".read scripts/compare_sources_by_category.sql"

WITH ovt AS (
  SELECT CASE category
           WHEN 'supermarket' THEN 'super'
           WHEN 'convenience_store' THEN 'conv'
           WHEN 'drugstore' THEN 'drug'
           WHEN 'grocery_store' THEN 'grocery'
           ELSE 'fresh' END AS bucket   -- butcher_shop/farmers_market/seafood_market
  FROM 'data/overture_food_deduped_jp.parquet'
),
osm_raw AS (
  SELECT lower(shop) AS shop, lower(amenity) AS amenity
  FROM read_csv('data/osm_food_stores_japan.tsv', delim='\t')
),
osm AS (
  SELECT CASE
    WHEN shop='supermarket' THEN 'super'
    WHEN shop='convenience' THEN 'conv'
    WHEN shop IN ('chemist','drugstore','drug store','drugs','dragstore','cosmetics') THEN 'drug'
    WHEN shop IN ('grocery','food','general','deli','confectionery') THEN 'grocery'
    WHEN shop IN ('greengrocer','seafood','butcher','farm') OR amenity='marketplace' THEN 'fresh'
    ELSE NULL END AS bucket
  FROM osm_raw
),
o AS (SELECT bucket, count(*) n FROM ovt GROUP BY 1),
s AS (SELECT bucket, count(*) n FROM osm WHERE bucket IS NOT NULL GROUP BY 1)
SELECT
  CASE b.bucket WHEN 'super' THEN 'スーパー' WHEN 'conv' THEN 'コンビニ'
                WHEN 'drug' THEN 'ドラッグストア' WHEN 'grocery' THEN '食料品店'
                WHEN 'fresh' THEN '生鮮専門店・直売所' END AS カテゴリ,
  COALESCE(o.n,0) AS Overture名寄せ済,
  COALESCE(s.n,0) AS OpenStreetMap,
  COALESCE(o.n,0) - COALESCE(s.n,0) AS 差
FROM (SELECT unnest(['super','conv','drug','grocery','fresh']) AS bucket) b
LEFT JOIN o USING(bucket) LEFT JOIN s USING(bucket)
ORDER BY array_position(['super','conv','drug','grocery','fresh'], b.bucket);
