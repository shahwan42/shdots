# Native macOS account profiles

Current architecture (2026-10-03): `as-host/as` is personal; `as-host/foodics`
is work. macOS is the primary development platform. `as-host/fdx-dev` is the
only temporary canonical Linux compatibility VM; the duplicate on `fdx-host`
is stopped and preserved. Tailscale identity remains unchanged.

```text
as-host
  shared: /opt/homebrew, /Applications, physical hardware
  as       -> personal config + personal authentication + local development
  foodics  -> work config + work authentication + local development
  fdx-dev  -> optional Linux compatibility (explicit invocation)
```

## Data and account boundaries

`kind=mac|vm` selects platform behavior. `hostname` is the existing machine key;
`username` records the current OS account, independently of the machine.
`role=personal|work` selects consumers. Native `as` resolves to personal and
`foodics` to work, including old Mac configs whose role is empty. Unknown
accounts need an explicit role; mismatched known-user roles or recorded usernames
fail rendering. VM roles remain explicit.

`has-personal` / `has-work` are the common gates. Shared shell ergonomics, CLI,
terminals, portable agent skills, Worktrunk and editor configuration go to both
accounts. Personal Gmail/Calendar, personal GitHub PATs, tutoring DB declarations,
ClearMoney QA and Caveman integration stay personal. Work tool declarations
include AWS/Jira/Sonar tooling and Harlequin; EOD is work-only and opt-in.
No work package-registry credentials, AWS profile/login or repositories are copied.

The work shell defaults `GH_HOST=github.foodics.com`; public GitHub is an
explicit host override using the work account's own authentication.

The work account is `foodics`, full name `A. S. Foodics`, email
`a.shahwan@foodics.com`, role `work`, on `as-host`.
Git defaults to personal or Foodics identity at the account level, including
checkouts under `~/Code/worktrees`. The retired directory-based work Git include
is ignored. Repository-local Git overrides still take precedence: inspect them
when repositories are migrated later. New native work profiles have signing
turned off, allowing initial local commits before keys exist. Enable
`git_signing` only after provisioning an account-local key and registering it.
Public historical signers are verification metadata, not signing credentials;
the work render contains only historical work signers.

## Secret provisioning

Native profiles ignore both retained age-encrypted targets (`.config/op/env` and
`.ssh/config.d/foodics`) and never source the broad fleet service-account token.
Do not copy the age identity into the work account. The ciphertext and source
stash remain intact. Legacy VM handling is retained, not endorsed for new users.

`secret_integrations=false` is the work onboarding default. It prevents shell
secret consumers and PAT registration. The Enterprise OpenCode declaration is
disabled until the flag is enabled. Existing personal targeted PAT consumers
remain available through personal account-local 1Password authentication.
An opt-in work render includes only the work PAT/Jira/Sonar references. These
old UUID references must be reviewed against a work-only vault/login before
opting in; template gating does not grant or restrict 1Password vault access.

Provision separately, in the intended account: GitHub Enterprise; public GitHub
if needed; fresh SSH Git keys; 1Password SSH-agent/company-server access;
package registries; AWS; AI tool logins. Review any work-only token replacement
in shdots by reference, never by copying its value. `.npmrc`, `.aws`, `.ssh/id_*`,
AI login/session files, approvals and scheduled tasks are unmanaged.

SSH loads only `.ssh/config.d/personal/*` or `.ssh/config.d/work/*`. It ignores
the old mixed directory's files. `linux-compat` is an optional alias to
`fdx-dev.local`; no terminal startup connects to it. `herdr-devbox` requires
an explicit VM name. Work Git authentication points to a future local key;
company-server hosts and 1Password key selection remain manual provisioning.

## Shared installation, isolated state

One `/opt/homebrew` installation is owned/maintained primarily by `as`; both
users consume its binaries. Only `as` can run the managed Brewfile installer.
`foodics` must not install a second Homebrew or run `brew bundle`. The Brewfile
is a physical-machine inventory; receiving it is not permission to maintain it.
No Homebrew ownership/permission changes are part of this migration.

chezmoi and mise executables are installed per user in `~/.local/bin`.
mise config, data, state, caches and runtime installs remain user-local;
`foodics` never depends on `as`'s mise store. Project
`mise.toml` files remain authoritative. No shared writable runtime store is
introduced. App runtimes needed by a project should be provisioned natively
through that project's documented runtime setup, not by defaulting to Sail or
remote Docker. Generic Docker inspection tools remain optional utilities.

Neovim's editor repository remains `nvim-config` and is fetched over public
HTTPS. A URL naming its author is provenance, not a login/account selection.
No additional configuration repository is introduced.

## AI paths and background behavior

Worktrunk uses `~/Code/worktrees/{{ repo }}/{{ branch | sanitize_hash }}` in
both accounts. Client references are `$HOME` or chezmoi home/source templates;
there are no portable absolute paths into the other user's home. Codex only
gets portable instructions and role-scoped MCP registration; its existing
config/trust records stay account-local. Fresh trust is reviewed in each
account, as [documented by OpenAI](https://developers.openai.com/codex/config-basic/).
Claude and OpenCode generated configuration also stays local. Worktrunk project
approvals and agent plugin trust need local review; none are transplanted.

Herdr defaults to local sessions. Native plugin onboarding is deferred rather
than importing VM plugin/runtime state. Native shell startup never runs SSH
into a VM. The old default `as-dev` helper and active workflow-launch keybind
are removed; `herdr-devbox <vm-name>` remains optional. Native cleanup scripts
are disabled: historical state is reviewed manually, not deleted at bootstrap.

Native `auto_update=false` excludes the update LaunchAgent; the installer is
inert and the update helper exits before fetching/applying. No AI scheduled
job, personal integration session or obsolete VM service is copied. Tools'
configuration/install scripts would run on a future authorized apply, but
none have run during Step 3. macOS defaults are an explicitly invoked helper,
never a chezmoi run script. Existing live agents keep their current behavior
until an authorized rollout. Legacy update timers follow `origin/main`;
publishing the migration branch does not change their applied source.

## macOS and keyboard candidate

`macos-user-defaults` previews by default and requires `--apply` from the intended
account. It declares repeat 2/15, press-and-hold off, keyboard UI mode 2,
English/Arabic (Egypt), trackpad tap/right click, and Finder hidden files,
extensions, path/status bars, column view and current-folder search. Input
source metadata records observed ABC (252) and Arabic PC (-17921); add these in
System Settings rather than replacing macOS's full input-source array.

The optional Karabiner complex-modification asset declares Caps Lock → Escape
and Escape → Caps Lock, matching the selected live `as-host` profile. It is
available for manual selection, not active, and contains no device identifiers.
The source Escape → grave/tilde behavior is not selected. Existing device
mappings and all privacy/security permissions remain local. Before enabling,
review existing simple modifications to avoid stacking duplicate mappings.

## Validation and rollback

Run `python3 tests/account_profiles.py` with chezmoi, Git and Zsh available.
Set `SHDOTS_AUDIT_DIR` to retain full dumps, diffs, dry-run output, command logs
and syntax-check results. Tests use isolated config/cache/state and empty scratch
destinations, override account username/home/source paths, exclude encrypted
files and externals, and never execute run scripts. Externals are checked
statically; downloading/pulling them is deferred. Both native profiles, legacy
empty-role configs, rejected identity mismatches, opt-in token consumers and
Linux role renders are covered. Git config inheritance is checked using
scratch `.git` pointer fixtures at two unrelated checkout paths.

`foodics` still needs one verification from its own local terminal: initialize
chezmoi configuration without applying, confirm `hostname=as-host`, username,
role and onboarding flags, run `chezmoi diff --exclude=externals`, then `chezmoi apply --dry-run
--verbose --exclude=externals`. Review its current unmanaged state and actual
application paths. No age key is required. Excluding externals avoids a Neovim
pull during this review; their later clone/pull needs its own onboarding check.

Rollback before applying: continue using the original clean `main` checkout;
the published migration branch is opt-in. After a later rollout, rollback must
be account-local and reviewed; old mixed-identity configuration is not a safe
work-account fallback. The preservation checkpoint and original source state
remain intact. Restarting the duplicate legacy VM would restore the duplicate
node-identity problem; require a separate identity decision before any restart.
