/** データソース・カテゴリ・件数の定義。UI と地図レイヤーはここだけを見る。 */

import type { ExpressionSpecification } from "maplibre-gl";

export type SourceKey = "ovt" | "osm" | "permit";

/** 表示モード: ソース別（色＝データソース）／カテゴリ別（色＝業態・高ズームでピン）。 */
export type Mode = "source" | "category";

/** カテゴリ別モードで丸点からピンに切り替わるズーム。 */
export const PIN_MINZOOM = 13;

export interface SourceDef {
  key: SourceKey;
  /**
   * ソースの種類。既定は PMTiles（ベクタタイル）。
   * "geojson" は点数が少ない確認用レイヤ向け（tippecanoe を要求しない）。
   */
  kind?: "pmtiles" | "geojson";
  /** PMTiles 内のレイヤー名（kind:"geojson" では不要） */
  sourceLayer?: string;
  /** public/ 配下のファイル名 */
  file: string;
  name: string;
  /** 名称の後ろに小さく添える補足 */
  note?: string;
  /**
   * このソース固有の出典。MapLibre が AttributionControl に自動集約するので、
   * **customAttribution には書かない**（レイヤーを OFF にするとソースごと外れるため、
   * 表示中だけ出典が出るのが正しい振る舞いになる）。
   * OSM / Overture は ODbL の常時表示要件があるので main.ts の customAttribution 側。
   */
  attribution?: string;
  color: string;
  on: boolean;
  opacity: number;
}

export const SOURCES: SourceDef[] = [
  {
    key: "ovt",
    sourceLayer: "overture",
    file: "overture_food.pmtiles",
    name: "Overture Maps",
    note: "名寄せ済",
    color: "#2a78d6",
    on: true,
    opacity: 0.75,
  },
  {
    key: "osm",
    sourceLayer: "osm",
    file: "osm_food.pmtiles",
    name: "OpenStreetMap",
    color: "#e8590c",
    on: true,
    opacity: 0.75,
  },
  // 食品営業許可・届出データからの純増（ATP 基準マスターに投入した 20,400点と同じもの）。
  // 比較の主役は Overture vs OSM なので**既定は OFF**。目視確認用に後から足せる形にしてある。
  // 点数が少ないので PMTiles ではなく GeoJSON（docs/sources/検証_許可データ_*_補完効果.md）。
  {
    key: "permit",
    kind: "geojson",
    file: "permit_gapfill.json",
    name: "食品営業許可・届出",
    note: "純増のみ",
    attribution:
      '食品営業許可・届出オープンデータ（<a href="https://ifas.mhlw.go.jp/faspub/" target="_blank" rel="noopener">厚生労働省 食品衛生申請等システム</a>／各自治体、CC BY 4.0・政府標準利用規約）',
    color: "#0ca678",
    on: false,
    opacity: 0.85,
  },
];

export interface CatDef {
  key: string;
  label: string;
  /** 絞り込み用の "all" 以外は、カテゴリ色とスプライトのアイコン名を持つ */
  color?: string;
  icon?: string;
}

// 色は shiwaku/custom-smartmap-sprite の食料品店アイコン5点に合わせる
// （アイコン側の色を変えたらここも合わせること）
export const CATEGORIES: CatDef[] = [
  { key: "all", label: "すべて" },
  { key: "super", label: "スーパー", color: "#E23B3B", icon: "food-supermarket" },
  { key: "conv", label: "コンビニ", color: "#2477E0", icon: "food-convenience" },
  { key: "drug", label: "ドラッグストア", color: "#2E9E4F", icon: "food-drugstore" },
  { key: "grocery", label: "食料品店", color: "#8A4FD6", icon: "food-grocery" },
  { key: "fresh", label: "生鮮・直売所", color: "#FF7A1A", icon: "food-fresh" },
];

/** 凡例・カテゴリ着色に使う（"all" を除いた）カテゴリ。 */
export const STYLED_CATEGORIES = CATEGORIES.filter(
  (c): c is Required<CatDef> => c.color != null && c.icon != null,
);

/** cat 値 → カテゴリ色。未知の値はグレー。 */
export function catColorExpr(): ExpressionSpecification {
  const cases = STYLED_CATEGORIES.flatMap((c) => [c.key, c.color]);
  return ["match", ["get", "cat"], ...cases, "#9aa0a6"] as unknown as ExpressionSpecification;
}

/** cat 値 → スプライトのアイコン名（`<スプライトid>:<アイコン名>`）。 */
export function catIconExpr(spriteId: string): ExpressionSpecification {
  const cases = STYLED_CATEGORIES.flatMap((c) => [c.key, `${spriteId}:${c.icon}`]);
  const fallback = `${spriteId}:food-grocery`;
  return ["match", ["get", "cat"], ...cases, fallback] as unknown as ExpressionSpecification;
}

/**
 * カテゴリ別件数（ソースデータの実数）。
 * PMTiles は低ズームで点が間引かれるため実行時カウントできず、事前集計値を持つ。
 * 出典: scripts/compare_sources_by_category.sql（Overture 名寄せ済 / OSM 農水省定義準拠）
 * PMTiles を再生成したら同スクリプトで出し直してここを更新すること。
 * permit は scripts/build_permit_geojson.py が最後に表示する値
 * （convenience / drugstore は許可データから入れていないので 0）。
 */
export const COUNTS: Record<string, Record<SourceKey, number>> = {
  all: { ovt: 109602, osm: 81380, permit: 20400 },
  super: { ovt: 18521, osm: 20348, permit: 3157 },
  conv: { ovt: 54987, osm: 48676, permit: 0 },
  drug: { ovt: 7735, osm: 4554, permit: 0 },
  grocery: { ovt: 20608, osm: 275, permit: 0 },
  fresh: { ovt: 7751, osm: 7527, permit: 17243 },
};

export function countOf(cat: string, src: SourceKey): number {
  return (COUNTS[cat] ?? COUNTS.all)[src];
}

const CAT_LABEL: Record<string, string> = Object.fromEntries(
  CATEGORIES.filter((c) => c.key !== "all").map((c) => [c.key, c.label]),
);

const esc = (s: string): string =>
  s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c] as string);

/**
 * クリック時のポップアップ。属性は name / addr / cat / cat_raw / confidence。
 * addr は Overture のみ（OSM の元データが住所タグを持たない。build_pmtiles.sh 参照）。
 * カテゴリ別モードでは点の色がソースを表さないので、ソース色のドットは出さない。
 */
export function popupHtml(def: SourceDef, p: Record<string, unknown>, mode: Mode): string {
  const name = (p.name as string) || "(名称なし)";
  const cat = (p.cat as string) ?? "";
  const rows: string[] = [];
  if (p.addr) rows.push(`<dt>住所</dt><dd class="pp-addr">${esc(String(p.addr))}</dd>`);
  rows.push(`<dt>カテゴリ</dt><dd>${esc(CAT_LABEL[cat] ?? cat ?? "—")}</dd>`);
  if (p.cat_raw) rows.push(`<dt>原カテゴリ</dt><dd>${esc(String(p.cat_raw))}</dd>`);
  if (p.confidence != null) {
    rows.push(`<dt>confidence</dt><dd>${Number(p.confidence).toFixed(2)}</dd>`);
  }
  const dot = mode === "source" ? `<span class="pp-dot" style="background:${def.color}"></span>` : "";
  return (
    `<div class="pp-title">${esc(name)}</div>` +
    `<div class="pp-sub">${dot}${esc(def.name)}</div>` +
    `<dl class="pp-dl">${rows.join("")}</dl>`
  );
}
