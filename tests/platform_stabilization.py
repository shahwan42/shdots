"""Scratch-only shell and mocked installer regression checks for native accounts."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def command(args, env, cwd, log, ok=True):
    result = subprocess.run(args, env=env, cwd=cwd, text=True, capture_output=True)
    log.write_text(result.stdout + result.stderr)
    check((result.returncode == 0) == ok,
          f'{args}: unexpected exit {result.returncode}\n{result.stdout}{result.stderr}')
    return result.stdout


def executable(path, contents):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents)
    path.chmod(0o755)


def environment(home):
    # No inherited authentication, mise state, user shell config or project config.
    return dict(HOME=str(home), ZDOTDIR=str(home), PATH='/usr/bin:/bin:/usr/sbin:/sbin',
                XDG_CONFIG_HOME=str(home/'.config'), XDG_DATA_HOME=str(home/'.local/share'),
                XDG_CACHE_HOME=str(home/'.cache'), XDG_STATE_HOME=str(home/'.local/state'),
                TERM='dumb', SHELL='/bin/zsh', LC_ALL='C')


def verify_compinit(rendered, audit):
    # Mock compaudit's findings and zstat ownership, without chown or other users'
    # homes. Exercise the actual rendered policy and capture compinit's arguments.
    script = r'''
source "$1"
HOMEBREW_PREFIX=/opt/homebrew
compaudit() { [[ -n $finding ]] && print -r -- "$finding"; return 1; }
compinit() { print -r -- "compinit:$*"; }
zstat() {
  [[ $4 == /opt/homebrew ]] && { _stat=(uid 501); return 0; }
  [[ $4 == /unexpected ]] && { _stat=(uid 777); return 0; }
  [[ $owner == missing ]] && return 1
  _stat=(uid $owner)
}
case_check() {
  local finding=$1 owner=$2 expected=$3 actual
  actual=$(_shdots_compinit)
  [[ $actual == "compinit:$expected" ]] || {
    print -u2 -r -- "finding=$finding owner=$owner expected=$expected actual=$actual"
    return 1
  }
  print -r -- "PASS: finding=$finding owner=$owner args=$expected"
}
case_check /root-owned 0 -u || exit 1
case_check /opt/homebrew/share/zsh 501 -u || exit 1
case_check /opt/homebrew/share/zsh 502 '' || exit 1
case_check /outside-homebrew 501 '' || exit 1
case_check /opt/homebrew/share/zsh missing '' || exit 1
case_check $'/opt/homebrew/share/zsh\n/unexpected' 501 '' || exit 1
case_check '' 501 '' || exit 1
# Resolved paths must stay inside the prefix, even through a symlink.
case_check "$2/escape" 501 '' || exit 1
unset HOMEBREW_PREFIX
case_check /opt/homebrew/share/zsh 501 '' || exit 1
'''
    (audit/'escape').unlink(missing_ok=True)
    (audit/'escape').symlink_to('/usr/share')
    scriptfile = audit/'compinit-tests.zsh'
    scriptfile.write_text(script)
    command(['/bin/zsh', '-f', str(scriptfile),
             str(rendered/'.config/zsh/functions/shdots-compinit.zsh'), str(audit)],
            environment(audit), audit, audit/'compinit.txt')


def verify_path(label, entries, audit):
    home = audit/'shell-home'
    if home.exists():
        shutil.rmtree(home)
    home.mkdir()
    for name in ['.zshenv', '.zprofile', '.zshrc', '.config/zsh/env.zsh',
                 '.config/zsh/functions/shdots-compinit.zsh']:
        dest = home/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(entries[name]['contents'])
    localbin = home/'.local/bin'
    localbin.mkdir(parents=True)
    shims = home/'.local/share/mise/shims'
    shims.mkdir(parents=True)
    project = home/'project-tools'
    project.mkdir()
    # Suppress unrelated tool integrations. Simulate mise's real tool prepend.
    for tool in ['wt', 'zoxide', 'starship', 'fzf']:
        executable(localbin/tool, '#!/bin/sh\nexit 0\n')
    executable(localbin/'mise', '#!/bin/sh\necho \'path=("$HOME/project-tools" $path)\'\n')
    env = environment(home)
    query = r'''
for tool in git brew php composer ls sed awk xcrun; do
  print -r -- "$tool=$(whence -p $tool)"
done
print -r -- "PATH=$PATH"
print -r -- "GH_HOST=${GH_HOST:-}"
'''
    resolutions = {}
    for mode in ['-lc', '-lic', '-ic', '-c']:
        output = command(['/bin/zsh', mode, query], env, home,
                         audit/('path-'+mode.lstrip('-')+'.txt'))
        values = dict(line.split('=', 1) for line in output.splitlines() if '=' in line)
        for tool in ['git', 'brew', 'php', 'composer']:
            check(values[tool] == '/opt/homebrew/bin/'+tool,
                  f'{label} {mode}: {tool} resolves to {values[tool]}')
        for tool in ['ls', 'sed', 'awk', 'xcrun']:
            check(values[tool].startswith(('/usr/bin/', '/bin/')),
                  f'{label} {mode}: missing system tool {tool}')
        paths = values['PATH'].split(':')
        check(len(paths) == len(set(paths)), f'{label} {mode}: duplicate PATH entries')
        check(paths.index(str(shims)) < paths.index(str(localbin)) <
              paths.index('/opt/homebrew/bin') < paths.index('/usr/bin'),
              f'{label} {mode}: incorrect PATH precedence: {paths}')
        check(values['GH_HOST'] == ('github.foodics.com' if label == 'work' else ''),
              f'{label}: incorrect CLI host')
        resolutions[mode] = values
    # Project tools win over user executables; user executables win over brew.
    executable(project/'php', '#!/bin/sh\nexit 0\n')
    executable(localbin/'git', '#!/bin/sh\nexit 0\n')
    executable(shims/'git', '#!/bin/sh\nexit 0\n')
    output = command(['/bin/zsh', '-lic', query], env, home, audit/'path-overrides.txt')
    values = dict(line.split('=', 1) for line in output.splitlines() if '=' in line)
    check(values['php'] == str(project/'php'), f'{label}: project runtime lost precedence')
    check(values['git'] == str(shims/'git'), f'{label}: mise shim lost precedence')
    (shims/'git').unlink()
    output = command(['/bin/zsh', '-lic', query], env, home, audit/'path-user-local.txt')
    check('git='+str(localbin/'git') in output, f'{label}: local binary lost precedence')
    (audit/'path-resolutions.json').write_text(json.dumps(resolutions, indent=2)+'\n')


def verify_karabiner(entries, cz, audit):
    targets = ['.config/karabiner', '.config/karabiner/assets',
               '.config/karabiner/assets/complex_modifications']
    for name in targets:
        check(entries[name]['perm'] == 0o700, f'{name}: expected private directory')
    # Apply only these targets to a separate scratch destination/state. Never
    # execute bootstrap scripts, download externals or activate karabiner.json.
    dest = audit/'karabiner-home'
    (dest/'.config').mkdir(parents=True, exist_ok=True)
    isolated = ['--destination', str(dest), '--persistent-state', str(audit/'karabiner-state.boltdb')]
    absolute_targets = [str(dest/name) for name in targets]
    cz(*isolated, 'apply', '--include=dirs,files', *absolute_targets)
    for name in targets:
        check((dest/name).stat().st_mode & 0o777 == 0o700, f'{name}: applied mode mismatch')
    check(cz(*isolated, 'diff', '--include=dirs,files', *absolute_targets).stdout == '',
          'Karabiner scratch state did not converge')
    check(not (dest/'.config/karabiner/karabiner.json').exists(), 'Karabiner activated')


def verify_profile(label, entries, rendered, audit, cz):
    verify_compinit(rendered, audit)
    verify_path(label, entries, audit)
    verify_karabiner(entries, cz, audit)
    check('.local/bin/install.sh' not in entries, 'stray installer is managed')


def verify_bootstrap(root, artifacts):
    audit = artifacts/'cbm-bootstrap'
    if audit.exists():
        shutil.rmtree(audit)
    audit.mkdir()
    fixture = audit/'codebase-memory-mcp'
    executable(fixture, '''#!/bin/sh
if [ "$1" = --version ]; then
  echo "codebase-memory-mcp ${CANDIDATE_VERSION:-0.11.0}"
  exit 0
fi
printf '%s\\n' "$*" >> "$HOME/install-calls"
echo '# unwanted installer PATH append' >> "$HOME/.zshrc"
[ "${INSTALL_FAIL:-false}" = false ] || exit 9
mkdir -p "$HOME/.local/bin"
cp "$0" "$HOME/.local/bin/codebase-memory-mcp"
chmod 755 "$HOME/.local/bin/codebase-memory-mcp"
''')
    archive = audit/'fixture.tar.gz'
    with tarfile.open(archive, 'w:gz') as tar:
        tar.add(fixture, arcname='codebase-memory-mcp')
    mocks = audit/'mocks'
    mocks.mkdir()
    executable(mocks/'uname', '#!/bin/sh\n[ "$1" = -s ] && echo "${TEST_OS:-Darwin}" || echo "${TEST_ARCH:-arm64}"\n')
    executable(mocks/'curl', '''#!/bin/sh
echo "$*" >> "$HOME/download-calls"
[ "${DOWNLOAD_FAIL:-false}" = false ] || exit 22
while [ "$1" != -o ]; do shift; done
cp "$FIXTURE_ARCHIVE" "$2"
''')
    # Success fixtures mock the known release digest; the real release archive
    # is independently verified during review. Corruption must fail closed.
    for tool in ['sha256sum', 'shasum']:
        executable(mocks/tool, '#!/bin/sh\necho "$TEST_DIGEST  fixture.tar.gz"\n')
    for tool in ['codesign', 'xattr']:
        executable(mocks/tool, '#!/bin/sh\nexit 0\n')
    executable(mocks/'sysctl', '#!/bin/sh\necho "${TEST_ROSETTA:-0}"\n')
    helper = root/'.chezmoitemplates/codebase-memory-install.sh'
    runner = audit/'run.sh'
    runner.write_text('. "'+str(helper)+'"\nif install_codebase_memory; then exit 0; else exit 1; fi\n')
    digests = {
        'darwin-arm64': '4dee7f38b63740e6751d7a7ed7eb10291c1f2a3ea2415f599dc68370ca0a2d18',
        'darwin-amd64': 'dbf1c73bfcbde64e7dde4cd1320da7afc02e2c972ee1789ae039521411f5132e',
        'linux-arm64-portable': 'd62eeb224d5ee3eba3070938ec62cf1033f10b041ec1c4b2fb67f7aef390cc7b',
        'linux-amd64-portable': '1f9e8293eb2bc5c05cfa27a7e8fc033da6d729ffad525ccfcdaa3fd606306683',
    }
    cases = [
        ('fresh', {}, True, False, 'darwin-arm64'),
        ('existing-rc', {}, True, True, 'darwin-arm64'),
        ('checksum-failure', {'TEST_DIGEST': 'bad-digest'}, False, True, 'darwin-arm64'),
        ('download-failure', {'DOWNLOAD_FAIL': 'true'}, False, True, 'darwin-arm64'),
        ('install-failure', {'INSTALL_FAIL': 'true'}, False, True, 'darwin-arm64'),
        ('install-failure-no-rc', {'INSTALL_FAIL': 'true'}, False, False, 'darwin-arm64'),
        ('wrong-version', {'CANDIDATE_VERSION': '0.12.0'}, False, True, 'darwin-arm64'),
        ('intel', {'TEST_ARCH': 'x86_64'}, True, False, 'darwin-amd64'),
        ('rosetta', {'TEST_ARCH': 'x86_64', 'TEST_ROSETTA': '1'}, True, False, 'darwin-arm64'),
        ('linux-arm64', {'TEST_OS': 'Linux'}, True, False, 'linux-arm64-portable'),
        ('linux-amd64', {'TEST_OS': 'Linux', 'TEST_ARCH': 'x86_64'}, True, False, 'linux-amd64-portable'),
        ('unsupported', {'TEST_ARCH': 'sparc'}, False, False, 'darwin-arm64'),
    ]
    for label, extra, ok, rc_exists, platform in cases:
        home = audit/label
        home.mkdir()
        temp = home/'tmp'
        temp.mkdir()
        env = environment(home)
        env.update(PATH=str(mocks)+':/usr/bin:/bin', TMPDIR=str(temp),
                   FIXTURE_ARCHIVE=str(archive), TEST_DIGEST=digests[platform])
        env.update(extra)
        rc = home/'.zshrc'
        original = '# original managed shell\n'
        if rc_exists:
            rc.write_text(original)
            rc.chmod(0o640)
        command(['/bin/sh', str(runner)], env, home, home/'result.txt', ok=ok)
        check(not list(temp.iterdir()), f'{label}: temporary files leaked')
        check(not (home/'.local/bin/install.sh').exists(), f'{label}: installer leaked')
        check(rc.read_text() == original if rc_exists else not rc.exists(),
              f'{label}: shell configuration drift')
        if rc_exists:
            check(rc.stat().st_mode & 0o777 == 0o640, f'{label}: shell mode drift')
        if ok:
            download = (home/'download-calls').read_text()
            check('/releases/download/v0.11.0/codebase-memory-mcp-'+platform+'.tar.gz' in download,
                  f'{label}: unpinned/wrong download')
            check('--skip-config' in (home/'install-calls').read_text(), f'{label}: client mutation')
            calls = (download, (home/'install-calls').read_text())
            command(['/bin/sh', str(runner)], env, home, home/'retry.txt')
            check(calls == ((home/'download-calls').read_text(), (home/'install-calls').read_text()),
                  f'{label}: repeat install was not idempotent')
        elif label in ['checksum-failure', 'download-failure', 'wrong-version', 'unsupported']:
            check(not (home/'install-calls').exists(), f'{label}: unsafe candidate executed')
    print('PASS: bootstrap pin, platform selection, integrity rejection, idempotency, temp cleanup and shell preservation.')
