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

### Overture Places の原典データと構成比

Overture Places は財団自身が生成したデータではなく、複数の提供元を統合したもの。本データセットの Overture 抽出（全国・食料品店カテゴリ、confidence/重複除去前の 246,400 件）における原典の構成比は以下（各レコードは単一原典 + 財団の `Overture` タグを持つ）。

| 原典データセット | 提供元 | 件数 | 構成比 | 備考 |
|---|---|---:|---:|---|
| **meta** | Meta（Facebook） | 101,763 | **41.3%** | 最大の供給元 |
| **Foursquare** | Foursquare（FSQ OS Places） | 66,272 | 26.9% | この分のライセンスは Apache 2.0 |
| **AllThePlaces** | [All the Places](https://www.alltheplaces.xyz/)（公式店舗ロケーターのスクレイプ） | 60,085 | 24.4% | 座標が正確なことが多い |
| **Microsoft** | Microsoft | 18,280 | 7.4% | |

> 集計元: `data/overture_food_full_jp.parquet` の `datasets` 配列（`Overture` タグを除外しレコード単位で算出）。同一実店舗が提供元ごとに別レコードとして残る（Overture の conflation 漏れ）ため、提供元別件数は名寄せ前の値。詳細は `docs/検証_食品店データ_OSM_vs_Overture.md` を参照。

> **ライセンス注意**: OSM を混合した派生物は ODbL の継承（share-alike）対象になり得る。また Overture Places の Foursquare 由来分は Apache 2.0（帰属表示が必要）。公開・再配布の前に必ずライセンス範囲を精査すること。詳細は `docs/調査_食料品店マスターのライセンス.md` を参照。

## ライセンス

コードは MIT ライセンス（予定）。使用データは各提供元のライセンスに従う。
