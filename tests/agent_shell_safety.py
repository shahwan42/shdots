#!/usr/bin/env python3
"""Agent-only zsh compatibility checks; all generated files stay in scratch."""
import json
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def run(args, cwd, env=None, ok=True):
    result = subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=True)
    check((result.returncode == 0) == ok,
          f'{args}: unexpected exit {result.returncode}\n{result.stdout}{result.stderr}')
    return result


def render(audit, home):
    config = audit/'chezmoi.toml'
    config.write_text('''[data]
kind = "mac"
hostname = "agent-shell-test"
role = "personal"
eod = false
auto_update = false
secret_integrations = false
git_signing = false
''')
    override = {'chezmoi': {'username': 'agent-shell-test', 'homeDir': str(home),
                            'sourceDir': str(ROOT), 'os': 'darwin'}}
    base = ['chezmoi', '--config', str(config), '--source', str(ROOT),
            '--destination', str(home), '--cache', str(audit/'cache'),
            '--persistent-state', str(audit/'state.boltdb'),
            '--refresh-externals=never', '--no-tty', '--no-pager', '--color=false',
            '--override-data', json.dumps(override)]
    dumped = run(base+['dump', '--exclude=encrypted,externals', '--format=json'], ROOT)
    entries = json.loads(dumped.stdout)
    for name in ['.zshenv', '.zprofile', '.zshrc', '.config/zsh/env.zsh']:
        target = home/name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(entries[name]['contents'])
    for name in ['.claude/CLAUDE.md', '.codex/AGENTS.md',
                 '.config/opencode/instructions/baseline.md']:
        check('**zsh shell note**' in entries[name]['contents'],
              f'{name}: rendered baseline omitted the shell note')
        check('KSH_ARRAYS' in entries[name]['contents'],
              f'{name}: rendered baseline omitted the KSH_ARRAYS finding')
    return entries


def shell_environment(home, markers=None):
    env = {
        'HOME': str(home),
        'ZDOTDIR': str(home),
        'PATH': f'{home}/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin',
        'XDG_CONFIG_HOME': str(home/'.config'),
        'XDG_DATA_HOME': str(home/'.local/share'),
        'XDG_CACHE_HOME': str(home/'.cache'),
        'XDG_STATE_HOME': str(home/'.local/state'),
        'TERM': 'dumb',
        'SHELL': '/bin/zsh',
        'LC_ALL': 'C',
        'USER': 'agent-shell-test',
        'LOGNAME': 'agent-shell-test',
        'KITTY_WINDOW_ID': '1',
    }
    env.update(markers or {})
    return env


def make_scratch_commands(home):
    localbin = home/'.local/bin'
    localbin.mkdir(parents=True)
    for name in ['eza', 'kitten']:
        tool = localbin/name
        tool.write_text('#!/bin/sh\nexit 0\n')
        tool.chmod(0o755)
    docs = home/'docs'
    docs.mkdir()
    (docs/'result.md').write_text('x\n')
    functions = home/'.config/zsh/functions'
    functions.mkdir(parents=True)
    (functions/'shdots-compinit.zsh').write_text('_shdots_compinit() { :; }\n')


def check_agent_commands(home, mode, markers):
    env = shell_environment(home, markers)
    script = '''\\
echo ====
print -r -- nomatch*.none
grep -rl x --include=*.md "$HOME/docs"
print -r -- "nomatch_option:$options[nomatch]"
print -r -- "equals_option:$options[equals]"
print -r -- "ls_alias:${aliases[ls]-<unset>}"
print -r -- "l_alias:${aliases[l]-<unset>}"
print -r -- "ll_alias:${aliases[ll]-<unset>}"
print -r -- "la_alias:${aliases[la]-<unset>}"
print -r -- "lsa_alias:${aliases[lsa]-<unset>}"
print -r -- "ssh_alias:${aliases[ssh]-<unset>}"
print -r -- "git_alias:${aliases[g]-<unset>}"
'''
    result = run(['/bin/zsh', mode, script], home, env)
    check('====' in result.stdout, f'{mode}: echo ==== was changed')
    check('nomatch*.none\n' in result.stdout,
          f'{mode}: unmatched glob did not pass through literally')
    check(str(home/'docs/result.md') in result.stdout,
          f'{mode}: grep did not process the bash-style include glob')
    check('no matches found' not in result.stderr and '= not found' not in result.stderr,
          f'{mode}: zsh emitted its original expansion error: {result.stderr}')
    check('nomatch_option:off' in result.stdout, f'{mode}: NOMATCH stayed enabled')
    check('equals_option:off' in result.stdout, f'{mode}: EQUALS stayed enabled')
    check('ls_alias:<unset>' in result.stdout,
          f'{mode}: agent shell retained an ls alias')
    if mode == '-ic':
        for key in ['ls_alias', 'l_alias', 'll_alias', 'la_alias', 'lsa_alias', 'ssh_alias']:
            check(f'{key}:<unset>' in result.stdout,
                  f'{mode}: agent shell retained {key}: {result.stdout}')
        check('git_alias:git' in result.stdout,
              f'{mode}: harmless git alias was removed')


def check_non_agent_behavior(home):
    env = shell_environment(home)
    script = '''\\
print -r -- "nomatch_option:$options[nomatch]"
print -r -- "equals_option:$options[equals]"
print -r -- "ls_alias:${aliases[ls]-<unset>}"
print -r -- "l_alias:${aliases[l]-<unset>}"
print -r -- "ssh_alias:${aliases[ssh]-<unset>}"
'''
    result = run(['/bin/zsh', '-ic', script], home, env)
    check('nomatch_option:on' in result.stdout, 'ordinary interactive NOMATCH changed')
    check('equals_option:on' in result.stdout, 'ordinary interactive EQUALS changed')
    check('ls_alias:eza --color=always --icons=always' in result.stdout,
          'ordinary interactive ls alias changed')
    check('l_alias:ls -lah' in result.stdout, 'ordinary interactive ls shortcuts changed')
    check('ssh_alias:kitten ssh' in result.stdout, 'ordinary Kitty ssh alias changed')

    failed_glob = run(['/bin/zsh', '-lc', 'ls *.none'], home, env, ok=False)
    check('no matches found' in failed_glob.stderr,
          'ordinary login shell no longer rejects an unmatched glob')


def main():
    with tempfile.TemporaryDirectory(prefix='shdots-agent-shell-') as temp:
        audit = Path(temp)
        home = audit/'home'
        home.mkdir()
        render(audit, home)
        make_scratch_commands(home)
        check_agent_commands(home, '-lc', {'CODEX_THREAD_ID': 'test-thread'})
        check_agent_commands(home, '-ic', {
            'CLAUDECODE': '1',
            'AI_AGENT': 'claude-code_test_agent',
        })
        check_non_agent_behavior(home)
    print('PASS: agent zsh startup, aliases, baseline note renders, and ordinary-shell defaults.')


if __name__ == '__main__':
    main()
