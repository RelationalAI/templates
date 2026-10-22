# Decision intelligence research for the transit demo

Research checked 2026-10-22. This note uses Gartner's public market description and research abstracts, not paywalled report text. The design recommendations below are our interpretation, not Gartner certification or an endorsement of this demo.

## What Gartner says

Gartner's [Decision Intelligence Platforms market page](https://www.gartner.com/reviews/market/decision-intelligence-platforms) describes platforms that combine data, analytics, knowledge, and AI around explicit decisions. The published feature list covers decision modeling, reusable decision services, human and automated execution, governance, and monitoring with outcome assessment. It mentions graphs, rules, optimization, simulation, and ML among possible techniques, not as a requirement that each decision use all of them.

The public abstract of [Leverage Decision Intelligence for Effective D&A Governance](https://www.gartner.com/en/documents/6989666) argues that decision governance improves the quality and outcomes of data, analytics, and AI. The public abstract of [Decision Governance Mitigates Risks of Generative AI Agents](https://www.gartner.com/en/documents/6993466) emphasizes accountability for automated choices and agent risk. Neither abstract supplies an implementation schema; our `DecisionPoint` design is a demo-specific interpretation.

Gartner's [2025 data and analytics trends release](https://www.gartner.com/en/newsroom/press-releases/2025-03-05-gartner-identifies-top-trends-in-data-and-analytics-for-2025) recommends prioritizing important decisions, using complementary techniques such as graphs and optimization, and addressing ethics, legal, and compliance concerns in automation.

## Design implications

| Capability | Transit demo evidence | Still needed for a production claim |
| --- | --- | --- |
| Decision modeling | `DecisionPoint` separates a business moment and its known inputs from multiple `DecisionRun` evaluations. PyRel links the case, trigger, input snapshot, code assets, policy, rules, and proposal. | Visual authoring, versioned blueprint management, and change approval. |
| Collaboration | Explicit human review records, distinct from solver output and upstream event actors. | Authenticated identity, delegation, escalation, and override workflow. |
| Composition | Generator, ontology, policy rules, solver, and governance queries have separate responsibilities. | Discoverable service contracts and production integration. |
| Execution | RAI/HiGHS computes proposals on pinned synthetic snapshots. | Deployment, production orchestration, and execution evidence. |
| Monitoring | Follow-up observations can be joined to approved decisions; cost and benefit are queryable. | Real telemetry, alert thresholds, quality checks, and drift monitoring. |
| Governance | File hashes, model/solver source hashes, policy and rule IDs, review actors, timestamps, and outcomes form a queryable trail. | Tamper-evident storage, access control, retention, and independent audit. |

## Why `DecisionPoint` is separate

A `DecisionCase` is the continuing closure problem. A `DecisionPoint` is what the organization knew when a new choice was needed (07:30 closure, 07:42 vehicle veto, 08:00 traffic update). A point can have multiple `DecisionRun`s: the 07:30 point has both the policy-constrained proposal and a deliberately non-dispatchable accessibility-relaxed counterfactual. A later human review is a `DecisionAction`, not an optimizer result. A later outcome belongs to the approved run, not to every candidate at that point. This separation prevents a counterfactual or an unapproved proposal from being credited as business value.

Minimum decision-time evidence: event ID and time; input snapshot hash and per-file hashes; exact `transit_model.py` and `dispatch.py` SHA-256 hashes; policy version and numeric parameters; applied rule IDs; solver status and selected assignments; and an explanation of the proposal. Code hashes identify source bytes, not a deployable artifact or a reproducible environment by themselves. Replaying a decision also requires preserved source files, dependencies, solver version/settings, and any external data.

## ROI question and its limits

For the demo, *estimated decision ROI* is `(modeled baseline disruption cost - simulated observed disruption cost - realized incremental spend) / realized incremental spend`. Roll up by **summing dollar benefits and spend first**, then divide; averaging per-decision percentages would weight tiny and large decisions equally. Only approved, simulated-executed runs with a follow-up observation qualify. The accessibility-relaxed run is excluded. Non-overlapping outcome windows reduce double counting across the three re-decisions of one case.

This is an illustrative, synthetic comparison, **not measured or causally established business ROI**. Avoided loss requires a counterfactual baseline, so changing its assumptions can change the ranking. With one small case and a few actors, the answer demonstrates ontology traversal and accountable metric construction, not personnel performance. For a real ranking, add independent cases, actual dispatch/telemetry and finance data, a documented attribution method, comparable windows, uncertainty, and minimum sample sizes.

## Questions the ontology should support

1. What was known at `DP-...`? Trace it to the exact snapshot files and code hashes.
2. Which rules and policy parameters were in force, and which run relaxed a safeguard?
3. Which proposal was approved, by whom, when, and with what rationale?
4. What changed between the 07:30, 07:42, and 08:00 points?
5. Which actors' **approved synthetic decisions** have the highest estimated return, and what observations and assumptions support that answer?

## Source access boundary

The linked Gartner market page and public abstracts were accessible on 2026-10-22. Full client research was not accessed. The capability mapping above is a paraphrase of public material plus our own implementation choices.
