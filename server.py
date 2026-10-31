"""DevPulse server: login, per-user entries. Python standard library only.

Run:   python server.py [port]        (default 127.0.0.1:8000)
Tests: python test_server.py
"""
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import sys
import threading
import time
from datetime import date
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "devpulse.db")
PBKDF2_ITERATIONS = 240_000
SESSION_TTL = 8 * 3600
MAX_FAILS, LOCK_SECONDS = 5, 60
MAX_BODY = 10_000

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL UNIQUE COLLATE NOCASE,
  name TEXT NOT NULL, email TEXT NOT NULL, team TEXT NOT NULL DEFAULT '',
  pw_salt BLOB NOT NULL, pw_hash BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS entries(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id),
  date TEXT NOT NULL, what TEXT NOT NULL, mins INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS entries_user_date ON entries(user_id, date);
"""


def hash_password(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)


_DUMMY_SALT = secrets.token_bytes(16)
_DUMMY_HASH = hash_password("dummy-password", _DUMMY_SALT)


class State:
    """Per-server state: db path, sessions, login-failure counters."""

    def __init__(self, db_path):
        self.db_path = db_path
        self.lock = threading.Lock()
        self.sessions = {}   # token -> (user_id, expires)
        self.fails = {}      # (username, ip) -> (count, locked_until)
        c = self.db()
        try:
            c.executescript(SCHEMA)
        finally:
            c.close()

    def db(self):
        c = sqlite3.connect(self.db_path)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        return c

    def run(self, sql, args=(), one=False, write=False):
        c = self.db()
        try:
            cur = c.execute(sql, args)
            if write:
                c.commit()
                return cur
            return cur.fetchone() if one else cur.fetchall()
        finally:
            c.close()

    def new_session(self, user_id):
        token = secrets.token_urlsafe(32)
        with self.lock:
            now = time.time()
            self.sessions = {t: v for t, v in self.sessions.items() if v[1] > now}
            self.sessions[token] = (user_id, now + SESSION_TTL)
        return token

    def session_user(self, token):
        with self.lock:
            v = self.sessions.get(token)
            if v and v[1] > time.time():
                return v[0]
            self.sessions.pop(token, None)
        return None

    def end_session(self, token):
        with self.lock:
            self.sessions.pop(token, None)

    def locked(self, key):
        with self.lock:
            n, until = self.fails.get(key, (0, 0))
            return n >= MAX_FAILS and until > time.time()

    def record_fail(self, key):
        with self.lock:
            n, until = self.fails.get(key, (0, 0))
            if n >= MAX_FAILS and until <= time.time():
                n = 0
            n += 1
            self.fails[key] = (n, time.time() + LOCK_SECONDS if n >= MAX_FAILS else 0)

    def clear_fails(self, key):
        with self.lock:
            self.fails.pop(key, None)


def make_handler(state, secure_cookie=False):
    class Handler(BaseHTTPRequestHandler):
        server_version = "DevPulse"
        sys_version = ""

        def log_message(self, fmt, *args):  # request line only; never bodies/credentials
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

        # ---- helpers ----
        def send_json(self, status, obj, cookie=None):
            body = json.dumps(obj).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            if cookie:
                self.send_header("Set-Cookie", cookie)
            self.end_headers()
            self.wfile.write(body)

        def err(self, status, msg):
            self.send_json(status, {"error": msg})

        def cookie_header(self, token, max_age):
            c = "session=%s; HttpOnly; SameSite=Strict; Path=/; Max-Age=%d" % (token, max_age)
            return c + ("; Secure" if secure_cookie else "")

        def token(self):
            try:
                m = SimpleCookie(self.headers.get("Cookie", "")).get("session")
            except Exception:
                return None
            return m.value if m else None

        def current_user(self):
            t = self.token()
            uid = state.session_user(t) if t else None
            if uid is None:
                return None
            return state.run("SELECT id,username,name,email,team FROM users WHERE id=?", (uid,), one=True)

        def read_json(self):
            if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                self.err(415, "Content-Type must be application/json")
                return None
            origin = self.headers.get("Origin")
            if origin and origin.split("://", 1)[-1] != self.headers.get("Host"):
                self.err(403, "Cross-origin request refused")
                return None
            try:
                n = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                n = -1
            if n < 0 or n > MAX_BODY:
                self.err(413, "Request body too large")
                return None
            try:
                data = json.loads(self.rfile.read(n) or b"{}")
            except ValueError:
                self.err(400, "Invalid JSON")
                return None
            if not isinstance(data, dict):
                self.err(400, "Expected a JSON object")
                return None
            return data

        @staticmethod
        def text(d, key, lo, hi):
            v = d.get(key, "")
            if not isinstance(v, str):
                return None
            v = v.strip()
            return v if lo <= len(v) <= hi else None

        # ---- routing ----
        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                try:
                    with open(os.path.join(HERE, "index.html"), "rb") as f:
                        body = f.read()
                except OSError:
                    return self.err(500, "index.html missing")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Security-Policy",
                                 "default-src 'self'; script-src 'unsafe-inline'; "
                                 "style-src 'unsafe-inline'; frame-ancestors 'none'")
                self.end_headers()
                self.wfile.write(body)
                return
            if path == "/api/me":
                u = self.current_user()
                return self.send_json(200, dict(u)) if u else self.err(401, "Not logged in")
            if path == "/api/entries":
                u = self.current_user()
                if not u:
                    return self.err(401, "Not logged in")
                rows = state.run("SELECT id,date,what,mins FROM entries WHERE user_id=? ORDER BY id", (u["id"],))
                return self.send_json(200, [dict(r) for r in rows])
            self.err(404, "Not found")

        def do_POST(self):
            path = self.path.split("?", 1)[0]
            if path == "/api/logout":
                t = self.token()
                if t:
                    state.end_session(t)
                return self.send_json(200, {"ok": True}, self.cookie_header("", 0))
            d = self.read_json()
            if d is None:
                return
            if path == "/api/register":
                return self.register(d)
            if path == "/api/login":
                return self.login(d)
            if path == "/api/entries":
                return self.add_entry(d)
            self.err(404, "Not found")

        def do_DELETE(self):
            m = re.fullmatch(r"/api/entries/(\d+)", self.path.split("?", 1)[0])
            if not m:
                return self.err(404, "Not found")
            u = self.current_user()
            if not u:
                return self.err(401, "Not logged in")
            cur = state.run("DELETE FROM entries WHERE id=? AND user_id=?", (int(m.group(1)), u["id"]), write=True)
            if cur.rowcount:
                return self.send_json(200, {"ok": True})
            self.err(404, "Not found")

        # ---- handlers ----
        def register(self, d):
            username = self.text(d, "username", 3, 32)
            name = self.text(d, "name", 1, 80)
            email = self.text(d, "email", 3, 120)
            team = d.get("team", "")
            team = team.strip() if isinstance(team, str) and len(team.strip()) <= 80 else None
            pw = d.get("password")
            if not username or not USERNAME_RE.match(username):
                return self.err(400, "Username must be 3-32 letters, digits, . _ -")
            if not name:
                return self.err(400, "Name is required")
            if not email or not EMAIL_RE.match(email):
                return self.err(400, "A valid email is required")
            if team is None:
                return self.err(400, "Team is too long")
            if not isinstance(pw, str) or not 8 <= len(pw) <= 128:
                return self.err(400, "Password must be 8-128 characters")
            salt = secrets.token_bytes(16)
            try:
                cur = state.run("INSERT INTO users(username,name,email,team,pw_salt,pw_hash) VALUES(?,?,?,?,?,?)",
                                (username, name, email, team, salt, hash_password(pw, salt)), write=True)
            except sqlite3.IntegrityError:
                return self.err(409, "Username already taken")
            self.send_json(201, {"username": username, "name": name, "email": email, "team": team},
                           self.cookie_header(state.new_session(cur.lastrowid), SESSION_TTL))

        def login(self, d):
            username, pw = d.get("username"), d.get("password")
            if not isinstance(username, str) or not isinstance(pw, str) or len(username) > 64 or len(pw) > 128:
                return self.err(401, "Invalid credentials")
            key = (username.lower(), self.client_address[0])
            if state.locked(key):
                return self.err(429, "Too many failed attempts. Try again in a minute.")
            row = state.run("SELECT id,pw_salt,pw_hash FROM users WHERE username=?", (username,), one=True)
            salt, good = (row["pw_salt"], row["pw_hash"]) if row else (_DUMMY_SALT, _DUMMY_HASH)
            ok = hmac.compare_digest(hash_password(pw, salt), good) and row is not None
            if not ok:
                state.record_fail(key)
                return self.err(401, "Invalid credentials")
            state.clear_fails(key)
            self.send_json(200, {"ok": True}, self.cookie_header(state.new_session(row["id"]), SESSION_TTL))

        def add_entry(self, d):
            u = self.current_user()
            if not u:
                return self.err(401, "Not logged in")
            what = self.text(d, "what", 1, 200)
            mins = d.get("mins")
            day = d.get("date") or date.today().isoformat()
            if not what:
                return self.err(400, "Describe what you worked on (max 200 characters)")
            if isinstance(mins, bool) or not isinstance(mins, int) or not 1 <= mins <= 1440:
                return self.err(400, "Minutes must be a whole number from 1 to 1440")
            try:
                day = date.fromisoformat(day).isoformat() if isinstance(day, str) else None
            except ValueError:
                day = None
            if not day:
                return self.err(400, "Invalid date")
            cur = state.run("INSERT INTO entries(user_id,date,what,mins) VALUES(?,?,?,?)",
                            (u["id"], day, what, mins), write=True)
            self.send_json(201, {"id": cur.lastrowid, "date": day, "what": what, "mins": mins})

    return Handler


def make_server(port=8000, db_path=DB_PATH, host="127.0.0.1"):
    return ThreadingHTTPServer((host, port), make_handler(State(db_path)))


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    srv = make_server(port)
    print("DevPulse running at http://127.0.0.1:%d  (Ctrl+C to stop)" % port)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
