-- 名寄せの空間検証: コンビニ汎用名エントリの重複を近傍判定で定量化
--
-- ルール: あるコンビニPOIが「汎用名」(店名が「店」で終わらない=支店名なし)で、
--         かつ半径 R メートル以内に同一チェーンの「支店名つき」(〜店)POIが存在する場合、
--         そのエントリは支店名つきの実店舗と同一の重複とみなして削除する。
--
-- 距離計算: DuckDB の ST_Distance_Spheroid は本環境で -nan を返すため使用せず、
--           緯度補正つき等距円筒近似(equirectangular)で m を算出する。
--           近傍探索はグリッドセル(step度)＋8近傍セルで総当たりを回避する。
--
-- 依存: なし(標準SQLのみ)。生データ data/overture_food_stores_japan.parquet が入力。
-- 使い方: duckdb -c ".read scripts/dedup_convenience_spatial.sql"
--
-- === 検証結果サマリ(2026-07-13) ===
-- ・コンビニ汎用名エントリ(例「セブン-イレブン」ハイフン付 25,737件)は実店舗の重複レコードで、
--   座標が数百m単位でズレている。セブン汎用名28,053件のうち支店名つきが 50m内 31% / 500m内 89%。
--   → 「丸ごと重複」というドキュメントの見立ては概ね正しいが、50m名寄せでは18%しか捕捉できず不十分。
-- ・注意: 本DuckDB(v1.3.2)では ST_Distance_Spheroid / ST_DWithin_Spheroid が -nan を返すため使用不可。
--   本スクリプトは等距円筒近似で距離を算出している。
-- ・支店名つきセットの完全性はチェーンで差が大きい(セブン20,076≒実数, ローソン7,245≪実数14,600)ため、
--   「〜店」サフィックス基準だけでは真の実数を復元できない。厳密には fuzzy な record-linkage が必要。
-- ・カテゴリ差: スーパー(supermarket)は支店名つき62%で水増し軽微、実数約2万店とほぼ一致。
--   水増しが深刻なのはコンビニ。診断アプリの主目的地(スーパー)は比較的クリーン。

-- 判定半径(メートル)とグリッド一辺(度)。step≒0.0007°≒最大約78m(緯度26-44度)で50m判定を内包。
SET VARIABLE radius_m = 50;
SET VARIABLE step_deg = 0.0007;

WITH src AS (
  SELECT
    id, name, lon, lat,
    CASE
      WHEN name LIKE '%セブン%イレブン%' THEN 'セブンイレブン'
      WHEN name LIKE '%ローソン%'          THEN 'ローソン'
      WHEN name LIKE '%ファミリーマート%' OR name LIKE '%ファミマ%' THEN 'ファミリーマート'
      WHEN name LIKE '%ミニストップ%'      THEN 'ミニストップ'
      WHEN name LIKE '%デイリーヤマザキ%'  THEN 'デイリーヤマザキ'
      ELSE 'その他'
    END AS chain,
    (name LIKE '%店') AS branded,
    CAST(floor(lon / getvariable('step_deg')) AS BIGINT) AS gx,
    CAST(floor(lat / getvariable('step_deg')) AS BIGINT) AS gy
  FROM 'data/overture_food_stores_japan.parquet'
  WHERE category = 'convenience_store'
),
generic AS (SELECT * FROM src WHERE NOT branded),
branded AS (SELECT * FROM src WHERE branded),
-- 汎用名の各点の周囲9セルに同チェーンの支店名つきが居るか、居れば等距円筒距離で50m判定
nbr AS (
  SELECT g.id, g.lon, g.lat, b.lon AS blon, b.lat AS blat,
    sqrt(
      pow((b.lon - g.lon) * 111320.0 * cos(radians(g.lat)), 2) +
      pow((b.lat - g.lat) * 110540.0, 2)
    ) AS dist_m
  FROM generic g
  JOIN branded b
    ON g.chain = b.chain
   AND b.gx BETWEEN g.gx - 1 AND g.gx + 1
   AND b.gy BETWEEN g.gy - 1 AND g.gy + 1
),
dup AS (
  SELECT DISTINCT id FROM nbr WHERE dist_m <= getvariable('radius_m')
)
SELECT
  s.chain AS チェーン,
  count(*) FILTER (WHERE s.branded)                          AS 支店名つき,
  count(*) FILTER (WHERE NOT s.branded)                      AS 汎用名,
  count(*) FILTER (WHERE NOT s.branded AND d.id IS NOT NULL) AS 汎用名うち近傍重複,
  count(*) FILTER (WHERE NOT s.branded AND d.id IS NULL)     AS 汎用名うち孤立,
  count(*) - count(*) FILTER (WHERE NOT s.branded AND d.id IS NOT NULL) AS 名寄せ後件数
FROM src s
LEFT JOIN dup d USING (id)
GROUP BY ROLLUP(s.chain)
ORDER BY 名寄せ後件数 DESC NULLS FIRST;
