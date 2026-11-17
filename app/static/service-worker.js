/* EduShare service worker: caches only public static assets.
   Private routes (messages, auth, profile, admin, uploads, API) are never cached. */
const CACHE_NAME = 'edushare-static-v1';
const PUBLIC_ASSETS = [
  // Never precache '/': when signed in it contains personalised content.
  '/offline',
  '/static/css/style.css',
  '/static/js/app.js',
  '/static/vendor/bootstrap-icons/bootstrap-icons.css',
  '/static/vendor/bootstrap-icons/fonts/bootstrap-icons.woff2',
  '/static/images/icon-192.png',
  '/static/images/icon-512.png',
  '/static/images/icon-maskable-512.png',
  '/static/images/default-avatar.svg',
  '/static/manifest.json'
];
const PRIVATE_PREFIXES = [
  '/auth/', '/messages', '/profile', '/notifications', '/admin/',
  '/api/', '/dashboard', '/books/new', '/static/uploads/', '/location'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PUBLIC_ASSETS)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

function isPrivate(url) {
  return PRIVATE_PREFIXES.some((prefix) => url.pathname.startsWith(prefix));
}

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin || isPrivate(url)) return;

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => response)
        // Graceful offline page; never a cached private page.
        .catch(() => caches.match('/offline'))
    );
    return;
  }

  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(request).then((cached) => cached || fetch(request).then((response) => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
        }
        return response;
      }))
    );
  }
});
