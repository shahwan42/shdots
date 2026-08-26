# Provisioning assets

This directory holds reproducible machine-provisioning files that belong in
the repository but must never be applied directly into `$HOME` by chezmoi.

Future work and VM onboarding may add cloud-init files, compose overrides, and
LaunchAgents here. The entire directory is excluded in `.chezmoiignore.tmpl`.

## Contents

- `cleanup-after-unification.sh` — removes tools/files made redundant by the
  mise unification. Dry-run by default; review the output, then re-run with
  `--apply`. Run manually — chezmoi never executes it.
