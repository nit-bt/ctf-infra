#!/usr/bin/env python3
"""ctf-live board: receives agent pushes and streams them live to a login-protected page.

Config: /etc/default/ctf-live-board (or CTF_LIVE_BOARD_CONF)
    PORT=3002
    LIVE_TOKEN=...              agents must send this (X-Live-Token)
    LIVE_USER=admin             page login
    LIVE_PASS_HASH=pbkdf2_sha256$...   set with:  sudo ctf-live-passwd
    STATE_DIR=/var/lib/ctf-live where the list of VMs is saved

Login security: PBKDF2-SHA256 password hash (never stored in plain text), session cookie
(random 256-bit, HttpOnly, Secure behind HTTPS, SameSite=Strict, 12 h), lockout after 5 wrong
tries per IP for 15 min plus a global cap, constant-time compares, CSRF checks (SameSite + Origin +
a custom header on API calls), strict security headers with a per-response script nonce.

Only the Python standard library. Keeps 5 minutes of history per server in memory.
VMs are added/removed from the page (Servers tab). An agent that reports for a name that isn't on the
list is added automatically; a removed VM stays hidden even if its agent keeps sending, until it's added again.

CLI:
    board.py --set-password     prompt for a new password, store its hash in the config
    board.py --hash             read a password on stdin, print its hash (used by the installer)
"""
import base64
import getpass
import hashlib
import hmac
import json
import os
import re
import secrets
import sys
import threading
import time
import urllib.parse
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
CONF = os.environ.get("CTF_LIVE_BOARD_CONF", "/etc/default/ctf-live-board")
HISTORY_SEC = 300
FORGET_SEC = 6 * 3600           # drop an unregistered server that hasn't reported for 6 h
SESSION_SEC = 12 * 3600
LOCK_TRIES, LOCK_WINDOW = 5, 15 * 60          # per IP: 5 wrong passwords in 15 min -> locked 15 min
GLOBAL_TRIES, GLOBAL_LOCK = 50, 5 * 60        # all IPs together: 50 in 15 min -> logins paused 5 min
PBKDF2_ITER = 600_000
COOKIE = "ctflive_sid"
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,39}$")
ROLES = ("platform", "chal", "monitor", "other")


# --------------------------------------------------------------------------- config / passwords
def load_conf(path):
    conf = {}
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    conf[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return conf


def hash_password(pw):
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, PBKDF2_ITER)
    return "pbkdf2_sha256$%d$%s$%s" % (PBKDF2_ITER, base64.b64encode(salt).decode(), base64.b64encode(dk).decode())


def check_password(pw, stored):
    try:
        algo, it, salt, dk = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        got = hashlib.pbkdf2_hmac("sha256", pw.encode(), base64.b64decode(salt), int(it))
        return hmac.compare_digest(got, base64.b64decode(dk))
    except Exception:
        return False


def set_conf_value(path, key, value, drop=()):
    lines = []
    try:
        with open(path) as f:
            lines = f.read().splitlines()
    except OSError:
        pass
    out, done = [], False
    for line in lines:
        k = line.split("=", 1)[0].strip()
        if k in drop:
            continue
        if k == key:
            out.append("%s=%s" % (key, value))
            done = True
        else:
            out.append(line)
    if not done:
        out.append("%s=%s" % (key, value))
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write("\n".join(out) + "\n")
    os.chmod(tmp, 0o600)
    try:
        st = os.stat(path)
        os.chown(tmp, st.st_uid, st.st_gid)
    except OSError:
        pass
    os.replace(tmp, path)


def cli():
    if "--hash" in sys.argv:
        pw = sys.stdin.readline().rstrip("\n")
        print(hash_password(pw))
        return True
    if "--set-password" in sys.argv:
        pw = getpass.getpass("New board password (12+ characters): ")
        if len(pw) < 12:
            raise SystemExit("Too short: use at least 12 characters.")
        if getpass.getpass("Again: ") != pw:
            raise SystemExit("Passwords don't match.")
        set_conf_value(CONF, "LIVE_PASS_HASH", hash_password(pw), drop=("LIVE_PASS",))
        print("Saved. Restart the board:  sudo systemctl restart ctf-live-board")
        return True
    return False


# --------------------------------------------------------------------------- state
C = {}
servers = {}                    # name -> {"data": {...}, "seen": t, "hist": deque[(t, cpu, ram%)]}
lock = threading.Lock()
changed = threading.Condition(lock)
registry, removed = {}, set()   # registry: name -> {"role", "added"}; removed: names to ignore
sessions = {}                   # token -> expires
fails = {}                      # ip -> deque of failure times
global_fails = deque()
global_pause_until = [0.0]
auth_lock = threading.Lock()


def reg_file():
    return os.path.join(C["STATE_DIR"], "servers.json")


def load_registry():
    try:
        with open(reg_file()) as f:
            r = json.load(f)
        return r.get("servers", {}), set(r.get("removed", []))
    except (OSError, ValueError):
        return {}, set()


def save_registry():
    try:
        os.makedirs(C["STATE_DIR"], exist_ok=True)
        tmp = reg_file() + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"servers": registry, "removed": sorted(removed)}, f, indent=1)
        os.replace(tmp, reg_file())
    except OSError as e:
        print("could not save %s: %s" % (reg_file(), e), flush=True)


def snapshot():
    now = time.time()
    out = []
    for name, s in list(servers.items()):
        if name in removed or (name not in registry and now - s["seen"] > FORGET_SEC):
            del servers[name]
            continue
        d = dict(s["data"])
        d["age"] = round(now - s["seen"], 1)
        d["hist"] = [[round(t - now, 1), c, r] for t, c, r in s["hist"]]
        out.append(d)
    reported = {d["name"] for d in out}
    for name, r in registry.items():
        if name not in reported and name not in removed:
            out.append({"name": name, "role": r.get("role", "chal"), "waiting": True,
                        "age": round(now - r.get("added", now), 1)})
    out.sort(key=lambda d: (d.get("role") != "platform", d.get("name", "")))
    return {"now": now, "servers": out}


def page(name, nonce, **subs):
    html = open(os.path.join(HERE, name), encoding="utf-8").read()
    html = html.replace("<script>", '<script nonce="%s">' % nonce)
    for k, v in subs.items():
        html = html.replace("{{%s}}" % k, v)
    return html.encode()


# --------------------------------------------------------------------------- HTTP
class H(BaseHTTPRequestHandler):
    server_version = "ctf-live"
    sys_version = ""

    def log_message(self, *a):
        pass

    # ---- request helpers
    def client_ip(self):
        remote = self.client_address[0]
        if remote in ("127.0.0.1", "::1"):         # behind Caddy: use the real client address
            ip = self.headers.get("CF-Connecting-IP") or self.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            if ip:
                return ip[:64]
        return remote

    def via_https(self):
        return self.client_address[0] in ("127.0.0.1", "::1") and self.headers.get("X-Forwarded-Proto") == "https"

    def cookie(self, name):
        for part in self.headers.get("Cookie", "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == name:
                return v
        return ""

    def session_ok(self):
        tok = self.cookie(COOKIE)
        if not tok:
            return False
        with auth_lock:
            exp = sessions.get(tok)
            if exp and exp > time.time():
                return True
            sessions.pop(tok, None)
        return False

    def same_origin(self):
        origin = self.headers.get("Origin")
        if not origin:
            return True          # old browsers / same-origin GETs; SameSite=Strict still protects the cookie
        host = self.headers.get("X-Forwarded-Host") or self.headers.get("Host", "")
        return urllib.parse.urlparse(origin).netloc == host

    def ui_ok(self):
        # page actions need the session AND a header a cross-site form can't send AND a same-origin request
        return self.session_ok() and self.headers.get("X-Live-UI") == "1" and self.same_origin()

    def read_body(self, limit):
        n = int(self.headers.get("Content-Length", "0") or 0)
        if n <= 0 or n > limit:
            return None
        return self.rfile.read(n)

    # ---- responses
    def headers_common(self, nonce=None):
        csp = ("default-src 'none'; img-src 'self' data:; connect-src 'self'; "
               "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; "
               "form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
        if nonce:
            csp += "; script-src 'nonce-%s'" % nonce
        self.send_header("Content-Security-Policy", csp)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "same-origin")   # no-referrer would make browsers send Origin: null on our own form posts
        self.send_header("Cache-Control", "no-store")

    def send_html(self, code, body, nonce, extra=()):
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.headers_common(nonce)
        for k, v in extra:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def redirect(self, to, extra=()):
        self.send_response(303)
        self.send_header("Location", to)
        self.headers_common()
        for k, v in extra:
            self.send_header(k, v)
        self.end_headers()

    def json_reply(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.headers_common()
        self.end_headers()
        self.wfile.write(body)

    def login_page(self, code=200, error=""):
        nonce = secrets.token_urlsafe(16)
        err = ('<p class="err" role="alert">%s</p>' % error) if error else ""
        self.send_html(code, page("login.html", nonce, ERROR=err, USER_HINT=""), nonce)

    def cookie_header(self, value, max_age):
        attrs = ["%s=%s" % (COOKIE, value), "Path=/", "HttpOnly", "SameSite=Strict", "Max-Age=%d" % max_age]
        if self.via_https():
            attrs.append("Secure")
        return ("Set-Cookie", "; ".join(attrs))

    # ---- login / logout
    def do_login(self):
        if not self.same_origin():
            return self.login_page(403, "Request blocked (wrong origin).")
        ip, now = self.client_ip(), time.time()
        with auth_lock:
            q = fails.setdefault(ip, deque())
            while q and now - q[0] > LOCK_WINDOW:
                q.popleft()
            while global_fails and now - global_fails[0] > LOCK_WINDOW:
                global_fails.popleft()
            if len(q) >= LOCK_TRIES:
                wait = int(LOCK_WINDOW - (now - q[0])) // 60 + 1
                return self.login_page(429, "Too many wrong tries from your network. Try again in %d min." % wait)
            if now < global_pause_until[0]:
                return self.login_page(429, "Logins are paused for a few minutes (too many failed attempts).")
        raw = self.read_body(2048) or b""
        form = urllib.parse.parse_qs(raw.decode("utf-8", "replace"))
        user = (form.get("username") or [""])[0]
        pw = (form.get("password") or [""])[0]
        ok_user = hmac.compare_digest(user.encode(), C["LIVE_USER"].encode())
        ok_pw = check_password(pw, C["LIVE_PASS_HASH"])      # always run (same time for wrong user or password)
        if ok_user and ok_pw:
            tok = secrets.token_urlsafe(32)
            with auth_lock:
                for t, exp in list(sessions.items()):
                    if exp < now:
                        sessions.pop(t, None)
                sessions[tok] = now + SESSION_SEC
                fails.pop(ip, None)
            print("login ok from %s" % ip, flush=True)
            return self.redirect("./", [self.cookie_header(tok, SESSION_SEC)])
        with auth_lock:
            fails[ip].append(now)
            global_fails.append(now)
            if len(global_fails) >= GLOBAL_TRIES:
                global_pause_until[0] = now + GLOBAL_LOCK
            left = LOCK_TRIES - len(fails[ip])
        print("login FAILED from %s (user %r)" % (ip, user[:40]), flush=True)
        time.sleep(1)
        msg = "Wrong username or password." + (" %d tries left." % left if 0 < left <= 3 else "")
        if left <= 0:
            msg = "Too many wrong tries from your network. Try again in 15 min."
        return self.login_page(401, msg)

    def do_logout(self):
        tok = self.cookie(COOKIE)
        with auth_lock:
            sessions.pop(tok, None)
        return self.redirect("login", [self.cookie_header("", 0)])

    # ---- methods
    def do_DELETE(self):
        if not self.path.startswith("/api/servers/"):
            return self.send_error(404)
        if not self.ui_ok():
            return self.json_reply(401 if not self.session_ok() else 403, {"error": "login required"})
        name = urllib.parse.unquote(self.path[len("/api/servers/"):])
        if not NAME_RE.match(name):
            return self.json_reply(400, {"error": "bad name"})
        with changed:
            registry.pop(name, None)
            servers.pop(name, None)
            removed.add(name)
            save_registry()
            changed.notify_all()
        return self.json_reply(200, self.api_servers())

    def do_POST(self):
        if self.path == "/login":
            return self.do_login()
        if self.path == "/logout":
            if not self.same_origin():
                return self.send_error(403)
            return self.do_logout()
        if self.path == "/api/servers":
            if not self.ui_ok():
                return self.json_reply(401 if not self.session_ok() else 403, {"error": "login required"})
            try:
                d = json.loads(self.read_body(4096) or b"{}")
            except ValueError:
                d = {}
            name, role = str(d.get("name", "")).strip(), str(d.get("role", "chal"))
            if not NAME_RE.match(name):
                return self.json_reply(400, {"error": "Name: letters, numbers, . _ - (max 40), e.g. contabo-chal-1"})
            if role not in ROLES:
                return self.json_reply(400, {"error": "Role must be one of: " + ", ".join(ROLES)})
            with changed:
                removed.discard(name)
                registry[name] = {"role": role, "added": time.time()}
                save_registry()
                changed.notify_all()
            return self.json_reply(200, self.api_servers())
        if self.path != "/push":
            return self.send_error(404)
        if not hmac.compare_digest(self.headers.get("X-Live-Token", "").encode(), C["LIVE_TOKEN"].encode()):
            return self.send_error(403)
        raw = self.read_body(64 * 1024)
        if raw is None:
            return self.send_error(413)
        try:
            d = json.loads(raw)
            name = str(d["name"])[:40]
            if not NAME_RE.match(name):
                raise ValueError
        except Exception:
            return self.send_error(400)
        now = time.time()
        ram_pct = 100.0 * d.get("ram_used", 0) / max(1, d.get("ram_total", 1))
        with changed:
            if name in removed:            # removed on the board: accept quietly, don't show
                self.send_response(204)
                self.end_headers()
                return
            if name not in registry:
                role = str(d.get("role", "chal"))
                registry[name] = {"role": role if role in ROLES else "other", "added": now}
                save_registry()
            s = servers.setdefault(name, {"hist": deque()})
            s["data"], s["seen"] = d, now
            s["hist"].append((now, d.get("cpu", 0), round(ram_pct, 1)))
            while s["hist"] and now - s["hist"][0][0] > HISTORY_SEC:
                s["hist"].popleft()
            changed.notify_all()
        self.send_response(204)
        self.end_headers()

    def api_servers(self):
        with lock:
            return {"servers": [{"name": n, "role": r.get("role"), "reporting": n in servers,
                                 "last_seen": round(time.time() - servers[n]["seen"], 1) if n in servers else None}
                                for n, r in sorted(registry.items()) if n not in removed],
                    "removed": sorted(removed)}

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/health":
            self.send_response(200)
            self.end_headers()
            return self.wfile.write(b"ok")
        if path == "/login":
            return self.redirect("./") if self.session_ok() else self.login_page()
        if not self.session_ok():
            if path.startswith("/api/") or path == "/stream":
                return self.json_reply(401, {"error": "login required"})
            return self.redirect("login")
        if path in ("/", "/index.html"):
            nonce = secrets.token_urlsafe(16)
            return self.send_html(200, page("index.html", nonce, USER=C["LIVE_USER"]), nonce)
        if path == "/api/me":
            return self.json_reply(200, {"user": C["LIVE_USER"]})
        if path == "/api/servers":
            return self.json_reply(200, self.api_servers())
        if path == "/api/agent-config":
            if self.headers.get("X-Live-UI") != "1":
                return self.json_reply(403, {"error": "forbidden"})
            return self.json_reply(200, {"token": C["LIVE_TOKEN"], "port": int(C["PORT"])})
        if path == "/stream":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            tok = self.cookie(COOKIE)
            try:
                while True:
                    with auth_lock:
                        if sessions.get(tok, 0) < time.time():
                            return                  # logged out or expired: close the stream
                    with changed:
                        msg = json.dumps(snapshot())
                    self.wfile.write(b"data: " + msg.encode() + b"\n\n")
                    self.wfile.flush()
                    with changed:
                        changed.wait(timeout=1.0)   # push arrived, or 1 s tick (so "no data" ages show)
            except (BrokenPipeError, ConnectionResetError, OSError):
                return
        self.send_error(404)


def main():
    global registry, removed
    C.update(load_conf(CONF))
    C.setdefault("PORT", "3002")
    C.setdefault("LIVE_USER", "admin")
    C.setdefault("STATE_DIR", "/var/lib/ctf-live")
    if not C.get("LIVE_TOKEN"):
        raise SystemExit("Set LIVE_TOKEN in %s" % CONF)
    if not C.get("LIVE_PASS_HASH"):
        if C.get("LIVE_PASS"):           # old plain-text config: hash it in memory, tell the admin to migrate
            C["LIVE_PASS_HASH"] = hash_password(C["LIVE_PASS"])
            print("WARNING: plain-text LIVE_PASS in %s. Run: sudo ctf-live-passwd" % CONF, flush=True)
        else:
            raise SystemExit("No password set. Run: sudo ctf-live-passwd")
    registry, removed = load_registry()
    srv = ThreadingHTTPServer(("0.0.0.0", int(C["PORT"])), H)
    srv.daemon_threads = True
    print("ctf-live board on :%s" % C["PORT"], flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    if not cli():
        main()
