---
title: "Transaction Screening (Local DuckDB)"
description: "Rules + query fraud-ring triage: structuring and large-sender flags, suspect classification, and one-hop investigation expansion via a relationship self-join."
featured: false
experience_level: beginner
industry: "Financial Services"
reasoning_types:
  - Rules-based
tags:
  - Rules-Based Reasoning
  - Anti-Money-Laundering
  - Local Development
  - DuckDB
  - Getting Started
---

## What this template is for

Anti-money-laundering teams triage a transfer ledger to decide which accounts deserve a closer look. This template demonstrates that triage with **rules-based reasoning** in RelationalAI: it classifies accounts that move money just under reporting thresholds, flags large senders, and expands the investigation to everyone one hop away in the transfer network.

It runs entirely on a local DuckDB database, so you can try the full ontology → rules → query workflow with nothing but a Python install. It is the local-development counterpart to the Snowflake-backed templates: the same modeling patterns, on an engine you can run anywhere.

What runs locally vs. needs a Snowflake connection:

| Used here (local DuckDB) | Needs a Snowflake connection |
| --- | --- |
| Data loading, querying (filter / join / aggregate / group) | Graph reasoner (`Graph()` — centrality, community, WCC) |
| Rules / logic (classification flags, chaining) | Optimization solve (`Problem`) |
| Relationship traversal (multi-hop self-joins, connectivity) | GNN training / inference |

## Who this is for

- Anyone who wants to try RelationalAI without provisioning Snowflake
- Developers prototyping an ontology, rules, and queries before pointing at production data
- Anyone learning the rules + relationship-traversal patterns on a legible dataset with a realistic low base rate of suspicious activity

## What you'll build

- An `Account` concept and a self-referential `transfers_to` relationship loaded from a CSV
- Declarative classification rules (`structuring`, `large sender`, `suspect`) using `define()` + `where()`
- A one-hop investigation expansion across the transfer network via a relationship self-join
- Queries that summarize the network and surface the accounts to review

## What's included

- **Model**: `Account`, the `transfers_to` relationship, and the classification + expansion rules
- **Runner**: a single Python script (and `runbook.md`, an analyst paste-test walkthrough)
- **Sample data**: a 75-transfer ledger across 54 accounts — a structuring ring and a large sender embedded in a legitimate-traffic majority (6 of 54 accounts flag)
- **Outputs**: printed tables (network overview, per-account volume, suspects, counterparties, investigation set)

## Prerequisites

- Python 3.10+
- `relationalai>=1.12.0` (DuckDB ships with it; 1.12 is the minimum for the local path)

No Snowflake account, Native App, or `raiconfig.yaml` is required — the script builds an in-memory DuckDB config inline. (Local DuckDB execution relies on deploy mode, which the package currently flags as experimental.)

## Quickstart

1. Download the ZIP file for this template and extract it:

   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/transaction_screening_local.zip
   unzip transaction_screening_local.zip
   cd transaction_screening_local
   ```

   > [!TIP]
   > You can also download the template ZIP using the "Download ZIP" button at the top of this page.

2. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install -U pip
   ```

3. Install dependencies:

   ```bash
   python -m pip install .
   ```

4. Run the template:

   ```bash
   python transaction_screening_local.py
   ```

## Template structure

```text
transaction_screening_local/
├── README.md
├── runbook.md                       # analyst paste-test walkthrough
├── pyproject.toml
├── transaction_screening_local.py   # model, rules, and queries
└── data/
    └── transactions.csv             # sample transfer ledger
```

## Sample data

`data/transactions.csv` is a 75-transfer ledger across 54 accounts, with columns `id, src, dst, amount`. Most of it is legitimate small-business traffic (the `C3xxx` accounts — payroll runs, vendor invoices, retail transfers) that never flags. The suspicious activity is a small minority: `C2001–C2005` form a ring that cycles money in amounts just under the $10,000 reporting threshold (structuring), and `C1001` makes one large $60,000 transfer. In all, 6 of 54 accounts flag (~11%) — a realistic AML base rate. A few near-miss transfers (8,900; exactly 10,000; 49,000; exactly 50,000) sit right on the threshold edges and deliberately stay clean.

## Model overview

The model derives accounts from both ends of every transfer, links them with a `transfers_to` relationship, then layers rules on top:

- **`is_structuring`** — sent a transfer in the 9,000–10,000 band.
- **`is_large_sender`** — sent a transfer over 50,000.
- **`is_suspect`** — either of the above (defined as two rules, an OR).
- **`near_suspect`** — transacted directly with a suspect, in either direction.
- **`under_review`** — the investigation set: suspect OR near a suspect.

## How it works

The local path is configured with a `duckdb` connection plus a `deployment` section (`schema` + `auto_deploy`):

```python
config = create_config(
    connections={"local": DuckDBConnection(path=":memory:")},  # or a file path, e.g. "./dev.duckdb"
    default_connection="local",
    deployment={"schema": "main", "auto_deploy": True},
)
```

The `transfers_to` relationship is built with explicit two-ref binding so each row links the correct source and destination accounts:

```python
Account.transfers_to = model.Relationship(f"{Account} transfers to {Account:other}")
_src, _dst = Account.ref(), Account.ref()
model.where(_src.id == txn.src, _dst.id == txn.dst).define(_src.transfers_to(_dst))
```

Rules are declarative derived Relationships; `is_suspect` chains on the flags below it:

```python
Account.is_suspect = model.Relationship(f"{Account} is suspect")
model.where(Account.is_structuring()).define(Account.is_suspect())
model.where(Account.is_large_sender()).define(Account.is_suspect())
```

Connectivity ("who transacts with whom") comes from a self-join over `transfers_to`, not a graph reasoner:

```python
_other = Account.ref()
model.where(Account.transfers_to(_other), _other.is_suspect()).define(Account.near_suspect())
```

## Customize this template

- Adjust `STRUCTURING_FLOOR`, `STRUCTURING_CEILING`, and `LARGE_TRANSFER` at the top of the script to match your thresholds.
- Replace `data/transactions.csv` with your own `id, src, dst, amount` ledger (or change the `read_csv_auto(...)` path).
- To move to production scale, point `model.Table(...)` at a Snowflake table instead of the DuckDB connection — the ontology, rules, and queries stay the same.

## Troubleshooting

<details>
<summary><code>Expected a fully-qualified table name with 3 parts</code></summary>

DuckDB tables need a three-part name. Reference them as `memory.<schema>.<table>` (in-memory DuckDB defaults to the `memory` database).
</details>

<details>
<summary>A query falls back to a Snowflake path, or reads an empty model relation</summary>

Make sure the config includes a `deployment` section with `auto_deploy: true` so the model is routed to the DuckDB executor and materialized before queries.
</details>

<details>
<summary><code>Existing object ... is of type Table, trying to replace with type View</code></summary>

DuckDB is case-insensitive, so a source table named like a concept collides with the installed view. Keep source tables in a schema (`raw`) separate from the model install schema (`main`).
</details>

## Related templates

- [commercial_underwriting](../commercial_underwriting/) — rules-based eligibility and risk-tier classification on a hierarchical ontology.
- [fraud-detection](../fraud-detection/) — the full multi-reasoner fraud pipeline (Graph + Rules + Predictive + Prescriptive) on Snowflake.
