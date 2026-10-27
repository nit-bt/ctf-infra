# Load test · GCP sandbox · 27 Oct 2026

**Result: PASS.** 25 players starting at the same second all got a working instance, spread over 2 challenge servers.

## Setup

| | |
|---|---|
| Where | GCP `asia-southeast1-c`, Ubuntu 26.04 |
| Platform | `platform-ctf`, CTFd 3.7.7 (MariaDB, Users mode) + plugin fork `eb4871e` |
| chal-1 | `challenge-ctf`, 4 vCPU / 8 GB, image `ctf/test-web` (nginx hello) |
| chal-2 | `challenge-ctf-2`, 2 vCPU / 4 GB, image `ctf/test-whoami` (traefik/whoami) |
| Per container | 256 MB RAM, 0.5 CPU, 256 processes |
| Connection | TLS + client certs, host firewall on both chal servers |
| Tool | `tools/load-test.py` (plugin repo), run on the platform |

Method: 25 hidden players (`loadtest-01..25`) logged in, then all pressed **Start** at the same moment. Players split over the 2 docker challenges, one per server. The tool then checked every instance answers on its port.

## Results

| | |
|---|---|
| Started OK | **25 / 25** |
| Reachable | **25 / 25** |
| Start time per player | median **4.5 s**, 95% 5.4 s, slowest 5.5 s |
| Whole burst | 5.5 s |
| Split | chal-1: 13 · chal-2: 12 |

### Resources during the test

| | Containers | RAM per container | Server RAM used | Available |
|---|---|---|---|---|
| chal-1 (8 GB) | 14 (13 test + 1 leftover, see below) | ~4.6 MB | 751 MB / 7.7 GB | 7.0 GB |
| chal-2 (4 GB) | 12 | ~1.7 MB | 645 MB / 3.8 GB | 3.2 GB |

CPU idle on all containers. No swap on either server.

## Findings

1. **Works at internal-CTF scale.** 25 simultaneous starts is the worst case for the internal CTF (25 solo players), and about the same for ATC (~25 teams, 1 container per team).
2. **~4.5 s per start** in real conditions (0.9 s in the local test with fake Docker). The difference is real container creation + TLS round-trips. Acceptable for a button players press a few times.
3. **Abandoned containers are never cleaned up** ⚠️. chal-1 had a 14th container: a manual test instance from 26 Oct 15:53, still running ~20 h later. The 2-hour cleanup only runs when the *same* player starts another container. At an event, every player who leaves an instance running keeps it forever. **Fix before the event** (global cleanup on every start + a cron sweep).
4. **Test images are not representative.** nginx/whoami use 2-5 MB; real web challenges (Flask, PHP, Node) are typically 30-100 MB. Re-run with the real images once built.

## Capacity estimate (worst case: every container at its 256 MB cap)

| Server | Containers | RAM needed (+~0.7 GB OS/Docker) | Fits? |
|---|---|---|---|
| 4 GB | 13 | ~4.0 GB | borderline |
| 8 GB (Contabo) | 13 | ~4.0 GB | yes |
| 8 GB (Contabo) | 25 on one server | ~7.1 GB | just fits |

→ 4 vCPU / 8 GB per challenge server is enough for both events, even in the worst case.

## Next

- [ ] Fix finding 3 (stale container cleanup), re-test
- [ ] Re-run with real challenge images
- [ ] Re-run on Contabo before the event (MariaDB + real network)
- [ ] Delete `loadtest-*` players before the event
