"""Scratch-only regression checks for chezmoi-autoupdate's apply gates.

Builds a throwaway origin and source clone with SSH-signed commits, renders the
real updater with auto_update=true, and runs it against an empty scratch home.
Nothing outside the temp dir is read or written; no real source is fetched.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from platform_stabilization import check, environment

ROOT = Path(__file__).resolve().parents[1]
CHEZMOI = shutil.which('chezmoi') or str(Path.home()/'.local/bin/chezmoi')
GOOD_ZSHRC = 'export SHDOTS_AUTOUPDATE_TEST={}\n'

tmp = Path(tempfile.mkdtemp(prefix='shdots-autoupdate-'))
home = tmp/'home'
src = home/'.local/share/chezmoi'
origin = tmp/'origin.git'
env = environment(home) | {'TMPDIR': str(tmp/'t')}
(tmp/'t').mkdir()


def run(args, cwd=None, ok=True):
    result = subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=True)
    check((result.returncode == 0) == ok, f'{args}: exit {result.returncode}\n{result.stdout}{result.stderr}')
    return result.stdout.strip()


def git(*args, cwd=src, ok=True):
    return run(['git', *args], cwd=cwd, ok=ok)


def push_commit(path, contents, message, signed=True, branch='main'):
    work = tmp/'work'
    (work/path).parent.mkdir(parents=True, exist_ok=True)
    (work/path).write_text(contents)
    git('add', '-A', cwd=work)
    git('commit', '-q', '-S' if signed else '--no-gpg-sign', '-m', message, cwd=work)
    git('push', '-q', 'origin', f'HEAD:{branch}', cwd=work)


def autoupdate():
    result = subprocess.run(['sh', str(updater)], env=env, text=True, capture_output=True)
    check(result.returncode == 0, f'autoupdate exited {result.returncode}\n{result.stdout}{result.stderr}')
    marker = home/'.cache/chezmoi-stale'
    return marker.read_text().strip() if marker.exists() else ''


# Identity: one SSH signing key, trusted through allowed_signers.
(home/'.ssh').mkdir(parents=True)
key = home/'.ssh/test_signing'
run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', 'test', '-f', str(key)])
(home/'allowed_signers').write_text(f'test@example.com {(key.with_suffix(".pub")).read_text()}')
for k, v in {'user.name': 'Test', 'user.email': 'test@example.com', 'gpg.format': 'ssh',
             'user.signingkey': str(key), 'gpg.ssh.allowedSignersFile': str(home/'allowed_signers'),
             'init.defaultBranch': 'main'}.items():
    run(['git', 'config', '--global', k, v])

# chezmoi: scratch config and binary; the updater finds both through $HOME.
(home/'.local/bin').mkdir(parents=True)
(home/'.local/bin/chezmoi').symlink_to(CHEZMOI)
(home/'.config/chezmoi').mkdir(parents=True)
(home/'.config/chezmoi/chezmoi.toml').write_text(f'sourceDir = {json.dumps(str(src))}\n[data]\nkind = "vm"\nrole = "personal"\n')

# Origin with one signed commit; the source clone is applied and converged.
git('init', '-q', '--bare', str(origin), cwd=tmp)
git('clone', '-q', str(origin), str(tmp/'work'), cwd=tmp)
push_commit('dot_zshrc.tmpl', GOOD_ZSHRC.format(1), 'initial')
git('clone', '-q', str(origin), str(src), cwd=tmp)
run([CHEZMOI, 'apply', '--no-tty'])

updater = tmp/'chezmoi-autoupdate'
updater.write_text(run([CHEZMOI, '--source', str(ROOT), 'execute-template', '--override-data',
                        json.dumps({'kind': 'vm', 'role': 'personal', 'auto_update': True}),
                        '--file', str(ROOT/'dot_local/bin/executable_chezmoi-autoupdate.tmpl')]))


def head():
    return git('rev-parse', 'HEAD')


# 1. A signed, valid update fast-forwards and applies.
push_commit('dot_zshrc.tmpl', GOOD_ZSHRC.format(2), 'good update')
marker = autoupdate()
check(marker == '' and head() == git('rev-parse', 'origin/main'), f'good update not applied: {marker!r}')
check((home/'.zshrc').read_text() == GOOD_ZSHRC.format(2), 'good update not rendered')
print('PASS: signed valid update applies')

# 2. A template error on the tip is refused before the clone moves.
before = head()
push_commit('dot_zshrc.tmpl', '{{ .missing.key }}\n', 'broken template')
marker = autoupdate()
check(head() == before and 'pre-apply check' in marker and 'missing' in marker, f'broken template not refused: {marker!r}')
check((home/'.zshrc').read_text() == GOOD_ZSHRC.format(2), 'broken template touched $HOME')
print('PASS: template error refused, $HOME untouched')

# 3. A zsh syntax error is refused too.
push_commit('dot_zshrc.tmpl', 'if [[ ; then\n', 'broken zsh')
marker = autoupdate()
check(head() == before and 'pre-apply check' in marker and '.zshrc' in marker, f'zsh syntax error not refused: {marker!r}')
print('PASS: zsh syntax error refused')

# 4. An unsigned commit behind a signed tip is refused.
push_commit('dot_zshrc.tmpl', GOOD_ZSHRC.format(3), 'unsigned', signed=False)
push_commit('dot_zshrc.tmpl', GOOD_ZSHRC.format(4), 'signed tip')
marker = autoupdate()
check(head() == before and 'not signed by a trusted key' in marker, f'unsigned commit not refused: {marker!r}')
print('PASS: unsigned commit in range refused')

# 5. A checkout on another branch is never auto-applied.
git('switch', '-q', '-c', 'feature')
marker = autoupdate()
check(head() == before and "on 'feature', not main" in marker, f'feature branch not skipped: {marker!r}')
print('PASS: non-main checkout skipped')

check(not any((tmp/'t').iterdir()), f'temp files left behind: {list((tmp/"t").iterdir())}')
print('PASS: no temp files left behind')
shutil.rmtree(tmp)
