# Fleet topology plan: one workstation, disposable boxes

Status: **Phase 1 done (2026-09-23). Phases 2–5 not started.**
Owner: Ahmed. Written for any agent (Claude, Codex, OpenCode) picking this up.

Read this whole file before starting a phase. Then re-check the live state
(`chezmoi git log`, `chezmoi status`, `multipass list`) — the fleet may have
moved on since the status line above was written. Update the status line and
the phase's "State" when you finish or stop.

---

## 1. Goal

Ahmed uses **one physical machine day to day** (as-host). Everything he develops
on or deploys to is an Ubuntu **box** that can be recreated from this repo:

```
New Mac      -> chezmoi init shdots          -> ready to work (control plane)
New dev box  -> provision/new-box <name>     -> ready to develop on, reached from the Mac
New prod box -> provision/new-box --prod ... -> ready to receive deploys
```

## 2. Vocabulary and target topology

| Term | Machines | Chezmoi data | Notes |
|---|---|---|---|
| **workstation** | `as-host` (primary), `fdx-host` (fallback twin) | `kind=mac`, `role=""` | Identity-neutral: carries personal **and** work tools. |
| **dev box** | `as-dev` (personal), `fdx-dev` (work) | `kind=vm`, `role=personal\|work` | Disposable. Multipass on as-host today; maybe a VPS later. |
| **prod box** | `as-prod-01`, `as-prod-02`, … | none — **not chezmoi-managed** | Personal projects only. Rebuildable, not disposable. |

```
                        shdots (GitHub)
          ┌────────────────┼──────────────────────┐
     chezmoi init    cloud-init + chezmoi     cloud-init only
          │                ▼                      ▼
   WORKSTATION        DEV BOX                PROD BOX (as-prod-##)
   as-host / fdx-host as-dev, fdx-dev        many apps per box
   both identities    one identity each      Docker Compose + Caddy
          │                ▲                      ▲
          ├── plain SSH to <name>.local ──┘       │
          └── Tailscale SSH + docker context ─────┘
                                   public: 80/443 only; SSH over tailnet only
```

Company infrastructure is out of scope. `fdx-host` keeps everything, including its
chezmoi auto-update timer.

## 3. Decision log (do not reopen without asking Ahmed)

| # | Decision | Why |
|---|---|---|
| D1 | Identity lives in the box, not the Mac. Macs get both personal and work tools; only a VM is asked for `role`. | One workstation must do both jobs; browser profiles and per-host config separate them. |
| D2 | Gate tools with `includeTemplate "has-personal" .` / `"has-work" .`; gate work-VM-only things with `and (eq .kind "vm") (eq .role "work")`; never test a Mac's `role`. | A Mac's role is empty, so role tests silently fall into `else` branches. |
| D3 | Names: *workstation* / *dev box* / *prod box*. Chezmoi keeps `kind = mac\|vm` (no rename). | Renaming values touches ~15 templates for no behaviour change. |
| D4 | Prod boxes are **not** managed by chezmoi. All provisioning is cloud-init. | Every push auto-deploys within 6h; the age key and 1Password service-account token are shared. A prod box must hold neither. |
| D5 | Prod deploys: `docker compose` over an SSH `docker context`; **caddy-docker-proxy** routes by container labels. | Remote docker contexts can't copy files, so a Caddyfile-per-app needs an extra SSH step; labels keep a deploy to one command. Docker-socket mount accepted. |
| D6 | Prod firewall: **ufw only** (no provider firewall). Docker bypasses ufw, so only the edge Caddy stack may publish ports (80/443); everything else publishes nothing or binds `127.0.0.1:`. Enforced by a **pre-deploy check**, not `ufw-docker`. | Keeps the box simple; the check is cheap. |
| D7 | Tailscale on prod (and any future VPS box) only. Local Multipass dev boxes use plain SSH to `<name>.local`. | Removes the auth key and node churn from disposable boxes. Ahmed never needs a dev box away from the laptop. |
| D8 | Dev-box secrets (age key, 1Password service-account token) are **copied over SSH after launch**, never put in cloud-init user-data. | User-data persists under `/var/lib/cloud`. |
| D9 | Prod joins the tailnet by hand: public port 22 stays open until Ahmed runs `tailscale up`, then a step closes it. On rebuild, Ahmed removes the old node in the admin console first. | No Tailscale auth/API key stored anywhere. |
| D10 | Dev boxes: one SSH key per box (`id_ed25519`), generated on each rebuild and registered with `gh` on github.com (and github.foodics.com for work boxes) as auth + signing. Delete the old box's **auth** key by title; keep old **signing** keys. | Background agents must push after Ahmed disconnects, so no agent forwarding. Keeping signing keys keeps old commits Verified. |
| D11 | Box→Mac SSH is not allowed (Macs don't trust box keys). | Box keys rotate on every rebuild. Add back only when truly needed. |
| D12 | Prod provider: Hetzner; netcup possible. Launchers are thin and per-provider; the cloud-init is shared. | |
| D13 | Keep Eternal Terminal. | Useful for VPS boxes. |
| D14 | Work servers are reached from either Mac through the 1Password SSH agent, serving only fdx-host's key (1Password item `gvljlmfqa2z23h3ip2rchz36uu`). Never add more keys to work servers. | Extra keys there would raise questions. |
| D15 | Shell tokens come from the managed `~/.config/zsh/secrets.zsh`, by 1Password UUID, never by title. It never exports `GITHUB_TOKEN`/`GH_ENTERPRISE_TOKEN`. | `gh` gives those vars precedence over its stored login. |
| D16 | Multipass only for dev boxes today, but keep the dev cloud-init provider-neutral. | A dev VPS is possible later. |

## 4. Reference facts

**1Password items (vault `dev-secrets`)**

| UUID | Title | What |
|---|---|---|
| `jypxoxjttljurjhg3f72bvlx6e` | GitHub PAT (github.com, read-only) | fine-grained, public read-only; `GITHUB_READONLY_TOKEN` / `MISE_GITHUB_TOKEN` |
| `xwug424pq6bcit35v5abzpt5vm` | GitHub PAT (github.com, MCP write) | classic; Claude/Codex `github` MCP; `GH_TOKEN` on personal VMs |
| `i4fkk5sxnoihinvcnv2evqg7be` | GitHub Enterprise GHE MCP PAT | github.foodics.com, scopes `repo, workflow`; `GHE_MCP_TOKEN` |
| `cuhmbyox773pricvf6xmm5nfba` | Foodics: Jira API Token | `JIRA_API_TOKEN` |
| `vxwnzlffnicehkjjd5jjmg63xe` | Foodics: SonarQube Token | `SONAR_TOKEN` |
| `gvljlmfqa2z23h3ip2rchz36uu` | Foodics MacBook (SSH key) | fdx-host's key = the work-server key (D14) |

**SSH keys after Phase 1:** each machine has one `~/.ssh/id_ed25519`. fdx-dev
still also has `id_ed25519_foodics` (its work identity) until its Phase 3 rebuild.
The retired `id_rsa` and `id_ed25519_hetzner` live in
`~/.ssh/retired-ssh-keys-2026-09/`. Public keys of the workstations are in
`.chezmoidata/fleet.yaml`; signers in `dot_config/git/allowed_signers`.

**Auto-update trusts only signed commits.** `chezmoi-autoupdate` runs
`git verify-commit` against each machine's *current* `allowed_signers`. A commit
that adds a new signing key must be signed by a key the fleet already trusts.

**Dev VM spec:** see "Dev VM spec" in `AGENTS.md` (6 CPU / 12G / 220G / 24.04).
as-host has 32 GiB RAM and 10 CPUs, so two 12G boxes is the practical ceiling.

---

## 5. Gotchas already paid for

1. **VM clocks drift and break 1Password.** On 2026-09-23 both VMs were ~3h37m
   slow; the service account then returned `Authorization: (401)` on every
   `op read`, which looks exactly like a revoked token. Cause: cloud-init writes
   `makestep 1.0 -1` to `/etc/chrony/conf.d/99-vm.conf`, but
   `/etc/chrony/chrony.conf` has `makestep 1 3` *after* its `confdir` line, so it
   wins. Live fix: `sudo chronyc makestep`. Real fix: Phase 2, step 2.
2. **macOS blocks SSH sessions from 1Password.** Over SSH into a Mac,
   `~/Library/Group Containers/2BUA8C4S2C.com.1password/…` gives
   `Interrupted system call`, the agent's approval prompt shows on an unattended
   screen, and `op` via the desktop app hangs. Test anything 1Password-related on
   a Mac from its own terminal. The work-host `Match` block skips the agent when
   `$SSH_CONNECTION` is set for this reason.
3. **macOS blocks app changes from SSH sessions.** `brew bundle` over SSH hangs
   on cask installs/upgrades (it hung 2h on fdx-host). Run it at the keyboard.
4. **1Password rewrites `~/.ssh/config`.** Turning on its SSH agent appends
   `Host * IdentityAgent …`. Chezmoi must win (`chezmoi apply --force ~/.ssh/config`),
   or every SSH connection goes through an agent that only holds the work key.
5. **Scripts must call `/usr/bin/ssh`.** Interactive `ssh` is aliased to kitty's
   `kitten ssh`, which needs a TTY.
6. **Rebuilt boxes reuse their `.local` name with a new host key.** Run
   `ssh-keygen -R <name>.local` before the first connection.
7. **Renaming the key a machine pulls with breaks the pull that would fix it.**
   Register the new key on GitHub *before* switching templates, and keep the old
   file on disk until the switch is applied.
8. **Config-template changes make every machine `degraded`** until
   `chezmoi init` runs by hand. Prefer data derived inside templates
   (like `has-work`) over new config keys. New prompts must have
   non-interactive answers (`--promptBool`, `--promptChoice`, `--promptString`).
9. **`chezmoi apply` from a non-interactive shell** can pick a different `op`
   than interactive zsh. A stale `/usr/local/bin/op` 2.16 once shadowed
   Homebrew's 2.39 and hung. Check `which -a op`.
10. **avahi on Multipass works** (verified 2026-09-22, Multipass 1.16.3):
    `packages: [avahi-daemon]` is enough; `<name>.local` resolves in
    milliseconds, follows address changes, and Ubuntu's default ufw rules
    already allow mDNS. Docker bridge addresses are not advertised to the Mac.
    Fallback: an ssh `ProxyCommand` that looks the IP up with
    `multipass info <name> --format json | jq -r --arg n <name> '.info[$n].ipv4[0]'`.
11. **Test ssh_config changes on every OpenSSH version in the fleet.** Commit
    `cfecd94` put `\"` inside a `Match … exec "…"`; macOS's OpenSSH accepted it,
    Ubuntu 24.04's OpenSSH 9.6 rejected the whole file, breaking all SSH from
    the VMs until `c244b86` fixed it. Before pushing an SSH config change, run
    `ssh -G <host>` against the rendered file on a Mac **and** on a VM.

---

## 6. Phases

Stop and ask Ahmed before: **every push** (it deploys fleet-wide), **destroying a
dev box** (have him push uncommitted work first), **creating paid resources**,
**adding or removing keys on GitHub or servers**.

### Phase 1 — Identity-neutral workstations, one key per machine ✅

Done 2026-09-23 in commits `66be6cd`, `cd07431`, `cfecd94`. Delivered:
`has-personal`/`has-work` partials; role prompted on VMs only; Brewfile work
block removed (1Password and Chrome now shared); git `includeIf` for
`~/Code/foodics/`; both GitHub MCPs on Macs; 1Password SSH agent for work hosts;
`secrets.zsh`; `opencode.jsonc` create-only; as-host moved to `id_ed25519`;
Hetzner key retired. All four machines converged, `chezmoi status` clean.

Leftovers for Ahmed (at fdx-host's keyboard): `brew bundle`,
`mcp-github-register`; rotate the Sonar token; on as-host
`sudo brew services restart tailscale`.

### Phase 2 — `provision/new-box` for dev boxes

**Goal:** `provision/new-box <name> --role personal|work` produces a working dev
box with no manual steps except AI-CLI sign-in.

**State:** not started.

**Files**
- `provision/dev-vm-cloud-init.yaml` — edit.
- `provision/launch-dev-vm.sh` — becomes the Multipass launcher called by `new-box` (or is folded into it).
- `provision/new-box` — new. POSIX sh or bash, `set -eu`.
- `provision/README.md`, `AGENTS.md` ("Dev VM spec"), `README.md` — update.
- `private_dot_ssh/config.tmpl`, `.chezmoitemplates/git-signing-key`, `.chezmoidata/herdr.yaml` — see step 6.

**Steps**
1. Cloud-init: add `avahi-daemon` to `packages`; remove the whole Tailscale
   install block and the `tailscale0` / `41641/udp` ufw rules; **enable ufw at
   launch** (it no longer waits for `tailscale0`). Keep the Multipass port-22
   rule on the NAT NIC, or `multipass stop` becomes a hard power-off.
2. Chrony fix (gotcha 1): replace the `makestep` line in
   `/etc/chrony/chrony.conf` itself (for example
   `sed -i 's/^makestep .*/makestep 1.0 -1/' /etc/chrony/chrony.conf` in
   `runcmd`, then restart chrony) instead of relying on the `conf.d` drop-in.
3. Firewall for Mac→box access. Today `docker-user-fw.service` drops **new**
   connections to containers arriving on the `enp*` NIC, and ufw only allows 22
   there; web ports and `et` (2022) used to arrive via `tailscale0`. On
   **Multipass**: allow new connections from the Mac's bridge address only
   (currently `192.168.252.1`; derive it at runtime, for example the default
   gateway) for container ports and 2022. On a **VPS**: keep the drop rule.
   Make this a launcher-supplied placeholder so the cloud-init stays
   provider-neutral (D16).
4. `new-box` flow, all over `/usr/bin/ssh ubuntu@<name>.local`:
   ```
   validate name (DNS label, not as-host/fdx-host, no "-prod-", not "primary")
   multipass launch (via launch-dev-vm.sh) with both workstation pubkeys
     from .chezmoidata/fleet.yaml in ssh_authorized_keys
   wait for cloud-init: ssh <box> cloud-init status --wait
   ssh-keygen -R <name>.local
   copy ~/.config/chezmoi/key.txt           (D8)
   generate ~/.ssh/id_ed25519 on the box, comment "<name>"
   gh ssh-key add (auth + signing) on github.com; on github.foodics.com too
     for --role work; first delete any existing AUTH key titled <name>   (D10)
   append the box key to dot_config/git/allowed_signers? — NO: see open question Q3
   chezmoi init --apply shahwan42/shdots \
     --promptChoice kind=vm,role=<role> --promptString hostname=<name> \
     --promptBool "Install eod skill=<true for work>"
   run the "Verifying a new VM" checks from provision/README.md
   ```
   The 1Password service-account token reaches the box through chezmoi
   (`dot_config/private_op/encrypted_private_env.age`, decrypted with the age key).
5. `secrets.zsh` already provides the GitHub tokens, so the old
   "export GITHUB_TOKEN" manual step disappears.
6. Collapse per-role key naming once both boxes use one key: `git-signing-key`
   becomes `id_ed25519` everywhere and the work-VM branch in
   `private_dot_ssh/config.tmpl` goes. Only do this **after** fdx-dev is rebuilt
   (Phase 3), or fdx-dev breaks.
7. SSH config on the Macs: add `Host *.local` with `User ubuntu`, **alongside**
   the current tailnet `Host fdx-dev as-dev` entry. Keep the tailnet entry until
   Phase 3 passes, or both current boxes become unreachable. Update
   `.chezmoidata/herdr.yaml` / `et` usage to the `.local` names the same way.

**Done when:** a throwaway box (`as-scratch`, small: `--cpus 2 --memory 4G --disk 20G`)
goes from nothing to passing every check in `provision/README.md` "Verifying a new
VM" with no manual step; `ssh as-scratch.local`, `et as-scratch.local` and a
browser to a container port on it work from as-host; then it is destroyed and its
GitHub auth keys deleted.

### Phase 3 — Rebuild drill

**Goal:** prove boxes are disposable by rebuilding the real ones.

**State:** not started. Depends on Phase 2.

1. 🛑 Ask Ahmed to push or stash all work on **as-dev**; list any Docker volumes
   he wants kept.
2. `multipass delete --purge as-dev` (instance-scoped only; never a bare
   `multipass purge`), then `provision/new-box as-dev --role personal`.
   Target: working in under 30 minutes. Record the real time here.
3. Repeat for **fdx-dev** (`--role work`). ⚠️ github.foodics.com may forbid
   adding SSH keys through the API; if `gh ssh-key add` fails there, Ahmed adds
   the key in the web UI.
4. Ahmed removes both old nodes in the Tailscale admin console.
5. Remove the tailnet `Host fdx-dev as-dev` block and the old herdr entries; do
   Phase 2 step 6.

**Done when:** both boxes are rebuilt from `new-box`, reached only over
`<name>.local`, `chezmoi status` clean, `chezmoi-health check` ok.

### Phase 4 — Prod box

**Goal:** `provision/new-box as-prod-01 --prod --provider multipass|hetzner`
gives a box ready for `docker compose` deploys.

**State:** not started. Try on a local Multipass box first (free), then Hetzner.

**Files (new):** `provision/prod-cloud-init.yaml`, `provision/edge/compose.yaml`
(caddy-docker-proxy), `provision/deploy` (Mac-side deploy script with the port
check), per-provider launchers.

**Cloud-init contents:** timezone, swap, chrony (with the Phase 2 fix),
unattended security upgrades without auto-reboot, Docker Engine + Compose,
Tailscale package (not joined), Eternal Terminal, a `deploy` user in the
`docker` group with both workstation pubkeys, ufw: allow 80/443 and 22,
`allow in on tailscale0`, deny everything else, enabled.

**Steps**
1. Launch. Ahmed runs `sudo tailscale up --ssh --hostname=as-prod-01` (D9).
2. A `close-public-ssh` step removes the public 22 rule, but **refuses** unless
   `tailscale0` is up and an SSH over the tailnet succeeds.
3. Start the edge stack: caddy-docker-proxy on the external network `edge`,
   publishing 80/443, with its `/data` on a named volume (Let's Encrypt allows
   5 duplicate certificates a week; a rebuild loop would hit it).
4. Mac side: `docker context create as-prod-01 --docker host=ssh://deploy@as-prod-01`.
5. `provision/deploy <app-dir> as-prod-01`: run `docker compose config --format json`,
   **fail** if any service outside the edge stack publishes a port not bound to
   `127.0.0.1`, then `docker --context as-prod-01 compose up -d`.
6. Deploy a hello-world app with Caddy labels and check HTTPS works.

**Stable across rebuilds:** tailnet name (remove the old node first), public IP
(Hetzner Primary IP / reserved IP), Caddy `/data`, app data off the root disk.

**Done when:** a rebuilt `as-prod-01` serves the hello-world app over HTTPS,
public scan shows only 80/443, and the deploy check rejects a compose file that
publishes `5432:5432`.

### Phase 5 — Docs and fallback drill

**State:** not started.

1. Rewrite the README "Machine topology" section to section 2 of this file
   (validate any mermaid with `mmdc` first).
2. Fallback drill on **fdx-host**: create a throwaway dev box with `new-box`,
   deploy to a prod box, reach the work servers. Fix whatever needs as-host.
3. Mark this plan done.

---

## 7. Open questions (ask Ahmed; not decided)

- **Q1** Prod app secrets (`.env` delivery) and per-app data persistence: deferred on purpose. Phase 4 must leave room for both.
- **Q2** Does netcup accept cloud-init user-data at server creation? Unverified. Fallback: copy the file over SSH and run `cloud-init` against it.
- **Q3** Box signing keys and `allowed_signers`: box keys rotate on every rebuild. Should boxes be able to push signed commits to shdots (then `new-box` must add the key to `allowed_signers` and push), or should shdots changes only come from workstations?
- **Q4** Custom dev-box names (for example `as-blog`, `fdx-cashflow`): explored, parked. If picked up: prefix convention `as-`/`fdx-` sets the role, per-class herdr defaults instead of per-host entries, and size tiers, because RAM is the real limit.
- **Q5** herdr: how a new box is registered on the Mac's herdr client (`herdr machine add`?) is unverified.
