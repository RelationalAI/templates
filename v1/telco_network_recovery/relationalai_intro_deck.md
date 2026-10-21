# RelationalAI Intro Deck

## Slide 1 — RelationalAI brings decision intelligence to high-stakes questions

**Claim:** RelationalAI adds decision intelligence over governed enterprise data.

**Talk track:** Rel is a decision agent grounded in your semantic model, running inside Snowflake, and powered by RelationalAI reasoners.

## Slide 2 — The model is Python-backed, not a black box

**Claim:** Your semantic layer is inspectable Python code.

**Proof points:**

- Concepts, properties, relationships, and rules are declared in Python.
- Models can live in source control.
- Developers can test, review, and evolve them like normal software.

## Slide 3 — Extensible by design

**Claim:** RelationalAI lets teams add new logic without replacing the system.

**Proof points:**

- Add new concepts and relationships.
- Add durable business rules.
- Add custom query functions for agents.
- Add reasoner outputs as new tables or model properties.

## Slide 4 — Inspectability is a product feature

**Claim:** You can inspect the model, the relationships, and the query surface.

**Proof points:**

- See what concepts exist.
- Understand how tables and documents connect to business concepts.
- Explain how a property or rule is derived.
- Inspect generated answers through catalog queries and deployed stored procedures.

## Slide 5 — Provenance comes with the answer

**Claim:** Answers are tied back to model concepts, rules, result tables, and reasoner stages.

**Proof points:**

- Plan summary comes from `RESTORE_PLAN`.
- Selected towers come from optimization output.
- Failure risk comes from predictive output.
- Customer impact comes from graph output.
- Call paths come from path reasoning output.

## Slide 6 — Corrections become durable model changes

**Claim:** If the system gets something wrong, you correct the model, not a one-off answer.

**Proof points:**

- Add or refine a rule.
- Update a relationship mapping.
- Add a curated query.
- Turn business intuition into durable logic and redeploy so the correction persists for every future answer.

## Slide 7 — Multiple reasoners, one governed workflow

**Claim:** Infer, anticipate, discover, pathfinding, and optimization can all operate over the same business model.

**Telco example:**

- Infer with rules to flag operationally critical towers.
- Anticipate equipment failure risk with predictive GNN outputs.
- Discover customer impact with graph analysis.
- Find influential call routes with path reasoning.
- Optimize upgrade tiers under budget and install constraints.

## Slide 8 — Telco demo: the question

**Question:** Given tower health, equipment advisories, subscriber impact, call graph, and fixed capex, which towers should we upgrade, why those towers, and what constraint limits the plan?

## Slide 9 — Snowflake agent experience

**Claim:** Business users ask natural-language questions inside Snowflake, while RelationalAI supplies grounded tools behind the scenes.

**Demo prompts:**

- What is the final telco recovery plan summary?
- Which towers have the highest combined failure risk and customer impact?
- Show selected upgrades by region.
- Which equipment items are most likely to fail?
- What is the most influential call path and which towers does it use?

## Slide 10 — Agent answer: final recovery plan

**Question:** What is the final telco recovery plan summary?

**Answer from the system:**

- Plan status: `OPTIMAL`
- Total cost: `$4,985,789`
- Capacity restored: `183 Gbps`
- Towers covered: `27`
- Install weeks: `167`
- Binding constraint: `Budget`
- Tier mix: Gold `8`, Silver `8`, Bronze `11`

**Talk track:** This is the prescriptive reasoner at work. It selected a feasible upgrade portfolio, stayed under the capex envelope, and tells us budget is the constraint that limits the plan.

## Slide 11 — Agent answer: combined risk and impact

**Question:** Which towers have the highest combined failure risk and customer impact?

**Answer from the system:**

| Tower | Failure intensity | Active subscribers | Weighted impact |
| --- | ---: | ---: | ---: |
| TWR-0021 | 9.86 | 32 | 324,669 |
| TWR-0030 | 9.08 | 26 | 76,180 |
| TWR-0067 | 8.05 | 24 | 1,466,615 |
| TWR-0086 | 8.02 | 39 | 1,120,168 |
| TWR-0114 | 6.09 | 34 | 3,125,836 |
| TWR-0015 | 5.06 | 38 | 1,987,444 |

**Talk track:** This combines predictive failure scoring with graph-derived customer impact, so we can distinguish simple failure likelihood from business-critical risk.

## Slide 12 — Agent answer: selected upgrades by region

**Question:** Show selected upgrades by region.

**Answer from the system:**

| Region | Towers | Cost | Capacity | Weeks |
| --- | ---: | ---: | ---: | ---: |
| West | 6 | $1,733,199 | 54 | 49 |
| Central | 4 | $976,697 | 32 | 33 |
| East | 7 | $924,664 | 40 | 35 |
| South | 6 | $828,525 | 34 | 27 |
| North | 4 | $522,704 | 23 | 23 |
| Total | 27 | $4,985,789 | 183 | 167 |

**Talk track:** The agent can decompose the optimization output by the business dimensions users care about: region, spend, restored capacity, and install effort.

## Slide 13 — Agent answer: likely equipment failures

**Question:** Which equipment items are most likely to fail?

**Answer from the system:**

| Rank | Equipment | Failure probability |
| ---: | --- | ---: |
| 1 | EQP-00361 | 99.23% |
| 2 | EQP-01386 | 99.22% |
| 3 | EQP-00382 | 99.22% |
| 4 | EQP-00969 | 99.22% |
| 5 | EQP-00729 | 99.22% |
| 6 | EQP-00169 | 99.22% |
| 7 | EQP-00244 | 99.22% |
| 8 | EQP-00167 | 99.21% |

**Talk track:** This is the predictive reasoner. The agent is not guessing from prose; it is reading deployed prediction results from the governed model output.

## Slide 14 — Agent answer: influential call path

**Question:** What is the most influential call path and which towers does it use?

**Answer from the system:**

- Hub subscriber: `SUB-CON-00900`
- Influence load: `0.00904`
- Subscriber path: `SUB-CON-00900 -> SUB-CON-00814 -> SUB-ENT-0038 -> SUB-CON-00644`
- Tower path: `TWR-0094 -> TWR-0113 -> TWR-0055`

**Talk track:** This is the graph and paths reasoner. It traces the actual relationship path behind the answer, so users can see why those towers matter.

## Slide 15 — Closing

**Claim:** RelationalAI turns a modeled business domain into a governed, correctable, extensible answer system.

**Close:** The value is not just a smarter answer. It is an answer you can inspect, trace, correct, redeploy, and trust.
