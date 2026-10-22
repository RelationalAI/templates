# Transit Decision Network: goals and demo plan

Status: decision and governance slice validated. See [README.md](README.md) for synthetic snapshots, the PyRel ontology and rules, dispatch formulation, four live RelationalAI/HiGHS solves, and queryable `DecisionPoint` history with synthetic follow-up. The UI, graph and predictive jobs, deployment, and agent are not yet built. The first fixture is intentionally smaller than the full inventory below. [Decision-intelligence research](DECISION_INTELLIGENCE_RESEARCH.md) records the public Gartner framing and our claim boundaries.

## The decision

At 07:30, a rail link closes during the morning peak. The dispatcher asks:

> Which bus-bridge routes, vehicles, and drivers should we dispatch for the next two hours, within an $18,000 operating limit, while preserving accessible service, and why?

This is a decision, not a dashboard metric. The answer depends on network reachability, expected demand, policy, scarce resources, and a human approval. When an accessible bus becomes unavailable or road conditions change, the system must produce a new proposal and explain the difference.

The demo uses a fictional transit agency and wholly synthetic, aggregate data. It is not an operational safety or public-service recommendation.

## Goals

1. **Decision modeling:** Show a visible decision blueprint with named inputs, steps, alternatives, constraints, outputs, and links to later decisions. Represent the operational concepts and relationships in one executable RelationalAI ontology.
2. **Decision collaboration:** Give the agent a proposal role and the dispatcher an approval role. A rejection or override must carry a reason, become a new input, and trigger a new solve; the UI must never silently edit a solver result.
3. **Decision service composition:** Package impact assessment, forecast retrieval, policy screening, optimization, explanation, and outcome checks as reusable services with explicit inputs and outputs. Expose vetted read-only questions to a CoWork agent.
4. **Decision execution:** Run a baseline proposal, a human-constrained revision, and a later re-decision from changed data. Keep model changes separate from scenario runs, and show the path from development to a deployed demo.
5. **Decision monitoring:** Inspect each proposal and approved action, compare predicted and observed outcomes, and raise clear alerts for missing inputs, policy breaches, forecast error, or approval gaps.
6. **Decision governance:** Record actor, timestamps, input snapshot, model/policy/prediction versions, solver status, chosen and rejected alternatives, approval, and outcome. Make the decision replayable and queryable under role-based access.

**Success criterion:** A viewer can trace one selected route from source facts through graph, forecast, rules, and optimization to human approval and observed outcome, then see exactly what changed on re-decision.

## Capability boundary

| Layer | Demo implementation | What we can honestly claim |
| --- | --- | --- |
| RelationalAI / PyRel | Ontology, derived policy rules, graph impact, constrained optimization, curated queries | Executable business meaning and reasoner-backed decision logic over Snowflake data. |
| Predictive job | RAI GNN regression on synthetic historical demand, with a time-based holdout; materialize scored demand for the decision model | A versioned forecast input. Do not call its score calibrated or accurate until evaluated. Current GNN docs say predictive jobs are not part of model deployment, so run this separately. |
| Snowflake + small Python service | Immutable decision-run ledger, snapshots, approval events, outcome observations, API boundary | Per-decision audit and workflow records that **we build**. The RAI model op log tracks model changes, not every dispatch decision. |
| Demo UI | Decision canvas, parameter controls, comparison view, approval screen, alert and provenance drill-down | A purpose-built visual, low-code-like demo surface. Do not present this as a built-in PyRel drag-and-drop authoring or human-workflow engine. |
| CoWork agent | Curated query catalog over the deployed model and decision ledger | Natural-language inspection and explanation. Proposal and approval remain explicit service/UI actions, not autonomous agent side effects. |

The visual blueprint is a readable representation of a versioned Python model and service graph. Editing a displayed threshold creates a new scenario input or policy version; it does not mutate deployed code invisibly. "Real-time" should only be claimed after measured end-to-end latency; the first demo can use batch-refreshed signals and an on-demand solve.

## Synthetic scenario and data

Use a fixed generator seed and a fictional city map. Publish the generator, CSV fixtures, validation checks, and a data dictionary together.

| Source table | Approximate size | Key fields and role |
| --- | ---: | --- |
| STOPS | 24 | Stop ID, line, accessible flag, zone, depot proximity. No passenger identities. |
| RAIL_LINKS and ROAD_LINKS | 32 and 42 | Directed endpoints, travel time, capacity, availability; graph inputs. |
| TRAFFIC_FEED_EVENTS | About 24 | Synthetic partner event ID, road link, travel-time update, event and ingest times; integration and freshness checks. |
| RIDERSHIP_HISTORY | 17,280 | 90 days x 24 stops x 8 peak slots; timestamped aggregate demand and synthetic disruption/weather features. |
| INCIDENTS | 4 | Closure ID, affected rail link, start/end, severity, source event time. One is the live story; others provide history/tests. |
| ROUTE_OPTIONS | 12 | Candidate bus-bridge paths, stops served, duration, cost, capacity and accessible-vehicle requirement. Candidates are data, not free-form agent inventions. |
| VEHICLES and DRIVERS | 12 and 16 | Capacity, accessibility, depot, availability, qualifications, shift limits. |
| POLICY_VERSIONS | 2 | Budget, service floor, accessible coverage, labor limits, review thresholds, effective dates. |
| DEMAND_FORECASTS | 24 per run | Stop/slot forecast, model version, generated time, validation metric, input snapshot ID. |
| DECISION_CASES and DECISION_RUNS | 1 case, several runs | Scenario parameters, model and policy versions, solver status, objective, binding limits, input snapshot hash. |
| RUN_ASSIGNMENTS, APPROVAL_EVENTS, EXECUTION_EVENTS, OUTCOMES | Several rows per run | Selected alternatives, human actions, dispatch facts, observed service and alert results. |

Generation requirements:

- Reserve the last 14 days of RIDERSHIP_HISTORY for a temporal holdout; never train on the incident or outcome being demonstrated.
- Seed a closure of link S08-S09 at 07:30. At 07:42, accessible vehicle B07 becomes unavailable; the dispatcher records a veto with a reason. At 08:00, a synthetic partner traffic event increases travel time on a bridge route. Each event produces a separate run, not a rewrite of the previous one.
- Make a cheapest-only plan fail an accessible-service or minimum-coverage rule, so the constraint has visible decision value. Include one missing forecast and one infeasible scenario to demonstrate safe failure and escalation.
- Do not prewrite the "correct" assignments in the fixture. Generate inputs, solve, and assert that the intended trade-offs actually appear. If they do not, adjust the generator and rerun validation.
- Keep fairness claims narrow: show zone-level service ratios and accessibility safeguards. Do not claim legal equity or bias certification from synthetic data.

## Decision blueprint

The on-screen network is:

Incident signal -> affected stops -> demand forecast -> candidate routes -> policy gate -> optimized proposal -> human review -> dispatch -> observed outcome -> next decision.

The ontology now distinguishes `DecisionCase` (continuing problem), `DecisionPoint` (as-of input change), `DecisionRun` (one evaluated proposal or counterfactual), `DecisionAction` (later human review), and `OutcomeObservation` (later synthetic follow-up). A point links to an event, input snapshot and file hashes, model and solver code hashes, and policy; each run links to its applied rules and selected assignments. A forecast version, authenticated approval, execution event, and real outcome are still future work. Multiple runs can belong to one point, so the policy-relaxed counterfactual cannot be mistaken for an approved decision.

Reasoner handoffs:

1. **Graph:** Build rail and road graphs from links. Identify affected/reachable stops and network bottlenecks. Use graph results to define the impacted set and candidate-route context; do not imply that centrality alone determines the dispatch.
2. **Predictive:** Estimate riders needing bridge service by stop and time slot. Save predictions, model ID, and holdout error as a versioned input table. Begin with a transparent deterministic forecast fixture; replace it with an evaluated RAI GNN job when the core decision loop works.
3. **Rules:** Derive route eligibility, driver qualification, accessible-service requirements, missing-input flags, and human-review triggers. Show the exact input facts and threshold behind each flag.
4. **Prescriptive:** Select vehicle-route and driver-route assignments. Minimize operating cost plus a documented dollar-equivalent penalty per unmet rider, subject to budget, availability, one assignment per resource, capacity, shift limits, minimum zone coverage, and accessible-service constraints. Use explicit slack only where unmet demand is allowed; report it, never hide it.
5. **Explanation:** Return selected assignments, objective components, binding constraints, excluded-option rule reasons, solver status/gap, and counterfactual totals. A solver result does not by itself prove why every unselected option lost; use controlled counterfactual re-solves for that claim.

The dispatch supervisor may reject a proposed route or mark B07 unavailable. That action creates an ApprovalEvent and a new scenario input, then reruns the solver. The approved plan is a distinct DecisionRun. If no feasible plan remains, surface the conflict and require manual escalation instead of publishing an invalid assignment.

## Composable services and controls

| Service | Inputs | Output | Owner |
| --- | --- | --- | --- |
| assess_impact | Incident ID, network snapshot | Affected stops, graph metrics | RAI graph + ontology |
| ingest_partner_traffic | Partner event ID, road link, event time | Versioned travel-time input or stale-feed alert | Application integration + Snowflake |
| forecast_demand | Case ID, time window, model version | Versioned stop forecasts | Separate RAI predictive job; fixture fallback |
| screen_options | Route/vehicle/driver options, policy version | Eligibility and review flags with reasons | RAI rules |
| propose_dispatch | Impact, forecasts, eligible options, budget | Solution, status, costs, coverage, diagnostics | RAI prescriptive |
| review_dispatch | Proposal ID, actor, action, reason | Approval or veto event | Application workflow |
| record_outcome | Approved run, telemetry | Observed coverage, delays, alerts | Snowflake ledger + RAI rules |

Use a typed request/response contract for every service. Simulations are read-only with respect to approvals and dispatch. Only an authenticated human approval may change a proposal into an executable plan. Record the actor and reason even for an emergency override.

## Live demo sequence

1. **Ask the decision.** "Rail service between S08 and S09 is closed. What bus bridges should we dispatch, and why?" Show proposed assignments and uncovered demand before naming the reasoners.
2. **Reveal the blueprint.** Click through the incident, impacted stops, forecast, policies, alternatives, optimizer, and proposed outcome on one connected canvas.
3. **Inspect evidence.** Show an affected path, a forecast with its model version and holdout metric, and the policy rule that removes one candidate route.
4. **Show the trade-off.** Compare cheapest-only against policy-constrained proposals. Display budget, vehicle use, expected uncovered riders, and accessible coverage.
5. **Hand off to a person.** The dispatcher rejects a route because B07 is unavailable. Re-solve and show a side-by-side run diff and the recorded approval.
6. **Monitor and adapt.** Ingest the 08:00 partner traffic update and observed service. Raise an alert if a threshold is crossed or the feed is stale, create a new run, and show what changed and who accepted it.
7. **Ask CoWork.** Query the ledger and ontology: "Why did the approved plan change, what evidence did it use, and did it meet the service floor?"

Example agent questions: Which stops became critical after the closure? Which routes failed policy and why? What does the current forecast predict? Which constraints bind the $18,000 plan? What changes at $20,000? Who approved the revised plan? Which outcomes breached a threshold? Trace run R2 to its source snapshot and versions.

## Build order and acceptance checks

1. **Data and baseline:** Write deterministic generator, schemas, integrity checks, and one hand-calculated tiny case. Prove every foreign key and timestamp is valid. No Snowflake deployment yet.
2. **Ontology and rules:** Map the sources to typed concepts; test eligibility and safeguard edge cases. Verify the model exposes every field used by later services.
3. **Graph and optimizer:** Test affected-stop results and a small solver instance against a hand-checked answer. Validate budget, capacity, accessibility, staffing, infeasibility, and solution status. Fix tie-breaking or record solver settings before promising replay equivalence.
4. **Decision ledger and UI:** Store append-only runs and approval/outcome events. Build the decision canvas, parameter controls, plan diff, evidence panel, and role-gated review. Verify replay from a pinned snapshot and that an unapproved plan cannot be dispatched.
5. **Agent and deployment:** Deploy stable ontology outputs to a dedicated Snowflake schema, keep model op-log history enabled, register curated CoWork queries, and validate every live question. Use separate development and demo schemas/roles; do not call this a production workflow.
6. **Prediction and monitoring:** Train/evaluate the GNN in a separate job, materialize forecasts, compare with the deterministic fixture, then wire threshold alerts and observed-outcome checks. Only use the trained model in the live decision if its holdout result is defensible.

The first shippable cut is steps 1-4 with deterministic forecast input. Steps 5-6 extend the same decision model; they are not separate demos. Capture expected rows, solver totals, and screen states only after an end-to-end run succeeds.

## Sources and implementation notes

- [PyRel semantic modeling](https://docs.relational.ai/get-started/start-building-with-pyrel)
- [Graph API](https://docs.relational.ai/api/python/v1.31/semantics/reasoners/graph/core/graph_class/)
- [Prescriptive Problem API](https://docs.relational.ai/api/python/v1.23/semantics/reasoners/prescriptive/problem/problem_class/)
- [GNN API and deployment limitation](https://docs.relational.ai/api/python/v1.35/semantics/reasoners/predictive/gnn_class/)
- [Model deployment and op-log lifecycle](https://docs.relational.ai/build/guides/modeling/deploy-a-model)
- [CoWork curated query catalog](https://docs.relational.ai/api/python/v1.35/agent/cortex/queries/queries_class/)
- [Gartner's public Decision Intelligence Platforms description](https://www.gartner.com/reviews/market/decision-intelligence-platforms)

Pin and test a RelationalAI version when implementation starts; the local templates environment currently uses 1.30.3, while the linked API pages describe several versions. Verify the exact predictive and deployment behavior on the target account before promising it in a live presentation.
