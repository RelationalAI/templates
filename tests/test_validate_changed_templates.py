"""Tests for changed-template documentation policy."""

from __future__ import annotations

import unittest

from scripts.validate_changed_templates import Change, validate_changes


class ValidateChangedTemplatesTests(unittest.TestCase):
    def test_new_template_requires_sidecar(self) -> None:
        changes = [Change("A", None, "example/README.md")]
        errors = validate_changes(changes, {"example/README.md"})

        self.assertEqual(len(errors), 1)
        self.assertIn("must include example/template-docs.yaml", errors[0])

    def test_new_template_accepts_tracked_sidecar(self) -> None:
        changes = [
            Change("A", None, "example/README.md"),
            Change("A", None, "example/template-docs.yaml"),
        ]
        head_paths = {
            "example/README.md",
            "example/template-docs.yaml",
        }

        self.assertEqual(validate_changes(changes, head_paths), [])

    def test_modified_legacy_template_does_not_require_adoption(self) -> None:
        changes = [Change("M", None, "legacy/README.md")]

        self.assertEqual(validate_changes(changes, {"legacy/README.md"}), [])

    def test_adopted_template_cannot_delete_sidecar(self) -> None:
        changes = [
            Change("D", "example/template-docs.yaml", None),
        ]

        errors = validate_changes(changes, {"example/README.md"})

        self.assertEqual(len(errors), 1)
        self.assertIn("cannot be deleted", errors[0])

    def test_removing_whole_template_is_not_a_documentation_downgrade(self) -> None:
        changes = [
            Change("D", "example/README.md", None),
            Change("D", "example/template-docs.yaml", None),
        ]

        self.assertEqual(validate_changes(changes, set()), [])

    def test_renamed_template_is_treated_as_new(self) -> None:
        changes = [
            Change("R", "old/README.md", "new/README.md"),
        ]

        errors = validate_changes(changes, {"new/README.md"})

        self.assertEqual(len(errors), 1)
        self.assertIn("new/template-docs.yaml", errors[0])

    def test_flattening_existing_template_is_not_treated_as_new(self) -> None:
        changes = [
            Change("R", "v1/example/README.md", "example/README.md"),
        ]

        self.assertEqual(validate_changes(changes, {"example/README.md"}), [])

    def test_reserved_root_readmes_are_not_templates(self) -> None:
        for path in (
            "sample-template/README.md",
            "scripts/README.md",
            "tests/README.md",
            ".github/README.md",
        ):
            with self.subTest(path=path):
                changes = [Change("A", None, path)]
                self.assertEqual(validate_changes(changes, {path}), [])


if __name__ == "__main__":
    unittest.main()
