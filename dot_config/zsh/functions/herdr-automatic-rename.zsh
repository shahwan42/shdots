# herdr-automatic-rename: live per-command tab naming (zsh hook loader).
#
# The plugin ships shell/hook.zsh inside its content-hashed install dir under
# ~/.config/herdr/plugins/github/herdr-automatic-rename-<hash>/. Sourcing it
# registers preexec/precmd hooks so a tab is renamed the instant a command
# starts, rather than waiting for the next herdr event. Everything else -- tab
# switches, new tabs, agents, [N] numbering -- is driven by the plugin's own
# herdr events and needs nothing here.
#
# Not host-scoped on purpose. The (N) glob qualifier makes this a no-op wherever
# the plugin is not installed (as-host is client-only and never gets it), and
# hook.zsh itself no-ops outside a herdr pane. So this file stays correct if the
# fleet gains another execution host, with no template branch to keep in sync.
#
# Idempotent: add-zsh-hook dedupes the hooks on re-source. Cheap: the sourced
# file is ~3 KB and backgrounds its actual work, so startup pays one source
# inside a herdr pane and nothing at all elsewhere.
for _f in ${HOME}/.config/herdr/plugins/github/herdr-automatic-rename-*/shell/hook.zsh(N); do
  source "$_f"
  break
done
unset _f
