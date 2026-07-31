import maplibregl from "maplibre-gl";
import { Protocol } from "pmtiles";
import "maplibre-gl/dist/maplibre-gl.css";

import { getBasemapStyle, haloColor, type Basemap } from "./basemap";
import { CATEGORIES, SOURCES, countOf, popupHtml, type SourceDef } from "./layers";
import { applyThemeAttr, initialTheme, type Theme } from "./theme";
import "./style.css";

// 帰属表示。OSM は ODbL で常時表示が必須なので、レイヤーの ON/OFF や表示範囲に
// 依存しない customAttribution に置く。地理院ベースマップの出典はスタイル側の
// ソース attribution が自動表示するため、ここには含めない（二重表示になる）。
const DATA_ATTRIBUTION = [
  '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap contributors</a>（ODbL）',
  '© <a href="https://overturemaps.org/" target="_blank" rel="noopener">Overture Maps Foundation</a>',
].join(" ｜ ");

let theme: Theme = initialTheme();
let base: Basemap = "pale";
let cat = "all";
applyThemeAttr(theme);

const isMobile = window.matchMedia("(max-width: 640px)").matches;

const protocol = new Protocol();
maplibregl.addProtocol("pmtiles", protocol.tile);

const map = new maplibregl.Map({
  container: "map",
  style: getBasemapStyle(base, theme),
  center: [138.5, 36.5],
  zoom: 5,
  maxZoom: 17,
  // 地図位置を URL の #ズーム/緯度/経度 に反映（共有・リロード時の位置維持）
  hash: true,
  attributionControl: false,
  // モバイルは GPU/メモリが限られるため保持タイル数と描画バッファを抑える
  // （WebGL コンテキスト消失＝地図が真っ白になる事象の予防）
  maxTileCacheSize: isMobile ? 24 : undefined,
  pixelRatio: isMobile ? Math.min(window.devicePixelRatio || 1, 2) : undefined,
});

map.addControl(new maplibregl.NavigationControl({ showCompass: true, visualizePitch: true }), "top-right");
map.addControl(
  new maplibregl.GeolocateControl({
    positionOptions: { enableHighAccuracy: true },
    trackUserLocation: true,
    showUserLocation: true,
  }),
  "top-right",
);
map.addControl(new maplibregl.FullscreenControl(), "top-right");
map.addControl(new maplibregl.ScaleControl(), "bottom-left");
map.addControl(new maplibregl.AttributionControl({ compact: true, customAttribution: DATA_ATTRIBUTION }));

// ---- データレイヤー ----

const layerId = (key: string): string => `${key}-pt`;
const defOf = (id: string): SourceDef | undefined => SOURCES.find((s) => layerId(s.key) === id);
const activeLayerIds = (): string[] =>
  SOURCES.filter((s) => s.on).map((s) => layerId(s.key)).filter((id) => map.getLayer(id));

const catFilter = (): maplibregl.FilterSpecification | null =>
  cat === "all" ? null : ["==", ["get", "cat"], cat];

function ensureLayer(def: SourceDef): void {
  if (map.getLayer(layerId(def.key))) return;
  if (!map.getSource(def.key)) {
    map.addSource(def.key, { type: "vector", url: `pmtiles://./${def.file}` });
  }
  // filter は「無し」を undefined で渡すと MapLibre のバリデーションが落ちるため、
  // 全カテゴリ表示のときはキー自体を持たせない。
  const f = catFilter();
  const spec: maplibregl.CircleLayerSpecification = {
    id: layerId(def.key),
    type: "circle",
    source: def.key,
    "source-layer": def.sourceLayer,
    paint: {
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 5, 1.5, 12, 4, 16, 6],
      "circle-color": def.color,
      "circle-opacity": def.opacity,
      "circle-stroke-width": 0.4,
      "circle-stroke-color": haloColor(base, theme),
    },
  };
  if (f) spec.filter = f;
  map.addLayer(spec);
}

function removeLayer(def: SourceDef): void {
  if (map.getLayer(layerId(def.key))) map.removeLayer(layerId(def.key));
  if (map.getSource(def.key)) map.removeSource(def.key);
}

/** 有効なソースだけを地図に載せる。無効なものはソースごと持たない＝軽量。 */
function addDataLayers(): void {
  for (const def of SOURCES) {
    if (def.on) ensureLayer(def);
    else removeLayer(def);
  }
}

// 背景スタイルを差し替える。ラスタ（写真）↔ベクタ（淡色）の切替では diff 適用が
// 効かないため diff:false で完全に再構築し、描画が落ち着く idle でデータ層を貼り直す。
function reloadStyle(): void {
  map.setStyle(getBasemapStyle(base, theme), { diff: false });
  map.once("idle", () => addDataLayers());
}

// ---- テーマ切替 ----

const themeBtn = document.getElementById("theme-btn") as HTMLButtonElement;
const renderThemeBtn = (): void => {
  themeBtn.textContent = theme === "dark" ? "☀️" : "🌙";
};
themeBtn.addEventListener("click", () => {
  theme = theme === "dark" ? "light" : "dark";
  applyThemeAttr(theme);
  renderThemeBtn();
  reloadStyle();
});

// ---- パネル開閉 ----

const panel = document.getElementById("panel") as HTMLElement;
const collapseBtn = document.getElementById("collapse-btn") as HTMLButtonElement;
const renderCollapseBtn = (): void => {
  collapseBtn.textContent = panel.classList.contains("collapsed") ? "▾" : "▴";
};
collapseBtn.addEventListener("click", () => {
  panel.classList.toggle("collapsed");
  renderCollapseBtn();
});

// ---- カテゴリチップ（単一選択） ----

const catsDiv = document.getElementById("cats") as HTMLElement;

function buildChips(): void {
  for (const c of CATEGORIES) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "chip";
    btn.textContent = c.label;
    btn.dataset.cat = c.key;
    btn.setAttribute("aria-pressed", String(c.key === cat));
    btn.addEventListener("click", () => setCategory(c.key));
    catsDiv.append(btn);
  }
}

function setCategory(next: string): void {
  cat = next;
  for (const btn of catsDiv.querySelectorAll<HTMLButtonElement>(".chip")) {
    btn.setAttribute("aria-pressed", String(btn.dataset.cat === cat));
  }
  const f = catFilter();
  for (const def of SOURCES) {
    if (map.getLayer(layerId(def.key))) map.setFilter(layerId(def.key), f);
  }
  renderCounts();
}

// ---- ソーストグル（件数バッジ＋不透明度） ----

const layersDiv = document.getElementById("layers") as HTMLElement;

function buildToggles(): void {
  for (const def of SOURCES) {
    const item = document.createElement("div");
    item.className = "layer-item";
    item.dataset.key = def.key;

    const label = document.createElement("label");
    label.className = "toggle";

    // checkbox は必ずこのラベル内に閉じ込める（視覚非表示は position:absolute）。
    // パネル外を基準にするとフォーカス移動でパネルのスクロールが壊れる。
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = def.on;
    input.addEventListener("change", () => setSourceVisible(def, input.checked));

    const sw = document.createElement("span");
    sw.className = "switch";

    const dot = document.createElement("span");
    dot.className = "src-dot";
    dot.style.background = def.color;

    const text = document.createElement("span");
    text.className = "t-label";
    text.textContent = def.name;
    if (def.note) {
      const note = document.createElement("span");
      note.className = "t-note";
      note.textContent = def.note;
      text.append(note);
    }

    const count = document.createElement("span");
    count.className = "count";

    label.append(input, sw, dot, text, count);

    const opac = document.createElement("div");
    opac.className = "layer-opacity";
    opac.hidden = !def.on;
    const range = document.createElement("input");
    range.type = "range";
    range.min = "0.1";
    range.max = "1";
    range.step = "0.05";
    range.value = String(def.opacity);
    range.setAttribute("aria-label", `${def.name}の不透明度`);
    const val = document.createElement("span");
    val.className = "op-val";
    val.textContent = `${Math.round(def.opacity * 100)}%`;
    range.addEventListener("input", () => {
      const v = Number(range.value);
      val.textContent = `${Math.round(v * 100)}%`;
      setSourceOpacity(def, v);
    });
    opac.append(range, val);

    item.append(label, opac);
    layersDiv.append(item);
  }
}

function renderCounts(): void {
  for (const def of SOURCES) {
    const el = layersDiv.querySelector<HTMLElement>(`.layer-item[data-key="${def.key}"] .count`);
    if (el) el.textContent = countOf(cat, def.key).toLocaleString("ja-JP");
  }
}

function setSourceVisible(def: SourceDef, on: boolean): void {
  def.on = on;
  if (on) ensureLayer(def);
  else removeLayer(def);
  const item = layersDiv.querySelector<HTMLElement>(`.layer-item[data-key="${def.key}"]`);
  item?.querySelector<HTMLElement>(".layer-opacity")?.toggleAttribute("hidden", !on);
  item?.classList.toggle("off", !on);
}

function setSourceOpacity(def: SourceDef, v: number): void {
  def.opacity = v;
  const id = layerId(def.key);
  if (map.getLayer(id)) map.setPaintProperty(id, "circle-opacity", v);
}

function setAll(on: boolean): void {
  for (const def of SOURCES) {
    if (def.on === on) continue;
    const input = layersDiv.querySelector<HTMLInputElement>(`.layer-item[data-key="${def.key}"] input`);
    if (input) input.checked = on;
    setSourceVisible(def, on);
  }
}
(document.getElementById("all-on") as HTMLButtonElement).addEventListener("click", () => setAll(true));
(document.getElementById("all-off") as HTMLButtonElement).addEventListener("click", () => setAll(false));

// ---- 背景地図スイッチャー（右下） ----

class BasemapControl implements maplibregl.IControl {
  private el!: HTMLElement;
  onAdd(): HTMLElement {
    this.el = document.createElement("div");
    this.el.className = "maplibregl-ctrl basemap-switch";
    const defs: [Basemap, string][] = [
      ["pale", "地図"],
      ["photo", "写真"],
    ];
    for (const [b, label] of defs) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = label;
      btn.dataset.base = b;
      btn.setAttribute("aria-selected", String(b === base));
      btn.addEventListener("click", () => setBase(b));
      this.el.append(btn);
    }
    return this.el;
  }
  onRemove(): void {
    this.el.remove();
  }
  sync(): void {
    for (const btn of this.el.querySelectorAll<HTMLButtonElement>("button")) {
      btn.setAttribute("aria-selected", String(btn.dataset.base === base));
    }
  }
}
const basemapCtrl = new BasemapControl();
map.addControl(basemapCtrl, "bottom-right");

function setBase(next: Basemap): void {
  if (next === base) return;
  base = next;
  basemapCtrl.sync();
  reloadStyle();
}

// ---- ホバーカーソル / クリックポップアップ ----

if (window.matchMedia("(hover: hover)").matches) {
  map.on("mousemove", (e) => {
    const ids = activeLayerIds();
    const hit = ids.length > 0 && map.queryRenderedFeatures(e.point, { layers: ids }).length > 0;
    map.getCanvas().style.cursor = hit ? "pointer" : "";
  });
}

map.on("click", (e) => {
  const ids = activeLayerIds();
  if (!ids.length) return;
  const f = map.queryRenderedFeatures(e.point, { layers: ids })[0];
  if (!f) return;
  const def = defOf(f.layer.id);
  if (!def) return;
  new maplibregl.Popup({ closeButton: true, maxWidth: "280px", offset: 8 })
    .setLngLat(e.lngLat)
    .setHTML(popupHtml(def, f.properties as Record<string, unknown>))
    .addTo(map);
});

// ---- 初期化 ----

const buildEl = document.getElementById("build-ver");
if (buildEl) buildEl.textContent = `build: ${__BUILD_TIME__}`;
renderThemeBtn();
buildChips();
buildToggles();
renderCounts();
// スマホは初期状態でパネルを畳んで地図を広く見せる
if (isMobile) panel.classList.add("collapsed");
renderCollapseBtn();
map.on("load", addDataLayers);

// WebGL コンテキスト消失からの復帰。iOS Safari 等ではメモリ逼迫で GL コンテキストが
// 失われ、点レイヤーが消えたまま戻らないことがある。復帰時に貼り直して自動回復する。
const canvas = map.getCanvas();
canvas.addEventListener("webglcontextlost", (e) => {
  // preventDefault しないと自動復帰イベントが発火しない
  e.preventDefault();
});
canvas.addEventListener("webglcontextrestored", () => {
  if (map.isStyleLoaded()) addDataLayers();
  else map.once("idle", addDataLayers);
});

// デバッグ/外部連携用にマップを公開
(window as unknown as { __map: maplibregl.Map }).__map = map;
