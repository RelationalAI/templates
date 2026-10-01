"""Tests for the flat repository template index."""

from __future__ import annotations

import unittest
from pathlib import Path

from scripts.generate_template_index import build_index, collect_templates

REPO_ROOT = Path(__file__).parents[1]


class GenerateTemplateIndexTests(unittest.TestCase):
    def test_collects_only_root_template_directories(self) -> None:
        entries = collect_templates(REPO_ROOT)
        names = {entry.name for entry in entries}

        self.assertEqual(len(entries), 54)
        self.assertIn("retail-delivery-agent", names)
        self.assertIn("simple-start", names)
        self.assertNotIn("sample-template", names)
        self.assertNotIn("scripts", names)
        self.assertNotIn("tests", names)

    def test_root_index_uses_flat_template_links(self) -> None:
        entries = collect_templates(REPO_ROOT)
        index = build_index(entries, "")

        self.assertIn("[simple-start](simple-start/)", index)
        self.assertIn("[retail-delivery-agent](retail-delivery-agent/)", index)
        self.assertNotIn("(v1/", index)


if __name__ == "__main__":
    unittest.main()
