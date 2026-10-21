# Follow-On Demo: CoWork, CoWork + Semantic Views, and CoWork + Semantic Views + RelationalAI

## Purpose

This follow-on segment complements the main 5-minute marketplace video. The tone should be partner-positive: Snowflake provides the governed AI and data platform. RelationalAI extends that platform with **Decision Intelligence native to Snowflake**.

The message is:

> We want to be a good partner to Snowflake and show explicitly what customers gain with RelationalAI.

The current positioning is:

> Snowflake brings the data and AI together. RelationalAI brings the business logic to the data.

This is not a "Snowflake versus RelationalAI" comparison. It is a progression across the same Snowflake-native working style:

1. **CoWork**: natural-language analysis, code, SQL, and inspection
2. **CoWork + semantic views**: governed source metrics and better business vocabulary
3. **CoWork + semantic views + RelationalAI**: governed metrics plus governed executable business logic through a RelationalAI-backed Cortex agent

The sharp distinction:

> Semantic views govern metrics. Relational ontologies govern business logic.

## Setup

Use the same telco recovery scenario for all three demos.

The business question is intentionally decision-heavy:

> **Question:** Given tower health, equipment advisories, subscriber impact, call graph, and fixed capex, which towers should we upgrade, why those towers, and what constraint limits the plan?

A complete answer requires more than text generation and more than a single SQL aggregation. It needs:

- Rules to identify visibly degraded or operationally critical towers.
- Prediction to score future equipment and tower failure risk.
- Graph analysis to measure customer impact and influence.
- Path reasoning to trace influential call routes through towers.
- Prescriptive optimization to choose upgrade tiers under budget and install-week constraints.
- Provenance so the user can inspect where the answer came from.
- A correction path so new business logic persists.

## Systems To Compare

### 1. CoWork Baseline

Use this as the Snowflake-native baseline.

Expected strengths:

- Works close to governed Snowflake data.
- Can help generate SQL, inspect schemas, summarize results, and automate data/analytics tasks.
- Can use Snowflake-native capabilities such as code generation, SQL execution, tool use, and inspection depending on configuration.
- Good for getting from a natural-language request to useful analysis quickly.

Expected limitation in this demo:

- Without explicit semantic modeling or executable business logic, the agent can inspect data and propose analysis, but it does not inherently know the telco business ontology or the reasoning chain.
- It may produce a reasonable analytical workflow, but it should not be expected to return the exact optimized recovery plan unless that business logic has been implemented somewhere.

Demo framing:

"This is already valuable. Snowflake keeps the work governed and close to the data. CoWork is a strong way to create, inspect, and iterate on Snowflake-native analytics workflows. But for this umbrella question, CoWork is still being asked to invent or generate the business logic for what 'best tower upgrade plan' means."

### 2. CoWork + Semantic Views

Use this as the governed business-metrics layer. In the demo, make this a **source-only semantic view** built over raw telco operational tables, not over RelationalAI result tables.

Expected strengths:

- Semantic views define governed business dimensions, metrics, joins, and descriptions.
- CoWork and Snowflake agent experiences can use semantic views for natural-language analytics over structured data.
- Better than raw schema inspection because the system has business names, verified metrics, and modeled relationships.
- Good for questions like: "show tower health by region," "rank towers by observed latency and packet loss," or "summarize raw upgrade costs by region" when those measures are modeled.

Expected limitation in this demo:

- Semantic views make source data understandable and queryable, but they do not by themselves create predictive, graph, path, or optimization outputs.
- A source-only semantic view can produce a plausible heuristic shortlist from observable metrics.
- It still cannot decide upgrade tiers under a fixed budget, solve install-week tradeoffs, prove optimality, or return the binding constraint.

Demo framing:

"Semantic views are the right next step. They make dimensions and metrics governable, understandable, extensible, and executable. For many analytics questions, this is exactly what customers need. But the umbrella question is not just 'show me a metric.' It asks the agent to execute business logic: predict risk, reason over a graph, trace paths, and optimize a constrained recovery plan."

### 3. CoWork + Semantic Views + RelationalAI-Backed Cortex Agent

Use this as the full decision-intelligence stack: CoWork for the user experience, semantic views for governed source metrics, and RelationalAI for a Snowflake-native relational ontology plus reasoners.

Expected strengths:

- The agent answers from deployed RelationalAI result tables and curated query tools.
- The model represents connected business concepts: towers, equipment, advisories, subscribers, calls, upgrade options, budgets, and constraints.
- Rules, predictions, graph analysis, path reasoning, and optimization operate over the same ontology.
- The answer includes exact computed outputs, not only a suggested analysis plan.
- Users can inspect provenance and correct durable model logic.
- The agent stays thin because it calls governed, executable business logic instead of recreating that logic in generated code.

Expected result for the telco demo:

- Plan status: `OPTIMAL`
- Total cost: `$4,985,789`
- Capacity restored: `183 Gbps`
- Towers covered: `27`
- Install weeks: `167`
- Binding constraint: `Budget`
- Tier mix: Gold `8`, Silver `8`, Bronze `11`

Demo framing:

"This is where RelationalAI adds to Snowflake. The user still works in CoWork and Snowflake. The data still lives in Snowflake. Semantic views still provide governed metrics where they fit. RelationalAI brings the business logic to the data, so the agent can return a computed decision instead of a generated analysis plan."

## Evaluation Criteria

Use these criteria while narrating the comparison:

| Criterion | CoWork | CoWork + Semantic Views | CoWork + Semantic Views + RelationalAI |
| --- | --- | --- | --- |
| Data proximity | Strong: governed Snowflake environment | Strong: governed Snowflake semantic layer | Strong: deployed into Snowflake workflows |
| Business vocabulary | Depends on schema/docs/instructions | Stronger: metrics and dimensions are modeled | Strongest: ontology captures concepts, rules, relationships, and constraints |
| Exact answer | Can help build analysis | Can rank and summarize source metrics | Can return computed decision outputs |
| Multi-step reasoning | Requires custom code/workflow | Requires custom code or precomputed outputs | Native reasoner workflow across rules, graph, paths, prediction, optimization |
| Provenance | Tool/query/code traces | Semantic view definitions and generated SQL | Tables, curated tools, rules, model logic, and reasoner outputs |
| Durable correction | Update code/instructions | Update dimensions, metrics, descriptions, or verified queries | Update model logic, rules, relationships, constraints, objectives, or curated tools |

## Demo Flow

### 0:00-0:30 — Partner-Positive Frame

"The goal of this follow-on is to be very clear about the partnership story. Snowflake gives customers the governed AI data platform: data, permissions, Cortex, agents, semantic views, and the user experience in Snowflake."

"RelationalAI adds value when the question moves from analytics to decision reasoning. We are not replacing Snowflake. Snowflake brings the data and AI together; RelationalAI brings the business logic to the data."

### 0:30-1:30 — Step 1: CoWork Baseline

Prompt:

> We are a regional telco. We have tower health, equipment advisories, subscriber impact, call graph data, upgrade options, and a fixed capex budget. Which towers should we upgrade, why those towers, and what constraint limits the plan?

Expected behavior:

- The system can inspect available tables and propose SQL or analysis steps.
- It may suggest ranking towers by degraded status, health score, subscriber impact, and advisory exposure.
- It may propose writing SQL, creating views, or building an optimization workflow.
- It should not be expected to return the exact optimal answer unless that model has already been built.

Talk track:

"This baseline is useful. CoWork helps the user work inside Snowflake, write analysis, and reason over the schema. But the answer is still a workflow to build, not a governed decision result. CoWork can help us get started, but the business definition of the decision is not yet encoded."

### 1:30-2:45 — Step 2: CoWork + Source-Only Semantic Views

Prompt:

> Using the source-only semantic view, which towers look like the highest upgrade candidates based on observed health, latency, packet loss, utilization, call activity, and raw upgrade cost?

Expected behavior:

- The semantic view gives the agent clearer business vocabulary over raw source tables.
- It can rank observed operational metrics and summarize regional source data.
- In the tested source-only baseline, it produces a plausible WEST-heavy shortlist: `TWR-0012`, `TWR-0011`, `TWR-0009`, `TWR-0005`, and `TWR-0010`.
- It still cannot decide which tier to choose for each tower, satisfy capex and install-week constraints, prove optimality, or return a binding constraint.

Talk track:

"This is the Snowflake semantic layer doing what it should do. Metrics and dimensions become reusable. The agent has better business context and can produce SQL-grounded answers over source data."

"But the umbrella question is not only 'show me a metric.' It asks which upgrades to choose under constraints, how risk and customer impact interact, and which network paths explain the answer. Semantic views govern metrics. They do not create the full reasoning chain by themselves."

### 2:45-4:15 — Step 3: CoWork + Semantic Views + RelationalAI

Prompt:

> What is the final telco recovery plan summary?

Expected answer:

- Plan status: `OPTIMAL`
- Total cost: `$4,985,789`
- Capacity restored: `183 Gbps`
- Towers covered: `27`
- Install weeks: `167`
- Binding constraint: `Budget`
- Tier mix: Gold `8`, Silver `8`, Bronze `11`

Follow-up prompts:

> Which towers have the highest combined failure risk and customer impact?

> What is the most influential call path and which towers does it use?

> What table or reasoner output supports that answer?

Talk track:

"Now CoWork is no longer just generating analysis or ranking source metrics through semantic views. It can use a RelationalAI-backed Cortex agent/tool layer that calls deployed business logic. The plan summary comes from optimization output. Failure risk comes from prediction. Customer impact comes from graph analysis. Call-path answers come from path reasoning."

"The Snowflake user experience stays the same, but the answer is more complete because RelationalAI supplies a relational ontology and data-aware reasoners behind the scenes."

### 4:15-5:00 — Correction And Persistence

Scenario:

> The business changes the policy: enterprise subscriber exposure should matter more when selecting upgrades, even if raw tower health is acceptable.

Talk track:

"With CoWork, we can ask the assistant to modify code or SQL. With semantic views, we can add or refine metrics and dimensions. Those are both useful Snowflake-native correction paths."

"With RelationalAI, we correct the underlying business logic: update a rule, relationship, derived property, optimization constraint, objective, or curated query. Then redeploy it so future agent answers use the corrected logic."

"That is the added benefit: not only a better answer once, but a governed reasoning asset that improves over time."

## Recommended Demo Questions

Use these questions in sequence:

1. With CoWork: what analysis would you build to decide tower upgrades under budget?
2. With CoWork + source-only semantic views: which towers look like the highest upgrade candidates from observed health, performance, call, and cost metrics?
3. With CoWork + source-only semantic views: summarize source tower health and call activity by region.
4. With CoWork + semantic views + RelationalAI: what is the final telco recovery plan summary?
5. With CoWork + semantic views + RelationalAI: which towers have the highest combined failure risk and customer impact?
6. With CoWork + semantic views + RelationalAI: what is the most influential call path and which towers does it use?
7. With CoWork + semantic views + RelationalAI: what table, rule, or reasoner output supports that answer?
8. With CoWork + semantic views + RelationalAI: if enterprise subscriber exposure should matter more, where would we correct the model?

## Contrast Summary

| Stage | What Customers Get | What RelationalAI Adds |
| --- | --- | --- |
| CoWork | Governed AI workflow close to Snowflake data; code, SQL, inspection, automation | A target reasoning model that CoWork or a Cortex agent can call for exact decision answers |
| CoWork + source-only semantic views | Governed business vocabulary, reusable source metrics, better text-to-SQL | Business logic beyond metrics: prediction, graph, paths, optimization, constraints |
| CoWork + semantic views + RelationalAI | Snowflake-native assistant/agent experience plus governed metrics and computed decision outputs | Relational ontology, rules, graph, paths, prediction, optimization, provenance, and persistent correction |

## Closing Line

"Snowflake gives the customer the governed AI data platform. RelationalAI brings business logic to the data. Together, customers get a Snowflake-native agent that does not just describe the data; it can compute, explain, inspect, and correct the decision."
