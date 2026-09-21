# 検証: 公開できる店舗マスターを Overture ＋ OSM ＋ 食品営業許可オープンデータで組む（2026-09-21）

**結論: 組める。ATP 基準マスターとほぼ同等。**
しかも **OSM を外しても落ちない**ので、ODbL の継承を避けた全行再配布可のレイヤが作れる。

| レイヤ | 店舗数 | 地方部 r | 地方部 圏外率 | 地方部 比>1 | ATP再現率 | 公開 |
|---|---:|---:|---:|---:|---:|---|
| ATP基準＋許可⑪（現行・推計用） | 122,249 | 0.2472 | 56.32% | 21 | （自明100%） | **不可** |
| Overture＋OSM＋許可 | 130,345 | 0.2440 | 55.70% | 20 | 80.4% | ODbL継承あり |
| **Overture＋許可（ODbL無し）** | **124,970** | **0.2490** | **56.50%** | **19** | **80.4%** | **可** |
| Phase1（Overture＋OSM・許可なし） | 102,984 | 0.2370 | 60.20% | 7 | 67.4% | ODbL継承あり |
| 許可データ単独 | 97,762 | 0.2144 | 66.89% | 12 | — | 可 |

判定は [japan-food-access-analysis](https://github.com/shiwaku/japan-food-access-analysis) の
`04_road_distance.py`（道路距離 m）→ `02_validate_access_difficulty.py`、47県・1,740市区町村。
地方部＝高齢者密度 <1,500人/km²（可住地ベース・店舗レイヤに依存しない区分）の1,586市区町村。

## 1. なぜ組み直すのか

ATP 基準マスターは 47県・地方部の実測で最良だが、**自前クロール38チェーン 47,005店（38%）が
再配布不可**（`調査_自前クロールソースの利用規約と再配布可否.md`。再配布を明示的に許諾する社はゼロ）。
**推計に使うだけなら制約は無い**が、地図タイルや診断サービスのような**公開物には載せられない**。
外すと convenience −26,458 / drugstore −11,488 / supermarket −9,058 の穴が空く。

## 2. 許可データの cat は業種コードで振ってはいけない

`build_jff_only_master.py` の設計。詳細は `検証_JFF単独レイヤ_店舗レイヤ適性.md`。

| 測り方 | 大手コンビニ3社の網羅率 |
|---|---:|
| `⑩ コンビニエンスストア` だけで拾う | 28.5% |
| 業種を無視して**店名でチェーン照合** | **66.7%** |

コンビニは店内調理があるため `① 飲食店営業` で届け出ているのが普通。
`⑪ 百貨店、総合スーパー` も受け皿区分で supermarket 49.9% / drugstore 34.1% の混在。

## 3. 構成（`scripts/build_public_master.py`）

| 層 | ソース | 件数 | ライセンス |
|---|---|---:|---|
| 土台 | Phase1 マスター（Overture 主・OSM 補完） | 102,984 | CDLA-Permissive-2.0 / ODbL-1.0 |
| 補完 | 食品営業許可オープンデータ（純増のみ） | 27,361 | CC BY 系 / 公共データ利用規約 |

突合は「同カテゴリ 100m 以内」＋「同ブランド 500m 以内」（座標ズレ対策。permit_gapfill と同じ）。

**許可データからの純増の内訳**: drugstore 11,760 / convenience 8,649 / supermarket 6,952。
生鮮は既定で入れない（47県・地方部で悪化することが issue #46 で実測済み）。

### 店舗ごとに出所が追える

公開時の出典表示に必要なので、行単位で持たせている。

| 列 | 中身 |
|---|---|
| `src` | `overture` / `osm` / `permit` |
| `src_cat` | Overture の category / OSM の shop タグ（土台のみ） |
| `business_type` | 届出・許可の業種（許可のみ・複数は `\|` 連結） |
| `sources` | 元データの公開元（例「大阪市食品営業許可施設一覧」） |
| `licenses` | 元データのライセンス（例「CC BY 4.0」） |
| `license` | 行単位のライセンス |
| `attribution` | 出典表示の文字列 |

ライセンス別の件数（Overture＋OSM＋許可版）:

| license | 件数 |
|---|---:|
| CDLA-Permissive-2.0（Overture） | 97,600 |
| 公共データ利用規約 第1.0版 PDL1.0（厚労省 FAS） | 25,832 |
| ODbL-1.0（OSM） | 5,384 |
| CC BY 4.0 ほか自治体の個別ライセンス | 約1,500 |

## 4. ATP を正解データにした突合（`scripts/eval_master_against_atp.py`）

ATP は**公開マスターには入れられない**が、**分析・検証に使うことに制約は無い**。
チェーン店については各社の公表値そのものなので、**網羅性の基準として最も確からしい**。

ATP の1店ごとに、同カテゴリの店舗が 100m 以内にあるかで再現率を測る。

| レイヤ | 全体 | convenience | drugstore | supermarket |
|---|---:|---:|---:|---:|
| Phase1（Overture＋OSM） | 67.4% | 78.1% | **34.1%** | 69.5% |
| **＋許可データ** | **80.4%** | **81.7%** | **75.3%** | **82.6%** |

**許可データの寄与はドラッグストアで決定的**（34.1% → 75.3%）。
位置ずれ（当たった組の距離）の中央値は convenience 3.3m / drugstore 10.9m / supermarket 16.3m。

> ⚠ ATP基準マスターの再現率が100%になるのは **ATP を内包しているので自明**。
> 意味があるのは Phase1 と公開可能版の比較。
> また ATP は supermarket が実数の46.6%・fresh_food が0なので、
> **この再現率はチェーン店の網羅率**であって独立店の網羅性は測れない。

県別では 沖縄71.7% 〜 富山86.3%。Phase1 からの伸びは富山 +25.3pt・石川 +21.8pt・京都 +20.3pt が大きく、
青森 +3.7pt・沖縄 +5.5pt が小さい（許可データの収録が薄い県）。
→ `検証_公開可能マスター_ATP突合_都道府県別.csv`

## 5. OSM を外してよい

OSM 由来は **fresh_food 5,384件だけ**（Phase1 の構成上、Overture が conv/super/drug を、
OSM が生鮮を埋めている）。外すと fresh_food は 10,070 → 4,686 に減るが、
**47県・地方部の指標はむしろ良くなる**（r 0.2440 → 0.2490、比>1 20 → 19件）。
圏外率は 55.70% → 56.50% と 0.8pt 上がる。

→ **ODbL の継承を避けたいなら Overture＋許可で組めばよい**（`OSM=0`）。
公開物の帰属表示は CDLA-Permissive-2.0（Overture）と各自治体・厚労省のライセンスだけで済む。

## 6. 失敗した組み方（記録）

**ATP基準マスターから再配布可の行だけ抜いて許可データを足す**のは筋が悪い（r 0.212）。
ATP 基準マスターは ATP を土台に Overture/OSM で穴を埋める設計なので、
自前クロールを抜くと土台に穴が空いたレイヤになり、Overture が主の Phase1 から組むより悪くなる。
**土台は Phase1（Overture 主）に戻すこと。**

## 7. 残る限界

- **廃業が落とせない**。許可データの届出行には `license_date` / `expire_date` が無い。
  偽陽性（閉店店舗）は圏外率を過小にする方向に残る。
- **許可データの収録は県で厚みが違う**（総レコード数で島根1,052 〜 東京149,727）。
  ATP再現率の県別の幅（71.7〜86.3%）はこれを反映している。
- **都市部では農水省の公表値を再現できない**のは店舗レイヤの問題ではない
  （確率版との構造差。japan-food-access-analysis issue #4）。

## 8. 再現

```bash
curl -sSL -o data/facilities-all.csv https://food.japan-facilities.com/api/facilities-all.csv
python scripts/build_jff_only_master.py        # 許可データに cat を振る
python scripts/build_public_master.py          # → data/food_store_master_public.parquet
OSM=0 OUT_PARQUET=data/food_store_master_public_noosm.parquet \
    python scripts/build_public_master.py      # ODbL 無し版
python scripts/eval_master_against_atp.py      # ATP を正解にした突合

cd ../japan-food-access-analysis
cp ../japan-food-store-master/data/food_store_master_public_noosm.parquet input/
FOOD_STORES=input/food_store_master_public_noosm.parquet \
    OUT_ROAD=data/mesh_road_dist_noosm.parquet python scripts/04_road_distance.py
ROAD_DIST=data/mesh_road_dist_noosm.parquet OUT_SUFFIX=_Overture_許可_47県 WRITE_MESH=0 \
    python scripts/02_validate_access_difficulty.py <47県>
```
