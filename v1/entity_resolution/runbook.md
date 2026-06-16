# Runbook: Entity Resolution — Multi-Reasoner Walkthrough

An insurer accumulates the same customer many times over: a household holds auto, home, and life policies in separate administration systems, and acquired books of business arrive with their own records. The bundled sample has 50 raw party records — pulled from AUTO (21), HOME (14), LIFE (11), and an acquired LEGACY book (4) — that refer to just 30 real people. The chain resolves them into one record per insured party, so the customer view, total exposure, and sanctions/fraud screening all see one person instead of several, and scores itself against ground-truth labels.

> **Headline figures below are from a real Snowflake-backed run and are deterministic** — the matching is rule-scored (no stochastic model), so the same input reproduces the same 30 parties and `F1 = 1.000` every run. Re-tune the `MATCH_THRESHOLD` and per-field weights (template README, *Tune parameters*) to trade precision against recall on your own data.

## The chain

```
Ontology: 2 concepts — Record (50 raw party records across AUTO/HOME/LIFE/
LEGACY) and CandidateMatch (25 accepted pairwise matches). The chain resolves
50 records into 30 insured parties (20 duplicate records collapsed) and scores
pairwise precision/recall/F1 = 1.000 against the ground-truth labels.

  ─────────────────────────────────────────────────────────────────
  SETUP    Ontology      ──►  Record (50), CandidateMatch (25)
   /rai-build-starter-        Blocking cuts 1,225 possible pairs to 27
   ontology, /rai-            candidates; weighted field-similarity
   pyrel-coding               scoring keeps the 25 pairs >= 0.55.
  ─────────────────────────────────────────────────────────────────
  STAGE 1  Graph         ──►  Record.entity_id  (30 parties)
   /rai-graph-analysis        Weakly-connected-components over match
                              edges; transitive closure merges chains
                              (e.g. the 3 "O'Brien" records).
  ─────────────────────────────────────────────────────────────────
  STAGE 2  Rules         ──►  CandidateMatch.confidence_tier
   /rai-rules-authoring       (HIGH 20 / MEDIUM 2 / REVIEW 3);
                              Record.is_duplicate  (35 records).
  ─────────────────────────────────────────────────────────────────
  STAGE 3  Interpret     ──►  Golden record per party + pairwise
   /rai-querying              precision/recall/F1 = 1.000
                              (true pos 26 / false pos 0 / false neg 0).
  ─────────────────────────────────────────────────────────────────
```

## Workflow

> **How to use this walkthrough.** Each section below is a Prompt that an analyst pastes into a fresh agent session loaded with the named `/rai-*` skill. Prompts are designed to run **in order, in a single session** — every step relies on enrichments the previous steps wrote back to the shared ontology, so the agent inherits accumulated model state across prompts.

### 1. Build the ontology

**Prompt**

```
/rai-build-starter-ontology Build an entity-resolution ontology from data/records.csv. Create a Record concept identified by record_id. Load the always-present columns (source_system, full_name, street, city, state, postal_code, created_at) by schema. Load the optional columns (email, phone, date_of_birth, gov_id_last4) only for the rows where they are non-empty, so a missing value stays null instead of dropping the whole record.
```

**Response**

`Record` concept (PK `record_id`) bound to the bundled CSV, 50 records across four source systems (AUTO 21, HOME 14, LIFE 11, LEGACY 4). The four optional properties are loaded over their non-empty subsets — a single `model.data(df).new(...)` over the full frame would silently drop the 9 records that have a blank email, phone, date of birth, or government ID, so required columns load by schema and each optional column loads via `Record.lookup(...).<prop>(...)` over its present rows.

### 2. Examine the ontology

**Prompt**

```
/rai-querying How many records are there per source system, and how complete are the matchable identifiers — how many records are missing an email, a phone, a date of birth, or a government-ID fragment?
```

**Response**

50 `Record` rows: AUTO 21, HOME 14, LIFE 11, LEGACY 4. Missing identifiers: email 4, phone 4, date of birth 1, government-ID fragment 5 — concentrated in the LEGACY book and a few cross-system records, which is exactly why no single identifier can carry the match and the score has to combine several fields.

### 3. Generate candidate matches

**Prompt**

```
/rai-pyrel-coding Generate candidate duplicate pairs and load them as a CandidateMatch concept (identified by pair_id, with rec_a and rec_b functional links to Record and a float score). Block first: only compare records that share a normalized email handle, the same last-10-digit phone, or the same first-four-of-last-name plus 3-digit postal prefix. Score each candidate pair in [0,1]: +0.45 if full emails match (or +0.32 if only the handle matches across different domains), +0.42 if phones match, +0.30 if dates of birth match, +0.20 if government-ID fragments match, +0.30 * Jaro-Winkler on names (fold nicknames like Bob->Robert first), +0.15 * Jaro-Winkler on the full address. Load every pair scoring >= 0.55 as a CandidateMatch.
```

**Response**

Blocking and the field-similarity scoring run in pandas as a data-prep step — PyRel has no built-in string-similarity (Jaro-Winkler) primitive, so the fuzzy work happens Python-side and only the accepted pairs cross into the model. Blocking reduces the 1,225 possible pairs to 27 candidates (97.8% fewer comparisons); 25 score at or above the 0.55 threshold and load as `CandidateMatch` (`rec_a`, `rec_b`, `score`). `rec_a` and `rec_b` are functional Properties (each match has exactly one of each), populated with `Record.lookup(record_id=...)`. The two sub-threshold candidates are the same-name "John Smith" pair and the O'Brien chain's non-adjacent endpoints — correctly left unmatched.

### 4. Resolve parties

**Prompt**

```
/rai-graph-analysis Which records refer to the same insured party? Treat each CandidateMatch as an undirected link between its two records, and group records that are connected either directly or through a chain of intermediate matches into one party. Write each record's resolved party id back onto Record, and report how many parties the 50 records collapse into.
```

**Response**

A weakly-connected-components pass over 50 record nodes and 25 match edges writes `Record.entity_id` (the component label) and resolves the 50 records into **30 insured parties** — 20 duplicate records collapsed. The transitive case is the payoff: the three "O'Brien" records form one party even though its endpoints share no identifier (record 1014 links to 1015 on phone + date of birth, 1015 links to the legacy record 1016 on email, and 1014 and 1016 match on nothing). A pairwise pass would leave them as two or three separate customers.

### 5. Tier the matches

**Prompt**

```
/rai-rules-authoring How confident is each match? Classify every CandidateMatch into a confidence tier on its score: HIGH at or above 0.90, MEDIUM from 0.75 up to 0.90, and REVIEW from the 0.55 merge threshold up to 0.75 (accepted but resting on the weakest evidence, worth a steward's spot-check).
```

**Response**

`CandidateMatch.confidence_tier` derived by three score bands: **HIGH 20, MEDIUM 2, REVIEW 3** (25 total). The 20 HIGH matches (several identifiers agree) are stable; the 2/3 split at the 0.75 MEDIUM/REVIEW boundary is sensitive to the exact string-similarity implementation, so a faithful re-implementation may divide those few borderline matches slightly differently. The REVIEW tier surfaces the legacy-record merges that clear the threshold on a single shared identifier — e.g. the O'Brien email-only link and the Chen/Whitfield records whose legacy entries match on phone or date of birth alone.

### 6. Flag duplicate records

**Prompt**

```
/rai-rules-authoring Which records are duplicates? Flag every record whose resolved party contains more than one record, so the single-record parties (no match found) are left unflagged.
```

**Response**

`Record.is_duplicate` set on **35 records** — every record that shares its `entity_id` with at least one other, derived by counting records per party and flagging those in a party of size two or more. The remaining 15 records are single-record parties. The flag turns "which records need merging" into a one-predicate query for downstream MDM or screening workflows.

### 7. Golden records and evaluation

**Prompt**

```
/rai-querying For each multi-record party, which record is the golden survivor (the most recently created), and how accurate is the resolution overall — what is the pairwise precision, recall, and F1 against the ground_truth.csv labels?
```

**Response**

15 multi-record parties, each with a golden record chosen by latest `created_at` (swap for source-priority or most-complete in the template's *Customize* section). Scored against the labels by counting record pairs that share a party versus pairs that share a true entity: **precision 1.000, recall 1.000, F1 1.000** (true positives 26, false positives 0, false negatives 0). The 26 true pairs exceed the 25 match edges because transitive closure creates within-party pairs that were never scored directly — the O'Brien and Chen chains each contribute a pair no edge covers.

## Data

Bundled CSVs in `data/`: `records.csv` (50 party records across AUTO / HOME / LIFE / LEGACY, covering 30 people; 15 appear in more than one system, largest party has 4 records) and `ground_truth.csv` (record_id → true party label for evaluation). Two cases are placed deliberately: a transitive chain (`M. O'Brien`) that only clustering resolves, and a same-name trap (two distinct Chicago "John Smith" policyholders) that scoring keeps apart. The dataset is fixed and hand-curated so the walkthrough's numbers are stable. The full chain runs end-to-end via `entity_resolution.py`.
