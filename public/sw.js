const CACHE_NAME = "imprint-v5";
const MAX_CACHE_ITEMS = 80;
const ASSETS_TO_CACHE = [
  "/",
  "/manifest.json",
  "/favicon.png",
  "/icons/icon-72.png",
  "/icons/icon-96.png",
  "/icons/icon-128.png",
  "/icons/icon-144.png",
  "/icons/icon-152.png",
  "/icons/icon-180.png",
  "/icons/icon-192.png",
  "/icons/icon-384.png",
  "/icons/icon-512.png",
];

// Only cache static assets and navigations
const shouldCache = (url) => {
  const path = new URL(url).pathname;
  return (
    path === "/" ||
    path === "/manifest.json" ||
    path.startsWith("/icons/") ||
    path === "/favicon.png" ||
    path.startsWith("/_next/static/") ||
    path.endsWith(".css") ||
    path.endsWith(".woff2")
  );
};

// Trim cache to prevent unbounded growth
const trimCache = async (name, max) => {
  const cache = await caches.open(name);
  const keys = await cache.keys();
  if (keys.length > max) {
    await Promise.all(
      keys.slice(0, keys.length - max).map((k) => cache.delete(k))
    );
  }
};

// Install — cache essential assets
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS_TO_CACHE))
  );
  self.skipWaiting();
});

// Activate — clean old caches
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Fetch — network-first with cache fallback
self.addEventListener("fetch", (event) => {
  // Skip non-GET and cross-origin requests
  if (event.request.method !== "GET") return;
  if (!event.request.url.startsWith(self.location.origin)) return;

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        // Cache successful responses for cacheable assets
        if (response.ok && shouldCache(event.request.url)) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, clone);
            trimCache(CACHE_NAME, MAX_CACHE_ITEMS);
          });
        }
        return response;
      })
      .catch(() => {
        // Offline — serve from cache
        return caches.match(event.request).then((cached) => {
          if (cached) return cached;
          // Fallback to root for navigation requests (SPA)
          if (event.request.mode === "navigate") {
            return caches.match("/");
          }
          return new Response("Offline", { status: 503 });
        });
      })
  );
});
