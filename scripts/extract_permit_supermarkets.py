#!/usr/bin/env python3
"""食品営業届出の「⑪ 百貨店、総合スーパー」から、マスターに無いスーパーを拾う（issue #26）。

**このスクリプトはマスターを書き換えない**（読むだけ）。採否の材料を出すのが役目。
ATP（チェーン公式サイトのクロール）は supermarket 46.6% で頭打ちで、残っているのは
地場スーパー・JA の生活センターなど公式サイトが無い層。届出データはその層を含む。

入力: data/facilities-all.csv（japan-facilities-address の統合出力。1,437,799行）
      data/food_store_master.parquet（FOOD_MASTER で差し替え可）
出力: data/permit_supermarket_candidates.parquet（判定フラグ付きの全候補）
      docs/sources/検証_許可データ_総合スーパー_都道府県別.csv

結果の解釈は docs/sources/検証_許可データ_総合スーパー_補完効果.md。

注意点:
 - **区分番号は衝突する**。「⑪」は許可業種の「⑪ 菓子製造業」(37,032行)にも使われる。
   区分名まで含めた完全一致で抽出すること。
 - **⑪ 行に license_date / expire_date は無い**（届出には許可期限が無く、全件空）。
   したがって**廃業の除外はこのデータでは不可能**。閉店が混じる方向の偽陽性が残る。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import permit_gapfill  # noqa: E402
from food_store_rules import permit_excluded_sql  # noqa: E402

BUSINESS_TYPE = "⑪ 百貨店、総合スーパー"

permit_gapfill.run(
    label="⑪『" + BUSINESS_TYPE + "』",
    type_sql="business_type = '" + BUSINESS_TYPE + "'",
    exclude_sql=permit_excluded_sql("name"),
    master=os.environ.get("FOOD_MASTER", "data/food_store_master.parquet"),
    out_parquet=os.environ.get(
        "OUT_PARQUET", "data/permit_supermarket_candidates.parquet"),
    out_csv=os.environ.get(
        "OUT_CSV", "docs/sources/検証_許可データ_総合スーパー_都道府県別.csv"),
    radius_m=float(os.environ.get("RADIUS_M", "100")),
    stats_cat="supermarket",
)
