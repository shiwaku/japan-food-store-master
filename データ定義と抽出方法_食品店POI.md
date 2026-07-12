# データ定義と抽出方法: 食品店POI

**作成**: 2026年7月12日
**目的**: 「移動しやすさ診断」の食料品店レイヤーで使うPOIデータの、定義・抽出条件・カテゴリ対応を再現可能な形で記録する。

---

## 1. 農林水産省「食料品アクセス」の定義

本プロジェクトの食料品店データは、農水省・農林水産政策研究所の**食料品アクセス困難人口**の推計で使われる「店舗」の考え方に合わせる。

### 食料品アクセス困難人口の定義

> **店舗まで直線距離500m以上 かつ 自動車利用が困難な65歳以上高齢者**

500mメッシュ単位で、国勢調査人口と店舗位置から推計される。

### 「店舗（食料品店）」に含まれる業態

| 含む | 備考 |
|---|---|
| 食品スーパー・各種食料品小売業 | いわゆるスーパー |
| 百貨店・総合スーパー（GMS） | |
| コンビニエンスストア | 地方では主要な食料調達先 |
| 生鮮食料品専門店（青果・精肉・鮮魚） | |
| **ドラッグストア** | **2020年推計から追加**（食品を扱うため） |

### 含まないもの（重要）

- **調剤薬局（食品を扱わない薬局）は含まない**。データ上、ドラッグストアと調剤薬局は別物として扱う必要がある。

### 数値の非連続に関する注意

- 2020年からドラッグストアが店舗定義に追加されたため、2015年以前の推計値とは非連続。経年比較の際は注意。

### 出典（農水省・公式）

- [食料品アクセス問題の現状（農水省）](https://www.maff.go.jp/j/shokusan/eat/access_genjo.html)
- [食料品アクセスマップ（農林水産政策研究所）](https://www.maff.go.jp/primaff/seika/fsc/faccess/a_map.html)
- [推計資料（2020年国勢調査ベース、2024年2月公表）PDF](https://www.maff.go.jp/primaff/koho/seminar/2023/attach/pdf/240319_01.pdf)

> **補足: 「空白地域」の所管の違い**
> 「交通空白地」は**国土交通省**の所管（下記）。農水省が扱うのは**食料品アクセス問題（買い物困難者／フードデザート）**。本アプリは両者を横断する（交通空白×食料品アクセス）。
> - [「交通空白」解消に関する取組（国交省）](https://www.mlit.go.jp/sogoseisaku/transport/sosei_transport_tk_000237.html)
> - [交通空白解消 特設サイト（国交省）](https://kotsu-kuhaku.jp/)

### 食料品アクセス困難人口の推計方法（詳細）

農林水産政策研究所の推計は、おおむね次式でメッシュ（500m）ごと・年齢階層別に困難人口を算出している。

> **困難人口 ≒ P(最寄り店舗まで500m以上) × 65歳以上人口 × (1 − 自動車利用率)**

#### (a) 「自動車利用が困難」の算出 ← 本アプリで最重要

- 車を使えない人を直接数えるのではなく、**統計上の「自動車利用率」の補数（1 − 利用率）**を高齢者人口に按分している。
- **現行方式（2015年推計〔2018年公表〕以降）＝ 個人単位の自動車利用率**。世帯に車があっても高齢者本人が利用できない場合を想定し、旧方式（世帯単位の「保有の有無」）から改めた。
- 適用の粒度 = **都道府県別 × 年齢階層別（65〜74歳／75歳以上の2区分）**。「65歳以上」一括ではない。
- 元データ = **2015年推計:『平成26年全国消費実態調査』の個票 ＋『民力』の市町村別自動車登録台数**／**2020年推計:『家計調査』個票等**（全国消費実態調査の全国家計構造調査への改組に伴い差替）。
- 参考値（全国・2015年）: 65〜74歳 79.7%／75歳以上 57.0%（＝困難割合 約20%／約43%）。都道府県差大（例: 山形94.4%）。
- **旧方式（2005〜2010年推計）＝ 世帯単位の自動車保有率**（『平成15年住宅・土地統計調査』ベース）。方式・元データとも推計年で変わり、**時系列は連続しない**（農水省も明記）。
- **⚠️ 未確認**: 個票と登録台数から利用率を出す具体的な回帰式は、出典とされる薬師寺哲郎(2017)『高齢者の自動車利用の推計』（食料供給プロジェクト研究資料第3号, pp.87-113）にあるとされるが本文未取得のため数式は一次資料で未確認。2020年推計が都道府県別粒度を維持したかも報告会PDFでは明記されず。

#### (b) 距離・メッシュ（確率法）

- **直線距離500m**（道路ネットワーク距離ではない）。人口のある500mメッシュごとに、当該＋周辺メッシュの店舗状況から「最寄り店舗が500m以上である確率」を算出し、人口に乗じる。

#### (c) 店舗の所在地データ

- 従来は「商業統計 地域メッシュ統計」。商業統計廃止後の**2020年推計は日本スーパー名鑑・電話帳データ等**（コンビニは日本フランチャイズチェーン協会の店舗数）。
- 業態別に「500m以上確率」を求め、消費者の**食料支出金額シェアで加重平均**（2020年推計の65歳以上世帯主シェア: 一般小売5.0%／スーパー等85.9%／コンビニ3.9%／ドラッグストア5.2%）。

#### (d) 人口データ

- 各推計年の**国勢調査 地域メッシュ統計（500mメッシュ、65歳以上・65〜74歳・75歳以上）**。2020年推計＝令和2年国勢調査。

#### 本アプリとの異同（応募での差別化ポイント）

| 観点 | 農水省 食料品アクセス困難人口 | 本アプリ（japan-transit-desert-analysis-125 + 診断） |
|---|---|---|
| 距離 | 直線500m | **道路ネットワーク距離（Dijkstra）** |
| 「移動できるか」の判定 | 統計上の自動車利用率を按分（個人の実態ではない） | **公共交通（バス停・駅）＋徒歩での到達可否** |
| 軸 | 食料品アクセス（買い物） | 交通空白 × 食料品アクセスを横断 |

→ 農水省は「車利用率の統計按分＋直線距離」。本作品は「道路距離＋公共交通到達」で、**車を使えない人が実際に生活できるかをメッシュ単位で捉え直す**点が新規性・補完性になる。

#### 推計方法の出典

- [2020年食料品アクセスマップと困難人口の推計結果について（研究成果報告会PDF, 高橋克也 2024）](https://www.maff.go.jp/primaff/koho/seminar/2023/attach/pdf/240319_01.pdf) … 推計方法変更の表・確率計算図
- [高橋克也(2018)「食料品アクセス問題の現状と今後」『フードシステム研究』25巻3号](https://www.jstage.jst.go.jp/article/jfsr/25/3/25_119/_pdf/-char/ja) … 個人単位／世帯単位・データソースの根拠
- [プレスリリース「2020年食料品アクセス困難人口の推計結果の公表」（2024/2/27）](https://www.maff.go.jp/j/press/kanbo/kihyo01/240227.html)
- （数式が載るとされる未取得資料）薬師寺哲郎(2017)『高齢者の自動車利用の推計』食料供給プロジェクト研究資料第3号, pp.87-113

---

## 2. 抽出対象カテゴリと相互対応

農水省定義に合わせ、両ソースを共通カテゴリ（`cat`）に正規化する。**調剤薬局は両ソースとも除外**。

| 共通カテゴリ `cat` | Overture `categories.primary` | OSM タグ |
|---|---|---|
| `super`（スーパー） | `supermarket` | `shop=supermarket` |
| `conv`（コンビニ） | `convenience_store` | `shop=convenience` |
| `drug`（ドラッグストア） | `drugstore` | `shop=chemist` |
| `grocery`（食料品店） | `grocery_store` | `shop=greengrocer/grocery/food` |
| `fresh`（生鮮専門店・直売所） | `butcher_shop` / `seafood_market` / `fruits_and_vegetables_store` / `farmers_market` | `shop=butcher/seafood`, `amenity=marketplace` |
| `discount`（ディスカウント） | `discount_store` | `shop=discount/variety_store` |
| `dept`（百貨店） | `department_store` | `shop=department_store` |
| **除外** | ~~`pharmacy`（調剤薬局）~~ | ~~`amenity=pharmacy`~~ |

---

## 3. Overture Places の抽出方法

- **ソース**: Overture Maps Foundation, Places テーマ（GeoParquet, S3公開）
- **リリース**: `s3://overturemaps-us-west-2/release/2026-06-17.0/theme=places/type=place/`
- **ライセンス**: CDLA-Permissive-2.0（タイル化・再配布可）
- **抽出ツール**: DuckDB（httpfs + spatial 拡張）
- **抽出範囲（bbox）**: `bbox.xmin BETWEEN 122.5 AND 154.0 AND bbox.ymin BETWEEN 24.0 AND 45.8`（日本全域、南西諸島〜北海道・小笠原を含む）
- **⚠️ 国フィルタ（必須）**: 上記bboxは韓国・北朝鮮・ロシア沿海州・中国沿岸を含むため、**`addresses[].country = 'JP'` で日本のみに絞る**。この属性は欠損なし。国別内訳（食品系全カテゴリ）は JP 234,077・KR 12,109・RU 160・CN 53・KP 1。bboxだけだと国外POIが約12,300件混入する。
- **カテゴリ条件**: 下記11カテゴリを抽出後、`pharmacy` を除外（農水省定義準拠）
  ```
  supermarket, grocery_store, convenience_store,
  butcher_shop, seafood_market, fruits_and_vegetables_store, farmers_market,
  drugstore, department_store, discount_store
  （抽出時は pharmacy も取得したが、定義準拠版では除外）
  ```
- **取得属性**: `id, names.primary(name), categories.primary(category), confidence, addresses[1].country/region, ST_X/Y(geometry)`
- **件数**: bbox生データ 246,400件 → `country='JP'`＋`pharmacy`除外後 **183,790件**
- **既知の課題**:
  - `region`（都道府県）属性が約66%欠損 → 都道府県別集計は行政区域データ（国土数値情報N03）との空間結合が必要（※`country`は欠損なし）
  - コンビニに支店名なしの重複エントリが多数（要ブランド名寄せ）
  - `fruits_and_vegetables_store` は0件（Overtureタクソノミー上、青果は別カテゴリの可能性。要確認）

### 抽出クエリ（DuckDB）

```sql
INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;
SET s3_region='us-west-2';
COPY (
  SELECT id, names.primary AS name, categories.primary AS category, confidence,
         addresses[1].country AS country, addresses[1].region AS region,
         ST_X(geometry) AS lon, ST_Y(geometry) AS lat
  FROM read_parquet('s3://overturemaps-us-west-2/release/2026-06-17.0/theme=places/type=place/*')
  WHERE bbox.xmin BETWEEN 122.5 AND 154.0 AND bbox.ymin BETWEEN 24.0 AND 45.8
    AND categories.primary IN (
      'supermarket','grocery_store','convenience_store',
      'butcher_shop','seafood_market','fruits_and_vegetables_store','farmers_market',
      'drugstore','pharmacy','department_store','discount_store')
) TO 'data/overture_food_stores_bbox.parquet' (FORMAT PARQUET);
-- 利用時は country='JP' AND category<>'pharmacy' で絞る（農水省定義・日本のみ）
```

---

## 4. OpenStreetMap の抽出方法

- **ソース**: OpenStreetMap（Overpass API）
- **エンドポイント**: `https://overpass-api.de/api/interpreter`（POSTパラメータ名は `data`）
- **ライセンス**: ODbL（出典表記のうえ再配布可）
- **取得日**: 2026-07-12
- **範囲**: `area["ISO3166-1"="JP"][admin_level=2]`（日本全域）
- **対象タグ**:
  ```
  shop = supermarket | convenience | greengrocer | grocery | food
       | butcher | seafood | department_store | chemist | discount | variety_store
  amenity = pharmacy | marketplace
  ```
- **定義準拠処理**: `amenity=pharmacy`（調剤薬局、`shop`タグ無し）を除外
- **件数**: 生データ 111,186件 → `amenity=pharmacy`除外後 **88,964件**
- **注意**: `shop=chemist`（ドラッグストア、食品扱う）は残し、`amenity=pharmacy`（調剤薬局）は除外。両者はOSM上で別タグ。

### 抽出クエリ（Overpass QL）

```
[out:csv(::type,::id,::lat,::lon,shop,amenity,name; true; "\t")][timeout:900][maxsize:1073741824];
area["ISO3166-1"="JP"][admin_level=2]->.jp;
(
  nwr[shop~"^(supermarket|convenience|greengrocer|grocery|food|butcher|seafood|department_store|chemist|discount|variety_store)$"](area.jp);
  nwr[amenity=pharmacy](area.jp);
  nwr[amenity=marketplace](area.jp);
);
out center;
```

取得コマンド:
```bash
curl -A "japan-mobility-ease-diagnosis (contact: ...)" \
  --data-urlencode data@overpass_query.txt \
  https://overpass-api.de/api/interpreter -o data/osm_food_stores_japan.tsv
```

---

## 5. 成果物ファイル

`data/`（gitignore対象・再生成可能）:
| ファイル | 内容 |
|---|---|
| `overture_food_stores_bbox.parquet` | Overture生抽出（bbox内・country列つき・pharmacy含む、246,400件。JP 234,077/KR 12,109/RU 160/CN 53/KP 1） |
| `osm_food_stores_japan.tsv` | OSM生抽出（111,186件） |

`public/`（GitHub Pages公開・農水省定義準拠・日本のみ）:
| ファイル | 内容 |
|---|---|
| `overture_food.pmtiles` | Overture 183,790件（country='JP'＋pharmacy除外） |
| `osm_food.pmtiles` | OSM 88,964件（amenity=pharmacy除外） |
| `compare.html` → `src/compare.ts` | MapLibre比較ビューワー（Vite+TS） |
| `compare_overview_jp.png` | 全国分布の静的比較画像 |

---

## 6. 品質検証の予定データソース

- **e-Stat 経済センサス 地域メッシュ統計**（令和3年、500m/1kmメッシュ、2025年10月提供開始）: 産業分類別「小売業」事業所数と突合し、両ソースの絶対カバー率を評価。政府標準利用規約で再配布可。
  - https://www.stat.go.jp/data/mesh/index.html
- **チェーン公式店舗一覧**: デモ県（長崎・青森）でスーパーの目視照合。

---

*関連: [検証_食品店データ_OSM_vs_Overture.md](検証_食品店データ_OSM_vs_Overture.md)*
