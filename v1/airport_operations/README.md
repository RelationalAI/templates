---
title: "Airport Operations Decision Hub"
description: "Use an executable A-CDM ontology to audit flight readiness, trace delay cascades, rank gate conflicts, and re-sequence departures."
featured: false
experience_level: advanced
industry: "Aviation"
reasoning_types:
  - Rules
  - Graph
  - Prescriptive
tags:
  - airport-operations
  - a-cdm
  - flight-rotations
  - departure-sequencing
  - snowflake-intelligence
---

# Airport Operations Decision Hub

This demo models Airport Collaborative Decision Making (A-CDM) for a synthetic Amsterdam Schiphol (EHAM) operating day. The ontology connects flights, aircraft rotations, stands, handlers, milestones, weather, and runway slots. Five acts move from a TOBT readiness audit to a delay-cascade trace, a gate-conflict ranking, and two constrained departure-sequencing solves.

The dataset and scenario are synthetic. The MS5 gate-conflict ranking is a **deterministic PyRel heuristic**, not a trained predictive model or a calibrated probability. The talks and figures are presentation material; use the code and validation queries to check any live result.

## What's included

| Path | Purpose |
| --- | --- |
| `data/` | Deterministic generator, 320-flight seed dataset, Snowflake DDL/load script, and validation SQL. |
| `rai_code/manual/` | PyRel ontology, five query/solve acts, and notebooks. |
| `agent/` | Curated Cortex-agent queries and deployment CLI. |
| `RUNNING.html` | Self-contained browser run map with embedded figures. |
| `A-CDM-Decision-Hub-Talk-Track.md` | Modular 18-22 minute speaker script. |
| `DEMO_QUESTIONS.md`, `SNOWSIGHT_DEMO.md` | Operator questions and shorter Snowflake Intelligence flow. |
| `build/generate_demo_figures.py`, `build/figures/` | Figure-generation code and reference PNGs. |
| `prep_demo.py` | Full preflight and warm-up; see its side effects below. |
| `DEMO_RUNBOOK.md` | Deployed object locations, verified prompts, expected answers, and live-demo checks. |

## Prerequisites

- Python 3.13 is the tested version. `requirements.txt` pins the public RelationalAI 1.25.0 release used by the CoWork stored procedures.
- A Snowflake account with the RelationalAI Native App, a warehouse, and permissions to create objects in `ACDM_DEMO` and deploy a Cortex agent if using the agent act.
- A Snowflake CLI connection (default name `rai`) and a RelationalAI `raiconfig.yaml` created for your own account. Neither credentials nor the source machine's local config are included.

## Quickstart

From this directory:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
rai init
snow connection test -c rai
```

Review the target database and schema in `data/out/eham_demo_ddl.sql` before loading. The loader runs `CREATE OR REPLACE` on demo tables and overwrites the staged CSV; it is **not** read-only:

```bash
bash data/load_to_snowflake.sh
snow sql -c rai -f data/out/eham_demo_validation.sql
python -m rai_code.manual.demo_queries
```

For model and Snowflake Intelligence deployment, configure your account's `raiconfig.yaml`, including a unique `deployment.schema`. The current demo deployment uses `BERTOLANI.AIRPORT_OPERATIONS` for the ontology and `BERTOLANI.AIRPORT_OPERATIONS_AGENT` for agent procedures. The agent is `SNOWFLAKE_INTELLIGENCE.AGENTS.AIRPORT_OPERATIONS`. Change those targets in `agent/deploy.py` for another account:

```bash
export RAI_CONFIG_FILE_PATH="$PWD/raiconfig.yaml"
env -u DEBUG rai models deploy --wait
env -u DEBUG ACDM_DISABLE_DEPLOYMENT_CONFIG=1 python -m agent.deploy preflight
env -u DEBUG ACDM_DISABLE_DEPLOYMENT_CONFIG=1 python -m agent.deploy deploy
env -u DEBUG ACDM_DISABLE_DEPLOYMENT_CONFIG=1 python -m agent.deploy chat "Show TOBT violations by handler"
```

The model's deployed tables serve materialized ontology reads. The agent currently evaluates its curated reasoner queries against the same ontology in eager mode: this RAI version does not support prescriptive `Problem.solve()` on a deployed model. Do not describe the optimizer as reading the deployed tables. See `DEMO_RUNBOOK.md` for the tested flow.

`prep_demo.py` is **not a read-only check**: it can warm engines, deploy/update the agent, regenerate figures, and sync a notebook stage. Inspect its flags and targets before running it. Open `RUNNING.html` directly in a browser for the presenter map; it does not require a server.

## Demo arc and claim boundaries

1. **Rules:** flag ready-time (`ARDT`) deviations greater than five minutes from `TOBT`, then audit by ground handler.
2. **Graph:** trace the late `KL1234` flight through aircraft rotation, stand contention, and slot-block relationships.
3. **Heuristic ranking:** rank inbound flights for MS5 gate-conflict attention. This is not a trained forecast, despite the "predictive" act name in the original talk track.
4. **Prescriptive:** assign 47 departures to storm-window slots with HiGHS under runway and pier constraints.
5. **Rule + re-solve:** cap delays for high-connection KL flights at eight minutes and compare with Act 4. In this seed data the cap is already met by the baseline, so the objective remains 1079.6 and KL691 stays at zero delay. Three assignments differ between equal-objective solutions; the cap did not force an improvement.

The talks describe expected seed-data answers, but several original claims are broader than the implemented queries. The `data/out/eham_demo_validation.sql` queries validate source data; `DEMO_RUNBOOK.md` records observed PyRel and CoWork answers and claim boundaries.

## Configuration and safety

The copied demo deliberately excludes `.env`, `raiconfig.yaml`, virtual environments, local RAI state, and previous run logs. Keep your own credentials out of version control. Some source docs predate the current implementation and describe Act 3 as a probability model; the implemented query is the authority for that act. The loader and deployment CLI target named Snowflake objects, so use an isolated demo database or edit those constants before running against another account.
