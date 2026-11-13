#!/usr/bin/env python3
"""Checks that the shell guard hook blocks the failing forms and allows the working ones."""
import json
from pathlib import Path
import subprocess

HOOK = Path(__file__).resolve().parents[1] / 'dot_local/bin/executable_shell-guard-hook'

BLOCKED = [
    "sed -i 's/a/b/' file",
    "cd x && sed -i -e 's/a/b/' file",
    "rg foo | sed -i 's/a/b/' f",
    "sed -i -e 's/a/b/' file",
    "git rev-parse --short origin/main HEAD",
    "git fetch -q && git rev-parse --verify a b",
]
ALLOWED = [
    "sed -i '' 's/a/b/' file",
    'sed -i "" "s/a/b/" file',
    "sed -n '1,5p' file",
    "sed 's/a/b/' file > out",
    "git rev-parse --short HEAD",
    "git rev-parse origin/main HEAD",
    "git rev-parse --show-toplevel",
    "ls -i file",
    "git commit -m 'avoid sed -i x on macOS'",
    "echo 'sed -i s/a/b/ f' > note.txt",
]


def run(command, tool='Bash'):
    event = {'tool_name': tool, 'tool_input': {'command': command}}
    return subprocess.run(['python3', str(HOOK)], input=json.dumps(event),
                          text=True, capture_output=True)


for command in BLOCKED:
    result = run(command)
    assert result.returncode == 2 and result.stderr.startswith('Blocked:'), (command, result)
for command in ALLOWED:
    result = run(command)
    assert result.returncode == 0 and not result.stderr, (command, result)
assert run("sed -i 's/a/b/' f", tool='Read').returncode == 0
bad = subprocess.run(['python3', str(HOOK)], input='not json', text=True, capture_output=True)
assert bad.returncode == 0
print('shell guard hook ok')
