"""Real stat, glob and symlink regression checks; all writes stay in scratch."""
from pathlib import Path
import subprocess

from platform_stabilization import check, command, environment


def audit_for_other_account(audit):
    # Keep the installed compaudit implementation, changing only the accepted
    # process owner. This exercises shared-install findings without sudo/chown.
    result = subprocess.run(['/bin/zsh', '-f', '-c',
                             'autoload -Uz compaudit; autoload +X compaudit; '
                             'print -r -- $functions[compaudit]'],
                            text=True, capture_output=True, check=True)
    check('u0u${EUID}' in result.stdout, 'compaudit owner seam changed')
    file = audit/'other-account-compaudit.zsh'
    file.write_text('compaudit() {\n' + result.stdout.replace(
        'u0u${EUID}', 'u0u${_test_audit_uid}') + '\n}\n')
    return file


def verify_compinit_paths(rendered, audit):
    fixture = audit/'completion-filesystem'
    fixture.mkdir()
    prefix = fixture/'brew'
    site = prefix/'share/zsh/site-functions'
    site.mkdir(parents=True)
    (prefix/'bin').mkdir()
    (prefix/'bin/brew').write_text('#!/bin/sh\nexit 0\n')
    (prefix/'bin/brew').chmod(0o755)
    apps = fixture/'Applications'
    target = apps/'Example.app/Contents/Resources/zsh/site-functions/_example'
    target.parent.mkdir(parents=True)
    target.write_text('#compdef example\n')
    for directory in [fixture, prefix, *prefix.rglob('*'), apps, *apps.rglob('*')]:
        if directory.is_dir():
            directory.chmod(0o755)
    target.chmod(0o644)
    (site/'_app').symlink_to(target)
    (site/'_broken').symlink_to(apps/'Missing.app/_missing')
    for label, relative in [('tmp', 'tmp/_outside'),
                            ('work-home', 'Users/work/_outside'),
                            ('brew-home', 'Users/maintainer/_outside'),
                            ('other-prefix', 'other-brew/_outside'),
                            ('non-bundle', 'Applications/plain/_outside')]:
        outside = fixture/relative
        outside.parent.mkdir(parents=True, exist_ok=True)
        outside.write_text('#compdef outside\n')
        (site/('_'+label)).symlink_to(outside)
    (fixture/'ordinary').write_text('#compdef outside\n')
    (fixture/'secure').mkdir()
    (fixture/'insecure').mkdir()
    (fixture/'insecure').chmod(0o777)
    (fixture/'empty-parent').mkdir()
    (fixture/'outside-link').symlink_to(target)
    (site/'_root-target').symlink_to('/usr/bin/true')
    # Only relocate the fixed Applications root in this test copy. Production
    # has no configurable application allowlist. Resolution and stat stay real.
    source = rendered/'.config/zsh/functions/shdots-compinit.zsh'
    relocated = audit/'fixture-compinit.zsh'
    relocated.write_text(source.read_text().replace('/Applications', str(apps.resolve())))
    other_audit = audit_for_other_account(audit)
    script = Path(__file__).with_suffix('.zsh')
    command(['/bin/zsh', '-f', str(script), str(relocated), str(fixture),
             str(other_audit), str(source)], environment(audit), audit,
            audit/'compinit-filesystem.txt')
