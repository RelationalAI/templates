# Ad Spend Allocation — Analyst Runbook

A marketing team wants to split an advertising budget across channels and campaigns to maximize expected conversions, and wants to see how the best allocation shifts as the total budget grows. The dataset is 5 channels (each with min/max spend thresholds), 3 campaigns (each with its own budget), and the 15 channel-campaign conversion rates. The analysis solves a mixed-integer program that sets the spend on every channel-campaign pair, sweeping three total-budget levels ($35k, $45k, $55k) in a single solve.

```text
5 channels (min/max spend) · 3 campaigns (budget) · 15 channel-campaign conversion rates
      │
      ▼
/rai-prescriptive-problem-formulation + /rai-prescriptive-solver-management
   • decisions: spend per (channel-campaign, budget level) + binary "fund this pair?"
   • constraints: spend within channel min/max when funded; per-campaign budget;
     ≥ 1 funded channel per campaign; total spend ≤ the scenario's budget level
   • objective: maximize sum(spend x conversion rate)
   • budget levels $35k / $45k / $55k in one solve · HiGHS  -> OPTIMAL, 9,740 conversions
      │
      ▼
/rai-prescriptive-results-interpretation
   • $35k and $45k levels spend their full budget; the $55k level spends only $45k
   • diminishing returns — beyond $45k there's no profitable pair left to fund
```

Each prompt is pasted into a fresh agent session loaded with the named `/rai-*` skill (named at the start of each prompt). They run in order in a single session — the formulate step reads the `Channel`/`Campaign`/`Effectiveness` concepts the build step created, and the interpret step reads the spend decisions the solve wrote back.

---

## 1. Build the ontology

**Prompt:** /rai-build-starter-ontology Build an ontology from `data/channels.csv` (each channel has a min and max spend), `data/campaigns.csv` (each campaign has a budget), and `data/effectiveness.csv` (the conversion rate — conversions per dollar — for each channel-campaign pair). Model effectiveness as a relationship linking a channel and a campaign to its conversion rate.

**Response:** Loads `Channel` (5: Search, Social, Display, Video, Email — each with `min_spend`, `max_spend`), `Campaign` (3: Brand_Awareness $15k, Product_Launch $20k, Seasonal_Sale $10k), and `Effectiveness` (15, every channel-campaign pair, with `conversion_rate` 0.03–0.12).

## 2. Examine the ontology

**Prompt:** /rai-querying What concepts and relationships does the ontology have, and how many of each?

**Response:** Three concepts — 5 `Channel` (min/max spend), 3 `Campaign` (budget), and 15 `Effectiveness` (one conversion rate per channel-campaign pair).

## 3. Allocate spend across budget levels

**Prompt:** /rai-prescriptive-problem-formulation + /rai-prescriptive-solver-management How should we spend across each channel-campaign pair to maximize total expected conversions, at three total-budget levels — $35k, $45k, and $55k — solved together? Use a continuous spend per pair and a binary "fund this pair" decision: when a pair is funded its spend must sit within that channel's min and max, each campaign's spend across channels can't exceed its budget, every campaign needs at least one funded channel, and total spend can't exceed the budget level. Model the budget level as a first-class scenario concept with the spend indexed by (pair, level). Maximize conversions and persist the spend to the ontology.

**Response:** OPTIMAL (HiGHS), combined **9,740 conversions** across the three budget levels (relative gap 0.0). 90 variables (45 continuous spend + 45 binary funding) and 111 constraints; spend and funding are written back as `Allocation.x_spend(Scenario)` and `Allocation.x_active(Scenario)`.

## 4. Read the allocation across budget levels

**Prompt:** /rai-prescriptive-results-interpretation How much of each budget level actually gets spent, and what does that say about diminishing returns?

**Response:** The $35k and $45k levels both spend their **entire** budget (the cap binds), but the **$55k level spends only $45k** — its allocation is identical to the $45k case. Beyond $45k there's no remaining channel-campaign pair whose conversion rate justifies more spend (per-campaign budgets and per-channel max-spend are exhausted on the profitable pairs), so the extra $10k sits idle. The marginal budget stops buying conversions at $45k.

## Data

Bundled CSVs in `data/`: 5 channels, 3 campaigns, 15 effectiveness rows. The three budget levels ($35k, $45k, $55k) are defined in the script. Full model in `ad_spend_allocation.py`.
