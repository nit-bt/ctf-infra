# Troubleshooting

Everything we actually hit, with the fix.

## GCP

| Symptom | Cause | Fix |
|---|---|---|
| VM has no External IP; dropdown only shows *None*; "External IPs for VM instances organisation policy does not allow…" | Org policy `compute.vmExternalIpAccess` | Org policies → Allow all ([01](01-gcp-sandbox.md#org-policies-one-time)) |
| "IAM policy update failed … Domain-restricted sharing" | Org policy `iam.allowedPolicyMemberDomains` | Org policies → Allow all |
| `sudo: I'm sorry <user>. I'm afraid I can't do that` | OS Login without admin role | Grant **Compute OS Admin Login**; if still failing, startup-script sudoers ([01](01-gcp-sandbox.md#sudo-under-os-login)) |
| "To add a startup script, use the 'Startup script' section" | Put it in Metadata as `startup-script` | Use **Automation → Startup script** box instead |
| Can't change service account | VM running | Stop the VM first |
| "Some features are restricted … data sovereignty" banner | Org policies | Info only; check *Details* if an option you need is greyed |
| Challenge links stopped working after a restart | Ephemeral external IP changed | Update *Public address* in Docker Config |
| `git: command not found` on a new VM | *Minimal* Ubuntu image | `sudo apt install -y git` (or recreate with the normal image) |

## Platform

| Symptom | Cause | Fix |
|---|---|---|
| Browser **502**, `ctfd` container **Restarting** | Check `sudo docker compose logs ctfd --tail 40` | see below |
| Log: `Can't locate revision identified by '…'` | DB created by a newer CTFd (e.g. 3.8.6) than the one running (3.7.7) | `down` → `sudo rm -rf .data` → `up -d` (wipes the DB). `down -v` does **not** remove `.data` |
| Everyone logged out after restart | No fixed `SECRET_KEY` | `.env` with `SECRET_KEY` ([07](07-production-contabo.md)) |
| Old challenge page behaviour after plugin update | Browser cached JS | `Ctrl+Shift+R` |

## Plugin / instances

| Message | Meaning |
|---|---|
| Docker Config host **DOWN** | CTFd can't reach `<ip>:2376`: wrong IP, VPC/firewall rule, `<platform-ip>` in `harden-chal-host.sh` wrong, or Docker not running |
| "Challenge not available" | Challenge is Hidden (players). Admins can start hidden ones |
| "This challenge has no Docker host set" | Edit challenge → pick Docker Host |
| "Image for this challenge is not available" | Image not on that server, or repo not ticked in Allowed repositories |
| "Another container is already running…" | 1 at a time; stop the other one |
| "Please wait N seconds…" | 30 s cooldown after Stop |
| "Your previous request is still running…" | Player clicked twice, or a teammate clicked at the same time; wait a second and retry |
| "Start failed … port is already allocated" / "external connectivity" | 3 port clashes in a row; very unlikely with the reservation. Check nothing else on the chal server uses 30000-31000 |
| "…reverted 5 minutes after creation" | Revert has a 5 min wait (Stop doesn't) |
| "No free ports left" | Port range full: widen it (and the firewall rule) or add a server |
| "Could not start container: Cannot reach Docker host…" | Server down / unreachable (CTFd gives up after 10 s) |
| Instance shows as running right after you open the page | It's an older container still alive; CTFd restarts don't kill containers. Anything older than 2 h is removed automatically |
| "uploaded, new file overwrites" next to the cert fields | That host already has certs; leave empty to keep them. Check the form says *Edit <the right host>* |

## Challenge server

| Symptom | Fix |
|---|---|
| `setup-docker-tls.sh` doesn't print `OK` | `sudo journalctl -u docker -n 50`, usually a typo'd IP or `daemon.json` |
| `Failed to restart docker.service: Unit docker.service not found` | Docker not installed yet → `install-docker.sh` first, then rerun (newer script versions check this) |
| `!! x.x.x.x is not an IP of this machine` | You passed another server's IP; use this server's own from `hostname -I` |
| New host **DOWN** right after adding | Wrong server's cert files, or cert made with the wrong IP → rerun `setup-docker-tls.sh <right IP>` and re-upload |
| Firewall self-test FAIL | `sudo ctf-docker-firewall status`; rerun `harden-chal-host.sh` |
| Challenge needs internet / DNS at runtime | Not allowed by design, bake it into the image |
| setuid binary doesn't escalate in a challenge | `no-new-privileges` is on by design |

## Useful commands

```bash
sudo docker compose ps / logs ctfd --tail 50      # platform
sudo docker ps / stats                            # challenge server
sudo ctf-docker-firewall status
curl --cacert ca.pem --cert cert.pem --key key.pem https://<ip>:2376/_ping   # test API with certs
```
