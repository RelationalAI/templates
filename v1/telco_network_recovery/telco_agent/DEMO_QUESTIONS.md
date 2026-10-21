# CoWork demo questions

Agent: `BERTOLANI.TELCO_NETWORK_RECOVERY_AGENT.TELCO_NETWORK_RECOVERY_AGENT`

Ask these in Snowflake CoWork. From `v1/telco_network_recovery`, the CLI equivalent is:

```bash
env -u DEBUG RAI_CONFIG_FILE_PATH=raiconfig_reasoners.yaml ../../.venv/bin/python -m telco_agent.si_agent chat '<question>'
```

| Reasoner | Question | Catalog query |
| --- | --- | --- |
| Rules | Which WEST towers do the deployed operational rules flag as critical for restoration? Give every flagged tower ID as a plain-text numbered list, not a chart or table. For each, include status, packet loss percentage, and average equipment health score, then explain the rule thresholds. | `operational_critical_restore_towers` |
| Predictive | Which equipment items are most likely to fail? Show the failure probability, current status, equipment model, and tower for each. Give the top 10 as a plain-text numbered list, not a chart. | `high_risk_equipment_predictions` |
| Graph | Which towers carry the greatest customer value at risk in the call graph? Show active subscriber counts and PageRank-weighted influence. Give the top 10 as a plain-text numbered list, not a chart. | `top_tower_customer_impact` |
| Prescriptive | Given everything we know about the network and a fixed $5M budget, which towers and upgrade tiers should we choose and why? List every selected tower ID and tier as a plain-text numbered list, not a chart, and include total spend and restored capacity. | `upgrade_plan_with_rationale` |
| Prescriptive scenario | Optimize tower upgrades with a budget of $4 million. Run the live budget optimization; list every selected tower ID and tier, total spend, capacity restored, and install weeks used. | `optimize_upgrades_for_budget(budget_usd=4000000)` |

Optional graph/path follow-up: "What is the most influential enumerated call path, and which towers carry its hops?" (`top_call_path`).

These are live agent queries against deployed semantic tables and materialized reasoner outputs. Chat does not retrain the GNN or rerun PageRank or path enumeration. The budget-scenario query reruns **only** the upgrade optimization against the current materialized inputs; it accepts any positive whole-dollar budget and keeps the 200-week install limit. It returns an isolated result without changing the stored $5M plan. Other queries that refer to "the current plan" still use that stored baseline. A cold live solve may take a few minutes. Rerun the corresponding `run_*.py` job to refresh a materialized result snapshot.

The rules question uses the stable deployed operational flag (12 WEST towers in the current snapshot). The older in-memory walkthrough also describes a broader critical-restore rule that includes predicted failure intensity; that combined flag is not deployed in this agent.

## Multi-reasoner incident scenario

Load the separate synthetic incident overlay once, then update the existing agent's stored procedures:

```bash
../../.venv/bin/python load_demo_incidents.py
env -u DEBUG RAI_CONFIG_FILE_PATH=raiconfig_reasoners.yaml ../../.venv/bin/python -m telco_agent.si_agent update
```

The fixture is `data/demo_incidents.csv`, loaded to `BERTOLANI.TELCO_NETWORK_RECOVERY_RESULTS.DEMO_INCIDENT_INPUT`. It contains eight open incidents and one resolved control. It does **not** edit the deployed network source tables or rerun the $5M optimization. The agent joins it to materialized RAI outputs, so these are cross-reasoner **analyses of the existing plan**, not a freshly optimized incident response.

| # | Ask CoWork | Reasoner handoff | Catalog query |
| --- | --- | --- | --- |
| 1 | Of the open network incidents, which towers have the highest combined failure risk and customer impact? Show incident ID, tower, severity, risk and impact, operational rule flag, and whether the current $5M plan upgrades it. | GNN tower score + call-graph impact + rules + optimization | `open_incident_risk_and_impact` |
| 2 | Which open incidents are on towers the WEST restoration rule marks critical but the current $5M plan does not upgrade? Show summed equipment GNN intensity and routed-call customer impact. State that the cause of each solver exclusion is unknown from the stored plan, that a GNN intensity above 1 is not a risk threshold, and that the plan was not rerun for incidents. | Rules -> GNN/graph context -> optimization gap | `unfunded_critical_incidents` |
| 3 | Which installed recalled equipment sits on towers with open incidents? Show equipment ID, model, current status, GNN score, customer impact and whether that tower is selected for upgrade. | Advisory data + GNN equipment score + graph impact + optimization | `recalled_equipment_on_open_incidents` |
| 4 | Along the most influential call path, which hops have open incidents and which are covered by the $5M plan? Show path order, affected towers, risk and graph impact where an incident exists. | Graph path enumeration -> incident/rule/risk context -> optimization | `call_path_incident_coverage` |
| 5 | Give me an incident response briefing across all open demo incidents: combine rule flags, GNN risk, customer impact, recalled equipment, top-path membership and current $5M upgrade coverage. Compare only within the eight open incidents; do not infer why any tower was excluded by the solver or claim the plan was rerun. | Rules + GNN + graph impact/paths + advisory joins + optimization | `incident_response_briefing` |

Validated examples in the current snapshot:

- `INC-002` is the sole open, rule-flagged WEST incident not covered by the plan: `TWR-0004` has failure intensity `1.03` and graph-weighted impact about `1.09M`.
- `INC-003` on `TWR-0032` has three installed `TRX-H1` recalled units, including `EQP-00244`; the plan selects Gold there. The recalled-equipment question returns 18 equipment rows across open-incident towers.
- The top call path is `TWR-0094 -> TWR-0113 -> TWR-0055`. `INC-007` is on unfunded `TWR-0113`; `INC-006` is on `TWR-0055`, selected at Silver.
- The full briefing has eight open incident rows and retains the baseline `$4,985,789` plan. `INC-009` is resolved and absent from every open-incident answer.

The displayed tower failure intensity is the **sum** of equipment GNN scores, not a normalized risk or calibrated future-failure probability. The GNN was trained on synthetic current-status labels. `risk_impact_proxy` is a ranking product, not a dollar estimate. `weighted_impact` sums active caller value over routed call records and can repeat a subscriber; it is separate from `weighted_pagerank` and is not unique revenue. The current solver output does not explain why a particular tower was excluded. To demonstrate changed *decisions* rather than a changed *briefing*, add incident-aware rules/objective terms, rerun the optimization job, and then update the materialized plan.
