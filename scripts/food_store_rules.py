#!/usr/bin/env python3
"""マスター構築（build_food_store_master.py）と品質検証（verify_master_quality.py）で
共有する判定ルール。**両方から import すること**。片方だけ直すと「除去したはずのものを
検証が偽陽性として数え続ける」といったズレが起きる。
"""

# ---- 調剤専業（＝食品を扱わない）の除外ルール ----
#
# 設計_食料品店マスター構築.md 7章「調剤薬局は除外」の実装。
# Overture は pharmacy と drugstore を別カテゴリに持つが、**調剤薬局が drugstore に
# 紛れている**ため、カテゴリだけでは分離できない（category_alt にも pharmacy は
# 一件も無く、データ側に手がかりが無いことを確認済み）。やむを得ず名称で判定する。
#
# 素朴に「名称に 薬局/調剤 を含むもの」を全部落とすと、**食品を扱う地方ドラッグストアを
# 巻き添えにする**。マスターの該当 648 件を実際に目視して、屋号に「薬局」を含む
# ドラッグストアチェーンを洗い出したのが下のリスト。
DRUGSTORE_CHAINS = [
    # 全国・広域チェーン
    "ウエルシア", "スギ", "ココカラ", "サンドラッグ", "マツモトキヨシ", "マツキヨ",
    "ツルハ", "アオキ", "コスモス", "トモズ", "薬王堂", "ダイコク", "キリン堂",
    "カワチ", "サツドラ", "クリエイト", "セイジョー", "ハックドラッグ", "ゲンキー",
    # 地方チェーン（648 件の名称を目視して同定）
    "レデイ",      # 愛媛ほか四国・ツルハG
    "ウォンツ",    # 広島ほか中国・ツルハG
    "ヤックス",    # 千葉（ヤックスドラッグ / ヤックスケアタウン）
    "セイムス",    # 富士薬品（ドラッグセイムス）
    "セガミ",      # ドラッグセガミ・ココカラ系
    "杏林堂",      # 静岡
    "ププレ",      # 広島（ププレひまわり）
    "ウェルネス",  # 島根・鳥取
    "大賀薬局",    # 福岡
    "セキ薬局",    # 埼玉
    "福太郎",      # 千葉・ツルハG
    "金光薬局",    # 岡山（金光薬品）
    "フタツカ",    # 兵庫
    "灰吹屋",      # 神奈川
    "龍生堂",      # 東京
    "コクミン",    # コクミンドラッグ
    "サンキュー",  # 福岡・北九州（サンキュードラッグ）
    "ミニストップ",  # コンビニ併設の調剤（店舗自体はコンビニ）
]

# 屋号自体がドラッグストアを名乗るもの。チェーン名を列挙しなくても救える。
DRUGSTORE_TOKENS = ["ドラッグ", "ドラック", "drug", "くすり", "クスリ", "薬品"]


def dispensing_only_sql(name_col: str = "name") -> str:
    """調剤専業の疑い（＝マスターから除外すべき）を判定する SQL 述語を返す。

    「名称に 薬局／調剤 を含む」かつ「ドラッグストアチェーン名にも
    ドラッグストアを示す語にも一致しない」。ilike なので大文字小文字は無視する。
    """
    hit = f"({name_col} ilike '%薬局%' or {name_col} ilike '%調剤%')"
    keep = " or ".join(
        f"{name_col} ilike '%{w}%'" for w in DRUGSTORE_CHAINS + DRUGSTORE_TOKENS
    )
    # coalesce は必須。name が NULL だと ilike が NULL を返し、`where not (…)` が
    # 真にならないため、名称欠損の店舗（マスターに 495 件ある）が黙って全部落ちる。
    return f"coalesce({hit} and not ({keep}), false)"


# ---- 調剤特化業態の除外（チェーン名で救うルールの穴埋め）----
#
# 上の DRUGSTORE_CHAINS は「屋号に薬局を含むドラッグストアを巻き添えにしない」ためのリストだが、
# **同じチェーンの調剤専門業態まで救ってしまう**（「スギ薬局調剤 コトブキ薬局橿原店」241件、
# 「調剤薬局ツルハドラッグ ○○店」104件、「オストジャパン ○○調剤薬局」等）。これらは食品を扱わない。
#
# ただし素朴に「調剤」を含むものを落とすと、**ウエルシアの表記**を巻き添えにする。
# ウエルシアは併設を示す注記として店舗名に「(調剤薬局)」を付ける（「ウエルシア 江戸川葛西店 (調剤薬局)」）。
# これは店舗本体なので残さなければならない。
# → **括弧書きを除いた名称に「調剤」が残るもの**だけを調剤特化業態と判定する。
import re as _re

_PAREN = _re.compile(r"[（(].*?[)）]")


def is_dispensing_format(*parts: str | None) -> bool:
    """調剤専門業態（＝食品を扱わない）かどうか。brand / branch / name を渡す。"""
    text = " ".join(str(p) for p in parts if p)
    return "調剤" in _PAREN.sub("", text)


# ---- ブランド名の正規化 ----
#
# ソース間でブランド表記が揺れる。マスターは「セブンイレブン」、ATP は「セブン-イレブン」。
# 正規化せずに突合すると**同じ店が「純増」に化ける**（seven_eleven の純増 3,415件のうち
# 1,570件＝46%が実は既存店だった。issue #28-3）。突合の前に必ずこれを通すこと。
_BRAND_STRIP = str.maketrans("", "", "-‐－―ー・ 　　")


def normalize_brand(s: str | None) -> str:
    """ブランド／店名の突合用キー。記号・空白を落として小文字化する。"""
    return (s or "").translate(_BRAND_STRIP).lower()


def normalize_brand_sql(col: str) -> str:
    """normalize_brand と同じ正規化を行う SQL 式。"""
    expr = f"coalesce({col}, '')"
    for ch in ("-", "‐", "－", "―", "ー", "・", " ", "　"):
        expr = f"replace({expr}, '{ch}', '')"
    return f"lower({expr})"


# ---- 食品営業許可・届出データの業態フィルタ ----
#
# 厚労省 FAS の届出区分「⑪ 百貨店、総合スーパー」は**受け皿区分**で、食品を売る大型小売が
# ひとまとめに入る。実測（25,189行 → 施設 24,973件、2026-08-27）では
# ドラッグストア名 8,652件（35%）のほか、ホームセンター・家電量販・移動販売・事業所内売店が
# 混ざる。農水省の食料品アクセス定義（経済センサス 581 百貨店・総合スーパー ほか）に
# 合わせるため、以下を名称で落とす。**⑪ は許可業種の「⑪ 菓子製造業」(37,032行)と
# 番号が衝突するので、抽出は必ず区分名まで含めた完全一致で行うこと。**

# ホームセンター（食品売場を持つ店もあるが、センサス 581 には入らない）。
# マスター側にも殆ど入っていない（コーナン2件・カインズ2件・コメリ1件）ので、
# 入れると系統的な上振れになる。ナフコ37件・綿半17件は既にマスターにある。
HOMECENTER_CHAINS = [
    "コーナン", "カインズ", "コメリ", "ホーマック", "DCM", "ジョイフル本田",
    "ケーヨー", "ビバホーム", "ハンズマン", "ホームセンター", "ムサシ",
]

# 家電・衣料・雑貨。ドン・キホーテは食品主力の総合ディスカウントで
# マスターにも 138件入っているため**ここには入れない**（残す）。
NON_FOOD_RETAIL_CHAINS = [
    "ヤマダ", "エディオン", "ケーズデンキ", "ノジマ", "ジョーシン", "しまむら",
    "ユニクロ", "ニトリ", "西松屋", "ダイソー", "セリア", "キャンドゥ",
    "ヴィレッジヴァンガード", "書店", "ブックオフ", "TSUTAYA", "ゲオ",
    "ワークマン", "無印良品", "ロフト",
]

# 移動販売。定点の店舗ではないので 500m メッシュに固定できない。
MOBILE_VENDOR_TOKENS = ["とくし丸", "移動販売", "移動スーパー", "号車"]

# 事業所・施設の中の売店（一般客が使えない、または施設名で登録されているもの）。
INSTITUTIONAL_TOKENS = [
    "研究所", "工場", "本社", "支社", "学校", "大学", "高校", "病院", "クリニック",
    "テレビ", "放送", "市役所", "役場", "刑務所", "自衛隊", "駐屯地", "空港",
    "ターミナルビル", "アミュプラザ", "フェリー", "サービスエリア",
    "パーキングエリア", "道の駅", "駅ビル", "寮", "社員", "職員",
    "事業部", "営業部", "営業所", "事務所",
    # 「センター」は一括で落とせない。JA の「生活センター」やフードセンター・
    # ショッピングセンターは**店舗**（⑪ の有力候補）なので、施設側の複合語だけ挙げる。
    "教育センター", "研修センター", "医療センター", "保健センター", "文化センター",
    "振興センター", "研究センター", "給食センター", "福祉センター", "総合センター",
]

# 法人形態・組織名の接頭辞。ソース間で付く／付かないが揺れるので、
# ブランド突合キーを作る前に落とす（マスターは「コープさっぽろ○○店」、
# 許可データは「生活協同組合コープさっぽろ○○店」）。
ORG_PREFIXES = [
    "株式会社", "有限会社", "合同会社", "合資会社", "合名会社", "（株）", "(株)",
    "㈱", "（有）", "(有)", "㈲", "生活協同組合", "消費生活協同組合",
    "農業協同組合", "漁業協同組合", "協同組合", "一般社団法人", "医療法人",
]


def permit_excluded_sql(name_col: str = "name") -> str:
    """⑪ から落とす業態（ドラッグ／HC／家電雑貨／移動販売／事業所内）の SQL 述語。

    ドラッグストアは農水省の定義には含まれるが、ATP 基準マスターで既に実数の
    111.6% あり、⑪ からの補完対象は supermarket なので落とす。
    coalesce は必須（name が NULL の 10件が `where not (…)` で黙って消えるため）。
    """
    words = (
        DRUGSTORE_CHAINS + DRUGSTORE_TOKENS + HOMECENTER_CHAINS
        + NON_FOOD_RETAIL_CHAINS + MOBILE_VENDOR_TOKENS + INSTITUTIONAL_TOKENS
    )
    hit = " or ".join(f"{name_col} ilike '%{w}%'" for w in words)
    return f"coalesce({hit}, false)"


def strip_org_words(s: str | None) -> str:
    """法人形態・組織名の語を落とす。normalize_brand の前に通す。

    **先頭だけでは足りない**。許可データには「イオンリテール株式会社イオン小松店」の
    ように法人名が名称の途中に入る形があり、先頭一致だけだと突合キーが
    「イオンリテ…」になってマスターの「イオン小松店」と一致しない（偽の純増になる）。
    """
    t = (s or "")
    for p in ORG_PREFIXES:
        t = t.replace(p, "")
    return t.strip()


def strip_org_words_sql(col: str) -> str:
    """strip_org_words と同じ処理の SQL 式。

    case を入れ子にすると式が接頭辞の数の指数で膨らむので、正規表現で一度に落とす。
    """
    alt = "|".join(_re.escape(p) for p in ORG_PREFIXES)
    return f"trim(regexp_replace(coalesce({col}, ''), '{alt}', '', 'g'))"


def match_key_sql(col: str) -> str:
    """ソース間で店名を突合するためのキー（法人語を落として記号・空白を除去）。"""
    return normalize_brand_sql(strip_org_words_sql(col))

# ---- Overture grocery_store の浄化ルール ----
#
# Overture の `grocery_store` は「各種食料品店」で、小規模食料品店を広く含む一方、
# 飲食サービス系（カフェ・食堂）と雑貨店が混ざる。マスター構築（build_food_store_master.py）で
# supermarket に統合する前に落とすのがこのルール。**分解検証（decompose_supermarket.py）と
# 共有すること**（片方だけ直すと「マスターに入っている件数」と「検証が数える件数」がズレる）。
GROCERY_NOISE_ALT = [
    "restaurant", "cafe", "bar", "eat_and_drink", "japanese_restaurant",
    "smoothie_juice_bar", "food_beverage_service_distribution",
    "home_goods_store", "shopping",
]
GROCERY_FOOD_ALT = [
    "supermarket", "grocery_store", "health_food_store", "bakery", "liquor_store",
    "delicatessen", "specialty_grocery_store", "fishmonger",
    "fruits_and_vegetables", "butcher", "convenience_store", "farm",
]
GROCERY_NAME_NOISE = [
    "カフェ", "coffee", "cafe", "食堂", "ZAKKA", "雑貨", "セレクトショップ", "レストラン",
]


def grocery_noise_sql(name_col: str = "name", alt_col: str = "category_alt") -> str:
    """grocery_store のうち落とすべきノイズ（飲食サービス系・雑貨）の SQL 述語。

    「食物 retail の alt を持たず飲食/雑貨の alt だけを持つ」または「名称がノイズ」。
    """
    noise = "[" + ", ".join(f"'{w}'" for w in GROCERY_NOISE_ALT) + "]"
    food = "[" + ", ".join(f"'{w}'" for w in GROCERY_FOOD_ALT) + "]"
    name_noise = "(" + " or ".join(
        f"{name_col} ilike '%{w}%'" for w in GROCERY_NAME_NOISE) + ")"
    return (f"(({alt_col} is not null and len(list_intersect({alt_col},{noise}))>0"
            f" and len(list_intersect({alt_col},{food}))=0) or {name_noise})")

# ---- 生鮮3業種（魚介類販売・食肉販売・野菜果物販売）の抽出とフィルタ ----
#
# 実測（2026-08-27、施設単位 71,254件）: センサス 582/583/584 計 33,960 に対して**2倍以上ある**。
# 課題は収集ではなく**フィルタリング**（docs/sources/調査_freshfood補完ソース.md）。
# 内訳は スーパー・GMS 8.3% / コンビニ 4.9% / 卸・市場 1.5% / 加工・製造 1.1% /
# 移動販売 0.6% / 事業所内 0.7% / その他 82.5%。「その他」にも飲食店とスーパーが残る。

# 業種の抽出条件。**製造・処理・競り売り（卸売市場）は入れない**。
FRESH_TYPE_SQL = (
    "regexp_matches(business_type, '(魚介類販売|食肉販売|野菜果物販売)') "
    "and not regexp_matches(business_type, '(処理業|製造業|競り売り|せり売|小分け)')"
)

# 飲食店。焼肉・寿司・ラーメン店などが生鮮の許可を取っている。
# **これを落とさないと全国に偽の食料品店が湧く**（500mメッシュ指標が過小に出る）。
RESTAURANT_TOKENS = [
    "レストラン", "食堂", "居酒屋", "焼肉", "寿司", "すし", "鮨", "ラーメン", "らーめん",
    "カフェ", "cafe", "coffee", "喫茶", "料理", "厨房", "ダイニング", "dining", "バル",
    "ビストロ", "酒場", "屋台", "キッチン", "kitchen", "食事", "定食", "そば", "うどん",
    "ホテル", "旅館", "民宿", "宿", "温泉", "会館", "斎場", "カラオケ", "居食屋",
    # 純増サンプルの目視で追加（沖縄・高知の候補から）
    "ステーキ", "茶屋", "ラウンジ", "ラウンヂ", "rounge", "lounge", "スナック", "パブ",
    "焼鳥", "焼き鳥", "天ぷら", "とんかつ", "割烹", "料亭", "ビアガーデン", "バーベキュー",
]

# 卸・市場・仲卸（一般消費者向けでない）。
WHOLESALE_TOKENS = ["卸", "仲卸", "市場", "商事", "物流", "配送センター", "問屋"]

# 加工・製造の場（店頭小売でない）。
PROCESSING_TOKENS = ["水産加工", "加工場", "加工センター", "食品工業", "製造", "工場", "精肉加工"]

# 移動販売・露店・無人販売（定点の店舗として500mメッシュに固定できない）。
FRESH_MOBILE_TOKENS = ["移動", "号車", "自動車", "露店", "仮設", "行商", "無人", "自販"]


def fresh_excluded_sql(name_col: str = "name") -> str:
    """生鮮3業種から落とす業態の SQL 述語（名称ベース）。

    飲食店・卸・加工・移動販売・事業所内、およびドラッグストア（別カテゴリで補完済み）。
    **スーパー／コンビニのチェーン名はここでは列挙しない**。列挙し切れないので、
    「全国のマスターに同名の店が複数ある＝チェーンの売場」というデータ駆動の判定
    （extract_permit_fresh_food.py の chain_hit）で落とす。
    coalesce は必須（name が NULL の行が `where not (…)` で黙って消えるため）。
    """
    words = (
        RESTAURANT_TOKENS + WHOLESALE_TOKENS + PROCESSING_TOKENS
        + FRESH_MOBILE_TOKENS + INSTITUTIONAL_TOKENS
        + DRUGSTORE_CHAINS + DRUGSTORE_TOKENS
    )
    hit = " or ".join(f"{name_col} ilike '%{w}%'" for w in words)
    return f"coalesce({hit}, false)"
