#!/usr/bin/env python3
"""食品営業許可・届出の生鮮3業種から、マスターに無い青果・鮮魚・精肉店を拾う。

CLAUDE.md「次の一手」2番（fresh_food の補完）の実装。**マスターは書き換えない**。
路線の選定理由は docs/sources/調査_freshfood補完ソース.md
（農水省本家の生鮮レイヤーは電話帳データ製だが有償・再配布不可。許可・届出データが
無償・再配布可で唯一公開マスターと両立する候補）。

対象業種: 魚介類販売業 / 食肉販売業 / 野菜果物販売業（製造・処理・競り売りは除く）。
実測 92,074行・施設 71,254件で、センサス 582/583/584 計 33,960 の**2倍以上ある**。
つまり課題は収集ではなくフィルタリング:

 1. 名称フィルタ（`fresh_excluded_sql()`）— 飲食店・卸・市場・加工場・移動販売・
    事業所内・ドラッグストア。**飲食店を落とすのが最重要**（焼肉・寿司店が生鮮の
    許可を取っているため、放置すると全国に偽の食料品店が湧いて500mメッシュ指標が過小に出る）
 2. チェーン売場フィルタ — スーパー／コンビニの鮮魚・精肉コーナーの届出を、
    「同じブランドキーの店がマスターに全国3件以上ある」で落とす（チェーン名は列挙し切れない）
 3. マスターとの突合（100m一致＋同ブランド500m一致）— 既存店の売場・重複を落とす

環境変数:
  FOOD_MASTER     突合するマスター（既定 data/food_store_master.parquet）
  INCLUDE_PACKAGED  1 なら「包装済みのみ」の届出も含める（既定は許可＝未包装のみ）
  MIN_LEVEL       ジオコーディング精度の足切り。既定 3（元座標＝空欄は常に通す）
  OUT_PARQUET / OUT_CSV / RADIUS_M
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import permit_gapfill  # noqa: E402
from food_store_rules import FRESH_TYPE_SQL, fresh_excluded_sql  # noqa: E402

type_sql = FRESH_TYPE_SQL
label = "生鮮3業種（魚介類・食肉・野菜果物 販売業）"
if os.environ.get("INCLUDE_PACKAGED", "0") != "1":
    # 「包装済みのみ」は届出業種で捕捉が薄く、かつスーパーの売場が中心。既定では落とす。
    type_sql += " and not coalesce(business_type ilike '%包装済%', false)"
    label += "・未包装（許可）のみ"

min_level = int(os.environ.get("MIN_LEVEL", "3"))
# 空欄は「自治体が公表した元座標」なので常に通す。数値が入っているのはジオコーディング補完分。
# 施設単位に畳んだあとの列名は glv（permit_gapfill 側の命名）。
level_sql = ("glv is null or trim(glv) = '' or try_cast(glv as int) >= {n}".format(n=min_level))

permit_gapfill.run(
    label=label,
    type_sql=type_sql,
    exclude_sql=fresh_excluded_sql("name"),
    master=os.environ.get("FOOD_MASTER", "data/food_store_master.parquet"),
    out_parquet=os.environ.get(
        "OUT_PARQUET", "data/permit_fresh_food_candidates.parquet"),
    out_csv=os.environ.get(
        "OUT_CSV", "docs/sources/検証_許可データ_生鮮3業種_都道府県別.csv"),
    radius_m=float(os.environ.get("RADIUS_M", "100")),
    stats_cat="fresh_food",
    level_sql=level_sql,
    chain_filter=True,
)
