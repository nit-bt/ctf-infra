#!/usr/bin/env python3
"""ctf-live agent: sends this server's live stats to the ctf-live board every INTERVAL seconds.

Config: /etc/default/ctf-live (or CTF_LIVE_CONF)
    LIVE_URL=http://<monitor-ip>:3002     the board
    LIVE_TOKEN=...                        same token as the board
    NAME=challenge-ctf                    shown on the card (default: hostname)
    ROLE=chal                             chal | platform
    INTERVAL=2                            seconds
    SITE_URL=http://localhost             platform only: checked every 10 s

Only the Python standard library. Reads /proc and the cgroup files directly (cheap),
asks Docker for container names every 15 s.
"""
import glob
import json
import os
import socket
import subprocess
import time
import urllib.request

CONF = os.environ.get("CTF_LIVE_CONF", "/etc/default/ctf-live")


def load_conf(path):
    conf = {}
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                conf[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return conf


C = load_conf(CONF)
URL = C.get("LIVE_URL", "").rstrip("/")
TOKEN = C.get("LIVE_TOKEN", "")
NAME = C.get("NAME") or socket.gethostname()
ROLE = C.get("ROLE", "chal")
INTERVAL = max(1.0, float(C.get("INTERVAL", "2")))
SITE_URL = C.get("SITE_URL", "http://localhost")


def read(path, default=""):
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return default


def cpu_times():
    parts = read("/proc/stat").split("\n", 1)[0].split()[1:]
    vals = [int(x) for x in parts]
    idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
    return sum(vals), idle


def net_bytes():
    rx = tx = 0
    for line in read("/proc/net/dev").splitlines()[2:]:
        name, data = line.split(":", 1)
        name = name.strip()
        if name == "lo" or name.startswith(("docker", "veth", "br-")):
            continue
        f = data.split()
        rx += int(f[0])
        tx += int(f[8])
    return rx, tx


def meminfo():
    m = {}
    for line in read("/proc/meminfo").splitlines():
        k, v = line.split(":", 1)
        m[k] = int(v.split()[0])
    total = m.get("MemTotal", 1)
    avail = m.get("MemAvailable", 0)
    return total, avail


def container_cgroups():
    """{full_id: cgroup_dir} for running Docker containers (cgroup v2, systemd driver)."""
    out = {}
    for d in glob.glob("/sys/fs/cgroup/system.slice/docker-*.scope"):
        cid = os.path.basename(d)[len("docker-"):-len(".scope")]
        out[cid] = d
    return out


_names = {"t": 0, "map": {}}


def container_names():
    if time.time() - _names["t"] > 15:
        try:
            r = subprocess.run(["docker", "ps", "--no-trunc", "--format", "{{.ID}}\t{{.Names}}\t{{.Image}}"],
                               capture_output=True, text=True, timeout=5)
            m = {}
            for line in r.stdout.splitlines():
                cid, name, image = (line.split("\t") + ["", ""])[:3]
                m[cid] = (name, image)
            _names["map"] = m
        except Exception:
            pass
        _names["t"] = time.time()
    return _names["map"]


def site_check():
    t0 = time.time()
    try:
        req = urllib.request.Request(SITE_URL, headers={"User-Agent": "ctf-live"})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req, timeout=3) as r:
            code = r.status
    except urllib.error.HTTPError as e:
        code = e.code
    except Exception:
        code = 0
    return {"code": code, "ms": int((time.time() - t0) * 1000)}


def send(payload):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(URL + "/push", data=body, method="POST",
                                 headers={"Content-Type": "application/json", "X-Live-Token": TOKEN})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=3) as r:
        r.read()


def main():
    if not URL or not TOKEN:
        raise SystemExit("Set LIVE_URL and LIVE_TOKEN in %s" % CONF)
    prev_cpu = cpu_times()
    prev_net = net_bytes()
    prev_ccpu = {}
    prev_t = time.time()
    site = None
    site_t = 0
    ncpu = os.cpu_count() or 1
    while True:
        time.sleep(INTERVAL)
        now = time.time()
        dt = max(0.001, now - prev_t)

        tot, idle = cpu_times()
        dtot, didle = tot - prev_cpu[0], idle - prev_cpu[1]
        cpu = 0.0 if dtot <= 0 else 100.0 * (dtot - didle) / dtot
        prev_cpu = (tot, idle)

        rx, tx = net_bytes()
        net_in, net_out = (rx - prev_net[0]) / dt, (tx - prev_net[1]) / dt
        prev_net = (rx, tx)

        total, avail = meminfo()
        st = os.statvfs("/")
        disk = 100.0 * (1 - st.f_bavail / st.f_blocks) if st.f_blocks else 0

        cgs = container_cgroups()
        names = container_names()
        conts = []
        new_ccpu = {}
        for cid, d in cgs.items():
            mem = int(read(d + "/memory.current", "0") or 0)
            usage = 0
            for line in read(d + "/cpu.stat").splitlines():
                if line.startswith("usage_usec"):
                    usage = int(line.split()[1])
            new_ccpu[cid] = usage
            ccpu = 0.0
            if cid in prev_ccpu:
                ccpu = max(0.0, (usage - prev_ccpu[cid]) / (dt * 1e6) * 100.0)   # % of one CPU
            name, image = names.get(cid, (cid[:12], ""))
            conts.append({"name": name, "image": image, "mem": mem, "cpu": round(ccpu, 1)})
        prev_ccpu = new_ccpu
        prev_t = now
        conts.sort(key=lambda c: c["mem"], reverse=True)

        if ROLE == "platform" and now - site_t >= 10:
            site = site_check()
            site_t = now

        payload = {
            "name": NAME[:40], "role": ROLE, "t": int(now), "interval": INTERVAL,
            "cpu": round(cpu, 1), "ncpu": ncpu, "load": float(read("/proc/loadavg", "0").split()[0]),
            "ram_used": (total - avail) * 1024, "ram_total": total * 1024,
            "disk": round(disk, 1), "net_in": int(net_in), "net_out": int(net_out),
            "containers": len(conts), "cont_mem": sum(c["mem"] for c in conts),
            "top": conts[:8], "site": site,
        }
        try:
            send(payload)
        except Exception:
            pass   # board unreachable: keep going, the card turns "no data" on the board


if __name__ == "__main__":
    main()
