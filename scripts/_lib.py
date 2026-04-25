"""Shared helpers for paperloom scripts.

Imported by sibling scripts. Keeps YAML frontmatter, path resolution, slug
generation, and wikilink handling in one place.
"""

from __future__ import annotations

import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import yaml


FRONTMATTER_RE = re.compile(
    r"\A---\n(?P<fm>.*?)\n---\n?(?P<body>.*)\Z",
    re.DOTALL,
)


def die(msg: str, code: int = 1) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def resolve_vault(raw: str | os.PathLike[str] | None) -> Path:
    """Expand ~, env vars, and resolve to absolute path. Does not require existence."""
    if raw is None or raw == "":
        raw = "~/PaperLoom"
    p = Path(os.path.expandvars(os.path.expanduser(str(raw)))).resolve()
    return p


def require_vault(raw: str | os.PathLike[str] | None) -> Path:
    vault = resolve_vault(raw)
    if not vault.is_dir():
        die(f"vault does not exist: {vault} — run /paperloom:init first")
    if not (vault / "CLAUDE.md").is_file():
        die(f"vault missing CLAUDE.md: {vault} — run /paperloom:init first")
    return vault


def read_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    """Return (frontmatter_dict, body). Empty dict if no frontmatter."""
    text = path.read_text(encoding="utf-8")
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm_raw = m.group("fm")
    body = m.group("body")
    try:
        fm = yaml.safe_load(fm_raw) or {}
    except yaml.YAMLError as e:
        die(f"invalid YAML frontmatter in {path}: {e}")
    if not isinstance(fm, dict):
        die(f"frontmatter is not a mapping in {path}")
    return fm, body


def write_frontmatter(path: Path, fm: dict[str, Any], body: str) -> None:
    """Serialize frontmatter + body back to disk. Preserves wikilink-in-list style."""
    fm_yaml = dump_frontmatter(fm)
    path.write_text(f"---\n{fm_yaml}---\n{body}", encoding="utf-8")


class _WikilinkStr(str):
    """Marker subclass so the YAML dumper knows to double-quote."""


def _wikilink_representer(dumper: yaml.Dumper, data: _WikilinkStr):
    return dumper.represent_scalar("tag:yaml.org,2002:str", str(data), style='"')


yaml.add_representer(_WikilinkStr, _wikilink_representer)


def tag_wikilinks(obj: Any) -> Any:
    """Walk nested structure, mark any '[[...]]' string as needing double quotes."""
    if isinstance(obj, str) and obj.startswith("[[") and obj.endswith("]]"):
        return _WikilinkStr(obj)
    if isinstance(obj, list):
        return [tag_wikilinks(x) for x in obj]
    if isinstance(obj, dict):
        return {k: tag_wikilinks(v) for k, v in obj.items()}
    return obj


def dump_frontmatter(fm: dict[str, Any]) -> str:
    tagged = tag_wikilinks(fm)
    return yaml.dump(tagged, sort_keys=False, allow_unicode=True, default_flow_style=False)


WIKILINK_RE = re.compile(r"\[\[([^\]|#]+?)(?:\|[^\]]+)?(?:#[^\]]+)?\]\]")


def extract_wikilinks(text: str) -> list[str]:
    """All [[slug]] references inside text (body or any frontmatter string)."""
    return WIKILINK_RE.findall(text)


def all_wikilinks_in_file(path: Path) -> set[str]:
    """Every wikilink target in frontmatter values + body."""
    fm, body = read_frontmatter(path)
    seen: set[str] = set()

    def walk(v: Any) -> None:
        if isinstance(v, str):
            seen.update(extract_wikilinks(v))
        elif isinstance(v, list):
            for x in v:
                walk(x)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)

    walk(fm)
    seen.update(extract_wikilinks(body))
    return seen


def wrap_wikilink(slug: str) -> str:
    """'foo' -> '[[foo]]'. Idempotent."""
    s = slug.strip()
    if s.startswith("[[") and s.endswith("]]"):
        return s
    return f"[[{s}]]"


def unwrap_wikilink(s: str) -> str:
    """'[[foo]]' -> 'foo'. Handles '[[foo|display]]' by stripping alias."""
    s = s.strip()
    if s.startswith("[[") and s.endswith("]]"):
        s = s[2:-2]
    return s.split("|", 1)[0].split("#", 1)[0].strip()


_KEBAB_RE = re.compile(r"[^a-z0-9]+")


def kebab(text: str, max_len: int = 60) -> str:
    """Lowercase, ASCII-ish kebab-case. Good enough for slugs."""
    t = text.lower()
    # Common transliterations. Keep minimal — the LLM usually normalizes first.
    t = t.replace("α", "alpha").replace("β", "beta").replace("→", "to")
    t = _KEBAB_RE.sub("-", t).strip("-")
    if len(t) > max_len:
        t = t[:max_len].rstrip("-")
    return t


def today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def now_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def iter_vault_files(vault: Path, subdir: str) -> Iterable[Path]:
    d = vault / subdir
    if not d.is_dir():
        return []
    return sorted(p for p in d.iterdir() if p.is_file() and p.suffix == ".md")


def slug_from_path(path: Path) -> str:
    return path.stem


def yaml_list(items: Iterable[Any]) -> str:
    """Inline flow-style YAML list for simple cases — used by template filling.

    Always returns valid YAML. Empty list -> '[]'. Otherwise a block list.
    """
    items = list(items)
    if not items:
        return "[]"
    tagged = [tag_wikilinks(x) for x in items]
    return "\n" + yaml.dump(tagged, allow_unicode=True, default_flow_style=False).rstrip("\n")


def yaml_scalar(v: Any) -> str:
    """Render a scalar for template substitution (None -> null, strings quoted when needed)."""
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    # If already quoted or clearly safe, keep as-is; else let yaml decide.
    dumped = yaml.dump(s, default_flow_style=True, allow_unicode=True).rstrip("\n")
    # yaml.dump wraps strings with newlines etc. For a scalar it gives 'text\n...'. Strip trailing.
    return dumped.strip()
