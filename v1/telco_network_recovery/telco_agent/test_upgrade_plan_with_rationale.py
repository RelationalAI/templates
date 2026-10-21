"""Offline checks for the agent's combined upgrade decision query."""

import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

from telco_agent import queries


class UpgradePlanWithRationaleTests(unittest.TestCase):
    def setUp(self):
        self.model = MagicMock()
        self.plan = pd.DataFrame(
            [
                {
                    "plan_id": "TELCO_RECOVERY_STANDALONE",
                    "status": "OPTIMAL",
                    "total_cost_usd": 500_000,
                    "install_weeks": 10,
                    "capacity_restored_gbps": 13,
                    "towers_covered": 2,
                    "binding_constraint": "budget",
                }
            ]
        )
        self.upgrades = pd.DataFrame(
            [
                {
                    "tower_id": "TWR-1",
                    "tier": "SILVER",
                    "region": "WEST",
                    "capacity_gbps": 5,
                    "cost_usd": 200_000,
                    "install_weeks": 4,
                    "failure_intensity": 2.0,
                    "weighted_impact": 100_000.0,
                    "objective_contribution": 1_000_000.0,
                },
                {
                    "tower_id": "TWR-2",
                    "tier": "GOLD",
                    "region": "EAST",
                    "capacity_gbps": 8,
                    "cost_usd": 300_000,
                    "install_weeks": 6,
                    "failure_intensity": 3.0,
                    "weighted_impact": 200_000.0,
                    "objective_contribution": 4_800_000.0,
                },
            ]
        )
        self.model.select.return_value.to_df.return_value = self.upgrades

    def test_returns_plan_and_ranked_tower_explanations(self):
        with patch.object(queries, "plan_summary", return_value=self.plan), patch.object(
            queries, "_table", return_value=MagicMock()
        ):
            result = queries.upgrade_plan_with_rationale(self.model)

        self.assertEqual(result["tower_id"].tolist(), ["TWR-2", "TWR-1"])
        self.assertEqual(result["plan_total_cost_usd"].tolist(), [500_000] * 2)
        self.assertEqual(result["plan_capacity_restored_gbps"].tolist(), [13] * 2)
        self.assertEqual(result["binding_constraint"].tolist(), ["budget"] * 2)
        self.assertEqual(result.iloc[0]["capacity_gbps"], 8)
        self.assertEqual(result.iloc[0]["failure_intensity"], 3.0)
        self.assertEqual(result.iloc[0]["weighted_impact"], 200_000.0)
        self.assertEqual(result.iloc[0]["objective_contribution"], 4_800_000.0)

    def test_requires_one_materialized_plan(self):
        with patch.object(queries, "plan_summary", return_value=pd.DataFrame()):
            with self.assertRaisesRegex(RuntimeError, "Expected one restore plan"):
                queries.upgrade_plan_with_rationale(self.model)

    def test_reports_empty_selection(self):
        self.model.select.return_value.to_df.return_value = self.upgrades.iloc[0:0]
        with patch.object(queries, "plan_summary", return_value=self.plan), patch.object(
            queries, "_table", return_value=MagicMock()
        ):
            with self.assertRaisesRegex(RuntimeError, "no selected upgrades"):
                queries.upgrade_plan_with_rationale(self.model)

    def test_rejects_mismatched_plan_totals(self):
        self.plan.loc[0, "total_cost_usd"] = 400_000
        with patch.object(queries, "plan_summary", return_value=self.plan), patch.object(
            queries, "_table", return_value=MagicMock()
        ):
            with self.assertRaisesRegex(RuntimeError, "disagree"):
                queries.upgrade_plan_with_rationale(self.model)


if __name__ == "__main__":
    unittest.main()
