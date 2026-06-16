---
title: "Entity Resolution"
description: "Resolve duplicate policyholder records across an insurer's policy systems and acquired books into one record per insured party, using fuzzy matching, weakly-connected-components clustering, and confidence-tier rules."
featured: false
experience_level: intermediate
industry: "Financial Services"
reasoning_types:
  - Graph
  - Rules-based
tags:
  - Entity Resolution
  - Record Linkage
  - Deduplication
  - Weakly Connected Components
  - Fuzzy Matching
  - Master Data Management
  - Insurance
---

# Entity Resolution

## What this template is for

This template chains **Graph** analysis and **Rules-based** reasoning to resolve duplicate policyholder records into one record per real-world insured party.

Insurers accumulate the same customer many times over. A household holds auto, home, and life policies in separate administration systems; books of business arrive through acquisitions; and names, addresses, and contact details drift between them ("Robert Chen" / "Bob Chen", `415-555-0142` / `(415) 555-0142`, a street that gained an apartment number). Left unresolved, these duplicates fragment the customer view, understate a household's total exposure for accumulation and catastrophe risk, waste outreach on the same person twice, and weaken sanctions and fraud screening — one individual can sit behind several "distinct" claimants.

The hard part is that duplicates link *transitively*. Record A may match B on phone, and B match C on email, while A and C share nothing directly. A pairwise spreadsheet pass records the A–B and B–C matches but never concludes that A, B, and C are one person. This template treats accepted matches as edges in a graph and runs weakly-connected-components, so each connected group collapses into a single insured party — then classifies how confident each match is so a steward can review the weakest merges.

## Who this is for

- Data and analytics teams building a single customer or single-party view across insurance systems
- Master-data, SIU/fraud, and compliance teams that need duplicate parties collapsed before screening
- Anyone learning to combine fuzzy matching with graph clustering and rule-based classification in RelationalAI

## What you'll build

- A candidate-generation step that blocks records into buckets and scores each pair with field-level similarity (name, date of birth, government-ID fragment, email, phone, address)
- A record graph whose edges are accepted matches, clustered into insured parties with weakly-connected-components
- Rule-derived `confidence_tier` (HIGH / MEDIUM / REVIEW) on each match and an `is_duplicate` flag on each record, both queryable in the ontology
- A golden (surviving) record per party and a pairwise precision / recall / F1 score against ground-truth labels

## What's included

- **Model**: a `Record` concept (raw party records) and a `CandidateMatch` concept (accepted pairwise matches); a graph that derives each record's resolved `entity_id`; and rules that derive match `confidence_tier` and the `is_duplicate` flag.
- **Runner**: `entity_resolution.py`, run end to end with `python entity_resolution.py`.
- **Sample data**: `data/records.csv` (50 dirty party records across AUTO / HOME / LIFE / LEGACY systems) and `data/ground_truth.csv` (record-to-party labels for evaluation).
- **Outputs**: printed blocking statistics, graph size, the resolved-party and golden-record summary, the confidence-tier breakdown, and pairwise precision / recall / F1.

## Prerequisites

### Access

- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools

- Python >= 3.10

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

6. Expected output (abridged):
   ```text
   ============================================================
   Blocking & scoring
   ============================================================
   Records:                50
   All possible pairs:     1225
   Candidate pairs:        27  (97.8% fewer comparisons)
   Accepted match edges:   25  (score >= 0.55)
   Graph:                  50 nodes, 25 match edges

   ============================================================
   Resolved parties
   ============================================================
   Resolved 50 records into 30 insured parties (20 duplicate records collapsed).
   Records flagged as duplicates (in a multi-record party): 35

   Multi-record parties (golden record in CAPS, then merged duplicates):

     M. O'BRIEN  <mobrien@fastmail.com>  [golden from LEGACY, 2023-10-04]
         record 1014 [AUTO   ] Margaret O'Brien       -
         record 1015 [HOME   ] Maggie O'Brien         mobrien@fastmail.com
         record 1016 [LEGACY ] M. O'Brien             mobrien@fastmail.com        <- golden
     ... (14 more multi-record parties)

   ============================================================
   Match confidence tiers
   ============================================================
     HIGH    20 matches
     MEDIUM  2 matches
     REVIEW  3 matches

   ============================================================
   Evaluation vs ground truth (pairwise)
   ============================================================
     precision: 1.000
     recall:    1.000
     f1:        1.000
     (true positives=26, false positives=0, false negatives=0)
   ```

   The `M. O'Brien` party is the payoff: record 1014 (no email) links to 1015 on phone and date of birth, 1015 links to the acquired legacy record 1016 on email, and 1014 and 1016 share no identifier at all. Weakly-connected-components still resolves all three into one insured party.

## Template structure

```text
.
├── README.md
├── pyproject.toml
├── entity_resolution.py
└── data/
    ├── records.csv          # 50 dirty party records (AUTO / HOME / LIFE / LEGACY)
    └── ground_truth.csv     # record_id -> true_entity_id labels for evaluation
```

**Start here**: run `python entity_resolution.py` for the full blocking -> graph -> rules -> evaluation pipeline.

## Sample data

`data/records.csv` holds 50 party records pulled from four sources — three policy systems (`AUTO`, `HOME`, `LIFE`) and an acquired book of business (`LEGACY`) — covering 30 real people. Fifteen people appear in more than one system, with realistic corruptions: nickname versus legal name, typos, email and phone format drift, an apartment number that comes and goes, a mistyped date of birth, and government-ID fragments that the legacy system never captured (empty cells).

Each row has a `record_id`, `source_system`, `full_name`, `date_of_birth`, `gov_id_last4`, `email`, `phone`, `street`, `city`, `state`, `postal_code`, and `created_at`. `email`, `phone`, `date_of_birth`, and `gov_id_last4` may be empty.

Two cases are placed deliberately:

- **A transitive chain** (`M. O'Brien`): three records where the endpoints share no identifier and are linked only through the middle record — resolved correctly only because clustering closes over the graph.
- **A same-name trap** (two `John Smith` records in Chicago): blocking puts them in the same bucket, but they differ on date of birth, government ID, contact details, and address, so scoring keeps them as two separate parties.

`data/ground_truth.csv` maps each `record_id` to its true party so the script can score the resolution. In practice this is a labeled sample used to tune the match threshold.

## Model overview

- **Key entities**: `Record` (one raw party record from a source system) and `CandidateMatch` (one accepted pairwise match between two records).
- **Primary identifiers**: `Record` is identified by `record_id`; `CandidateMatch` by `pair_id`.
- **Important invariants**: a match links two distinct records; `entity_id` (the resolved party) is shared by every record in a connected component.

### `Record`

A raw party record before resolution. `email`, `phone`, `date_of_birth`, and `gov_id_last4` are optional and may be null.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `record_id` | int | Yes | Loaded from `data/records.csv` |
| `source_system` | string | No | `AUTO`, `HOME`, `LIFE`, or `LEGACY` |
| `full_name` | string | No | Raw, uncleaned name |
| `date_of_birth` | string | No | `YYYY-MM-DD`; optional |
| `gov_id_last4` | string | No | Last four digits of a government ID; optional |
| `email` | string | No | Optional |
| `phone` | string | No | Any format; optional |
| `street` / `city` / `state` / `postal_code` | string | No | Mailing address |
| `created_at` | string | No | Record load date; used for golden-record survivorship |
| `entity_id` | (graph) | No | Resolved party — the weakly-connected-component label (Stage 1) |
| `is_duplicate` | flag | No | Set when the record's party has more than one record (Stage 2) |

### `CandidateMatch`

An accepted pairwise match. `rec_a` and `rec_b` are functional links to `Record`, so they are Properties, not Relationships.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `pair_id` | int | Yes | Row in the candidate set |
| `rec_a` / `rec_b` | `Record` | No | The two matched records |
| `score` | float | No | Field-similarity score in `[0, 1]` |
| `confidence_tier` | string | No | `HIGH` / `MEDIUM` / `REVIEW`, derived from `score` (Stage 2) |

## How it works

The script runs blocking and scoring in pandas (fuzzy string work is awkward in any query language), then hands the accepted matches to RelationalAI for the parts that genuinely need a reasoning engine: transitive clustering and declarative classification.

### Candidate generation (pandas)

Comparing all 1,225 record pairs is wasteful. Blocking groups records that share an email handle, a phone number, or a name-and-postal key, and only those candidate pairs are scored — here, 27 pairs instead of 1,225. Each candidate gets a weighted similarity score across name (Jaro-Winkler with nickname folding), date of birth, government-ID fragment, email, phone, and address. Pairs at or above `MATCH_THRESHOLD` become match edges.

### Stage 1 — Graph: transitive clustering

Each accepted match is an undirected edge between two records. Weakly-connected-components collapses every connected group into one resolved party, so a chain of pairwise matches becomes a single insured customer:

```python
graph = Graph(model, directed=False, weighted=False, node_concept=Record)

match_ref = CandidateMatch.ref()
rec_a, rec_b = Record.ref(), Record.ref()
model.where(
    match_ref.rec_a == rec_a,
    match_ref.rec_b == rec_b
).define(graph.Edge.new(src=rec_a, dst=rec_b))

# Each record's resolved entity id is its weakly-connected-component label,
# available directly on Record because node_concept=Record.
graph.Node.entity_id = graph.weakly_connected_component()
```

Because `node_concept=Record`, every record is a node, so a record with no matches forms its own single-record party.

### Stage 2 — Rules-based: confidence tiers and duplicate flags

The rules read graph output (`entity_id`) and match scores and write classifications back to the ontology, where any query can filter on them:

```python
records_per_entity = aggregates.count(Record).per(Record.entity_id)
model.define(Record.is_duplicate(Record)).where(records_per_entity >= 2)

model.define(CandidateMatch.confidence_tier("HIGH")).where(
    CandidateMatch.score >= HIGH_TIER
)
```

### Resolution summary and evaluation

A golden record is chosen per party (most recent record wins), and the resolution is scored against `ground_truth.csv` with pairwise precision / recall / F1.

```text
records (CSV) -> block + score (pandas) -> match edges -> WCC clusters -> tier + duplicate rules -> golden record + evaluation
```

## Customize this template

### Use your own data

- Replace `data/records.csv` with your records. Keep the `record_id`, `full_name`, and address columns; `email`, `phone`, `date_of_birth`, and `gov_id_last4` may be blank.
- Optional fields are loaded only for rows where they are present (see `load_optional_property`), so blank cells become nulls rather than dropping the record.
- Provide `data/ground_truth.csv` for a labeled sample to measure accuracy, or delete the evaluation block if you have no labels.

### Tune parameters

- `MATCH_THRESHOLD` (default `0.55`) is the merge cutoff. Raise it to merge more conservatively, lower it to merge more aggressively.
- `HIGH_TIER` / `MEDIUM_TIER` set the confidence bands. The per-field weights live in `pair_score`; reweight them to match which fields you trust most.
- `NICKNAMES` folds nicknames to legal first names — extend it for your population.

### Extend the model

- **Blocking keys**: add keys in `blocking_keys` (for example, date of birth or government-ID fragment) to catch duplicates whose contact details changed.
- **Survivorship**: the golden record uses most-recent-wins. Swap in source-priority (prefer `AUTO` over `LEGACY`) or most-complete-record by changing the `groupby` selection.
- **Review queue**: filter `CandidateMatch` to `confidence_tier == "REVIEW"` to route the weakest merges to a steward.

### Scale up / productionize

- Point `Record` at a Snowflake table instead of a CSV (see the data-loading docs) and let the engine cluster at warehouse scale.
- For very large inputs, tighten blocking so candidate counts stay manageable; blocking, not clustering, dominates cost.

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

`model.data(df).to_schema()` drops any row that has an empty or null cell in one of the loaded columns. If your data has optional fields (blank email, phone, etc.), load the always-present columns via `to_schema` and load each optional column only over the rows where it is present, as `load_optional_property` does here. A quick check: `model.select(Record.record_id).to_df().shape[0]` should equal your row count.
</details>

<details>
<summary>Everything merged into one giant party (or nothing merged)</summary>

This is almost always `MATCH_THRESHOLD`. Too low and unrelated records link into a megacluster; too high and real duplicates stay split. Inspect the `score` column on `CandidateMatch` and pick a threshold that separates your true matches from coincidental ones.
</details>

<details>
<summary>Two different people keep merging</summary>

A shared identifier (a recycled phone number, a family email) can over-link. Lower the weight of that field in `pair_score`, require a second corroborating field, or route borderline pairs to the `REVIEW` tier instead of auto-merging.
</details>

## Learn more

- [RelationalAI documentation](https://docs.relational.ai/) — language, modeling, and reasoner reference.
- [Template gallery](https://docs.relational.ai/build/templates) — other runnable templates, including graph and rules-based examples.

## Support

- Questions or issues: [support.relational.ai](https://support.relational.ai).
