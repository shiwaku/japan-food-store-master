import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

// GitHub Pages プロジェクトページのため base にリポジトリ名を指定
export default defineConfig({
  base: "/japan-food-store-master/",
  // エントリは viewer/index.html（Vite 既定）。
  define: {
    __BUILD_TIME__: JSON.stringify(new Date().toISOString().replace("T", " ").slice(0, 16) + " UTC"),
  },
  plugins: [
    VitePWA({
      registerType: "autoUpdate",
      // PMTiles はプリキャッシュしない（巨大 & HTTP Range 配信を壊さないため）
      workbox: {
        globPatterns: ["**/*.{js,css,html,png,json}"],
        // permit_gapfill.json は 4MB の確認用レイヤで**既定 OFF**。json が
        // globPatterns に入っている（webmanifest 用）ので、明示的に除外しないと
        // 全訪問者が初回に 4MB を落とすことになる。
        globIgnores: ["**/*.pmtiles", "**/permit_gapfill.json"],
        maximumFileSizeToCacheInBytes: 6 * 1024 * 1024,
        // 地図データ・タイルは runtime キャッシュせずネットワーク直通
        navigateFallback: null,
      },
      includeAssets: ["icon-192.png", "icon-512.png", "apple-touch-icon.png"],
      manifest: {
        name: "食品店POI比較: OSM vs Overture",
        short_name: "食品店POI比較",
        description:
          "農水省「食料品アクセス」定義準拠の食品店POIを、OSMとOverture Placesで網羅性比較",
        start_url: "./index.html",
        scope: "./",
        display: "standalone",
        background_color: "#ffffff",
        theme_color: "#2a78d6",
        lang: "ja",
        icons: [
          { src: "./icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
          { src: "./icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
          { src: "./icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
      },
    }),
  ],
});
