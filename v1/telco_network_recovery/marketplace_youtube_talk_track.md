# RelationalAI Marketplace Video Talk Track v0.2

## Positioning

This version is outcome-led. The spine of the story is the telco decision:

> **Given everything we know about the network, and a fixed budget, which towers should we upgrade, and why?**

That is the payoff to reach quickly. The demo should then show that RelationalAI combines the required ontology, rules, reasoning, and optimization behind the scenes, rather than verbally walking through every reasoning type as a separate feature tour.

Core message:

> Snowflake gives agents access to enterprise data. RelationalAI gives them an Ontology Management System: an executable model of how the enterprise works, including the relationships, rules, and reasoning needed to make decisions.

Recommended visual hierarchy:

```text
Snowflake enterprise data
        ↓
RelationalAI ontology
        ↓
Decision reasoning
        ↓
CoWork / Snowflake agent
```

The ontology should appear as the connective tissue, not as one feature among many. CoWork and agent experiences should be framed as consumers of the ontology.

## 5-Minute Script

### 0:00-0:25 — Open With The Decision

**Visual:** Show the telco source tables in Snowflake: towers, equipment, health telemetry, network performance, subscribers, call records, upgrade options, and model advisories.

**Voiceover:**

Every network operator has the same practical question: given everything we know about the network, and a fixed budget, which towers should we upgrade, and why?

That sounds simple, but it is not just a metric. The answer has to combine asset inventory, equipment health, vendor advisories, customer impact, operational policy, and budget constraints. A dashboard can show pieces of that picture. The business needs a decision.

### 0:25-0:55 — The Marketplace Frame

**Visual:** Layered diagram: `Snowflake data -> RelationalAI ontology -> decision -> CoWork / agent`.

**Voiceover:**

This is where RelationalAI fits into the Snowflake Marketplace story.

Snowflake gives the agent access to enterprise data. RelationalAI gives it an Ontology Management System: an executable model of how the enterprise works. The ontology captures the entities, relationships, rules, and reasoning needed to make a decision.

In this demo, CoWork and the Snowflake agent are consumers of that model. They can ask business questions over the ontology, and the ontology gives those questions operational meaning.

### 0:55-1:30 — Build The Business Model

**Visual:** Highlight ontology concepts: `CellTower`, `NetworkEquipment`, `EquipmentModel`, `ModelAdvisory`, `EquipmentHealth`, `NetworkPerformance`, `Subscriber`, `CallDetailRecord`, and `TowerUpgradeOption`.

**Voiceover:**

We start by turning raw telco tables into business concepts.

Cell towers have installed equipment. Equipment belongs to equipment models. Models can have recall or defect advisories. Health readings belong to equipment. Performance measurements belong to towers. Subscribers place calls through towers. Upgrade options describe cost, capacity gain, and installation effort.

That ontology is the connective tissue. It is not a separate reporting layer. It is the executable business model that downstream reasoning and agents consume.

### 1:30-2:05 — Ask The Business Question

**Visual:** Show the user or agent prompt:

> Which towers should we upgrade within the 5 million dollar budget, and why?

**Voiceover:**

Now we can ask the business question directly: which towers should we upgrade within the budget, and why?

The answer has to account for several kinds of evidence. Some towers are visibly degraded. Some equipment looks operational but sits on a recalled or defective model. Some towers carry more customer value and churn risk than others. Some upgrades deliver more restored capacity per dollar. And the final plan still has to fit the budget and crew constraints.

### 2:05-2:45 — Reasoning Behind The Scenes

**Visual:** Keep the ontology at the center. Show reasoning signals feeding into the final decision without turning this into a long feature tour.

**Voiceover:**

Behind the scenes, RelationalAI applies the reasoning required to answer that question.

Predictive reasoning estimates equipment failure risk from health signals, tower context, and manufacturer advisories. Rules identify towers that are operationally critical to restore. Graph analysis measures customer impact by looking at which subscribers route calls through which towers. Optimization chooses the best set of upgrades under the budget and installation constraints.

The important point is not that these are separate features. The important point is that they operate over the same ontology.

### 2:45-3:25 — Concrete Inspection: Recalled Equipment Still Active

**Visual:** Show a compact query/result table for recalled equipment still in active use: equipment id, model, tower, region, recall severity, recall date.

**Voiceover:**

For example, the ontology lets the agent ask a precise operational question: which recalled equipment is still in active use?

That question joins equipment to its model, joins the model to vendor advisories, filters to recall advisories, and checks which equipment is still operational in the network.

In our sample data, the query finds active equipment on recalled models, including Cisco `RTR-A2` and Mediatek `TRX-H1`. This is not just a text lookup. The ontology understands how equipment, models, advisories, and towers relate.

### 3:25-4:20 — The Payoff: Upgrade Plan With Rationale

**Visual:** Show the final plan summary: selected towers, upgrade tiers, total cost, restored capacity, install weeks, binding constraint, and rationale tags.

**Voiceover:**

The final result is an upgrade plan.

For each selected tower, we can explain why it made the cut: visible operational degradation, predicted advisory-driven risk, high customer value at risk, or some combination of those signals.

The plan is constrained by the actual business envelope: a 5 million dollar capex budget and limited installation capacity. So the output is not just a ranked list. It is a feasible decision.

And because the decision comes from the ontology, follow-up questions remain grounded: why was this tower selected, which constraint is binding, which recalled equipment is still active, what would change if the budget increased, or where should we correct the model if enterprise exposure should matter more?

### 4:20-5:00 — Close: Why This Matters For Agents

**Visual:** Return to the layered diagram:

```text
Snowflake data -> RelationalAI ontology -> decision reasoning -> CoWork / agent
```

**Voiceover:**

This is why the ontology matters for agents.

An agent can retrieve rows from Snowflake. But to answer operational questions, it needs to understand how the business works: what entities exist, how they relate, what rules apply, and what reasoning is required to make a decision.

Semantic views are important because they govern business dimensions and metrics. RelationalAI extends that pattern to business logic: relationships, rules, graph reasoning, prediction, optimization, provenance, and correction.

Snowflake gives agents access to enterprise data. RelationalAI gives them an executable model of the enterprise.

In this telco demo, that model turns raw network data into a defensible upgrade decision: which towers to upgrade, within budget, and why.

## Demo Prompts

Use these prompts in sequence if showing the agent experience.

### Prompt 1 — Decision Payoff

> Which towers should we upgrade within the 5 million dollar budget, and why?

Talk track:

This gets to the business outcome immediately. The answer should show selected towers, upgrade tiers, total cost, capacity restored, and the rationale for the selected plan.

### Prompt 2 — Recall Inspection

> Which recalled equipment is still in active use?

Talk track:

This makes the ontology visible. The answer requires the model to understand equipment, equipment models, model advisories, tower placement, and operational equipment status.

### Prompt 3 — Risk And Impact

> Which towers have the highest combined failure risk and customer impact?

Talk track:

Failure risk comes from prediction over equipment health and advisory context. Customer impact comes from subscriber value and call activity. The ontology connects both signals to towers.

### Prompt 4 — Constraint Explanation

> What business constraint limits the plan?

Talk track:

The answer should identify the binding constraint, such as budget, and explain what the optimizer could not select because of that constraint.

### Prompt 5 — Correction Path

> If enterprise subscriber exposure should matter more, where would we correct the model?

Talk track:

This shows why the ontology is durable. We correct the model logic, objective, constraints, or curated query surface, then future agent answers inherit that correction.

## Optional Shorter Close

Use this if the demo is running long:

> Semantic views govern metrics. RelationalAI governs executable business logic. Together with Snowflake and CoWork, that gives agents more than access to data. It gives them a model they can use to compute, explain, inspect, and correct decisions.

