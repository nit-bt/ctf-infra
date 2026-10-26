# 04 · Challenge server

Do this once per challenge server. For ATC: 3 times (web / pwn / reverse).

## 1. Docker API with TLS

```bash
hostname -I              # first IP = this box's private IP (ignore 172.17.0.1)
sudo /opt/ctf/CTFd-Docker-Challenges/setup-docker-tls.sh <private-ip>
```
Must end with:
```
OK
Without client cert (must FAIL):
rejected, good
```
Client certs land in `~/docker-client-certs/` (`ca.pem`, `cert.pem`, `key.pem`).

On Contabo without a private network, pass the **public IP** too:
`setup-docker-tls.sh <private-ip> <public-ip>`, the cert must name every address CTFd uses.

## 2. Get the 3 client files to your laptop

Browser SSH download button, or copy-paste:
```bash
cat ~/docker-client-certs/ca.pem      # copy from -----BEGIN to -----END----- (incl.)
```
Paste into a text editor → save as `ca.pem` (type **All files**, not `.txt`). Same for `cert.pem`, `key.pem`.

Save them in a **non-synced** folder (not OneDrive/Google Drive Desktop). Delete after uploading to CTFd.
`key.pem` = full control of this server's Docker.

## 3. Add it in CTFd

Admin → Plugins → **Docker Config** → **+ Add host**

| Field | Value |
|---|---|
| Name | `chal-1` (ATC: `web-srv`, `pwn-srv`, `rev-srv`) |
| Docker API address | `<private-ip>:2376` |
| Public address | public IP or `chalN.<domain>`, what players connect to |
| Port min / max | `30000` / `31000`, must match the firewall rule |
| Memory / CPU / processes | 256 MB / 0.5 / 256 (raise per server if a challenge needs it) |
| TLS | **Yes** + upload `ca.pem`, `cert.pem`, `key.pem` |

Save → host shows **UP**. Then tick its **Allowed repositories** → Save.

## 4. Firewall

```bash
sudo /opt/ctf/CTFd-Docker-Challenges/firewall/harden-chal-host.sh <platform-ip>
```
`<platform-ip>` = the IP CTFd uses to reach this box (GCP: platform's **internal** IP · Contabo: platform's public IP, unless you set up a private network).

Ends with a self-test from inside a real container, must be `6 passed, 0 failed`:

| From a container to… | Result |
|---|---|
| internet | blocked |
| cloud metadata 169.254.169.254 | blocked |
| other containers | blocked |
| this host (Docker API, SSH) | blocked |
| players → published ports | open |

Rules re-apply on boot and on Docker restart.
`sudo ctf-docker-firewall status` · off: `sudo systemctl stop ctf-docker-firewall`

**Consequence:** containers have no network out at all (no DNS, no `pip install` at runtime). Everything goes into the image at build time.

## 5. GCP only

Give the VM **No service account** ([01](01-gcp-sandbox.md#challenge-vm-no-service-account)). Stopping it changes the external IP → update *Public address* in Docker Config.
