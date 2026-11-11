"""server/identity.py without a server: the kernel's connection tables, the people file, who a request is (docs/people.md).

    python3 tests/identity_test.py -v        (tests/run.sh runs it under "== identity"; runs on Windows too)

The tables are canned text in the shape of /proc/net/tcp and /proc/net/tcp6 on a little-endian machine. One test reads this
machine's real tables for a real connection: it runs on Linux and says it is skipped elsewhere (no /proc)."""
import importlib.util, json, os, shutil, socket, sys, tempfile, time, unittest

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location('argus_identity', os.path.join(R, 'server', 'identity.py'))
idn = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(idn)
HAS_PROC = os.path.isfile('/proc/net/tcp')

HEAD = '  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode\n'
def row(n, local, remote, st='01', uid=0, inode=12345):
    return f'{n:4d}: {local} {remote} {st} 00000000:00000000 00:00000000 00000000 {uid:5d}        0 {inode} 1 0000000000000000 20 4 30 10 -1\n'

# 127.0.0.1:8095 is 0100007F:1F9F; a client on 127.0.0.1:54321 is 0100007F:D431
SERVER4, CLIENT4 = '0100007F:1F9F', '0100007F:D431'
# ::1 is four words 0,0,0,1, each printed in the machine's order: 00000000 00000000 00000000 01000000
SERVER6, CLIENT6 = '00000000000000000000000001000000:1F9F', '00000000000000000000000001000000:D431'
# ::ffff:127.0.0.1, how an IPv4 connection made through an IPv6 socket appears in tcp6
MAPPED_S, MAPPED_C = '0000000000000000FFFF00000100007F:1F9F', '0000000000000000FFFF00000100007F:D431'
PEER4, OURS4 = ('127.0.0.1', 54321), ('127.0.0.1', 8095)

class Tables(unittest.TestCase):
    def test_ipv4_row_and_owner_root(self):
        rows = idn.parse_table(HEAD + row(0, SERVER4, '00000000:0000', '0A', 1000) + row(1, CLIENT4, SERVER4, uid=0)
                               + row(2, SERVER4, CLIENT4, uid=1000), 'little')
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[1]['local'], (idn.norm('127.0.0.1'), 54321))
        self.assertEqual(idn.owner_uid(rows, PEER4, OURS4), 0, "the client's end of the connection is owned by root")

    def test_owner_is_someone_else(self):
        rows = idn.parse_table(HEAD + row(1, CLIENT4, SERVER4, uid=1000) + row(2, SERVER4, CLIENT4, uid=0), 'little')
        self.assertEqual(idn.owner_uid(rows, PEER4, OURS4), 1000, 'our own end (server -> client) is never the one read')

    def test_ipv6(self):
        rows = idn.parse_table(HEAD + row(0, CLIENT6, SERVER6, uid=0), 'little')
        self.assertEqual(rows[0]['local'][0], idn.norm('::1'))
        self.assertEqual(idn.owner_uid(rows, ('::1', 54321), ('::1', 8095)), 0)
        self.assertIsNone(idn.owner_uid(rows, PEER4, OURS4), '::1 is not 127.0.0.1')

    def test_ipv4_connection_in_the_ipv6_table(self):
        rows = idn.parse_table(HEAD + row(0, MAPPED_C, MAPPED_S, uid=0), 'little')
        self.assertEqual(rows[0]['local'][0], idn.norm('127.0.0.1'))
        self.assertEqual(idn.owner_uid(rows, PEER4, OURS4), 0)
        self.assertEqual(idn.owner_uid(rows, ('::ffff:127.0.0.1', 54321), ('127.0.0.1', 8095)), 0, 'either spelling of the peer')

    def test_no_row(self):
        rows = idn.parse_table(HEAD + row(1, CLIENT4, SERVER4, uid=0), 'little')
        self.assertIsNone(idn.owner_uid(rows, ('127.0.0.1', 54322), OURS4), 'another port: no row')
        self.assertIsNone(idn.owner_uid(rows, PEER4, ('127.0.0.1', 8096)), 'another server port: no row')
        self.assertIsNone(idn.owner_uid([], PEER4, OURS4))

    def test_closed_sockets_never_count_as_root(self):
        # after the client closes, the kernel keeps a stand-in that prints user id 0 and inode 0 (TIME_WAIT 06, FIN_WAIT2 05)
        for st in ('05', '06'):
            rows = idn.parse_table(HEAD + row(1, CLIENT4, SERVER4, st=st, uid=0, inode=0), 'little')
            self.assertIsNone(idn.owner_uid(rows, PEER4, OURS4), st)
        rows = idn.parse_table(HEAD + row(1, CLIENT4, SERVER4, uid=0, inode=0), 'little')
        self.assertIsNone(idn.owner_uid(rows, PEER4, OURS4), 'no socket behind the row: its owner is unknown')

    def test_our_own_end_must_match(self):
        rows = idn.parse_table(HEAD + row(1, CLIENT4, SERVER4, uid=0, inode=111) + row(2, SERVER4, CLIENT4, uid=1000, inode=222), 'little')
        self.assertEqual(idn.owner_uid(rows, PEER4, OURS4, our_inode=222), 0)
        self.assertIsNone(idn.owner_uid(rows, PEER4, OURS4, our_inode=333), 'a row of an earlier connection on the same ports')
        rows = idn.parse_table(HEAD + row(1, CLIENT4, SERVER4, uid=0, inode=111), 'little')
        self.assertIsNone(idn.owner_uid(rows, PEER4, OURS4, our_inode=222), 'our own end is not in the tables at all')

    def test_garbage(self):
        text = HEAD + 'garbage\n   7: ZZZZZZZZ:1F9F 0100007F:D431 01 x\n' + '   8: 0100007F 0100007F:D431 01 0 0 0 0 0 0\n\n' + row(9, CLIENT4, SERVER4, uid=0)
        rows = idn.parse_table(text, 'little')
        self.assertEqual(len(rows), 1, 'only the one good row is kept')
        self.assertEqual(idn.parse_table('', 'little'), []); self.assertEqual(idn.parse_table(None, 'little'), [])
        self.assertEqual(idn.parse_table('\x00\xff' * 50, 'little'), [])

    def test_missing_tables(self):
        d = tempfile.mkdtemp(prefix='identity-test-')
        try: self.assertIsNone(idn.connection_uid(PEER4, OURS4, proc=d), 'no /proc: no identity')
        finally: shutil.rmtree(d, ignore_errors=True)

    def test_serve_uid(self):
        said = []
        self.assertEqual(idn.serve_uid({}, own=1000), 0)
        self.assertEqual(idn.serve_uid({'ARGUS_SERVE_UID': '1001'}, own=1000), 1001)
        self.assertEqual(idn.serve_uid({'ARGUS_SERVE_UID': 'root'}, own=1000), 0, 'a value that is not a number: the default')
        self.assertIsNone(idn.serve_uid({'ARGUS_SERVE_UID': '1000'}, own=1000, log=said.append), "the page's own user is refused")
        self.assertEqual(len(said), 1); self.assertIn("page's own user", said[0])
        self.assertEqual(idn.serve_uid({'ARGUS_SERVE_UID': '1000', 'ARGUS_DEV': '1'}, own=1000), 1000, 'allowed for tests (ARGUS_DEV)')

    def test_own_addresses(self):
        for ip in ('127.0.0.1', '127.8.9.10', '::1', '::ffff:127.0.0.1', '0.0.0.0', '::', '[::1]'):
            self.assertTrue(idn.is_own_address(ip), ip)
        for ip in ('192.0.2.10', '2001:db8::7', 'not an address', ''):
            self.assertFalse(idn.is_own_address(ip), ip + ': another device, or not an address: never this machine')
        self.assertFalse(idn.from_this_machine(None), 'no header: changes nothing')
        self.assertTrue(idn.from_this_machine('127.0.0.1')); self.assertTrue(idn.from_this_machine('::1'))
        self.assertTrue(idn.from_this_machine('192.0.2.10, 127.0.0.1'), 'any own address in the list counts')
        self.assertTrue(idn.from_this_machine('127.0.0.1, 192.0.2.10'))
        self.assertFalse(idn.from_this_machine('192.0.2.10, 2001:db8::7'), 'two other devices')
        self.assertFalse(idn.from_this_machine('garbage, , ???'), 'unreadable: changes nothing (a phone is never locked out)')
        host = socket.gethostbyname(socket.gethostname())
        self.assertTrue(idn.is_own_address(host), f"this machine's own address {host} (found by binding to it)")

    def test_header_value(self):
        self.assertEqual(idn.header_value(' owner@example.com '), 'owner@example.com')
        self.assertEqual(idn.header_value('=?utf-8?q?J=C3=BCrgen?='), 'Jürgen')
        self.assertEqual(idn.header_value(None), '')

    @unittest.skipUnless(HAS_PROC, 'no /proc here: the real lookup runs on Linux (CI)')
    def test_real_connection_on_this_machine(self):
        srv = socket.socket(); srv.bind(('127.0.0.1', 0)); srv.listen(1)
        cli = socket.create_connection(srv.getsockname()); conn, peer = srv.accept()
        try:
            inode = os.fstat(conn.fileno()).st_ino
            uid = idn.connection_uid(peer, conn.getsockname(), our_inode=inode)
            print(f'\n  [real /proc lookup ran: client end owned by uid {uid}, our end inode {inode}]', file=sys.stderr)
            self.assertEqual(uid, os.getuid())
            self.assertIsNone(idn.connection_uid(peer, conn.getsockname(), our_inode=inode + 1), 'our own end must be the socket we hold')
        finally: conn.close(); cli.close(); srv.close()

class PeopleFile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='identity-people-'); self.f = os.path.join(self.tmp, 'people.json'); self.logged = []
    def tearDown(self): shutil.rmtree(self.tmp, ignore_errors=True)
    def write(self, doc):
        with open(self.f, 'w', encoding='utf-8') as fh: fh.write(doc if isinstance(doc, str) else json.dumps(doc))
        st = os.stat(self.f); os.utime(self.f, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000 * (len(self.logged) + 2)))
    def people(self): return idn.People(self.f, log=self.logged.append)
    GOOD = {'people': [{'id': 'owner-one', 'name': 'Owner One', 'role': 'owner', 'logins': ['Owner@Example.com']},
                       {'name': 'Learner Two', 'role': 'learner', 'logins': ['learner@example.com']}]}

    def test_no_file_is_everyone_the_owner(self):
        st = self.people().current()
        self.assertEqual(st, ('absent', None, None))
        for login, trusted in (('owner@example.com', True), (None, False), ('x@example.com', False)):
            self.assertEqual(idn.resolve(st, login, trusted), {'person': 'owner', 'name': 'You', 'role': 'owner'})

    def test_good_file_and_case(self):
        self.write(self.GOOD); st = self.people().current()
        self.assertEqual(st[0], 'ok')
        self.assertEqual(idn.resolve(st, 'OWNER@example.COM', True), {'person': 'owner-one', 'name': 'Owner One', 'role': 'owner'})
        self.assertEqual(idn.resolve(st, 'learner@EXAMPLE.com', True), {'person': 'learner-two', 'name': 'Learner Two', 'role': 'learner'},
                         'an id made from the name, and logins compared without regard to case')
        self.assertEqual(idn.resolve(st, 'stranger@example.com', True)['role'], 'none', 'a trusted login that is not listed')
        self.assertEqual(idn.resolve(st, 'owner@example.com', False)['role'], 'none', 'a listed login that is not trusted')
        self.assertEqual(idn.resolve(st, None, False), {'person': None, 'name': None, 'role': 'none'})

    def test_two_owners_allowed(self):
        doc = {'people': [dict(self.GOOD['people'][0]), {'name': 'Owner Three', 'role': 'owner', 'logins': ['three@example.com']}]}
        self.write(doc); st = self.people().current()
        self.assertEqual(st[0], 'ok'); self.assertEqual(idn.resolve(st, 'three@example.com', True)['role'], 'owner')

    def test_broken_files(self):
        cases = {'not json': '{"people": [', 'no list': {'folk': []}, 'not an object': [1],
                 'no owner': {'people': [{'name': 'Learner Two', 'role': 'learner', 'logins': ['learner@example.com']}]},
                 'one login twice': {'people': [self.GOOD['people'][0], {'name': 'Learner Two', 'role': 'learner', 'logins': ['OWNER@example.com']}]},
                 'a role that is neither': {'people': [self.GOOD['people'][0], {'name': 'X', 'role': 'admin', 'logins': []}]},
                 'logins not a list': {'people': [dict(self.GOOD['people'][0], logins='owner@example.com')]},
                 'no name': {'people': [self.GOOD['people'][0], {'role': 'learner'}]},
                 'one id twice': {'people': [self.GOOD['people'][0], {'id': 'owner-one', 'name': 'Other', 'role': 'learner'}]},
                 'no owner with a login': {'people': [dict(self.GOOD['people'][0], logins=[]), self.GOOD['people'][1]]},
                 'nested too deeply': '{"people": ' + '[' * 100000 + ']' * 100000 + '}'}
        for why, doc in cases.items():
            self.write(doc); st = self.people().current()
            self.assertEqual(st[0], 'broken', why); self.assertIn('people file', st[2], why)
            for login in ('owner@example.com', 'learner@example.com', 'stranger@example.com'):
                self.assertEqual(idn.resolve(st, login, True)['role'], 'none', why + ': no good copy known: closed to everyone')
        why = str(self._why({'people': cases['one login twice']['people']}))
        self.assertIn('entry 2 repeats a login of entry 1', why)
        self.assertNotIn('@', why, 'the reason names entries by number, never a login'); self.assertNotIn('Owner One', why)

    def _why(self, doc):
        try: idn.parse_people(doc)
        except ValueError as e: return e

    def test_broken_after_a_good_read_keeps_the_last_good_copy(self):
        ppl = self.people(); self.write(self.GOOD); self.assertEqual(ppl.current()[0], 'ok')
        self.write('{"people": [ broken'); st = ppl.current()
        self.assertEqual(st[0], 'stale'); self.assertIn('last good copy', st[2])
        self.assertEqual(idn.resolve(st, 'learner@example.com', True)['role'], 'learner', 'the last good copy still decides')
        self.assertEqual(idn.resolve(st, 'stranger@example.com', True)['role'], 'none')
        self.assertEqual(len(self.logged), 1); ppl.current(); ppl.current(); self.assertEqual(len(self.logged), 1, 'one log line, not one per request')
        self.write(self.GOOD); self.assertEqual(ppl.current(), ('ok', ppl.good, None), 'fixed: the problem is gone')

    def test_changed_on_disk_is_read_again(self):
        ppl = self.people(); self.write(self.GOOD)
        self.assertEqual(idn.resolve(ppl.current(), 'new@example.com', True)['role'], 'none')
        doc = json.loads(json.dumps(self.GOOD)); doc['people'][1]['logins'].append('new@example.com'); self.write(doc)
        self.assertEqual(idn.resolve(ppl.current(), 'new@example.com', True)['role'], 'learner', 'added without a restart')
        os.remove(self.f)
        self.assertEqual(ppl.current(), ('absent', None, None), 'the file taken away: as before people existed')

    def test_problem_never_names_the_home_folder(self):
        home = os.path.expanduser('~')
        self.assertEqual(idn.shown(os.path.join(home, '.config', 'argus-ui', 'people.json')), '~/.config/argus-ui/people.json')
        os.makedirs(self.f)                                       # a folder where the file should be: an OSError naming the path
        st = self.people().current()
        self.assertEqual(st[0], 'broken'); self.assertNotIn(self.tmp, st[2].replace(self.f, ''), st[2])
        self.assertNotIn(self.tmp, self.logged[-1].split(': ', 1)[1] if ': ' in self.logged[-1] else '', 'the reason itself carries no path')

    def test_an_unexpected_error_never_leaves_the_old_mode(self):
        ppl = self.people(); self.assertEqual(ppl.current()[0], 'absent')
        self.write('{"people": ' + '[' * 100000 + ']' * 100000 + '}')
        st = ppl.current(); self.assertEqual(st[0], 'broken'); self.assertIn('nested too deeply', st[2])
        self.assertEqual(ppl.current()[0], 'broken', 'asked again: still broken, not back to absent')

    @unittest.skipUnless(hasattr(os, 'symlink'), 'no symlinks here')
    def test_a_link_to_nothing_is_broken_not_absent(self):
        try: os.symlink(os.path.join(self.tmp, 'gone', 'people.json'), self.f)
        except OSError: self.skipTest('this system would not make a symlink')
        st = self.people().current()
        self.assertEqual(st[0], 'broken'); self.assertIn('link to a file that is not there', st[2])

    def test_last_good_copy_survives_a_restart(self):
        saved = os.path.join(self.tmp, 'state', 'people.last-good.json')
        ppl = idn.People(self.f, log=self.logged.append, last_good=saved); self.write(self.GOOD)
        self.assertEqual(ppl.current()[0], 'ok'); self.assertTrue(os.path.isfile(saved))
        if os.name == 'posix': self.assertEqual(os.stat(saved).st_mode & 0o777, 0o600, 'readable by this user only')
        self.write('{"people": [ broken')
        st = idn.People(self.f, log=self.logged.append, last_good=saved).current()     # a restart (or a deploy) with a broken file
        self.assertEqual(st[0], 'stale', 'the saved copy decides, nobody becomes the owner')
        self.assertEqual(idn.resolve(st, 'learner@example.com', True)['role'], 'learner')
        self.assertEqual(idn.resolve(st, 'stranger@example.com', True)['role'], 'none')

    def test_good_then_gone_then_broken_keeps_the_good_copy(self):
        ppl = self.people(); self.write(self.GOOD); self.assertEqual(ppl.current()[0], 'ok')
        os.remove(self.f); self.assertEqual(ppl.current()[0], 'absent')
        self.write('{"people": [ broken')                       # an editor that saves by rename, or a bad copy put back
        st = ppl.current(); self.assertEqual(st[0], 'stale')
        self.assertEqual(idn.resolve(st, 'stranger@example.com', True)['role'], 'none', 'a stranger never becomes the owner')

    def test_a_named_file_that_is_missing_is_broken(self):
        st = idn.People(self.f, log=self.logged.append, must_exist=True).current()
        self.assertEqual(st[0], 'broken', 'ARGUS_PEOPLE names a file that is not there: somebody meant one to be there')
        self.assertEqual(idn.resolve(st, 'owner@example.com', True)['role'], 'none')
        self.assertEqual(self.people().current()[0], 'absent', 'the default path, missing: no file')

    def test_a_broken_saved_copy_is_not_used(self):
        saved = os.path.join(self.tmp, 'saved.json')
        with open(saved, 'w') as fh: fh.write('{not json')
        self.write('{"people": [ broken')
        st = idn.People(self.f, log=self.logged.append, last_good=saved).current()
        self.assertEqual(st[0], 'broken'); self.assertEqual(idn.resolve(st, 'owner@example.com', True)['role'], 'none', 'closed')
        self.assertTrue(any('saved copy' in m for m in self.logged))

class Small(unittest.TestCase):
    def test_roles_and_allows(self):
        self.assertEqual(idn.plugin_roles({'get': {'next': 'learner', 'x': 'owner', 'y': 'none'}, 'post': {'answer': 'learner'}, 'put': {}}),
                         {'get': {'next': 'learner'}, 'post': {'answer': 'learner'}})
        self.assertEqual(idn.plugin_roles(None), {'get': {}, 'post': {}}); self.assertEqual(idn.plugin_roles(['x']), {'get': {}, 'post': {}})
        self.assertTrue(idn.allows('owner', 'owner')); self.assertTrue(idn.allows('learner', 'learner')); self.assertTrue(idn.allows('none', 'none'))
        self.assertFalse(idn.allows('learner', 'owner')); self.assertFalse(idn.allows('none', 'learner')); self.assertFalse(idn.allows('learner', 'nonsense'), 'an unknown need is the owner')

    def test_private_page_escapes_the_login(self):
        html = idn.private_page('<script>alert(1)</script>@example.com', True)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;@example.com', html); self.assertNotIn('<script', html)
        self.assertIn('did not come through Tailscale', idn.private_page(None, False))
        self.assertIn('came from the server itself', idn.private_page('owner@example.com', False, from_self=True))
        closed = idn.private_page('owner@example.com', True, closed=True)
        self.assertIn('move the people file aside to a dated name', closed); self.assertIn('closed to everyone', closed)
        self.assertNotIn('<script', idn.private_page(None, False)); self.assertNotRegex(html, r'(src|href)="(https?:)?//')

if __name__ == '__main__':
    unittest.main()
