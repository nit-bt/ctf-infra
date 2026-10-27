# Crash test · GCP sandbox · 28 Oct 2026

**Result:** one 4 vCPU / 8 GB challenge server holds about **30 worst-case players**. Past that it doesn't crash:
Docker gets too slow to start new instances and RAM sits at 98 %. The platform is unaffected throughout,
and every alert fired.

## Setup

| | |
|---|---|
| Challenge server | `challenge-ctf`, 4 vCPU / 8 GB, no swap, firewall on, limits 256 MB / 0.5 CPU per instance |
| Platform | `platform-ctf`, CTFd 3.7.7 + plugin fork |
| Instance | `ctf/stress` (plugin `tools/stress-image`): holds ~230 MB and burns its full CPU share. The worst possible player, far heavier than real challenges |
| Tool | `tools/load-test.py`, players start at the same moment, `--keep` between steps |
| Watching | ctf-alert → Discord `#ctf-alerts` + `#ctf-status`, Uptime Kuma Push monitors |

## Results

| Step | Instances | What happened |
|---|---|---|
| 20 players | 20 | fine |
| 30 players | 30 started, 26 answered in time | RAM **98 %** (130 MB free), load **31.7** on 4 vCPU, **3 instances OOM-killed** (exit 137). Alert *RAM at 98 %* within a minute |
| 45 players (fresh) | 22 started, **23 failed** | `Could not start container: Cannot reach Docker host 'chal-1' … Read timed out`. Starts: median 9.9 s, 95 % 40.4 s, slowest 42.7 s. Server still up and reporting, RAM 98 % |
| Platform, all steps | n/a | RAM 809 MB, load 0.19: a drowning challenge server does not affect the site |

Alerts: RAM alert, Kuma Down with the reason, Discord cards 🔴 with the reason, reports arriving late
(orange in Kuma) while the CPU was starved, ✅ after cleanup.

## Findings

1. **Capacity: ~30 worst-case instances per 8 GB server.** Matches the estimate (25 × 256 MB ≈ 7.1 GB). The internal CTF
   has 25 players with one instance each, so it fits even in the worst case. Real challenges use far less (re-test with them).
2. **What breaks first is the Docker API, not the server.** Under overload Docker answers CTFd too slowly (10 s timeout),
   so players get "Could not start container". The server stays reachable, alerts keep coming (late).
3. **CPU saturates before RAM matters.** 30 × 0.5 CPU wanted on 4 vCPU = load 31. Real challenges idle most of the time.
4. **Nuke All didn't work under overload.** It removed instances one by one (up to 10 s each) and the page showed nothing.
   → **Fixed** in plugin `a28ad1b`: removes all in parallel with an 8 s timeout, shows progress and "Removed N".
5. **Fastest emergency cleanup is on the server itself:** `sudo docker rm -f $(sudo docker ps -q)`, then Nuke All in CTFd to clear the records.

## Event-day takeaways

- One 4 vCPU / 8 GB challenge server is enough for the internal CTF (25 players).
- If RAM > 85 % alerts on the day: shorten the instance lifetime first (Docker Config), lower the RAM cap only if the
  challenges' measured peak allows it (docs/05, measure with `docker stats`).
- If Docker is too slow ("Could not start container" for many players): remove idle/old instances, or move a heavy
  challenge to the GCP spare host (docs/failover.md, scenario B).

## Next

- [ ] Re-run with the real challenge images (expected: much more headroom)
- [ ] Re-run on Contabo before the event (slower shared CPUs)
- [ ] Delete the STRESS challenge and `loadtest-*` users
