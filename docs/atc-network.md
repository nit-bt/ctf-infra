# ATC event network (no AI, no internet)

ATC runs on the **school Wi-Fi**, so school IT sets the rules. The idea: players get a separate Wi-Fi that can reach
**only our CTF servers**. Everything else (ChatGPT, Claude, Google, VPNs, Discord) fails because it isn't allowed.

## 1. What to ask school IT

Send this **at least 3 weeks before** the event (fill in the IPs once the ATC servers exist):

| # | Ask | Why |
|---|---|---|
| 1 | A separate SSID, e.g. `ATC-CTF`, with its own password and its own VLAN, on only for the event day, in the event room only | players never touch the normal school network |
| 2 | **Client isolation** on that SSID | players can't attack each other's laptops |
| 3 | Firewall policy for that VLAN: **default deny everything** | the allowlist |
| 4 | Allow **TCP 80, 443** to `<platform-ip>` | the CTF site |
| 5 | Allow **TCP 30000-31000** to `<chal1-ip>`, `<chal2-ip>`, `<chal3-ip>` | challenge instances |
| 6 | Allow **DNS (53) only to the firewall's own DNS**, block 53/853 anywhere else | no other DNS, no DNS-over-TLS |
| 7 | That DNS answers **only** `atc.ctfc.live`, `chal1/2/3.ctfc.live` (static entries), **no forwarding** to the internet | other names "don't exist", no DNS tunnels |
| 8 | Block all other UDP (QUIC, WireGuard, etc.) | closes UDP VPNs |
| 9 | Wired ports in the room: off, or on the same VLAN | no way around the Wi-Fi |
| 10 | A test slot one week before, and an IT contact on the day | see section 3 |

Organizers need normal internet (Discord, monitoring): a **different SSID or staff wired port**, not `ATC-CTF`.

## 2. Our side

- [ ] `atc.ctfc.live` in Cloudflare: **DNS only (grey cloud)** for the event. Orange = Cloudflare's shared IPs = WARP and thousands of other sites would be reachable.
- [ ] Platform HTTPS: **Let's Encrypt** certificate instead of the Cloudflare origin certificate (browsers don't trust the origin one directly). Do it the day before, check in a browser.
- [ ] **Self-host the theme fonts** (`branding/theme-header.html` loads Google Fonts → blocked → site falls back to plain fonts).
- [ ] No challenge needs the internet (no OSINT, no external APIs, no `pip install` inside instances).
- [ ] Tools players need are on our servers: CyberChef self-hosted, challenge files in CTFd, offline cheat sheet.
- [ ] Support on the day = raise a hand (players can't reach Discord).
- [ ] Rules sheet: no phones/hotspots, no local AI models (Ollama, LM Studio, etc.), caught = disqualified. Proctors walk around.

After the event: `atc.ctfc.live` back to orange cloud, origin certificate back.

## 3. Test (one week before, on `ATC-CTF`, with a normal laptop)

| Test | Must |
|---|---|
| `https://atc.ctfc.live` (login, open a challenge, download a file) | ✅ work |
| Start an instance, open its link | ✅ work |
| `chatgpt.com`, `claude.ai`, `gemini.google.com`, `google.com` | ❌ fail |
| `nslookup chatgpt.com` | ❌ no answer |
| `nslookup chatgpt.com 8.8.8.8` | ❌ timeout |
| A VPN app (e.g. Proton VPN free) | ❌ can't connect |
| Cloudflare WARP (1.1.1.1 app) | ❌ can't connect |
| Ping / open another laptop on `ATC-CTF` | ❌ fail (client isolation) |
| Chrome "Secure DNS" on, then `chatgpt.com` | ❌ fail |

Any ❌ that works → send IT the exact test that got through.
