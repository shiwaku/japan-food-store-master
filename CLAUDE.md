# CLAUDE.md — japan-food-store-master

このリポジトリで作業するときの前提・手順・落とし穴をまとめる。次回はまずこれを読むこと。

## このリポジトリは何か

農水省「[食料品アクセス](https://www.maff.go.jp/j/shokusan/eat/access_genjo.html)」（食料品アクセス困難人口の推計）の定義に準拠した、**全国の食料品店 POI マスターデータセット**の構築・検証・可視化リポジトリ。

- 姉妹リポジトリ `japan-mobility-ease-diagnosis`（住所を入れるだけの移動しやすさ診断）の**目的地レイヤー**として使う食料品店データを、再現可能なパイプラインとして分離・整備するのが目的。
- 2026-07-19 に `japan-mobility-ease-diagnosis` から履歴ごと分離して発足（分離前の履歴は両repo共通）。

## リポジトリ構成

```
scripts/     構築パイプライン（DuckDB SQL / Python / 食品オープンデータ再現）
docs/        網羅性検証・データ設計・ライセンス調査（分析の一次記録。まずここを読む）
data/        成果物・中間データ（大容量・生データは .gitignore。qml のみ追跡）
viewer/      OSM vs Overture 比較ビューア（Vite + TypeScript + MapLibre GL / PMTiles）
  index.html   エントリ
  src/main.ts  アプリ本体
  public/      公開用 PMTiles・ベースマップスタイル(pale.json)・アイコン
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

- **Phase1 マスター構築済み**: 約 103,230 店 / 農水省加重ベースの実質カバー率 93.5%。
- マスター実体: `data/food_store_master.csv` / `.parquet`（列 `cat`, `name` 等）。カテゴリ別件数:
  `convenience 54,793 / supermarket 30,638 / fresh_food 10,070 / drugstore 7,729`。
- 次の一手候補: 地方 supermarket の OSM 補完、道の駅の追加検討（`docs/検討_道の駅の追加可否.md`、現状は見送り）。

## データソースと役割

| ソース | 役割 | ライセンス |
|---|---|---|
| Overture Places | **位置の主ソース**（コンビニ・スーパー等） | CDLA-Permissive-2.0（Foursquare 由来分は Apache 2.0） |
| OpenStreetMap | 位置の**補完**（生鮮・GMS 等）・比較対象 | **ODbL 1.0（継承あり）** |
| 食品営業許可オープンデータ | クロス検証の一材料 | 各自治体（保健所）／**厚生労働省** FAS |
| 経済センサス・商業動態統計（e-Stat） | 数量検証・カテゴリ別カバー率 | 政府標準利用規約 |
| 業界実数（JFA・SM白書・JACDS 等） | 全国実数のクロスチェック | 各提供元 |

- Overture を主にした理由・網羅性検証の数値・原典構成比（Meta 39.8% ほか）は README と `docs/設計_食料品店マスター構築.md` / `docs/検証_食品店データ_OSM_vs_Overture.md` 参照。

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
- カテゴリ絞り込みで上部の件数が連動する。**件数は `viewer/src/main.ts` の `COUNTS` にハードコード**（pmtiles は tippecanoe の間引きで実行時カウント不可のため）。pmtiles を再生成したら `scripts/compare_sources_by_category.sql` で件数を出し直して `COUNTS` を更新すること。

## 落とし穴・環境メモ

- **DuckDB spheroid バグ**: この環境では `ST_Distance_Spheroid` / `ST_DWithin_Spheroid` が `-nan` を返して使えない。距離は等距円筒近似（緯度補正した平面距離）で代替する。
- **Overture の bbox 抽出は国外を含む**: `data/overture_food_full_jp.parquet`（246,400 件）は日本の bbox 抽出で韓国・ロシア等を含む。日本のみは `country = 'JP'`（234,077 件）で絞る。
- **pmtiles は低ズームで点が間引かれる**（`--drop-densest-as-needed`）。地図上の描画数＝実データ件数ではない。
- DuckDB CLI: `/home/shi-works/.duckdb/cli/latest/duckdb`。

## 再現の要点

- Overture 比較用 pmtiles 再生成: `bash scripts/build_pmtiles.sh`（`data/overture_food_deduped_jp.parquet` → `viewer/public/overture_food.pmtiles`、tippecanoe 必要）。
- カテゴリ別件数の集計: `duckdb -c ".read scripts/compare_sources_by_category.sql"`。
- 食品オープンデータ再現 MVP: `scripts/reproduce_food_opendata/`（Python、92 出典 → 統合。README 参照）。
