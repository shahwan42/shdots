# Provisioning assets

This directory holds reproducible machine-provisioning files that belong in
the repository but must never be applied directly into `$HOME` by chezmoi.

Future work and VM onboarding may add cloud-init files, compose overrides, and
LaunchAgents here. The entire directory is excluded in `.chezmoiignore.tmpl`.
