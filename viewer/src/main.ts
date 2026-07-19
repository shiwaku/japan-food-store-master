import maplibregl, { type MapGeoJSONFeature } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { Protocol } from "pmtiles";
import "./style.css";

// ── PMTiles プロトコル登録 ──
const protocol = new Protocol();
maplibregl.addProtocol("pmtiles", protocol.tile);

const map = new maplibregl.Map({
  container: "map",
  style: "./pale.json", // 国土地理院 最適化ベクトルタイル（淡色地図風）
  center: [138.5, 36.5],
  zoom: 5,
  maxZoom: 17,
  hash: true,
  attributionControl: false, // 下でカスタム帰属表示を追加（地理院＋各データ出典）
});

// 帰属表示（OSMは ODbL で常時表示が必須。レイヤーON/OFFや表示範囲に依存せず
// 常に出るよう、3出典すべてを customAttribution に集約する）
map.addControl(
  new maplibregl.AttributionControl({
    compact: false,
    customAttribution: [
      '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap contributors</a>（ODbL）',
      '© <a href="https://overturemaps.org/" target="_blank" rel="noopener">Overture Maps Foundation</a>',
      "地図：国土地理院ベクトルタイル",
    ].join(" ｜ "),
  }),
  "bottom-right",
);
map.addControl(new maplibregl.NavigationControl(), "top-right");
// 現在地（GPS）ボタン
map.addControl(
  new maplibregl.GeolocateControl({
    positionOptions: { enableHighAccuracy: true },
    trackUserLocation: true,
    showUserLocation: true,
  }),
  "top-right",
);
// 全画面ボタン
map.addControl(new maplibregl.FullscreenControl(), "top-right");

type LayerDef = { id: string; src: "ovt" | "osm"; sourceLayer: string; color: string; label: string };

const LAYERS: LayerDef[] = [
  { id: "ovt-pt", src: "ovt", sourceLayer: "overture", color: "#1c7ed6", label: "Overture Maps" },
  { id: "osm-pt", src: "osm", sourceLayer: "osm", color: "#e8590c", label: "OpenStreetMap" },
];

map.on("load", () => {
  // 出典は上の AttributionControl(customAttribution) に集約済み（常時表示）
  map.addSource("ovt", { type: "vector", url: "pmtiles://./overture_food.pmtiles" });
  map.addSource("osm", { type: "vector", url: "pmtiles://./osm_food.pmtiles" });

  for (const l of LAYERS) {
    map.addLayer({
      id: l.id,
      type: "circle",
      source: l.src,
      "source-layer": l.sourceLayer,
      paint: {
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 5, 1.5, 12, 4, 16, 6],
        "circle-color": l.color,
        "circle-opacity": 0.7,
        "circle-stroke-width": 0.4,
        "circle-stroke-color": "#fff",
      },
    });

    map.on("click", l.id, (e) => {
      const f = e.features?.[0] as MapGeoJSONFeature | undefined;
      if (!f) return;
      const p = f.properties as Record<string, unknown>;
      const conf = p.confidence != null ? `<br>confidence: ${Number(p.confidence).toFixed(2)}` : "";
      new maplibregl.Popup({ offset: 8 })
        .setLngLat(e.lngLat)
        .setHTML(
          `<b>${(p.name as string) || "(名称なし)"}</b><br>ソース: ${l.label}` +
            `<br>カテゴリ: ${(p.cat_raw as string) || (p.cat as string)}${conf}`,
        )
        .addTo(map);
    });
    map.on("mouseenter", l.id, () => (map.getCanvas().style.cursor = "pointer"));
    map.on("mouseleave", l.id, () => (map.getCanvas().style.cursor = ""));
  }

  // カテゴリ絞り込み
  const catSelect = document.getElementById("cat") as HTMLSelectElement;
  catSelect.addEventListener("change", () => {
    const c = catSelect.value;
    const filter = c === "all" ? null : ["==", ["get", "cat"], c];
    for (const l of LAYERS) map.setFilter(l.id, filter as never);
  });

  // ソース別ON/OFF
  const bind = (checkboxId: string, layerId: string) => {
    const cb = document.getElementById(checkboxId) as HTMLInputElement;
    cb.addEventListener("change", () =>
      map.setLayoutProperty(layerId, "visibility", cb.checked ? "visible" : "none"),
    );
  };
  bind("t-ovt", "ovt-pt");
  bind("t-osm", "osm-pt");
});

// ── パネル開閉 ──
const panel = document.getElementById("panel")!;
const panelOpen = document.getElementById("panel-open")!;
document.getElementById("panel-close")!.addEventListener("click", () => {
  panel.classList.add("collapsed");
  panelOpen.classList.add("show");
});
panelOpen.addEventListener("click", () => {
  panel.classList.remove("collapsed");
  panelOpen.classList.remove("show");
});
