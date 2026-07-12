// Service Worker — アプリシェルのみキャッシュ。
// 地図タイル(.pmtiles/.pbf)・Range要求・外部タイルはネットワーク直通(SWは介入しない)。
// これによりPMTilesのHTTP Range配信を壊さない。
const CACHE = "poi-compare-v1";
const SHELL = [
  "./compare.html",
  "./pale.json",
  "./manifest.webmanifest",
  "./icon-192.png",
  "./icon-512.png",
  "https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js",
  "https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css",
  "https://unpkg.com/pmtiles@3.2.1/dist/pmtiles.js"
];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  const url = new URL(req.url);

  // 地図データ・Range要求・GSIタイルはSWを通さずネットワーク直通
  if (
    req.method !== "GET" ||
    req.headers.has("range") ||
    url.pathname.endsWith(".pmtiles") ||
    url.pathname.endsWith(".pbf") ||
    url.hostname.includes("cyberjapandata") ||
    url.hostname.includes("gsi-cyberjapan") ||
    url.hostname.includes("gsi.go.jp")
  ) {
    return; // デフォルトのネットワーク処理に任せる
  }

  // HTML(ナビゲーション)は network-first（更新を即反映、オフライン時はキャッシュ）
  const isHTML = req.mode === "navigate" ||
    (req.headers.get("accept") || "").includes("text/html");
  if (isHTML) {
    e.respondWith(
      fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(req, copy));
        return res;
      }).catch(() => caches.match(req).then((c) => c || caches.match("./compare.html")))
    );
    return;
  }

  // その他アプリシェル(JS/CSS/アイコン/style): cache-first、無ければ取得しキャッシュ
  e.respondWith(
    caches.match(req).then((cached) => {
      const net = fetch(req).then((res) => {
        if (res && res.ok && (res.type === "basic" || res.type === "cors")) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy));
        }
        return res;
      }).catch(() => cached);
      return cached || net;
    })
  );
});
