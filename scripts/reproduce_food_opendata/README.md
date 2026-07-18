# 食品営業許可オープンデータ 再現パイプライン

大橋さんの `facilities-all.csv`（92出典統合・約145万件）とカバレッジPDFを、
抽出した92ソースURLから**再取得・再現・月次更新**できるようにするパイプライン。

現状は **MVP（縦切り5ソース）** まで実装・検証済み。横展開（全92ソース）は未着手。

## 構成

| ファイル | 役割 |
|---|---|
| `common.py` | 16列スキーマ定義／CSV(エンコーディング自動判定)・Excel読込／日付正規化(西暦・和暦・Excelシリアル) |
| `normalize.py` | ソース設定を適用し16列共通スキーマへ正規化。`colmap="_FAS_"` でFAS25列を使い回し |
| `sources_mvp.py` | MVP対象5+3ソースの取得先＋列マッピング設定 |
| `render_pdf.py` | カバレッジ表→PDF(reportlab, 日本語フォント) |
| `run_mvp.py` | オーケストレータ: 正規化→統合→名寄せ→CSV＋PDF＋一致度検証 |
| `downloads/` | 取得した生データ |
| `output/` | `facilities_mvp.csv`（16列統合）／`coverage_mvp.pdf` |

## 実行
```bash
cd <プロジェクトルート>
python3 scripts/reproduce_food_opendata/run_mvp.py
# 依存: pandas openpyxl requests chardet reportlab (pip install済)
```

## 共通スキーマ（大橋さん facilities-all.csv と同一の16列）
prefecture, city, city_raw, name, name_kana, business_type, address, lat, lng,
geocoding_level, phone, license_no, license_date, expire_date, sources, licenses

## MVPで実証した処理
- 多形式取得: 34列標準CSV(港区) / 11列CP932(神戸) / 18列Excel見出し2行目(兵庫県) / CKAN経由Excel(BODIK前橋) / FAS25列
- 日付正規化: 西暦 `2024/03/19` ・和暦 `R02/09/30` ・Excelシリアル `45212` を YYYY-MM-DD へ
- FAS層統合: 各エリアに i2fas の157ファイルを重ねて名寄せ（大橋さんと同じ設計）
- 名寄せ: 正規化(名称+住所+業態)キーで重複除去、sources を統合

## 一致度（大橋さんデータ比・MVP時点）
| エリア | 大橋 | 再現 | 一致 |
|---|---|---|---|
| 前橋市 | 5,370 | 5,440 | 101.3% |
| 神戸市 | 29,795 | 29,146 | 97.8% |
| 兵庫県所管域 | 34,529 | 33,644 | 97.4% |

残差2〜3%はスナップショット時点差＋名寄せ粒度の違い。

## 横展開（未着手・次の一手）
1. **全ソース登録簿**を `coverage_municipality_links.csv` から生成（92 distinct URL）
2. **全ソースDL**：直CSV/XLSX/TXT＋**BODIKはCKAN APIで全リソース解決（マルチリソース必須。前橋の教訓）**＋Box
3. **スキーマ自動プロファイル＆クラスタリング**：列シグネチャで~92→数十パターンに集約し colmap 使い回し
4. **lat/lng欠落ソースのジオコーディング**（geocoding_level算出）
5. 全1,741市区町村の**カバレッジ判定→本番PDF**、大橋さんデータと全体突き合わせ

### 横展開の既知の注意点
- BODIKデータセットは複数リソース（例: 前橋=「既存システム分」xlsx＋「新システム分=i2fas」）→ 全リソース取得が必要
- 兵庫県のような「管轄主体」ファイルは per-row の市区町村列が無く、住所からの抽出が必要
- 大橋さんの件数は sources 複合（FAS名寄せ込み）＝出所は `_srcid` で厳密追跡する
