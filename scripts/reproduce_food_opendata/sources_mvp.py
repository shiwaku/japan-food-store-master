"""MVP 対象 5 ソースの取得先＋正規化設定。

実列を確認した上で、共通16列スキーマへのマッピングを定義。
横展開時はこの SOURCES を全92ソースに増やす（同形式は colmap を使い回せる）。
"""
DL = "scripts/reproduce_food_opendata/downloads"

SOURCES = [
    {
        "id": "minato",
        "pref": "東京都", "muni": "港区", "route": "自身",
        "source_name": "東京都港区 食品営業許可（オープンデータ）",
        "license": "CC BY 4.0",
        "format": "csv", "path": f"{DL}/minato.csv", "encoding": "utf-8-sig",
        "url": "https://opendata.city.minato.tokyo.jp/dataset/54d8c582-00e2-4730-a23f-4a5befec9ae5/resource/c9d0299e-8e05-4317-877f-83055709e41f/download/food_business_all.csv",
        "const": {},
        "colmap": {
            "prefecture": "施設所在地_都道府県", "city": "施設所在地_市区町村",
            "city_raw": "地方公共団体名", "name": "施設名称", "name_kana": "施設名称_カナ",
            "business_type": "営業の種類", "lat": "緯度", "lng": "経度",
            "phone": "施設電話番号", "license_no": "許可番号",
            "license_date": "許可年月日", "expire_date": "許可満了日",
        },
        "address_parts": ["所在地_連結表記"],
    },
    {
        "id": "kobe",
        "pref": "兵庫県", "muni": "神戸市", "route": "自身",
        "source_name": "神戸市食品営業許可施設一覧",
        "license": "CC BY 4.0",
        "format": "csv", "path": f"{DL}/kobe.csv", "encoding": "cp932",
        "url": "https://www.city.kobe.lg.jp/documents/6359/20260407150739.csv",
        "const": {"prefecture": "兵庫県", "city": "神戸市", "city_raw": "神戸市"},
        "colmap": {
            "name": "屋号", "business_type": "業種情報公開名称", "phone": "営業所ＴＥＬ１",
            "license_no": "許可番号", "license_date": "許可決定日", "expire_date": "許可満了日",
        },
        "address_parts": ["営業所所在地", "営業所方書"],
    },
    {
        "id": "hyogo",
        "pref": "兵庫県", "muni": "(県所管域)", "route": "管轄主体",
        "source_name": "兵庫県食品関係営業施設リスト（許可）",
        "license": "CC BY 4.0",
        "format": "excel", "path": f"{DL}/hyogo.xlsx", "header_row": 1,
        "url": "https://web.pref.hyogo.lg.jp/kf14/documents/000028_food_business_lisence_all.xlsx",
        "const": {"prefecture": "兵庫県"},  # 市区町村は住所に含まれる(per-row列なし)
        "colmap": {
            "name": "営業所名称", "business_type": "業種", "phone": "営業所電話番号",
            "license_no": "許可番号", "license_date": "許可日", "expire_date": "有効期限",
        },
        "address_parts": ["営業所所在地"],
    },
    {
        "id": "bodik_maebashi",
        "pref": "群馬県", "muni": "前橋市", "route": "自身",
        "source_name": "前橋市 食品等営業許可・届出一覧（BODIK）",
        "license": "CC BY 4.0",
        "format": "excel", "path": f"{DL}/bodik_maebashi.xlsx", "header_row": 0,
        "url": "https://data.bodik.jp/dataset/be0e8464-4b96-41f6-901d-1aa4bf11bcc0",
        "const": {"prefecture": "群馬県", "city": "前橋市", "city_raw": "前橋市"},
        "colmap": {
            "name": "営業所名", "business_type": "営業の種類",
            "license_no": "許可番号", "license_date": "許可年月日", "expire_date": "許可満了日",
        },
        "address_parts": ["営業所所在地"],
    },
    # --- FAS層(各エリアの新システム分)。自前/県データと名寄せ統合して一致度を上げる ---
    {
        "id": "fas_maebashi", "pref": "群馬県", "muni": "前橋市", "route": "i2fas",
        "source_name": "厚生労働省 食品衛生申請等システム（オープンデータ）",
        "license": "公共データ利用規約（第1.0版, PDL1.0）",
        "format": "csv", "path": "data/faspub_food_business/10201_food_business_all.csv",
        "encoding": "utf-8-sig",
        "url": "https://i2fas.mhlw.go.jp/faspub/IO_S010303.do?method=a_menu_o01Action",
        "const": {}, "colmap": "_FAS_", "address_parts": ["営業施設所在地", "営業施設方書"],
    },
    {
        "id": "fas_kobe", "pref": "兵庫県", "muni": "神戸市", "route": "i2fas",
        "source_name": "厚生労働省 食品衛生申請等システム（オープンデータ）",
        "license": "公共データ利用規約（第1.0版, PDL1.0）",
        "format": "csv", "path": "data/faspub_food_business/28100_food_business_all.csv",
        "encoding": "utf-8-sig",
        "url": "https://i2fas.mhlw.go.jp/faspub/IO_S010303.do?method=a_menu_o01Action",
        "const": {}, "colmap": "_FAS_", "address_parts": ["営業施設所在地", "営業施設方書"],
    },
    {
        "id": "fas_hyogo", "pref": "兵庫県", "muni": "(県所管域)", "route": "i2fas",
        "source_name": "厚生労働省 食品衛生申請等システム（オープンデータ）",
        "license": "公共データ利用規約（第1.0版, PDL1.0）",
        "format": "csv", "path": "data/faspub_food_business/28000_food_business_all.csv",
        "encoding": "utf-8-sig",
        "url": "https://i2fas.mhlw.go.jp/faspub/IO_S010303.do?method=a_menu_o01Action",
        "const": {}, "colmap": "_FAS_", "address_parts": ["営業施設所在地", "営業施設方書"],
    },
    {
        "id": "fas_hakodate",
        "pref": "北海道", "muni": "函館市", "route": "i2fas",
        "source_name": "厚生労働省 食品衛生申請等システム（オープンデータ）",
        "license": "公共データ利用規約（第1.0版, PDL1.0）",
        "format": "csv", "path": "data/faspub_food_business/01202_food_business_all.csv",
        "encoding": "utf-8-sig",
        "url": "https://i2fas.mhlw.go.jp/faspub/IO_S010303.do?method=a_menu_o01Action",
        "const": {},
        "colmap": {
            "prefecture": "都道府県名", "city": "市区町村名",
            "name": "営業施設名称、屋号又は商号",
            "name_kana": "営業施設名称、屋号又は商号（フリガナ）",
            "business_type": "営業の種類", "lat": "緯度", "lng": "経度",
            "phone": "営業施設電話番号", "license_no": "許可番号",
            "license_date": "許可年月日", "expire_date": "許可満了日",
        },
        "address_parts": ["営業施設所在地", "営業施設方書"],
    },
]
