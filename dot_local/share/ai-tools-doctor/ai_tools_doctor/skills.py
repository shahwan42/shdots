"""Skill discovery: names, roots and resolved symlink targets; adapters vs conflicts."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

from .context import Context
from .model import result
from .redact import tilde

GLOBAL_ROOTS = {
    "canonical": ".agents/skills", "claude": ".claude/skills",
    "opencode": ".config/opencode/skills", "codex": ".codex/skills",
}
PROJECT_ROOTS = {"project-agents": ".agents/skills", "project-claude": ".claude/skills"}


def holds_skills(directory: Path, depth: int) -> bool:
    """True when a SKILL.md exists within `depth` levels below (an app-managed container, e.g. synced/)."""
    if depth == 0:
        return False
    try:
        children = [c for c in directory.iterdir() if c.is_dir() and not c.name.startswith(".")]
    except OSError:
        return False
    return any((c / "SKILL.md").is_file() or holds_skills(c, depth - 1) for c in children)


def scan_root(label: str, root: Path) -> list[dict]:
    entries = []
    if not root.is_dir():
        return entries
    for entry in sorted(root.iterdir()):
        if entry.name.startswith("."):
            continue
        real = Path(os.path.realpath(entry))
        skill_file = real / "SKILL.md"
        digest = None
        if skill_file.is_file():
            digest = hashlib.sha256(skill_file.read_bytes()).hexdigest()[:16]
        container = real.is_dir() and not skill_file.is_file() and holds_skills(real, depth=3)
        entries.append({"name": entry.name, "root": label, "path": str(entry), "symlink": entry.is_symlink(),
                        "container": container,
                        "resolved": str(real), "broken": not real.exists(), "has_skill_md": skill_file.is_file(),
                        "digest": digest})
    return entries


def analyze(ctx: Context) -> tuple[list[dict], dict]:
    roots = {label: Path(ctx.home) / rel for label, rel in GLOBAL_ROOTS.items()}
    project = Path(ctx.project)
    if str(project) != ctx.home:
        roots |= {label: project / rel for label, rel in PROJECT_ROOTS.items()}
    entries = [e for label, root in roots.items() for e in scan_root(label, root)]
    containers = [e for e in entries if e["container"]]
    entries = [e for e in entries if not e["container"]]
    by_name: dict[str, list[dict]] = {}
    for entry in entries:
        by_name.setdefault(entry["name"], []).append(entry)
    rows, summary = [], {"roots": {k: tilde(str(v), ctx.home) for k, v in roots.items() if v.is_dir()},
                         "skills": len(by_name), "adapters": 0, "duplicates": 0, "conflicts": 0, "broken": 0,
                         "containers_not_enumerated": [tilde(e["path"], ctx.home) for e in containers]}
    prov = "filesystem scan of skill roots"
    for name, group in sorted(by_name.items()):
        broken = [e for e in group if e["broken"] or not e["has_skill_md"]]
        for e in broken:
            summary["broken"] += 1
            rows.append(result(client="all", check=f"skill {name}", layer="skills", outcome="failed",
                               detail=f"{tilde(e['path'], ctx.home)} ({e['root']}) is "
                                      f"{'a broken symlink' if e['broken'] else 'missing SKILL.md'}.",
                               next_action="Remove the dangling adapter or restore its target via chezmoi apply.",
                               provenance=prov))
        good = [e for e in group if e not in broken]
        targets = {e["resolved"] for e in good}
        digests = {e["digest"] for e in good}
        if len(good) > 1 and len(targets) == 1:
            summary["adapters"] += 1
        elif len(good) > 1 and len(digests) == 1:
            summary["duplicates"] += 1
        elif len(digests) > 1:
            summary["conflicts"] += 1
            where = ", ".join(f"{e['root']}={e['digest']}" for e in good)
            project_shadow = any(e["root"].startswith("project") for e in good) \
                and any(not e["root"].startswith("project") for e in good)
            rows.append(result(client="all", check=f"skill {name}", layer="skills", outcome="failed",
                               detail=f"Same-named skill has different content across roots ({where})."
                                      + (" A global copy shadows the project skill in Claude and OpenCode."
                                         if project_shadow else ""),
                               next_action="Rename or remove one implementation; owner is the repo that ships it "
                                           "(dotfiles dot_agents/skills or the project .agents/skills).",
                               provenance=prov))
    rows.append(result(client="all", check="skill discovery", layer="skills",
                       outcome="passed" if not (summary["conflicts"] or summary["broken"]) else "failed",
                       detail=f"{summary['skills']} skills; {summary['adapters']} adapter groups to one canonical file, "
                              f"{summary['duplicates']} identical copies, {summary['conflicts']} conflicts, "
                              f"{summary['broken']} broken, {len(containers)} nested containers not enumerated. "
                              "Plugin-provided skills are not enumerated (unverified).",
                       next_action="" if not (summary["conflicts"] or summary["broken"]) else "See skill rows above.",
                       provenance=prov))
    return rows, summary
