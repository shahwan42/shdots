# shdots

Account-aware dotfiles managed with [chezmoi](https://chezmoi.io).
macOS development runs natively on `as-host` in two isolated accounts.

| Machine | Username | Role | Default Git identity |
| --- | --- | --- | --- |
| as-host | as | personal | Ahmed Shahwan / a.shahwan42@gmail.com |
| as-host | foodics | work | A. S. Foodics / a.shahwan@foodics.com |

`kind=mac|vm` selects platform behavior; `hostname` names the physical machine;
`username` and `role` select account behavior. `has-personal` and `has-work`
resolve one role, including older Mac configs with an empty role. Mismatched
account data fails closed. See [native onboarding and boundaries](docs/plans/account-aware-macos.md).

## Validate before onboarding

Use the existing chezmoi executable and source; first provisioning is manual.
`tests/account_profiles.py` runs isolated renders, diffs, and dry-run applies.
It never decrypts secrets, executes bootstrap scripts, or writes a real home.

```sh
python3 tests/account_profiles.py
```

On a native account, initialize configuration without `--apply`, review `chezmoi
diff`, then `chezmoi apply --dry-run --verbose`. Applying remains a separate
user-authorized step. New Mac profiles default `auto_update=false`; work profiles
also default `secret_integrations=false`, `git_signing=false`, and `eod=false`.

## Ownership

`shdots` owns portable shell, Git, terminal, Worktrunk and agent configuration.
`nvim-config` remains the separate editor repository, fetched over public HTTPS;
its URL conveys configuration provenance, not a GitHub login or credential.

One `/opt/homebrew` installation is maintained by `as`. Both users consume its
binaries and `/Applications`; `foodics` neither bootstraps Homebrew nor runs the
Brewfile script. No permissions changes or second Homebrew installation are needed.
chezmoi and the mise executable are installed per user in `~/.local/bin`.
mise config, data, state, caches and runtime installs remain under each user's
home. Project `mise.toml` files are authoritative.
Global versions are pinned in `dot_config/mise/config.toml.tmpl`, with no shared
writable store and `lockfile=false`.

## Secrets and background jobs

Native accounts ignore retained encrypted files and never source the shared
1Password service-account environment. Provision authentication separately in
each account. Personal Gmail/Calendar and personal PAT consumers stay personal;
work PAT consumers require an explicit integrations opt-in after work-vault review.
SSH keys, package credentials, AWS logins, AI sessions, approvals and scheduled
AI tasks remain unmanaged. Native profiles install no update LaunchAgent by
default; the update helper also exits before doing work when disabled.

Legacy VM provisioning remains in `provision/` for compatibility research only.
It creates machines, copies broad legacy credentials and applies configuration:
it is not a native-account bootstrap path. The [old fleet plan](docs/plans/fleet-topology.md)
is historical. Legacy update timers follow `origin/main`; publishing a migration
branch does not deploy it. Changes to `main` require an explicit rollout review.
