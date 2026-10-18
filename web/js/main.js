// Argus UI - start up.
render(); setInterval(refresh, 15000);
if ('serviceWorker' in navigator && location.protocol === 'https:') navigator.serviceWorker.register(url('sw.js')).catch(() => {});
