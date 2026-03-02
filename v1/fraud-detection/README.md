---
title: "Fraud Detection"
description: "Use graph reasoning to find suspicious users based on shared identifiers and uncommon sharing patterns."
experience_level: beginner
industry: "Financial Services"
featured: true
reasoning_types:
  - Graph
tags:
  - Fraud Detection
  - Graph
  - Identity Resolution
---

## What this template is for

Fraud and risk teams often need to investigate **identity graphs**: networks where users may be connected by shared identifiers like email, phone number, address, or payment instrument.
This template is a runnable notebook that shows how to:

- Model user-profile attributes in RelationalAI
- Build an identity graph and find connected communities
- Add simple rules to flag **uncommon sharing patterns** that merit investigation

## Who this is for

- Analysts and engineers who want a concrete starting point for graph-based fraud signals
- Users who are comfortable running a Jupyter notebook and making small edits

## What you’ll build

- A notebook that loads a small example dataset and models it with the RelationalAI v1 PyRel semantics API
- Community detection using Weakly Connected Components on an identity graph
- A simple, explainable suspicious-user rule set (size-based filtering + sharing patterns)
- (Optional) Export of suspicious users to a Snowflake table

## What’s included

- **Model**: `User` and `Address` concepts, plus derived types for flagged users
- **Runner**: `fraud-detection.ipynb` (primary notebook)
- **Sample data**: in-notebook in-memory lists for users and addresses (no CSVs)
- **Outputs**: a pandas DataFrame of suspicious users; optionally a Snowflake table written via `into(...).exec()`

## Prerequisites

### Access

- A Snowflake account with the RelationalAI Native App installed
- A Snowflake user/role that can run the RAI Native App
- If you plan to run the export step: permissions to create/overwrite the destination table you choose

### Tools

- Python >= 3.10
- Jupyter Notebook/Lab

This template installs:

- `relationalai==1.0.0`
- `jupyter`

## Quickstart

1. **Download the ZIP file for this template and extract it:**

   ```bash
   curl -L -O https://docs.relational.ai/templates/zips/v1/fraud-detection.zip
   unzip fraud-detection.zip
   cd fraud-detection
   ```

   > [!TIP]
   > You can also download the template ZIP using the "Download ZIP" button at the top of this page.

2. **Create and activate a virtual environment**

  From the template folder (this is `v1/fraud-detection` if you cloned the full repository):

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install -U pip
   ```

3. **Install dependencies**

   ```bash
   python -m pip install .
   ```

4. **Configure credentials**

   This notebook executes RelationalAI queries and (optionally) writes results back to Snowflake, so you need a working RelationalAI/Snowflake configuration.

   If you use the RelationalAI CLI, run:

   ```bash
   rai init
   ```

   If you have multiple profiles, set one explicitly:

   ```bash
   export RAI_PROFILE=<your_profile>
   ```

5. **Start Jupyter**

   ```bash
   jupyter notebook
   ```

6. **Run the template**

   Open `fraud-detection.ipynb` and run the cells top-to-bottom (or "Run All").

7. **Expected output**

   You should see:

   - Printed community summaries, for example:

     ```text
     Group 1 with 5 connected users: ['David Evans', 'Eva Green', 'Hannah Lee', 'Jane Smith', 'John Doe']
     ```

     (Group numbering may differ.)

   - A DataFrame listing suspicious users and linked attributes.

   - If you run the export section: a Snowflake table created at the configured destination (defaults to `RAI_DEMO.FRAUD_DETECTION.SUSPICIOUS_USERS_V1` in the notebook).

## Template structure

```text
.
├─ README.md
├─ pyproject.toml              # Python dependencies for running the notebook
└─ fraud-detection.ipynb       # start here (main notebook)
```

**Start here**: `fraud-detection.ipynb`

## Sample data

The notebook uses in-memory sample data (Python lists of dicts) with two tables:

- `users_data`: user profile attributes (`id`, `fullname`, `phone_number`, `email`, `address_id`, `credit_card_number`)
- `addresses_data`: address attributes (`id`, `street_address`, `city`, `state`)

The model links users to addresses using `address_id`.

## Model overview

The notebook models a small identity graph and then derives suspicious-user signals.

The `Address` concept represents a physical location record:

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | integer | Yes | Joins from `users_data.address_id` |
| `street_address` | string | No | Example: `"123 Fake St"` |
| `city` | string | No | Example: `"Springfield"` |
| `state` | string | No | Example: `"IL"` |

The `User` concept represents a user/account profile:

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | integer | Yes | Primary key for users |
| `fullname` | string | No | Display name |
| `phone_number` | string | No | Used as an identifier for linking |
| `email` | string | No | Used as an identifier for linking |
| `credit_card_number` | string | No | Used as an identifier for linking |
| `address` | relationship | No | Links a `User` to an `Address` |

## How it works

At a high level, the notebook:

1. Creates example `users_data` and `addresses_data`.
2. Defines `User` and `Address` concepts and loads the data into the model.
3. Builds an identity graph and assigns each user to a community using Weakly Connected Components.
4. Marks users in large communities (default: 4+ users).
5. Flags suspicious users based on sharing email/phone while having different addresses, then propagates suspicion via shared address.
6. Queries results into a pandas DataFrame.
7. (Optional) Exports results to a Snowflake table using `into(...).exec()`.

## Customize this template

### Use your own data

- Replace the in-memory lists with Snowflake tables by using the pattern shown in the notebook:
  - `m.Table("MY_DB.MY_SCHEMA.MY_TABLE")` (as long as the schema matches)
- Keep the same key structure (`users.id`, `addresses.id`, and `users.address_id`) so joins stay valid.

### Tune parameters

- Change `LARGE_GROUP_SIZE` to control how aggressively you flag large communities.
- Adjust the rule that defines suspicious users (for example, require multiple shared identifiers instead of one).

### Extend the model

- Add more identifiers (device ID, IP address, bank account, shipping address) and connect them into the identity graph.
- Add additional graph analytics (for example, centrality or shortest-path checks) before applying rules.
- Expand the export schema to include more investigation context.

## Troubleshooting

<details>
  <summary>Jupyter can’t import <code>relationalai</code> (or uses the wrong environment)</summary>

- Confirm your virtual environment is active: `which python` should point to `.venv`.
- Reinstall dependencies: `python -m pip install .`.
- In Jupyter/VS Code, select the kernel that points to the `.venv` interpreter.

</details>

<details>
  <summary>Authentication/configuration fails when the notebook runs queries</summary>

- Make sure your RelationalAI/Snowflake configuration is present and correct.
- If you use the RelationalAI CLI, run `rai init` to create/update your config.
- If you have multiple profiles, set `RAI_PROFILE` to the one you want.

</details>

<details>
  <summary>The Snowflake export step fails</summary>

- Ensure the destination table name is valid and you have permission to create/write it.
- Edit the `destination = m.Table("...")` line in the notebook to write into a schema you control.

</details>

<details>
  <summary>I don’t have the <code>rai</code> command</summary>

- Make sure your virtual environment is active and that you installed the dependencies with `python -m pip install .`.

</details>

## Learn more

- RelationalAI documentation: https://docs.relational.ai/build
- Jupyter documentation: https://jupyter.org/documentation
- Snowflake documentation: https://docs.snowflake.com/
