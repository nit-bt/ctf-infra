#!/usr/bin/env python3
"""ctf-live board: receives agent pushes and streams them live to a password-protected page.

Config: /etc/default/ctf-live-board (or CTF_LIVE_BOARD_CONF)
    PORT=3002
    LIVE_TOKEN=...          agents must send this (X-Live-Token)
    LIVE_USER=admin         page login (HTTP basic auth)
    LIVE_PASS=...
    STATE_DIR=/var/lib/ctf-live   where the list of VMs is saved

Only the Python standard library. Keeps 5 minutes of history per server in memory.
VMs are added/removed from the page (Servers panel). An agent that reports for a name that isn't on the
list is added automatically; a removed VM stays hidden even if its agent keeps sending, until it's added again.
"""
import base64
import hmac
import json
import os
import re
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
CONF = os.environ.get("CTF_LIVE_BOARD_CONF", "/etc/default/ctf-live-board")
HISTORY_SEC = 300
FORGET_SEC = 6 * 3600          # drop a server that hasn't reported for 6 h


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


C = load_conf(CONF)
PORT = int(C.get("PORT", "3002"))
TOKEN = C.get("LIVE_TOKEN", "")
USER = C.get("LIVE_USER", "admin")
PASS = C.get("LIVE_PASS", "")
STATE_DIR = C.get("STATE_DIR", "/var/lib/ctf-live")
if not TOKEN or not PASS:
    raise SystemExit("Set LIVE_TOKEN and LIVE_PASS in %s" % CONF)
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,39}$")
ROLES = ("platform", "chal", "monitor", "other")

servers = {}                    # name -> {"data": {...}, "seen": t, "hist": deque[(t, cpu, ram%)]}
lock = threading.Lock()
changed = threading.Condition(lock)
REG_FILE = os.path.join(STATE_DIR, "servers.json")


def load_registry():
    try:
        with open(REG_FILE) as f:
            r = json.load(f)
        return r.get("servers", {}), set(r.get("removed", []))
    except (OSError, ValueError):
        return {}, set()


registry, removed = load_registry()   # registry: name -> {"role", "added"}; removed: names to ignore


def save_registry():
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        tmp = REG_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"servers": registry, "removed": sorted(removed)}, f, indent=1)
        os.replace(tmp, REG_FILE)
    except OSError as e:
        print("could not save %s: %s" % (REG_FILE, e), flush=True)


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


class H(BaseHTTPRequestHandler):
    server_version = "ctf-live"

    def log_message(self, *a):
        pass

    def authed(self):
        h = self.headers.get("Authorization", "")
        if h.startswith("Basic "):
            try:
                u, p = base64.b64decode(h[6:]).decode().split(":", 1)
            except Exception:
                return False
            return hmac.compare_digest(u, USER) and hmac.compare_digest(p, PASS)
        return False

    def deny(self):
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="CTFC Live"')
        self.end_headers()

    def json_reply(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def ui_ok(self):
        # page actions need the login AND a header a cross-site form can't send (blocks CSRF)
        return self.authed() and self.headers.get("X-Live-UI") == "1"

    def read_json(self):
        n = int(self.headers.get("Content-Length", "0") or 0)
        if n <= 0 or n > 4096:
            return None
        try:
            return json.loads(self.rfile.read(n))
        except ValueError:
            return None

    def api_servers(self):
        with lock:
            return {"servers": [{"name": n, "role": r.get("role"), "reporting": n in servers,
                                 "last_seen": round(time.time() - servers[n]["seen"], 1) if n in servers else None}
                                for n, r in sorted(registry.items()) if n not in removed],
                    "removed": sorted(removed)}

    def do_DELETE(self):
        if not self.path.startswith("/api/servers/"):
            return self.send_error(404)
        if not self.ui_ok():
            return self.deny() if not self.authed() else self.send_error(403)
        name = self.path[len("/api/servers/"):]
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
        if self.path == "/api/servers":
            if not self.ui_ok():
                return self.deny() if not self.authed() else self.send_error(403)
            d = self.read_json() or {}
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
        if not hmac.compare_digest(self.headers.get("X-Live-Token", ""), TOKEN):
            return self.send_error(403)
        n = int(self.headers.get("Content-Length", "0") or 0)
        if n <= 0 or n > 64 * 1024:
            return self.send_error(413)
        try:
            d = json.loads(self.rfile.read(n))
            name = str(d["name"])[:40]
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
                registry[name] = {"role": str(d.get("role", "chal"))[:10], "added": now}
                save_registry()
            s = servers.setdefault(name, {"hist": deque()})
            s["data"], s["seen"] = d, now
            s["hist"].append((now, d.get("cpu", 0), round(ram_pct, 1)))
            while s["hist"] and now - s["hist"][0][0] > HISTORY_SEC:
                s["hist"].popleft()
            changed.notify_all()
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.end_headers()
            return self.wfile.write(b"ok")
        if not self.authed():
            return self.deny()
        if self.path in ("/", "/index.html"):
            body = open(os.path.join(HERE, "index.html"), "rb").read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return self.wfile.write(body)
        if self.path == "/api/servers":
            return self.json_reply(200, self.api_servers())
        if self.path == "/api/agent-config":
            return self.json_reply(200, {"token": TOKEN, "port": PORT})
        if self.path == "/stream":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            try:
                while True:
                    with changed:
                        msg = json.dumps(snapshot())
                    self.wfile.write(b"data: " + msg.encode() + b"\n\n")
                    self.wfile.flush()
                    with changed:
                        changed.wait(timeout=1.0)   # push arrived, or 1 s tick (so "no data" ages show)
            except (BrokenPipeError, ConnectionResetError, OSError):
                return
        self.send_error(404)


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), H)
    srv.daemon_threads = True
    print("ctf-live board on :%d" % PORT, flush=True)
    srv.serve_forever()
