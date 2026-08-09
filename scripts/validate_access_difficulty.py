#!/usr/bin/env python3
"""
食料品店マスターを「農水省 食料品アクセス困難人口」の指標で検証する。

なぜ必要か
----------
既存の検証（`検証_マスターPhase1_*.csv`）は **県単位の件数比を食料支出シェアで加重した率**。
一方 農水省の指標は **500mメッシュ人口 × 最近隣店舗まで500m以上** という二値・空間指標であり、
件数比が合っていても空間的な穴は見えない。加重カバー率は距離指標の代理にならない。
→ メッシュ単位で「500m圏外の65歳以上人口」を出し、農水省公表値（表5・2020年）と突合する。

農水省の操作化について（このスクリプトで実測した結論）
------------------------------------------------------
「500m以上」の実装候補を3つ試し、公表値との比（= 暗黙の自動車利用困難率）の分布を比べた:

  変種A 同一500mメッシュ内に店舗があるか   → 比 中央値0.370 / sd0.109  ★整合
  変種B 自メッシュ+8近傍メッシュ            → 比 中央値0.592 / sd2.696
  変種C メッシュ重心から実距離500m以内      → 比 中央値0.446 / sd0.504

農水省の困難人口は「圏外 かつ 自動車利用困難」なので、比は必ず1以下でなければならない。
B と C は比が1を超える市区町村が出る（＝論理的に不整合）。**変種Aのみ全市区町村で比≤1** かつ
比のばらつきが極小（p10-p90 = 0.26-0.52 ＝ 自動車利用困難率として妥当な幅）。
→ 公表値と整合する操作化は「店舗を500mメッシュに集計し、自メッシュに店舗が無ければ圏外」。
   つまり**隣メッシュの店舗には救われない**＝店舗レイヤの網羅性が直に効く。

したがって本スクリプトは **変種A を主**の指標とし、変種C を対照として併記する。

距離・メッシュの扱い
--------------------
- 500mメッシュコード（9桁）の相互変換を自前実装（`mesh500_code` / 逆変換は fetch_mesh_population.py）。
- 変種C の近傍探索は等距円筒近似でメートル平面へ投影し 500m グリッドでバケット化する。
  この環境の DuckDB は `ST_Distance_Spheroid` が -nan を返すため（CLAUDE.md 参照）。
- DuckDB の `/` は DOUBLE を返し `::int` が四捨五入するため、メッシュ添字は必ず `//` を使う。

使い方
------
  python3 scripts/fetch_mesh_population.py 高知県 島根県 宮城県   # 先にメッシュ人口を用意
  python3 scripts/validate_access_difficulty.py 高知県 島根県 宮城県
出力
----
  docs/master/検証_アクセス困難人口_市区町村別.csv
  docs/master/検証_アクセス困難人口_カテゴリ感度.csv
"""
import os
import sys
import urllib.request
import zipfile

import duckdb

MASTER = "data/food_store_master.parquet"
MESH = "data/mesh/mesh500_pop.parquet"
BND_DIR = "data/boundary"
MAFF_XLSX = "data/maff_2020_table05.xlsx"
OUT_CITY = "docs/検証_アクセス困難人口_市区町村別.csv"
OUT_SENS = "docs/検証_アクセス困難人口_カテゴリ感度.csv"

MAFF_TABLE05_URL = ("https://www.maff.go.jp/primaff/seika/fsc/faccess/attach/excel/"
                    "2020_table05.xlsx")
BND_URL = ("https://www.e-stat.go.jp/gis/statmap-search/data"
           "?dlserveyId=A002005212020&code={pref_code}"
           "&coordSys=1&format=shape&downloadType=5&datum=2000")

PREF_CODES = {
    "北海道": "01", "青森県": "02", "岩手県": "03", "宮城県": "04", "秋田県": "05",
    "山形県": "06", "福島県": "07", "茨城県": "08", "栃木県": "09", "群馬県": "10",
    "埼玉県": "11", "千葉県": "12", "東京都": "13", "神奈川県": "14", "新潟県": "15",
    "富山県": "16", "石川県": "17", "福井県": "18", "山梨県": "19", "長野県": "20",
    "岐阜県": "21", "静岡県": "22", "愛知県": "23", "三重県": "24", "滋賀県": "25",
    "京都府": "26", "大阪府": "27", "兵庫県": "28", "奈良県": "29", "和歌山県": "30",
    "鳥取県": "31", "島根県": "32", "岡山県": "33", "広島県": "34", "山口県": "35",
    "徳島県": "36", "香川県": "37", "愛媛県": "38", "高知県": "39", "福岡県": "40",
    "佐賀県": "41", "長崎県": "42", "熊本県": "43", "大分県": "44", "宮崎県": "45",
    "鹿児島県": "46", "沖縄県": "47",
}

# 農水省の対象業種は生鮮専門店・ドラッグストアも含む（access_genjo.html 原文）。
# 入れ子にして「どのカテゴリの欠落が何人分の誤差になるか」を分離する。
NESTED = [
    ("S1_supermarketのみ", "has_sm"),
    ("S2_+convenience", "(has_sm or has_cv)"),
    ("S3_+drugstore", "(has_sm or has_cv or has_dg)"),
    ("S4_全カテゴリ", "(has_sm or has_cv or has_dg or has_fr)"),
]

THRESHOLD_M = 500


def mesh500_code(lat, lng):
    """緯度経度 -> 9桁の500m（4次）メッシュコード。"""
    a = lat * 1.5
    p = int(a); a -= p
    q = int(a * 8); a = a * 8 - q
    r = int(a * 10); a = a * 10 - r
    m_lat = int(a * 2)
    f = lng - 100
    u = int(f); f -= u
    v = int(f * 8); f = f * 8 - v
    w = int(f * 10); f = f * 10 - w
    m_lng = int(f * 2)
    return f"{p:02d}{u:02d}{q}{v}{r}{w}{m_lat * 2 + m_lng + 1}"


def fetch_boundary(pref):
    """e-Stat 統計GIS の 令和2年国勢調査 小地域境界（shapefile, appId不要）。"""
    code = PREF_CODES[pref]
    shp = os.path.join(BND_DIR, f"r2ka{code}.shp")
    if os.path.exists(shp):
        return shp
    os.makedirs(BND_DIR, exist_ok=True)
    print(f"取得: 境界データ {pref}({code})")
    with urllib.request.urlopen(BND_URL.format(pref_code=code), timeout=300) as r:
        body = r.read()
    if not body.startswith(b"PK"):
        sys.exit(f"境界データがzipでない: {pref}")
    zpath = os.path.join(BND_DIR, f"r2ka{code}.zip")
    with open(zpath, "wb") as f:
        f.write(body)
    with zipfile.ZipFile(zpath) as z:
        z.extractall(BND_DIR)
    if not os.path.exists(shp):
        sys.exit(f"展開後に {shp} が無い")
    return shp


def load_maff_table05():
    """農水省 表5（市区町村別 食料品アクセス困難人口, 2020年）。

    8行目のキー: code1741=市区町村コード / numi=名称 / ep20_65=65歳以上困難人口(人) / e20=割合(%)
    """
    import openpyxl
    if not os.path.exists(MAFF_XLSX):
        os.makedirs("data", exist_ok=True)
        print(f"取得: {MAFF_TABLE05_URL}")
        urllib.request.urlretrieve(MAFF_TABLE05_URL, MAFF_XLSX)
    ws = openpyxl.load_workbook(MAFF_XLSX, data_only=True)["表５ 市町村別"]
    rows = []
    for r in ws.iter_rows(min_row=9, values_only=True):
        code, name, pop, rate = r[1], r[2], r[3], r[4]
        if not (code and isinstance(code, str) and code.strip().isdigit()):
            continue
        if pop is None or rate is None:
            continue
        rows.append((code.strip(), str(name).strip(), float(pop), float(rate)))
    return rows


def main():
    prefs = sys.argv[1:]
    if not prefs:
        sys.exit("使い方: python3 scripts/validate_access_difficulty.py 高知県 [島根県 ...]")
    for p in prefs:
        if p not in PREF_CODES:
            sys.exit(f"未知の県名: {p}")
    for f in (MASTER, MESH):
        if not os.path.exists(f):
            sys.exit(f"入力が無い: {f}（先に fetch_mesh_population.py を実行）")

    shps = [fetch_boundary(p) for p in prefs]
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    con.create_function("mesh500", mesh500_code, ["DOUBLE", "DOUBLE"], "VARCHAR")

    # ---- 1. 小地域境界（ASCII のコード列のみ。DBF は CP932 で名称列は読めない）----
    # geom::GEOMETRY で SRS 付き型を素の GEOMETRY に落とさないと rtree が作れない。
    union_sql = " union all ".join(
        f"select PREF || CITY as city_code, geom::GEOMETRY as geom from ST_Read('{s}')"
        for s in shps)
    con.execute(f"create table area as {union_sql}")
    con.execute("create index area_ix on area using rtree(geom)")
    print(f"小地域ポリゴン {con.execute('select count(*) from area').fetchone()[0]:,} 件")

    # ---- 2. メッシュを対象県に限定し市区町村を割当（政令市の区は市に寄せる）----
    con.execute(f"""create table mesh as
      select m.mesh_code, m.lat, m.lng, m.pop_total, m.pop_65over,
             case when regexp_matches(a.city_code, '^\\d{{2}}1\\d{{2}}$')
                  then substr(a.city_code,1,2) || '100' else a.city_code end as city_code
      from read_parquet('{MESH}') m
      join area a on ST_Contains(a.geom, ST_Point(m.lng, m.lat))""")
    n_mesh, pop65 = con.execute("select count(*), sum(pop_65over) from mesh").fetchone()
    print(f"対象県内の500mメッシュ {n_mesh:,} 件 / 65歳以上 {pop65:,} 人")

    # ---- 3. 店舗を500mメッシュへ割当（変種A）----
    con.execute(f"""create table smesh as
      select mesh500(lat, lng) as mesh_code, cat from read_parquet('{MASTER}')""")
    con.execute("""create table hitA as
      select mesh_code,
             bool_or(cat='supermarket') has_sm, bool_or(cat='convenience') has_cv,
             bool_or(cat='drugstore')   has_dg, bool_or(cat='fresh_food')  has_fr
      from smesh group by 1""")

    # ---- 4. 対照: 重心から実距離500m以内（変種C）----
    con.execute(f"""create table sb as
      select floor(lng*111320*cos(radians(lat))/{THRESHOLD_M})::bigint cx,
             floor(lat*111320/{THRESHOLD_M})::bigint cy,
             lng*111320*cos(radians(lat)) x, lat*111320 y
      from read_parquet('{MASTER}')""")
    con.execute(f"""create table mkC as
      select mesh_code, lng*111320*cos(radians(lat)) x, lat*111320 y,
             floor(lng*111320*cos(radians(lat))/{THRESHOLD_M})::bigint + dx cx,
             floor(lat*111320/{THRESHOLD_M})::bigint + dy cy
      from mesh, (select unnest([-1,0,1]) dx) a, (select unnest([-1,0,1]) dy) b""")
    con.execute(f"""create table hitC as
      select distinct k.mesh_code from mkC k join sb s on k.cx=s.cx and k.cy=s.cy
      where sqrt(power(k.x-s.x,2)+power(k.y-s.y,2)) <= {THRESHOLD_M}""")

    con.execute("""create table cov as
      select m.mesh_code, m.city_code, m.pop_65over, m.pop_total,
             coalesce(a.has_sm,false) has_sm, coalesce(a.has_cv,false) has_cv,
             coalesce(a.has_dg,false) has_dg, coalesce(a.has_fr,false) has_fr,
             (c.mesh_code is not null) as inC
      from mesh m
      left join hitA a using (mesh_code)
      left join hitC c using (mesh_code)""")

    # ---- 5. カテゴリ感度（主指標 = 変種A）----
    print("\n=== カテゴリ感度: 500m圏外の65歳以上人口（変種A・対象県計）===")
    sens = []
    prev = None
    for label, expr in NESTED:
        out65, all65 = con.execute(
            f"select sum(pop_65over) filter (where not {expr}), sum(pop_65over) from cov"
        ).fetchone()
        out65 = out65 or 0
        delta = (prev - out65) if prev is not None else None
        sens.append((label, out65, all65, round(out65 / all65, 4), delta))
        d = f"  （前段からの削減 {delta:,} 人）" if delta is not None else ""
        print(f"  {label:22s} 圏外 {out65:>9,} / {all65:>9,} = {out65/all65*100:5.1f}%{d}")
        prev = out65
    outC, allC = con.execute(
        "select sum(pop_65over) filter (where not inC), sum(pop_65over) from cov").fetchone()
    print(f"  {'(対照) 変種C 実距離500m':22s} 圏外 {outC:>9,} / {allC:>9,} = {outC/allC*100:5.1f}%")

    con.execute("create table sens(店舗集合 varchar, 圏外65歳以上人口 bigint, "
                "総65歳以上人口 bigint, 圏外率 double, 前段からの削減人数 bigint)")
    con.executemany("insert into sens values (?,?,?,?,?)", sens)
    os.makedirs("docs", exist_ok=True)
    con.execute(f"copy sens to '{OUT_SENS}' (header, delimiter ',')")

    # ---- 6. 市区町村別 × 農水省突合 ----
    maff = load_maff_table05()
    con.execute("create table maff(city_code varchar, 市区町村名 varchar, "
                "maff_pop double, maff_rate double)")
    con.executemany("insert into maff values (?,?,?,?)", maff)
    print(f"\n農水省 表5（2020年）読み込み: {len(maff):,} 市区町村")

    con.execute("""create table city as
      select c.city_code as 市区町村コード, m.市区町村名,
             c.pop65 as 総65歳以上人口,
             c.outA as 圏外65歳以上人口_変種A,
             round(c.outA / nullif(c.pop65,0), 4) as 圏外率_変種A,
             c.outA_sm as 圏外65歳以上人口_supermarketのみ,
             c.outC as 圏外65歳以上人口_変種C,
             round(c.outC / nullif(c.pop65,0), 4) as 圏外率_変種C,
             round(m.maff_rate/100, 4) as 農水省_困難人口割合,
             round(m.maff_pop) as 農水省_困難人口,
             round((m.maff_rate/100) / nullif(c.outA / nullif(c.pop65,0), 0), 3) as 比_農水省÷変種A
      from (select city_code, sum(pop_65over) pop65,
                   sum(case when not (has_sm or has_cv or has_dg or has_fr) then pop_65over else 0 end) outA,
                   sum(case when not has_sm then pop_65over else 0 end) outA_sm,
                   sum(case when not inC then pop_65over else 0 end) outC
            from cov group by 1) c
      left join maff m using (city_code)
      order by 圏外率_変種A desc""")
    con.execute(f"copy city to '{OUT_CITY}' (header, delimiter ',')")
    print(f"出力: {OUT_SENS}")
    print(f"出力: {OUT_CITY}")

    matched, total = con.execute(
        "select count(農水省_困難人口), count(*) from city").fetchone()
    print(f"コード突合: {matched}/{total} 市区町村")

    print("\n=== 対象県 全体 ===")
    a = con.execute("""select sum(総65歳以上人口), sum(圏外65歳以上人口_変種A),
                              sum(圏外65歳以上人口_変種C), sum(農水省_困難人口)
                       from city where 農水省_困難人口 is not null""").fetchone()
    print(f"  65歳以上人口              {a[0]:>10,}")
    print(f"  変種A 500m圏外人口         {a[1]:>10,}  ({a[1]/a[0]*100:.1f}%)")
    print(f"  変種C 500m圏外人口         {a[2]:>10,}  ({a[2]/a[0]*100:.1f}%)")
    print(f"  農水省 困難人口（公表）     {int(a[3]):>10,}  ({a[3]/a[0]*100:.1f}%)")
    print(f"  比 農水省÷変種A            {a[3]/a[1]:>10.3f}  ← 自動車利用困難率に相当")

    print("\n=== 比_農水省÷変種A の分布（1を超えたら操作化が不整合）===")
    q = con.execute("""select count(*), min(比_農水省÷変種A), quantile_cont(比_農水省÷変種A,0.1),
                              median(比_農水省÷変種A), quantile_cont(比_農水省÷変種A,0.9),
                              max(比_農水省÷変種A), stddev(比_農水省÷変種A),
                              corr(圏外率_変種A, 農水省_困難人口割合)
                       from city where 比_農水省÷変種A is not null""").fetchone()
    print(f"  n={q[0]}  min={q[1]:.3f}  p10={q[2]:.3f}  median={q[3]:.3f}  "
          f"p90={q[4]:.3f}  max={q[5]:.3f}  sd={q[6]:.3f}  r={q[7]:.3f}")

    print("\n=== 比が小さい＝圏外率が過大（店舗レイヤの穴の疑い）top10 ===")
    for r in con.execute("""select 市区町村コード, 市区町村名, 総65歳以上人口, 圏外率_変種A,
                                   農水省_困難人口割合, 比_農水省÷変種A
                            from city where 比_農水省÷変種A is not null and 総65歳以上人口 >= 3000
                            order by 比_農水省÷変種A limit 10""").fetchall():
        print(f"  {r[0]} {str(r[1]):12s} 65+={r[2]:>7,} "
              f"変種A圏外={r[3]*100:5.1f}% 農水省={r[4]*100:5.1f}% 比={r[5]}")

    print("\n=== 比が大きい＝圏外率が過小（店舗の偽陽性・過剰計上の疑い）top10 ===")
    for r in con.execute("""select 市区町村コード, 市区町村名, 総65歳以上人口, 圏外率_変種A,
                                   農水省_困難人口割合, 比_農水省÷変種A
                            from city where 比_農水省÷変種A is not null and 総65歳以上人口 >= 3000
                            order by 比_農水省÷変種A desc limit 10""").fetchall():
        print(f"  {r[0]} {str(r[1]):12s} 65+={r[2]:>7,} "
              f"変種A圏外={r[3]*100:5.1f}% 農水省={r[4]*100:5.1f}% 比={r[5]}")


if __name__ == "__main__":
    main()
