// Argus service worker: lets LeafySovereign install the page as an app. Always fetches live data.
self.addEventListener('install',e=>self.skipWaiting());self.addEventListener('activate',e=>self.clients.claim());self.addEventListener('fetch',()=>{});
