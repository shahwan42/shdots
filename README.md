# shdots

Personal + work dotfiles, managed with [chezmoi](https://chezmoi.io). One source
serves four machine classes, selected at init by two answers:

| data   | values            |
|--------|-------------------|
| `role` | `personal` \| `work` |
| `kind` | `mac` \| `vm`      |

## Bootstrap a new machine

Two cross-platform `curl` one-liners — no Homebrew required (`curl` ships on macOS
and is installed by the VM's cloud-init):

```sh
# 1. chezmoi installs itself and applies this repo (prompts for role + kind)
sh -c "$(curl -fsLS get.chezmoi.io)" -- init --apply shahwan42

# 2. mise is installed automatically by run_once_before_00-install-mise.sh
#    (curl https://mise.run | sh) and the toolchain is provisioned by
#    run_onchange_after_20-mise-install.sh (mise install).
```

After apply, open a fresh login shell. On a Mac, run `brew bundle --file=~/Brewfile`
once for the native/GUI packages that stay outside mise.

## How installs are split

- **mise** (`~/.config/mise/config.toml`) — the cross-platform CLI toolchain, shared
  across all machines (a `role=work` block adds work-only tools). Prefer this for any
  new tool. Uses `aqua:`/`ubi:`/`github:` backends (prebuilt binaries).
- **Homebrew** (`Brewfile`, macOS only) — only behavior-sensitive natives (GNU
  coreutils, ffmpeg), system services (nginx, dnsmasq, docker), GUI apps/casks, and
  the PHP/iOS stack. Not the general CLI toolchain.
- **chezmoi externals** (`.chezmoiexternal.toml`) — zsh plugins, pulled from git into
  `~/.local/share/zsh/plugins` identically everywhere.
- **herdr** — PHP/composer environment (kept off mise; native extension matrix).

## Secrets & the work SSH sync

Never committed: `~/.npmrc`, `~/.ssh/id_*`, `~/.zshrc.local` (machine-local exports),
and per-host SSH config. A gitleaks pre-commit hook is wired on every machine by
`run_once_after_10-configure-git-hooks.sh`.

Work SSH hosts (bastion + internal staging) are **age-encrypted** and sync only to
`role=work` machines. The decryption identity lives, unmanaged, at
`~/.config/chezmoi/key.txt` — provision it once per work machine (copy from an existing
work machine over the tailnet), then `chezmoi init` picks up the encryption config.
Personal machines ignore the encrypted file entirely.

> This repo is **public**. Anything genuinely secret stays unmanaged or age-encrypted;
> enable GitHub secret-scanning push protection as a backstop.

## Retiring what the unification replaced

`provision/cleanup-after-unification.sh` removes tools/files made redundant by the move
to mise. It is **dry-run by default** — review its output, then run with `--apply`.
