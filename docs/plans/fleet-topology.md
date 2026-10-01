# Fleet topology plan: one workstation, disposable boxes

Status: **Phase 1 done (2026-09-23). Phase 2 done 2026-09-25, committed locally,
not pushed (Ahmed approves). Phases 3 and 5 not started. Prod boxes (old
Phase 4) moved to the infra repo on 2026-10-01.**
Owner: Ahmed. Written for any agent (Claude, Codex, OpenCode) picking this up.

Read this whole file before starting a phase. Then re-check the live state
(`chezmoi git log`, `chezmoi status`, `multipass list`) — the fleet may have
moved on since the status line above was written. Update the status line and
the phase's "State" when you finish or stop.

---

## 1. Goal

Ahmed uses **one physical machine day to day** (as-host). Everything he develops
on is an Ubuntu **box** that can be recreated from this repo:

```
New Mac      -> chezmoi init shdots          -> ready to work (control plane)
New dev box  -> provision/new-box <name>     -> ready to develop on, reached from the Mac
```

Prod/VPS boxes live in the infra repo. They are not chezmoi-managed, and they
never hold the age key or the 1Password service-account token (D4).

## 2. Vocabulary and target topology

| Term | Machines | Chezmoi data | Notes |
|---|---|---|---|
| **workstation** | `as-host` (primary), `fdx-host` (fallback twin) | `kind=mac`, `role=""` | Identity-neutral: carries personal **and** work tools. |
| **dev box** | `as-dev` (personal), `fdx-dev` (work) | `kind=vm`, `role=personal\|work` | Disposable. Multipass on as-host today; maybe a VPS later. |

```
              shdots (GitHub)
          ┌────────┴──────────┐
     chezmoi init    cloud-init + chezmoi
          │                   ▼
   WORKSTATION           DEV BOX
   as-host / fdx-host    as-dev, fdx-dev
   both identities       one identity each
          │                   ▲
          └── plain SSH to <name>.local
```

Company infrastructure is out of scope. `fdx-host` keeps everything, including its
chezmoi auto-update timer.

## 3. Decision log (do not reopen without asking Ahmed)

| # | Decision | Why |
|---|---|---|
| D1 | Identity lives in the box, not the Mac. Macs get both personal and work tools; only a VM is asked for `role`. | One workstation must do both jobs; browser profiles and per-host config separate them. |
| D2 | Gate tools with `includeTemplate "has-personal" .` / `"has-work" .`; gate work-VM-only things with `and (eq .kind "vm") (eq .role "work")`; never test a Mac's `role`. | A Mac's role is empty, so role tests silently fall into `else` branches. |
| D3 | Names: *workstation* / *dev box* / *prod box*. Chezmoi keeps `kind = mac\|vm` (no rename). | Renaming values touches ~15 templates for no behaviour change. |
| D4 | Prod/VPS boxes are **not** managed by chezmoi; they live in the infra repo. | Every push auto-deploys within 6h; the age key and 1Password service-account token are shared. A prod box must hold neither. |
| D5 | Moved to the infra repo. | |
| D6 | Moved to the infra repo. | |
| D7 | No Tailscale on local Multipass dev boxes; plain SSH to `<name>.local`. | Removes the auth key and node churn from disposable boxes. Ahmed never needs a dev box away from the laptop. |
| D8 | Dev-box secrets (age key, 1Password service-account token) are **copied over SSH after launch**, never put in cloud-init user-data. | User-data persists under `/var/lib/cloud`. |
| D9 | Moved to the infra repo. | |
| D10 | Dev boxes: one SSH key per box (`id_ed25519`), generated on each rebuild and registered with `gh` on github.com (and github.foodics.com for work boxes) as auth + signing. Delete the old box's **auth** key by title; keep old **signing** keys. | Background agents must push after Ahmed disconnects, so no agent forwarding. Keeping signing keys keeps old commits Verified. |
| D11 | Box→Mac SSH is not allowed (Macs don't trust box keys). | Box keys rotate on every rebuild. Add back only when truly needed. |
| D12 | Moved to the infra repo. | |
| D13 | Keep Eternal Terminal. | Survives sleep and network changes. |
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
The retired `id_rsa` and the old per-host key live in
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
12. **A fresh box `chezmoi init --apply`s `origin/main`, not your working
    tree.** An unpushed fix (even one already committed) has zero effect on a
    box's own clone. To test a fix on a real box before pushing: commit it,
    `git bundle create x.bundle origin/main..main`, `scp` the bundle over,
    `git -C ~/.local/share/chezmoi pull --ff-only x.bundle main` on the box,
    then `chezmoi apply`. Field-tested 2026-09-25 to land the fix in gotcha 15
    on `as-scratch` without pushing.
13. **Multipass silently drops the quotes around a `write_files:` string that
    looks like a number.** `permissions: "0755"` in
    `provision/dev-vm-cloud-init.yaml` survives Multipass's own YAML
    re-serialization as the bare number `493` (0755 read as octal, YAML 1.1
    rules), and `cloud-init schema --system` then rejects it —
    `cloud-init status --long` reports `degraded`. Don't set `permissions:` on
    a `write_files` entry there; `chmod` it in `runcmd` instead.
14. **Relaunching (or even just stopping/starting) a Multipass box under the
    same name can trigger an mDNS conflict.** avahi on the box detects what it
    thinks is still another host answering for `<name>.local` (stale
    announcement from an earlier instance of the same name) and silently
    renames itself to `<name>-2.local`; `ssh <name>.local` then fails to
    resolve even though the box is up and healthy. `journalctl -u avahi-daemon`
    on the box shows `Host name conflict, retrying with <name>-2`. No fix
    applied yet — noted here for whoever hits it next; a full `multipass delete
    --purge` + relaunch (not just stop/start) seems to avoid it, but wasn't
    confirmed to always avoid it.
15. **`docker-user-fw.sh`'s Mac-bridge allow rule is IPv4-only.** The DOCKER-USER
    chain's IPv6 half (`ip6tables -S DOCKER-USER`) is created but left with no
    rules at all — neither the drop-all nor the Mac-only accept — so a
    container port is unfiltered over IPv6 to anything that can route to the
    box's ULA address (`fd0d:...`), which in practice means other hosts on the
    same L2/bridge. IPv4 access from the Mac is correctly scoped (verified
    2026-09-25: `iptables -L DOCKER-USER -v -n` shows the Mac's bridge address
    ACCEPTed above a DROP-all). Needs an Ahmed call: mirror the same two rules
    into `ip6tables`, or disable IPv6 on the Docker daemon for dev boxes
    (`ipv6: false` in `/etc/docker/daemon.json`).

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
old per-host key retired. All four machines converged, `chezmoi status` clean.

Leftovers for Ahmed (at fdx-host's keyboard): `brew bundle`,
`mcp-github-register`; rotate the Sonar token; on as-host
`sudo brew services restart tailscale`.

### Phase 2 — `provision/new-box` for dev boxes

**Goal:** `provision/new-box <name> --role personal|work` produces a working dev
box with no manual steps except AI-CLI sign-in.

**State:** steps 1–5 and 7 done 2026-09-25, committed locally (`e7218c8`,
`69c83c9`, `7331d18`), **not pushed** — Ahmed approves the push. Step 6 (collapse
per-role key naming) is explicitly Phase 3, not done.

Done-check ran for real on a throwaway `as-scratch` box (`--role personal`,
2 cpu/4G/20G). It surfaced and fixed one pre-existing bug that isn't
Phase-2-scoped but blocked every box `new-box` creates:
`run_onchange_after_45-herdr-plugins.sh.tmpl` crashed `chezmoi apply` on any
host absent from `.chezmoidata/herdr.yaml` (gotcha 12 explains the Go-template
root cause). Fixed in `e7218c8`. Because a fresh box clones `origin/main`, not
this working tree, the fix could only be exercised on the real box via the
git-bundle method in gotcha 12 (**not** by pushing) — do that again if this
plan is picked up again before `e7218c8`/`69c83c9` land on `main`.

All 10 "Verifying a new VM" checks passed (`data`, `status`, `zshrc-parse`,
`mise-missing`, `nvim-external`, `docker-hello`, `et-active`, `update-timer`,
`git-signing`, `role-guard`). From as-host: `ssh as-scratch.local`,
`et as-scratch.local`, and `curl` to a `docker run -p 8080:80 nginx` on the box
all worked; `iptables -L DOCKER-USER -v -n` showed the Mac's bridge address
ACCEPTed above the DROP-all; a full `multipass stop`/`start` proved the ufw
rules, `docker-user-fw.service`, and the container's `--restart unless-stopped`
all survive a reboot. `new-box destroy as-scratch` removed its GitHub
authentication key and purged the instance; `multipass list` and
`gh api user/keys` confirmed a clean fleet afterward.

Two things fell out of scope for a fix here, both new gotchas (14, 15): the
stop/start cycle triggered an mDNS name conflict (avahi renamed the box to
`as-scratch-2.local`), and the Mac-bridge firewall allow is IPv4-only — the
IPv6 half of DOCKER-USER has no rules at all.

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

### Phase 5 — Docs and fallback drill

**State:** not started.

1. Rewrite the README "Machine topology" section to section 2 of this file
   (validate any mermaid with `mmdc` first).
2. Fallback drill on **fdx-host**: create a throwaway dev box with `new-box`,
   reach the work servers. Fix whatever needs as-host.
3. Mark this plan done.

---

## 7. Open questions (ask Ahmed; not decided)

- **Q1, Q2** Moved to the infra repo.
- **Q3 — answered 2026-09-25.** Only the existing signers are trusted for shdots
  commits: the workstations and the current as-dev + fdx-dev keys already in
  `dot_config/git/allowed_signers`. `new-box` does **not** add a new box's key to
  `allowed_signers`, and never pushes. New boxes still register their key on
  GitHub as authentication + signing (for project repos, not shdots). **Revisit in
  Phase 3:** rebuilding as-dev/fdx-dev rotates their keys, so both drop out of
  `allowed_signers` the moment they're rebuilt — Phase 3 must either add the new
  keys (from a workstation, signed by a still-trusted key) before or as part of the
  rebuild, or accept that old commits signed by the retired keys stop verifying.
- **Q4** Custom dev-box names (for example `as-blog`, `fdx-cashflow`): explored, parked. If picked up: prefix convention `as-`/`fdx-` sets the role, per-class herdr defaults instead of per-host entries, and size tiers, because RAM is the real limit.
- **Q5 — answered 2026-09-25.** Skipped for now: `new-box` does not register a new
  box with the Mac's herdr client. `.chezmoidata/herdr.yaml` still names only
  `as-dev` as onboarded; a box created by `new-box` gets no herdr desired-state
  entry and `run_onchange_after_45-herdr-plugins.sh.tmpl` no-ops for it (falls into
  its "no Herdr desired-state ... nothing to do" branch). Revisit if/when herdr
  registration for a fresh box is worked out.
