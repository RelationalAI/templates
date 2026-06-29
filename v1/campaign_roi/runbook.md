# Campaign ROI — Analyst Runbook

A marketing team wants to rebalance a fixed quarterly budget across an existing portfolio of campaigns to lift total conversions — moving money toward the highest-converting campaigns without abandoning any, and respecting a hard cap on a paused region. The dataset is 12 campaigns across 5 regions, each with a current budget and an empirical conversion rate (conversions per $K). The analysis solves a linear program that reassigns every campaign's budget while holding total spend constant.

```text
12 campaigns across 5 regions · current budget ($K) + conversion rate each · $1,130K total
      │
      ▼
/rai-prescriptive-problem-formulation + /rai-prescriptive-solver-management
   • decision: a new budget per campaign, ≥ 0
   • constraints: each campaign within 10%–300% of its current budget;
     total spend ≤ $1,130K (pure reallocation); paused WEST region ≤ 50% of total
   • objective: maximize sum(budget x conversion rate)
   • HiGHS linear program                        -> OPTIMAL, 3,151 conversions (+17.1%)
      │
      ▼
/rai-prescriptive-results-interpretation
   • total budget binds at $1,130K; WEST binds at its $565K cap
   • high-rate campaigns pushed to their 3x ceiling; low-rate ones cut toward their floor
```

Each prompt is pasted into a fresh agent session loaded with the named `/rai-*` skill (named at the start of each prompt). They run in order in a single session — the formulate step reads the `Campaign` concept the build step created, and the interpret step reads the `Campaign.x_budget` decisions the solve wrote back.

---

## 1. Build the ontology

**Prompt:** /rai-build-starter-ontology Build an ontology from `data/campaigns.csv` — each campaign has a name, a region, a current budget (in $K), and a conversion rate (conversions per $K).

**Response:** Loads `Campaign` (12, with `region`, `current_budget`, `conversion_rate`) across 5 regions (CENTRAL 3, SOUTH 3, EAST 2, NORTH 2, WEST 2), totalling $1,130K of current budget; WEST holds the two highest-rate campaigns.

## 2. Examine the ontology

**Prompt:** /rai-querying What concepts and relationships does the ontology have, and how many rows are in each?

**Response:** One concept, `Campaign` (12 rows, with `region`, `current_budget`, `conversion_rate`), spanning 5 regions and $1,130K of total current budget.

## 3. Rebalance the portfolio

**Prompt:** /rai-prescriptive-problem-formulation + /rai-prescriptive-solver-management How should we reallocate the budget across campaigns to maximize total expected conversions, keeping total spend at today's $1,130K? Each campaign's new budget must stay between 10% and 300% of its current budget, and the paused WEST region can get at most 50% of the total. Maximize conversions (budget times conversion rate) and persist the new budgets to the ontology.

**Response:** OPTIMAL (HiGHS), **3,151 expected conversions** — up from the current baseline of 2,691, a **+17.1% lift** — at unchanged total spend. One continuous budget variable per campaign; new budgets are written back as `Campaign.x_budget`. Both the total-budget constraint ($1,130K) and the WEST cap ($565K) bind exactly.

## 4. Read the reallocation

**Prompt:** /rai-prescriptive-results-interpretation Where does the money move, and which constraints decide the shape of the new plan?

**Response:** The optimizer concentrates spend on the highest-converting campaigns — three are pushed all the way to their **3x ceiling** — while the lowest-rate campaigns are cut toward their **10% floor**; every campaign keeps a nonzero budget (the floor guarantees it). The plan is shaped by two binding limits: total spend holds at **$1,130K**, and the paused **WEST region sits at its $565K (50%) cap** even though it holds the two best conversion rates — so WEST's headroom, not campaign quality, is what stops more money flowing there.

## Data

Bundled CSV in `data/`: 12 campaigns with region, current budget, and conversion rate. The budget bounds (10%–300%), total-spend cap, and WEST regional cap are constants in the script. Full model in `campaign_roi.py`.
