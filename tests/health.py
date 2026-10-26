"""Scratch-only checks for chezmoi-health's open-problem tracking.

Runs the source script against a throwaway XDG_STATE_HOME; the real log is
never read or written.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile

from platform_stabilization import check, environment

ROOT = Path(__file__).resolve().parents[1]
HEALTH = ROOT/'dot_local/bin/executable_chezmoi-health'

tmp = Path(tempfile.mkdtemp(prefix='shdots-health-'))
env = environment(tmp/'home') | {'XDG_STATE_HOME': str(tmp/'state')}


def health(*args):
    return subprocess.run(['sh', str(HEALTH), *args], env=env, text=True, capture_output=True)


def is_open(expected, why):
    result = health('check')
    check((result.returncode == 1) == expected, f'{why}: check exit {result.returncode}\n{result.stderr}')
    return result.stderr


is_open(False, 'no log yet')
check(health('problems').stdout.strip() == 'no open problems', 'empty log lists problems')

health('run', 'ok')
health('note', '25-brew-bundle', 'brew-bundle', 'fail', 'brew bundle exited non-zero')
message = is_open(True, 'script failure after an ok run')
check('1 open problem' in message and 'fail 25-brew-bundle brew-bundle' in message, f'unexpected nag: {message!r}')
print('PASS: a script failure after an ok sync run is open')

health('note', '25-brew-bundle', 'brew-bundle', 'ok', 'brew bundle succeeded')
is_open(False, 'later ok for the same item')
print('PASS: a later ok for the same script and item closes it')

health('note', '40-claude-mcp-sync', 'citra', 'fail', 'claude mcp add failed')
health('note', '40-claude-mcp-sync', 'context7', 'ok', 'claude mcp add succeeded')
is_open(True, 'ok for a different item')
health('note', '40-claude-mcp-sync', 'citra', 'ok', 'resolved by hand')
health('note', '41-opencode-mcp-sync', 'python', 'skip', 'python3 not available')
health('note', '45-herdr-plugins', 'x', 'ok', 'detail with "status":"fail" inside')
is_open(False, 'skip, manual ok and quoted detail')
print('PASS: other items, skips, manual dismissal and quoted details are handled')

health('run', 'degraded', 'chezmoi init needed')
check('degraded sync -' in health('problems').stdout, 'degraded run not listed')
health('run', 'ok')
is_open(False, 'later ok run')
print('PASS: a non-ok sync run is open until the next ok run')

shown = health('2').stdout.splitlines()
check(len(shown) == 3 and shown[0].startswith('# '), f'count argument ignored: {shown}')
print('PASS: `chezmoi-health <n>` shows n events')

shutil.rmtree(tmp)
