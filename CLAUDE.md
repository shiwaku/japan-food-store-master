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

**マスターは2系統ある。**

| | 件数 | 位置づけ |
|---|---:|---|
| `data/food_store_master.parquet` | 102,984 | Phase1（Overture 主・OSM 補完）。**公開マスターの実体** |
| `data/food_store_master_atp_based.parquet` | 119,092 | **ATP 基準**（2026-08-26 追加。`scripts/build_atp_based_master.py`）。座標の出所を店の公表値に揃えた系統。**推計用** |

ATP 基準は現行より drugstore が 42.5% → 111.6% と大きく改善し、3県の500m圏外率は 62.2% → 59.8%、
比 農水省÷変種A は 0.420 → 0.437（全市区町村で 比≤1 を維持）。設計と結果は
`docs/master/設計_ATP基準マスター構築.md`。**現行マスターは変更していない**ので、両方が並存する。

- **Phase1 マスター構築済み**: 約 102,984 店 / 農水省加重ベースの実質カバー率 93.5%。
- マスター実体: `data/food_store_master.csv` / `.parquet`（列 `cat`, `src_cat`, `name` 等。
  **`src_cat` はソース側の生カテゴリ**（Overture の category / OSM の shop）で、
  カバー率の分母が業態ごとに違うため 2026-08-27 に追加した。issue #33）。カテゴリ別件数:
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
- **「supermarket は実数の137%だから補完不要」は誤り**（issue #33、
  `docs/master/検証_supermarket分解と分母の確定.md`）。137% は業態が違う2系統の合成で、
  `src_cat='supermarket'`（Overture supermarket）由来 18,487 件だけをセンサス561+581（23,401）で割ると
  **79.0%＝約4,900店の不足**。地方はさらに低く島根42.5%・高知46.9%。
  `src_cat='grocery_store'` 由来 12,151 件は589系で**分母が手元に無い**（e-Stat API の appId が必要）。
  → **分母はセンサス561+581、分子は src_cat='supermarket' のみ**で語る。
  ただし grocery 由来を落とすと3県の圏外率は +2.0pt 悪化する（＝指標には効いている）ので**消さない**。
- **カテゴリ優先度が加重の議論と逆転する**: convenience −16.6pt ＞ fresh_food −3.3pt ＞ drugstore −1.2pt。
  fresh_food は drugstore の約3倍効き、かつカバー率30%（不足23,890店）＝伸びしろ最大。
  「drugstore/fresh は補完不要」（`docs/archive/Phase1検証まとめと次の一手.md`）は **fresh_food については誤り**。

### 次の一手（優先順）

> 2026-08-26 時点の未対応は GitHub issue に起票済み:
> #26（許可データでの補完 → **⑪ 総合スーパーは 2026-08-27 に実測済み**、下記）/ #33（supermarket 132% → **2026-08-27 に分母を確定**、下記）/ #34（convenience 106%）/ #35（自前クロール28本の規約）/
> #36（マスターのデイリーヤマザキ測地系ズレ）/ #37（OSM のローソン440mズレ）/ #38（47県への拡張）。

1. **自動車利用困難率を外部データで固定**して係数0.42を分解する（絶対推計への唯一の道）。
2. **fresh_food の補完 → 2026-08-27 に許可データで実測済み**
   （`docs/sources/検証_許可データ_生鮮3業種_補完効果.md`）。生鮮3業種（魚介類・食肉・野菜果物 販売業）
   からの純増は 21,511件で、3県の500m圏外率 62.2%→60.1%、比≤1 維持、
   **農水省公表値との相関 r が 0.448→0.460 に改善**。ATP基準＋生鮮＋⑪ なら 57.3%（比 max 0.793 / r 0.462）。
   `python3 scripts/extract_permit_fresh_food.py`（マスターは書き換えない）。
   残るのは投入の判断と、level 3（町丁目レベル）座標の扱い（`MIN_LEVEL=8` の効果は未測定）。
3. **許可データ⑪の投入**（issue #26、`docs/sources/検証_許可データ_総合スーパー_補完効果.md`）。
   届出「⑪ 百貨店、総合スーパー」からの純増は現行マスターに 4,191件・ATP基準に 3,157件で、
   3県の500m圏外率は 62.2%→61.4%（ATP基準 59.8%→59.2%）、比≤1 は全市区町村で維持。
   **ライセンスは再配布可（CC BY / 政府標準利用規約）＝ ATP の自前クロールと違い公開マスターに入れられる**。
   ただし**相関 r はわずかに下がる**（0.448→0.445。純増が都市部に多く地方の穴に効かない）ので、
   **生鮮3業種（2番）を先に入れる**こと。公開マスターへは #33 の整理が先。
   `python3 scripts/extract_permit_supermarkets.py`（マスターは書き換えない）。
4. 地方 supermarket の OSM 補完（S1で83.2%が圏外＝穴は大きい。**実装前に検証器で効果を測る**）。
   純増は 4,576件（100m判定）で許可⑪ との重複は 1,209件＝28.8% だけ＝**両者は相補的**。
   ただし OSM は **ODbL 継承**が付くので、投入はライセンス精査とセット。
5. 閉店店舗の除外（Overture deduped は `operating_status` 空＝偽陽性方向）。
   **許可データの届出行では代替できない**（日付列が全件空。落とし穴の節）。
6. 検証県を47県に拡張。
- その他候補: 道の駅の追加検討（`docs/master/検討_道の駅の追加可否.md`、現状は見送り）。

## データソースと役割

**現時点でマスターに入っているのは Overture と OSM の2つだけ**。他は「検証用」または「投入候補」で、
まだ入っていない（実測: `data/food_store_master.parquet` の `src` 列は overture 97,600 / osm 5,384 の2値のみ）。

| ソース | 役割 | ライセンス |
|---|---|---|
| Overture Places | **構築**: 位置の主ソース（コンビニ・スーパー等） | CDLA-Permissive-2.0（Foursquare 由来分は Apache 2.0） |
| OpenStreetMap | **構築**: 位置の補完（生鮮・GMS 等）・比較対象 | **ODbL 1.0（継承あり）** |
| All The Places ＋自前クロール（`data/atp/` 52チェーン） | **ATP 基準マスターの土台**（86,363件）。公開マスターには未投入 | 公式14本は CC-0／自前38本は**再配布不可** |
| 食品営業許可オープンデータ | **検証**＋**穴埋めの投入候補**（⑪総合スーパーの純増4,191件を実測。まだ入っていない） | 各自治体（保健所）／**厚生労働省** FAS ／CC BY 4.0・政府標準利用規約（**再配布可**） |
| 経済センサス・商業動態統計（e-Stat） | **検証のみ**: 数量検証・カテゴリ別カバー率 | 政府標準利用規約 |
| 業界実数（JFA・SM白書・JACDS 等） | **検証のみ**: 全国実数のクロスチェック | 各提供元 |

- **食品営業許可オープンデータを位置ソースに採らなかった理由**: 許可台帳であって施設マスタではない
  （同一施設が業種ごとに複数行）／コンビニは実数の約半分（27,615 / 約56,000）。詳細は `docs/permits/`。
  `scripts/reproduce_food_opendata/`（92出典の再現 MVP）も検証用の資産で、マスター構築パイプラインではない。

- Overture を主にした理由・網羅性検証の数値・原典構成比（Meta 39.8% ほか）は README と `docs/master/設計_食料品店マスター構築.md` / `docs/sources/検証_食品店データ_OSM_vs_Overture.md` 参照。

## ATP（チェーン公式サイト由来）の扱い

- 実体は `data/atp/*.geojson`（52チェーン）→ `scripts/build_atp_geoparquet.py` で
  `data/atp_food_stores_japan_geo.parquet`（86,363件）に畳む。
- **再配布できるのは ATP 公式ラン14本（CC-0）だけ**。自前クロール38本は各社規約で再配布不可。
  出力の `redistributable` 列で行単位に判別できる。**分析・推計に使うことに制約は無い**（禁じられているのは
  店舗データそのものの再配布）。詳細は `docs/sources/調査_自前クロールソースの利用規約と再配布可否.md`。
- カテゴリ別の素性: convenience 101%・drugstore 110%（実数統計比）は ATP 単独で満たすが、
  **supermarket 46.6%・fresh_food 0%**。だから「ATP 単独ではマスターにならない、土台＋補完」。

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

- **ブランド名の表記ゆれで重複が「純増」に化ける**。マスターは「セブンイレブン」、ATP は
  「セブン-イレブン」。ソース間の突合前に `-`／`‐`／`－`／空白を落として正規化すること
  （seven_eleven の純増 3,415 件のうち 1,570 件が実は既存店だった）。

- **データ側に測地系ズレが混ざっている**。マスター（Overture 由来）の**デイリーヤマザキ 943件**は
  旧日本測地系のままで北へ+358m・西へ−264m ずれる（補正すると 87% が別の500mメッシュへ移る）。
  **OSM のローソン 11,369件**も約440mずれる（viewer の `osm_food.pmtiles` に影響）。
  位置がおかしいと感じたら、まずブランド単位で他ソースとの差分の中央値を取ること。

- **食品営業許可・届出データの区分番号「⑪」は衝突する**。許可業種の `⑪ 菓子製造業`（37,032行）と
  届出業種の `⑪ 百貨店、総合スーパー`（25,189行）が別体系で同じ番号を使う。
  **番号だけで絞ると菓子製造業を巻き込む**ので、区分名まで含めた完全一致で抽出する。

- **届出行には `license_date` / `expire_date` が無い**（⑪ の25,189行は全件空。許可業種の行にはある）。
  したがって**許可データで廃業・閉店を落とすことはできない**。閉店混入は過剰計上の方向に残る。

- **法人名は名称の先頭とは限らない**。「イオンリテール株式会社イオン小松店」のように途中に入る形があり、
  接頭辞だけ剥がすと突合キーが「イオンリテル…」になってマスターの「イオン小松店」に当たらず
  **偽の純増**になる。`food_store_rules.py` の `match_key_sql()`（法人語をどこにあっても落とす）を使い、
  ブランド突合は**両方向**（許可→マスター、マスター→許可）見ること。

- **許可データの生鮮3業種は「収集」ではなく「フィルタリング」が本体**。施設 58,493件は
  センサス582/583/584（33,960）の約1.7倍あり、飲食店（焼肉・寿司・ステーキ店が食肉／魚介類販売業の
  許可を持つ）・卸・市場・加工場・移動販売・チェーンの鮮魚精肉売場が混ざる。
  **飲食店を落とさないと全国に偽の食料品店が湧いて500mメッシュ指標が過小に出る**。
  判定リストは `food_store_rules.py` の `fresh_excluded_sql()`。

- **チェーン判定の接頭辞は3文字にする**。ブランドキー（先頭5文字）で突合すると「ローソン」は
  正規化で長音が落ちて3文字（ロソン）になり、キーに店名が食い込んで店ごとに変わるため
  **一件も当たらない**（コンビニの売場が丸ごと漏れる）。実測: 先頭3文字・全国10件以上で 4,953件、
  先頭4文字では 1,894件しか当たらない。`permit_gapfill.run(chain_filter=True)`。

- **件数を足せば圏外率は必ず下がるので、下がったこと自体は判定材料にならない**。
  投入の可否は「比 農水省÷変種A が1を超えないこと」と
  **「農水省公表値との相関 r が上がること」**で見る（検証器が両方出す）。

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
- **ATP 基準マスターの再生成**（`docs/master/設計_ATP基準マスター構築.md`）:
  ```
  python3 scripts/fetch_alltheplaces_jp.py data/atp    # 52チェーンの geojson → parquet
  python3 scripts/build_atp_geoparquet.py              # → data/atp_food_stores_japan_geo.parquet
  python3 scripts/build_atp_based_master.py            # → data/food_store_master_atp_based.parquet
  FOOD_MASTER=data/food_store_master_atp_based.parquet OUT_SUFFIX=_ATP基準     python3 scripts/validate_access_difficulty.py 高知県 島根県 宮城県
  ```
  座標がずれているチェーンは住所から取り直す:
  `python3 scripts/geocode_atp_geojson.py --replace data/atp/<chain>.geojson`
- **supermarket の分解（分母の確定。issue #33）**:
  ```
  python3 scripts/build_food_store_master.py     # src_cat 列つきで再生成（件数は 102,984 のまま不変）
  python3 scripts/decompose_supermarket.py       # → docs/master/検証_supermarket分解_都道府県別.csv
  ```

- **許可データ⑪からの supermarket 補完候補**（`docs/sources/検証_許可データ_総合スーパー_補完効果.md`）:
  ```
  python3 scripts/extract_permit_supermarkets.py          # → data/permit_supermarket_candidates.parquet
  FOOD_MASTER=data/food_store_master_atp_based.parquet \
      OUT_PARQUET=data/permit_supermarket_candidates_atp.parquet \
      OUT_CSV=docs/sources/検証_許可データ_総合スーパー_都道府県別_ATP基準.csv \
      python3 scripts/extract_permit_supermarkets.py
  ```
  入力は `data/facilities-all.csv`（`japan-facilities-address` の統合出力・gitignore）。
  マスターは書き換えない。投入効果を測るときは純増を足した parquet を作って検証器に渡す。

- **許可データ生鮮3業種からの fresh_food 補完候補**
  （`docs/sources/検証_許可データ_生鮮3業種_補完効果.md`）:
  ```
  python3 scripts/extract_permit_fresh_food.py     # → data/permit_fresh_food_candidates.parquet
  INCLUDE_PACKAGED=1 python3 scripts/extract_permit_fresh_food.py   # 包装済み届出も含める（既定は除外）
  MIN_LEVEL=8 python3 scripts/extract_permit_fresh_food.py          # 町丁目レベル座標を落とす
  ```
  ⑪ と生鮮は `scripts/permit_gapfill.py` を共有する（抽出→畳み→フィルタ→突合→県別）。

- **検証器の店舗レイヤと出力先は環境変数で差し替えられる**（`FOOD_MASTER` / `OUT_SUFFIX`、
  `compare_atp_with_master.py` は `OUT_CSV`）。既存の検証結果 CSV を実験で上書きしないこと。
