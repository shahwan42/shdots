# Provisioning assets

Reproducible machine-provisioning files that belong in the repository but must never be
applied into `$HOME` by chezmoi. The entire directory is excluded in `.chezmoiignore.tmpl`,
so chezmoi never reads anything here.

## Contents

- `new-box` — **the supported way to get a new dev box.** Launches, waits for
  cloud-init, seeds the age identity, generates and registers an SSH key with
  GitHub, runs `chezmoi init --apply` non-interactively, primes mise, and runs the
  verification checks below — end to end, no manual step except AI-CLI sign-in.
  Also has a `destroy` subcommand. See `./new-box --help`.
- `dev-vm-cloud-init.yaml` — cloud-init for a dev VM. One file for every dev box; the
  `@@`-delimited placeholders are substituted at launch by `launch-dev-vm.sh` (this is
  not a chezmoi template — it is never rendered by chezmoi).
- `launch-dev-vm.sh` — the Multipass launcher `new-box` calls. Fills in the cloud-init
  placeholders and runs `multipass launch`; also usable standalone.

## Getting a new dev box

```sh
./new-box as-scratch --role personal --cpus 2 --memory 4G --disk 20G   # a throwaway box
./new-box fdx-dev --role work                                          # the fleet default spec
./new-box as-dev --role personal --dry-run                             # print the plan, do nothing
./new-box destroy as-scratch                                           # GitHub auth keys + multipass delete --purge
```

Every dev VM gets one spec by default (6 cpu / 12G / 220G — see "Dev VM spec" in
`AGENTS.md` at the repo root); `--cpus`/`--memory`/`--disk` are one-off overrides for a
single launch. Both workstations' public keys (`.chezmoidata/fleet.yaml`) are trusted on
every box, not just the launching Mac's. `--role` decides `chezmoi`'s `role` prompt and
which GitHub host(s) get the box's SSH key (github.com always; github.foodics.com too for
`--role work`).

`launch-dev-vm.sh` remains directly usable for the low-level launch step alone:

```sh
./launch-dev-vm.sh as-dev                              # personal VM — 6 cpu / 12G / 220G
./launch-dev-vm.sh fdx-dev                             # work VM — same spec
./launch-dev-vm.sh as-dev --dry-run                    # print the plan, launch nothing
```

## What cloud-init does, and what it deliberately leaves

Unattended: timezone, swap, chrony (fixed directly in `/etc/chrony/chrony.conf` — a
`conf.d` drop-in never wins there, see fleet-topology.md gotcha 1), no-auto-reboot for
unattended-upgrades, Docker Engine + a `docker-user-fw.service` unit that reconciles the
`DOCKER-USER` chain (and, on Multipass, `et`'s ufw rule) on every boot, avahi (`<name>.local`
resolution from a Mac), Eternal Terminal from a signed repo, zsh as the login shell, mise,
and ufw **enabled** (rules are staged before `ufw enable` runs, so the multipass NAT
NIC's port-22 allow is always in place first). Dev boxes don't use Tailscale (D7).

Left to a human, or to `new-box`, because it is interactive or decision-gated:

| # | Step | Command |
|---|------|---------|
| 1 | age identity — `chezmoi init` aborts on `~/.config/op/env` without it | `ssh <name>.local 'mkdir -p ~/.config/chezmoi'` then `scp ~/.config/chezmoi/key.txt <name>.local:~/.config/chezmoi/key.txt` |
| 2 | SSH key — commit signing is on everywhere and fails loudly without it | `ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519`; add the `.pub` to GitHub as **both** an authentication and a signing key (github.foodics.com too for a work box — one key, two hosts, D10) |
| 3 | chezmoi — prompts for role and kind | `sh -c "$(curl -fsLS get.chezmoi.io/lb)" -- init --apply shahwan42/shdots` |
| 4 | AI agents — mise installs the binaries; each still needs an interactive sign-in on first run | `claude`, then `/login`; run `codex` and follow its sign-in prompt |

`GITHUB_TOKEN` is no longer a manual step: the managed `~/.config/zsh/secrets.zsh` pulls
mise's GitHub token from 1Password once the age identity is on the box (step 1). Its
cache is only populated by an *interactive* shell, so a box's first `chezmoi apply` can
still 403 partway through `mise install` — non-fatally. `new-box` primes this itself
(one `zsh -ic 'mise install -y'` after `chezmoi init`); doing it by hand is just opening
an interactive shell and re-running `mise install`.

`package_upgrade: true` means two launches weeks apart get different package sets —
"reproducible" here is same shape, not bit-identical.

## Verifying a new VM

`new-box` runs all of this itself and prints PASS/FAIL per check. To run it by hand:

```sh
chezmoi data | grep -E 'role|kind'      # the class you answered in step 3
chezmoi status                          # empty
chezmoi cat ~/.zshrc | zsh -n           # parses
mise ls --missing                       # empty — the real completeness test
git -C ~/.config/nvim remote get-url origin   # nvim-config external cloned
docker run --rm hello-world             # group membership took effect
systemctl is-active et
systemctl --user is-enabled chezmoi-update.timer
git -C ~/.local/share/chezmoi config commit.gpgsign && test -f "$(git -C ~/.local/share/chezmoi config user.signingkey)"
```

On a `role=personal` box, `~/.ssh/config.d/foodics` must be **absent** — that is the role
guard working. On a `role=work` box created by `new-box` *before* Phase 3 step 6 lands,
the git-signing-key check above is expected to **fail**: `.chezmoitemplates/git-signing-key`
still names `~/.ssh/id_ed25519_foodics` for `kind=vm, role=work`, a file `new-box`
deliberately does not create (D10 calls for one key; the templates haven't been collapsed
onto it yet — see fleet-topology.md Phase 2 step 6 / Phase 3 step 5). `role=personal` is
unaffected.
