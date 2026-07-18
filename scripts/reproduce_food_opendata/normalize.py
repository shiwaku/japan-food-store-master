"""ソース設定を適用して 16列共通スキーマの DataFrame を返す。"""
from __future__ import annotations
import pandas as pd
from common import SCHEMA, read_csv_any, read_excel_any, normalize_date

_DATE_FIELDS = {"license_date", "expire_date"}

# FAS(i2fas) 25列共通マッピング。sources_mvp で colmap="_FAS_" と書けば使い回せる
_FAS_COLMAP = {
    "prefecture": "都道府県名", "city": "市区町村名",
    "name": "営業施設名称、屋号又は商号",
    "name_kana": "営業施設名称、屋号又は商号（フリガナ）",
    "business_type": "営業の種類", "lat": "緯度", "lng": "経度",
    "phone": "営業施設電話番号", "license_no": "許可番号",
    "license_date": "許可年月日", "expire_date": "許可満了日",
}


def load_raw(src: dict) -> pd.DataFrame:
    fmt = src["format"]
    if fmt in ("csv", "fas"):
        return read_csv_any(src["path"], encoding=src.get("encoding"),
                            header_row=src.get("header_row", 0))
    if fmt == "excel":
        return read_excel_any(src["path"], header_row=src.get("header_row", 0),
                             sheet=src.get("sheet", 0))
    raise ValueError(f"unknown format: {fmt}")


def normalize(src: dict) -> pd.DataFrame:
    raw = load_raw(src)
    raw.columns = [str(c).strip() for c in raw.columns]
    n = len(raw)
    out = pd.DataFrame({c: [""] * n for c in SCHEMA})

    # 列マッピング(colmap="_FAS_" は共通FASマッピングへ展開)
    colmap = src.get("colmap", {})
    if colmap == "_FAS_":
        colmap = _FAS_COLMAP
    for tgt, col in colmap.items():
        if col in raw.columns:
            out[tgt] = raw[col].astype(str).str.strip()
        else:
            print(f"  [warn] {src['id']}: 列 '{col}' が見つからない (→ {tgt} 空欄)")

    # 住所の結合
    parts = [p for p in src.get("address_parts", []) if p in raw.columns]
    if parts:
        out["address"] = (raw[parts].astype(str)
                          .apply(lambda r: " ".join(x.strip() for x in r if x.strip()), axis=1))

    # 定数(ソースに列が無い項目)
    for k, v in src.get("const", {}).items():
        out[k] = v

    # city_raw 未設定なら city を流用
    empty_raw = out["city_raw"].eq("")
    out.loc[empty_raw, "city_raw"] = out.loc[empty_raw, "city"]

    # 日付正規化
    for f in _DATE_FIELDS:
        out[f] = out[f].map(normalize_date)

    # geocoding_level: 緯度経度がソースに有れば 'source'、無ければ空(要ジオコーディング)
    has_ll = out["lat"].astype(str).str.strip().ne("") & out["lng"].astype(str).str.strip().ne("")
    out["geocoding_level"] = has_ll.map(lambda b: "source" if b else "")

    # provenance
    out["sources"] = src["source_name"]
    out["licenses"] = src["license"]

    # 空行(施設名も住所も無い)は除外
    keep = out["name"].str.strip().ne("") | out["address"].str.strip().ne("")
    out = out[keep].reset_index(drop=True)
    return out
