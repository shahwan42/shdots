# Provisioning assets

This directory holds reproducible machine-provisioning files that belong in
the repository but must never be applied directly into `$HOME` by chezmoi.

Future work and VM onboarding may add cloud-init files, compose overrides, and
LaunchAgents here. The entire directory is excluded in `.chezmoiignore.tmpl`.

## Contents

- `cleanup-after-unification.sh` — removes tools/files made redundant by the
  mise unification. Dry-run by default; review the output, then re-run with
  `--apply`. Run manually — chezmoi never executes it.
- `fdx-dev-cloud-init.yaml` — cloud-init for the disposable dev VM. Regenerate
  fdx-dev on the work Host with:

  ```sh
  multipass launch 24.04 --name fdx-dev --cpus 6 --memory 10G --disk 160G \
    --cloud-init fdx-dev-cloud-init.yaml
  ```

  Nothing in it is machine-specific — reuse verbatim for the future personal
  `as-dev` VM (identity comes from `--name` and `tailscale up --hostname`).
  Post-launch manual steps (tailscale, ufw, credentials) are listed in the
  file's header comment.
