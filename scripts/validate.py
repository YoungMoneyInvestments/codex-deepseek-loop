"""Validate skill metadata, local references and plugin manifests. Standard library only."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def parse_frontmatter(text):
    if not text.startswith("---\n"):
        raise ValueError("missing frontmatter (or UTF-8 BOM present)")
    block = text.split("---", 2)[1]
    values = {}
    for key in ("name", "description"):
        match = re.search(r"^%s:\s*(.+?)\s*$" % key, block, re.M)
        if not match:
            raise ValueError("missing %s in frontmatter" % key)
        value = match.group(1).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key] = value
    return values


def validate(root=ROOT):
    errors = []
    for path in sorted((root / "skills").glob("*/SKILL.md")):
        try:
            front = parse_frontmatter(path.read_text(encoding="utf-8"))
            if front["name"] != path.parent.name:
                raise ValueError("name must match the skill folder")
            if not front["description"] or len(front["description"]) > 1024:
                raise ValueError("description must be a nonempty string of at most 1024 characters")
        except (ValueError, IndexError, AttributeError) as exc:
            errors.append("%s: %s" % (path.relative_to(root), exc))
    # Validate local links in public docs and active instructions, excluding fenced code.
    for path in [root / "README.md", *sorted((root / "skills").rglob("*.md"))]:
        if not path.exists():
            errors.append("%s: missing" % path.relative_to(root))
            continue
        text = re.sub(r"```.*?```", "", path.read_text(encoding="utf-8"), flags=re.S)
        for link in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
            if re.match(r"[a-z]+://|#|mailto:", link):
                continue
            target = link.split("#", 1)[0]
            if target and not (path.parent / target).exists():
                errors.append("%s: missing reference %s" % (path.relative_to(root), link))
    runner = root / "skills" / "deepseek-loop" / "scripts" / "deepseek_review.py"
    if not runner.is_file():
        errors.append("Missing reviewer runner: %s" % runner.relative_to(root))
    for folder in (".claude-plugin", ".codex-plugin"):
        manifest_path = root / folder / "plugin.json"
        if not manifest_path.is_file():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not manifest.get("name") or not manifest.get("version"):
                errors.append("%s: missing name/version" % folder)
        except (OSError, ValueError) as exc:
            errors.append("%s: %s" % (folder, exc))
    marketplace_path = root / ".claude-plugin" / "marketplace.json"
    if marketplace_path.is_file():
        try:
            marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
            manifest = json.loads((root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
            if marketplace["plugins"][0]["name"] != manifest["name"]:
                errors.append("Claude marketplace plugin name mismatch")
        except (OSError, ValueError, KeyError, IndexError) as exc:
            errors.append(".claude-plugin/marketplace.json: %s" % exc)
    return errors


if __name__ == "__main__":
    failures = validate()
    print("\n".join(failures) if failures else "Skill metadata, references and manifests passed.")
    sys.exit(bool(failures))
