#!/usr/bin/env python3
"""Generate template indexes from template README front matter.

This script scans version folders (e.g. v0.13, v0.14, v1), reads each
template README front matter, extracts `description`, `industry`, and
`reasoning_types`, and writes a collapsible, industry-grouped index.

The index is written to two places:

* each version folder's `README.md` (the per-version index), and
* the repository root `README.md`, between the
  `<!-- BEGIN TEMPLATE INDEX -->` / `<!-- END TEMPLATE INDEX -->`
  markers (the index for the current `v1` templates).
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

VERSION_DIR_RE = re.compile(r"^v\d")
FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", re.DOTALL)

# Version whose index is mirrored into the repository root README.
ROOT_INDEX_VERSION = "v1"
ROOT_INDEX_BEGIN = "<!-- BEGIN TEMPLATE INDEX -->"
ROOT_INDEX_END = "<!-- END TEMPLATE INDEX -->"
ROOT_INDEX_RE = re.compile(
    re.escape(ROOT_INDEX_BEGIN) + r".*?" + re.escape(ROOT_INDEX_END),
    re.DOTALL,
)

UNCATEGORIZED = "Uncategorized"


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


def collect_templates(version_dir: Path) -> list[TemplateEntry]:
    entries: list[TemplateEntry] = []
    for child in sorted(version_dir.iterdir(), key=lambda p: p.name):
        if not child.is_dir() or child.name.startswith("."):
            continue

        template_readme = child / "README.md"
        if not template_readme.exists():
            continue

        metadata = parse_front_matter(template_readme)
        entries.append(build_entry(child.name, metadata))

    if not entries:
        raise ValueError(f"no template README files found in {version_dir}")

    return entries


def build_index(entries: list[TemplateEntry], link_prefix: str) -> str:
    """Build the collapsible, industry-grouped index body.

    `link_prefix` is prepended to each template's folder link: `./` for a
    per-version README that sits beside the templates, `v1/` for the root
    README one level up.
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


def build_version_readme(version: str, entries: list[TemplateEntry]) -> str:
    parts = [
        f"# {version} Templates",
        "",
        (
            f"This directory contains the templates for {version}. "
            "Each template folder includes its own code, data, and detailed README."
        ),
        "",
        "## Template Index",
        "",
        "Templates are grouped by industry. Expand an industry to see its "
        "templates, the reasoners each uses, and a one-line description.",
        "",
        build_index(entries, "./"),
        "",
    ]
    return "\n".join(parts)


def build_root_readme(current: str, entries: list[TemplateEntry]) -> str:
    if not ROOT_INDEX_RE.search(current):
        raise ValueError(
            "root README missing "
            f"{ROOT_INDEX_BEGIN} / {ROOT_INDEX_END} markers"
        )

    index = build_index(entries, f"{ROOT_INDEX_VERSION}/")
    block = f"{ROOT_INDEX_BEGIN}\n\n{index}\n\n{ROOT_INDEX_END}"
    # Use a replacement function so backslashes in `block` (escaped table
    # cells) are not interpreted as regex backreferences.
    return ROOT_INDEX_RE.sub(lambda _match: block, current)


def find_version_dirs(repo_root: Path) -> list[Path]:
    return sorted(
        [
            path
            for path in repo_root.iterdir()
            if path.is_dir() and VERSION_DIR_RE.match(path.name)
        ],
        key=lambda p: p.name,
    )


def check_or_write(repo_root: Path, check_only: bool) -> int:
    version_dirs = find_version_dirs(repo_root)
    if not version_dirs:
        print("No version directories found.", file=sys.stderr)
        return 1

    out_of_date: list[Path] = []
    entries_by_version: dict[str, list[TemplateEntry]] = {}

    for version_dir in version_dirs:
        entries = collect_templates(version_dir)
        entries_by_version[version_dir.name] = entries
        expected = build_version_readme(version_dir.name, entries)
        readme_path = version_dir / "README.md"

        current = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""
        if current != expected:
            out_of_date.append(readme_path)
            if not check_only:
                readme_path.write_text(expected, encoding="utf-8")
                print(f"Updated {readme_path.relative_to(repo_root)}")

    root_readme = repo_root / "README.md"
    root_entries = entries_by_version.get(ROOT_INDEX_VERSION)
    if root_entries and root_readme.exists():
        current = root_readme.read_text(encoding="utf-8")
        expected = build_root_readme(current, root_entries)
        if current != expected:
            out_of_date.append(root_readme)
            if not check_only:
                root_readme.write_text(expected, encoding="utf-8")
                print(f"Updated {root_readme.relative_to(repo_root)}")

    if check_only and out_of_date:
        print("Template indexes are out of date:", file=sys.stderr)
        for path in out_of_date:
            print(f"- {path.relative_to(repo_root)}", file=sys.stderr)
        print(
            "Run: python scripts/generate_version_indexes.py",
            file=sys.stderr,
        )
        return 1

    if check_only:
        print("Template indexes are up to date.")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate template indexes from template README front matter."
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
