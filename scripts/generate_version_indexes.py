#!/usr/bin/env python3
"""Generate version README template indexes from template README metadata.

This script scans version folders (e.g. v0.13, v0.14, v1), reads each
template README front matter, extracts `description`, and writes a concise
index README for each version.
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


@dataclass(frozen=True)
class TemplateEntry:
    name: str
    description: str


def escape_md_table_cell(value: str) -> str:
    """Escape markdown table delimiters and normalize whitespace."""
    return " ".join(value.split()).replace("|", r"\|")


def extract_description(readme_path: Path) -> str:
    text = readme_path.read_text(encoding="utf-8")
    front_matter_match = FRONT_MATTER_RE.match(text)
    if not front_matter_match:
        raise ValueError("missing YAML front matter block")

    front_matter = front_matter_match.group(1)
    try:
        metadata = yaml.safe_load(front_matter) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML front matter: {exc}") from exc

    if not isinstance(metadata, dict):
        raise ValueError("front matter must parse to a mapping")

    value = metadata.get("description")
    if not isinstance(value, str):
        raise ValueError("description key not found in front matter")

    value = escape_md_table_cell(value)
    if not value:
        raise ValueError("empty description value")
    return value


def collect_templates(version_dir: Path) -> list[TemplateEntry]:
    entries: list[TemplateEntry] = []
    for child in sorted(version_dir.iterdir(), key=lambda p: p.name):
        if not child.is_dir() or child.name.startswith("."):
            continue

        template_readme = child / "README.md"
        if not template_readme.exists():
            continue

        description = extract_description(template_readme)
        entries.append(TemplateEntry(name=child.name, description=description))

    if not entries:
        raise ValueError(f"no template README files found in {version_dir}")

    return entries


def build_version_readme(version: str, entries: list[TemplateEntry]) -> str:
    lines = [
        f"# {version} Templates",
        "",
        (
            f"This directory contains the templates for {version}. "
            "Each template folder includes its own code, data, and detailed README."
        ),
        "",
        "## Template Index",
        "",
        "| Template | Description |",
        "| --- | --- |",
    ]

    for entry in entries:
        lines.append(f"| [{entry.name}](./{entry.name}/) | {entry.description} |")

    return "\n".join(lines) + "\n"


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

    for version_dir in version_dirs:
        entries = collect_templates(version_dir)
        expected = build_version_readme(version_dir.name, entries)
        readme_path = version_dir / "README.md"

        current = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""
        if current != expected:
            out_of_date.append(readme_path)
            if not check_only:
                readme_path.write_text(expected, encoding="utf-8")
                print(f"Updated {readme_path.relative_to(repo_root)}")

    if check_only and out_of_date:
        print("Version README indexes are out of date:", file=sys.stderr)
        for path in out_of_date:
            print(f"- {path.relative_to(repo_root)}", file=sys.stderr)
        print(
            "Run: python scripts/generate_version_indexes.py",
            file=sys.stderr,
        )
        return 1

    if check_only:
        print("Version README indexes are up to date.")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate version README indexes from template README metadata."
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
