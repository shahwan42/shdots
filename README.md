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

> **`GITHUB_TOKEN`**: mise's `github:`/`ubi:` backends call the GitHub API, which is
> rate-limited to 60/hr unauthenticated — a full `mise install` will 403 partway.
> Put a read-only PAT in the unmanaged **`~/.zshrc.local`** (where machine-local
> secrets already live), which the shell sources:
>
> ```sh
> export GITHUB_TOKEN="$(op read 'op://Private/GitHub PAT/token')"   # or a literal on the VM
> ```
>
> `mise install` then picks it up from the environment. The `aqua:`/`core:`/`pipx:`
> tools install fine without it.

## Machine topology

Every box is a first-class Tailscale node; the personal MacBook reaches the VM and the
Host directly by tailnet name. Inside `fdx-dev`, the cashflow stack binds web ports to
the tailnet but keeps datastores on loopback.

```mermaid
flowchart TB
  personal["Personal MacBook<br/>role=personal · kind=mac"]

  subgraph host["Work MacBook — the Host (role=work · kind=mac)"]
    chrome["Chrome + browser-harness (CDP)"]
    mp["Multipass CLI"]
    colima["colima (stopped, preserved)"]
  end

  subgraph vm["fdx-dev — Ubuntu VM (role=work · kind=vm)"]
    herdr["herdr sessions"]
    misevm["mise toolchain"]
    subgraph stack["cashflow — docker compose"]
      web["web ports (tailnet-reachable)<br/>api 8080 · console 8081 · vite 15173"]
      data["datastores (loopback-only, via ssh -L)<br/>mysql · redis · microcks"]
    end
  end

  personal -->|tailscale ssh| vm
  personal -->|"tailscale ssh · Screen Sharing"| host
  personal -->|"browser → http://fdx-dev:8080"| web
  mp -.->|launches / manages| vm
  personal -.->|"ssh host browser-harness"| chrome
```

## How every machine gets provisioned

One public repo, one `chezmoi apply`; the `role × kind` answers decide what each machine
receives. The cross-platform CLI toolchain comes from mise (shared), Homebrew is trimmed
to Mac-only natives and GUIs, and zsh plugins are pulled as chezmoi externals.

```mermaid
flowchart TB
  bootstrap["Bootstrap (curl, no Homebrew)<br/>get.chezmoi.io → mise.run"]
  repo["shdots — public GitHub repo"]
  bootstrap --> repo
  repo --> chezmoi{"chezmoi apply<br/>keyed by role × kind"}

  chezmoi --> shared["Shared everywhere<br/>zsh · git · nvim · gitignore_global"]
  chezmoi --> mac["kind=mac only<br/>Brewfile natives/GUI · GPG signing · Sourcetree"]
  chezmoi --> work["role=work only<br/>work mise tools · AWS/JIRA env"]

  chezmoi --> ext["zsh plugins<br/>.chezmoiexternal (git-repo)"]
  chezmoi --> mise["mise install<br/>aqua · ubi · pipx · github backends"]
  mise --> tools["one cross-platform toolchain<br/>Mac + VM, ~40 shared tools"]

  age["age-encrypted work SSH hosts<br/>identity: ~/.config/chezmoi/key.txt"] --> work
  secrets["Unmanaged secrets<br/>.npmrc · ssh keys · .zshrc.local"] -.->|never committed| repo
  hook["gitleaks pre-commit hook<br/>wired on every machine"] -.->|guards| repo
```

## How installs are split

- **mise** (`~/.config/mise/config.toml`) — the cross-platform CLI toolchain, shared
  across all machines (a `role=work` block adds work-only tools). Prefer this for any
  new tool. Uses `aqua:`/`ubi:`/`github:` backends (prebuilt binaries).
- **Homebrew** (`Brewfile`, macOS only) — only behavior-sensitive natives (GNU
  coreutils, ffmpeg), system services (nginx, dnsmasq, docker), GUI apps/casks, and
  the PHP/iOS stack. Not the general CLI toolchain.
- **chezmoi externals** (`.chezmoiexternal.toml`) — zsh plugins, pulled from git into
  `~/.local/share/zsh/plugins` identically everywhere.
- **PHP / composer** — kept native (Homebrew `php@8.3` on Mac, apt php modules on the
  VM), not routed through mise, so the extension matrix comes ready-built.

[herdr](https://herdr.dev) — the terminal multiplexer — is just another shared mise
tool (`aqua:herdrdev/herdr`), the same on Mac and VM.

## Secrets & the work SSH sync

Never committed: `~/.npmrc`, `~/.ssh/id_*`, `~/.zshrc.local` (machine-local exports),
and per-host SSH config. A gitleaks pre-commit hook is wired on every machine by
`run_once_after_10-configure-git-hooks.sh`.

Age encryption is enabled on **every** machine class. The decryption identity lives,
unmanaged, at `~/.config/chezmoi/key.txt` — provision it once per machine (copy from an
existing machine over the tailnet), then `chezmoi init` picks up the encryption config.
Role guards decide *what* decrypts *where*:

- Work SSH hosts (bastion + internal staging) — `role=work` only; personal machines
  ignore the encrypted file entirely.
- 1Password service-account token (`~/.config/op/env`) — all machines. Sourced by
  `.zshrc`, it makes `op read op://dev-secrets/<item>/<field>` and
  `op run --env-file … -- <cmd>` work headless (no GUI unlock, no `op signin`) — the
  runtime-secrets layer for agents and scripts. The service account is read-only and
  scoped to the `dev-secrets` vault; rotate/revoke it from the 1Password web console.
  Macs get `op` from the `1password-cli` cask, VMs from mise (`aqua:1password/cli`).

> This repo is **public**. Anything genuinely secret stays unmanaged or age-encrypted;
> enable GitHub secret-scanning push protection as a backstop.

## Retiring what the unification replaced

`provision/cleanup-after-unification.sh` removes tools/files made redundant by the move
to mise. It is **dry-run by default** — review its output, then run with `--apply`.
