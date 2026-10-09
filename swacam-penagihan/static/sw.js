const CACHE_NAME = 'pln-s2jb-penagihan-v3';
const OFFLINE_URLS = [
  '/',
  '/static/logo-pln.png',
  '/static/manifest.json',
];

// Install: Cache essential assets
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      console.log('[SW] Caching app shell');
      return cache.addAll(OFFLINE_URLS);
    })
  );
  self.skipWaiting();
});

// Activate: Cleanup old caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Fetch: Network-first for API, Cache-first for static assets
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  
  // Skip non-GET requests (POST uploads etc.)
  if (event.request.method !== 'GET') return;
  
  // API requests: always network-first
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/download/')) {
    event.respondWith(
      fetch(event.request).catch(() => {
        return new Response(JSON.stringify({
          error: true,
          detail: 'Anda sedang offline. Data akan disinkronkan saat terhubung kembali.'
        }), {
          headers: { 'Content-Type': 'application/json' },
          status: 503
        });
      })
    );
    return;
  }
  
  // Static assets: Cache-first, fallback to network
  event.respondWith(
    caches.match(event.request).then(cached => {
      if (cached) return cached;
      return fetch(event.request).then(response => {
        // Cache successful GET requests for static files
        if (response.status === 200 && (url.pathname.startsWith('/static/') || url.pathname === '/')) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        }
        return response;
      });
    }).catch(() => {
      // Ultimate fallback - return cached root page
      return caches.match('/');
    })
  );
});