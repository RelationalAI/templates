---
title: "Ad Spend Allocation"
description: "Allocate a marketing budget across advertising channels and campaigns to maximize expected conversions. Sweeps three budget levels in a single solve to show where extra budget stops paying off."
featured: false
experience_level: intermediate
industry: "Retail & Consumer"
reasoning_types:
  - Prescriptive
tags:
  - Budget Allocation
  - Mixed-Integer Programming (MIP)
  - Marketing
  - What-If Analysis
  - Scenario Analysis
---

## What this template is for

Marketing teams face a recurring challenge: how to distribute a limited budget across multiple advertising channels and campaigns to get the most conversions. Each channel (search, social, display, video, email) has different minimum and maximum spend thresholds, and each channel-campaign combination has a different conversion rate. The goal is to find the spend allocation that maximizes total expected conversions while respecting per-channel bounds, per-campaign budgets, and an overall budget cap. Guessing at this by hand leaves conversions on the table; a small change in the mix can move the outcome more than a small change in the total budget.

This template also answers the follow-up question every planner asks: if we had more budget, would it help? It sweeps three total-budget levels ($35K, $45K, $55K) so you can see how additional budget translates into incremental conversions and which channels the optimizer activates at each level — often revealing that beyond a point the extra money buys nothing.

**Under the hood it uses prescriptive reasoning: a mixed-integer program where binary variables decide which channel-campaign pairs to fund and continuous variables set the spend, solved for all three budget levels at once.**

## Who this is for

- Marketing analysts optimizing media spend across channels.
- Growth teams evaluating budget scenarios for campaign planning.
- Data scientists building prescriptive models for advertising optimization.
- Developers learning mixed-integer programming (MIP) with RelationalAI.
- **Assumed knowledge**: comfortable reading Python. The marketing and optimization terms are explained as they come up, and no prior RelationalAI experience is required to run it.

## What you'll build

- A funded spend allocation across every channel-campaign pair that maximizes total expected conversions within per-channel, per-campaign, and total-budget limits, produced by **prescriptive reasoning** (mixed-integer program).
- Channel activation logic that enforces minimum and maximum spend only when a pair is funded, using binary decision variables.
- A `Scenario` concept that drives three budget levels through a single solve, so the whole what-if sweep is one optimization rather than three.
- A per-scenario allocation table you can query from the ontology after the run, showing which pairs are funded and at what spend.

## What's included

- **Model**: a single ontology with `Channel`, `Campaign`, `Effectiveness`, `Scenario`, and an `Allocation` decision concept — plus the prescriptive formulation (decision variables, constraints, objective) that runs on it.
- **Runner**: `ad_spend_allocation.py` — one Python script that loads the CSVs, builds the model, solves all scenarios at once, and prints the allocation table.
- **Runbook**: `runbook.md` — a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the script itself.
- **Sample data**: 5 channels with spend bounds, 3 campaigns with budgets, and the 15 channel-campaign conversion rates. See *Sample data* below.
- **Outputs**: solver termination status, objective value, and a per-scenario table of non-trivial spend allocations printed to stdout; the spend and funding decisions are also written back to the ontology as queryable properties.

## Prerequisites

### Access

- A Snowflake account with the RelationalAI Native App installed.
- A Snowflake user with permissions to access the RelationalAI Native App.

### Tools

- Python >= 3.10.
- RelationalAI Python SDK (`relationalai == 1.0.14`).

## Quickstart

1. Download the template and extract it:

   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/ad_spend_allocation.zip
   unzip ad_spend_allocation.zip
   cd ad_spend_allocation
   ```

   > [!TIP]
   > You can also download the template ZIP using the "Download ZIP" button at the top of this page.

2. Create a virtual environment and activate it:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   ```

3. Install dependencies:

   ```bash
   python -m pip install .
   ```

4. Configure your RelationalAI connection:

   ```bash
   rai init
   ```

5. Run the template end-to-end:

   ```bash
   python ad_spend_allocation.py
   ```

6. Expected output. A per-scenario allocation table confirms a successful run (trimmed to the first budget level here; the full run also prints the $45K and $55K scenarios):

   ```text
   Spend allocation per scenario:
       scenario channel         campaign    spend
     budget_35k   Email  Brand_Awareness   2000.0
     budget_35k   Email    Seasonal_Sale   2000.0
     budget_35k  Search   Product_Launch  10000.0
     budget_35k  Search    Seasonal_Sale   8000.0
     budget_35k  Social  Brand_Awareness   3000.0
     budget_35k   Video   Product_Launch  10000.0
   ```

   All three budgets invest heavily in Search and Video (highest ROI channels). The $35K budget activates 6 channel-campaign pairs. The $45K and $55K budgets add Search Brand_Awareness ($5K) and increase Social Brand_Awareness to $8K — diminishing returns mean the extra $10K from $45K to $55K produces no new activations. See `runbook.md` for the full printout and a step-by-step walkthrough.

## Template structure

The tree below shows the top-level layout:

```text
ad_spend_allocation/
├── ad_spend_allocation.py   # Main script (ontology, formulation, single-solve scenario sweep)
├── data/
│   ├── channels.csv         # 5 channels with min/max spend and ROI coefficient
│   ├── campaigns.csv        # 3 campaigns with budget and target conversions
│   └── effectiveness.csv    # 15 channel-campaign conversion rates
├── README.md                # this file
├── runbook.md               # analyst-facing paste-testable walkthrough
└── pyproject.toml           # dependencies
```

**Start here**: run `python ad_spend_allocation.py` for the full run end to end, or follow `runbook.md` to reproduce it step by step with the RAI skills.

## Sample data

The bundled data is synthetic and illustrative — designed to teach the optimization flow, not to match a specific advertiser's account.

- **`channels.csv`** (5 rows) — the marketing channels (Search, Social, Display, Video, Email), each with a minimum and maximum spend and an ROI coefficient.
- **`campaigns.csv`** (3 rows) — the campaigns (Brand_Awareness, Product_Launch, Seasonal_Sale), each with a budget and a target-conversions figure.
- **`effectiveness.csv`** (15 rows) — one row per channel-campaign pair, giving the conversion rate (conversions per dollar spent) for that pair.

The three budget levels ($35K, $45K, $55K) that drive the scenario sweep are defined in the script, not in a CSV.

## Model overview

One ontology holds the inputs and the decision variables. The three source CSVs load into `Channel`, `Campaign`, and `Effectiveness`; `Scenario` carries the budget levels; and `Allocation` holds the per-pair decision variables the solver sets.

- **Key entities**: `Channel` — a marketing channel with spend bounds and an ROI coefficient; `Campaign` — a campaign with a budget and a conversion target; `Effectiveness` — the conversion rate for one channel-campaign pair (also the link between a channel and a campaign); `Scenario` — a budget level in the what-if sweep; and the decision concept `Allocation` — one per channel-campaign pair, holding the spend and funding variables the solver sets (indexed by `Scenario`, so a single solve covers all budget levels).
- **Primary identifiers**: integer `id` on `Channel` and `Campaign`; a composite `channel_id` + `campaign_id` on `Effectiveness`; a string `name` on `Scenario`; and the linked `Effectiveness` on `Allocation`.
- **Important invariants**: spend is non-negative; `x_active` is binary (0/1); spend on a pair sits within its channel's min/max only when the pair is active; per-campaign spend stays within the campaign budget; every campaign has at least one funded channel; and total spend stays within the scenario's total budget.

For the full concept and property definitions, see `ad_spend_allocation.py`; `runbook.md` builds them step by step with the RAI skills.

## How it works

The script loads the CSVs into concepts, defines the decision variables, adds the constraints and objective, and solves all budget levels in one call.

1. **Define the ontology.** Channels, campaigns, and their per-pair effectiveness (conversion rates) load into concepts, with the effectiveness rows linking each channel to each campaign.

2. **Model budget levels as a concept.** `Scenario` carries the three total-budget levels, so the what-if sweep is data rather than a Python loop.

3. **Define decision variables.** For each channel-campaign pair the solver sets a continuous spend amount and a binary activation indicator, both indexed by scenario so one solve covers every budget level.

4. **Add constraints.** Spend must fall within a channel's min/max only when its pair is active, per-campaign spend stays within the campaign budget, every campaign keeps at least one active channel, and total spend stays within the scenario's total budget — each scoped per scenario.

5. **Maximize conversions.** The objective sums spend times conversion rate across all allocations, so the solver funds the highest-return pairs first.

6. **Solve once for all scenarios.** A single HiGHS solve covers all three budget levels; results are extracted per scenario and printed as a table.

See `ad_spend_allocation.py` for the implementation and `runbook.md` for the skill-driven reproduction. The end-to-end flow:

```text
CSV inputs → load into concepts → decision variables (spend + funding, per scenario)
   → constraints + objective → single HiGHS solve → per-scenario allocation table
```

## Customize this template

Focus on the first changes most users will make.

### Use your own data

- Replace the CSVs in `data/` with your own; keep the column names listed in *Sample data* above (`channels.csv`: `id`, `name`, `min_spend`, `max_spend`, `roi_coefficient`; `campaigns.csv`: `id`, `name`, `budget`, `target_conversions`; `effectiveness.csv`: `channel_id`, `campaign_id`, `conversion_rate`).
- Add or remove channels by editing `channels.csv` with new spend bounds and ROI coefficients; add campaigns by extending `campaigns.csv` and adding the corresponding rows in `effectiveness.csv`.
- Change the conversion rates in `effectiveness.csv` to reflect your own channel-campaign performance data. Rates are conversions per dollar (a rate of 0.10 means 0.10 conversions per dollar), so keep min/max spend bounds and campaign budgets in the same currency units.
- For Snowflake-backed runs, swap the `read_csv(...)` calls for `model.data(snowflake_table)` calls.

### Tune parameters

- **Budget levels** — the three scenarios (`budget_35k`, `budget_45k`, `budget_55k`) are defined in the `scenario_data` block near the top of the script. Add, remove, or change levels there to sweep a different range.
- **Spend bounds and budgets** — per-channel `min_spend` / `max_spend` live in `channels.csv`; per-campaign `budget` lives in `campaigns.csv`. These are usually the binding limits, so they are the first knobs to adjust when the total-budget cap stops mattering.
- **Solver settings** — the solve uses HiGHS with a 60-second time limit (`problem.solve("highs", time_limit_sec=60)`); adjust the limit for larger instances.

### Extend the model

- **Add diminishing returns** by introducing piecewise-linear or concave conversion functions in place of the flat per-dollar rate.
- **Add channel-level constraints** such as a maximum total spend per channel across all campaigns.
- **Add temporal dimensions** to model multi-period budget allocation with carry-over effects.
- **Add a coverage floor** such as a minimum spend or minimum conversion target per campaign.

### Scale up / productionize

- Replace the `data/` CSV bundle with data loaded directly from Snowflake tables via `model.data(...)`.
- Pin the `relationalai` SDK version (see *Prerequisites*) so runs are reproducible; the single-solve `Scenario` design keeps the whole sweep deterministic within a solve.
- Schedule the run as part of a planning pipeline and read the written-back `Allocation.x_spend` / `Allocation.x_active` properties from the ontology for downstream reporting.

## Troubleshooting

<details>
  <summary>Solver returns INFEASIBLE</summary>

- Check that each scenario's total budget is large enough to satisfy the minimum-spend requirements for at least one channel per campaign.
- Verify that per-campaign budgets in `campaigns.csv` are consistent with channel minimum spends.
- Ensure every campaign has at least one channel in `effectiveness.csv`.

</details>

<details>
  <summary>Import error for <code>relationalai</code></summary>

- Confirm your virtual environment is active: `which python` should point to `.venv`.
- Reinstall dependencies: `python -m pip install .`.

</details>

<details>
  <summary>Authentication or configuration errors</summary>

- Run `rai init` to create or update your RelationalAI / Snowflake configuration.
- If you have multiple profiles, set `export RAI_PROFILE=<your_profile>`.

</details>

<details>
  <summary>Objective value seems too low or too high</summary>

- Conversion rates in `effectiveness.csv` are per dollar spent. A rate of 0.10 means 0.10 conversions per dollar.
- Verify that your conversion rates are scaled appropriately for your use case.
- Check that channel min/max spend bounds are in the same units as campaign budgets.

</details>

## Learn more

### Core concepts

- [PyRel v1 query language](https://docs.relational.ai/) — `model.where(...)`, `model.select(...)`, and aggregation used to build and read the model.

### Reasoner reference

- [Prescriptive reasoner](https://docs.relational.ai/) — the `Problem` API, decision variables, constraints, and objectives used in this template.

### CLI / SDK guides

- [RelationalAI setup and configuration](https://docs.relational.ai/) — installing the SDK and running `rai init`.

## Support

- File issues at the RelationalAI templates repository.
