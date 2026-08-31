# Provisioning assets

Reproducible machine-provisioning files that belong in the repository but must never be
applied into `$HOME` by chezmoi. The entire directory is excluded in `.chezmoiignore.tmpl`,
so chezmoi never reads anything here.

## Contents

- `dev-vm-cloud-init.yaml` — cloud-init for a dev VM. One file for every dev box; the
  `@@VM_NAME@@` and `@@HOST_SSH_PUBKEY@@` placeholders are substituted at launch by the
  script below (this is not a chezmoi template — it is never rendered by chezmoi).
- `launch-dev-vm.sh` — fills in those placeholders and runs `multipass launch`. The only
  supported way to use the cloud-init.

## Launching a dev VM

```sh
./launch-dev-vm.sh as-dev                              # personal VM: 6 cpu / 12G / 200G
./launch-dev-vm.sh fdx-dev --memory 10G --disk 160G    # work VM, as originally built
./launch-dev-vm.sh as-dev --dry-run                    # print the plan, launch nothing
```

Run it **on the Host that will own the VM** — it authorizes that Mac's own public key
(`~/.ssh/id_ed25519.pub`, else `~/.ssh/id_rsa.pub`; override with `--pubkey`). This is
why the work Host's key is no longer hardcoded: a VM launched from `as-host` must trust
`as-host`, not `fdx-host`.

Sizing is per-Host, not per-VM-role — `as-host` has more RAM and disk than `fdx-host` but
fewer cores, hence the different defaults. The `--disk` value is a ceiling; qemu allocates
sparsely.

## What cloud-init does, and what it deliberately leaves

Unattended: timezone, swap, chrony (`makestep`, so a guest that slept doesn't wake with a
wrong clock), no-auto-reboot for unattended-upgrades, Docker Engine + the `DOCKER-USER`
rule that stops published container ports bypassing ufw on the NAT NIC, Tailscale and
Eternal Terminal from signed repos, zsh as the login shell, mise, and ufw rules **staged
but not enabled**.

Left to a human because it is interactive or decision-gated:

| # | Step | Command |
|---|------|---------|
| 1 | Tailscale — needs browser auth | `sudo tailscale up --ssh --hostname=<name>` then `sudo tailscale set --auto-update` |
| 2 | age identity — `chezmoi init` aborts on `~/.config/op/env` without it | `ssh <name> 'mkdir -p ~/.config/chezmoi'` then `scp ~/.config/chezmoi/key.txt <name>:~/.config/chezmoi/key.txt` |
| 3 | SSH keys — commit signing is on everywhere and fails loudly without it | personal VM: `ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_personal`; work VM: generate **both** `id_ed25519_foodics` **and** `id_ed25519_personal` (the managed ssh config offers the personal key to github.com on work VMs too). Add each `.pub` to its GitHub as **both** an authentication and a signing key, then append it to `dot_config/git/allowed_signers` |
| 4 | `GITHUB_TOKEN` — export in the **current shell** (step 5 needs it) *and* persist: `export GITHUB_TOKEN=...` then `echo 'export GITHUB_TOKEN=...' >> ~/.zshrc.local` | else `mise install` 403s partway on the `github:`/`ubi:` backends — *non-fatally*, so a bootstrap can look complete |
| 5 | chezmoi — prompts for role and kind | `sh -c "$(curl -fsLS get.chezmoi.io/lb)" -- init --apply shahwan42/shdots` |
| 6 | ufw — only after confirming `multipass shell <name>` still works | `sudo ufw enable` |

Step 6 matters: the staged rules include a port-22 allow on the multipass NAT interface.
Lose it and every `multipass stop` becomes a hard power-off.

`package_upgrade: true` means two launches weeks apart get different package sets —
"reproducible" here is same shape, not bit-identical.

## Verifying a new VM

```sh
chezmoi data | grep -E 'role|kind'      # the class you answered in step 5
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
guard working.
