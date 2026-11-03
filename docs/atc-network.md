# ATC event network (internet on, AI chatbots blocked)

ATC runs on the **school Wi-Fi**, so school IT sets the rules. Players get a separate Wi-Fi with normal internet
(Google, Google search AI answers and docs are fine), but **AI chatbots are blocked**: ChatGPT, Claude, DeepSeek, Gemini and the others.

This is a **blocklist**: it stops the known AI sites and the usual ways around them (VPN, other DNS), not 100 %.
The rest is rules + proctors. (A stricter option, "only our servers, no internet", is in git history: commit `5be14f6`.)

## 1. What to ask school IT

Send this **at least 3 weeks before** the event:

| # | Ask | Why |
|---|---|---|
| 1 | A separate SSID, e.g. `ATC-CTF`, own password and VLAN, on only for the event day, in the event room only | rules apply only to players |
| 2 | **Client isolation** on that SSID | players can't attack each other's laptops |
| 3 | Web filter on that VLAN: block category **Artificial Intelligence / Generative AI** (FortiGuard, Sophos, Palo Alto, Cisco all have it) **+ the list in section 2** | the AI block |
| 4 | Block category **Proxy Avoidance / VPN / Anonymizers** | stops VPNs |
| 5 | Force DNS: allow DNS (53) **only to the school DNS**; block 53/853 elsewhere and the DNS-over-HTTPS servers (category or list below) | players can't skip the filter with 8.8.8.8 or Secure DNS |
| 6 | Block **UDP 443 (QUIC)** and other outbound UDP except DNS to the school DNS | QUIC and WireGuard VPNs slip past filters |
| 7 | HTTPS filtering by **domain name (SNI)**, no need to decrypt traffic | works without installing certificates on laptops |
| 8 | Wired ports in the room: off, or on the same VLAN | no way around the Wi-Fi |
| 9 | A test slot one week before, and an IT contact on the day | section 4 |

## 2. Block list (domains, include all subdomains)

**Chatbots**
`chatgpt.com` `openai.com` `oaiusercontent.com` `claude.ai` `claude.com` `anthropic.com` `deepseek.com`
`gemini.google.com` `aistudio.google.com` `bard.google.com` `notebooklm.google.com`
`copilot.microsoft.com` `copilot.cloud.microsoft` `perplexity.ai` `poe.com` `grok.com` `x.ai` `meta.ai`
`chat.mistral.ai` `kimi.com` `kimi.ai` `moonshot.cn` `chat.qwen.ai` `tongyi.aliyun.com` `doubao.com` `chatglm.cn` `z.ai`
`huggingface.co` `hf.space` `character.ai` `you.com` `phind.com` `blackbox.ai` `duck.ai` `lmarena.ai` `openrouter.ai`
`groq.com` `together.ai` `chatbotapp.ai` `monica.im` `merlin.foyer.work` `getmerlin.in`

**AI used from apps / code editors** (VS Code extensions, scripts)
`api.openai.com` `api.anthropic.com` `api.deepseek.com` `generativelanguage.googleapis.com`
`githubcopilot.com` `copilot-proxy.githubusercontent.com` `api.githubcopilot.com` `cursor.sh` `cursor.com` `codeium.com` `windsurf.com`

**Ways around the filter**
`dns.google` `cloudflare-dns.com` `one.one.one.one` `dns.quad9.net` `doh.opendns.com` `nextdns.io` `dns.adguard-dns.com`
`mask.icloud.com` `mask-h2.icloud.com` (iCloud Private Relay) · `cloudflareclient.com` (WARP)
`use-application-dns.net` → make it **not exist** (turns off Firefox's automatic DoH)

Category 3 catches new and unknown AI sites; this list makes sure the big ones are blocked even if a category misses them.

## 3. Our side

- [ ] Rules sheet: no AI chatbots, no VPN/hotspot, no local AI models (Ollama, LM Studio), AI extensions off. Caught = disqualified.
- [ ] Phones collected or face-down; proctors walk around.
- [ ] Optional: block Discord/Telegram/Messenger on `ATC-CTF` too (stops sharing flags between teams, and Telegram AI bots).

## 4. Test (one week before, on `ATC-CTF`, with a normal laptop)

| Test | Must |
|---|---|
| `https://atc.ctfc.live`, start an instance, open its link | ✅ work |
| `google.com` search, docs sites, GitHub | ✅ work |
| `chatgpt.com`, `claude.ai`, `chat.deepseek.com`, `gemini.google.com`, `perplexity.ai`, `copilot.microsoft.com` | ❌ blocked |
| A small AI site not on the list (pick one) | ❌ blocked (= the category works) |
| `nslookup chatgpt.com 8.8.8.8` | ❌ timeout |
| Chrome Secure DNS on, then `chatgpt.com` | ❌ blocked |
| A VPN app (e.g. Proton VPN free), Cloudflare WARP | ❌ can't connect |
| Ping another laptop on `ATC-CTF` | ❌ fail |

Anything that gets through → send IT the exact test.
