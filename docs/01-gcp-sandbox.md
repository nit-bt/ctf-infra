# 01 · GCP sandbox

Sandbox only, paid with GCP credits. Production goes on Contabo ([07](07-production-contabo.md)).

## Org policies (one-time)

Our GCP account sits under an **organisation** with "secure by default" policies. Two block us:

| Policy | ID | Symptom | Fix |
|---|---|---|---|
| Define allowed external IPs for VM instances | `compute.vmExternalIpAccess` | VM has no External IP, dropdown only offers *None* | Allow all |
| Domain restricted sharing | `iam.allowedPolicyMemberDomains` | "IAM policy update failed … Domain-restricted sharing" when granting a role | Allow all |

How:
1. Top bar project picker → pick the **organisation** (🏢), not the project
2. Search bar → **Organisation policies**
3. Filter → paste the ID → open it
4. **Manage policy** → Override parent's policy → Replace → Add rule → **Allow all** → **Set policy**
5. Wait 1-2 min

> Only one member in the org, so opening these is low risk. If teammates join the org later, tighten them again.

## VMs

| | platform | challenge |
|---|---|---|
| Name | `platform-ctf` | `challenge-ctf` |
| Region / zone | `asia-southeast1` / **same zone for both** | same |
| Machine | E2 custom, 4 vCPU / 8 GB | E2 custom, 4 vCPU / 8 GB |
| OS | Ubuntu 26.04 LTS x86/64 (normal image, not *Minimal*) | same |
| Disk | 30 GB balanced | 40 GB balanced |
| Network tag | `platform-ctf` | `challenge-ctf` |
| Allow HTTP/HTTPS | ✅ | ❌ |
| External IP | Ephemeral, **Standard** tier | Ephemeral, **Standard** tier |
| Snapshots / Ops Agent | off | off |
| Service account | default | **No service account** (see below) |

Why the same zone: platform ↔ challenge traffic is free and fastest.
Why Standard tier: cheaper, 200 GB/month free egress, players and servers are all in SEA anyway.
Specs match Contabo's 4 vCPU / 8 GB so tests mean something.
The *Minimal* Ubuntu image has no `git`; if you end up on it: `sudo apt install -y git`.
Extra test challenge servers (e.g. `challenge-ctf-2`) can be `e2-medium`; set **No service account** and the sudo startup script while creating, and give them the same `challenge-ctf` tag so the firewall rules apply.

Ephemeral external IPs **change on every stop/start** → update the challenge server's *Public address* in CTFd after a restart. Internal IPs don't change.

## VPC firewall rules

VPC network → Firewall → Create firewall rule (Logs **off**, Ingress, Allow):

| Name | Targets (tags) | Source | Ports | Why |
|---|---|---|---|---|
| (built-in via checkbox) | `platform-ctf` | 0.0.0.0/0 | tcp 80, 443 | website |
| `ctf-docker-api` | `challenge-ctf` | **Source tags** `platform-ctf` | tcp 2376 | only CTFd may control Docker |
| `ctf-chal-ports` | `challenge-ctf` | 0.0.0.0/0 | tcp 30000-31000 | players → their instance |

Firewall rules match **tags**, so they can be created before the VM exists.

## sudo stops working after a few minutes

Symptom: `sudo` works, then a few minutes later: `sudo: I'm sorry <user>. I'm afraid I can't do that`.

Cause (from `/var/log/auth.log` and `journalctl -u google-guest-agent`): the browser **SSH** button adds a **temporary SSH key that expires after ~3 minutes**. While a valid key exists, Google's guest agent puts you in the `google-sudoers` group (that's where sudo comes from). When the key expires it removes you from the group, so sudo stops even though the SSH window stays open:
```
google_guest_agent: Adding existing user <user> to google-sudoers group
google_guest_agent: invalid ssh key entry - expired key ...
google_guest_agent: Removing user <user>
gpasswd: user <user> removed by root from group google-sudoers
```

Options:
- **Quick (what we do in the sandbox):** close the SSH tab and open a new one when sudo stops; run sudo commands right after connecting.
- **Permanent:** add your own SSH key (comment = your username) under Compute Engine → **Metadata → SSH keys**, then `ssh <user>@<ip>` from your laptop. The key never expires, so you stay in `google-sudoers`.

(We first thought this was OS Login and tried an IAM role and a sudoers startup script. Neither was the cause. The startup script can be removed.)

## Challenge VM: no service account

Anything on a GCP VM can ask `169.254.169.254` for a token of the VM's service account (default one ≈ Editor on the project). A player escaping a container could take over the project.

VM → **Stop** → Edit → Security and access → Service account → **No service account** → Save → Start.
(Shielded VM checkboxes: leave as they are.)

The challenge firewall also blocks the metadata server; this is the second layer.

## Save credits

```bash
gcloud compute instances stop platform-ctf challenge-ctf --zone=<zone>
```
Stopped VMs still pay for disks, and **unattached static IPs are billed by the hour** (we had an old `trot-prod-ip` sitting around). Delete what you don't use.
