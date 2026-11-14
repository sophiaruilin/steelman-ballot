// Offline support: the app shell is cached; the last ballot and cards you opened stay readable
// with no connection (for example at the polling place). API calls: network first, cache fallback.
const SHELL = "sb-shell-v2";
const DATA = "sb-data-v1";
const SHELL_FILES = ["/", "/app.css", "/app.js", "/i18n.js", "/icon.svg", "/manifest.webmanifest",
  "/fonts/eb-garamond-latin-500-normal.woff2", "/fonts/ibm-plex-sans-latin-400-normal.woff2"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(SHELL).then((c) => c.addAll(SHELL_FILES)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((keys) =>
    Promise.all(keys.filter((k) => ![SHELL, DATA].includes(k)).map((k) => caches.delete(k)))
  ).then(() => self.clients.claim()));
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  if (url.pathname.startsWith("/api/card/")) {
    e.respondWith(fetch(e.request).then((r) => {
      if (r.ok) { const copy = r.clone(); caches.open(DATA).then((c) => c.put(e.request, copy)); }
      return r;
    }).catch(() => caches.match(e.request)));
    return;
  }
  if (url.pathname.startsWith("/api/")) return;   // ballot lookups contain an address: never cached
  // App files: network first (so updates show right away), cached copy when offline.
  e.respondWith(fetch(e.request).then((r) => {
    if (r.ok) { const copy = r.clone(); caches.open(SHELL).then((c) => c.put(e.request, copy)); }
    return r;
  }).catch(() => caches.match(e.request)));
});
