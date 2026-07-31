/** データソース・カテゴリ・件数の定義。UI と地図レイヤーはここだけを見る。 */

export type SourceKey = "ovt" | "osm";

export interface SourceDef {
  key: SourceKey;
  /** PMTiles 内のレイヤー名 */
  sourceLayer: string;
  /** public/ 配下のファイル名 */
  file: string;
  name: string;
  /** 名称の後ろに小さく添える補足 */
  note?: string;
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
];

export interface CatDef {
  key: string;
  label: string;
}

export const CATEGORIES: CatDef[] = [
  { key: "all", label: "すべて" },
  { key: "super", label: "スーパー" },
  { key: "conv", label: "コンビニ" },
  { key: "drug", label: "ドラッグストア" },
  { key: "grocery", label: "食料品店" },
  { key: "fresh", label: "生鮮・直売所" },
];

/**
 * カテゴリ別件数（ソースデータの実数）。
 * PMTiles は低ズームで点が間引かれるため実行時カウントできず、事前集計値を持つ。
 * 出典: scripts/compare_sources_by_category.sql（Overture 名寄せ済 / OSM 農水省定義準拠）
 * PMTiles を再生成したら同スクリプトで出し直してここを更新すること。
 */
export const COUNTS: Record<string, Record<SourceKey, number>> = {
  all: { ovt: 109602, osm: 81380 },
  super: { ovt: 18521, osm: 20348 },
  conv: { ovt: 54987, osm: 48676 },
  drug: { ovt: 7735, osm: 4554 },
  grocery: { ovt: 20608, osm: 275 },
  fresh: { ovt: 7751, osm: 7527 },
};

export function countOf(cat: string, src: SourceKey): number {
  return (COUNTS[cat] ?? COUNTS.all)[src];
}

const CAT_LABEL: Record<string, string> = Object.fromEntries(
  CATEGORIES.filter((c) => c.key !== "all").map((c) => [c.key, c.label]),
);

const esc = (s: string): string =>
  s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c] as string);

/** クリック時のポップアップ。属性は name / cat / cat_raw / confidence。 */
export function popupHtml(def: SourceDef, p: Record<string, unknown>): string {
  const name = (p.name as string) || "(名称なし)";
  const cat = (p.cat as string) ?? "";
  const rows: string[] = [];
  rows.push(`<dt>カテゴリ</dt><dd>${esc(CAT_LABEL[cat] ?? cat ?? "—")}</dd>`);
  if (p.cat_raw) rows.push(`<dt>原カテゴリ</dt><dd>${esc(String(p.cat_raw))}</dd>`);
  if (p.confidence != null) {
    rows.push(`<dt>confidence</dt><dd>${Number(p.confidence).toFixed(2)}</dd>`);
  }
  return (
    `<div class="pp-title">${esc(name)}</div>` +
    `<div class="pp-sub"><span class="pp-dot" style="background:${def.color}"></span>${esc(def.name)}</div>` +
    `<dl class="pp-dl">${rows.join("")}</dl>`
  );
}
