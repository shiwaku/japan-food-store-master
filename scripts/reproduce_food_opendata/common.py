"""共通ユーティリティ: 16列スキーマ定義・多様な入力の読み込み・日付正規化。

大橋さんの facilities-all.csv と同じ 16 列スキーマへ各オープンデータを寄せる。
"""
from __future__ import annotations
import io
import re
import datetime as _dt
import pandas as pd

# 大橋さんの facilities-all.csv と同一の 16 列
SCHEMA = [
    "prefecture", "city", "city_raw", "name", "name_kana", "business_type",
    "address", "lat", "lng", "geocoding_level", "phone", "license_no",
    "license_date", "expire_date", "sources", "licenses",
]

# 和暦の元号 → 開始西暦(元年=その年)
_ERA = {"M": 1867, "T": 1911, "S": 1925, "H": 1988, "R": 2018,
        "明治": 1867, "大正": 1911, "昭和": 1925, "平成": 1988, "令和": 2018}


def read_csv_any(path: str, encoding: str | None = None, header_row: int = 0) -> pd.DataFrame:
    """エンコーディング自動判定つき CSV 読込。encoding 指定時はそれを優先。"""
    raw = open(path, "rb").read()
    if encoding is None:
        # BOM 判定 → chardet フォールバック
        if raw[:3] == b"\xef\xbb\xbf":
            encoding = "utf-8-sig"
        else:
            try:
                import chardet
                enc = chardet.detect(raw[:100000]).get("encoding") or "utf-8"
                # 日本語系は CP932 に寄せると安定
                encoding = "cp932" if enc and enc.lower().replace("-", "") in (
                    "shiftjis", "sjis", "windows1252", "cp932") else enc
            except Exception:
                encoding = "utf-8"
    text = raw.decode(encoding, errors="replace")
    return pd.read_csv(io.StringIO(text), header=header_row, dtype=str,
                       keep_default_na=False, engine="python").fillna("")


def read_excel_any(path: str, header_row: int = 0, sheet=0) -> pd.DataFrame:
    """Excel 読込。header_row は 0 始まり(タイトル行がある場合に指定)。"""
    df = pd.read_excel(path, sheet_name=sheet, header=header_row, dtype=str, engine="openpyxl")
    return df.fillna("").astype(str).replace("nan", "")


def normalize_date(v) -> str:
    """西暦・和暦・Excel日付を YYYY-MM-DD に正規化。不明は空文字。"""
    if v is None:
        return ""
    s = str(v).strip()
    if not s or s.lower() in ("nan", "none", "-", "—"):
        return ""
    # Excel が datetime を返す場合
    if isinstance(v, (_dt.datetime, _dt.date)):
        return v.strftime("%Y-%m-%d")
    s = s.split(" ")[0]
    # Excel シリアル値(1899-12-30 起点)。日付列で 20000〜60000 の整数のみ対象
    if re.fullmatch(r"\d{4,5}", s):
        n = int(s)
        if 20000 <= n <= 60000:
            return (_dt.date(1899, 12, 30) + _dt.timedelta(days=n)).strftime("%Y-%m-%d")
    # 西暦 YYYY/MM/DD or YYYY-MM-DD
    m = re.match(r"^(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})$", s)
    if m:
        y, mo, d = map(int, m.groups())
        return _fmt(y, mo, d)
    # 和暦記号 R02/09/30, H8.6.12, 令和2年9月30日
    m = re.match(r"^([MTSHR明大昭平令][^\d]*)?(\d{1,2})[/\-.年](\d{1,2})[/\-.月](\d{1,2})日?$", s)
    if m and m.group(1):
        era = m.group(1)
        key = era[0] if era[0] in "MTSHR" else era[:2]
        base = _ERA.get(key)
        if base:
            y = base + int(m.group(2))
            return _fmt(y, int(m.group(3)), int(m.group(4)))
    return ""  # 不明形式は空(要調査)


def _fmt(y: int, mo: int, d: int) -> str:
    try:
        return _dt.date(y, mo, d).strftime("%Y-%m-%d")
    except ValueError:
        return ""
