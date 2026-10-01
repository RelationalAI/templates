# Delivery-agent live verification and safe operation (draft)

The Python package and oracle can be inspected offline. **No live combined
graph→prescriptive deployment, Snowflake semantic view, Cortex Agent, grants,
or CoWork conversation is claimed.** This is a review checklist until an
approved evaluation account is available. Do not remove the SQL gates,
advertise a runnable ZIP, or merge the upstream PR on offline evidence.

## Roles and preflight

1. **Feature owner / admin:** reconcile deployed prescriptive access for
   pinned `relationalai==1.33.0` with the older "internal only" catalog entry.
   Obtain account-specific approval and verify Graph, solver backend,
   Native App, model deployment, Cortex Analyst/Agent and CoWork entitlement
   in the target region. Check where the PAT **secret object** and EAI are
   provisioned; never place a secret value in this folder or logs.
2. **Admin:** reserve three isolated schemas in an existing demo database:
   `DELIVERY_SOURCES`, `DELIVERY_OUTPUTS`, and
   `DELIVERY_OUTPUTS_META`. Check role ownership, source-table change
   tracking, refresh/PAT user warehouse, `EXECUTE TASK`, relevant inference
   privileges, and separate grants to build, refresh and consume.
3. **SME:** agree that reachability ignores stock, travel is shortest
   *directed* minutes, all deadlines share a dispatch clock, each order is
   whole and uses one depot, and there are unlimited independent dispatches.
   Agree what a solver failure and unsupported hypothetical should say.

## Offline check before spending account resources

From the template root, run the README's pinned install/test/oracle commands.
`from model import model, Depot, Store, Order` constructs declarations and
source bindings in one Python process without a fixture load, write, or solve.
The pinned PyRel directory loader separately loads `model/`; no shared
Python object persists between the CLI and a standalone interpreter.
The oracle's North-open/closed assignments are **proposed ground truth**,
not PyRel observations. Keep the evaluator's gold file away from every
agent, view, tool description, and retrieval source.

## Live model and source validation gate

1. Confirm `scripts/load_fixture.py` targets a **new** schema in a database
   explicitly approved for the demo. Its `00_create_sources.sql` DDL
   autocommits separately from the five data inserts. Inspect data counts and
   keys if any step fails; do not overwrite or drop an unmarked schema.
2. Complete `raiconfig.example.yaml` locally as `raiconfig.yaml` using the
   configuration builder and account owner guidance. Check `model.path:
   model/`, source default schema, published and meta schemas, solver
   identity/warehouse, manual schedule with deploy-time refresh, and table
   materialization. Do not commit local config or credentials.
3. In the **approved** account run `rai models deploy --wait` with pinned
   release. Capture the graph route result, actual materialized object names,
   output columns and case, PKs, solver optimality, and the dependency
   sequence from graph to configured `Problem` to public decisions. One
   prescriptive-only test is not evidence of this combined chain.
4. Directly query the actual objects: one `StoreRouteStatus` row per store,
   one `OrderDecision` row per order, one `PlanSummary`; match both
   revisions, plan assignments and optimum counts against the independent
   oracle. Verify North→A=10, North→B=20, South→B/C=25, no false
   route to A after closure, and B reachable but unselected. Include a
   reachable-but-late case and failed solver/empty candidate cases. Do not
   present a non-optimal plan.
5. With other source writes paused, note the previous refresh run evidence.
   Call `scripts.change_state close` (guarded transaction); check the revision
   increments once. Trigger the same `REFRESH_STANDARD` task, wait for a
   **newer** successful `REFRESH_STATUS()` entry, then check revision and facts
   in both public outputs. Repeat close→reopen for revision 3, and repeat
   refresh without a source change to confirm no stale/no-op false success.
   Verify actual status field names before automating the check. Refreshes
   are eventually consistent, not globally snapshot-isolated.
6. Define the actual snapshot exporter/column mapping for
   `scripts/check_results.py` from observed Snowflake result columns:
   `sources` (all five normalized CSV-shaped tables), `routes` with
   `depot_id,store_id,minutes`, `store_route_status` with
   `store_id,state,revision`, `order_decision` with
   `order_id,store_id,units,deadline_minutes,state,depot_id,arrival_minutes,
   revision`, and `plan_summary` with
   `id,revision,solver_status,completed_orders`. Null chosen depot/arrival
   must be JSON `null`. The script deliberately cannot assert a live
   `REFRESH_STATUS` success without verified fields and run identity:
   preserve the separate refresh trace. Never generate the snapshot from
   the oracle and call it observed data.
   The opt-in `tests/test_live_chain.py` consumes two real snapshot files
   plus normalized refresh-plan/status evidence after an approved run.
   Set `RAI_LIVE_APPROVED=1`, `RAI_LIVE_OPEN_SNAPSHOT`,
   `RAI_LIVE_CLOSED_SNAPSHOT`, and
   `RAI_LIVE_PLAN_AND_REFRESH_EVIDENCE` only when those artifacts exist.
   Its normalized `plan` entries require `id`, `kind` and
   `dependency_ids`; `refreshes` require run IDs, status, source revision,
   start/end times and `source_mutation_at`. This file is skipped offline;
   it does not deploy, query an account, or substitute for inspecting the
   live SQL/agent evidence.

## Semantic interface and browser handoff gate

1. Replace `sql/10_semantic_view.sql` comments **only after** recording the
   real table names/PKs/case. Avoid a fanout between store status and order
   decisions; verify both questions with direct `SEMANTIC_VIEW(...)` SQL
   under a consumer-equivalent role. The SME signs off descriptions,
   count aggregation, and reachable-versus-selected language.
2. Replace `sql/20_create_agent.sql` comments with a tested named
   Cortex Analyst tool bound to that view, evidence-only instructions, and
   verified `orchestration.tool_not_accessible: reject` placement. The
   agent must refuse business-data answers if a tool or solver fails.
   Inspect tool invocation, generated SQL, and actual rows for both
   questions; test a hypothetical depot closure **without** source
   mutation to ensure the agent abstains.
3. Replace `sql/30_grants.sql` comments with reviewed, least-privilege
   statements. Test a role denied the view and a separate role denied its
   underlying published tables. CoWork users need default role/warehouse,
   agent access, and Analyst/read access to the published outputs; a
   missing-tool reject setting cannot catch all underlying-table failures.
   Have the admin expose the tested agent to CoWork and confirm end-user
   wording/UI in that account. A playground-only answer is insufficient.

## Evaluation, recovery and teardown

Use identical prompts in `evaluation/questions.json` before and after the
North source change in all three arms. Freeze settings, permissions and
grading **before** runs; repeat each pair and record per-question
correctness/abstention, SQL trace, source revision and solver status.
Raw-data arms must have tools/data too. Differences between B and C include
**new computed facts**; they cannot be described as pure semantic-lift
measurement. Report ties, uncertainty and failures, not an unverified lift.

If load, solve, refresh, Analyst, permissions, or CoWork handoff fails, pause
the agent demonstration. Do not fill missing rows with hard-coded SQL/Python
answers or trust a `SUCCEEDED` status from a *previous* run. Investigate
only the owned source/target/meta objects with an admin.

For teardown, identify and remove **only** the test agent and reviewed
semantic view using verified account-specific DDL; run `rai models teardown`
with the same local config for PyRel-managed deployment objects. Only then
use `scripts/teardown_sources.py` with a precise typed confirmation. It
rejects unmarked schemas or any objects beyond its five source tables.
