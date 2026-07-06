# Runbook: Entity Resolution — Multi-Reasoner Walkthrough

An insurer holds the same customer many times over: a household carries auto, home, and life policies in separate admin systems, and an acquired book (LEGACY) arrives with its own records. The bundled sample has 51 policy records -- AUTO, HOME, LIFE, and LEGACY -- referring to just 30 real people. Resolution is the step that makes the downstream reasoning correct: until the records are resolved, each insured's *total* exposure to the carrier is invisible, so no single policy looks dangerous while several households quietly breach an accumulation limit. The chain resolves the records, aggregates exposure per resolved household, flags the breaches, and chooses minimum-cost reinsurance cessions to clear them.

## The chain

```
Ontology: Record (51 policy records with per-policy coverage), CandidateMatch
(25 auto-merge pairs) and ReviewPair (1 held pair). The chain resolves 51 records
into 31 insured parties, flags 4 accumulation breaches that are invisible at the
record level, and cedes $927k of excess exposure to reinsurance for $111k.

  ─────────────────────────────────────────────────────────────────
  SETUP    Ontology + candidates  ──►  Record (51), CandidateMatch (25),
   /rai-build-starter-ontology,        ReviewPair (1). Blocking -> 28 candidate
   /rai-pyrel-coding                   pairs; two bands: >= 0.70 auto-merge,
                                       [0.55, 0.70) held for review.
  ─────────────────────────────────────────────────────────────────
  STAGE 1  Graph        ──►  Record.entity_key  (31 auto-resolved parties)
   /rai-graph-analysis        Weakly-connected-components over the auto-merge
                              edges; transitive closure (e.g. the 3 O'Brien
                              records).
  ─────────────────────────────────────────────────────────────────
  STAGE 2  Rules        ──►  CandidateMatch.confidence_tier; Record.is_duplicate;
   /rai-rules-authoring       ResolvedParty.total_exposure + is_over_limit.
                              0 record-level breaches -> 4 resolved households.
  ─────────────────────────────────────────────────────────────────
  STAGE 3  Prescriptive ──►  ResolvedParty.cede  (reinsurance knapsack)
   /rai-prescriptive-         OPTIMAL: cede Fitzgerald + Chen -> $927,000 of
   problem-formulation        excess exposure for $111,240 of the $120,000 budget.
  ─────────────────────────────────────────────────────────────────
  STAGE 4  Interpret    ──►  record-vs-resolved breach contrast; review queue
   /rai-querying              (+1 hidden breach); precision 1.000 / recall 0.963.
  ─────────────────────────────────────────────────────────────────
```

## Workflow

> **How to use this walkthrough.** Each section below is a Prompt that an analyst pastes into a fresh agent session loaded with the named `/rai-*` skill. Prompts are designed to run **in order, in a single session** — every step relies on enrichments the previous steps wrote back to the shared ontology, so the agent inherits accumulated model state across prompts.

### 1. Build the ontology

**Prompt**

```
/rai-build-starter-ontology Build an entity-resolution ontology from data/records.csv. Create a Record concept identified by record_id. Load the always-present columns (source_system, full_name, street, city, state, postal_code, created_at, coverage_amount) by schema; read coverage_amount as a float. Load the optional columns (email, phone, date_of_birth, gov_id_last4) only for the rows where they are non-empty, so a missing value stays null instead of dropping the whole record.
```

**Response**

`Record` (PK `record_id`) bound to the bundled CSV, 51 policy records across AUTO (21), HOME (14), LIFE (12), LEGACY (4), each with a `coverage_amount` (sum insured). The four optional identifiers load over their non-empty subsets via `Record.lookup(...).<prop>(...)` -- a single `.new(...)` over the full frame would drop the records with a blank email, phone, date of birth, or government ID.

### 2. Examine the ontology

**Prompt**

```
/rai-querying How many records are there per source system, how complete are the matchable identifiers (email, phone, date of birth, government-ID fragment), and does any single policy's coverage already exceed a $1,000,000 accumulation limit?
```

**Response**

51 records: AUTO 21, HOME 14, LIFE 12, LEGACY 4. Missing identifiers concentrate in the legacy/cross-system records (email 5, government ID 6, phone 4, date of birth 1). No single policy's `coverage_amount` reaches $1,000,000 -- so any accumulation breach can only appear after policies are resolved into one household.

### 3. Generate candidate matches in two bands

**Prompt**

```
/rai-pyrel-coding Generate candidate duplicate pairs and split them into two bands. Block first: only compare records that share a normalized email handle, the same last-10-digit phone, the same first-four-of-last-name plus 3-digit postal prefix, or the same date of birth. Score each candidate in [0,1]: +0.45 full email match (or +0.32 handle-only), +0.42 phone, +0.30 date of birth, +0.20 government-ID fragment, +0.30 * Jaro-Winkler on names (fold nicknames like Bob->Robert first), +0.15 * Jaro-Winkler on the full address. The fuzzy scoring runs in pandas (no string-similarity primitive in PyRel). Load pairs scoring >= 0.70 as a CandidateMatch concept (auto-merge) and pairs in [0.55, 0.70) as a ReviewPair concept (held for a steward), each with rec_a, rec_b, and score.
```

**Response**

Blocking reduces 1,275 possible pairs to 28 candidates. 25 score >= 0.70 and load as `CandidateMatch` (auto-merge); 1 lands in `[0.55, 0.70)` and loads as `ReviewPair`. The two sub-0.55 candidates -- the same-name "John Smith" pair and the O'Brien chain's non-adjacent endpoints -- are correctly dropped. The lone review pair is two policies that share only a date of birth.

### 4. Resolve parties

**Prompt**

```
/rai-graph-analysis Which records refer to the same insured party? Treat each CandidateMatch as an undirected link and group records connected directly or through a chain of matches into one party (connected components). Weakly-connected-components returns the representative record, so also derive a stable integer party key from it, and report how many parties the 51 records auto-resolve into.
```

**Response**

Weakly-connected-components over 51 nodes and 25 auto-merge edges resolves the records into 31 auto-resolved parties (the 30 true people plus one split: the review-band pair is not merged). `Record.entity_key` is derived from the representative node's `record_id`. The transitive O'Brien party holds together even though its endpoints share no identifier -- a pairwise pass would leave them separate.

### 5. Tier matches and flag duplicates

**Prompt**

```
/rai-rules-authoring Classify each auto-merge CandidateMatch by confidence: HIGH at or above 0.90, otherwise MEDIUM. Separately, flag every record whose resolved party contains more than one record as a duplicate.
```

**Response**

`CandidateMatch.confidence_tier` set to HIGH (20) or MEDIUM (5) across the 25 auto-merge matches. `Record.is_duplicate` flags 35 records -- every record sharing its party with at least one other -- derived by counting records per `entity_key` and flagging parties of size two or more.

### 6. Aggregate exposure and flag accumulation breaches

**Prompt**

```
/rai-rules-authoring For each resolved party, total the coverage across its policies, and flag the parties whose total exposure exceeds the $1,000,000 accumulation limit. How many policies breach the limit at the record level versus how many households breach it after resolution?
```

**Response**

A `ResolvedParty` per party key carries `total_exposure` (summed `coverage_amount`) and an `is_over_limit` flag. **0 policies breach at the record level; 4 households breach after resolution** -- Drew Fitzgerald ($1,892,000), Katie Nguyen ($1,406,000), Trish Johnson ($1,240,000), and Bob Chen ($1,035,000). The accumulation was invisible until resolution combined each household's policies.

### 7. Choose reinsurance cessions within budget

**Prompt**

```
/rai-prescriptive-problem-formulation We can spend a $120,000 reinsurance premium this period, at a 12% rate on line, to cede the excess exposure of breached households (premium = 12% of the amount over the limit). Which households should we cede to transfer the most excess exposure off the book? Each breached household is cede-or-not (binary), total premium must stay within budget, and we maximize the excess exposure ceded.
```

**Response**

A binary `ResolvedParty.cede` over the 4 breached households; budget constraint `sum(premium * cede) <= 120,000`; objective maximize `sum(excess * cede)`. Status OPTIMAL: cede **Fitzgerald** (excess $892,000, premium $107,040) and **Chen** (excess $35,000, premium $4,200) -- $927,000 of excess exposure transferred for $111,240 of the $120,000 budget. Nguyen and Johnson don't fit and are kept (candidates for next period or facultative placement).

### 8. Review queue and evaluation

**Prompt**

```
/rai-querying How many matches are held in the review queue, and would confirming them change the accumulation picture? Also score the auto-resolution against the ground_truth.csv labels: pairwise precision, recall, and F1.
```

**Response**

1 pair sits in the review queue. Confirming it merges a household whose combined exposure is $1,055,000 -- a **5th breach** that auto-resolution missed (resolution would then show 5 breached households, not 4), which is exactly why the queue is worth a steward's time. Against the labels: **precision 1.000, recall 0.963, F1 0.981** (true positives 26, false positives 0, false negatives 1 -- the one miss is the held review pair). High-precision automation, with the recall gap parked in the review queue rather than auto-merged.

## Data

Bundled CSVs in `data/`: `records.csv` (51 policy records across AUTO / HOME / LIFE / LEGACY, covering 30 people, with per-policy `coverage_amount`) and `ground_truth.csv` (record_id → true party label). Three cases are placed deliberately: a transitive chain (`M. O'Brien`) that only clustering resolves, a same-name trap (two distinct Chicago "John Smith" policyholders) that scoring keeps apart, and a review-band duplicate (`Ethan Brooks` / `E. Brooks`) whose hidden combined exposure breaches the limit only once confirmed. The dataset is fixed and hand-curated so the walkthrough's numbers are stable. The full chain runs end-to-end via `entity_resolution.py`.
