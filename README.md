# 全国 食料品店マスター（japan-food-store-master）

農水省「[食料品アクセス](https://www.maff.go.jp/j/shokusan/eat/access_genjo.html)」（[食料品アクセスマップ／農林水産政策研究所](https://www.maff.go.jp/primaff/seika/fsc/faccess/a_map.html)による食料品アクセス困難人口の推計）の定義に準拠した、全国の食料品店 POI マスターデータセットの構築・検証・可視化リポジトリ。

`japan-mobility-ease-diagnosis`（住所を入れるだけの移動しやすさ診断）の目的地レイヤーとして使う食料品店データを、単一の再現可能なパイプラインとして分離・整備することを目的とする。

> **アクセス困難人口の推計・検証は別リポジトリ**
> [japan-food-access-analysis](https://github.com/shiwaku/japan-food-access-analysis) に分離した（2026-08-27）。
> このリポジトリは**店舗レイヤの供給**に専念し、メッシュ人口・距離判定・農水省公表値との突合はそちらが持つ。
> 店舗レイヤの投入可否（比≤1・相関 r）を測るときは向こうの検証器に parquet を渡す。
> 人口レイヤは分離時に 500m → **125mメッシュ**（e-Stat `T001225`）へ変更済み。

## 何を作っているか

- **食料品店マスター**（スーパー・食料品店・コンビニ・ドラッグストア等）を統合構築。**現在2系統ある**
  - **公開マスター**: **Overture Places と OpenStreetMap の2ソース**から構築
    （実測: `src` 列は overture 97,600 / osm 5,384 の2値のみ）
  - **ATP 基準マスター**: チェーン公式サイト由来の店舗情報を土台に、不足を Overture / OSM で補完（後述）

  **食品営業許可オープンデータはどちらにも投入していない**（穴埋めの候補としては実測済み＝
  [docs/sources/検証_許可データ_総合スーパー_補完効果.md](docs/sources/検証_許可データ_総合スーパー_補完効果.md)）。
  下記「データソースとライセンス」参照
- 網羅性をカテゴリ別に実数と突合して検証。数量の裏取りには **経済センサス小売業・商業動態統計（e-Stat）** と **業界実数（JFA・スーパーマーケット白書・JACDS 等）** を用いる。主な検証結果：
  - コンビニ: 商業動態統計 **56,352 店**（≒JFA）に対し Overture 単独 **97.6%**
  - スーパー: スーパーマーケット白書 **23,078 店**・経済センサス小分類 581 に対し Overture 80% / OSM 88%（単一ソースでは悉皆にならず grocery 浄化が必要）
  - ドラッグストア: 商業動態統計 **17,622 店**・JACDS 約 21,000 店に対し POI は 4〜5 割（統計で件数補正）
- カテゴリマッピング・confidence フィルタ・重複除去の前処理を実装

現状: Phase1 構築済み（102,984 店 / 農水省加重ベースの実質カバー率 93.5%）。

> **生鮮（fresh_food）の穴は許可データで埋めた**（2026-08-27、ATP 基準マスターに投入済み）。
> 生鮮3業種（魚介類・食肉・野菜果物 販売業）からの純増で fresh_food は 29.6% → **80.4%**。
> → [docs/sources/検証_許可データ_生鮮3業種_補完効果.md](docs/sources/検証_許可データ_生鮮3業種_補完効果.md)

> **スーパーのカバー率は「137%」ではない**（2026-08-27、issue #33）。マスターの `supermarket` は
> Overture `supermarket` 由来 18,487 店と浄化 `grocery_store` 由来 12,151 店の合成で、業態が違うため分母も違う。
> 前者だけをセンサス 561+581（23,401）で割ると **79.0% ＝ 約4,900店の不足**（島根 42.5%・高知 46.9%）。
> 列 `src_cat` で由来を辿れる。→ [docs/master/検証_supermarket分解と分母の確定.md](docs/master/検証_supermarket分解と分母の確定.md)

加えて 2026-08-26 に **ATP 基準マスター**（119,092 店）を並行系統として追加し、
2026-08-27 に**食品営業許可・届出データの純増 20,400 店を投入**した
（`data/food_store_master_atp_permit.parquet`・**139,492 店**＝推計用の最新）。
3県の500m圏外率は 62.2% → **57.3%**、農水省公表値との相関は 0.448 → **0.462**（3県では比≤1 を維持）。

> **⚠️ 47県で測ると、この投入判断は逆転する**（2026-08-27）。1,740市区町村で測り直すと
> **比>1 が 44→102件に倍増し、相関 r は 0.305→0.271 に悪化**した。純増が都市部に偏っているため。
> 3県には大都市が仙台市しか無く副作用が見えていなかった。破れは都市部に集中し、
> **地方部1,621市区町村では比>1 は 0.9%** にとどまる。
> → [issue #46](https://github.com/shiwaku/japan-food-store-master/issues/46) / [japan-food-access-analysis#3](https://github.com/shiwaku/japan-food-access-analysis/pull/3)
許可データは CC BY 4.0・政府標準利用規約で**再配布可**。チェーン公式サイト由来の
店舗情報（All The Places ＋自前クロール、52チェーン）を土台に置き、足りない部分だけを Overture / OSM から補う。
座標の出所を「その店自身の公表値」に揃えるのが狙いで、drugstore のカバー率が 42.5% → 111.6% に改善する。
設計と検証結果は [docs/master/設計_ATP基準マスター構築.md](docs/master/設計_ATP基準マスター構築.md)。
**自前クロール分は再配布できない**ため、公開物に出すときは出力の `redistributable` 列で絞る必要がある。

## 構成

```
scripts/            # 構築パイプライン（DuckDB SQL / Python / 食品オープンデータ再現）
docs/               # 分析の一次記録（索引は docs/README.md）
  master/           #   マスターの設計・検証・ライセンス
  sources/          #   ソース比較と統計突合（OSM vs Overture / センサス）
  permits/          #   食品営業許可オープンデータ（別テーマ）
  archive/          #   古い記録・公開原稿
data/               # QGIS スタイル(.qml) 等（生データ・大容量成果物は .gitignore）
viewer/             # OSM vs Overture 食料品POI 比較ビューア（Vite + TypeScript + MapLibre GL / PMTiles）
  index.html        #   エントリ
  src/main.ts       #   アプリ本体
  public/           #   公開用 PMTiles・ベースマップスタイル・アイコン
```

## 比較ビューア

`viewer/` は、OSM と Overture Places の食料品店 POI 網羅性を地図上で目視照合する QA ツール（Vite + TypeScript）。公開先: **https://shiwaku.github.io/japan-food-store-master/**

```
cd viewer
npm ci
npm run dev      # ローカル確認
npm run build    # dist/ を生成（GitHub Actions で GitHub Pages へ自動デプロイ）
```

> ビューアは地図データの帰属を表示する: **© OpenStreetMap contributors（ODbL）** / **© Overture Maps Foundation** / 地図：国土地理院ベクトルタイル。

## データソースとライセンス

**役割**は「マスターに入る（構築）」と「入らない（検証）」の2つに分かれる。ここを取り違えないこと。

| データ | 役割 | 提供元 | ライセンス |
|---|---|---|---|
| 食料品店 POI（主） | **構築**（マスターに入る） | [Overture Places](https://docs.overturemaps.org/guides/places/) | CDLA-Permissive-2.0（Foursquare 由来分は Apache 2.0） |
| 食料品店 POI（補完） | **構築**（マスターに入る） | OpenStreetMap | **ODbL 1.0** |
| 食料品店 POI（チェーン公式） | **構築**（ATP 基準マスターの土台。公開マスターには入らない） | [All the Places](https://www.alltheplaces.xyz/) 公式ラン14本 ＋ 自前クロール38本（計52チェーン） | 公式ラン分は **CC-0**／自前クロール分は**各社規約により再配布不可**（出力の `redistributable` 列で判別） |
| 食品営業許可オープンデータ | **検証**＋**ATP基準マスターへ投入済み**（生鮮 17,243＋⑪ 3,157。公開マスターには未投入） | 各自治体（保健所）／ **厚生労働省**「食品衛生申請等システム（FAS）」 | 各データのオープンライセンス |
| 網羅性検証（実数突合） | **検証のみ**（マスターに入らない） | 経済センサス小売業（e-Stat）、JFA・SM白書・JACDS 等 | 各提供元の規約 |

> **食品営業許可オープンデータは検証用**。許可台帳であって施設マスタではなく（同一施設が業種ごとに複数行）、
> コンビニは実数の約半分しか載らない（27,615 / 約56,000）ため、位置ソースには採らなかった。
> 経緯は [docs/permits/](docs/permits/) を参照。再現パイプライン `scripts/reproduce_food_opendata/` も検証用資産。

> FAS（食品衛生申請等システム、`i2fas.mhlw.go.jp`）は営業許可・届出の全国システムで、許可データは各自治体（保健所）が入力し**厚生労働省**が運営・集約する。2024年の食品衛生行政再編で消費者庁へ移ったのは規格基準の策定（食品衛生「基準」行政）で、営業許可・届出などの「監視」行政は厚労省に残るため、本データの所管は引き続き厚労省。

### なぜ Overture Places を位置の主ソースにしたか

「位置（店舗座標）」の主ソースを Overture Places に置いた根拠は、検証に基づき以下の4点（詳細は `docs/master/設計_食料品店マスター構築.md` / `docs/sources/検証_食品店データ_OSM_vs_Overture.md`）。

1. **ライセンスと取得性** — CDLA-Permissive-2.0 で**再配布・改変・商用が自由（継承なし）**、かつ GeoParquet で**全国一括取得**できる。候補だった Yahoo!ローカルサーチ（YOLP）は規約でデータの保存・キャッシュが禁止されタイル化・再配布に使えず不可。**OSM を主ソースにすると ODbL の継承（share-alike）がマスター全体に及ぶ**ため、主を Overture にすることでライセンス上の律速を回避できる。
2. **網羅性（実測）** — 最重要カテゴリのコンビニで、Overture 単独が実数（商業動態 56,352）比 **97.6%** と悉皆に近い。Overture は4提供元（Meta/Foursquare/AllThePlaces/Microsoft）を統合しており、単一ソースの OSM よりコンビニ・ドラッグストアで網羅が広い。
3. **単一ソース優先の原則** — コンビニで Overture∪OSM を素朴に和集合すると座標ズレによる名寄せ失敗で件数が **133% に膨張**した（Overture の取りこぼしは 2.4% のみ）。→ **カテゴリごとに最網羅の単一ソースを主に据える**方針とし、最も比重の大きいコンビニ・スーパーで Overture が主になる。
4. **数量は統計で検証** — 座標は Overture から、件数の妥当性は経済センサス・商業動態統計・業界実数で裏取りする二層構成。

> **留意（Overture 万能ではない）**: スーパーは OSM の方が網羅が高く（OSM 88% / Overture supermarket 80%）、生鮮専門店・直売所も OSM 主。ドラッグストアは Overture・OSM とも実数の半分以下。このため OSM は「補完」ソースとして併用し、`grocery_store` の浄化（飲食店・雑貨の除外）とあわせてカテゴリ別に最適ソースを選ぶ設計になっている。

### Overture Places の原典データと構成比

Overture Places は財団自身が生成したデータではなく、複数の提供元を統合したもの。本データセットの Overture 抽出（日本全国・食料品店カテゴリ、confidence/重複除去前の **234,077 件**、`country = 'JP'`）における原典の構成比は以下（各レコードは単一原典 + 財団の `Overture` タグを持つ）。

| 原典データセット | 提供元 | 件数 | 構成比 | 備考 |
|---|---|---:|---:|---|
| **meta** | Meta（Facebook） | 93,125 | **39.8%** | 最大の供給元 |
| **Foursquare** | Foursquare（FSQ OS Places） | 62,960 | 26.9% | この分のライセンスは Apache 2.0 |
| **AllThePlaces** | [All the Places](https://www.alltheplaces.xyz/)（公式店舗ロケーターのスクレイプ） | 60,081 | 25.7% | 座標が正確なことが多い |
| **Microsoft** | Microsoft | 17,911 | 7.7% | |

> 集計元: `data/overture_food_full_jp.parquet` の `datasets` 配列（`Overture` タグを除外しレコード単位で算出）。このファイルは日本のバウンディングボックス抽出のため国外分（韓国 12,109・ロシア 160・中国 53・北朝鮮 1、計 12,323 件）を含む。上表は `country = 'JP'` に限定した 234,077 件が対象。同一実店舗が提供元ごとに別レコードとして残る（Overture の conflation 漏れ）ため、提供元別件数は名寄せ前の値。詳細は `docs/sources/検証_食品店データ_OSM_vs_Overture.md` を参照。

> **ライセンス注意**: OSM を混合した派生物は ODbL の継承（share-alike）対象になり得る。また Overture Places の Foursquare 由来分は Apache 2.0（帰属表示が必要）。公開・再配布の前に必ずライセンス範囲を精査すること。詳細は `docs/master/調査_食料品店マスターのライセンス.md` を参照。

## ライセンス

コードは MIT ライセンス（予定）。使用データは各提供元のライセンスに従う。
