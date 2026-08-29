# Provisioning assets

Reproducible machine-provisioning files that belong in the repository but must never be
applied into `$HOME` by chezmoi. The entire directory is excluded in `.chezmoiignore.tmpl`,
so nothing here is a chezmoi template — the `.tmpl` suffix on the cloud-init marks a file
with placeholders, filled in by the launcher below.

## Contents

- `dev-vm-cloud-init.yaml.tmpl` — cloud-init for a dev VM. One template for every dev box;
  `@@VM_NAME@@` and `@@HOST_SSH_PUBKEY@@` are substituted at launch.
- `launch-dev-vm.sh` — renders that template and runs `multipass launch`. The only
  supported way to use the cloud-init.
- `cleanup-after-unification.sh` — removes tools/files made redundant by the mise
  unification. Dry-run by default; review the output, then re-run with `--apply`.
  Run manually — chezmoi never executes it.

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
| 2 | age identity — `chezmoi init` aborts on `~/.config/op/env` without it | `scp ~/.config/chezmoi/key.txt <name>:~/.config/chezmoi/key.txt` |
| 3 | SSH key — commit signing is on everywhere and fails loudly without it | `ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_personal` (work VM: `id_ed25519_foodics`), add the `.pub` to GitHub as **both** an authentication and a signing key, then append it to `dot_config/git/allowed_signers` |
| 4 | `GITHUB_TOKEN` in unmanaged `~/.zshrc.local` | else `mise install` 403s partway on the `github:`/`ubi:` backends — *non-fatally*, so a bootstrap can look complete |
| 5 | chezmoi — prompts for role and kind | `sh -c "$(curl -fsLS get.chezmoi.io)" -- init --apply shahwan42/shdots` |
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
docker run --rm hello-world             # group membership took effect
systemctl is-active et
systemctl --user is-enabled chezmoi-update.timer
git -C ~/.local/share/chezmoi log --show-signature -1
```

On a `role=personal` box, `~/.ssh/config.d/foodics` must be **absent** — that is the role
guard working.
