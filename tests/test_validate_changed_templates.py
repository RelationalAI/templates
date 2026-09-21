"""Tests for changed-template documentation policy."""

from __future__ import annotations

import unittest

from scripts.validate_changed_templates import Change, validate_changes


class ValidateChangedTemplatesTests(unittest.TestCase):
    def test_new_v1_template_requires_sidecar(self) -> None:
        changes = [Change("A", None, "v1/example/README.md")]
        errors = validate_changes(changes, {"v1/example/README.md"})

        self.assertEqual(len(errors), 1)
        self.assertIn("must include v1/example/template-docs.yaml", errors[0])

    def test_new_v1_template_accepts_tracked_sidecar(self) -> None:
        changes = [
            Change("A", None, "v1/example/README.md"),
            Change("A", None, "v1/example/template-docs.yaml"),
        ]
        head_paths = {
            "v1/example/README.md",
            "v1/example/template-docs.yaml",
        }

        self.assertEqual(validate_changes(changes, head_paths), [])

    def test_modified_legacy_template_does_not_require_adoption(self) -> None:
        changes = [Change("M", None, "v1/legacy/README.md")]

        self.assertEqual(validate_changes(changes, {"v1/legacy/README.md"}), [])

    def test_adopted_template_cannot_delete_sidecar(self) -> None:
        changes = [
            Change("D", "v1/example/template-docs.yaml", None),
        ]

        errors = validate_changes(changes, {"v1/example/README.md"})

        self.assertEqual(len(errors), 1)
        self.assertIn("cannot be deleted", errors[0])

    def test_removing_whole_template_is_not_a_documentation_downgrade(self) -> None:
        changes = [
            Change("D", "v1/example/README.md", None),
            Change("D", "v1/example/template-docs.yaml", None),
        ]

        self.assertEqual(validate_changes(changes, set()), [])

    def test_renamed_template_is_treated_as_new(self) -> None:
        changes = [
            Change("R", "v1/old/README.md", "v1/new/README.md"),
        ]

        errors = validate_changes(changes, {"v1/new/README.md"})

        self.assertEqual(len(errors), 1)
        self.assertIn("v1/new/template-docs.yaml", errors[0])


if __name__ == "__main__":
    unittest.main()
