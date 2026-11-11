"""Phone alerts (server/push.py, server/summary.py, docs/phone-alerts.md), no browser:

    python3 tests/push_test.py -v        (tests/run.sh runs it under "== phone alerts")

  * encryption against the worked example of RFC 8291 (fixed keys and salt give its exact bytes), a round trip decrypted
    as a browser would, the VAPID token verified with the public key (RFC 8292);
  * the host rule: only known push services, never a look-alike, user-info, another port, http, an IP address or a redirect;
  * a fake push service on 127.0.0.1 inside this test: 201, 410 removes the device, 500 then 201 retried once, a timeout;
  * the sink's rules: kinds, owners only, 30 minutes, 6 an hour with the one folded message;
  * the daily summary: its words for a calm day, a repaired thing, a waiting yes; once a day across a restart; the 4-hour
    rule; off with ARGUS_SUMMARY=0;
  * the routes on a real server: a learner gets 403, an untrusted request cannot turn alerts on or test, no answer holds an
    endpoint or a key, the files are mode 600 (Linux).
Nothing leaves this machine: every message goes to the fake service. The `cryptography` package is needed; without it the
tests are skipped, except in CI (CI=true), where that is a failure."""
import base64, http.client, http.server, importlib.util, json, os, shutil, stat, sys, tempfile, threading, time, unittest
from datetime import datetime, timedelta, timezone

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = tempfile.mkdtemp(prefix='argus-push-test-')
HOME = os.path.join(TMP, 'home'); CONF = os.path.join(HOME, '.config', 'argus-ui'); STATE = os.path.join(TMP, 'state')
for d in (CONF, STATE): os.makedirs(d, exist_ok=True)
os.environ.update(HOME=HOME, USERPROFILE=HOME, ARGUS_DEV='1', ARGUS_WATCH='0',
                  ARGUS_PUSH_KEY=os.path.join(CONF, 'push-key.pem'), ARGUS_PUSH_DEVICES=os.path.join(STATE, 'push-devices.json'),
                  ARGUS_EVENTS=os.path.join(STATE, 'events.jsonl'), ARGUS_SUMMARY_STATE=os.path.join(STATE, 'summary.json'))
for k in ('ARGUS_PUSH_CONTACT', 'ARGUS_SUMMARY', 'ARGUS_SUMMARY_AT', 'ARGUS_PUSH_TEST_ORIGIN', 'ARGUS_PEOPLE'): os.environ.pop(k, None)
sys.path.insert(0, os.path.join(R, 'server'))
import notify, push, summary

HAVE = push.crypto() is not None
if not HAVE and os.environ.get('CI'):
    print('FAIL: the cryptography package is missing, and in CI the phone-alert tests must run', file=sys.stderr); sys.exit(1)
need = unittest.skipUnless(HAVE, 'the cryptography package is not installed here (CI installs it and runs these)')
if HAVE:
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
u = push.unb64
POSIX = os.name == 'posix'


def wait_for(cond, secs=15, what=''):
    end = time.time() + secs
    while time.time() < end:
        if cond(): return True
        time.sleep(0.05)
    raise AssertionError(f'timed out waiting for {what}')


# ---------- a fake push service on 127.0.0.1 ----------
class Fake:
    """Answers each POST with the next scripted answer (default 201): an int status, ('redirect', where) or 'hang'."""
    def __init__(self):
        fake = self; self.got = []; self.script = []; self.lock = threading.Lock()
        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a): pass
            def do_POST(self):
                body = self.rfile.read(int(self.headers.get('Content-Length') or 0))
                with fake.lock:
                    fake.got.append({'path': self.path, 'headers': {k.lower(): v for k, v in self.headers.items()}, 'body': body})
                    what = fake.script.pop(0) if fake.script else 201
                if what == 'hang': time.sleep(push.TIMEOUT + 1.5); what = 201
                if isinstance(what, tuple):
                    self.send_response(302); self.send_header('Location', what[1]); self.send_header('Content-Length', '0'); self.end_headers(); return
                self.send_response(what); self.send_header('Content-Length', '0'); self.end_headers()
        self.srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.origin = f'http://127.0.0.1:{self.srv.server_address[1]}'
    def reset(self, *script):
        with self.lock: self.got = []; self.script = list(script)


FAKE = Fake()
os.environ['ARGUS_PUSH_TEST_ORIGIN'] = FAKE.origin


def browser():
    """A browser's keys, as pushManager.subscribe() makes them: (private key, p256dh, auth)."""
    k = ec.generate_private_key(ec.SECP256R1())
    return k, k.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint), os.urandom(16)


def decrypt(body, ua_private, auth):
    """RFC 8291 decryption as the browser does it, with the cryptography package's own HKDF (not push.py's)."""
    salt, rs, idlen = body[:16], int.from_bytes(body[16:20], 'big'), body[20]
    as_public, ct = body[21:21 + idlen], body[21 + idlen:]
    ua_public = ua_private.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    ecdh = ua_private.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), as_public))
    ikm = HKDF(hashes.SHA256(), 32, auth, b'WebPush: info\x00' + ua_public + as_public).derive(ecdh)
    cek = HKDF(hashes.SHA256(), 16, salt, b'Content-Encoding: aes128gcm\x00').derive(ikm)
    nonce = HKDF(hashes.SHA256(), 12, salt, b'Content-Encoding: nonce\x00').derive(ikm)
    pt = AESGCM(cek).decrypt(nonce, ct, None).rstrip(b'\x00')
    assert pt.endswith(b'\x02') and rs == 4096, 'last record delimiter'
    return pt[:-1]


def add_device(person='owner', kinds=push.KINDS, label='Android phone, Chrome', tail=None):
    k, p256dh, auth = browser()
    endpoint = f'{FAKE.origin}/send/{tail or os.urandom(6).hex()}'
    code, d = push.subscribe(person, {'subscription': {'endpoint': endpoint, 'keys': {'p256dh': push.b64(p256dh), 'auth': push.b64(auth)}},
                                      'label': label, 'kinds': list(kinds)}, True)
    assert code == 200, d
    return d['id'], k, auth, endpoint


def devices(): return push.load_devices()


def clean():
    for f in (os.environ['ARGUS_PUSH_DEVICES'], os.environ['ARGUS_SUMMARY_STATE'], os.environ['ARGUS_EVENTS']):
        if os.path.exists(f): os.remove(f)
    push.gate.__init__(); push._tests.clear(); FAKE.reset()


# ---------- RFC 8291 / RFC 8292 ----------
@need
class Encryption(unittest.TestCase):
    # RFC 8291 section 5 and Appendix A
    AS_PRIVATE, AS_PUBLIC = 'yfWPiYE-n46HLnH0KqZOF1fJJU3MYrct3AELtAQ-oRw', 'BP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27mlmlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A8'
    UA_PRIVATE, UA_PUBLIC = 'q1dXpw3UpT5VOmu_cf_v6ih07Aems3njxI-JWgLcM94', 'BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcxaOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4'
    AUTH, SALT = 'BTBZMqHH6r4Tts7J_aSIgg', 'DGv6ra1nlYgDCS1FRnbzlw'
    PLAIN = b'When I grow up, I want to be a watermelon'
    RESULT = ('DGv6ra1nlYgDCS1FRnbzlwAAEABBBP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27ml'
              'mlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A_yl95bQpu6cVPT'
              'pK4Mqgkf1CXztLVBSt2Ks3oZwbuwXPXLWyouBWLVWGNWQexSgSxsj_Qulcy4a-fN')

    def key(self, d): return ec.derive_private_key(int.from_bytes(u(d), 'big'), ec.SECP256R1())

    def test_rfc8291_worked_example_exact_bytes(self):
        a = self.key(self.AS_PRIVATE)
        self.assertEqual(push.b64(push.point(a.public_key())), self.AS_PUBLIC)
        self.assertEqual(u('V2hlbiBJIGdyb3cgdXAsIEkgd2FudCB0byBiZSBhIHdhdGVybWVsb24'), self.PLAIN)
        body = push.encrypt(self.PLAIN, u(self.UA_PUBLIC), u(self.AUTH), as_private=a, salt=u(self.SALT))
        self.assertEqual(push.b64(body), self.RESULT)
        self.assertEqual(len(body), 144)

    def test_rfc8291_intermediate_values(self):
        a, ua = self.key(self.AS_PRIVATE), u(self.UA_PUBLIC)
        ecdh = a.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua))
        self.assertEqual(push.b64(ecdh), 'kyrL1jIIOHEzg3sM2ZWRHDRB62YACZhhSlknJ672kSs')
        prk_key = push._extract(u(self.AUTH), ecdh)
        self.assertEqual(push.b64(prk_key), 'Snr3JMxaHVDXHWJn5wdC52WjpCtd2EIEGBykDcZW32k')
        ikm = push._expand(prk_key, b'WebPush: info\x00' + ua + u(self.AS_PUBLIC), 32)
        self.assertEqual(push.b64(ikm), 'S4lYMb_L0FxCeq0WhDx813KgSYqU26kOyzWUdsXYyrg')
        prk = push._extract(u(self.SALT), ikm)
        self.assertEqual(push.b64(prk), '09_eUZGrsvxChDCGRCdkLiDXrReGOEVeSCdCcPBSJSc')
        self.assertEqual(push.b64(push._expand(prk, b'Content-Encoding: aes128gcm\x00', 16)), 'oIhVW04MRdy2XN9CiKLxTg')
        self.assertEqual(push.b64(push._expand(prk, b'Content-Encoding: nonce\x00', 12)), '4h_95klXJ5E_qnoN')

    def test_the_browser_side_of_the_example_decrypts_it(self):
        self.assertEqual(decrypt(u(self.RESULT), self.key(self.UA_PRIVATE), u(self.AUTH)), self.PLAIN)

    def test_round_trip_with_fresh_keys(self):
        k, p256dh, auth = browser()
        msg = json.dumps({'title': 'Media player runs, but cannot read its drive', 'body': 'Ünïcødé ✓'}).encode()
        a, b = push.encrypt(msg, p256dh, auth), push.encrypt(msg, p256dh, auth)
        self.assertNotEqual(a, b, 'a fresh key and salt every time')
        self.assertEqual(decrypt(a, k, auth), msg)
        self.assertEqual(decrypt(b, k, auth), msg)
        with self.assertRaises(Exception): decrypt(a, browser()[0], auth)       # another browser cannot read it

    def test_vapid_token_verifies_with_the_public_key(self):
        h = push.vapid('https://fcm.googleapis.com/fcm/send/abc:def', now=1_800_000_000)
        self.assertTrue(h.startswith('vapid t='))
        t, k = h[len('vapid t='):].split(', k=')
        head, claims, sig = t.split('.')
        self.assertEqual(json.loads(u(head)), {'typ': 'JWT', 'alg': 'ES256'})
        c = json.loads(u(claims))
        self.assertEqual(c, {'aud': 'https://fcm.googleapis.com', 'exp': 1_800_000_000 + 12 * 3600, 'sub': push.DEFAULT_CONTACT})
        self.assertEqual(k, push.public_key())
        pub = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), u(k))
        raw = u(sig); self.assertEqual(len(raw), 64)
        pub.verify(encode_dss_signature(int.from_bytes(raw[:32], 'big'), int.from_bytes(raw[32:], 'big')), f'{head}.{claims}'.encode(), ec.ECDSA(hashes.SHA256()))
        with self.assertRaises(Exception):
            pub.verify(encode_dss_signature(int.from_bytes(raw[:32], 'big'), int.from_bytes(raw[32:], 'big')), f'{head}.{claims}x'.encode(), ec.ECDSA(hashes.SHA256()))

    def test_contact_setting(self):
        for bad in ('elaia@example.com', 'https://elaia.your-tailnet.ts.net/', 'javascript:x'):
            os.environ['ARGUS_PUSH_CONTACT'] = bad; self.assertEqual(push.contact(), push.DEFAULT_CONTACT, bad)
        os.environ['ARGUS_PUSH_CONTACT'] = 'mailto:someone@example.org'; self.assertEqual(push.contact(), 'mailto:someone@example.org')
        os.environ.pop('ARGUS_PUSH_CONTACT')

    def test_the_key_is_made_once_kept_mode_600_and_reused(self):
        p = os.environ['ARGUS_PUSH_KEY']; first = push.public_key()
        self.assertTrue(os.path.isfile(p))
        if POSIX: self.assertEqual(stat.S_IMODE(os.stat(p).st_mode), 0o600)
        push._key.clear()
        self.assertEqual(push.public_key(), first, 'read back from the file, not made again')
        self.assertEqual([n for n in os.listdir(os.path.dirname(p)) if n.endswith('.tmp')], [], 'no temp file left behind')


class Hosts(unittest.TestCase):
    def test_known_push_services(self):
        for e in ('https://fcm.googleapis.com/fcm/send/abc', 'https://fcm.googleapis.com/wp/abc',
                  'https://updates.push.services.mozilla.com/wpush/v2/abc', 'https://wns2-by3p.notify.windows.com/w/?token=abc',
                  'https://web.push.apple.com/QGuQyavXutnMH', 'https://FCM.googleapis.com/fcm/send/abc'):
            self.assertTrue(push.endpoint_ok(e), e)

    def test_everything_else_is_refused(self):
        os.environ.pop('ARGUS_PUSH_TEST_ORIGIN', None)
        try:
            for e in ('https://fcm.googleapis.com.evil.example/fcm/send/abc', 'https://evilfcm.googleapis.com/x', 'https://googleapis.com/x',
                      'https://push.services.mozilla.com.evil.example/x', 'https://evilpush.services.mozilla.com/x', 'https://push.services.mozilla.com/x',
                      'https://notify.windows.com/x', 'https://evil.example/fcm.googleapis.com', 'https://evil.example/?h=.push.apple.com',
                      'https://fcm.googleapis.com@evil.example/x', 'https://user:pw@fcm.googleapis.com/x', 'https://evil.example@fcm.googleapis.com/x',   # private-ok: user-info tricks
                      'https://fcm.googleapis.com:8443/x', 'https://fcm.googleapis.com:80/x', 'http://fcm.googleapis.com/x',
                      'ftp://fcm.googleapis.com/x', 'https://192.0.2.1/x', 'https://[2001:db8::1]/x', 'https://fcm.googleapis.com./x',
                      'https://fcm.googleapis.com\\@evil.example/x', 'https://fcm.googleapis.com /x', '//fcm.googleapis.com/x',
                      'https://fcm.googleapis.com:443:80/x', 'https://fcm.googleapis.com:443/x', 'https://fcm.googleapis.com:/x', 'https://fcm.googleapis.com:0443/x', 'https://xn--fcm-xyz.googleapis.co/x', '', None, 42,
                      'http://127.0.0.1:9/x', 'https://127.0.0.1/x', 'https://localhost/x', 'https://' + 'a' * 1100 + '.push.apple.com/x'):
                self.assertFalse(push.endpoint_ok(e), e)
        finally: os.environ['ARGUS_PUSH_TEST_ORIGIN'] = FAKE.origin

    def test_the_test_service_only_with_ARGUS_DEV(self):
        self.assertTrue(push.endpoint_ok(FAKE.origin + '/send/x'))
        os.environ.pop('ARGUS_DEV')
        try: self.assertFalse(push.endpoint_ok(FAKE.origin + '/send/x'), 'without ARGUS_DEV the test address is just an http address')
        finally: os.environ['ARGUS_DEV'] = '1'
        os.environ['ARGUS_PUSH_TEST_ORIGIN'] = 'http://192.0.2.7:8080'
        try: self.assertFalse(push.endpoint_ok('http://192.0.2.7:8080/send/x'), 'the test address must be this machine')
        finally: os.environ['ARGUS_PUSH_TEST_ORIGIN'] = FAKE.origin


# ---------- sending, against the fake service ----------
@need
class Sending(unittest.TestCase):
    def setUp(self):
        clean(); push.RETRY_AFTER = 0.4; push.TIMEOUT = 1.0

    def send(self, did, kind='broke', subject='media'):
        ev = notify.make(kind, subject, 'Media player runs, but cannot read its drive', 'The drive was unplugged and came back.', 'argus')
        push.sender.put({'device': did, 'raw': push.message(ev), 'kind': kind, 'subject': subject})
        return ev

    def test_201_accepted_with_the_right_headers_and_a_readable_message(self):
        did, k, auth, endpoint = add_device()
        ev = self.send(did)
        wait_for(lambda: devices()[0]['last_ok'], what='last_ok')
        self.assertEqual(len(FAKE.got), 1); g = FAKE.got[0]
        self.assertEqual(g['path'], '/send/' + endpoint.rsplit('/', 1)[1])
        h = g['headers']
        self.assertEqual((h['ttl'], h['urgency'], h['content-encoding']), (str(6 * 3600), 'high', 'aes128gcm'))
        self.assertEqual(h['topic'], push.topic('media')); self.assertLessEqual(len(h['topic']), 32)
        self.assertRegex(h['topic'], r'^[A-Za-z0-9_-]+$')
        self.assertTrue(h['authorization'].startswith('vapid t=') and ', k=' + push.public_key() in h['authorization'])
        m = json.loads(decrypt(g['body'], k, auth))
        self.assertEqual(m, {'id': ev['id'], 'kind': 'broke', 'title': ev['title'], 'body': ev['body'], 'url': 'argus', 'at': ev['at'], 'tag': 'media'})
        self.assertEqual(devices()[0]['last_error'], '')

    def test_410_removes_the_device(self):
        did = add_device()[0]; FAKE.reset(410); self.send(did)
        wait_for(lambda: not devices(), what='the device to go')

    def test_404_removes_the_device_too(self):
        did = add_device()[0]; FAKE.reset(404); self.send(did)
        wait_for(lambda: not devices(), what='the device to go')

    def test_500_then_201_is_retried_once(self):
        did = add_device()[0]; FAKE.reset(500, 201); self.send(did)
        wait_for(lambda: devices()[0]['last_ok'], what='the retry')
        self.assertEqual(len(FAKE.got), 2); self.assertEqual(devices()[0]['last_error'], '')

    def test_429_twice_gives_up_with_plain_words(self):
        did = add_device()[0]; FAKE.reset(429, 429, 201); self.send(did)
        wait_for(lambda: devices()[0]['last_error'], what='last_error')
        time.sleep(push.RETRY_AFTER + 0.3)
        self.assertEqual(len(FAKE.got), 2, 'one more try, not a third')
        self.assertIn('asked Elaia to wait', devices()[0]['last_error'])

    def test_a_timeout_twice(self):
        did = add_device()[0]; FAKE.reset('hang', 'hang'); self.send(did)
        wait_for(lambda: devices()[0]['last_error'], secs=20, what='the timeout')
        self.assertEqual(len(FAKE.got), 2)
        self.assertEqual(devices()[0]['last_error'], push.say_failure('timeout'))

    def test_a_redirect_is_not_followed(self):
        did = add_device()[0]; FAKE.reset(('redirect', FAKE.origin + '/elsewhere'), 201); self.send(did)
        wait_for(lambda: devices()[0]['last_error'], what='last_error')
        time.sleep(0.3)
        self.assertEqual([g['path'] for g in FAKE.got if g['path'] == '/elsewhere'], [], 'nothing was sent to the new address')
        self.assertEqual(len(FAKE.got), 1); self.assertIn('never follows', devices()[0]['last_error'])

    def test_an_endpoint_that_became_unknown_is_not_called(self):
        did = add_device()[0]
        ds = devices(); ds[0]['endpoint'] = 'https://evil.example/send/x'; push.save_devices(ds)
        self.send(did); wait_for(lambda: devices()[0]['last_error'], what='last_error')
        self.assertEqual(FAKE.got, [])

    def test_the_message_is_at_most_2000_bytes(self):
        for body in ('x' * 5000, 'é✓' * 3000, '"' * 3000):
            raw = push.message({'id': 'a', 'kind': 'broke', 'subject': 's', 'title': 'T', 'body': body, 'url': '', 'at': ''})
            self.assertLessEqual(len(raw), push.MAX_MESSAGE)
            m = json.loads(raw); self.assertTrue(m['body'].endswith('…')); self.assertEqual(m['title'], 'T')


# ---------- the sink: what buzzes ----------
class Recorder:
    def __init__(self): self.jobs = []
    def put(self, job): self.jobs.append(job)


@need
class Sink(unittest.TestCase):
    def setUp(self):
        clean(); self.t = [1000.0]; push.clock = lambda: self.t[0]
        self.real, push.sender = push.sender, Recorder()
        push.role_of = lambda person: {'owner': 'owner', 'owner-two': 'owner', 'learner-two': 'learner'}.get(person, 'none')
    def tearDown(self):
        push.sender = self.real; push.clock = time.monotonic

    def ev(self, kind='broke', subject='media'):
        return notify.make(kind, subject, f'{subject} {kind}', 'body', 'argus')

    def kinds_sent(self): return [(j['kind'], j['device']) for j in push.sender.jobs]

    def test_only_three_kinds_buzz(self):
        did = add_device()[0]
        for k in ('fixed', 'recovered'): push.sink(self.ev(k))
        self.assertEqual(push.sender.jobs, [], 'a repair or a recovery never buzzes')
        for k, s in (('broke', 'a'), ('needs-yes', 'b'), ('summary', 'daily-summary')): push.sink(self.ev(k, s))
        self.assertEqual(self.kinds_sent(), [('broke', did), ('needs-yes', did), ('summary', did)])
        u_ = push.sender.jobs
        self.assertEqual([j['raw'] and json.loads(j['raw'])['kind'] for j in u_], ['broke', 'needs-yes', 'summary'])

    def test_only_the_kinds_a_device_wants(self):
        only_summary = add_device(kinds=['summary'])[0]; all_ = add_device()[0]
        push.sink(self.ev('broke'))
        self.assertEqual(self.kinds_sent(), [('broke', all_)])
        push.sink(self.ev('summary', 'daily-summary'))
        self.assertEqual(sorted(d for k, d in self.kinds_sent() if k == 'summary'), sorted([only_summary, all_]))

    def test_owners_only(self):
        add_device(person='learner-two'); add_device(person='stranger'); mine = add_device(person='owner-two')[0]
        push.sink(self.ev('broke'))
        self.assertEqual(self.kinds_sent(), [('broke', mine)])

    def test_the_same_thing_not_again_within_30_minutes(self):
        did = add_device()[0]
        push.sink(self.ev('broke')); push.sink(self.ev('broke'))
        self.t[0] += 29 * 60; push.sink(self.ev('broke'))
        self.assertEqual(len(push.sender.jobs), 1)
        push.sink(self.ev('needs-yes'))                                        # another kind about the same thing: said
        self.t[0] += 2 * 60; push.sink(self.ev('broke'))                       # 31 minutes after the first: said again
        self.assertEqual(self.kinds_sent(), [('broke', did), ('needs-yes', did), ('broke', did)])

    def test_six_an_hour_then_one_folded_message(self):
        did = add_device()[0]
        for i in range(9): push.sink(self.ev('broke', f'thing-{i}')); self.t[0] += 60
        self.assertEqual(len(push.sender.jobs), 6, 'six in the hour')
        self.assertEqual(push.gate.flush(), [], 'no room yet: nothing')
        self.t[0] = 1000.0 + 3600 + 1                                          # the first one left the hour
        out = push.gate.flush()
        self.assertEqual(len(out), 1); self.assertEqual(len(push.sender.jobs), 7)
        m = json.loads(push.sender.jobs[-1]['raw'])
        self.assertEqual((m['kind'], m['title']), ('more', '3 more things happened. Open Elaia.'))
        self.assertEqual(push.gate.flush(), [], 'folded once, sent once')
        self.t[0] += 10; push.sink(self.ev('broke', 'thing-new'))
        self.assertEqual(len(push.sender.jobs), 7, 'the folded message counts too: the hour is full again, so this one waits')

    def test_one_folded_says_thing(self):
        add_device()
        for i in range(7): push.sink(self.ev('broke', f't{i}'))
        self.t[0] += 3601; push.gate.flush()
        self.assertEqual(json.loads(push.sender.jobs[-1]['raw'])['title'], '1 more thing happened. Open Elaia.')

    def test_registered_through_notify(self):
        add_device(); push.start(push.role_of)
        try:
            notify.notify(notify.make('broke', 'via-notify', 'It broke', 'body'))
            self.assertEqual([j['subject'] for j in push.sender.jobs], ['via-notify'])
        finally: notify.SINKS.remove(push.sink)


# ---------- the daily summary ----------
class Summary(unittest.TestCase):
    NOW = datetime(2026, 11, 11, 8, 0, 30, tzinfo=timezone(timedelta(hours=-7)))
    ROWS = [{'id': 'media', 'title': 'Media player', 'works': True}, {'id': 'backup', 'title': 'Backups', 'works': True},
            {'id': 'photos', 'title': 'Photos', 'works': True}]

    def setUp(self): clean(); os.environ.pop('ARGUS_SUMMARY', None); os.environ.pop('ARGUS_SUMMARY_AT', None)

    def e(self, kind, subject, hours_ago):
        return notify.make(kind, subject, f'{subject} {kind}', '', at=self.NOW - timedelta(hours=hours_ago))

    def test_a_calm_day(self):
        s = summary.compose([], self.ROWS, self.NOW)
        self.assertEqual(s['title'], 'Yesterday: everything worked')
        self.assertEqual(s['body'], 'Argus checked 3 things all day, and nothing stopped working. Nothing waits for you.')
        self.assertEqual(s['url'], '')
        self.assertEqual(summary.compose([self.e('broke', 'media', 30), self.e('recovered', 'media', 29)], self.ROWS, self.NOW)['title'],
                         'Yesterday: everything worked', 'older than 24 hours does not count')

    def test_a_repaired_thing(self):
        ev = [self.e('fixed', 'media', 3), self.e('needs-yes', 'media', 4)]          # newest first, as read_events gives them
        s = summary.compose(ev, self.ROWS, self.NOW)
        self.assertEqual(s['title'], 'Yesterday: 1 thing stopped working, Argus fixed it')
        self.assertEqual(s['body'], 'Argus restarted Media player as you allowed, and it works now. Nothing waits for you.')
        self.assertEqual(s['url'], 'argus')
        back = summary.compose([self.e('recovered', 'backup', 1), self.e('broke', 'backup', 2)], self.ROWS, self.NOW)
        self.assertEqual(back['title'], 'Yesterday: 1 thing stopped working, and it works again')
        self.assertEqual(back['body'], 'Backups came back by itself. Nothing waits for you.')

    def test_a_waiting_yes(self):
        rows = [dict(r, works=False) if r['id'] == 'media' else r for r in self.ROWS]
        s = summary.compose([self.e('needs-yes', 'media', 2)], rows, self.NOW)
        self.assertEqual(s['title'], '1 thing is waiting for your yes')
        self.assertEqual(s['body'], 'Media player needs a restart, and Argus waits for your yes.')
        self.assertEqual(s['url'], 'argus')
        two = summary.compose([self.e('needs-yes', 'media', 2), self.e('needs-yes', 'photos', 3), self.e('broke', 'backup', 5)],
                              [dict(r, works=False) for r in self.ROWS], self.NOW)
        self.assertEqual(two['title'], '2 things are waiting for your yes')
        self.assertEqual(two['body'], 'Photos and Media player need a restart, and Argus waits for your yes. Backups does not work right now.')
        self.assertLessEqual(len([x for x in two['body'].split('. ') if x]), 3)

    def test_once_a_day_across_a_restart(self):
        sent = []; notify.register(sent.append)
        try:
            self.assertIsNotNone(summary.tick(lambda: self.ROWS, now=self.NOW))
            self.assertIsNone(summary.tick(lambda: self.ROWS, now=self.NOW + timedelta(minutes=1)), 'not twice')
            importlib.reload(summary)                                             # a restart: only the state file remains
            self.assertIsNone(summary.tick(lambda: self.ROWS, now=self.NOW + timedelta(hours=1)), 'not after a restart either')
            self.assertIsNotNone(summary.tick(lambda: self.ROWS, now=self.NOW + timedelta(days=1)), 'the next day again')
        finally: notify.SINKS.remove(sent.append)
        self.assertEqual([(e['kind'], e['subject'], e['level']) for e in sent], [('summary', 'daily-summary', 'info')] * 2)
        self.assertEqual(json.load(open(os.environ['ARGUS_SUMMARY_STATE']))['last'], '2026-11-12')
        self.assertEqual([e['kind'] for e in notify.read_events(10)], ['summary', 'summary'], 'it is an event like any other')

    def test_the_4_hour_rule(self):
        at8 = self.NOW.replace(minute=0, second=0)
        self.assertIsNone(summary.tick(now=at8 - timedelta(minutes=1)), 'not before the set time')
        self.assertIsNotNone(summary.tick(now=at8 + timedelta(hours=3, minutes=59)), 'back within 4 hours: sent')
        clean()
        self.assertIsNone(summary.tick(now=at8 + timedelta(hours=4)), 'back after 4 hours: that day has none')
        self.assertIsNone(summary.tick(now=at8 + timedelta(hours=10)))

    def test_set_time_and_midnight(self):
        os.environ['ARGUS_SUMMARY_AT'] = '22:30'
        late = self.NOW.replace(hour=22, minute=30)
        self.assertEqual(summary.due(late + timedelta(hours=3), '', summary.at()), '2026-11-11', 'after midnight: still yesterday\'s')
        self.assertIsNone(summary.due(late + timedelta(hours=3), '2026-11-11', summary.at()))
        os.environ['ARGUS_SUMMARY_AT'] = 'breakfast'
        self.assertEqual(summary.at(), (8, 0), 'a value that is not a time: 08:00')
        os.environ.pop('ARGUS_SUMMARY_AT')

    def test_off_with_the_setting(self):
        os.environ['ARGUS_SUMMARY'] = '0'
        try:
            self.assertIsNone(summary.tick(now=self.NOW)); self.assertIsNone(summary.start(lambda: []))
            self.assertFalse(os.path.exists(os.environ['ARGUS_SUMMARY_STATE']))
        finally: os.environ.pop('ARGUS_SUMMARY')


# ---------- the routes on a real server ----------
STATIC = os.path.join(TMP, 'static'); os.makedirs(STATIC, exist_ok=True)
with open(os.path.join(STATIC, 'theme.json'), 'w') as f: json.dump({'title': 'Elaia', 'agents': [{'key': 'argus', 'name': 'Argus', 'domain': 'Watchman'}]}, f)
with open(os.path.join(STATIC, 'index.html'), 'w') as f: f.write('<!doctype html><script>const INIT = /*STATE*/null;</script>')
PEOPLE = os.path.join(CONF, 'people.json')
OWNER, LEARNER = 'owner@example.com', 'learner@example.com'
os.environ.update(ARGUS_STATIC=STATIC, ARGUS_SERVE_UID=str(os.getuid() if hasattr(os, 'getuid') else 4242), ARGUS_PLUGINS=os.path.join(TMP, 'plugins'),
                  ARGUS_BUNDLED=os.path.join(TMP, 'bundled'), ARGUS_PEOPLE_LAST_GOOD=os.path.join(STATE, 'people.last-good.json'))
_spec = importlib.util.spec_from_file_location('argus_ui_push_test', os.path.join(R, 'server', 'argus_ui.py'))
a = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(a)
if not os.path.isfile('/proc/net/tcp'):              # no /proc (Windows, macOS): stand in for the lookup, as gate_test.py does
    a.identity.connection_uid = lambda peer, ours, proc='/proc', our_inode=None: int(os.environ['ARGUS_SERVE_UID'])


@need
class RouteBase(unittest.TestCase):
    """A real server in this process, and how to ask it (the tests are in Routes and AfterThePeopleFile)."""
    @classmethod
    def setUpClass(cls):
        cls.srv = a.ThreadingHTTPServer(('127.0.0.1', 0), a.H)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
    @classmethod
    def tearDownClass(cls): cls.srv.shutdown(); cls.srv.server_close()

    def setUp(self):
        clean(); push.RETRY_AFTER = 0.4; push.TIMEOUT = 1.0
        if os.path.exists(PEOPLE): os.remove(PEOPLE)
        a.PEOPLE = a.identity.People(PEOPLE)
        push.start(lambda person: push.role_in(a.PEOPLE.current(), person))
    def tearDown(self):
        if push.sink in notify.SINKS: notify.SINKS.remove(push.sink)

    def people(self):
        with open(PEOPLE, 'w') as f:
            json.dump({'people': [{'id': 'owner-one', 'name': 'Owner One', 'role': 'owner', 'logins': [OWNER]},
                                  {'id': 'learner-two', 'name': 'Learner Two', 'role': 'learner', 'logins': [LEARNER]}]}, f)
        a.PEOPLE = a.identity.People(PEOPLE)

    def req(self, verb, path, body=None, login=OWNER, xff='192.0.2.20'):
        c = http.client.HTTPConnection('127.0.0.1', self.srv.server_address[1], timeout=20)
        h = {'Host': '127.0.0.1', 'X-Forwarded-For': xff}
        if login: h['Tailscale-User-Login'] = login
        data = None
        if verb == 'POST': h['Content-Type'] = 'application/json'; data = json.dumps(body or {})
        c.request(verb, '/argus/' + path, body=data, headers=h); r = c.getresponse(); raw = r.read(); c.close()
        return r.status, raw, json.loads(raw) if raw[:1] in (b'{', b'[') else None

    def sub_body(self, tail='phone-1'):
        k, p256dh, auth = browser(); self.keys = (k, auth)
        self.secrets = (f'{FAKE.origin}/send/{tail}', push.b64(p256dh), push.b64(auth))
        return {'subscription': {'endpoint': self.secrets[0], 'expirationTime': None, 'keys': {'p256dh': self.secrets[1], 'auth': self.secrets[2]}},
                'label': 'Android phone, Chrome', 'kinds': ['broke', 'summary']}

    def assertNoSecret(self, raw):
        pem = open(os.environ['ARGUS_PUSH_KEY'], 'rb').read() if os.path.exists(os.environ['ARGUS_PUSH_KEY']) else b'-----'
        for s in self.secrets + ('/send/',):
            self.assertNotIn(s.encode(), raw, s)
        self.assertNotIn(b'PRIVATE', raw); self.assertNotIn(pem.split(b'\n')[1] if b'\n' in pem else pem, raw)

@need
class Routes(RouteBase):
    def test_turn_on_list_change_test_forget(self):
        code, raw, d = self.req('GET', 'api/push/status')
        self.assertEqual((code, d['available'], d['trusted'], d['devices']), (200, True, True, []))
        self.assertEqual(d['key'], push.public_key()); self.assertEqual(d['kinds'], ['broke', 'needs-yes', 'summary'])
        code, raw, d = self.req('POST', 'api/push/subscribe', self.sub_body())
        self.assertEqual(code, 200, d); did = d['id']; self.assertNoSecret(raw)
        self.assertEqual(did, push.device_id(self.secrets[0]))
        code, raw, d = self.req('GET', f'api/push/status?device={did}')
        self.assertNoSecret(raw)
        self.assertEqual([(x['id'], x['label'], x['kinds'], x['this'], x['last_ok']) for x in d['devices']],
                         [(did, 'Android phone, Chrome', ['broke', 'summary'], True, '')])
        self.assertFalse(self.req('GET', 'api/push/status')[2]['devices'][0]['this'])
        code, raw, d = self.req('POST', 'api/push/kinds', {'id': did, 'kinds': ['needs-yes', 'nonsense']})
        self.assertEqual((code, d['device']['kinds']), (200, ['needs-yes'])); self.assertNoSecret(raw)
        code, raw, d = self.req('POST', 'api/push/test', {'id': did})
        self.assertEqual(code, 200, d); self.assertIn('within a few seconds', d['msg'])
        wait_for(lambda: len(FAKE.got) == 1 and devices()[0]['last_ok'], what='the test buzz')
        self.assertEqual(self.req('POST', 'api/push/test', {'id': did})[0], 429, 'one per 10 seconds')
        m = json.loads(decrypt(FAKE.got[0]['body'], *self.keys))
        self.assertEqual((m['kind'], m['title'], m['url'], m['tag']), ('test', 'Test buzz from Elaia', 'phone', 'elaia-test'))
        self.assertEqual(FAKE.got[0]['headers']['urgency'], 'high')
        code, raw, d = self.req('POST', 'api/push/forget', {'id': did})
        self.assertEqual(code, 200); self.assertEqual(devices(), [])
        self.assertEqual(self.req('POST', 'api/push/forget', {'id': did})[0], 404)

    def test_the_files_are_mode_600(self):
        self.req('POST', 'api/push/subscribe', self.sub_body())
        for p in (os.environ['ARGUS_PUSH_KEY'], os.environ['ARGUS_PUSH_DEVICES']):
            self.assertTrue(os.path.isfile(p), p)
            if POSIX: self.assertEqual(stat.S_IMODE(os.stat(p).st_mode), 0o600, p)
        if not POSIX: print('  (mode 600 checked on Linux only; this machine has no Unix file modes)', file=sys.stderr)

    def test_a_learner_gets_403(self):
        self.people()
        for verb, path in (('GET', 'api/push/status'), ('POST', 'api/push/subscribe'), ('POST', 'api/push/kinds'),
                           ('POST', 'api/push/forget'), ('POST', 'api/push/test')):
            code, raw, d = self.req(verb, path, self.sub_body() if path.endswith('subscribe') else {'id': 'x'}, login=LEARNER)
            self.assertEqual(code, 403, path); self.assertIn('Only the owner', d['error'])
        self.assertEqual(devices(), [])
        self.assertEqual(self.req('POST', 'api/push/subscribe', self.sub_body(), login=OWNER)[0], 200, 'the owner, with the same file, may')
        self.assertEqual(devices()[0]['person'], 'owner-one')

    def test_an_untrusted_request_cannot_turn_on_or_test(self):
        did = add_device()[0]
        for login, xff, why in ((None, '192.0.2.20', 'no login: not through the front door'), (OWNER, '127.0.0.1', 'from the server itself')):
            code, raw, d = self.req('POST', 'api/push/subscribe', self.sub_body('other'), login=login, xff=xff)
            self.assertEqual(code, 403, why); self.assertEqual(d['msg'], push.UNTRUSTED)
            code, raw, d = self.req('POST', 'api/push/test', {'id': did}, login=login, xff=xff)
            self.assertEqual(code, 403, why)
            s = self.req('GET', 'api/push/status', login=login, xff=xff)[2]
            self.assertEqual((s['trusted'], s['untrusted_why']), (False, push.UNTRUSTED), why)
        self.assertEqual(len(devices()), 1); self.assertEqual(FAKE.got, [])

    def test_refusals_in_plain_words(self):
        b = self.sub_body(); b['subscription']['endpoint'] = 'https://fcm.googleapis.com.evil.example/send/x'
        code, raw, d = self.req('POST', 'api/push/subscribe', b)
        self.assertEqual(code, 400); self.assertIn('does not know', d['msg'])
        b = self.sub_body(); b['subscription']['keys']['p256dh'] = push.b64(b'\x04' + b'\x01' * 64)
        self.assertEqual(self.req('POST', 'api/push/subscribe', b)[0], 400, 'a point not on the curve')
        for i in range(push.MAX_DEVICES): self.assertEqual(self.req('POST', 'api/push/subscribe', self.sub_body(f'p{i}'))[0], 200)
        code, raw, d = self.req('POST', 'api/push/subscribe', self.sub_body('one-too-many'))
        self.assertEqual(code, 409); self.assertIn('Remove one', d['msg'])
        self.assertEqual(self.req('POST', 'api/push/subscribe', self.sub_body('p3'))[0], 200, 'the same device again: updated, not added')
        self.assertEqual(len(devices()), push.MAX_DEVICES)

    def test_without_the_package_it_says_so_and_the_rest_works(self):
        saved = push._c[:]; push._c[:] = [None]
        try:
            code, raw, d = self.req('GET', 'api/push/status')
            self.assertEqual((code, d['available'], d['why'], d['key']), (200, False, push.NO_CRYPTO, ''))
            self.assertEqual(self.req('POST', 'api/push/subscribe', self.sub_body())[0], 503)
            push.sink(notify.make('broke', 'x', 'x'))                        # does nothing, raises nothing
            self.assertEqual(self.req('GET', 'api/health')[0], 200)
        finally: push._c[:] = saved


# ---------- the fix round (R8): each of these failed on the reviewed head ----------
@need
class AfterThePeopleFile(RouteBase):
    """R8 finding 1: a device turned on before there was a people file keeps getting its alerts afterwards."""
    def test_a_device_from_before_keeps_buzzing_and_the_owner_sees_it(self):
        code, raw, d = self.req('POST', 'api/push/subscribe', self.sub_body('before'))     # no people file: the person "owner"
        self.assertEqual((code, devices()[0]['person']), (200, push.NO_FILE)); did = d['id']
        self.people()                                                                        # now an owner and a learner
        FAKE.reset(); notify.notify(notify.make('broke', 'media', 'Media player is not running', 'The service is not running.'))
        wait_for(lambda: len(FAKE.got) == 1, what='the buzz to the device from before')
        self.assertEqual(json.loads(decrypt(FAKE.got[0]['body'], *self.keys))['kind'], 'broke')
        s = self.req('GET', 'api/push/status', login=OWNER)[2]
        self.assertEqual([x['id'] for x in s['devices']], [did], "the owner's list shows it")
        self.assertEqual(self.req('GET', 'api/push/status', login=LEARNER)[0], 403, 'the learner gets nothing of it')
        self.assertFalse(push.owns(devices()[0], {'person': 'learner-two', 'name': 'Learner Two', 'role': 'learner'}))
        self.assertFalse(push.owns(devices()[0], {'person': None, 'name': None, 'role': 'none'}))
        self.assertEqual(self.req('POST', 'api/push/forget', {'id': did}, login=LEARNER)[0], 403)
        self.assertEqual(self.req('POST', 'api/push/kinds', {'id': did, 'kinds': ['summary']}, login=OWNER)[0], 200, 'the owner may change it')
        self.assertEqual(self.req('POST', 'api/push/forget', {'id': did}, login=OWNER)[0], 200, 'and remove it')
        self.assertEqual(devices(), [])

    def test_the_same_phone_turning_on_again_becomes_his(self):
        b = self.sub_body('same'); self.req('POST', 'api/push/subscribe', b)
        self.people()
        self.assertEqual(self.req('POST', 'api/push/subscribe', b, login=OWNER)[0], 200)
        self.assertEqual([x['person'] for x in devices()], ['owner-one'])

    def test_who_such_a_row_counts_for(self):
        ok = lambda people: ('ok', people, None)
        own = {'person': 'owner-one', 'role': 'owner'}; two = {'person': 'owner-two', 'role': 'owner'}
        self.assertEqual(push.role_in(ok([own]), push.NO_FILE), 'owner')
        self.assertEqual(push.role_in(ok([own, two]), push.NO_FILE), 'owner', 'several owners: it counts for the owners')
        self.assertEqual(push.role_in(ok([own, {'person': 'owner', 'role': 'learner'}]), push.NO_FILE), 'none',
                         'a learner who happens to have the id "owner" never gets it')
        self.assertEqual(push.role_in(('broken', [], None), push.NO_FILE), 'none')
        self.assertEqual(push.role_in(ok([own]), 'stranger'), 'none')


@need
class LockScreenWords(unittest.TestCase):
    """R8 finding 5: on a lock screen "needs my yes" and "stopped working" read differently in the first 40 characters."""
    def test_needs_yes_says_so_first(self):
        import watch
        push.name_of = lambda s: 'Media player' if s == 'media' else ''
        try:
            c = {'id': 'media', 'title': 'Media player', 'unit': 'jellyfin'}
            codes = ['unit-down'] + [k for k in watch.PROGRAM]
            for code in codes:
                reason, title, why = watch.words(c, code)
                yes = json.loads(push.message(notify.make('needs-yes', 'media', title, f'{why} Waiting for your yes.')))
                broke = json.loads(push.message(notify.make('broke', 'media', title, f'{why} This one has no automatic fix.')))
                self.assertNotEqual(yes['title'][:40], broke['title'][:40], code)
                self.assertEqual(yes['title'], 'Needs your yes: Media player', code)
                self.assertIn('Media player', broke['title'], code)
                self.assertTrue(yes['body'].startswith(title.rstrip('.') + '. '), (code, yes['body']))
                self.assertLessEqual(len(yes['title']), 40)
                self.assertEqual(broke['body'], f'{why} This one has no automatic fix.', 'broke: the words as they are')
            push.name_of = lambda s: ''
            m = json.loads(push.message(notify.make('needs-yes', 'x', 'Backups is not running', 'Restarting it should fix it.')))
            self.assertEqual(m['title'], 'Needs your yes: Backups is not running', 'no name known: the watch title, never cut')
        finally: push.name_of = lambda s: ''


@need
class Flapping(unittest.TestCase):
    """R8 finding 8: one check that breaks every 2 minutes all day buzzes far less than 48 times."""
    def setUp(self):
        clean(); self.t = [0.0]; push.clock = lambda: self.t[0]
        self.real, push.sender = push.sender, Recorder(); push.role_of = lambda p: 'owner' if p == 'owner' else 'none'
        add_device()
    def tearDown(self): push.sender = self.real; push.clock = time.monotonic

    def test_the_quiet_time_grows_and_comes_back(self):
        sent = []
        for i in range(24 * 30):                                   # every 2 minutes for 24 hours
            self.t[0] = i * 120.0; n = len(push.sender.jobs)
            push.sink(notify.make('broke', 'media', 'Media player is not running', ''))
            if len(push.sender.jobs) > n: sent.append(self.t[0] / 60)
        self.assertEqual(sent[:6], [0, 30, 90, 210, 450, 690], 'gaps of 30 minutes, 1 hour, 2 hours, then 4 hours')
        self.assertLessEqual(len(sent), 9)
        self.t[0] += 12 * 3600; push.sink(notify.make('broke', 'media', 'x', ''))
        self.t[0] += 31 * 60; push.sink(notify.make('broke', 'media', 'x', ''))
        self.assertEqual(len(push.sender.jobs), len(sent) + 2, 'quiet for 12 hours: back to 30 minutes')


@need
class SmallOnes(unittest.TestCase):
    """R8 findings 9, 10 and 11 (the Topic header)."""
    def setUp(self): clean(); push.RETRY_AFTER = 0.4; push.TIMEOUT = 1.0

    def test_aud_is_the_host_name_alone(self):
        for e in ('https://fcm.googleapis.com/x', 'https://FCM.googleapis.com/x'):
            t = push.vapid(e).split('t=')[1].split(',')[0]
            self.assertEqual(json.loads(u(t.split('.')[1]))['aud'], 'https://fcm.googleapis.com', e)
        self.assertFalse(push.endpoint_ok('https://fcm.googleapis.com:443/x'), 'an explicit port is refused')

    def test_a_contact_without_a_host_does_not_crash(self):
        for bad in ('https://@', 'https://', 'https://:443'):
            os.environ['ARGUS_PUSH_CONTACT'] = bad
            try: self.assertEqual(push.contact(), push.DEFAULT_CONTACT, bad)
            finally: os.environ.pop('ARGUS_PUSH_CONTACT')

    def test_a_failure_while_signing_shows_as_the_last_try(self):
        did = add_device()[0]; real = push.vapid
        push.vapid = lambda *a, **k: (_ for _ in ()).throw(AttributeError('boom'))
        try:
            push.sender.put({'device': did, 'raw': push.message(notify.make('broke', 's', 't')), 'kind': 'broke', 'subject': 's'})
            wait_for(lambda: devices()[0]['last_error'], what='last_error')
        finally: push.vapid = real
        self.assertEqual(devices()[0]['last_error'], push.say_failure('sign')); self.assertEqual(FAKE.got, [])

    def test_the_topic_is_salted_with_the_server_key(self):
        import hashlib
        k1, k2 = ec.generate_private_key(ec.SECP256R1()), ec.generate_private_key(ec.SECP256R1())
        self.assertEqual(push.topic('media', k1), push.topic('media', k1), 'stable for one subject')
        self.assertNotEqual(push.topic('media', k1), push.topic('media', k2), 'another server, another topic')
        self.assertNotEqual(push.topic('media', k1), push.topic('photos', k1))
        self.assertNotEqual(push.topic('media'), push.b64(hashlib.sha256(b'elaia:media').digest())[:32], 'not the plain hash')
        self.assertRegex(push.topic('media'), r'^[A-Za-z0-9_-]{32}$')


if __name__ == '__main__':
    try: unittest.main(verbosity=1)
    finally: shutil.rmtree(TMP, ignore_errors=True)
