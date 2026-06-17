---
title: "Entity Resolution"
description: "Resolve duplicate policyholder records scattered across an insurer's policy systems and acquired books into one insured party, then total each household's exposure, flag accumulation-limit breaches, and choose the lowest-cost reinsurance cessions to clear them."
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

An insurer accumulates the same customer many times over. A household holds auto, home, and life policies in separate administration systems, books of business arrive through acquisitions, and names, addresses, and contact details drift between them. Until those records are resolved into one insured party, the carrier's total exposure to each customer is invisible: no single policy looks dangerous, yet a household's combined coverage can quietly exceed an accumulation limit.

This template treats entity resolution as the foundation for a decision, not an end in itself. It uses **Graph** clustering to merge duplicate records into one insured party (following chains of matches that a simple pairwise comparison would miss), **Rules-based** aggregation to total each household's exposure and flag the ones over the accumulation limit, and **Prescriptive** optimization to choose the lowest-cost reinsurance cessions that bring breached households back under the limit. Resolution is the step that makes that downstream risk decision correct.

## Who this is for

- Accumulation, catastrophe, and reinsurance teams who need exposure measured per real insured, not per record
- Master-data, SIU/fraud, and compliance teams that need duplicate parties collapsed before screening
- Anyone learning to chain fuzzy matching, graph clustering, rule-based aggregation, and optimization in RelationalAI
- **Assumed knowledge**: comfortable reading Python; entity resolution, accumulation limits, and reinsurance terms are explained as they come up, so no prior RelationalAI experience is required to follow along

## What you'll build

- A two-band matcher (auto-merge vs review queue) over blocked, field-scored candidate pairs
- A record graph clustered into insured parties with weakly-connected-components
- Rule-derived match tiers, a duplicate flag, and per-party total exposure with an accumulation-limit breach flag
- A minimum-cost reinsurance cession plan (a prescriptive knapsack) over the breached households
- The record-level vs resolved-level breach contrast, a review queue, and pairwise precision / recall / F1

## What's included

- **Model**: `Record` (raw party records with coverage), `CandidateMatch` (auto-merged pairs) and `ReviewPair` (held pairs); a graph deriving each record's resolved party; rules deriving match `confidence_tier`, an `is_duplicate` flag, and `ResolvedParty` total exposure + breach flag; and a prescriptive cession decision.
- **Runner**: `entity_resolution.py`, run end to end with `python entity_resolution.py`.
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

## Template structure

```text
.
├── README.md
├── runbook.md               # paste-able multi-reasoner walkthrough (RAI skills)
├── pyproject.toml
├── entity_resolution.py
└── data/
    ├── records.csv          # 51 dirty party records (AUTO / HOME / LIFE / LEGACY) with coverage
    └── ground_truth.csv     # maps each record to its true party, for evaluation
```

**Start here**: run `python entity_resolution.py` for the full pipeline (blocking, then graph clustering, rules, and the prescriptive plan), or follow `runbook.md` to rebuild it step by step with a coding agent.

## Sample data

`data/records.csv` holds 51 party records from four sources -- three policy systems (`AUTO`, `HOME`, `LIFE`) and an acquired book (`LEGACY`) -- covering 30 real people, 16 of whom appear in more than one system. Each row carries identifiers (`full_name`, `date_of_birth`, `gov_id_last4`, `email`, `phone`, address) and a per-policy `coverage_amount` (sum insured). `email`, `phone`, `date_of_birth`, and `gov_id_last4` may be empty. No single policy reaches the $1,000,000 accumulation limit -- a household only breaches it once its policies are resolved together.

Three cases are placed deliberately:

- **A transitive chain** (`M. O'Brien`): three records whose endpoints share no identifier, linked only through the middle record -- resolved only because clustering closes over the graph.
- **A same-name trap** (two `John Smith` records in Chicago): blocked together but kept apart by differing date of birth, government ID, contact, and address.
- **A review-band duplicate** (`Ethan Brooks` / `E. Brooks`): a true second policy that shares only date of birth, so it scores in the review band and is *not* auto-merged. Its household's combined exposure ($1,055,000) breaches the limit -- a breach that stays hidden until a steward confirms the match.

`data/ground_truth.csv` maps each `record_id` to its true party for evaluation.

## Model overview

- **Key entities**: `Record` (one raw policy record), `CandidateMatch` (an auto-merged pair), `ReviewPair` (a held pair), and `ResolvedParty` (one real insured, keyed by its weakly-connected-component party key).
- **Primary identifiers**: `Record` by `record_id`; `CandidateMatch`/`ReviewPair` by `pair_id`; `ResolvedParty` by integer `key`.
- **Important invariants**: every record in a party shares one `entity_key`; a party breaches when its summed coverage exceeds the accumulation limit; only breached parties carry an `excess`, `premium`, and `cede` decision.

### `Record`

A raw policy record before resolution. `email`, `phone`, `date_of_birth`, and `gov_id_last4` are optional.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `record_id` | int | Yes | Loaded from `data/records.csv` |
| `source_system` | string | No | `AUTO`, `HOME`, `LIFE`, or `LEGACY` |
| `full_name` / address fields | string | No | Raw, uncleaned |
| `coverage_amount` | float | No | Per-policy sum insured |
| `date_of_birth` / `gov_id_last4` / `email` / `phone` | string | No | Optional matching identifiers |
| `entity_id` (graph) / `entity_key` | (node) / int | No | Resolved party — WCC label and its integer key (Stage 1) |
| `is_duplicate` | flag | No | Record shares its party with another (Stage 2) |

### `ResolvedParty`

One real insured, created from the distinct party keys.

| Property | Type | Notes |
|---|---|---|
| `key` | int | Identifying; the party's representative record id |
| `total_exposure` | float | Sum of coverage across the party's resolved policies |
| `is_over_limit` | flag | Total exposure exceeds the accumulation limit |
| `excess` / `premium` | float | Excess over the limit and premium to cede it (breached parties) |
| `cede` | float (binary) | Prescriptive decision: cede this party to reinsurance (Stage 3) |

## How it works

Blocking and fuzzy scoring run in pandas (no string-similarity primitive in any query language); the engine does the parts that need reasoning -- transitive clustering, declarative aggregation, and optimization.

### Candidate generation (pandas)

Blocking groups records sharing an email handle, phone, name+postal key, or date of birth, so only 28 candidate pairs are scored instead of 1,275. Each candidate's weighted field-similarity score lands it in one of two bands: at or above `AUTO_MERGE` it becomes a match edge; in `[REVIEW_FLOOR, AUTO_MERGE)` it is held for a steward instead of merged.

### Stage 1 -- Graph: transitive clustering

Each auto-merge match is an undirected edge; weakly-connected-components collapses connected records into one party. Because WCC returns the representative node, the script derives a stable integer party key from it:

```python
graph = Graph(model, directed=False, weighted=False, node_concept=Record)

match_ref = CandidateMatch.ref()
rec_a, rec_b = Record.ref(), Record.ref()
model.where(
    match_ref.rec_a == rec_a,
    match_ref.rec_b == rec_b
).define(graph.Edge.new(src=rec_a, dst=rec_b))

graph.Node.entity_id = graph.weakly_connected_component()
```

### Stage 2 -- Rules-based: exposure per resolved party

A `ResolvedParty` is created per party key; its total exposure is the summed coverage of its records, and it breaches when that total exceeds the limit:

```python
model.where(party_rec.entity_key == ResolvedParty.key).define(
    ResolvedParty.total_exposure(aggregates.sum(party_rec.coverage_amount).per(ResolvedParty))
)
model.define(ResolvedParty.is_over_limit(ResolvedParty)).where(
    ResolvedParty.total_exposure > ACCUMULATION_LIMIT
)
```

### Stage 3 -- Prescriptive: reinsurance cession knapsack

A binary cede decision per breached party, maximizing excess exposure transferred within the premium budget:

```python
problem.solve_for(
    ResolvedParty.cede,
    where=[ResolvedParty.is_over_limit()],
    name=["cede", ResolvedParty.key],
    type="bin",
    lower=0.0,
    upper=1.0,
)
problem.satisfy(
    model.require(aggregates.sum(ResolvedParty.premium * ResolvedParty.cede) <= REINSURANCE_BUDGET),
    name=["reinsurance_budget"],
)
problem.maximize(aggregates.sum(ResolvedParty.excess * ResolvedParty.cede))
```

```text
records (CSV) -> block + score (pandas) -> auto edges + review queue
   -> WCC clusters -> per-party exposure + breach flag -> reinsurance cession plan
```

## Customize this template

### Use your own data

- Replace `data/records.csv`. Keep `record_id`, `full_name`, `coverage_amount`, and address columns; `email`, `phone`, `date_of_birth`, `gov_id_last4` may be blank (loaded only where present, so a blank cell doesn't drop the record).
- Provide `data/ground_truth.csv` to measure accuracy, or delete the evaluation block.

### Tune parameters

- `AUTO_MERGE` / `REVIEW_FLOOR` set the two matching bands. Raise `AUTO_MERGE` to send more pairs to review (higher precision, lower recall); the per-field weights live in `pair_score`.
- `ACCUMULATION_LIMIT`, `REINSURANCE_RATE`, and `REINSURANCE_BUDGET` drive the downstream stages. A tighter budget forces the optimizer to prioritize; raise it and more breaches get ceded.

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

`model.data(df).to_schema()` drops any row that has an empty or null cell in a loaded column. Load the always-present columns via `to_schema` and load each optional column only over the rows where it is present, as `load_optional_property` does here. Quick check: `model.select(Record.record_id).to_df().shape[0]` should equal your row count.
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
