const CACHE_NAME = 'shakshuka-companion-v1';

// Minimal offline shell. This will work after the page is loaded once.
const CORE_ASSETS = [
  '/companion',
  '/static/images/icon.png',
  '/companion/manifest.webmanifest',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(CORE_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.map((k) => (k === CACHE_NAME ? Promise.resolve() : caches.delete(k))))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Only handle our app scope
  if (!url.pathname.startsWith('/companion')) return;

  event.respondWith(
    fetch(event.request)
      .then((resp) => {
        // Cache successful GET responses for offline use
        if (event.request.method === 'GET' && resp && resp.status === 200) {
          const copy = resp.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
        }
        return resp;
      })
      .catch(() => caches.match(event.request).then((r) => r || caches.match('/companion')))
  );
});
