"""Phone alerts (docs/phone-alerts.md): Web Push by the standards, and the sink that decides what buzzes.

    RFC 8030  the message goes to the push service the phone's browser named (Google's for Chrome on Android)
    RFC 8291  the message is encrypted for that one browser (aes128gcm): the push service cannot read it
    RFC 8292  the server signs each request (VAPID, an ES256 token), so the service knows it comes from this server

Only the `cryptography` package is needed beyond the standard library, and it is imported lazily: without it phone alerts say
"not available on this server" in plain words and everything else works as before.

Files (both mode 600, written through a temp file made with mkstemp and renamed):
    ~/.config/argus-ui/push-key.pem          the server's key pair (ARGUS_PUSH_KEY); made on first need, never logged or sent
    ~/.local/state/argus-ui/push-devices.json the devices (ARGUS_PUSH_DEVICES): {id, person, label, endpoint, keys, kinds, made,
                                              last_ok, last_error}; the endpoint is a secret address, never logged or answered
Settings: ARGUS_PUSH_CONTACT (the VAPID contact, default DEFAULT_CONTACT: an address under the reserved name .invalid). ARGUS_PUSH_TEST_ORIGIN (tests only,
honoured only with ARGUS_DEV=1 and only for an http address on this machine: the fake push service)."""
import base64, hashlib, hmac, http.client, ipaddress, json, os, queue, re, ssl, sys, tempfile, threading, time
from collections import deque
from datetime import datetime
from urllib.parse import urlsplit

import notify

KINDS = ('broke', 'needs-yes', 'summary')            # the only kinds that buzz (never fixed or recovered)
HOSTS = ('fcm.googleapis.com',)                      # the push services a browser may name: this host exactly,
SUFFIXES = ('.push.services.mozilla.com', '.notify.windows.com', '.push.apple.com')   # or a host that ends in one of these
MAX_DEVICES = 8                                      # per person
MAX_MESSAGE = 2000                                   # bytes of the message before encryption
RECORD = 4096                                        # the record size in the aes128gcm header (one record)
TIMEOUT = 10                                         # seconds for one request to the push service
RETRY_AFTER = 60                                     # 429, 5xx or no answer: one more try after this many seconds
REPEAT = 30 * 60                                     # the same subject and kind is not sent again within this; then the gap grows:
GAPS = (REPEAT, 3600, 2 * 3600, 4 * 3600)            # 30 min, 1 h, 2 h, then 4 h between buzzes about one thing that keeps going wrong,
CALM = 12 * 3600                                     # back to 30 minutes once that thing has been quiet for 12 hours
PER_HOUR = 6                                         # buzzes per person per rolling hour; more are folded into one later message
HOUR = 3600
TEST_GAP = 10                                        # one test buzz per person per this many seconds
OWN_PRESS = 120                                      # an event his own press on the page caused within this many seconds does not buzz
TTL = {'broke': 6 * 3600, 'needs-yes': 6 * 3600, 'summary': 12 * 3600, 'more': 6 * 3600, 'test': 600}
URGENCY = {'broke': 'high', 'needs-yes': 'high', 'summary': 'normal', 'more': 'normal', 'test': 'high'}
NO_CRYPTO = ('Phone alerts are not available on this server: it is missing the part that locks each message for your phone '
             '(the Python package "cryptography"). Everything else works as before.')
clock = time.monotonic                               # the sink's clock (tests replace it)
DEFAULT_CONTACT = 'mailto:elaia@example.invalid'     # private-ok: .invalid is reserved (RFC 2606), never a real address or the page's own


def log(msg): print(f'argus-ui: phone alerts: {msg}', file=sys.stderr, flush=True)


def b64(b): return base64.urlsafe_b64encode(b).rstrip(b'=').decode()


def unb64(s):
    s = str(s or '').strip()
    if not re.fullmatch(r'[A-Za-z0-9_-]*={0,2}', s): raise ValueError('not base64url')
    return base64.urlsafe_b64decode(s.rstrip('=') + '=' * (-len(s.rstrip('=')) % 4))


# ---------- the cryptography package, imported on first need ----------
_c = []


def crypto():
    """The parts of `cryptography` this needs, or None when the package is missing."""
    if not _c:
        try:
            from cryptography.hazmat.primitives.asymmetric import ec
            from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            _c.append(dict(ec=ec, dss=decode_dss_signature, hashes=hashes, ser=serialization, AESGCM=AESGCM))
        except ImportError:
            _c.append(None)
    return _c[0]


def available():
    """(True, '') or (False, one plain sentence why not)."""
    if not crypto(): return False, NO_CRYPTO
    try: server_key()
    except Exception as e:
        log(f'the key file cannot be used ({type(e).__name__})')
        return False, ('Phone alerts are not available: the server\'s key file for them cannot be read. Move it aside to a dated '
                       'name (docs/phone-alerts.md, "Start over") and a new one is made.')
    return True, ''


# ---------- files: written through a temp file, mode 600 ----------
def key_path(): return os.path.expanduser(os.environ.get('ARGUS_PUSH_KEY') or '~/.config/argus-ui/push-key.pem')


def devices_path(): return os.path.expanduser(os.environ.get('ARGUS_PUSH_DEVICES') or '~/.local/state/argus-ui/push-devices.json')


def write_secret(path, data):
    """Write bytes to path, readable by this user only: a temp file made with mkstemp (mode 600) in the same folder, renamed."""
    d = os.path.dirname(path) or '.'
    os.makedirs(d, mode=0o700, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix='.' + os.path.basename(path) + '.', suffix='.tmp')
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        try: os.unlink(tmp)
        except OSError: pass
        raise


_key = {}
_key_lock = threading.Lock()


def server_key():
    """The server's P-256 key pair: read from key_path(), or made and saved there on first need."""
    c = crypto()
    path = key_path()
    with _key_lock:
        if _key.get('path') == path: return _key['key']
        try:
            with open(path, 'rb') as f: key = c['ser'].load_pem_private_key(f.read(), password=None)
            if not isinstance(key, c['ec'].EllipticCurvePrivateKey) or key.curve.name != 'secp256r1': raise ValueError('not a P-256 key')
        except FileNotFoundError:
            key = c['ec'].generate_private_key(c['ec'].SECP256R1())
            write_secret(path, key.private_bytes(c['ser'].Encoding.PEM, c['ser'].PrivateFormat.PKCS8, c['ser'].NoEncryption()))
            log('made a new key pair for phone alerts')
        _key.update(path=path, key=key)
        return key


def point(key):
    """A public key as the 65-byte uncompressed point."""
    c = crypto()
    return key.public_bytes(c['ser'].Encoding.X962, c['ser'].PublicFormat.UncompressedPoint)


def public_key():
    """The server's public key for the browser (applicationServerKey), base64url."""
    return b64(point(server_key().public_key()))


# ---------- RFC 8291: message encryption (aes128gcm, one record) ----------
def _extract(salt, ikm): return hmac.new(salt, ikm, hashlib.sha256).digest()


def _expand(prk, info, n): return hmac.new(prk, info + b'\x01', hashlib.sha256).digest()[:n]   # n <= 32: one block


def encrypt(plaintext, ua_public, auth_secret, as_private=None, salt=None):
    """The body of a push message for one browser (RFC 8291 section 3, RFC 8188). as_private and salt are fresh each time;
    the tests pass the ones from RFC 8291 Appendix A to get its exact bytes."""
    c = crypto()
    as_private = as_private or c['ec'].generate_private_key(c['ec'].SECP256R1())
    salt = salt or os.urandom(16)
    as_public = point(as_private.public_key())
    ua = c['ec'].EllipticCurvePublicKey.from_encoded_point(c['ec'].SECP256R1(), ua_public)
    ecdh = as_private.exchange(c['ec'].ECDH(), ua)
    ikm = _expand(_extract(auth_secret, ecdh), b'WebPush: info\x00' + ua_public + as_public, 32)
    prk = _extract(salt, ikm)
    cek, nonce = _expand(prk, b'Content-Encoding: aes128gcm\x00', 16), _expand(prk, b'Content-Encoding: nonce\x00', 12)
    if len(plaintext) + 1 + 16 + 86 > RECORD: raise ValueError('message too large for one record')
    ct = c['AESGCM'](cek).encrypt(nonce, plaintext + b'\x02', None)     # 0x02: the last (and only) record, no padding
    return salt + RECORD.to_bytes(4, 'big') + bytes([len(as_public)]) + as_public + ct


# ---------- RFC 8292: VAPID ----------
def contact():
    c = str(os.environ.get('ARGUS_PUSH_CONTACT') or '').strip()
    try: host = urlsplit(c).hostname or '' if c.startswith('https://') else ''
    except ValueError: host = ''
    if re.fullmatch(r'mailto:[^\s@<>"]+@[^\s@<>"]+', c) or re.fullmatch(r'https://[^\s<>"]+', c) and host and not host.endswith('.ts.net'):
        return c
    if c: log('ARGUS_PUSH_CONTACT is not a mailto: or https: address (or is the page\'s own address); the default is used')
    return DEFAULT_CONTACT


def vapid(endpoint, key=None, now=None):
    """The Authorization header for one push service: 'vapid t=<ES256 JWT>, k=<public key>' (RFC 8292 section 3)."""
    c = crypto(); key = key or server_key()
    u = urlsplit(endpoint)
    claims = {'aud': f'{u.scheme}://{u.hostname}', 'exp': int(now or time.time()) + 12 * 3600, 'sub': contact()}
    head = b64(json.dumps({'typ': 'JWT', 'alg': 'ES256'}, separators=(',', ':')).encode())
    body = b64(json.dumps(claims, separators=(',', ':')).encode())
    r, s = c['dss'](key.sign(f'{head}.{body}'.encode(), c['ec'].ECDSA(c['hashes'].SHA256())))
    return f'vapid t={head}.{body}.{b64(r.to_bytes(32, "big") + s.to_bytes(32, "big"))}, k={b64(point(key.public_key()))}'


# ---------- which push services the server will ever call ----------
def test_origin():
    """(scheme, host, port) of the fake push service in the tests: only with ARGUS_DEV=1, only http on this machine."""
    o = os.environ.get('ARGUS_PUSH_TEST_ORIGIN')
    if not o or not os.environ.get('ARGUS_DEV'): return None
    try:
        u = urlsplit(o)
        if u.scheme == 'http' and u.hostname and ipaddress.ip_address(u.hostname).is_loopback and u.port: return ('http', u.hostname, u.port)
    except ValueError: pass
    return None


def endpoint_ok(endpoint):
    """True only for a known push service: https, no port written out, no user-info, and a host that is fcm.googleapis.com or ends in
    one of SUFFIXES (exact match on the parsed host). Checked at subscribe time and again before every send."""
    if not isinstance(endpoint, str) or not 8 < len(endpoint) <= 1024 or re.search(r'[\s\\\x00-\x1f\x7f]', endpoint): return False
    try:
        u = urlsplit(endpoint); port = u.port
    except ValueError: return False
    if '@' in u.netloc or u.username is not None or u.password is not None: return False
    host = u.hostname or ''
    t = test_origin()
    if t and (u.scheme, host, port) == t: return True
    if u.scheme != 'https' or port is not None or ':' in u.netloc: return False   # no explicit port, not even :443 (aud is https://host)
    if not re.fullmatch(r'[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+', host): return False   # no IP literal in [], no trailing dot
    try:
        ipaddress.ip_address(host); return False
    except ValueError: pass
    return host in HOSTS or any(host.endswith(s) for s in SUFFIXES)


# ---------- devices ----------
_dev_lock = threading.RLock()


def device_id(endpoint):
    """A device's id: from its endpoint, so the page can tell which one is itself without ever being sent the endpoint."""
    return hashlib.sha256(('argus-push:' + endpoint).encode()).hexdigest()[:16]


def load_devices():
    try:
        with open(devices_path(), encoding='utf-8') as f: d = json.load(f)
    except FileNotFoundError: return []
    except (OSError, ValueError) as e:
        log(f'the devices file cannot be read ({type(e).__name__}); no phone gets alerts until it is fixed or moved aside')
        raise
    return [x for x in d if isinstance(x, dict) and isinstance(x.get('endpoint'), str)] if isinstance(d, list) else []


def save_devices(devs):
    write_secret(devices_path(), json.dumps(devs, indent=1).encode())


def update_device(did, **changes):
    """Change one device's fields (last_ok, last_error); a device removed meanwhile stays removed."""
    with _dev_lock:
        try: devs = load_devices()
        except (OSError, ValueError): return
        for d in devs:
            if d['id'] == did: d.update(changes)
        save_devices(devs)


def remove_device(did):
    with _dev_lock:
        try: devs = load_devices()
        except (OSError, ValueError): return
        save_devices([d for d in devs if d['id'] != did])


# ---------- who is an owner (set by the server: the people file; standalone, the no-file rule) ----------
NO_FILE = 'owner'          # the person every request is while there is no people file (identity.YOU); rows turned on then carry it


def role_in(people_state, person):
    """The role of a person id in identity.People.current(): no file -> only 'owner' is the owner; a broken file -> nobody.
    A device turned on before the people file existed is stored with the person NO_FILE. Once a usable file is there, such a
    row belongs to the owners: it keeps buzzing (for the owner, or for every owner when there are several, since it is one
    phone), every owner sees it and can remove it, and it becomes his own when that phone turns alerts on again. Only if the
    file gives a LEARNER the id 'owner' does such a row count for nobody (never for her)."""
    mode, people, _ = people_state
    if mode == 'absent': return 'owner' if person == NO_FILE else 'none'
    if mode == 'broken': return 'none'
    p = next((p for p in people if p['person'] == person), None)
    if person == NO_FILE: return 'owner' if p is None or p['role'] == 'owner' else 'none'
    return p['role'] if p else 'none'


role_of = lambda person: 'owner' if person == NO_FILE else 'none'


def owns(d, who):
    """May this person see and change this device row: his own, or (as an owner) a row from before the people file."""
    p = d.get('person')
    if p == who.get('person') and who.get('role') == 'owner': return True     # the routes are owner-only too; belt and braces
    return p == NO_FILE and who.get('role') == 'owner' and role_of(NO_FILE) == 'owner'


name_of = lambda subject: ''   # the name of a thing as the page calls it (the check's title); the server sets it at start


# ---------- the message ----------
def message(event, kind=None):
    """The JSON a phone gets: {id, kind, title, body, url, at, tag}, at most MAX_MESSAGE bytes (the body is trimmed)."""
    kind = kind or event.get('kind', '')
    title, body = str(event.get('title') or 'Elaia'), str(event.get('body') or '')
    if kind == 'needs-yes':          # on a lock screen he must see at once that he is asked: the ask first, then what it is about
        try: name = str(name_of(str(event.get('subject') or '')) or '').strip()
        except Exception: name = ''
        said = title.rstrip('. ')
        body = f'{said}. {body}'.strip() if said and not body.startswith(said) else body
        title = f'Needs your yes: {name or said}'
    m = {'id': str(event.get('id') or ''), 'kind': kind, 'title': title[:200],
         'body': body, 'url': str(event.get('url') or ''), 'at': str(event.get('at') or ''),
         'tag': str(event.get('subject') or event.get('kind') or 'elaia')[:64]}
    dump = lambda: json.dumps(m, ensure_ascii=False).encode()
    raw = dump()
    if len(raw) > MAX_MESSAGE and m['body']:                      # the longest start of the body that fits, ended with …
        body, lo, hi = m['body'], 0, len(m['body'])
        while lo < hi:
            mid = (lo + hi + 1) // 2; m['body'] = body[:mid].rstrip() + '…'
            if len(dump()) <= MAX_MESSAGE: lo = mid
            else: hi = mid - 1
        m['body'] = body[:lo].rstrip() + '…' if lo else ''
        raw = dump()
    while len(raw) > MAX_MESSAGE and len(m['title']) > 20:        # only a title full of escaped characters gets here
        m['title'] = m['title'][:len(m['title']) // 2]; raw = dump()
    return raw


def topic(subject, key=None):
    """The Topic header: a newer message with the same topic replaces one the phone has not fetched yet (RFC 8030 5.4).
    At most 32 characters of the URL-safe base64 alphabet: an HMAC of the subject with a salt made from the server's private
    key, so the push service (which sees the header in clear) cannot guess the subject; stable for one server."""
    c = crypto(); key = key or server_key()
    salt = hashlib.sha256(b'elaia-topic\x00' + key.private_bytes(c['ser'].Encoding.DER, c['ser'].PrivateFormat.PKCS8, c['ser'].NoEncryption())).digest()
    return b64(hmac.new(salt, str(subject).encode(), hashlib.sha256).digest())[:32]


# ---------- sending: one worker thread, a small queue ----------
def post(endpoint, body, headers):
    """One POST to the push service; never follows a redirect (http.client does not). -> the status code."""
    u = urlsplit(endpoint)
    if u.scheme == 'https': conn = http.client.HTTPSConnection(u.hostname, u.port or 443, timeout=TIMEOUT, context=ssl.create_default_context())
    else: conn = http.client.HTTPConnection(u.hostname, u.port, timeout=TIMEOUT)
    try:
        conn.request('POST', (u.path or '/') + ('?' + u.query if u.query else ''), body=body, headers=headers)
        r = conn.getresponse(); r.read(4096)
        return r.status
    finally: conn.close()


def say_failure(why):
    return {'timeout': 'The phone maker\'s message service did not answer in time. Elaia tried twice.',
            'busy': 'The phone maker\'s message service asked Elaia to wait. Elaia tried twice.',
            'down': 'The phone maker\'s message service had a problem. Elaia tried twice.',
            'moved': 'The phone maker\'s message service answered with a different address, which Elaia never follows.',
            'refused': 'The phone maker\'s message service refused the message. Turning alerts off and on again on that device usually helps.',
            'unknown': 'This device asked for a message service Elaia does not know, so nothing was sent.',
            'nokey': 'The message could not be locked for this device. Turning alerts off and on again on it usually helps.',
            'sign': 'Elaia could not sign the message. Check the alert settings on the server (docs/phone-alerts.md, "Files and settings").'}[why]


class Sender:
    """Delivers jobs {device, raw, kind, subject} on its own thread. The watch loop and the request handlers only put a job
    in the queue; they never wait on the network."""
    def __init__(self):
        self.q = queue.Queue(maxsize=64); self.later = []; self.lock = threading.Lock(); self.thread = None
        self.sent = []                                   # (device id, kind, status) of the last attempts, for the tests

    def put(self, job):
        with self.lock:
            if not self.thread or not self.thread.is_alive():
                self.thread = threading.Thread(target=self.loop, name='argus-push', daemon=True); self.thread.start()
        try: self.q.put_nowait(job)
        except queue.Full: log('too many messages waiting; one was dropped')

    def loop(self):
        while True:
            try: job = self.q.get(timeout=0.5)
            except queue.Empty: job = None
            now = clock()
            with self.lock:
                due = [j for t, j in self.later if t <= now]; self.later = [(t, j) for t, j in self.later if t > now]
            for j in ([job] if job else []) + due:
                try: self.deliver(j)
                except Exception as e: log(f'a message could not be sent ({type(e).__name__})')
            try: gate.flush()
            except Exception as e: log(f'the folded message failed ({type(e).__name__})')

    def deliver(self, job):
        with _dev_lock:
            try: dev = next((d for d in load_devices() if d['id'] == job['device']), None)
            except (OSError, ValueError): return
        if not dev: return                                         # forgotten meanwhile
        if not endpoint_ok(dev['endpoint']):
            update_device(dev['id'], last_error=say_failure('unknown')); return
        try:
            body = encrypt(job['raw'], unb64(dev['keys']['p256dh']), unb64(dev['keys']['auth']))
        except Exception:
            update_device(dev['id'], last_error=say_failure('nokey')); return
        try:
            headers = {'TTL': str(TTL.get(job['kind'], 3600)), 'Urgency': URGENCY.get(job['kind'], 'normal'), 'Topic': topic(job['subject']),
                       'Content-Encoding': 'aes128gcm', 'Content-Type': 'application/octet-stream', 'Authorization': vapid(dev['endpoint'])}
        except Exception as e:
            log(f'a message could not be signed ({type(e).__name__})')
            update_device(dev['id'], last_error=say_failure('sign')); return
        try: status = post(dev['endpoint'], body, headers)
        except (TimeoutError, OSError, http.client.HTTPException) as e:
            status = 'timeout'
        self.sent.append((dev['id'], job['kind'], status))
        del self.sent[:-50]
        if isinstance(status, int) and 200 <= status < 300:
            update_device(dev['id'], last_ok=now_iso(), last_error='')
        elif status in (404, 410):
            remove_device(dev['id']); log('a device was removed: its message service says it no longer exists')
        elif status == 'timeout' or status == 429 or (isinstance(status, int) and status >= 500):
            if job.get('try', 0) == 0:
                with self.lock: self.later.append((clock() + RETRY_AFTER, dict(job, **{'try': 1})))
            else:
                update_device(dev['id'], last_error=say_failure('timeout' if status == 'timeout' else 'busy' if status == 429 else 'down'))
        else:
            update_device(dev['id'], last_error=say_failure('moved' if 300 <= status < 400 else 'refused'))
            log(f'a message was refused by its message service (status {status})')


def now_iso(): return datetime.now().astimezone().isoformat(timespec='seconds')


sender = Sender()


# ---------- the sink: what buzzes ----------
class Gate:
    """In memory: what each person was last told about (kind, subject), their buzzes in the rolling hour, and what was folded.
    A restart may forget these; the devices stay in their file."""
    def __init__(self):
        self.lock = threading.Lock(); self.told = {}; self.hour = {}; self.folded = {}

    def _room(self, person, now):
        q = self.hour.setdefault(person, deque())
        while q and now - q[0] >= HOUR: q.popleft()
        return q

    def offer(self, person, kind, subject, now=None):
        """'send', 'repeat' (said too recently: 30 minutes, growing to 4 hours for one thing that keeps going wrong) or 'folded'
        (the hour is full: counted for the later message)."""
        now = clock() if now is None else now
        with self.lock:
            k = (person, kind, subject)
            rec = self.told.get(k)                       # [last buzz, step in GAPS, last time it came up]
            if rec and now - rec[2] >= CALM: rec = None   # quiet for 12 hours: back to 30 minutes
            if rec and now - rec[0] < GAPS[rec[1]]:
                rec[2] = now; return 'repeat'
            self.told[k] = [now, min(rec[1] + 1, len(GAPS) - 1) if rec else 0, now]
            if kind == 'summary': return 'send'          # once a day: never folded into "N more things", not counted in the hour
            q = self._room(person, now)
            if len(q) >= PER_HOUR or self.folded.get(person):
                f = self.folded.setdefault(person, {'n': 0, 'kinds': set()}); f['n'] += 1; f['kinds'].add(kind)
                return 'folded'
            q.append(now)
            return 'send'

    def forget(self, subject):
        """A repair worked (a `fixed` event): drop the quiet-time records of that thing, so a new breakage later is not held
        back. Flapping (broke, then recovered by itself) never comes here, so its limit stays as it is."""
        with self.lock:
            for k in [k for k in self.told if k[2] == subject]: del self.told[k]

    def flush(self, now=None):
        """Once the hour has room again: ONE message per person for everything folded ("3 more things happened")."""
        now = clock() if now is None else now
        out = []
        with self.lock:
            for person, f in list(self.folded.items()):
                q = self._room(person, now)
                if len(q) >= PER_HOUR: continue
                q.append(now); del self.folded[person]; out.append((person, f))
        for person, f in out:
            n = f['n']
            ev = {'id': f'more-{int(time.time())}', 'kind': 'more', 'subject': 'elaia-more', 'at': now_iso(), 'url': '',
                  'title': f'{n} more thing{"s" if n != 1 else ""} happened. Open Elaia.',
                  'body': 'Elaia held these back so your phone would not buzz too often. Everything is on the page.'}
            to_devices(person, f['kinds'], ev, 'more')
        return out


gate = Gate()


def to_devices(person, kinds, event, kind):
    """Queue the message for each device of this person that wants one of these kinds."""
    try: devs = load_devices()
    except (OSError, ValueError): return 0
    raw = message(event, kind); n = 0
    for d in devs:
        if d.get('person') == person and set(d.get('kinds') or ()) & set(kinds):
            sender.put({'device': d['id'], 'raw': raw, 'kind': kind, 'subject': event.get('subject', '')}); n += 1
    return n


def own_press(event, now=None):
    """True for an event the owner's own press on the page caused less than OWN_PRESS seconds ago (watch.py writes `by` 'owner' and
    `pressed` on the events of his restart: it did not help, or could not be sent). He pressed it while looking at the page, and
    the page says how it went, so the phone keeps still; the event still goes into the events file, onto the page and into the
    daily summary. Later than that (a slow restart, or he walked away), it buzzes as any other."""
    if event.get('by') != 'owner': return False
    try: pressed = datetime.fromisoformat(str(event.get('pressed'))).timestamp()
    except (TypeError, ValueError, OverflowError, OSError): return False
    return abs((time.time() if now is None else now) - pressed) < OWN_PRESS


def sink(event):
    """notify.register(sink): buzz for broke, needs-yes and summary only, to owners' devices that want that kind; never for what
    the owner's own press caused a moment ago (own_press)."""
    kind = event.get('kind')
    if kind == 'fixed': gate.forget(str(event.get('subject', '')))   # never buzzes, but resets that thing's quiet time
    if kind not in KINDS or not crypto(): return
    if own_press(event): return                                       # he is looking at the page that says how his press went
    try: devs = load_devices()
    except (OSError, ValueError): return
    people = sorted({d.get('person') for d in devs if kind in (d.get('kinds') or ())})
    for person in people:
        if role_of(person) != 'owner': continue
        if gate.offer(person, kind, str(event.get('subject', ''))) == 'send':
            to_devices(person, [kind], event, kind)


# ---------- the routes (server/argus_ui.py hands these the request's who and trusted) ----------
UNTRUSTED = ('Alerts can be turned on and tested only when Elaia is opened through its secure address, signed in '
             '(the address that starts with https). This page was opened another way.')
_tests = {}


def _view(d, this):
    return {'id': d['id'], 'label': d.get('label', ''), 'kinds': [k for k in KINDS if k in (d.get('kinds') or ())], 'made': d.get('made', ''),
            'last_ok': d.get('last_ok', ''), 'last_error': d.get('last_error', ''), 'this': d['id'] == this}


def status(who, trusted, this=''):
    ok, why = available()
    out = {'available': ok, 'why': why, 'trusted': bool(trusted), 'untrusted_why': '' if trusted else UNTRUSTED,
           'kinds': list(KINDS), 'key': public_key() if ok else '', 'devices': []}
    try: devs = load_devices()
    except (OSError, ValueError):
        out.update(available=False, why='Phone alerts are not available: the server\'s list of devices cannot be read. '
                   'Move it aside to a dated name (docs/phone-alerts.md) and turn alerts on again.', key='')
        return out
    out['devices'] = [_view(d, str(this or '')) for d in devs if owns(d, who)]
    return out


def _clean_kinds(v):
    return [k for k in KINDS if isinstance(v, list) and k in v]


def route(name, body, who, trusted):
    """POST api/push/<name> -> (status, answer). Never answers an endpoint or a key."""
    if name not in ('subscribe', 'kinds', 'forget', 'test'): return 404, {'ok': False, 'msg': 'not found'}
    ok, why = available()
    if not ok: return 503, {'ok': False, 'msg': why}
    person = who.get('person')
    # the body is checked first (that tells nothing), then whether the request is trusted: subscribe and test need it
    if name == 'subscribe': return subscribe(person, body, trusted, who)
    did = str(body.get('id') or '')
    with _dev_lock:
        try: devs = load_devices()
        except (OSError, ValueError): return 503, {'ok': False, 'msg': 'The server\'s list of devices cannot be read.'}
        dev = next((d for d in devs if d['id'] == did and owns(d, who)), None)
        if not dev: return 404, {'ok': False, 'msg': 'That device is not on your list any more. Reload this page.'}
        if name == 'kinds':
            if not isinstance(body.get('kinds'), list): return 400, {'ok': False, 'msg': 'Say which alerts this device should get.'}
            dev['kinds'] = _clean_kinds(body.get('kinds')); save_devices(devs)
            return 200, {'ok': True, 'device': _view(dev, did)}
        if name == 'forget':
            save_devices([d for d in devs if d is not dev])
            return 200, {'ok': True, 'msg': f'{dev.get("label") or "That device"} gets no more alerts.'}
    if not trusted: return 403, {'ok': False, 'msg': UNTRUSTED, 'error': UNTRUSTED}
    now = clock()                                                     # test: one message to that one device
    if now - _tests.get(person, -TEST_GAP) < TEST_GAP:
        return 429, {'ok': False, 'msg': 'One test buzz every 10 seconds. Wait a moment, then try again.'}
    _tests[person] = now
    ev = {'id': f'test-{int(time.time())}', 'subject': 'elaia-test', 'at': now_iso(), 'url': 'phone',
          'title': 'Test buzz from Elaia', 'body': 'Alerts reach this device. Nothing else happened.'}
    sender.put({'device': dev['id'], 'raw': message(ev, 'test'), 'kind': 'test', 'subject': 'elaia-test'})
    return 200, {'ok': True, 'msg': 'Sent. It should arrive within a few seconds, also when Elaia is closed.'}


def subscribe(person, body, trusted, who=None):
    """Add or update this browser's device. `replaces` (optional) is the id this browser had before its address changed
    (the page and sw.js keep it): that record is retired only when it is this person's own (owns()); an unknown or foreign
    id is ignored, and the answer is the same either way, so it never tells whether an id exists. Without `label` or
    `kinds` (sw.js sends neither) the record keeps the ones it had."""
    sub = body.get('subscription')
    if not isinstance(sub, dict): return 400, {'ok': False, 'msg': 'This browser did not say where to send alerts. Try again.'}
    endpoint, keys = sub.get('endpoint'), sub.get('keys') if isinstance(sub.get('keys'), dict) else {}
    if not endpoint_ok(endpoint):
        return 400, {'ok': False, 'msg': 'This browser uses a message service Elaia does not know, so alerts stay off here. '
                                         'Chrome or Samsung Internet on the phone work.'}
    try:
        p256dh, auth = unb64(keys.get('p256dh')), unb64(keys.get('auth'))
        if len(p256dh) != 65 or p256dh[0] != 4 or len(auth) != 16: raise ValueError('wrong length')
        crypto()['ec'].EllipticCurvePublicKey.from_encoded_point(crypto()['ec'].SECP256R1(), p256dh)
    except Exception:
        return 400, {'ok': False, 'msg': 'This browser sent a lock Elaia cannot use, so alerts stay off here. Try again.'}
    if not trusted: return 403, {'ok': False, 'msg': UNTRUSTED, 'error': UNTRUSTED}
    label = re.sub(r'[\x00-\x1f\x7f<>]', '', str(body.get('label') or '')).strip()[:40]
    did = device_id(endpoint)
    rep = body.get('replaces')
    rep = rep if isinstance(rep, str) and re.fullmatch(r'[0-9a-f]{16}', rep) and rep != did else ''
    mine = (lambda d: owns(d, who)) if who is not None else (lambda d: d.get('person') == person)
    with _dev_lock:
        try: devs = load_devices()
        except (OSError, ValueError): return 503, {'ok': False, 'msg': 'The server\'s list of devices cannot be read.'}
        old = next((d for d in devs if d['id'] == did), None)
        if old and old.get('person') != person: devs.remove(old); old = None     # the same browser, now someone else's
        gone = next((d for d in devs if rep and d['id'] == rep and mine(d)), None)
        if gone: devs.remove(gone)                       # this browser's record from before its address changed
        was = old or gone or {}
        label = label or str(was.get('label') or '') or 'This device'
        kinds = _clean_kinds(body.get('kinds')) if 'kinds' in body else _clean_kinds(was['kinds']) if 'kinds' in was else list(KINDS)
        if not old and sum(1 for d in devs if d.get('person') == person) >= MAX_DEVICES:
            return 409, {'ok': False, 'msg': f'Elaia already sends alerts to {MAX_DEVICES} of your devices. Remove one below, then try again.'}
        dev = old or {'id': did, 'person': person, 'made': now_iso(), 'last_ok': '', 'last_error': ''}
        if not old: devs.append(dev)
        dev.update(label=label, endpoint=endpoint, keys={'p256dh': b64(p256dh), 'auth': b64(auth)}, kinds=kinds)
        save_devices(devs)
    return 200, {'ok': True, 'id': did, 'msg': 'Alerts are on for this device.'}


def start(role, names=None):
    """Called once at server start: who counts as an owner, the name of a thing as the page calls it, and the sink."""
    global role_of, name_of
    role_of = role
    if names: name_of = names
    notify.register(sink)
