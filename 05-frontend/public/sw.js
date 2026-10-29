/* YupReserved service worker — makes the site installable and usable on a poor connection.
 *
 *  app shell & built assets  → cache first (they are content-hashed, so never stale)
 *  /api/*                    → network first, falling back to the last good answer
 *  photos (Wikimedia)        → cache first, kept to the 120 most recent
 *  page navigations          → network first, falling back to the cached app shell
 */
const VERSION = "yup-v2";
const SHELL = ["/", "/manifest.webmanifest", "/favicon.svg", "/icons/icon-192.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => !k.startsWith(VERSION)).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

async function trim(cacheName, max) {
  const c = await caches.open(cacheName);
  const keys = await c.keys();
  for (let i = 0; i < keys.length - max; i++) await c.delete(keys[i]);
}

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;                       // bookings, payments, OTP: always live
  const url = new URL(req.url);

  if (url.pathname.startsWith("/api/lab/") || url.pathname.startsWith("/api/auth")) return;

  if (url.pathname.startsWith("/api/")) {
    e.respondWith(
      fetch(req).then((res) => {
        if (res.ok) caches.open(`${VERSION}-api`).then((c) => c.put(req, res.clone()));
        return res;
      }).catch(() => caches.match(req).then((r) => r || new Response(
        JSON.stringify({ error: "You're offline — this page hasn't been saved yet." }),
        { status: 503, headers: { "content-type": "application/json" } }))),
    );
    return;
  }

  if (url.hostname.endsWith("wikimedia.org")) {
    e.respondWith(caches.open(`${VERSION}-img`).then(async (c) => {
      const hit = await c.match(req);
      if (hit) return hit;
      const res = await fetch(req);
      if (res.ok || res.type === "opaque") { c.put(req, res.clone()); trim(`${VERSION}-img`, 120); }
      return res;
    }));
    return;
  }

  if (url.origin !== location.origin) return;

  if (req.mode === "navigate") {
    e.respondWith(fetch(req).then((res) => {
      caches.open(VERSION).then((c) => c.put("/", res.clone()));
      return res;
    }).catch(() => caches.match("/")));
    return;
  }

  e.respondWith(caches.match(req).then((hit) => hit || fetch(req).then((res) => {
    if (res.ok && url.pathname.startsWith("/assets/")) caches.open(VERSION).then((c) => c.put(req, res.clone()));
    return res;
  })));
});
