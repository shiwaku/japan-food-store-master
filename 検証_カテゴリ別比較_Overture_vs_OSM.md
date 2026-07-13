# 検証: カテゴリ別 件数比較 Overture Maps（名寄せ済） vs OpenStreetMap

**作成**: 2026年7月13日
**目的**: 食料品店POIの2ソース（Overture Places・OpenStreetMap）を、**同一のカテゴリバケットに揃えて件数を突合**し、どのカテゴリでどちらが手厚いかを定量把握する。
**対象範囲**: **農林水産省「食料品アクセス」定義準拠**（調剤薬局・100均/ディスカウント・百貨店は両ソースとも除外）。
**前提**: Overtureは**クロス提供元名寄せ済み**（コンビニ大手5チェーンを単一提供元方式で重複除去、171,180→109,602件）。名寄せの詳細は [検証_食品店データ_OSM_vs_Overture.md](検証_食品店データ_OSM_vs_Overture.md) セクション3-1/3-2 参照。
**再現**: `scripts/compare_sources_by_category.sql`（DuckDB）。

---

## 1. カテゴリ別 件数比較

| カテゴリ | Overture（名寄せ済） | OpenStreetMap | 差（Ovt−OSM） |
|---|---:|---:|---:|
| スーパー | 18,521 | **20,348** | −1,827 |
| コンビニ | **54,987** | 48,676 | +6,311 |
| ドラッグストア | **7,735** | 4,554 | +3,181 |
| 食料品店（grocery） | 20,608 | 275 | +20,333 ⚠️ |
| 生鮮専門店・直売所 | 7,751 | 7,527 | +224 |
| **合計** | **109,602** | **81,380** | +28,222 |

※OSM合計（定義準拠）81,380件は生111,186件から非食料品タグを除外したもの。[検証_食品店データ_OSM_vs_Overture.md](検証_食品店データ_OSM_vs_Overture.md) の81,363件とは軽微カテゴリの取り方で±17件の差。

## 2. カテゴリバケットの対応

| バケット | Overture `category` | OSM `shop` / `amenity` |
|---|---|---|
| スーパー | `supermarket` | `shop=supermarket` |
| コンビニ | `convenience_store` | `shop=convenience` |
| ドラッグストア | `drugstore` | `shop=chemist/drugstore/cosmetics 等` |
| 食料品店 | `grocery_store` | `shop=grocery/food/general/deli/confectionery` |
| 生鮮専門店・直売所 | `butcher_shop`・`farmers_market`・`seafood_market` | `shop=greengrocer/seafood/butcher/farm`・`amenity=marketplace` |

**両ソースで除外（非食料品）**: 調剤薬局（`amenity=pharmacy`）、100均/雑貨（`discount_store`・`variety_store`）、百貨店（`department_store`）、その他非食料品タグ。

## 3. 読み取り

- **スーパー**: OSMの方が多い（+1,827）。日本の主要スーパーはOSMのマッピングが手厚く、Overtureはやや取りこぼす。診断アプリの主目的地であり、この差は要注意。
- **コンビニ**: 名寄せ後でもOvertureが多い（54,987 vs 48,676）。Overtureは提供元4社（Foursquare/meta/AllThePlaces/Microsoft）を統合しており、単一ソースのOSMより網羅が広い。Overtureのコンビニ54,987件は実店舗数（約56,000）とよく整合。
- **ドラッグストア**: Overtureが多い（+3,181）。OSMは日本のドラッグストアのタグ付けが薄い。
- **生鮮専門店・直売所**: ほぼ互角（+224）。青果・精肉・鮮魚・直売所は両ソースとも同水準。
- **⚠️ 食料品店（grocery）は直接比較不能**: 20,608 vs 275 は実際の網羅差ではなく **タグ体系の違い**。OSM日本では `shop=grocery` がほとんど使われず（個人商店は別タグ or 未マッピング）、Overtureの `grocery_store` が受け皿カテゴリとして機能しているため。カテゴリ境界がソース間でずれる典型例で、この行だけを取り出して優劣を論じるのは不可。

## 4. 結論

- **カテゴリで優劣が入れ替わる**。スーパーはOSM有利、コンビニ・ドラッグストアはOverture有利。「どちらが網羅的か」はカテゴリ依存で、単一ソースでの一元化は一長一短。
- **grocery のタグ体系差**により、カテゴリ単位の単純比較には限界がある。実質比較には両ソースのカテゴリを横断した空間突合（100m一致など、[検証_食品店データ_OSM_vs_Overture.md](検証_食品店データ_OSM_vs_Overture.md) セクション1〜2の手法）が必要。
- 診断アプリの主目的地である**スーパーでOSMが上回る**点は、Overture単独運用時の取りこぼしリスクとして留意（マージ or OSM補完の検討材料）。

## 5. 残課題

- [ ] grocery のタグ体系差を吸収した「食料品店の実質比較」（カテゴリ横断の空間突合）
- [ ] スーパーのソース間差（OSM+1,827）の内訳を、チェーン別・地方/都市別に分解
- [ ] 両ソースのマージ時の重複除去（クロスソース名寄せ）の設計

---

*関連: [検証_食品店データ_OSM_vs_Overture.md](検証_食品店データ_OSM_vs_Overture.md)（網羅性比較・名寄せ） / [データ定義と抽出方法_食品店POI.md](データ定義と抽出方法_食品店POI.md)*
*分析: DuckDB / `scripts/compare_sources_by_category.sql`*
