const CACHE_NAME = 'neonstream-v2';
const ASSETS_TO_CACHE = [
    '/',
    '/static/style.css',
    '/static/script.js',
    '/static/manifest.json',
    '/static/icon-192.png',
    '/static/icon-512.png',
    'https://fonts.googleapis.com/css2?family=Orbitron:wght@400;500;700;900&family=Rajdhani:wght@400;500;600;700&display=swap'
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => {
                return cache.addAll(ASSETS_TO_CACHE);
            })
            .catch(err => console.log('Service Worker Cache error:', err))
    );
});

self.addEventListener('fetch', (event) => {
    // Only cache GET requests
    if (event.request.method !== 'GET') return;
    
    // Do not cache API endpoints (like /api/info or /api/download)
    if (event.request.url.includes('/api/')) return;

    event.respondWith(
        caches.match(event.request)
            .then((response) => {
                // Return cached version if found, otherwise fetch from network
                return response || fetch(event.request);
            })
    );
});

self.addEventListener('activate', (event) => {
    // Clean up old caches
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_NAME) {
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
});
