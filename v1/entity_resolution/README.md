---
title: "Entity Resolution"
description: "Resolve duplicate policyholder records across an insurer's policy systems and acquired books into one insured party. Total each household's exposure, flag accumulation-limit breaches, and choose the lowest-cost reinsurance cessions to clear them."
featured: false
experience_level: intermediate
industry: "Financial Services"
reasoning_types:
  - Graph
  - Rules-based
  - Prescriptive
tags:
  - Entity Resolution
  - Record Linkage
  - Deduplication
  - Weakly Connected Components
  - Accumulation Control
  - Reinsurance Optimization
  - Insurance
---

## What this template is for

An insurer has policyholder records spread across source systems and acquired books. Differences in names and identifiers can make the same insured party look like several customers, which can hide the party's total coverage and cause the insurer to miss accumulation-limit breaches.

This template matches and clusters records into resolved parties, aggregates coverage, identifies overexposed parties, and chooses reinsurance cessions within a premium budget. Use it as a starting point for other entity-resolution workflows where downstream decisions require a complete party view.

## Who this is for

- Accumulation, catastrophe, and reinsurance teams who need exposure measured per real insured, not per record
- Master-data, SIU/fraud, and compliance teams that need duplicate parties collapsed before screening
- Anyone learning to chain fuzzy matching, graph clustering, rule-based aggregation, and optimization in RelationalAI
- **Assumed knowledge**: comfortable reading Python; entity resolution, accumulation limits, and reinsurance terms are explained as they come up, so no prior RelationalAI experience is required to follow along

## What you'll build

You'll use Graph Reasoning to cluster accepted matches into insured parties, Rules-Based Reasoning to total each party's exposure and flag limit breaches, and Prescriptive Reasoning to choose the lowest-cost reinsurance cessions that clear them. Graph clustering follows chains of matches that pairwise comparison alone would miss, so downstream risk decisions use resolved parties rather than isolated records.

- A two-band matcher (auto-merge vs review queue) over blocked, field-scored candidate pairs
- A record graph clustered into insured parties with weakly-connected-components
- Rule-derived match tiers, a duplicate flag, and per-party total exposure with an accumulation-limit breach flag
- A minimum-cost reinsurance cession plan (a prescriptive knapsack) over the breached households
- The record-level vs resolved-level breach contrast, a review queue, and pairwise precision / recall / F1

## What's included

- **Schema**: `model/schema.py` declares `Record`, `CandidateMatch`, `ReviewPair`, and `ResolvedParty`, including their identities, properties, and relationships.
- **Source pipeline**: `model/source.py` reads the CSVs, normalizes matching fields, blocks and scores candidate pairs, and loads the base, accepted-match, and review facts.
- **Reasoning runner**: `entity_resolution.py` clusters accepted matches, derives party membership and exposure, solves the reinsurance decision, and reports the results. Run it end to end with `python entity_resolution.py`.
- **Sample data**: `data/records.csv` (51 dirty party records across AUTO / HOME / LIFE / LEGACY, with per-policy coverage) and `data/ground_truth.csv` (record-to-party labels for evaluation).
- **Outputs**: printed blocking/banding stats, graph size, resolved-party and golden-record summary, the record-vs-resolved accumulation contrast, the reinsurance cession plan, the review queue, and pairwise precision / recall / F1.
- **Runbook**: `runbook.md` -- a paste-able, ordered walkthrough that recreates the template with a coding agent using the RelationalAI skills (`/rai-*`), with the expected response at each step.

## Prerequisites

### Access

- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools

- Python >= 3.10
- The prescriptive stage solves with HiGHS, which ships with the prescriptive reasoner -- no extra solver license required.

## Quickstart

1. Download ZIP:
   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/entity_resolution.zip
   unzip entity_resolution.zip
   cd entity_resolution
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
   python entity_resolution.py
   ```

6. Expected output (a few lines confirm success):
   ```text
   Auto-resolved 51 records into 31 insured parties.
   Households over the limit after RESOLUTION:       4
     -> ceded $927,000 of excess exposure for $111,240 premium (of $120,000)
     precision: 1.000   recall: 0.963   f1: 0.981
   ```

   No single policy breaches the $1M limit, yet resolution surfaces four over-limit households and the optimizer cedes the most excess it can afford within budget. The full printout and a step-by-step walkthrough are in `runbook.md`.

## Sample data

[`data/records.csv`](data/records.csv) holds 51 party records from three policy systems (`AUTO`, `HOME`, `LIFE`) and an acquired book (`LEGACY`). The records cover 30 real people, 16 of whom appear in more than one system. Each row includes matching identifiers and a per-policy `coverage_amount` (sum insured). Optional identifiers may be empty.

This sample shows the three-record O'Brien chain. The first and third records share no identifier, but each matches the middle record:

| record_id | source_system | full_name | email | coverage_amount |
| ---: | --- | --- | --- | ---: |
| 1014 | AUTO | Margaret O'Brien | — | 73,000 |
| 1015 | HOME | Maggie O'Brien | mobrien@fastmail.com | 480,000 |
| 1016 | LEGACY | M. O'Brien | mobrien@fastmail.com | 400,000 |

The review-band case shares only a date of birth. It stays out of the automatic cluster until a steward confirms it:

| record_id | full_name | date_of_birth | coverage_amount |
| ---: | --- | --- | ---: |
| 1030 | Ethan Brooks | 1979-12-12 | 480,000 |
| 1031 | E. Brooks | 1979-12-12 | 575,000 |

No single policy reaches the $1,000,000 accumulation limit. The Brooks household reaches $1,055,000 only after review confirms the match.

[`data/ground_truth.csv`](data/ground_truth.csv) provides the labels used to evaluate pairwise precision, recall, and F1:

| record_id | true_entity_id |
| ---: | --- |
| 1014 | p07 |
| 1015 | p07 |
| 1016 | p07 |
| 1030 | p17 |
| 1031 | p17 |

The data also includes two distinct Chicago records named John Smith. Blocking compares them, but their other identifiers and addresses keep them apart.

## Model overview

- **Key entities**: `Record` (one raw policy record), `CandidateMatch` (an auto-merged pair), `ReviewPair` (a held pair), and `ResolvedParty` (one real insured, keyed by its weakly-connected-component party key).
- **Primary identifiers**: `Record` by `record_id`; `CandidateMatch`/`ReviewPair` by `pair_id`; `ResolvedParty` by integer `key`.
- **Important invariants**: every record in a party shares one `entity_key`; a party breaches when its summed coverage exceeds the accumulation limit; only breached parties carry an `excess`, `premium`, and `cede` decision.

For the complete concept, identity, property, and relationship declarations, see `model/schema.py`. The source mappings are in `model/source.py`, and `runbook.md` builds the flow step by step with the RAI skills.

## How it works

`model/source.py` performs blocking and fuzzy scoring in pandas. `entity_resolution.py` performs the reasoning stages: transitive clustering, declarative aggregation, and optimization.

```text
records (CSV) -> block + score (pandas) -> auto edges + review queue
   -> WCC clusters -> per-party exposure + breach flag -> reinsurance cession plan
```

### Candidate generation (pandas)

In `model/source.py`, blocking groups records sharing an email handle, phone, name+postal key, or date of birth, so only 28 candidate pairs are scored instead of 1,275. Each candidate's weighted field-similarity score lands it in one of two bands: at or above `AUTO_MERGE` it becomes a match edge; in `[REVIEW_FLOOR, AUTO_MERGE)` it is held for a steward instead of merged.

### Stage 1 -- Graph: transitive clustering

In `entity_resolution.py`, each auto-merge match becomes an undirected edge between two records, and weakly-connected-components collapses every connected group into one party — closing over transitive chains that a pairwise comparison would miss. WCC returns the representative node, from which the runner derives a stable integer party key.

### Stage 2 -- Rules-based: exposure per resolved party

A `ResolvedParty` is created per party key; its total exposure is the summed coverage of its records, and it is flagged over-limit when that total exceeds the accumulation limit.

### Stage 3 -- Prescriptive: reinsurance cession knapsack

A binary cede decision per breached party maximizes the excess exposure transferred to reinsurance, subject to keeping total cession premium within the budget — a knapsack over the over-limit households.

See `model/schema.py` for the shared model, `model/source.py` for source preparation and loading, `entity_resolution.py` for reasoning and reporting, and `runbook.md` for the skill-driven reproduction.

## Customize this template

### Use your own data

- Replace `data/records.csv`. Keep `record_id`, `full_name`, `coverage_amount`, and address columns; `email`, `phone`, `date_of_birth`, `gov_id_last4` may be blank (loaded only where present, so a blank cell doesn't drop the record).
- Provide `data/ground_truth.csv` to measure accuracy, or delete the evaluation block.

### Tune parameters

- In `model/source.py`, `AUTO_MERGE` and `REVIEW_FLOOR` set the two matching bands. Raise `AUTO_MERGE` to send more pairs to review (higher precision, lower recall); the per-field weights live in `pair_score`.
- In `entity_resolution.py`, `ACCUMULATION_LIMIT`, `REINSURANCE_RATE`, and `REINSURANCE_BUDGET` drive the downstream stages. A tighter budget forces the optimizer to prioritize; raise it and more breaches get ceded.

### Extend the model

- **Survivorship**: the golden record uses most-recent-wins; swap in source-priority or most-complete.
- **Cession objective**: maximize breaches *cured* instead of exposure ceded, or add a per-state rate on line so catastrophe-exposed accumulations cost more to cede.
- **Review workflow**: route `ReviewPair` rows to a steward; confirming one re-runs resolution and can surface a new breach.

### Scale up / productionize

- Point `Record` at a Snowflake table instead of a CSV and let the engine cluster and aggregate at warehouse scale.
- For very large inputs, tighten blocking so candidate counts stay manageable -- blocking, not clustering, dominates cost.

## Troubleshooting

<details>
<summary><code>ModuleNotFoundError</code></summary>

Make sure you activated the virtual environment and ran `python -m pip install .` to install the dependencies in `pyproject.toml`.
</details>

<details>
<summary>Connection or authentication errors</summary>

Run `rai init` to configure your Snowflake connection. Verify that the RAI Native App is installed and your user has the required permissions.
</details>

<details>
<summary>Why did some records silently disappear after loading?</summary>

`model.data(df).to_schema()` drops any row that has an empty or null cell in a loaded column. In `model/source.py`, `load_records` loads the always-present columns through `to_schema` and loads each optional column only over rows where it is present. Quick check: `model.select(Record.record_id).to_df().shape[0]` should equal your row count.
</details>

<details>
<summary><code>TypeMismatch: Expected 'String', got 'Record'</code> from the WCC output</summary>

`graph.weakly_connected_component()` returns the component-representative node, not a scalar. Don't key a concept by it directly as a string -- derive an integer key from the representative's id (`Record.entity_key` here) and key `ResolvedParty` off that.
</details>

<details>
<summary>The cession plan is empty or leaves the biggest breach uncovered</summary>

That is the budget binding. The knapsack maximizes excess exposure ceded within `REINSURANCE_BUDGET`; an expensive single accumulation can be skipped in favor of cheaper ones. Raise the budget, or change the objective to prioritize the largest breach.
</details>

## Learn more

- [RelationalAI documentation](https://docs.relational.ai/) — language, modeling, and reasoner reference.
- [Template gallery](https://docs.relational.ai/build/templates) — other runnable templates, including graph, rules, and prescriptive examples.

## Support

- Questions or issues: [support.relational.ai](https://support.relational.ai).
