---
title: "Transaction Screening (Local DuckDB)"
description: "Triage a transfer ledger with rules-based reasoning on a local DuckDB database, with no Snowflake account required: classify accounts that move money just under reporting thresholds, flag large senders, and expand the investigation to everyone who transacted with a flagged account."
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

Anti-money-laundering teams sift through large volumes of transfers to decide which accounts deserve a closer look. Most of the activity is ordinary business, and the suspicious behaviour is a small minority that has to be separated from the noise by rule rather than by hand. This template shows how RelationalAI does that triage. It classifies accounts that move money just under reporting thresholds, flags accounts that send unusually large amounts, and then widens the review to include everyone who transacted directly with a flagged account.

The value of the template is that you can try this entire workflow with nothing but a Python installation. It runs against a local DuckDB database, so there is no Snowflake account to provision and no infrastructure to set up. You write the model, the rules, and the queries exactly as you would against production data, and you run them on your own machine. The graph, optimization, and machine-learning reasoners in RelationalAI run against a Snowflake connection, which this template does not use. Everything shown here is the rules and querying workflow that runs locally.

## Who this is for

- Anyone who wants to try RelationalAI without provisioning Snowflake.
- Developers prototyping an ontology, rules, and queries before pointing them at production data.
- Anyone learning how rules and relationship traversal work together, on a small and legible dataset with a realistic, low rate of suspicious activity.

**Assumed knowledge:** basic Python and familiarity with reading a CSV file. No prior RelationalAI or Snowflake experience is required.

## What you'll build

- An `Account` concept and a self-referential `transfers_to` relationship, both loaded from a CSV file.
- Declarative classification rules for structuring, large senders, and suspects, written with `define()` and `where()`.
- A one-hop investigation expansion across the transfer network, built from a relationship self-join.
- Queries that summarize the network and surface the accounts to review.

## What's included

- **Model**: the `Account` concept, the `transfers_to` relationship, and the classification and expansion rules.
- **Runner**: a single Python script, together with `runbook.md`, an analyst paste-test walkthrough.
- **Runbook**: `runbook.md` — a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the script itself.
- **Sample data**: a ledger of 75 transfers across 54 accounts. A structuring ring and a large sender are embedded in a legitimate-traffic majority, and 6 of the 54 accounts flag.
- **Outputs**: printed tables for the network overview, per-account volume, suspects, counterparties, and the investigation set.

## Prerequisites

### Access

- No RelationalAI account, Snowflake connection, Native App, or `raiconfig.yaml` is required. The script builds an in-memory DuckDB configuration inline.

### Tools

- Python 3.10 or later.
- `relationalai` version 1.13.0 or later. DuckDB is included with the package, and 1.13 is the minimum version for the local path.

Local DuckDB execution relies on deploy mode, which the package currently flags as experimental.

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

5. Expected output (abbreviated). The suspects and the investigation set confirm a successful run — 6 of 54 accounts flag, and the review set expands to 8:

   ```text
   == Network overview ==
    transactions  total_moved
              75       870000

   == Suspect accounts (rules) ==
    suspect
      C1001
      C2001
      C2002
      C2003
      C2004
      C2005

   == Investigation set (suspect or one hop from a suspect) ==
    flagged_for_review
      C1001
      C1002
      C1003
      C2001
      C2002
      C2003
      C2004
      C2005
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

**Start here:** run `python transaction_screening_local.py` for the full run end to end, or follow `runbook.md` to reproduce it step by step with the RAI skills.

## Sample data

`data/transactions.csv` is a ledger of 75 transfers across 54 accounts, with the columns `id`, `src`, `dst`, and `amount`. Most of it is legitimate small-business traffic. The `C3xxx` accounts represent payroll runs, vendor invoices, and retail transfers that never flag. The suspicious activity is a small minority. Accounts `C2001` through `C2005` form a ring that cycles money in amounts just under the 10,000 dollar reporting threshold, which is the behaviour known as structuring, and account `C1001` makes one large transfer of 60,000 dollars. In all, 6 of the 54 accounts flag, which is about 11 percent and a realistic anti-money-laundering base rate. A few near-miss transfers, of 8,900, exactly 10,000, 49,000, and exactly 50,000 dollars, sit right on the threshold edges and deliberately stay clean.

## Model overview

- **Key entity**: `Account`, a party that sends or receives transfers.
- **Primary identifier**: an account is identified by its `id`, drawn from both ends of every transfer.
- **Important invariants**: every transfer has a sender and a receiver, and transfer amounts are positive.

For the full concept and property definitions, see `transaction_screening_local.py`; `runbook.md` builds them step by step with the RAI skills.

## How it works

The script starts by configuring a local DuckDB connection with automatic deployment, so the model materializes and runs on your machine with no Snowflake connection. It then loads the transfer ledger from CSV and derives an `Account` for every party seen at either end of a transfer.

Next it builds the `transfers_to` relationship, linking each sender to its receiver, one row per transfer. The classification rules follow as declarative derived relationships: an account is flagged as structuring when it sends a transfer just under the reporting threshold, and as a large sender when it sends a transfer over the large-transfer limit. An account is a suspect if either flag holds — expressed as two rules that together read as a logical OR.

Finally, connectivity comes from a self-join over `transfers_to` rather than a graph reasoner: an account sits near a suspect if it transacted directly with one in either direction. The investigation set — accounts under review — is the union of suspects and their direct counterparties. The queries at the bottom of the script summarize the network and print the review set.

```text
transactions.csv → load → Account + transfers_to → classification rules → suspects → one-hop expansion → review set
```

See `transaction_screening_local.py` for the implementation, and `runbook.md` to reproduce it step by step with the RAI skills.

## Customize this template

### Use your own data

Replace `data/transactions.csv` with your own ledger, using the columns `id`, `src`, `dst`, and `amount`, or change the `read_csv_auto(...)` path in the script.

### Tune parameters

Adjust `STRUCTURING_FLOOR`, `STRUCTURING_CEILING`, and `LARGE_TRANSFER` at the top of the script to match your own thresholds.

### Extend the model

Add new derived relationships in the same `define()` and `where()` style to capture additional rules, then surface them in the queries at the bottom of the script.

### Scale up / productionize

To move from local development to production scale, point `model.Table(...)` at a Snowflake table instead of the DuckDB connection. The ontology, rules, and queries stay the same. Because deploy mode on local DuckDB is flagged as experimental, confirm the support stance before relying on it for customer-facing work.

## Troubleshooting

<details>
<summary><code>Expected a fully-qualified table name with 3 parts</code></summary>

DuckDB tables need a three-part name. Reference them as `memory.<schema>.<table>`, because an in-memory DuckDB database defaults to the name `memory`.
</details>

<details>
<summary>A query falls back to a Snowflake path, or reads an empty model relation</summary>

Make sure the configuration includes a `deployment` section with `auto_deploy` set to true, so that the model is routed to the DuckDB executor and materialized before queries run.
</details>

<details>
<summary><code>Existing object ... is of type Table, trying to replace with type View</code></summary>

DuckDB is case-insensitive, so a source table named like a concept collides with the installed view. Keep source tables in a schema named `raw`, separate from the model install schema named `main`.
</details>

## Learn more

### Core concepts

- [PyRel v1 modeling](https://docs.relational.ai/) — concepts, relationships, and the `define()` / `where()` workflow this template is built on.
- [Local DuckDB development](https://docs.relational.ai/) — running RelationalAI on a local DuckDB database with no Snowflake account.

### Language / modeling reference

- [Rules and derived relationships](https://docs.relational.ai/) — authoring classification rules like `is_structuring`, `is_suspect`, and the investigation expansion.
- [Querying](https://docs.relational.ai/) — `select()`, filtering, and aggregation for the summary and review tables.

### CLI / SDK guides

- [RelationalAI Python SDK](https://docs.relational.ai/) — installing and configuring the `relationalai` package.

## Support

- File issues at the RelationalAI templates repository.

## Related templates

- [commercial_underwriting](../commercial_underwriting/) is a rules-based eligibility and risk-tier classification on a hierarchical ontology.
- [fraud-detection](../fraud-detection/) is the full multi-reasoner fraud pipeline, combining graph, rules, predictive, and prescriptive reasoning on Snowflake.
