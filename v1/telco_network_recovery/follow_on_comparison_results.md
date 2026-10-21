# Follow-On Comparison Test Results

Tested on 2026-09-29 against Snowflake account `AJB85638`, database `BERTOLANI`, warehouse `RAI_XS`.

## Umbrella Question

> We are a regional telco. We have tower health, equipment advisories, subscriber impact, call graph data, upgrade options, and a fixed capex budget. Which towers should we upgrade, why those towers, and what constraint limits the plan?

## 1. Regular Snowflake Cortex Baseline

Command path:

```sql
SELECT SNOWFLAKE.CORTEX.COMPLETE(
  'llama3.1-70b',
  'You are answering inside a regular Snowflake Cortex workflow ...'
) AS answer;
```

Observed answer shape:

- Returned a useful analysis workflow.
- Suggested filtering tower health and equipment advisories.
- Suggested joining to subscriber impact and upgrade options.
- Identified fixed capex budget as the likely limiting constraint.
- Did not return exact tower IDs, optimal total cost, tier mix, or plan totals because those outputs were not supplied.

Representative answer excerpt:

> To determine which towers should be upgraded, we need to analyze the available data to prioritize upgrades based on factors such as tower health, equipment advisories, and subscriber impact.

## 2. Snowflake Semantic Views

Created demo semantic views:

- `BERTOLANI.TELCO_NETWORK_RECOVERY_EXPERIMENTS.TELCO_SOURCE_NAIVE_SV`

This semantic view was built without RelationalAI result tables. It uses only raw/source telco tables from:

- `BERTOLANI.TELCO_NETWORK_RECOVERY_SOURCE.CELL_TOWERS`
- `BERTOLANI.TELCO_NETWORK_RECOVERY_SOURCE.NETWORK_PERFORMANCE`
- `BERTOLANI.TELCO_NETWORK_RECOVERY_SOURCE.CALL_DETAIL_RECORDS`
- `BERTOLANI.TELCO_NETWORK_RECOVERY_SOURCE.NETWORK_EQUIPMENT`
- `BERTOLANI.TELCO_NETWORK_RECOVERY_SOURCE.EQUIPMENT_HEALTH`
- `BERTOLANI.TELCO_NETWORK_RECOVERY_SOURCE.TOWER_UPGRADE_OPTIONS`

It represents what a naive Snowflake user might try first: governed dimensions and metrics over raw operational tables, plus a simple heuristic priority score.

Regional source-only metrics:

| Region | Towers | Avg health | Avg latency | Calls | Cheapest-upgrade total |
| --- | ---: | ---: | ---: | ---: | ---: |
| CENTRAL | 31 | 0.541 | 29.5 ms | 514 | $2,596,699 |
| EAST | 52 | 0.627 | 30.5 ms | 876 | $4,277,871 |
| NORTH | 42 | 0.635 | 29.9 ms | 718 | $3,761,774 |
| SOUTH | 44 | 0.620 | 29.9 ms | 728 | $3,624,945 |
| WEST | 81 | 0.589 | 59.3 ms | 3,164 | $6,887,904 |

Top naive candidates from raw health/performance/cost heuristics:

| Tower | Region | Status | Avg latency | Packet loss | Subscriber touches | Naive priority score |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| TWR-0012 | WEST | DEGRADED | 186.3 ms | 10.26 | 194 | 177.06 |
| TWR-0011 | WEST | DEGRADED | 176.6 ms | 10.18 | 204 | 175.47 |
| TWR-0009 | WEST | DEGRADED | 193.4 ms | 9.28 | 185 | 173.36 |
| TWR-0005 | WEST | DEGRADED | 201.9 ms | 8.76 | 176 | 170.90 |
| TWR-0010 | WEST | DEGRADED | 195.8 ms | 8.57 | 202 | 170.25 |

Observed answer shape:

- Returns a plausible operational shortlist, heavily weighted toward degraded WEST towers.
- Can explain metrics such as latency, packet loss, health score, utilization, call touches, and upgrade cost.
- Does not select upgrade tiers under a fixed budget.
- Does not optimize across budget and install-week constraints.
- Does not produce predictive failure probabilities, graph impact, path reasoning, or a binding constraint.

## 3. RelationalAI-Backed Agent Tools

Verified deployed agent object:

- `BERTOLANI.TELCO_NETWORK_RECOVERY_AGENT.TELCO_NETWORK_RECOVERY_AGENT`

Verified deployed catalog procedures:

- `BERTOLANI.TELCO_NETWORK_RECOVERY_AGENT.RAI_DISCOVER_MODELS()`
- `BERTOLANI.TELCO_NETWORK_RECOVERY_AGENT.RAI_QUERY_MODEL(NUMBER, VARCHAR)`

Discovery showed model `0` with these catalog queries:

- `plan_summary`
- `selected_upgrades`
- `regional_upgrade_summary`
- `top_tower_risk_and_impact`
- `high_risk_equipment_predictions`
- `top_call_path`

Plan summary from `RAI_QUERY_MODEL(0, '{"id":"plan_summary","args":{}}')`:

| Field | Value |
| --- | --- |
| Plan ID | `TELCO_RECOVERY_STANDALONE` |
| Status | `OPTIMAL` |
| Total cost | `$4,985,789` |
| Capacity restored | `183 Gbps` |
| Towers covered | `27` |
| Install weeks | `167` |
| Tier mix | Gold `8`, Silver `8`, Bronze `11` |
| Binding constraint | `budget` |

Top risk and impact rows from `top_tower_risk_and_impact`:

| Tower | Failure intensity | Active subscribers | Weighted impact |
| --- | ---: | ---: | ---: |
| TWR-0021 | 9.859 | 32 | 324,669 |
| TWR-0030 | 9.080 | 26 | 76,180 |
| TWR-0067 | 8.048 | 24 | 1,466,615 |
| TWR-0086 | 8.024 | 39 | 1,120,168 |
| TWR-0070 | 7.720 | 22 | 568,028 |

Top call path from `top_call_path`:

| Field | Value |
| --- | --- |
| Hub subscriber | `SUB-CON-00900` |
| Influence load | `0.009041314164` |
| Subscriber path | `SUB-CON-00900 -> SUB-CON-00814 -> SUB-ENT-0038 -> SUB-CON-00644` |
| Tower path | `TWR-0094 -> TWR-0113 -> TWR-0055` |

High-risk equipment examples from `high_risk_equipment_predictions`:

| Equipment | Failure probability |
| --- | ---: |
| EQP-00361 | 99.230% |
| EQP-01386 | 99.223% |
| EQP-00382 | 99.222% |
| EQP-00969 | 99.219% |
| EQP-00729 | 99.219% |

## Notes

The Python `si_agent.py chat/status` path was not usable from this shell because the Snowflake connector authentication hung. The same deployed agent resources were verified through Snowflake CLI, and the deployed RAI stored procedures returned the catalog tool outputs that the Cortex agent uses.
