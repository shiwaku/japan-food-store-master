-- Overture Places(release 2026-06-17.0)から日本の食料品系POIを
-- 名寄せ・再現に必要なフルフィールド付きで再抽出する。
--
-- 従来の data/overture_food_stores_japan*.parquet は簡略版で sources/brand/country を
-- 削いでおり、JP絞り込みとクロス提供元conflation(名寄せ)が再現不可だった。本抽出で解消する。
--
-- 出力: data/overture_food_full_jp.parquet
-- 使い方: duckdb -c ".read scripts/extract_overture_full.sql"

INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;
SET s3_region='us-west-2';

COPY (
  SELECT
    id,
    names.primary                                   AS name,
    categories.primary                              AS category,
    categories.alternate                            AS category_alt,
    confidence,
    brand.wikidata                                  AS brand_wikidata,
    brand.names.primary                             AS brand_name,
    operating_status,
    -- JP判定用: addresses配列の先頭の国と行政区
    addresses[1].country                            AS country,
    addresses[1].region                             AS region,
    addresses[1].locality                           AS locality,
    addresses[1].freeform                           AS address,
    -- 提供元データセット(名寄せの手がかり)
    list_transform(sources, s -> s.dataset)         AS datasets,
    -- 点ジオメトリなので bbox.xmin/ymin が lon/lat と一致(WKBパース不要)
    bbox.xmin                                       AS lon,
    bbox.ymin                                       AS lat
  FROM read_parquet('s3://overturemaps-us-west-2/release/2026-06-17.0/theme=places/type=place/*.parquet')
  WHERE bbox.xmin BETWEEN 122.5 AND 154.0
    AND bbox.ymin BETWEEN 24.0 AND 45.8
    AND categories.primary IN (
      'convenience_store','pharmacy','grocery_store','supermarket','discount_store',
      'drugstore','butcher_shop','farmers_market','department_store','seafood_market'
    )
) TO 'data/overture_food_full_jp.parquet' (FORMAT parquet, COMPRESSION zstd);
