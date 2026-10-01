#!/usr/bin/env python3
"""Generate the root template index from template README front matter.

This script scans template directories at the repository root, reads each
template README front matter, extracts `description`, `industry`, and
`reasoning_types`, and writes a collapsible, industry-grouped index between
the root README's template-index markers.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", re.DOTALL)

ROOT_INDEX_BEGIN = "<!-- BEGIN TEMPLATE INDEX -->"
ROOT_INDEX_END = "<!-- END TEMPLATE INDEX -->"
ROOT_INDEX_RE = re.compile(
    re.escape(ROOT_INDEX_BEGIN) + r".*?" + re.escape(ROOT_INDEX_END),
    re.DOTALL,
)

UNCATEGORIZED = "Uncategorized"
RESERVED_ROOT_DIRS = frozenset(
    {
        ".agents",
        ".git",
        ".github",
        "sample-template",
        "scripts",
        "tests",
    }
)


@dataclass(frozen=True)
class TemplateEntry:
    name: str
    description: str
    industry: str
    reasoners: tuple[str, ...]


def escape_md_table_cell(value: str) -> str:
    """Escape markdown table delimiters and normalize whitespace."""
    return " ".join(value.split()).replace("|", r"\|")


def parse_front_matter(readme_path: Path) -> dict:
    text = readme_path.read_text(encoding="utf-8")
    front_matter_match = FRONT_MATTER_RE.match(text)
    if not front_matter_match:
        raise ValueError("missing YAML front matter block")

    try:
        metadata = yaml.safe_load(front_matter_match.group(1)) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML front matter: {exc}") from exc

    if not isinstance(metadata, dict):
        raise ValueError("front matter must parse to a mapping")

    return metadata


def build_entry(name: str, metadata: dict) -> TemplateEntry:
    description = metadata.get("description")
    if not isinstance(description, str) or not description.strip():
        raise ValueError("description key not found in front matter")

    industry = metadata.get("industry")
    if not isinstance(industry, str) or not industry.strip():
        industry = UNCATEGORIZED

    raw_reasoners = metadata.get("reasoning_types")
    if not isinstance(raw_reasoners, list):
        raw_reasoners = []
    reasoners = tuple(
        escape_md_table_cell(str(item))
        for item in raw_reasoners
        if str(item).strip()
    )

    return TemplateEntry(
        name=name,
        description=escape_md_table_cell(description),
        industry=escape_md_table_cell(industry),
        reasoners=reasoners,
    )


def collect_templates(repo_root: Path) -> list[TemplateEntry]:
    entries: list[TemplateEntry] = []
    for child in sorted(repo_root.iterdir(), key=lambda p: p.name):
        if (
            not child.is_dir()
            or child.name.startswith(".")
            or child.name in RESERVED_ROOT_DIRS
        ):
            continue

        template_readme = child / "README.md"
        if not template_readme.exists():
            continue

        metadata = parse_front_matter(template_readme)
        entries.append(build_entry(child.name, metadata))

    if not entries:
        raise ValueError(f"no template README files found in {repo_root}")

    return entries


def build_index(entries: list[TemplateEntry], link_prefix: str) -> str:
    """Build the collapsible, industry-grouped index body.

    `link_prefix` is prepended to each template's folder link.
    """
    by_industry: dict[str, list[TemplateEntry]] = {}
    for entry in entries:
        by_industry.setdefault(entry.industry, []).append(entry)

    blocks: list[str] = []
    for industry in sorted(by_industry, key=str.lower):
        group = sorted(by_industry[industry], key=lambda e: e.name)
        block = [
            "<details>",
            f"<summary>{industry} ({len(group)})</summary>",
            "",
            "| Template | Reasoners | Description |",
            "| --- | --- | --- |",
        ]
        for entry in group:
            reasoners = ", ".join(entry.reasoners) if entry.reasoners else "—"
            block.append(
                f"| [{entry.name}]({link_prefix}{entry.name}/) "
                f"| {reasoners} | {entry.description} |"
            )
        block.extend(["", "</details>"])
        blocks.append("\n".join(block))

    return "\n\n".join(blocks)


def build_root_readme(current: str, entries: list[TemplateEntry]) -> str:
    if not ROOT_INDEX_RE.search(current):
        raise ValueError(
            "root README missing "
            f"{ROOT_INDEX_BEGIN} / {ROOT_INDEX_END} markers"
        )

    index = build_index(entries, "")
    block = f"{ROOT_INDEX_BEGIN}\n\n{index}\n\n{ROOT_INDEX_END}"
    # Use a replacement function so backslashes in `block` (escaped table
    # cells) are not interpreted as regex backreferences.
    return ROOT_INDEX_RE.sub(lambda _match: block, current)


def check_or_write(repo_root: Path, check_only: bool) -> int:
    out_of_date: list[Path] = []
    root_readme = repo_root / "README.md"
    if not root_readme.exists():
        raise ValueError("root README not found")

    entries = collect_templates(repo_root)
    current = root_readme.read_text(encoding="utf-8")
    expected = build_root_readme(current, entries)
    if current != expected:
        out_of_date.append(root_readme)
        if not check_only:
            root_readme.write_text(expected, encoding="utf-8")
            print(f"Updated {root_readme.relative_to(repo_root)}")

    if check_only and out_of_date:
        print("Template index is out of date:", file=sys.stderr)
        for path in out_of_date:
            print(f"- {path.relative_to(repo_root)}", file=sys.stderr)
        print(
            "Run: python scripts/generate_template_index.py",
            file=sys.stderr,
        )
        return 1

    if check_only:
        print("Template index is up to date.")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate the root template index from template README front matter."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check that generated files are up to date without writing changes.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    try:
        return check_or_write(repo_root=repo_root, check_only=args.check)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
