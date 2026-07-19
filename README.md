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
| 食料品店 POI（主） | [Overture Places](https://docs.overturemaps.org/guides/places/) | CDLA-Permissive-2.0 |
| 食料品店 POI（補完） | OpenStreetMap | **ODbL 1.0** |
| 食品営業許可オープンデータ | 各自治体 / FAS（食品衛生申請等システム） | 各データのオープンライセンス |
| 網羅性検証（実数突合） | 経済センサス小売業（e-Stat）、JFA・SM白書・JACDS 等 | 各提供元の規約 |

> **ライセンス注意**: OSM を混合した派生物は ODbL の継承（share-alike）対象になり得る。公開・再配布の前に必ずライセンス範囲を精査すること。詳細は `docs/` のライセンス調査を参照。

## ライセンス

コードは MIT ライセンス（予定）。使用データは各提供元のライセンスに従う。
