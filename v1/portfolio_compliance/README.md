---
title: "Portfolio Compliance"
description: "Define derived business rules for portfolio concentration limits, sector exposure, and high-risk trader detection."
featured: false
experience_level: beginner
industry: "Financial Services"
reasoning_types:
    - Rules-based
tags:
  - Derived Properties
  - Business Logic
  - Compliance
  - Aggregation
---

# Portfolio Compliance

## What this template is for

This template uses **rules-based reasoning** to define derived business rules for portfolio concentration limits, sector exposure, and high-risk trader detection.

Financial services firms must monitor portfolio positions for regulatory concentration limits. Business rules help surface violations automatically: which holdings are overconcentrated, which accounts have excessive sector exposure, which traders exhibit high-risk behavior.

This template uses RelationalAI's logic reasoner to define three derived rules as boolean flags on existing concepts. No optimization solver is involved -- rules are pure declarative logic evaluated over the data model.

The three rules demonstrate different rule patterns:
1. **Cross-entity threshold** -- flag holdings where value exceeds 10% of account balance
2. **Aggregation with grouping** -- flag accounts where one sector exceeds 30% of balance, using `.per(account, sector)` to group holding values
3. **Threshold + aggregation** -- flag users with high risk score AND more than 5 flagged transactions

## Who this is for

- Data scientists and analysts learning rule-based reasoning with RelationalAI
- Financial services teams wanting to automate compliance and risk detection
- Beginners who want to understand derived properties and aggregation patterns

## What you'll build

- A data model with users, accounts, stocks, holdings, and transactions
- Three derived rules using `model.where(...).define(...)` pattern
- Queries that surface which entities match each rule

## What's included

- `portfolio_compliance.py` -- Main script defining the data model and three rules
- `data/users.csv` -- User profiles with risk scores
- `data/accounts.csv` -- Brokerage and retirement accounts with balances
- `data/stocks.csv` -- Stock catalog with sectors and expected returns
- `data/holdings.csv` -- Portfolio positions linking accounts to stocks
- `data/transactions.csv` -- Transaction records with flagged status
- `pyproject.toml` -- Python package configuration with dependencies

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools
- Python >= 3.10

## Quickstart

1. Download ZIP:
   ```bash
   curl -O https://private.relational.ai/templates/zips/v1/portfolio_compliance.zip
   unzip portfolio_compliance.zip
   cd portfolio_compliance
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
   python portfolio_compliance.py
   ```

## Template structure

```text
.
├── README.md
├── pyproject.toml
├── portfolio_compliance.py
└── data/
    ├── users.csv
    ├── accounts.csv
    ├── stocks.csv
    ├── holdings.csv
    └── transactions.csv
```

## How it works

### 1. Define concepts and load data

The model defines five concepts (User, Account, Stock, Holding, Transaction) and loads each from CSV. Relationships link accounts to users, holdings to accounts and stocks, and transactions to users.

### 2. Define rules as derived Relationships

Each rule uses the `model.where(...).define(...)` pattern to create a boolean flag:

```python
# Cross-entity threshold rule (joins Holding -> Account)
Holding.is_overconcentrated = Relationship(f"{Holding} is overconcentrated")
acct_ref = Account.ref()
model.where(
    Holding.account(acct_ref),
    Holding.quantity * Holding.purchase_price > acct_ref.balance * 0.10,
).define(Holding.is_overconcentrated())

# Aggregation rule with per(account, sector) grouping
sector_total = (
    aggregates.sum(h_ref.quantity * h_ref.purchase_price)
    .per(a_ref, s_ref.sector)
    .where(h_ref.account(a_ref), h_ref.stock(s_ref))
)
model.where(sector_total > a_ref.balance * 0.30).define(
    Account.has_sector_concentration(a_ref)
)

# Threshold + aggregation rule
flagged_count = aggregates.count(txn_ref).per(User).where(
    txn_ref.user(User), txn_ref.is_flagged == True
)
model.where(
    User.risk_score > 0.8, flagged_count > 5
).define(User.is_high_risk_trader())
```

### 3. Query flagged entities

Each rule is queried with `model.select(...).where(Concept.rule_flag())` to display matching entities.

## Customize this template

- **Adjust thresholds**: Change the 10% holding limit, 30% sector limit, or risk score cutoff to match your regulatory requirements.
- **Add more rules**: Define additional Relationships for new business conditions (e.g., `Account.is_underperforming` based on expected returns).
- **Chain rules**: Reference one rule's output in another rule's definition (e.g., flag accounts as critical if they have sector concentration AND the owner is a high-risk trader).
- **Connect to optimization**: Use rule flags as constraint filters in a prescriptive formulation (e.g., rebalance portfolios to eliminate concentration violations).

## Troubleshooting

<details>
<summary><code>ModuleNotFoundError</code></summary>

Make sure you activated the virtual environment and ran `python -m pip install .` to install all dependencies listed in `pyproject.toml`.
</details>

<details>
<summary>Connection or authentication errors</summary>

Run `rai init` to configure your Snowflake connection. Verify that the RAI Native App is installed and your user has the required permissions.
</details>
