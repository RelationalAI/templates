"""Offline checks for the agent's parameterized tower-upgrade optimizer."""

import unittest
from unittest.mock import patch

import pandas as pd
from relationalai.semantics import Model

import run_optimization
from telco_agent.queries import build_tool_registry


class BudgetOptimizationTests(unittest.TestCase):
    def test_catalog_exposes_integer_budget(self):
        registry = build_tool_registry(Model("Budget Tool Metadata Test"))
        catalog = registry._tools[0]._queries

        metadata = catalog.get_available_queries()["queries"]["optimize_upgrades_for_budget"]
        self.assertEqual(metadata["args"], {"budget_usd": "int"})

    def test_tool_returns_scenario_rows_and_totals(self):
        model = Model("Budget Tool Result Test")
        registry = build_tool_registry(model)
        catalog = registry._tools[0]._queries
        selected = pd.DataFrame(
            [
                {
                    "TOWER_ID": "TWR-0012",
                    "TIER": "BRONZE",
                    "REGION": "WEST",
                    "CAPACITY_GBPS": 5,
                    "COST": 200_000,
                    "INSTALL_WEEKS": 4,
                    "FAILURE_INTENSITY": 2.0,
                    "WEIGHTED_IMPACT": 100_000.0,
                }
            ]
        )
        plan = pd.DataFrame(
            [
                {
                    "TERMINATION_STATUS": "OPTIMAL",
                    "TOTAL_COST": 200_000,
                    "TOTAL_INSTALL_WEEKS": 4,
                    "CAPACITY_RESTORED_GBPS": 5,
                    "TOWERS_COVERED": 1,
                    "BINDING_CONSTRAINT": "none",
                }
            ]
        )

        with patch.object(run_optimization, "optimize", return_value=(selected, plan)) as mocked:
            result = catalog.execute(
                "optimize_upgrades_for_budget", {"budget_usd": 3_000_000}
            )

        mocked.assert_called_once_with(3_000_000, config=model.config)
        self.assertEqual(result.iloc[0]["tower_id"], "TWR-0012")
        self.assertEqual(result.iloc[0]["requested_budget_usd"], 3_000_000)
        self.assertEqual(result.iloc[0]["plan_total_cost_usd"], 200_000)
        self.assertEqual(result.iloc[0]["objective_contribution"], 1_000_000)
        self.assertEqual(result.iloc[0]["install_week_limit"], 200)

    def test_invalid_budget_fails_before_loading_model(self):
        with patch.object(run_optimization, "build_model") as build_model:
            for budget in (0, -1, 1.5, True, "3000000"):
                with self.subTest(budget=budget), self.assertRaises(ValueError):
                    run_optimization.optimize(budget)
            build_model.assert_not_called()


if __name__ == "__main__":
    unittest.main()
