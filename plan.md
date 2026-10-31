# DevPulse: login with credentials (+ user details, weekly summary, chart)

## Context
`D:\ClaudeCodeWorkshop\index.html` is a working single-file DevPulse (log work + minutes, today list, user-details form, weekly summary with SVG bar chart; browser localStorage). Just rewritten, not yet browser-tested.
New request: a **login page with credentials**. A login that only lives in browser JS is not real security (anyone can read/skip it), so this needs a server. CLAUDE.md already defines the stack: Python stdlib-only `server.py` (run `python server.py`), tests in `test_server.py` (`python test_server.py`), plain JS in `index.html`, times as `1 h 30 min`.

## Approach
**server.py** (stdlib only: `http.server`, `hashlib.pbkdf2_hmac`, `secrets`, `hmac`, `json`, `sqlite3`)
- Storage: `devpulse.db` (sqlite3): `users(id, username unique, email, name, team, pw_salt, pw_hash)`, `entries(id, user_id, date, what, mins)`. Passwords: PBKDF2-SHA256, per-user random salt, >=200k iterations, constant-time compare. Never store/log plaintext.
- Sessions: random 32-byte token in an in-memory dict -> `Set-Cookie: session=...; HttpOnly; SameSite=Strict; Path=/` (add `Secure` when served over HTTPS). Expire after 8 h.
- Endpoints (JSON): `POST /api/register` (username, password >= 8 chars, name, email, team), `POST /api/login` (generic "Invalid credentials" error for both unknown user and wrong password), `POST /api/logout`, `GET /api/me`, `GET /api/entries`, `POST /api/entries`, `DELETE /api/entries/<id>`. Every entries route requires a valid session and filters by the session's user_id. Validate/limit all input (lengths, mins 1-1440, ISO date).
- Basic brute-force guard: per-username+IP failure counter, lock 60 s after 5 failures.
- Serves `index.html` at `/`; bind to `127.0.0.1` by default. Seed no default users.

**index.html** (plain JS, reuse existing `fmt`, `weekOf`, `drawChart`, `weekText`, `renderWeek`)
- Add login/register view (username, password; "Create account" toggle adds name, email, team) shown when `GET /api/me` returns 401; main app shown after login with name/email header + "Log out".
- Replace localStorage `load()/save()` for entries with `fetch` calls to the API; keep rendering code as is. Remove the separate profile form (details now come from registration; keep "Edit details" out of scope).
- Show server error messages via `textContent` (no innerHTML with user text).

**test_server.py** (stdlib `unittest`, starts the server on a random port with a temp db)
- register -> login -> add entry -> list; wrong password rejected with same message as unknown user; entries 401 without session; user A cannot read/delete user B's entries; lockout after 5 failures; password never in any response.

## Progress (2026-10-31)
- DONE: `server.py` and `test_server.py`; `python test_server.py` passes (9 tests).
- DONE: `index.html` has login/register, API-backed entries, Log out, weekly summary and the SVG bar chart. JS syntax check passes.
- DONE: live smoke test of the running server (page 200, /api/me 401 when logged out, register 201, add and list entry).
- NOT DONE: manual browser walkthrough (see Verification), including chart tooltip, dark mode and narrow layout.

## Files
- New: `D:\ClaudeCodeWorkshop\server.py`, `D:\ClaudeCodeWorkshop\test_server.py`
- Modify: `D:\ClaudeCodeWorkshop\index.html`

## Assumptions (not confirmed)
- Real accounts (register + login) with per-user data on the server, not a single hard-coded password.
- Local use over HTTP on localhost; for any real deployment it must sit behind HTTPS.
- Existing localStorage entries are not migrated.

## Verification
- `python test_server.py` passes.
- `python server.py`, open http://127.0.0.1:8000: register, log out, log in with wrong then right password; add entries; confirm today's list, weekly total and chart update; refresh keeps the session; second account sees none of the first's data; check browser console for errors, dark mode, and <480px layout.
