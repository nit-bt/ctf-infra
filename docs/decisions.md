# Decisions

Short record of what we chose and why, so we don't re-argue it.

| Decision | Chosen | Over | Why |
|---|---|---|---|
| Platform | CTFd **3.7.7** | latest 3.8.x | the docker plugin is built/tested on 3.7.7 |
| Instances | docker plugin, **our multi-host fork** | CTFd-whale + Swarm | fewer moving parts (no frp, no overlay network); per-category servers are easy to reason about on event day; whale had a Cloudflare issue before |
| Multiple servers | one server **per category**, chosen per challenge | one big server | one big server = single point of failure |
| Orchestration | plain Docker | Kubernetes | plugin speaks Docker API only, no time to port; k8s overhead eats small servers; scale doesn't need it. Revisit in the home lab (k3s + kCTF/klodd) |
| Sandbox | GCP (free credits) | testing on Contabo directly | free, disposable, same specs |
| Production | Contabo, Japan | GCP | cost |
| Specs | 4 vCPU / 8 GB each | | 25 players × 1-2 light containers ≈ 4-8 GB worst case with 1-at-a-time + timeouts |
| Docker API | TLS + client certs, port 2376 | plain HTTP 2375 | Docker API = root on that server |
| Container network | **no outbound at all** | allow internet | stops players using our servers as a proxy, reading cloud metadata, or attacking each other |
| Players | Users mode (internal), Teams mode (ATC) | | event format |
| Stop | any time + 30 s cooldown | upstream "after 5 min" | players asked; cooldown prevents spam |
| Platform per event | fresh install for ATC | restore Nov's disk | different players/mode/challenges; proves the docs work |
| Domain | `.me` / `.tech` | `.dev` / `.app` | those force HTTPS, breaking `http://host:port` |

## Plugin fork changes vs upstream

See the fork's README. In short: multi-host, public address per host, port range per host, container limits, Teams-mode crash fix, timeouts, stop any time, POST + CSRF for start/stop/nuke, `no-new-privileges`, admins can test hidden challenges.
