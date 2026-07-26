#!/usr/bin/env python3
"""
国勢調査2020 500mメッシュ 人口（総数・65歳以上）を取得する。

農水省「食料品アクセス困難人口」は 500mメッシュ人口 × 最近隣店舗距離500m で定義される。
その検証に使うメッシュ人口を e-Stat 統計GIS から取得する（**appId 不要**のダウンロードAPI）。

  https://www.e-stat.go.jp/gis/statmap-search/data
    ?dlserveyId=A002006212020 & statsId=T001141 & code=<1次メッシュ> & format=csv & downloadType=2

統計表 T001141（男女別人口・年齢別人口・世帯数, 500mメッシュ）の使用列:
  T001141001 = 人口（総数）
  T001141019 = 65歳以上人口 総数   ← 農水省の困難人口（65歳以上）に対応
  T001141022 = 75歳以上人口 総数   ← 農水省 表5 の 75歳以上 と突合する用
列番号は「総数・男・女」の3列組が並ぶ構造から数える（001-003 総数, 004-006 0-14歳,
007-009 15歳以上, 010-012 15-64歳, 013-015 18歳以上, 016-018 20歳以上,
019-021 65歳以上, 022-024 75歳以上）。**022 は75歳以上**なので取り違えないこと。

秘匿処理: HTKSYORI=2 の行は自メッシュの値が '*' で、HTKSAKI のメッシュに合算されている
（合算先の GASSAN に元メッシュが並ぶ）。**'*' は 0 として扱う**＝全国計は保たれるが、
秘匿元メッシュの人口は合算先メッシュの位置に寄る。500m格子では隣接メッシュへの寄せなので
アクセス判定への影響は限定的だが、注記として残す。

使い方:
  python3 scripts/fetch_mesh_population.py 高知県 島根県 宮城県
出力:
  data/mesh/mesh500_pop.parquet  (mesh_code, lat, lng, pop_total, pop_65over, pop_75over)
"""
import io
import os
import sys
import urllib.request
import zipfile

import duckdb

PREF_GEOJSON = "data/japan_pref.geojson"
PREF_URL = "https://raw.githubusercontent.com/dataofjapan/land/master/japan.geojson"
CACHE_DIR = "data/mesh/cache"
OUT_PARQUET = "data/mesh/mesh500_pop.parquet"

DL = ("https://www.e-stat.go.jp/gis/statmap-search/data"
      "?dlserveyId=A002006212020&statsId=T001141&code={mesh1}"
      "&coordSys=1&format=csv&downloadType=2")

COL_TOTAL = "T001141001"
COL_65OVER = "T001141019"
COL_75OVER = "T001141022"


def ensure_pref_geojson():
    if not os.path.exists(PREF_GEOJSON):
        os.makedirs(os.path.dirname(PREF_GEOJSON), exist_ok=True)
        print(f"取得: {PREF_URL} -> {PREF_GEOJSON}")
        urllib.request.urlretrieve(PREF_URL, PREF_GEOJSON)


def mesh1_codes_for(con, prefs):
    """対象県を覆う1次メッシュコードを列挙する（1次メッシュ = 緯度1/1.5度 x 経度1度）。

    県ごとの bbox から候補を作る。県をまたぐ bbox の合成は無関係な内陸まで拾うので、
    必ず**県単位**で列挙して和集合を取る。
    """
    codes = set()
    for pref in prefs:
        q = con.execute(
            "select min(ST_XMin(geom)), min(ST_YMin(geom)), max(ST_XMax(geom)), max(ST_YMax(geom)) "
            f"from ST_Read('{PREF_GEOJSON}') where nam_ja = '{pref}'"
        ).fetchone()
        if q[0] is None:
            sys.exit(f"県名が見つからない: {pref}")
        xmin, ymin, xmax, ymax = q
        for p in range(int(ymin * 1.5), int(ymax * 1.5) + 1):
            for u in range(int(xmin) - 100, int(xmax) - 100 + 1):
                codes.add(f"{p:02d}{u:02d}")
    return sorted(codes)


def fetch_mesh1(code):
    path = os.path.join(CACHE_DIR, f"T001141_{code}.zip")
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path
    os.makedirs(CACHE_DIR, exist_ok=True)
    url = DL.format(mesh1=code)
    try:
        with urllib.request.urlopen(url, timeout=120) as r:
            body = r.read()
    except Exception as e:  # 海上のみ等でデータが無い1次メッシュは404になる
        print(f"  {code}: 取得不可 ({e})")
        return None
    if not body.startswith(b"PK"):
        print(f"  {code}: zipでない（データ無しと判断）")
        return None
    with open(path, "wb") as f:
        f.write(body)
    return path


def parse_zip(path):
    """zip内のCSVから (mesh_code, pop_total, pop_65over, pop_75over) を返す。"""
    rows = []
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            text = z.read(name).decode("cp932", errors="replace")
            rdr = io.StringIO(text)
            header = next(rdr).rstrip("\r\n").split(",")
            next(rdr)  # 2行目 = 日本語見出し
            try:
                i_key = header.index("KEY_CODE")
                i_tot = header.index(COL_TOTAL)
                i_65 = header.index(COL_65OVER)
                i_75 = header.index(COL_75OVER)
            except ValueError:
                print(f"  {name}: 想定列が無い（スキップ）")
                continue
            for line in rdr:
                c = line.rstrip("\r\n").split(",")
                if len(c) <= i_75 or not c[i_key].strip():
                    continue
                rows.append((c[i_key].strip(), to_int(c[i_tot]),
                             to_int(c[i_65]), to_int(c[i_75])))
    return rows


def to_int(v):
    """'*'（秘匿）・'-'・空 は 0。"""
    v = v.strip()
    if v in ("", "*", "-", "X"):
        return 0
    try:
        return int(float(v))
    except ValueError:
        return 0


def mesh500_centroid(code):
    """9桁 500mメッシュコード -> 中心座標 (lat, lng)。Noneなら対象外の桁数。"""
    if len(code) != 9 or not code.isdigit():
        return None
    p, u = int(code[0:2]), int(code[2:4])
    q, v = int(code[4]), int(code[5])
    r, w = int(code[6]), int(code[7])
    m = int(code[8])
    if not 1 <= m <= 4:
        return None
    lat = p / 1.5 + q / 12 + r / 120 + ((m - 1) // 2) / 240
    lng = 100 + u + v / 8 + w / 80 + ((m - 1) % 2) / 160
    # 南西端 -> 中心（500mメッシュ = 緯度1/240度 x 経度1/160度）
    return lat + 1 / 480, lng + 1 / 320


def main():
    prefs = sys.argv[1:]
    if not prefs:
        sys.exit("使い方: python3 scripts/fetch_mesh_population.py 高知県 [島根県 ...]")

    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    ensure_pref_geojson()

    codes = mesh1_codes_for(con, prefs)
    print(f"対象県 {prefs} を覆う1次メッシュ候補 {len(codes)} 個")

    all_rows = []
    for code in codes:
        path = fetch_mesh1(code)
        if not path:
            continue
        rows = parse_zip(path)
        print(f"  {code}: {len(rows):,} メッシュ")
        all_rows.extend(rows)

    # 500mメッシュ（9桁）のみ・重心付与
    recs = []
    skipped = 0
    for mesh, tot, o65, o75 in all_rows:
        c = mesh500_centroid(mesh)
        if c is None:
            skipped += 1
            continue
        recs.append((mesh, c[0], c[1], tot, o65, o75))
    print(f"500mメッシュ {len(recs):,} 件（桁数不一致で除外 {skipped:,}）")

    os.makedirs(os.path.dirname(OUT_PARQUET), exist_ok=True)
    con.execute("create table mesh(mesh_code varchar, lat double, lng double, "
                "pop_total bigint, pop_65over bigint, pop_75over bigint)")
    con.executemany("insert into mesh values (?,?,?,?,?,?)", recs)
    n, t, o, o75 = con.execute(
        "select count(*), sum(pop_total), sum(pop_65over), sum(pop_75over) from mesh").fetchone()
    print(f"合計: {n:,} メッシュ / 総人口 {t:,} / 65歳以上 {o:,} / 75歳以上 {o75:,}")
    con.execute(f"copy mesh to '{OUT_PARQUET}' (FORMAT parquet)")
    print(f"出力: {OUT_PARQUET}")


if __name__ == "__main__":
    main()
