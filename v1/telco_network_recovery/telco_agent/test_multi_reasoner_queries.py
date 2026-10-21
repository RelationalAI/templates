"""Focused checks for the synthetic incident catalog questions."""

import unittest
from unittest.mock import patch

import pandas as pd

from load_demo_incidents import load_fixture
from telco_agent import queries


class MultiReasonerQueryTests(unittest.TestCase):
    def test_fixture_has_open_and_resolved_control(self):
        incidents = load_fixture()
        self.assertEqual(len(incidents), 9)
        self.assertEqual(set(incidents.loc[incidents.STATE == "RESOLVED", "INCIDENT_ID"]), {"INC-009"})
        self.assertEqual((incidents.STATE == "OPEN").sum(), 8)

    def test_unfunded_critical_incidents_excludes_selected_towers(self):
        signals = pd.DataFrame(
            [
                {"incident_id": "INC-001", "operational_critical": True, "selected_for_upgrade": True, "risk_impact_proxy": 10},
                {"incident_id": "INC-002", "operational_critical": True, "selected_for_upgrade": False, "risk_impact_proxy": 8},
                {"incident_id": "INC-003", "operational_critical": False, "selected_for_upgrade": False, "risk_impact_proxy": 12},
            ]
        )
        signals["tower_id"] = ["TWR-0015", "TWR-0004", "TWR-0030"]
        signals["tower_name"] = "Test tower"
        signals["region"] = "WEST"
        signals["incident_type"] = "SERVICE_DEGRADATION"
        signals["severity"] = "HIGH"
        signals["failure_intensity"] = 1.03
        signals["active_subscriber_count"] = 41
        signals["weighted_impact"] = 1092430
        with patch.object(queries, "_incident_signals", return_value=signals):
            result = queries.unfunded_critical_incidents(object())
        self.assertEqual(result.incident_id.tolist(), ["INC-002"])
        self.assertEqual(result.solver_exclusion_cause.tolist(), ["UNKNOWN_FROM_STORED_PLAN"])

    def test_path_coverage_preserves_hop_order_and_unfunded_gap(self):
        path = pd.DataFrame([{"hub_subscriber_id": "SUB-1", "influence_load": 7, "tower_path": "TWR-0094 -> TWR-0113 -> TWR-0055"}])
        signals = pd.DataFrame(
            [
                {"incident_id": "INC-007", "tower_id": "TWR-0113", "severity": "MEDIUM", "failure_intensity": 5.0, "weighted_impact": 333312, "operational_critical": False},
                {"incident_id": "INC-006", "tower_id": "TWR-0055", "severity": "HIGH", "failure_intensity": 6.0, "weighted_impact": 591384, "operational_critical": False},
            ]
        )
        selected = pd.DataFrame([{"tower_id": "TWR-0055", "tier": "SILVER"}])
        with patch.object(queries, "top_call_path", return_value=path), patch.object(queries, "_incident_signals", return_value=signals), patch.object(queries, "selected_upgrades", return_value=selected):
            result = queries.call_path_incident_coverage(object())
        self.assertEqual(result.tower_id.tolist(), ["TWR-0094", "TWR-0113", "TWR-0055"])
        self.assertEqual(result.has_open_incident.tolist(), [False, True, True])
        self.assertEqual(result.selected_for_upgrade.tolist(), [False, False, True])

    def test_briefing_uses_existing_plan_and_counts_recalled_equipment(self):
        signals = pd.DataFrame(
            [
                {"incident_id": "INC-003", "tower_id": "TWR-0032", "risk_impact_proxy": 100},
                {"incident_id": "INC-007", "tower_id": "TWR-0113", "risk_impact_proxy": 20},
            ]
        )
        recalls = pd.DataFrame(
            [
                {"incident_id": "INC-003", "equipment_id": "EQP-1"},
                {"incident_id": "INC-003", "equipment_id": "EQP-2"},
            ]
        )
        path = pd.DataFrame([{"tower_path": "TWR-0094 -> TWR-0113 -> TWR-0055"}])
        plan = pd.DataFrame([{"total_cost_usd": 4985789, "capacity_restored_gbps": 183}])
        with patch.object(queries, "_incident_signals", return_value=signals), patch.object(queries, "_recalled_equipment_on_incidents", return_value=recalls) as recall_query, patch.object(queries, "top_call_path", return_value=path), patch.object(queries, "plan_summary", return_value=plan):
            result = queries.incident_response_briefing(object())
        recall_query.assert_called_once()
        self.assertIs(recall_query.call_args.args[1], signals)
        self.assertEqual(result.recalled_equipment_count.tolist(), [2, 0])
        self.assertEqual(result.on_top_call_path.tolist(), [False, True])
        self.assertEqual(result.plan_total_cost_usd.tolist(), [4985789, 4985789])


if __name__ == "__main__":
    unittest.main()
