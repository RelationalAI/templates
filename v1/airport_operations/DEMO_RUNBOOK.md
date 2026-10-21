# Airport Operations Live Demo Runbook

## Deployment checked on 2026-10-14

- Source data: `ACDM_DEMO.EHAM`, including 320 synthetic flights. The demo clock is 2026-10-14 14:30; these are scenario timestamps, not live airport data.
- Deployed ontology: model `eham_acdm` in `BERTOLANI.AIRPORT_OPERATIONS`.
- Oplog: enabled with the Snowflake backend in the local `raiconfig.yaml`. Redeployment on 2026-10-14 refreshed the model, recorded 357 changes, and made `AIRPORT_OPERATIONS` appear in `rai models list`. This is the first recorded baseline; earlier deployments are not retroactively logged.
- Agent procedures and stage: `BERTOLANI.AIRPORT_OPERATIONS_AGENT`.
- Snowflake Intelligence agent: `SNOWFLAKE_INTELLIGENCE.AGENTS.AIRPORT_OPERATIONS`.
- SDK: public `relationalai==1.25.0`. The agent runtime also pins `opentelemetry-api==1.44.0`.
- The agent's reasoner queries execute the ontology in eager mode. The deployed schema is separately available for materialized ontology reads; `Problem.solve()` is not supported in deployment mode in this SDK. Do not say the agent's optimization reads the deployed tables.

This preparation did not regenerate or reload the synthetic source tables. The original `prep_demo.py` and loader have broader Snowflake side effects; inspect them before using them.

## Before presenting

Run from this directory with the Python 3.13 environment from `requirements.txt` active and a local, ignored `raiconfig.yaml` pointing to your authorized Snowflake account. Do not commit credentials. The current config uses the `sf` connection, `BERTOLANI.AIRPORT_OPERATIONS` deployment schema, and `rai_code/manual/eham_acdm.py` model path.

```bash
export RAI_CONFIG_FILE_PATH="$PWD/raiconfig.yaml"
env -u DEBUG rai connect
env -u DEBUG rai models list --limit 200
env -u DEBUG python -c 'from rai_code.manual.demo_queries import q1_tobt_violations_by_handler; print(q1_tobt_violations_by_handler().to_string(index=False))'
env -u DEBUG ACDM_DISABLE_DEPLOYMENT_CONFIG=1 python -m agent.deploy status
```

For a new deployment or after model edits:

```bash
env -u DEBUG rai models deploy --wait
env -u DEBUG ACDM_DISABLE_DEPLOYMENT_CONFIG=1 python -m agent.deploy preflight
env -u DEBUG ACDM_DISABLE_DEPLOYMENT_CONFIG=1 python -m agent.deploy deploy
```

For agent-only query or description edits, use `python -m agent.deploy update` with the same environment variables. The CLI creates a versioned zip of the local Python modules so Snowflake receives the current code. Engine cold starts took several minutes in validation; run a query before the live session. A warning about `CreateThreadResponse.external_id` appeared in local chat calls but did not prevent successful answers.

## Live questions and verified answers

Ask the questions in this order in Snowflake Intelligence or with `python -m agent.deploy chat '<question>'` (using the environment above). The catalog IDs are useful if the agent selects the wrong tool.

| Act | Prompt | Catalog query | Verified answer |
| --- | --- | --- | --- |
| 1. Rules | Show TOBT violations by ground handler in the four hours before 14:30 on October 14, 2026. Give counts and average deviation. | `tobt_violations_by_handler` | KLG 7 (+8.57 min), AGS 5 (+9.20), DNATA 3 (-9.33), MENZIES 2 (+7.50). |
| 2. Graph | Which flights are reachable downstream from KL1234 through aircraft rotation, slot-block, and stand-contention connections? List the six other callsigns. | `rotation_cascade_from_kl1234` | AF1241, HV5821, KL0407, KL1235, KL1402, KL1601. The raw result also includes KL1234 itself. |
| 3. Heuristic | Rank inbound flights landing between 14:30 and 15:00 on October 14 by the MS5 deterministic conflict-priority score. Show the top five; do not call it a probability. | `ms5_conflict_ranking` | KL0164 0.675, KL1234 0.649, KL0302 0.519, KL0918 0.508, DL0036 0.501. Eleven candidates total. |
| 4. Optimization | Run the curated TSAT storm-window re-sequencing optimization for October 14. How many flights are assigned and what are the first five callsigns with slot offsets and delays? | `tsat_resequence_under_storm` | `OPTIMAL`, 47 flights, objective 1079.6. KL0669 0/8, KL0842 1/5, KL0407 2/2, KL0144 4/7, KL0256 5/1 (offset/delay in minutes). |
| 5. Rule + optimization | Apply an eight-minute maximum delay for KL flights with more than 80 connecting passengers. Compare the baseline and preserved solutions: did the cap bind, did the objective change, and what happened to KL691? | `tsat_preservation_impact` | Both `OPTIMAL` at 1079.6. Zero baseline cap breaches. KL691 has zero delay in both plans. Three assignments differ across equal-objective solutions; the cap did not force an improvement. |

All five prompts were answered by the deployed CoWork agent during preparation. Act 5 was also checked directly against both RAI solves and through the deployed catalog procedure. Recheck after changing the model, source data, SDK, or agent code.

## Claim boundaries

- Act 1 returns handler aggregates, not an individual-flight list or evidence of actual TOBT/TSAT removal.
- Act 2 returns graph reachability. It does not calculate exact routes, elapsed impact, crew, gate assignments, or ATFM slot changes.
- Act 3 is a deterministic PyRel score, not a trained predictive model or a calibrated probability. Do not infer observed conflict outcomes from it.
- Act 4 minimizes delay weighted by `1 + 20 * ATFM penalty`. It enforces one flight per runway minute, one push per pier per minute, no early push, and wake separation. CTOT is **not** a hard constraint; passenger connections are **not** in the baseline objective.
- Act 5's cap is valid but nonbinding on the seed baseline. Differences between optimal assignments are not proof that the preservation rule caused the shifts. For a binding-rule story, create and validate a separate scenario rather than claiming one here.

## Direct checks

These skip the agent and run the curated functions with the same source data. `ACDM_DISABLE_DEPLOYMENT_CONFIG=1` is required for the graph and prescriptive reasoners.

```bash
env -u DEBUG ACDM_DISABLE_DEPLOYMENT_CONFIG=1 python -m rai_code.manual.demo_queries
env -u DEBUG ACDM_DISABLE_DEPLOYMENT_CONFIG=1 python -c 'from agent.queries import tsat_preservation_impact; print(tsat_preservation_impact().to_string(index=False))'
```

To verify a materialized ontology read, omit `ACDM_DISABLE_DEPLOYMENT_CONFIG` and run `q1_tobt_violations_by_handler()` from `rai_code.manual.demo_queries`. This is a separate check from the eager agent path.
