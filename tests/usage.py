"""Scratch-only checks for chezmoi-usage.

A throwaway HOME holds a minimal source tree, zsh history, and Claude/Codex
logs; the real ones are never read. No mise or brew on PATH, so casks are
'unknown' and mise tools match by name.
"""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

from platform_stabilization import check, environment

ROOT = Path(__file__).resolve().parents[1]
USAGE = ROOT/'dot_local/bin/executable_chezmoi-usage'

tmp = Path(tempfile.mkdtemp(prefix='shdots-usage-'))
home, src = tmp/'home', tmp/'src'
now = int(time.time())
recent, old = now - 86400, now - 200*86400


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def iso(ts):
    return time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime(ts))


write(src/'Brewfile.tmpl', 'brew "gnupg"\nbrew "MisterTea/et/et"  # comment\ncask "zulu@17"\n')
write(src/'dot_zshrc.tmpl', "alias gst='git status'\nalias gcp='git cherry-pick'\nalias n='nvim'\n"
      "alias -g ...='../..'\nalias -- -='cd -'\n")
write(src/'dot_local/bin/executable_chezmoi-health', '')
write(src/'dot_local/bin/executable_old-helper.tmpl', '')
for skill in ('pr', 'grilling', 'research', 'wizard'):
    (src/'dot_agents/skills'/skill).mkdir(parents=True)
(src/'dot_claude/skills/eod').mkdir(parents=True)
write(src/'run_onchange_after_40-claude-mcp-sync.sh.tmpl',
      'add context7 -- npx\nadd citra -- npx\n[ -x "$CBM_BIN" ] && add codebase-memory-mcp -- "$CBM_BIN"\n')
write(src/'private_dot_ssh/config.tmpl', 'Host *\nHost linux-compat\nHost fdx-host as-host\n')
write(src/'.usage-keep', 'keep brew:gnupg  verifies signatures\nexe mise:ripgrep rg\n'
      'exe mise:neovim nvim\nkeep mise:retired-tool  gone\n')
write(home/'.config/mise/config.toml', '[settings]\n# see [tools] below\nlockfile = false\n\n'
      '[tools]\neza = "1"\nripgrep = "1"\nbat = "1"\njq = "1"\nfd = "1"\nneovim = "1"\n'
      '"npm:@scope/thing" = "1"\n')

write(home/'.zsh_history', '\n'.join([
    f': {recent}:0;FOO=1 sudo eza -la | rg needle',
    f': {recent}:0;gst',
    f': {recent}:0;-',
    f': {recent}:0;cd ...',
    f': {recent}:0;ssh as@fdx-host',
    f': {recent}:0;echo multi \\',
    'et somewhere',
    f': {old}:0;bat README.md',
    f': {old}:0;gcp abc',
]) + '\n')


def tool_use(name, payload):
    return {'timestamp': iso(recent), 'message': {'content': [
        {'type': 'tool_use', 'id': 'toolu_1', 'name': name, 'input': payload}]}}


claude = [
    tool_use('Bash', {'command': 'cat x.json | jq ".a \\"b\\""'}),
    tool_use('Skill', {'skill': 'pr'}),
    tool_use('mcp__context7__query-docs', {}),
    {'timestamp': iso(recent), 'message': {'content': '<command-name>/grilling</command-name>'}},
    # A deferred-tool listing names a server without calling it.
    {'timestamp': iso(recent), 'attachment': 'mcp__citra__read mcp__citra__search'},
]
write(home/'.claude/projects/p/s.jsonl', '\n'.join(json.dumps(r, separators=(',', ':')) for r in claude) + '\n')

codex = [
    {'timestamp': iso(recent), 'type': 'event_msg', 'payload': {'type': 'item_completed', 'item': {
        'type': 'McpToolCall', 'id': 'exec-1', 'server': 'codebase-memory-mcp'}}},
    {'timestamp': iso(recent), 'type': 'response_item', 'payload': {
        'type': 'function_call', 'name': 'exec_command', 'arguments': json.dumps({'cmd': 'fd -e py'})}},
    {'timestamp': iso(recent), 'type': 'response_item', 'payload': {
        'type': 'custom_tool_call', 'name': 'js', 'input': 'read("/h/.agents/skills/research/SKILL.md")'}},
    # The skill listing in a developer message is not a read.
    {'timestamp': iso(recent), 'type': 'response_item', 'payload': {
        'type': 'message', 'content': '/h/.agents/skills/wizard/SKILL.md'}},
]
write(home/'.codex/sessions/2026/r.jsonl', '\n'.join(json.dumps(r, separators=(',', ':')) for r in codex) + '\n')

env = environment(home) | {'HISTFILE': str(home/'.zsh_history')}


def usage(*args):
    result = subprocess.run([sys.executable, str(USAGE), '--source', str(src), *args],
                            env=env, text=True, capture_output=True)
    check(result.returncode == 0, f'exit {result.returncode}\n{result.stderr}')
    rows = {}
    for line in result.stdout.splitlines():
        if line.startswith(('#', 'STATUS', 'no unused')):
            continue
        status, kind, name, last = line.split()[:4]
        rows[f'{kind}:{name}'] = (status, last)
    return rows, result


rows, result = usage()
status = {k: v[0] for k, v in rows.items()}
check('lockfile' not in ' '.join(status), f'[settings] key read as a tool: {status}')
check('stale rule in .usage-keep: keep mise:retired-tool' in result.stderr, result.stderr)
check('Claude logs' in result.stdout and 'cover less than the window' in result.stdout, result.stdout)

expected = {
    'mise:eza': 'used', 'mise:ripgrep': 'used', 'alias:gst': 'used', 'alias:-': 'used',
    'alias:...': 'used', 'ssh:fdx-host': 'used', 'brew:et': 'used',
    'mise:jq': 'used', 'skill:pr': 'used', 'skill:grilling': 'used', 'mcp:context7': 'used',
    'mcp:codebase-memory-mcp': 'used', 'mise:fd': 'used', 'skill:research': 'used',
    'mise:bat': 'unused', 'alias:gcp': 'unused', 'mcp:citra': 'unused', 'skill:wizard': 'unused',
    'skill:eod': 'unused', 'ssh:linux-compat': 'unused', 'bin:old-helper': 'unused',
    'mise:neovim': 'unused', 'mise:npm:@scope/thing': 'unused', 'alias:n': 'unused',
    'brew:gnupg': 'kept', 'cask:zulu@17': 'unknown',
}
wrong = {k: (status.get(k), v) for k, v in expected.items() if status.get(k) != v}
check(not wrong, f'(actual, expected): {wrong}')
check(rows['mise:bat'][1] != 'never', 'old use lost its last-used date')
print('PASS: history, agent shell commands, skills, MCP calls and SSH hosts are credited')
print('PASS: listings and out-of-window use do not count; keep rules and stale rules apply')

rows, _ = usage('--days', '365')
check(rows['mise:bat'][0] == 'used', 'a wider window should include the old use')
print('PASS: --days widens the window')

rows, _ = usage('--unused')
check({s for s, _ in rows.values()} == {'unused'}, f'--unused shows more: {rows}')
print('PASS: --unused lists only removal candidates')

# `n` runs nvim: using the alias credits the tool behind it.
with (home/'.zsh_history').open('a') as f:
    f.write(f': {recent}:0;n notes.md\n')
rows, _ = usage()
check(rows['alias:n'][0] == 'used' and rows['mise:neovim'][0] == 'used', f'alias target: {rows}')
print('PASS: an alias credits its target command')

shutil.rmtree(tmp)
