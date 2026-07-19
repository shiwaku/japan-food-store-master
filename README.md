# 全国 食料品店マスター（japan-food-store-master）

農水省「食料品アクセス」の定義に準拠した、全国の食料品店 POI マスターデータセットの構築・検証・可視化リポジトリ。

`japan-mobility-ease-diagnosis`（住所を入れるだけの移動しやすさ診断）の目的地レイヤーとして使う食料品店データを、単一の再現可能なパイプラインとして分離・整備することを目的とする。

## 何を作っているか

- **食料品店マスター**（スーパー・食料品店・コンビニ・ドラッグストア等）を、Overture Places / OpenStreetMap / 食品営業許可オープンデータ等から統合構築
- 網羅性を **経済センサス小売業（e-Stat）** および **業界実数**（JFA・スーパーマーケット白書・JACDS 等）と突合して検証
- カテゴリマッピング・confidence フィルタ・重複除去の前処理を実装

現状: Phase1 構築済み（約 103,230 店 / 農水省加重ベースの実質カバー率 93.5%）。

## 構成

```
scripts/     # 構築パイプライン（DuckDB SQL / Python / 食品オープンデータ再現）
docs/        # 網羅性検証・データ設計・ライセンス調査
data/        # QGIS スタイル(.qml) 等（生データ・大容量成果物は .gitignore）
compare.html # OSM vs Overture 食料品POI 比較ビューア（MapLibre GL + PMTiles）
src/         # 比較ビューアのソース
public/      # 公開用 PMTiles・ベースマップスタイル
```

## 比較ビューア

`compare.html` は、OSM と Overture Places の食料品店 POI 網羅性を地図上で目視照合する QA ツール。

```
npm ci
npm run dev      # ローカル確認
npm run build    # dist/ を生成（GitHub Pages 公開）
```

## データソースとライセンス

| データ | 提供元 | ライセンス |
|---|---|---|
| 食料品店 POI（主） | [Overture Places](https://docs.overturemaps.org/guides/places/) | CDLA-Permissive-2.0（Foursquare 由来分は Apache 2.0） |
| 食料品店 POI（補完） | OpenStreetMap | **ODbL 1.0** |
| 食品営業許可オープンデータ | 各自治体 / FAS（食品衛生申請等システム） | 各データのオープンライセンス |
| 網羅性検証（実数突合） | 経済センサス小売業（e-Stat）、JFA・SM白書・JACDS 等 | 各提供元の規約 |

### なぜ Overture Places を位置の主ソースにしたか

「位置（店舗座標）」の主ソースを Overture Places に置いた根拠は、検証に基づき以下の4点（詳細は `docs/設計_食料品店マスター構築.md` / `docs/検証_食品店データ_OSM_vs_Overture.md`）。

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

> 集計元: `data/overture_food_full_jp.parquet` の `datasets` 配列（`Overture` タグを除外しレコード単位で算出）。このファイルは日本のバウンディングボックス抽出のため国外分（韓国 12,109・ロシア 160・中国 53・北朝鮮 1、計 12,323 件）を含む。上表は `country = 'JP'` に限定した 234,077 件が対象。同一実店舗が提供元ごとに別レコードとして残る（Overture の conflation 漏れ）ため、提供元別件数は名寄せ前の値。詳細は `docs/検証_食品店データ_OSM_vs_Overture.md` を参照。

> **ライセンス注意**: OSM を混合した派生物は ODbL の継承（share-alike）対象になり得る。また Overture Places の Foursquare 由来分は Apache 2.0（帰属表示が必要）。公開・再配布の前に必ずライセンス範囲を精査すること。詳細は `docs/調査_食料品店マスターのライセンス.md` を参照。

## ライセンス

コードは MIT ライセンス（予定）。使用データは各提供元のライセンスに従う。
