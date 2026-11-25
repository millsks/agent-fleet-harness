"""Minimal Markdown frontmatter reader and writer (standard library only).

Handles the subset of YAML used by agent and skill files: ``key: value``
scalars, comma-separated lists, inline ``[a, b]`` lists, and ``#`` comments.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

LIST_KEYS = {"tools", "disallowedTools", "skills"}


@dataclass
class Document:
    meta: dict[str, object] = field(default_factory=dict)
    body: str = ""
    order: list[str] = field(default_factory=list)


class FrontmatterError(ValueError):
    pass


def _parse_value(key: str, raw: str) -> object:
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        value = value[1:-1]
    if value.startswith("[") and value.endswith("]"):
        items = [item.strip().strip("'\"") for item in value[1:-1].split(",")]
        return [item for item in items if item]
    if key in LIST_KEYS:
        return [item.strip() for item in value.split(",") if item.strip()]
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    if value.isdigit():
        return int(value)
    return value


def parse(text: str, source: str = "<text>") -> Document:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise FrontmatterError(f"{source}: missing opening '---'")
    try:
        end = next(i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration as exc:
        raise FrontmatterError(f"{source}: missing closing '---'") from exc

    doc = Document()
    for number, line in enumerate(lines[1:end], start=2):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            raise FrontmatterError(f"{source}:{number}: expected 'key: value', got {stripped!r}")
        key, _, raw = stripped.partition(":")
        key = key.strip()
        if key in doc.meta:
            raise FrontmatterError(f"{source}:{number}: duplicate key {key!r}")
        doc.meta[key] = _parse_value(key, raw)
        doc.order.append(key)
    doc.body = "\n".join(lines[end + 1 :]).strip("\n") + "\n"
    return doc


def load(path: Path) -> Document:
    return parse(path.read_text(encoding="utf-8"), source=str(path))


def dump(meta: dict[str, object], body: str) -> str:
    out = ["---"]
    for key, value in meta.items():
        if isinstance(value, list):
            items = ", ".join("'" + str(v) + "'" for v in value)
            out.append(f"{key}: [{items}]")
        elif isinstance(value, bool):
            out.append(f"{key}: {'true' if value else 'false'}")
        else:
            out.append(f"{key}: {value}")
    out.append("---")
    out.append("")
    return "\n".join(out) + body
