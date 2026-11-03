#!/usr/bin/env python3
"""ctf-live board: receives agent pushes and streams them live to a password-protected page.

Config: /etc/default/ctf-live-board (or CTF_LIVE_BOARD_CONF)
    PORT=3002
    LIVE_TOKEN=...          agents must send this (X-Live-Token)
    LIVE_USER=admin         page login (HTTP basic auth)
    LIVE_PASS=...

Only the Python standard library. Keeps 5 minutes of history per server in memory.
"""
import base64
import hmac
import json
import os
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
if not TOKEN or not PASS:
    raise SystemExit("Set LIVE_TOKEN and LIVE_PASS in %s" % CONF)

servers = {}                    # name -> {"data": {...}, "seen": t, "hist": deque[(t, cpu, ram%)]}
lock = threading.Lock()
changed = threading.Condition(lock)


def snapshot():
    now = time.time()
    out = []
    for name, s in list(servers.items()):
        if now - s["seen"] > FORGET_SEC:
            del servers[name]
            continue
        d = dict(s["data"])
        d["age"] = round(now - s["seen"], 1)
        d["hist"] = [[round(t - now, 1), c, r] for t, c, r in s["hist"]]
        out.append(d)
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

    def do_POST(self):
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
