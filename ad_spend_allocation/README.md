# Ad Spend Allocation

Allocate advertising budget across channels and campaigns to maximize conversions.

## Classification

| Dimension | Value |
|-----------|-------|
| **Reasoner** | Prescriptive |
| **Problem Type** | Allocation |
| **Industry** | Marketing / Advertising |
| **Method** | MILP (Mixed-Integer Linear Programming) |
| **Complexity** | Intermediate |

## What is this problem?

Marketing teams must distribute limited advertising budgets across multiple channels (Search, Social, Display, Video, Email) and campaigns to maximize return on investment. This template models allocating spend across 5 channels and 3 campaigns, where each channel-campaign combination has different conversion effectiveness.

The challenge is that each channel has minimum spend thresholds (you can't spend just $10 on a channel—there are setup costs) and maximum caps, while campaign budgets constrain total spend.

## Why is optimization valuable?

- **Improved ROAS**: Achieves higher Return on Ad Spend compared to manual allocation or simple rules <!-- TODO: Add % improvement from results -->
- **Budget efficiency**: Eliminates waste from over-allocating to saturated channels while identifying under-invested opportunities
- **Data-driven decisions**: Replaces gut-feel allocation with mathematically optimal distribution based on measured conversion rates

## What are similar problems?

- **Media mix modeling**: Allocate TV, radio, print, and digital budgets across markets
- **Sales territory assignment**: Distribute sales rep time across accounts to maximize revenue
- **R&D portfolio allocation**: Distribute research budget across projects based on expected payoff
- **Fundraising channel optimization**: Allocate nonprofit outreach budget across direct mail, email, events

## Problem Description

A marketing team manages multiple advertising campaigns across different channels (Search, Social, Display, Video, Email). Each channel has minimum and maximum spend limits. Each campaign has a total budget. The effectiveness (conversion rate) varies by channel-campaign combination.

The goal is to allocate spend across channels and campaigns to maximize total expected conversions while respecting budget constraints and channel limits.

### Decision Variables

- `Allocation.spend` (continuous): Amount to spend on each channel/campaign combination
- `Allocation.active` (binary): 1 if channel is used for campaign, 0 otherwise

### Objective

Maximize total conversions:
```
maximize sum(spend * conversion_rate)
```

### Constraints

1. **Channel limits**: When active, spend on a channel must be between min_spend and max_spend
2. **Campaign budget**: Total spend per campaign cannot exceed campaign budget
3. **Channel coverage**: Each campaign must use at least one channel

## Data

Data files are located in the `data/` subdirectory.

### channels.csv

| Column | Description |
|--------|-------------|
| id | Unique channel identifier |
| name | Channel name (Search, Social, Display, etc.) |
| min_spend | Minimum spend if channel is used ($) |
| max_spend | Maximum spend allowed ($) |
| roi_coefficient | Base return on investment coefficient |

### campaigns.csv

| Column | Description |
|--------|-------------|
| id | Unique campaign identifier |
| name | Campaign name |
| budget | Total budget available ($) |
| target_conversions | Target number of conversions |

### effectiveness.csv

| Column | Description |
|--------|-------------|
| channel_id | Reference to channel |
| campaign_id | Reference to campaign |
| conversion_rate | Expected conversions per dollar spent |

## Usage

```python
from ad_spend_allocation import solve, extract_solution

# Run optimization
solver_model = solve()
result = extract_solution(solver_model)

print(f"Status: {result['status']}")
print(f"Total conversions: {result['objective']:.0f}")
print(result['variables'])
```

Or run directly:

```bash
python ad_spend_allocation.py
```

## Expected Output

<!-- TODO: Run template and paste actual output here -->
```
Status: OPTIMAL
Total Expected Conversions: X
...
```
