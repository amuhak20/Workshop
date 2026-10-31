import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

import server


class Client:
    def __init__(self, base):
        self.base, self.cookie = base, None

    def call(self, method, path, body=None, raw=False):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        if self.cookie:
            req.add_header("Cookie", self.cookie)
        try:
            r = urllib.request.urlopen(req)
        except urllib.error.HTTPError as e:
            r = e
        text = r.read()
        sc = r.headers.get("Set-Cookie")
        if sc:
            self.cookie = None if sc.startswith("session=;") else sc.split(";")[0]
        return r.status, (text if raw else json.loads(text)), r.headers


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.srv = server.make_server(0, os.path.join(cls.tmp, "t.db"))
        cls.base = "http://127.0.0.1:%d" % cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def client(self):
        return Client(self.base)

    def register(self, c, user, pw="correct horse"):
        return c.call("POST", "/api/register",
                      {"username": user, "password": pw, "name": user.title(), "email": user + "@example.com", "team": "T"})

    def test_register_login_entries_flow(self):
        c = self.client()
        s, body, h = self.register(c, "alice")
        self.assertEqual(s, 201)
        self.assertIn("HttpOnly", h["Set-Cookie"])
        self.assertIn("SameSite=Strict", h["Set-Cookie"])
        self.assertEqual(c.call("GET", "/api/me")[1]["email"], "alice@example.com")
        s, e, _ = c.call("POST", "/api/entries", {"what": "Fix bug", "mins": 90, "date": "2026-10-30"})
        self.assertEqual(s, 201)
        self.assertEqual(c.call("GET", "/api/entries")[1][0]["mins"], 90)
        c.call("POST", "/api/logout", {})
        self.assertEqual(c.call("GET", "/api/me")[0], 401)
        c2 = self.client()
        self.assertEqual(c2.call("POST", "/api/login", {"username": "alice", "password": "correct horse"})[0], 200)
        self.assertEqual(len(c2.call("GET", "/api/entries")[1]), 1)

    def test_bad_credentials_same_message(self):
        c = self.client()
        self.register(c, "bob")
        c2 = self.client()
        s1, b1, _ = c2.call("POST", "/api/login", {"username": "bob", "password": "wrong-password"})
        s2, b2, _ = c2.call("POST", "/api/login", {"username": "nobody", "password": "wrong-password"})
        self.assertEqual((s1, s2), (401, 401))
        self.assertEqual(b1, b2)

    def test_requires_session(self):
        c = self.client()
        self.assertEqual(c.call("GET", "/api/entries")[0], 401)
        self.assertEqual(c.call("POST", "/api/entries", {"what": "x", "mins": 5})[0], 401)
        self.assertEqual(c.call("DELETE", "/api/entries/1")[0], 401)

    def test_users_are_isolated(self):
        a, b = self.client(), self.client()
        self.register(a, "carol")
        self.register(b, "dave")
        eid = a.call("POST", "/api/entries", {"what": "secret", "mins": 10})[1]["id"]
        self.assertEqual(b.call("GET", "/api/entries")[1], [])
        self.assertEqual(b.call("DELETE", "/api/entries/%d" % eid)[0], 404)
        self.assertEqual(len(a.call("GET", "/api/entries")[1]), 1)
        self.assertEqual(a.call("DELETE", "/api/entries/%d" % eid)[0], 200)

    def test_lockout_after_failures(self):
        c = self.client()
        self.register(c, "erin")
        c2 = self.client()
        for _ in range(5):
            self.assertEqual(c2.call("POST", "/api/login", {"username": "erin", "password": "nope-nope"})[0], 401)
        self.assertEqual(c2.call("POST", "/api/login", {"username": "erin", "password": "correct horse"})[0], 429)

    def test_validation(self):
        c = self.client()
        self.assertEqual(c.call("POST", "/api/register", {"username": "x", "password": "longenough", "name": "X", "email": "x@e.com"})[0], 400)
        self.assertEqual(c.call("POST", "/api/register", {"username": "frank", "password": "short", "name": "F", "email": "f@e.com"})[0], 400)
        self.assertEqual(c.call("POST", "/api/register", {"username": "frank", "password": "longenough", "name": "F", "email": "bad"})[0], 400)
        self.register(c, "gina")
        self.assertEqual(self.register(self.client(), "GINA")[0], 409)  # case-insensitive
        for bad in ({"what": "", "mins": 5}, {"what": "x", "mins": 0}, {"what": "x", "mins": 1441},
                    {"what": "x", "mins": "5"}, {"what": "x", "mins": True}, {"what": "x", "mins": 5, "date": "nope"}):
            self.assertEqual(c.call("POST", "/api/entries", bad)[0], 400, bad)

    def test_password_never_returned(self):
        c = self.client()
        _, body, _ = self.register(c, "hank", "s3cret-passphrase")
        blobs = json.dumps([body, c.call("GET", "/api/me")[1]])
        self.assertNotIn("s3cret-passphrase", blobs)
        self.assertNotIn("pw_", blobs)

    def test_rejects_non_json_and_cross_origin(self):
        req = urllib.request.Request(self.base + "/api/login", data=b"username=a", method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req)
        self.assertEqual(cm.exception.code, 415)
        req = urllib.request.Request(self.base + "/api/login", data=b"{}", method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Origin", "http://evil.example")
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req)
        self.assertEqual(cm.exception.code, 403)

    def test_serves_page(self):
        s, body, h = self.client().call("GET", "/", raw=True)
        self.assertEqual(s, 200)
        self.assertIn(b"DevPulse", body)
        self.assertIn("frame-ancestors", h["Content-Security-Policy"])


if __name__ == "__main__":
    unittest.main()
