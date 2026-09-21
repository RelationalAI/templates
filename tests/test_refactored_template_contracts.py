"""Static contracts for refactored templates."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parents[1]


def parse(path: str) -> ast.Module:
    return ast.parse((REPO_ROOT / path).read_text(), filename=path)


class RefactoredTemplateContractTests(unittest.TestCase):
    def test_entity_ground_truth_is_loaded_only_for_evaluation(self) -> None:
        source_module = parse("v1/entity_resolution/model/source.py")
        functions = {
            node.name: node
            for node in source_module.body
            if isinstance(node, ast.FunctionDef)
        }

        self.assertIn("ground_truth.csv", ast.dump(functions["load_ground_truth"]))
        self.assertNotIn("ground_truth.csv", ast.dump(functions["load_source_data"]))

        runner_module = parse("v1/entity_resolution/entity_resolution.py")
        ground_truth_calls = [
            node
            for node in ast.walk(runner_module)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "load_ground_truth"
        ]
        self.assertEqual(len(ground_truth_calls), 1)

    def test_fraud_explorer_properties_are_declared_in_schema(self) -> None:
        module = parse("v1/fraud-detection/model/schema.py")
        properties = set()
        for node in module.body:
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            target = node.targets[0]
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Attribute)
                and isinstance(node.value.func.value, ast.Name)
                and node.value.func.value.id == "model"
                and node.value.func.attr == "Property"
            ):
                properties.add(f"{target.value.id}.{target.attr}")

        expected = {
            "Account.account_type_prefix",
            "Transaction.step",
            "Transaction.step_ts",
            "Transaction.trans_type",
            "Transaction.amount",
            "Transaction.name_orig",
            "Transaction.old_balance_orig",
            "Transaction.new_balance_orig",
            "Transaction.name_dest",
            "Transaction.old_balance_dest",
            "Transaction.new_balance_dest",
            "Transaction.is_flagged_fraud",
            "Transaction.audit_cost",
        }
        self.assertLessEqual(expected, properties)


if __name__ == "__main__":
    unittest.main()
