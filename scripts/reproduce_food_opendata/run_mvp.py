"""MVP オーケストレータ: 5ソース → 正規化 → 部分統合CSV + ミニカバレッジPDF。

実行: cd プロジェクトルート && python3 scripts/reproduce_food_opendata/run_mvp.py
"""
from __future__ import annotations
import os
import sys
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from common import SCHEMA          # noqa: E402
from normalize import normalize    # noqa: E402
from sources_mvp import SOURCES     # noqa: E402
from render_pdf import render_coverage_pdf  # noqa: E402

OUT = os.path.join(HERE, "output")


def norm_key(df: pd.DataFrame) -> pd.Series:
    def clean(s):
        return (s.astype(str).str.replace(r"\s+", "", regex=True)
                 .str.replace("　", "", regex=False).str.strip())
    return clean(df["name"]) + "|" + clean(df["address"]) + "|" + clean(df["business_type"])


def main():
    frames, cov = [], []
    for src in SOURCES:
        print(f"[{src['id']}] {src['pref']}/{src['muni']} ({src['route']}) 正規化中...")
        df = normalize(src)
        df["_srcid"] = src["id"]          # 出所追跡(dedup後も残す)
        print(f"  -> {len(df):,} 行")
        frames.append(df)
        cov.append({
            "pref": src["pref"], "muni": src["muni"],
            "route": src["route"], "avail": "✅",
            "records": f"{len(df):,}", "source": src["source_name"],
            "license": src["license"], "url": src["url"],
        })

    merged = pd.concat(frames, ignore_index=True)[SCHEMA + ["_srcid"]]
    before = len(merged)

    # 名寄せ(MVP): 完全重複キーを畳み、sources / _srcid を統合
    merged["_k"] = norm_key(merged)
    agg = (merged.groupby("_k", sort=False)
                 .agg({**{c: "first" for c in SCHEMA if c not in ("sources", "licenses")},
                       "sources": lambda s: "; ".join(sorted(set(s))),
                       "licenses": lambda s: "; ".join(sorted(set(s))),
                       "_srcid": lambda s: ",".join(sorted(set(s)))}))
    dedup = agg.reset_index(drop=True)

    os.makedirs(OUT, exist_ok=True)
    csv_path = os.path.join(OUT, "facilities_mvp.csv")
    dedup[SCHEMA].to_csv(csv_path, index=False, encoding="utf-8-sig")

    print(f"\n統合前 {before:,} 行 → 名寄せ後 {len(dedup):,} 行 (重複除去 {before - len(dedup):,})")
    print(f"CSV: {csv_path}")

    # ミニカバレッジ PDF
    intro = ("MVP再現: 5ソース(自身/管轄主体/i2fas)を共通16列スキーマへ正規化し統合。"
             "各行=1ソース、availは収集可否。本番は全92ソース×1,741市区町村へ拡張予定。")
    cols = [("pref", "都道府県"), ("muni", "市区町村/範囲"), ("route", "収集経路"),
            ("avail", "データ"), ("records", "件数"), ("source", "ソース"),
            ("license", "ライセンス")]
    pdf_path = os.path.join(OUT, "coverage_mvp.pdf")
    render_coverage_pdf(cov, cols, pdf_path,
                        title="食品営業許可オープンデータ カバレッジ（MVP・5ソース）",
                        intro=intro)
    print(f"PDF: {pdf_path}")

    # 検証1: エリア別 一致度(大橋さんデータ比)。_srcid で出所を厳密集計
    #   大橋件数 = facilities-all.csv で各エリアの sources を含む行の実測値
    areas = [
        ("前橋市", {"bodik_maebashi", "fas_maebashi"}, 5370),
        ("神戸市", {"kobe", "fas_kobe"}, 29795),
        ("兵庫県所管域", {"hyogo", "fas_hyogo"}, 34529),
        ("港区", {"minato"}, None),
        ("函館市", {"fas_hakodate"}, None),
    ]
    def has_src(cell, ids):
        return bool(set(cell.split(",")) & ids)
    print("\n=== エリア別 一致度(大橋さん比) ===")
    for label, ids, ref in areas:
        mine = int(dedup["_srcid"].map(lambda c: has_src(c, ids)).sum())
        rate = f"{mine/ref*100:5.1f}%" if ref else "  ―  "
        print(f"  {label:10s} 大橋 {str(ref or '―'):>7s} / 再現 {mine:>7,d}  一致 {rate}")

    # 検証2: 列の充足率
    print("\n=== 列の充足率(非空%) ===")
    for c in SCHEMA:
        pct = (dedup[c].astype(str).str.strip().ne("").mean() * 100)
        print(f"  {c:16s} {pct:5.1f}%")


if __name__ == "__main__":
    main()
