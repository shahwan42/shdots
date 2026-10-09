**zsh shell note**
- In zsh, use `${VAR}:path` instead of `$VAR:path`; zsh treats the colon as a modifier.
- Run `git rev-parse --short <revision>` once per revision; two revisions fail with `Needed a single revision`.
- BSD `sed -i` needs `sed -i ''`; avoid GNU-only escapes and use a short Python script for multi-line edits.
- Use `/bin/ls` or `command ls` when parsing listings.
- `KSH_ARRAYS` also disables `$VAR:x`, but changes array indexing and expansion globally.
