---
title: "Delivery planning with a model-backed agent"
description: "Explore directed reachability and whole-order delivery planning in a synthetic PyRel model; Snowflake agent deployment awaits account verification."
private: false
experience_level: advanced
industry: Supply Chain & Logistics
reasoning_types:
  - Graph
  - Prescriptive
tags:
  - delivery
  - optimization
  - agent
  - evaluation
---

## What this template is for

Delivery planners need to distinguish a store with **no directed path from an
open depot** from a store whose orders are reachable but not selected for the
best stock-constrained plan. This synthetic example defines graph routes and a
maximum-*whole-order* decision problem in PyRel, then proposes a narrow
Snowflake Cortex Analyst/Cortex Agent/CoWork handoff over published outputs.
The agent reads selected, refreshed results, **not** arbitrary PyRel code.

**Draft, not a public runnable integration.** The offline fixture/oracle,
declarative model package, and source scripts are available for review. The
combined graph-to-scheduled-solver deployment, output schema, semantic view,
agent, grants, and CoWork access have **not** been tested in an approved live
account. SQL files `10`, `20`, `30`, and `90` are intentionally non-runnable
gates, not a substitute for verified account-specific SQL. Do not publish the
agent or use its recommendations until every gate in [runbook.md](runbook.md)
is cleared. Model deployment is Public Preview; prescriptive access must be
approved separately. Do not treat this as a production decision workflow.

## Who this is for

- A Python/Snowflake model author runs offline checks and, after approval,
  deploys and validates the PyRel model in a dedicated demo environment.
- An account administrator provisions least-privileged access and reviews the
  later semantic view/agent setup.
- A delivery SME signs off on the business meanings and observed answers.
- An authorized planner eventually uses only CoWork once the live gate passes.

## What you'll build

Five source tables encode two depots, three stores, directed roads through a
hub, four orders, and one increasing source revision. `model/schema.py` owns
the declarations, weighted directed shortest paths, on-time and full-stock
candidate pairs, a named binary `Problem`, and derived status/decision/summary
objects. `model/sources.py` binds Snowflake tables at import without reading
CSV data or solving. `model/__init__.py` loads schema then bindings and exports
`model`, `Depot`, `Store`, and `Order` for other processes.

The solver maximizes **number of complete orders**, not units: an order has at
most one depot; each depot's selected orders consume no more than its stock.
An on-time route alone does not promise stock or selection. The sample makes
unlimited separate dispatches and one SKU explicit simplifications; there is
no driver, vehicle, split shipment, or arbitrary what-if service. For larger
cases equally optimal assignment sets can exist even when the count is unique.
Only `OPTIMAL` permits a recommendation; timeout/failure means stop.

## What's included

- **Schema and sources**: [`model/`](model/) with all business rules in
  `schema.py`, Snowflake bindings in `sources.py`, and ordered package exports.
- **Fixture**: five synthetic [`data/`](data/) CSV files; no customer data.
- **Source changes**: guarded `scripts/load_fixture.py` and
  `scripts/change_state.py`; SQL `00`, `40`, and `41` document their scope.
- **Verification**: an independent Dijkstra/brute-force oracle in
  `evaluation/check_oracle.py`, fail-closed snapshot comparator
  `scripts/check_results.py`, and offline unit tests.
- **Account-gated handoff**: `raiconfig.example.yaml`, deliberately
  non-executable semantic-view/agent/grant/teardown SQL drafts, and a
  [runbook](runbook.md). `evaluation/` contains paired prompts, a blank
  scorecard, bounded held-out cases, and a separate gold key.

## Prerequisites

- Python 3.12, a clean environment, and exact `relationalai==1.33.0` from
  `pyproject.toml`. This version's package import and directory loader have
  been exercised **offline**; the combined deployment has not.
- For the **later, gated** account trial: an isolated existing Snowflake
  database and a saved Snowflake Connector connection profile authenticated
  outside this folder; Native App and graph access; by-request prescriptive
  solver enablement; approved refresh identity, secret object and external
  access integration; Cortex Analyst/Agent/CoWork regional entitlement and
  administrator-reviewed grants. Do not copy secret material into a config,
  ZIP, example command, output log, or PR.
- A delivery SME must approve the reachability/stock/deadline definitions,
  the output wording, and the observed open/closed plan.

## Quickstart

1. **Offline review (no account needed):** from this template directory,
   install the pinned runtime and connector into a fresh environment.

   ```bash
   python3.12 -m venv .venv
   .venv/bin/python -m pip install -e '.[fixture]'
   .venv/bin/python -m unittest discover -s tests -p 'test_*.py'
   .venv/bin/python evaluation/check_oracle.py
   ```

   The oracle independently checks the proposed fixture: when North is open,
   all stores are reachable and the maximum whole-order count is three
   (North→A1, South→C1/C2); when North is closed, A is unreachable and the
   count is two (South→C1/C2). North→B takes 20 minutes and South→B/C takes
   25 minutes; B remains reachable but unselected. **These are offline
   expectations, not observed PyRel/Snowflake output.** The tests also check
   zero/one/all closed depots, reversed roads, late deliveries, inventory
   competition, ties, failed solver status, and stale/mixed revisions.

2. **Stop here unless the account and feature owner have approved a live
   spike.** Have an admin inspect the exact source and output schema names and
   privilege boundaries in [runbook.md](runbook.md). Complete a local
   `raiconfig.yaml` from `raiconfig.example.yaml`; keep that local file and all
   connection credentials **outside the downloadable/committed files**.
   `model.path: model/` loads the *package directory*; import and CLI
   processes each construct their own model, not a shared in-memory object.

3. **Account-gated source setup:** with an existing Connector profile and
   only after confirming the database is dedicated, load a *new* source
   schema (the loader refuses any existing schema):

   ```bash
   .venv/bin/python -m scripts.load_fixture \
     --connection YOUR_SAVED_PROFILE --database YOUR_DEMO_DATABASE
   ```

   The loader checks IDs, road weights, source keys and counts, writes only
   the five tables under `DELIVERY_SOURCES`, and marks schema ownership.
   Source DDL may commit before the data transaction; on failure, inspect
   the partially created marked schema rather than blindly rerunning. No CSV
   is loaded on `import model`.

4. **Live gate, not a copy/paste deploy recipe yet:** in the approved
   environment test directory loading and graph→prescriptive dependencies;
   verify the actual output names/keys and the latest `REFRESH_STATUS()` after
   `rai models deploy --wait` on `1.33.0`. The example config uses one manual
   schedule (`interval_s: 0`, deploy-time initial run, `type: table`); the
   refresh task is not an instant freshness guarantee. A periodic schedule
   is a later adaptation. Do not run a comparison or agent on stale,
   non-optimal, missing, or mixed-revision outputs.

5. **Only after a live schema/permissions review:** replace the gated SQL
   drafts with a tested complete `CREATE SEMANTIC VIEW`, `SEMANTIC_VIEW(...)`
   checks, Cortex Analyst tool/agent definition, and scoped grants. Verify
   SQL rows and tool traces for both prompts in
   [`evaluation/questions.json`](evaluation/questions.json), then test as a
   least-privileged CoWork user. The consumer needs a default role and
   warehouse plus access to the view **and its underlying published tables**;
   view access alone does not suffice.

6. **Later source-change trial:** while all other writes are paused, use
   `.venv/bin/python -m scripts.change_state close --connection
   YOUR_SAVED_PROFILE --database YOUR_DEMO_DATABASE`, trigger the *same*
   manual refresh task, then verify a **later** successful run and a newer
   revision on **both** public result sets. Re-ask the **identical** two
   prompts. Reopening North uses `reopen` and increments the revision again,
   never resets it. `scripts/check_results.py` accepts an actual,
   account-exported JSON snapshot normalized to the documented columns;
   its snapshot exporter and the exact column mapping remain a **live
   blocker**. It refuses failed solver status and inconsistent results.

## Sample data

| Source | Representative synthetic facts |
| --- | --- |
| Depots and roads | North (stock 2)→A 10, →B 20; South (stock 4)→Hub 10; Hub→B/C 15. All edges are directed. |
| Orders | A1 needs 2, B1 needs 4, C1/C2 need 2 each; every deadline is 60 minutes from dispatch. |
| State | Revision starts at 1 and advances when a guarded source change commits. |

Closing North removes both its routes and its stock. Geographical
reachability ignores stock; eligibility for a full on-time order does not.

## Model overview

`Node`, `Depot`, `Store`, `Road`, and `Order` are base facts from dedicated
tables. The directed weighted `Graph` finds shortest travel times from
currently open depots. The configured `Problem` chooses whole orders from
eligible open-depot routes within stock. `StoreRouteStatus` includes every
store, including unreachable stores; `OrderDecision` includes every order
only after an optimal solve. Unselected decisions intentionally lack a chosen
depot and arrival; reachable but late and insufficient-stock states are
distinct. `PlanSummary` carries solver status and revision; its count should
be trusted only with an optimal solve.

## How it works

```text
source tables → model/sources.py → model/schema.py graph/solver
              → deployed outputs [LIVE GATE]
              → reviewed semantic view [LIVE GATE]
              → Cortex Analyst in Agent → CoWork [LIVE GATE]
```

`raiconfig.example.yaml` names a separate operational meta schema; never
attach that schema to Analyst. The published output schema is not itself
a Snowflake semantic view or an agent. Even after one refresh succeeds,
users querying during a later refresh can see eventually consistent data;
this example does not enforce a globally atomic freshness barrier.

## Troubleshooting and cleanup

- If import fails, use the pinned environment and run
  `.venv/bin/python -c 'from model import model, Depot, Store, Order'`;
  this imports definitions only, not a live solver result.
- If deployment, configured solve, or refresh fails, **stop**. Do not label
  feasible/timed-out assignments optimal; inspect the verified refresh
  status/solver diagnostics and retry only after the owner approves.
- If an Analyst query is empty or denied, check view and underlying-table
  grants separately. An inaccessible-tool policy does not cover every
  query-time error; do not let the agent answer from guesses.
- The default agent answers the *current published world*, not a hypothetical
  depot closure before a new source change and completed refresh.
- Before cleanup, verify ownership. Have an admin remove only the reviewed
  agent/view; use `rai models teardown` for managed deployment objects.
  `.venv/bin/python -m scripts.teardown_sources --connection
  YOUR_SAVED_PROFILE --database YOUR_DEMO_DATABASE --confirm
  YOUR_DEMO_DATABASE.DELIVERY_SOURCES` removes only the specifically marked
  five-table source schema with no unexpected objects; never drop shared data.

## Evaluation

Three matched arms are specified in [`evaluation/arms.sql`](evaluation/arms.sql)
as a **non-runnable protocol**, not three active agents: (A) minimally
described raw-data semantic view, (B) the same raw data plus reviewed
definitions, and (C) the same definitions plus derived outputs. All arms
need equally scoped evaluation data access, the same prompts and settings,
and a separately held gold key. Generate bounded additional cases with
`python -m evaluation.generate_cases --cases-output <new-local-case-file>
--gold-output <different-new-local-key-file>` and do not give the gold file
to any agent. Repeat each question per state/arm, record tool/SQL evidence,
correctness, calibrated abstention, latency/cost, and fixed/broken/net per
question in the blank [`scorecard.csv`](evaluation/scorecard.csv). The tiny
fixture is an inspectable demo, **not** an accuracy benchmark. Cases above
the brute-force bound are ungraded for optimality.
