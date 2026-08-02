# CLAUDE.md — japan-food-store-master

このリポジトリで作業するときの前提・手順・落とし穴をまとめる。次回はまずこれを読むこと。

## このリポジトリは何か

農水省「[食料品アクセス](https://www.maff.go.jp/j/shokusan/eat/access_genjo.html)」（食料品アクセス困難人口の推計）の定義に準拠した、**全国の食料品店 POI マスターデータセット**の構築・検証・可視化リポジトリ。

- 姉妹リポジトリ `japan-mobility-ease-diagnosis`（住所を入れるだけの移動しやすさ診断）の**目的地レイヤー**として使う食料品店データを、再現可能なパイプラインとして分離・整備するのが目的。
- 2026-07-19 に `japan-mobility-ease-diagnosis` から履歴ごと分離して発足（分離前の履歴は両repo共通）。

## リポジトリ構成

```
scripts/     構築パイプライン（DuckDB SQL / Python / 食品オープンデータ再現）
docs/        分析の一次記録。**docs/README.md が索引**（どれを読むかはそこで引く）
  master/    食料品店マスターの設計・検証・ライセンス（本題。新規参加者はここだけでよい）
  sources/   ソース比較と統計突合（OSM vs Overture、経済センサス・商業動態）
  permits/   食品営業許可オープンデータ（別テーマ。マスターの主ソースではない）
  archive/   古い記録・公開原稿（⚠ 現状と食い違う記述を含む。根拠に使わない）
data/        成果物・中間データ（大容量・生データは .gitignore。qml のみ追跡）
viewer/      OSM vs Overture 比較ビューア（Vite + TypeScript + MapLibre GL / PMTiles）
  index.html          パネルの静的マークアップ（中身は main.ts が生成）
  src/main.ts         アプリ本体（地図・UI 配線）
  src/layers.ts       ソース/カテゴリ/件数(COUNTS)/ポップアップの定義
  src/basemap.ts      淡色↔写真の切替とダークスタイル生成（明度反転）
  src/theme.ts        ライト/ダークの保存と <html data-theme>
  src/pale-style.json 地理院 最適化ベクトルタイル 淡色スタイル（ダーク化のため src に置く）
  public/             公開用 PMTiles・アイコン
.github/workflows/deploy.yml  viewer を GitHub Pages へ自動デプロイ
```

## 作業ワークフロー（厳守）

- **main へ直接コミット・push しない**。必ずブランチを切って PR を作成しマージする。
  ```
  git checkout -b <type>/<topic>      # feature/ fix/ docs/ 等
  # 変更 → コミット
  git push -u origin <branch>
  gh pr create --base main --head <branch> --title "..." --body "..."
  gh pr merge <n> --squash --delete-branch
  git checkout main && git pull --ff-only origin main
  ```
- コミットメッセージ末尾に `Claude-Session: <url>` を付ける。
- **追加系の実装（attribution・レイヤー・ソース・デフォルト値等）の前に、既存のスタイル/設定が提供済みでないか必ず grep で確認**する（重複防止）。特に MapLibre は style(pale.json) のソース `attribution` を自動集約するので、`customAttribution` に足すのはスタイルに無い出典だけ。

## 現状（データ）

- **Phase1 マスター構築済み**: 約 102,984 店 / 農水省加重ベースの実質カバー率 93.5%。
- マスター実体: `data/food_store_master.csv` / `.parquet`（列 `cat`, `name` 等）。カテゴリ別件数:
  `convenience 54,792 / supermarket 30,638 / fresh_food 10,070 / drugstore 7,484`。
- **調剤専業は除外済み**（2026-07-31・246件）。判定は `scripts/food_store_rules.py` に置き、
  構築（`build_food_store_master.py`）と検証（`verify_master_quality.py`）が**共有**する。
  名称ベースの判定なので、**食品を扱う地方ドラッグストアを巻き添えにしないためのチェーン名リストが本体**
  （レデイ・ウォンツ・ヤックス・セイムス・杏林堂・ウェルネス 等）。新しいチェーンを見つけたらここに足す。

### ⚠️ 加重カバー率（93.5%）を fit-for-purpose の根拠に使わないこと

農水省の指標は **500mメッシュ単位の二値・空間指標**で、件数比の加重平均とは別物。
メッシュ単位で検証した結果（`docs/master/検証_アクセス困難人口_メッシュ単位.md`、3県88市区町村）:

- **農水省の「500m以上」は同一500mメッシュ内の店舗存否**として実装されている（直線500m円ではない）。
  実距離500m版・9近傍メッシュ版は公表値との比が1を超える市区町村が出て論理的に不整合。
  → **隣メッシュの店舗には救われない**＝店舗の網羅性が距離指標に直に効く。
- 現状マスターは公表値を**単一係数0.42で再現**でき比≤1を全市区町村で満たす → 相対比較には使える。
  ただし係数が自動車利用困難率と店舗の穴のどちらに由来するか分離できていない
  → **絶対人数の推計にはまだ耐えない**。市区町村単位の店舗由来誤差は概ね ±20〜30%。
- **カテゴリ優先度が加重の議論と逆転する**: convenience −16.6pt ＞ fresh_food −3.3pt ＞ drugstore −1.2pt。
  fresh_food は drugstore の約3倍効き、かつカバー率30%（不足23,890店）＝伸びしろ最大。
  「drugstore/fresh は補完不要」（`docs/archive/Phase1検証まとめと次の一手.md`）は **fresh_food については誤り**。

### 次の一手（優先順）

1. **自動車利用困難率を外部データで固定**して係数0.42を分解する（絶対推計への唯一の道）。
2. **fresh_food の補完**（OSM の生鮮3種は計6,890件しかなく、センサス582/583/584 との差を埋める新ソースが必要）。
3. 地方 supermarket の OSM 補完（S1で83.2%が圏外＝穴は大きい。**実装前に検証器で効果を測る**）。
4. 閉店店舗の除外（Overture deduped は `operating_status` 空＝偽陽性方向）。
5. 検証県を47県に拡張。
- その他候補: 道の駅の追加検討（`docs/master/検討_道の駅の追加可否.md`、現状は見送り）。

## データソースと役割

**マスターに入るのは Overture と OSM の2つだけ**。他は全部「検証用」で、マスターには投入しない。
（実測: `data/food_store_master.parquet` の `src` 列は overture 97,600 / osm 5,384 の2値のみ）

| ソース | 役割 | ライセンス |
|---|---|---|
| Overture Places | **構築**: 位置の主ソース（コンビニ・スーパー等） | CDLA-Permissive-2.0（Foursquare 由来分は Apache 2.0） |
| OpenStreetMap | **構築**: 位置の補完（生鮮・GMS 等）・比較対象 | **ODbL 1.0（継承あり）** |
| 食品営業許可オープンデータ | **検証のみ**（マスターに入らない） | 各自治体（保健所）／**厚生労働省** FAS |
| 経済センサス・商業動態統計（e-Stat） | **検証のみ**: 数量検証・カテゴリ別カバー率 | 政府標準利用規約 |
| 業界実数（JFA・SM白書・JACDS 等） | **検証のみ**: 全国実数のクロスチェック | 各提供元 |

- **食品営業許可オープンデータを位置ソースに採らなかった理由**: 許可台帳であって施設マスタではない
  （同一施設が業種ごとに複数行）／コンビニは実数の約半分（27,615 / 約56,000）。詳細は `docs/permits/`。
  `scripts/reproduce_food_opendata/`（92出典の再現 MVP）も検証用の資産で、マスター構築パイプラインではない。

- Overture を主にした理由・網羅性検証の数値・原典構成比（Meta 39.8% ほか）は README と `docs/master/設計_食料品店マスター構築.md` / `docs/sources/検証_食品店データ_OSM_vs_Overture.md` 参照。

## ⚠️ ライセンス（律速は OSM の ODbL）

- **公開前に必ずライセンス範囲を精査する**（ユーザー厳命）。律速は OSM 由来物の **ODbL 継承（share-alike）**。
- 公開ビューアは OSM 由来 `viewer/public/osm_food.pmtiles` を配信する。**帰属表示は実装済み**（© OpenStreetMap contributors（ODbL）／© Overture Maps Foundation／地理院は pale.json 自動表示）だが、**ODbL の継承は別途精査対象**（派生DBの ODbL 提供担保）。

## viewer（比較ビューア）

- 公開 URL: **https://shiwaku.github.io/japan-food-store-master/**
- ローカル開発・ビルド:
  ```
  cd viewer
  npm ci
  npm run dev      # ローカル確認
  npm run build    # dist/ 生成
  ```
- デプロイ: `viewer/**` を含む push が main に入ると GitHub Actions が自動デプロイ（Pages ソースは GitHub Actions）。
- UI は `japan-mobility-ease-diagnosis` 系の
  [mlit-urban-planning-converter/viewer](https://github.com/shiwaku/mlit-urban-planning-converter/tree/main/viewer)
  に合わせた作り（CSS変数のライト/ダーク、デスクトップ＝全高サイドパネル／モバイル＝ボトムシート、
  トグルスイッチ、背景切替（地図/写真）、不透明度スライダー）。
- カテゴリ絞り込みでソース別件数が連動する。**件数は `viewer/src/layers.ts` の `COUNTS` にハードコード**（pmtiles は tippecanoe の間引きで実行時カウント不可のため）。pmtiles を再生成したら `scripts/compare_sources_by_category.sql` で件数を出し直して `COUNTS` を更新すること。
- **表示モードが2つある**（`viewer/src/layers.ts` の `Mode`）。
  - `source`（既定）: 色＝データソース（Overture 青／OSM 橙）。OSM vs Overture の比較用。
  - `category`: 色＝業態。z<13 はカテゴリ色の丸点、**z≥13 は
    [shiwaku/custom-smartmap-sprite](https://github.com/shiwaku/custom-smartmap-sprite) のピン**
    （`food-supermarket` `food-convenience` `food-drugstore` `food-grocery` `food-fresh`、MIT / Geolonia）。
  - **カテゴリ色はスプライトのアイコン色と手動同期**（`CATEGORIES` の `color`）。アイコンの色を変えたら
    `layers.ts` も直すこと。スプライトは `basemap.ts` の `withFoodSprite()` が全背景スタイルに注入する
    （MapLibre の複数スプライトは、接頭辞なしで引けるのは id `default` だけなので地理院側を `default` に据え、
    追加分は `smartmap:<アイコン名>` で参照する）。

### viewer の落とし穴（参考実装から引き継いだもの）

- **`backdrop-filter`（すりガラス）は使わない**。内部スクロールを持つパネルで実GPUの合成不具合が出る（白化・欠け）。背景は不透明にする。
- **パネルは `top:0`＋`bottom:0` で全高固定**。`height:auto` にすると内容が画面より低いとき下端が動く。モバイル（`top:auto`）で畳むときは `bottom:0` を明示しないとパネルが画面最上部へ飛ぶ。
- **checkbox は `position:absolute` で視覚非表示にし、必ず `.toggle` ラベル内に閉じ込める**。パネル外が基準になるとフォーカス移動でパネルのスクロールが壊れる。
- **MapLibre 5 は `filter: undefined` を明示的に渡すとバリデーションで落ちる**（`array expected, undefined found`）。フィルタ無しはキー自体を持たせない。
- **背景の差し替えは `setStyle(..., {diff:false})` ＋ `once('idle')` で再追加**。ラスタ（写真）↔ベクタ（淡色）は diff 適用が効かない。
- **WSL では vite の HMR が `/mnt/c` 配下の変更を拾わないことがある**。挙動が変わらないときは dev サーバーを再起動して、`curl http://localhost:PORT/.../src/main.ts` で配信内容を確認する。

## 落とし穴・環境メモ

- **除外ルールを `where not (…)` で書くと NULL 行が黙って消える**。`name` が NULL だと `ilike` が
  NULL を返し `not (NULL)` は真にならないため、名称欠損の 495 件が丸ごと落ちた（件数が合わずに発覚）。
  除外述語は必ず `coalesce(…, false)` で包む。

- **DuckDB spheroid バグ**: この環境では `ST_Distance_Spheroid` / `ST_DWithin_Spheroid` が `-nan` を返して使えない。距離は等距円筒近似（緯度補正した平面距離）で代替する。
- **Overture の bbox 抽出は国外を含む**: `data/overture_food_full_jp.parquet`（246,400 件）は日本の bbox 抽出で韓国・ロシア等を含む。日本のみは `country = 'JP'`（234,077 件）で絞る。
- **pmtiles の間引きは低ズームだけ**。`-r1`（droprate 1）でレート間引きは無効化してあり、
  `--drop-densest-as-needed` はタイルがサイズ上限を超えたときしか発動しない。実績（pmtiles の
  `strategies` メタデータで確認可能）は **Overture が z0–z8 のみ**（z8 で 19,273件）、**OSM は全ズームで未発動**。
  **z9 以上は両ソースとも全点保持**で、maxzoom 12 のタイルを z13 以上でオーバーズームするため
  拡大時も欠けない（渋谷の z12 タイルで実測 1,522 features / 同 bbox の元データ 1,440 件＝タイルバッファ分だけ多い）。
  低ズームでは「地図上の描画数＝実データ件数」にならない点だけ注意。
  なお**カテゴリ別モードのピンが間引かれて見えるのは MapLibre のシンボル衝突判定**で、タイル側の間引きとは別。
- DuckDB CLI: `/home/shi-works/.duckdb/cli/latest/duckdb`。
- **DuckDB の `/` は DOUBLE を返し `::int` が四捨五入する**。メッシュ添字等の整数除算は必ず `//` を使う（`(m-1)/2` で m=2 が 0.5→1 に丸められ別メッシュと衝突した）。
- **`ST_Read` の戻り型は `GEOMETRY('EPSG:4612')`** で、そのままでは rtree インデックスが作れない。`geom::GEOMETRY` で素の型に落とす。
- **e-Stat 境界 shapefile の DBF は CP932**。`CITY_NAME`/`PREF_NAME` を読むと DuckDB が unicode エラーを出す。ASCII のコード列（`PREF`,`CITY`）のみ読む。
- **e-Stat メッシュ統計の列番号**: `T001141019` が65歳以上、`T001141022` は**75歳以上**。取り違えると分母が半分になる。
- **e-Stat 統計GIS は appId 不要**でダウンロードできる（`statmap-search/data?dlserveyId=...&statsId=...`）。メッシュ統計・小地域境界とも。e-Stat API の appId はユーザー保有で、リポジトリには無い。

## 再現の要点

- 比較用 pmtiles 再生成: `bash scripts/build_pmtiles.sh [overture|osm|all]`（既定 all、tippecanoe 必要）。
  `data/overture_food_deduped_jp.parquet` → `viewer/public/overture_food.pmtiles`、
  `data/osm_food_stores_japan.tsv` → `viewer/public/osm_food.pmtiles`。
  **cat のバケット定義は `scripts/compare_sources_by_category.sql` と一致させること**
  （viewer の `COUNTS` はあの SQL の出力なので、定義がズレると表示件数とタイルの中身が食い違う）。
- カテゴリ別件数の集計: `duckdb -c ".read scripts/compare_sources_by_category.sql"`。
- 食品オープンデータ再現 MVP: `scripts/reproduce_food_opendata/`（Python、92 出典 → 統合。README 参照）。
- **アクセス困難人口でのマスター検証**（fit-for-purpose 判定に使う本命の検証器）:
  ```
  python3 scripts/fetch_mesh_population.py 高知県 島根県 宮城県      # 500mメッシュ人口
  python3 scripts/validate_access_difficulty.py 高知県 島根県 宮城県  # 圏外率＋農水省突合
  ```
  外部データは自動取得・キャッシュ（`data/mesh/` `data/boundary/` `data/maff_2020_table05.xlsx`、いずれも gitignore）。
  詳細と判定結果は `docs/master/検証_アクセス困難人口_メッシュ単位.md`。
- マスター再生成: `python3 scripts/build_food_store_master.py`（`data/japan_pref.geojson` は無ければ自動取得）。
