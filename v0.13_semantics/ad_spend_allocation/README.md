---
title: "Ad Spend Allocation"
description: "Allocate a fixed budget across channel–campaign combinations to maximize expected conversions, subject to channel spend bounds and per-campaign budget limits."
featured: false
experience_level: intermediate
industry: "Marketing"
reasoning_types:
  - Prescriptive
tags:
  - Allocation
  - MILP
---

# Ad Spend Allocation

## Who this is for

- You want an end-to-end example of **prescriptive reasoning (optimization)** with RelationalAI.
- You’re comfortable with basic Python and linear/mixed-integer optimization concepts.

## What you’ll build / learn

- Model business entities (channels, campaigns) as concepts with properties.
- Define decision variables (continuous spend + binary “active” flags).
- Add constraints (min/max spend, campaign budgets, minimum coverage).
- Solve with the **HiGHS** backend and inspect allocations.

## What’s included

- **Model + solve script**: `ad_spend_allocation.py`
- **Sample data**: `data/channels.csv`, `data/campaigns.csv`, `data/effectiveness.csv`
- **Python dependencies**: `pyproject.toml`
- **Outputs**: prints solver status, objective value, and a spend allocation table

## Prerequisites

### Access

- RelationalAI account with access to a Snowflake account that has the RAI Native App installed.

### Tools

- Python >= 3.10
- Python packages: `relationalai==0.13.3`, `pandas` (see `pyproject.toml`)
- Optional: the `rai` CLI (installed with the `relationalai` Python package)

### Configuration

This template creates a `Model(..., config=...)` using the active profile from a `raiconfig.toml` (or a `Config` object).

- If you already have RAI configured, you can skip setup.
- Otherwise, create or update `raiconfig.toml` with:

  ```bash
  rai init
  ```

If you use multiple profiles, you can select one via:

```bash
export RAI_PROFILE=<profile-name>
```

## Quickstart

1. **Create and activate a virtual environment**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install -U pip
   ```

2. **Install dependencies**

   From this folder:

   ```bash
   python -m pip install -e .
   ```

   If you prefer not to install the project, installing dependencies directly also works:

   ```bash
   python -m pip install relationalai==0.13.3 pandas
   ```

3. **(Optional) Configure RAI connection**

   ```bash
   rai init
   ```

4. **Run the template**

   ```bash
   python ad_spend_allocation.py
   ```

5. **Expected output**

   The script prints a termination status, the objective value (total expected conversions), and a table of non-zero spend decisions, for example:

   ```text
   Status: OPTIMAL
   Total expected conversions: 3430
   Spend allocation:
                            name   float
    active_Email_Brand_Awareness     1.0
      active_Email_Seasonal_Sale     1.0
   active_Search_Brand_Awareness     1.0
    active_Search_Product_Launch     1.0
     active_Search_Seasonal_Sale     1.0
   active_Social_Brand_Awareness     1.0
     active_Video_Product_Launch     1.0
     spend_Email_Brand_Awareness  2000.0
       spend_Email_Seasonal_Sale  2000.0
    spend_Search_Brand_Awareness  5000.0
     spend_Search_Product_Launch 10000.0
      spend_Search_Seasonal_Sale  8000.0
    spend_Social_Brand_Awareness  8000.0
      spend_Video_Product_Launch 10000.0
   ```

## Repository structure

```text
.
├─ README.md
├─ pyproject.toml
├─ ad_spend_allocation.py
└─ data/
   ├─ channels.csv
   ├─ campaigns.csv
   └─ effectiveness.csv
```

**Start here**: `ad_spend_allocation.py`

## How it works (overview)

- Load three CSVs into the model as concepts and properties.
- Construct an `Allocation` decision concept for each `(channel, campaign)` pair.
- Solve for two variables per allocation:
  - `Allocation.spend` (continuous, >= 0)
  - `Allocation.active` (binary)
- Add constraints:
  - If active, spend must be between `min_spend` and `max_spend` for the channel.
  - Total spend per campaign must be <= campaign budget.
  - Each campaign must use at least one channel.
- Maximize total expected conversions: `sum(spend * conversion_rate)`.

## Data model (relations)

Describe the main entities and the most important relationships.

Include two compact tables:

### Concepts (entity types)

| Concept type | Main properties | Identifying properties | Notes |
|---|---|---|---|
| `Channel` | `name`, `min_spend`, `max_spend`, `roi_coefficient` | `id` | Loaded from `data/channels.csv` |
| `Campaign` | `name`, `budget`, `target_conversions` | `id` | Loaded from `data/campaigns.csv` |
| `Effectiveness` | `channel`, `campaign`, `conversion_rate` | (`channel`, `campaign`) | One row per channel–campaign pair |
| `Allocation` | `effectiveness`, `spend`, `active` | `effectiveness` | Decision concept created for all `Effectiveness` |

### Relationships

The template uses semantic “reading strings” when declaring properties. The table below summarizes the key ones.

| Relationship | Schema (reading string fields) | Notes |
|---|---|---|
| `Channel.id` | `Channel`, `id:int` | Key used when loading `channels.csv` |
| `Campaign.id` | `Campaign`, `id:int` | Key used when loading `campaigns.csv` |
| `Effectiveness.channel` | `Effectiveness`, `channel:Channel` | Joined via `channels.csv.id == effectiveness.csv.channel_id` |
| `Effectiveness.campaign` | `Effectiveness`, `campaign:Campaign` | Joined via `campaigns.csv.id == effectiveness.csv.campaign_id` |
| `Effectiveness.conversion_rate` | `Effectiveness`, `conversion_rate:float` | Conversions per $ |
| `Allocation.effectiveness` | `Allocation`, `effectiveness:Effectiveness` | One allocation per effectiveness row |
| `Allocation.spend` | `Allocation`, `spend:float` | Continuous decision variable |
| `Allocation.active` | `Allocation`, `active:float` | Binary decision variable (0/1) |

## Sample data

Data files are in `data/`.

### `channels.csv`

| Column | Meaning |
|---|---|
| `id` | Unique channel identifier |
| `name` | Channel name (e.g., Search, Social) |
| `min_spend` | Minimum spend if the channel is active |
| `max_spend` | Maximum spend allowed |
| `roi_coefficient` | Additional channel attribute (not used in the objective in this template) |

### `campaigns.csv`

| Column | Meaning |
|---|---|
| `id` | Unique campaign identifier |
| `name` | Campaign name |
| `budget` | Total spend allowed for the campaign |
| `target_conversions` | Campaign attribute (not used as a constraint in this template) |

### `effectiveness.csv`

| Column | Meaning |
|---|---|
| `channel_id` | Foreign key to `channels.csv.id` |
| `campaign_id` | Foreign key to `campaigns.csv.id` |
| `conversion_rate` | Expected conversions per $ spent |

## Features showcased

- **Semantic modeling (concepts + properties)** — Declare entity types and relate them with readable property declarations.
- **Optimization modeling** — Create continuous and binary decision variables, constraints, and a linear objective.
- **Solver backend integration (HiGHS)** — Solve a MILP and inspect the solution.

## Customize this template

### Use your own data

- Replace the CSVs in `data/` with your own, keeping the same column names (or update the loading logic in `ad_spend_allocation.py`).
- Ensure that `effectiveness.csv` only references valid `channel_id` and `campaign_id` values.

### Tune parameters

- **Solver**: the template uses `Solver("highs")`.
- **Time limit**: `time_limit_sec=60` in the call to `s.solve(...)`.

### Extend the model

- Add per-channel total spend limits across all campaigns.
- Add campaign conversion targets as constraints (using `Campaign.target_conversions`).
- Add diminishing returns (piecewise linear approximations) if conversion rate decreases with spend.

### Scale up / productionize (optional)

- Replace CSV ingestion with Snowflake sources (see the overview in `../README.md`).
- Write allocations back to Snowflake after solving.

## Troubleshooting

Include the top 5–8 failure modes with specific fixes.

<details>
  <summary>Why does authentication/configuration fail?</summary>

  - Run `rai init` to create/update `raiconfig.toml`.
  - If you have multiple profiles, set `RAI_PROFILE` or switch profiles in your config.
  - See the configuration guide linked below for profile discovery and precedence.
</details>

<details>
  <summary>Why does the script fail to connect to the RAI Native App?</summary>

  - Verify the Snowflake account/role/warehouse and `rai_app_name` are correct in `raiconfig.toml`.
  - Ensure the RAI Native App is installed and you have access.
</details>

<details>
  <summary>Why do I get <code>Status: INFEASIBLE</code>?</summary>

  - Check that each campaign budget is high enough to pay for at least one active channel’s `min_spend`.
  - Check that channel `min_spend` values are not greater than `max_spend`.
  - Confirm conversion rates are present for each campaign (missing effectiveness rows reduce options).
</details>

<details>
  <summary>Why is the spend allocation empty?</summary>

  - The script filters allocations with `Allocation.spend > 0.001`. If everything is near zero, inspect constraints and budgets.
  - Confirm input CSVs were read correctly and contain rows.
</details>

---

## Next steps

- Add scenario parameters (e.g., channel saturation, campaign priorities) and compare solutions.
- Persist the results (CSV or Snowflake table) and build a small dashboard.
- Extend the objective (e.g., weighted conversions, CAC/ROAS trade-offs).
