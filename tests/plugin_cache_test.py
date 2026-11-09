"""Plugin file caching (4.27.0) without a browser: validators, 304s and the Cache-Control rules, read from raw headers.

    python3 tests/plugin_cache_test.py -v        (tests/run.sh runs it under "== plugin cache"; runs on Windows too)

The server runs in this process on a free port with a temporary plugin folder (a copy of
tests/plugin-fixtures/spartamelee plus a few extra names); nothing outside a temporary folder is touched."""
import http.client, importlib.util, os, shutil, sys, tempfile, threading, time, unittest
from email.utils import formatdate

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = tempfile.mkdtemp(prefix='argus-cache-test-')
PLUG = os.path.join(TMP, 'plugins')
shutil.copytree(os.path.join(R, 'tests', 'plugin-fixtures', 'spartamelee'), os.path.join(PLUG, 'spartamelee'))
EXTRA = {'assets.json': '{}', 'data/roster.json': '{}', 'audio/hit.ogg': 'not a sound', 'thumbs/ares.webp': 'x',
         'ui/menu.0f1e2d3c.webp': 'x', 'app.9a8b7c6d.js': '//', 'models/zeus.1A2B3C4D.glb': 'upper-case hex is not a hash'}
for name, text in EXTRA.items():
    f = os.path.join(PLUG, 'spartamelee', *name.split('/')); os.makedirs(os.path.dirname(f), exist_ok=True)
    with open(f, 'w') as fh: fh.write(text)
os.makedirs(os.path.join(TMP, 'static'))
with open(os.path.join(TMP, 'static', 'theme.json'), 'w') as fh: fh.write('{}')
os.environ.update(ARGUS_PLUGINS=PLUG, ARGUS_BUNDLED=os.path.join(TMP, 'bundled'), ARGUS_STATIC=os.path.join(TMP, 'static'),
                  ARGUS_LINKS=os.path.join(TMP, 'links.json'), ARGUS_REGISTRY=os.path.join(TMP, 'agents'),
                  ARGUS_ALERTS=os.path.join(TMP, 'alerts'))
_spec = importlib.util.spec_from_file_location('argus_ui_under_test', os.path.join(R, 'server', 'argus_ui.py'))
a = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(a)

YEAR, FRESH, HOUR = 'public, max-age=31536000, immutable', 'no-cache', 'max-age=3600'

class PluginCache(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = a.ThreadingHTTPServer(('127.0.0.1', 0), a.H)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown(); cls.srv.server_close(); shutil.rmtree(TMP, ignore_errors=True)

    def get(self, path, **headers):
        # raw request: the path goes out exactly as written (.. included)
        c = http.client.HTTPConnection('127.0.0.1', self.srv.server_address[1], timeout=5)
        c.request('GET', '/argus/' + path, headers={'Host': '127.0.0.1', **headers})
        r = c.getresponse(); body = r.read(); c.close()
        return r.status, {k.lower(): v for k, v in r.getheaders()}, body

    def test_first_get_has_validators(self):
        code, h, body = self.get('plugins/spartamelee/models/ares.1a2b3c4d.glb')
        self.assertEqual(code, 200); self.assertTrue(body)
        self.assertRegex(h['etag'], r'^"[0-9a-f]+-[0-9a-f]+"$')
        self.assertTrue(h['last-modified'].endswith(' GMT'))
        self.assertEqual(h['cache-control'], YEAR)

    def test_if_none_match_gives_304_with_sandbox_headers(self):
        _, h, _ = self.get('plugins/spartamelee/models/ares.1a2b3c4d.glb')
        code, h2, body = self.get('plugins/spartamelee/models/ares.1a2b3c4d.glb', **{'If-None-Match': h['etag']})
        self.assertEqual(code, 304); self.assertEqual(body, b'')
        self.assertEqual(h2['etag'], h['etag']); self.assertEqual(h2['cache-control'], YEAR)
        for k, v in a.PLUGIN_HEADERS.items(): self.assertEqual(h2[k.lower()], v, k)
        # weak form, a list, and * all match; another tag does not
        for inm in ('W/' + h['etag'], '"nope", ' + h['etag'], '*'):
            self.assertEqual(self.get('plugins/spartamelee/models/ares.1a2b3c4d.glb', **{'If-None-Match': inm})[0], 304, inm)
        self.assertEqual(self.get('plugins/spartamelee/models/ares.1a2b3c4d.glb', **{'If-None-Match': '"nope"'})[0], 200)

    def test_if_modified_since(self):
        _, h, _ = self.get('plugins/spartamelee/index.html')
        self.assertEqual(self.get('plugins/spartamelee/index.html', **{'If-Modified-Since': h['last-modified']})[0], 304)
        self.assertEqual(self.get('plugins/spartamelee/index.html', **{'If-Modified-Since': formatdate(0, usegmt=True)})[0], 200)
        self.assertEqual(self.get('plugins/spartamelee/index.html', **{'If-Modified-Since': 'not a date'})[0], 200)
        # If-None-Match wins: a stale tag means a full answer even with a current date
        self.assertEqual(self.get('plugins/spartamelee/index.html', **{'If-Modified-Since': h['last-modified'],
                                                                      'If-None-Match': '"stale"'})[0], 200)

    def test_changed_file_gets_a_new_etag(self):
        f = os.path.join(PLUG, 'spartamelee', 'thumbs', 'ares.webp')
        _, h, _ = self.get('plugins/spartamelee/thumbs/ares.webp')
        with open(f, 'w') as fh: fh.write('a new picture')
        st = os.stat(f); os.utime(f, ns=(st.st_atime_ns, st.st_mtime_ns + 2_000_000_000))
        code, h2, body = self.get('plugins/spartamelee/thumbs/ares.webp', **{'If-None-Match': h['etag']})
        self.assertEqual(code, 200); self.assertEqual(body, b'a new picture'); self.assertNotEqual(h2['etag'], h['etag'])

    def test_cache_rules(self):
        want = {'models/ares.1a2b3c4d.glb': YEAR, 'ui/menu.0f1e2d3c.webp': YEAR, 'app.9a8b7c6d.js': YEAR,
                '': FRESH, 'index.html': FRESH, 'app.js': FRESH, 'assets.json': FRESH, 'data/roster.json': FRESH,
                'data.json': HOUR, 'audio/hit.ogg': HOUR, 'thumbs/ares.webp': HOUR, 'models/zeus.1A2B3C4D.glb': HOUR}
        for name, cache in want.items():
            code, h, _ = self.get('plugins/spartamelee/' + name)
            self.assertEqual((code, h.get('cache-control')), (200, cache), name)
            self.assertIn('etag', h, name); self.assertIn('content-security-policy', h, name)
        self.assertEqual(a.plugin_cache('plugin.json'), FRESH)   # never served, but the rule holds

    def test_traversal_and_private_files_unchanged(self):
        for path in ('plugins/spartamelee/../../static/theme.json', 'plugins/spartamelee/../spartamelee/plugin.json',
                     'plugins/spartamelee/plugin.json', 'plugins/nope/x.js'):
            code, h, _ = self.get(path)
            self.assertEqual(code, 404, path); self.assertNotIn('etag', h, path)
        self.assertEqual(self.get('plugins/spartamelee/plugin.json', **{'If-None-Match': '*'})[0], 404)

if __name__ == '__main__':
    unittest.main()
