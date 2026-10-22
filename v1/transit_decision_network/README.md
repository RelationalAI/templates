# Transit Decision Network

This is an executable slice of the [decision-intelligence demo plan](DEMO_PLAN.md). A synthetic rail closure creates a bus-bridge dispatch decision. The runner re-solves the case after a dispatcher-style vehicle veto and a partner-style traffic update, with each source snapshot identified by a hash. The data is fictional and aggregate. See [decision-intelligence research](DECISION_INTELLIGENCE_RESEARCH.md) for the Gartner framing and claim boundaries.

## Included now

- `data/generate.py` builds three deterministic CSV snapshots, cumulative input events, SHA-256 manifests, and a **synthetic** review/outcome fixture.
- `transit_model.py` maps the decision case, input events, stops, links, zones, routes, vehicles, drivers, and assignment alternatives into a PyRel ontology. Eligibility is derived by rules, including availability, shift time, and accessible-service qualification.
- `decision_governance.py` adds `DecisionPoint`, `InputSnapshot`, `SnapshotFile`, `CodeAsset`, `PolicyVersion`, `DecisionRule`, `DecisionRun`, `RunSelection`, `DecisionActor`, `DecisionAction`, and `OutcomeObservation` to the same ontology.
- `dispatch.py` solves a mixed-integer dispatch problem with RelationalAI HiGHS. The objective is operating cost plus $250 per unmet rider; budget, one-use resources, service floors, and accessible coverage are constraints.
- `run_demo.py` prints each result, including an accessibility-relaxed counterfactual, verifies arithmetic and coverage, and can append run records with source, model-code, solver-code, policy, and rule fingerprints to a JSONL ledger.
- `decision_history.py` validates that ledger and the synthetic follow-up; `governance_queries.py` runs decision-lineage and estimated-ROI queries in PyRel.
- `transit_decision_deck.html` is a standalone eleven-slide presentation, including the decision ontology and an ROI query.
- `tests/test_data.py` checks data integrity, intended trade-offs, and governance validation. These tests do **not** validate the RAI solver; the live solve and queries below do.

## Run

From this directory, with a working RelationalAI/Snowflake connection and HiGHS reasoner. The checked-in `data/out/decision_runs.jsonl` contains four validated solver results, so you can query the governance ontology without re-solving. The explicit config avoids an older home-level `raiconfig.toml` pointing at a different account:

```bash
env -u DEBUG RAI_CONFIG_FILE_PATH=../telco_network_recovery/raiconfig.yaml ../../.venv/bin/python governance_queries.py --ledger data/out/decision_runs.jsonl
```

To regenerate inputs, test locally, and perform a fresh solve, use a new ledger path:

```bash
env -u DEBUG ../../.venv/bin/python -m data.generate
env -u DEBUG RAI_CONFIG_FILE_PATH=../telco_network_recovery/raiconfig.yaml ../../.venv/bin/python -m unittest discover -s tests -v
env -u DEBUG RAI_CONFIG_FILE_PATH=../telco_network_recovery/raiconfig.yaml ../../.venv/bin/python run_demo.py --ledger data/out/replayed_runs.jsonl
env -u DEBUG RAI_CONFIG_FILE_PATH=../telco_network_recovery/raiconfig.yaml ../../.venv/bin/python governance_queries.py --ledger data/out/replayed_runs.jsonl
```

Substitute another Python environment with RelationalAI installed if needed. `decision_history.py` rejects multiple conflicting versions of the same stage and variant in one ledger; keep each replay in its own file.

The route changes are R5/B07 at closure, R5/B08 after B07 is vetoed, and R6/B08 after the road update. The relaxed-policy counterfactual selects cheap R7 in the South but fails the accessible-service safeguard; it is **not** a dispatchable proposal. A real dispatcher has not approved these synthetic runs. The ledger is a demo artifact, not a tamper-proof audit store.

## Present

Open [transit_decision_deck.html](transit_decision_deck.html) directly in a browser; no server is required. Use the on-screen arrows or keyboard arrow keys to advance. Slide 7 has tabs for the closure, vehicle-veto, and traffic-update snapshots. Slides 8-10 show the `DecisionPoint` ontology, evidence trail, and actor-ROI query. It is a presentation, not a live decision editor or approval interface.

## Decision governance

`DecisionCase` is the continuing problem. A `DecisionPoint` is the moment when an input change requires a choice. The three points (07:30, 07:42, 08:00) link to the triggering event, exact input snapshot and per-file hashes, `transit_model.py` and `dispatch.py` SHA-256 hashes, policy version, budget, and penalty. Each point has one or more `DecisionRun`s; the 07:30 point has both a compliant proposal and a non-dispatchable counterfactual. Runs link to applied rule IDs, selected assignments, and solver results. Separate `DecisionAction` and `OutcomeObservation` concepts hold later human review and follow-up.

```text
DecisionCase -> DecisionPoint -> DecisionRun -> RunSelection
                    |                |  -> DecisionRule
                    |                +----> DecisionAction -> DecisionActor
                    |                +----> OutcomeObservation
                    +-> InputEvent / InputSnapshot -> SnapshotFile
                    +-> CodeAsset (model and solver) / PolicyVersion
```

The follow-up approvals, spending, and disruption costs in `data/out/decision_follow_up.csv` are synthetic scenario data, **not real dispatch or financial observations**. The ROI query includes only approved, policy-constrained runs with follow-up evidence. For each actor it computes `(sum(modeled baseline loss - simulated observed loss) - sum(simulated incremental spend)) / sum(simulated incremental spend)`. The current illustrative result is Morgan Vale: 2 decisions, $19,300 estimated net value, about 135% estimated ROI; Avery Tran: 1 decision, $1,200 estimated net value, 100% estimated ROI. Outcome windows do not overlap. The baseline is modeled, so this ranking is neither causal ROI nor a personnel assessment.

Try `decision_lineage()`, `snapshot_files()`, `solver_code()`, `applied_rules()`, `decision_returns()`, and `actor_roi()` from [governance_queries.py](governance_queries.py). They answer what was known at a point, which safeguard was relaxed in a counterfactual, who approved a proposal, and how the estimated return was calculated. The PyRel model uses the latest snapshot to resolve all three input events; historical route facts should be inspected through each point's pinned snapshot, not through the latest `RouteOption` instance.

## Live validation

On 2026-10-22, the explicit telco config connected to Snowflake, the ontology returned all three zone demands, and all four eager RelationalAI/HiGHS solves completed `OPTIMAL` (HiGHS 1.13.1). The new decision-lineage, actor-ROI, and per-decision-return PyRel queries also completed against that ledger. Seven local tests passed. The `steve_bertolani` engine was `READY` in `RELATIONALAI.API.ENGINES` at the initial validation. No model was deployed.

| Run | South assignment | Operating cost | Objective | Unmet riders | South accessible capacity |
| --- | --- | ---: | ---: | ---: | ---: |
| Closure | R5 / B07 | $15,550 | $15,550 | 0 | 40 |
| Accessibility-relaxed counterfactual | R7 / B09 | $13,050 | $13,050 | 0 | 0 |
| Vehicle veto | R5 / B08 | $16,350 | $16,350 | 0 | 40 |
| Traffic update | R6 / B08 | $15,350 | $16,600 | 5 | 35 |

North remains R1/B01 and Central remains R3/B02. Driver IDs may change between equal-cost optimal assignments. The traffic objective includes a $1,250 unmet-rider penalty, not just operating cost.

## Boundary and next work

This cut uses a fixed demand input and precomputed route-vehicle capacity projection. It does not yet run RAI graph or GNN reasoners, deploy a model or CoWork agent, provide a visual editor or authenticated approval UI, ingest a live partner feed, or monitor real outcomes. The JSONL ledger is not tamper-evident; source and code hashes identify bytes but do not by themselves guarantee replay without preserved dependencies and solver settings. The next slice is graph-derived impact and demand/forecast versioning, followed by application-owned authenticated review, execution, and outcome capture. See `DEMO_PLAN.md` for the full six-capability target.
