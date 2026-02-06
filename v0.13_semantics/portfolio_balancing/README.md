---
title: "Portfolio Optimization"
description: "Allocate investment across stocks to minimize risk while achieving a target return."
featured: false
experience_level: intermediate
industry: "Finance"
reasoning_types:
  - Prescriptive
tags:
  - Allocation
  - QP
---

# Portfolio Optimization

## What is this problem?

Investors must allocate capital across multiple assets to achieve target returns while managing risk. This template implements the classic Markowitz mean-variance optimization—finding stock allocations that minimize portfolio variance (risk) while achieving a minimum expected return.

The key insight is that diversification reduces risk: a portfolio of assets that don't move perfectly together can have lower variance than any individual asset. The covariance matrix captures these relationships.

## Why is optimization valuable?

- **Better risk-adjusted returns**: Achieves target returns with mathematically minimal risk through optimal diversification
- **Efficient frontier analysis**: Understand the full range of risk-return trade-offs available to make informed investment decisions
- **Constraint handling**: Incorporate regulatory limits, sector caps, and investment policies into allocation decisions systematically

## What are similar problems?

- **Pension fund allocation**: Distribute retirement assets across equities, bonds, real estate, and alternatives
- **Insurance reserve investment**: Allocate reserves to match liability duration while meeting return targets
- **Endowment management**: Balance growth objectives with spending needs and risk tolerance
- **Personal retirement planning**: Allocate 401(k) across funds based on risk tolerance and time horizon

## Problem Details

### Model

**Concepts:**
- `Stock`: Available investments with expected return and variance
- `Covariance`: Pairwise risk correlation between stocks
- `Allocation`: Decision entity for investment amount per stock

**Relationships:**
- `Covariance` links pairs of `Stock` entities

### Decision Variables

- `Stock.quantity` (continuous): Amount allocated to each stock (>= 0)

### Objective

Minimize portfolio risk (variance):
```
minimize sum(quantity_i * quantity_j * covariance_ij)
```

### Constraints

1. **Budget**: Total quantity allocated cannot exceed budget
2. **Minimum return**: Expected portfolio return must meet target
3. **No shorting**: Quantities must be non-negative

## Data

Data files are located in the `data/` subdirectory.

### returns.csv

| Column | Description |
|--------|-------------|
| index | Stock identifier (1, 2, 3, ...) |
| returns | Expected return for this stock (decimal, e.g., 0.05 = 5%) |

### covariance.csv

| Column | Description |
|--------|-------------|
| i | First stock index |
| j | Second stock index |
| covar | Covariance between stocks i and j |

The covariance matrix is symmetric (covar_ij = covar_ji).

## Usage

```python
from portfolio_balancing import solve, extract_solution

# Run optimization with minimum return target of 20 and budget of 1000
solver_model = solve(min_return=20, budget=1000)
result = extract_solution(solver_model)

print(f"Status: {result['status']}")
print(f"Portfolio risk (variance): {result['objective']:.4f}")
print(result['variables'])
```

Or run directly:

```bash
python portfolio_balancing.py
```

## Expected Output

```
Status: OPTIMAL
Portfolio risk (variance): 1462.6398
Minimum return target: 20

Stock allocations:
 name      float
qty_1  15.447778   (Low return 2.5%, low risk - diversification anchor)
qty_2 411.690255   (Medium return 4.0%, medium risk - core holding)
qty_3  44.945648   (High return 7.0%, high risk - growth allocation)
```

The optimal portfolio demonstrates diversification across all three assets:
- **Stock 2** (medium risk-return) dominates as the efficient core holding
- **Stock 3** (high return) provides growth potential despite higher risk
- **Stock 1** (low risk) provides stability through low correlation with others
- Total risk (1463) is lower than any single-asset portfolio achieving the same return
