---
title: "Ad Spend Allocation"
description: "Allocate marketing budget across channels and campaigns to maximize conversions."
featured: false
experience_level: intermediate
industry: "Marketing"
reasoning_types:
  - Prescriptive
tags:
  - budget-allocation
  - mixed-integer-programming
  - marketing
  - what-if-analysis
---

# Ad Spend Allocation

## What this template is for

Marketing teams face a recurring challenge: how to distribute a limited budget across multiple advertising channels and campaigns to get the most conversions. Each channel (search, social, display, video, email) has different minimum and maximum spend thresholds, and each channel-campaign combination has a different conversion rate. The goal is to find the spend allocation that maximizes total expected conversions while respecting per-channel bounds, per-campaign budgets, and an overall budget cap.

This template formulates the ad spend allocation problem as a mixed-integer program. Binary variables determine which channel-campaign combinations are active, while continuous variables set the spend levels. Constraints enforce minimum/maximum spend per channel (when active), per-campaign budget limits, and a global budget ceiling. The objective maximizes the total expected conversions computed from spend times conversion rate.

The template includes scenario analysis that sweeps over three total budget levels ($35K, $45K, $55K), letting you see how additional budget translates into incremental conversions and which channels the optimizer activates at each budget level.

## Who this is for

- Marketing analysts optimizing media spend across channels
- Growth teams evaluating budget scenarios for campaign planning
- Data scientists building prescriptive models for ad optimization
- Developers learning mixed-integer programming with RelationalAI

## What you'll build

- A mixed-integer optimization model for multi-channel, multi-campaign budget allocation
- Channel activation logic with minimum/maximum spend enforcement
- Per-campaign budget constraints and a global budget cap
- Scenario analysis across three budget levels with comparison of results

## What's included

- `ad_spend_allocation.py` -- main script with ontology, formulation, and scenario loop
- `data/channels.csv` -- 5 channels with spend bounds and ROI coefficients
- `data/campaigns.csv` -- 3 campaigns with budgets and target conversions
- `data/effectiveness.csv` -- 15 channel-campaign conversion rates
- `pyproject.toml` -- Python package configuration

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools
- Python >= 3.10

## Quickstart

1. Download ZIP:
   ```bash
   curl -L -O https://docs.relational.ai/templates/zips/v1/ad_spend_allocation.zip
   unzip ad_spend_allocation.zip
   cd ad_spend_allocation
   ```
   > [!TIP]
   > You can also download the template ZIP using the "Download ZIP" button at the top of this page.

2. Create venv:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   ```

3. Install:
   ```bash
   python -m pip install .
   ```

4. Configure:
   ```bash
   rai init
   ```

5. Run:
   ```bash
   python ad_spend_allocation.py
   ```

6. Expected output:
   ```text
   Running scenario: total_budget = 35000
     Status: OPTIMAL, Objective: 2765.0

     Spend allocation:
                        name    value
    spend_Search_Seasonal_Sale  10000.0
    spend_Social_Seasonal_Sale   8000.0
    spend_Video_Product_Launch  12000.0
     spend_Email_Seasonal_Sale   2000.0
      spend_Email_Brand_Awareness 1000.0
      spend_Search_Product_Launch 2000.0

   Running scenario: total_budget = 45000
     Status: OPTIMAL, Objective: 3575.0
     ...

   Running scenario: total_budget = 55000
     Status: OPTIMAL, Objective: 4205.0
     ...

   ==================================================
   Scenario Analysis Summary
   ==================================================
     35000: OPTIMAL, obj=2765.0
     45000: OPTIMAL, obj=3575.0
     55000: OPTIMAL, obj=4205.0
   ```

## Template structure
```text
.
├── README.md
├── pyproject.toml
├── ad_spend_allocation.py
└── data/
    ├── channels.csv
    ├── campaigns.csv
    └── effectiveness.csv
```

## How it works

**1. Define the ontology.** Channels, campaigns, and their effectiveness (conversion rates) are modeled as concepts:

```python
Channel = Concept("Channel", identify_by={"id": Integer})
Channel.min_spend = Property(f"{Channel} has {Float:min_spend}")
Channel.max_spend = Property(f"{Channel} has {Float:max_spend}")

Campaign = Concept("Campaign", identify_by={"id": Integer})
Campaign.budget = Property(f"{Campaign} has {Float:budget}")

Effectiveness = Concept("Effectiveness", identify_by={"channel_id": Integer, "campaign_id": Integer})
Effectiveness.conversion_rate = Property(f"{Effectiveness} has {Float:conversion_rate}")
```

**2. Define decision variables.** Continuous spend amounts and binary activation indicators per channel-campaign pair:

```python
Allocation = Concept("Allocation", identify_by={"effectiveness": Effectiveness})
Allocation.x_spend = Property(f"{Allocation} has {Float:spend}")
Allocation.x_active = Property(f"{Allocation} is {Float:active}")

s.solve_for(Allocation.x_spend, name=[...], lower=0)
s.solve_for(Allocation.x_active, type="bin", name=[...])
```

**3. Add constraints.** Minimum/maximum spend when active, per-campaign budget limits, at least one active channel per campaign, and a global budget cap:

```python
s.satisfy(model.require(Allocation.x_spend >= Allocation.effectiveness.channel.min_spend * Allocation.x_active))
s.satisfy(model.require(Allocation.x_spend <= Allocation.effectiveness.channel.max_spend * Allocation.x_active))

campaign_spend = sum(Allocation.x_spend).where(Allocation.effectiveness.campaign == Campaign).per(Campaign)
s.satisfy(model.require(campaign_spend <= Campaign.budget))
s.satisfy(model.require(sum(Allocation.x_spend) <= total_budget))
```

**4. Maximize conversions.** The objective sums spend times conversion rate across all active allocations:

```python
total_conversions = sum(Allocation.x_spend * Allocation.effectiveness.conversion_rate)
s.maximize(total_conversions)
```

**5. Run scenarios.** The loop iterates over budget levels, building a fresh Problem for each and comparing results.

## Customize this template

- **Add or modify channels** by editing `channels.csv` with new spend bounds and ROI coefficients.
- **Add campaigns** by extending `campaigns.csv` and adding corresponding rows in `effectiveness.csv`.
- **Change conversion rates** to reflect your own channel-campaign performance data.
- **Add diminishing returns** by introducing piecewise linear or concave conversion functions.
- **Add channel-level constraints** such as maximum total spend per channel across all campaigns.
- **Add temporal dimensions** to model multi-period budget allocation with carry-over effects.

## Troubleshooting

<details>
  <summary>Solver returns INFEASIBLE</summary>

- Check that `total_budget` is large enough to satisfy the minimum-spend requirements for at least one channel per campaign.
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

- Run `rai init` to create or update your RelationalAI/Snowflake configuration.
- If you have multiple profiles, set `export RAI_PROFILE=<your_profile>`.

</details>

<details>
  <summary>Objective value seems too low or too high</summary>

- Conversion rates in `effectiveness.csv` are per dollar spent. A rate of 0.10 means 0.10 conversions per dollar.
- Verify that your conversion rates are scaled appropriately for your use case.
- Check that channel min/max spend bounds are in the same units as campaign budgets.

</details>
