#!/usr/bin/env python3
"""Validate template-docs adoption policy for changed v1 templates."""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable


@dataclass(frozen=True)
class Change:
    """One parsed entry from git diff --name-status."""

    status: str
    old_path: str | None
    new_path: str | None


def run_git(repo_root: Path, *args: str) -> str:
    """Run a read-only Git command and return stdout."""
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout


def parse_name_status(output: str) -> list[Change]:
    """Parse the tab-separated output from git diff --name-status."""
    changes: list[Change] = []
    for line in output.splitlines():
        if not line:
            continue
        fields = line.split("\t")
        code = fields[0][:1]
        if code in {"C", "R"}:
            if len(fields) != 3:
                raise ValueError(f"Unexpected rename/copy entry: {line}")
            changes.append(Change(code, fields[1], fields[2]))
        else:
            if len(fields) != 2:
                raise ValueError(f"Unexpected changed-file entry: {line}")
            old_path = fields[1] if code == "D" else None
            new_path = None if code == "D" else fields[1]
            changes.append(Change(code, old_path, new_path))
    return changes


def is_v1_file(path: str | None, filename: str) -> bool:
    """Return whether path is exactly v1/<slug>/<filename>."""
    if path is None:
        return False
    parts = PurePosixPath(path).parts
    return len(parts) == 3 and parts[0] == "v1" and parts[2] == filename


def template_sidecar(readme_path: str) -> str:
    """Return the canonical sidecar path beside a template README."""
    return str(PurePosixPath(readme_path).with_name("template-docs.yaml"))


def is_new_template_readme(change: Change) -> bool:
    """Return whether a change introduces a README at a new v1 template path."""
    if not is_v1_file(change.new_path, "README.md"):
        return False
    if change.status in {"A", "C"}:
        return True
    if change.status != "R" or change.old_path is None or change.new_path is None:
        return False
    return PurePosixPath(change.old_path).parent != PurePosixPath(change.new_path).parent


def validate_changes(changes: Iterable[Change], head_paths: set[str]) -> list[str]:
    """Return policy violations for the supplied diff and head tree."""
    errors: list[str] = []
    for change in changes:
        if is_new_template_readme(change):
            assert change.new_path is not None
            sidecar_path = template_sidecar(change.new_path)
            if sidecar_path not in head_paths:
                errors.append(
                    f"New v1 template {PurePosixPath(change.new_path).parent} "
                    f"must include {sidecar_path}."
                )

        if change.old_path is None or not is_v1_file(
            change.old_path, "template-docs.yaml"
        ):
            continue
        if change.status not in {"D", "R"}:
            continue

        old_template = PurePosixPath(change.old_path).parent
        old_readme = str(old_template / "README.md")
        old_sidecar = str(old_template / "template-docs.yaml")
        if old_readme in head_paths and old_sidecar not in head_paths:
            errors.append(
                f"{old_sidecar} cannot be deleted while {old_readme} remains; "
                "once adopted, enhanced template documentation is required."
            )

    return errors


def changed_files(repo_root: Path, base_ref: str, head_ref: str) -> list[Change]:
    """Read the merge-base diff used by pull-request validation."""
    output = run_git(
        repo_root,
        "diff",
        "--name-status",
        "--find-renames",
        f"{base_ref}...{head_ref}",
        "--",
        "v1",
    )
    return parse_name_status(output)


def tree_paths(repo_root: Path, ref: str) -> set[str]:
    """Return tracked paths at a Git ref."""
    return set(run_git(repo_root, "ls-tree", "-r", "--name-only", ref).splitlines())


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Require template-docs.yaml for newly added v1 templates and "
            "prevent its deletion from adopted templates."
        )
    )
    parser.add_argument(
        "--base-ref",
        required=True,
        help="Base commit or ref for the pull-request merge-base diff.",
    )
    parser.add_argument(
        "--head-ref",
        default="HEAD",
        help="Head commit or ref to validate (default: HEAD).",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    try:
        changes = changed_files(repo_root, args.base_ref, args.head_ref)
        errors = validate_changes(changes, tree_paths(repo_root, args.head_ref))
    except (RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if errors:
        print("Changed-template validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("Changed-template documentation policy passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
