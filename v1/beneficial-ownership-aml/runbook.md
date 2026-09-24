# Runbook: Beneficial Ownership & Control for AML — Multi-Reasoner Walkthrough

A Financial Intelligence Unit has to decide which suspicious transaction reports (STRs) to investigate,
and a report often matters only because of who is really behind the money. This chain turns a company
register, personal links and transactions into scored, explained cases and a budget-feasible
investigation plan. It derives control through ownership chains, predicts family links no registry
records, lifts control to families, scores every STR with explainable AML patterns, and picks the cases
analysts should take within their hours. Four reasoner families work on one ontology.

## The chain

```
5,000 companies, 3,000 persons, 33K transfers and 460 STRs (synthetic). The chain derives control
and ownership, predicts hidden family links, scores and explains every STR, then picks the cases
that cover the most expected value within 400 analyst-hours: OPTIMAL, 14.4M covered, 2.6x the
naive sort-by-score.

  ─────────────────────────────────────────────────────────────────
  STAGE 1  Rules        ──►  Entity.controls, Entity.control_depth, ControlStep
                             Control layer by layer (>50% directly, or with the
                             companies you control); CEO rule; evidence per step.
  ─────────────────────────────────────────────────────────────────
  STAGE 2  Rules        ──►  Entity.phi, Company.close_link
                             Accumulated ownership along paths; ECB close links.
  ─────────────────────────────────────────────────────────────────
  STAGE 3  Graph+Rules  ──►  Person.link (predicted), Family, Family.controls
                             VADA-LINK: Louvain blocks -> candidate pairs ->
                             calibrated Graham probability -> family control.
  ─────────────────────────────────────────────────────────────────
  STAGE 4  Predictive   ──►  Pair.gnn_score, Entity.gnn_account_prob (optional)
                  (GNN)      Link-prediction GNN as one more link feature; account
                             classifier fed with rule outputs.
  ─────────────────────────────────────────────────────────────────
  STAGE 5  Rules        ──►  Finding, STR.score, STR.offence, Case
                             AML patterns, noisy-OR score, offence class, cases.
  ─────────────────────────────────────────────────────────────────
  STAGE 6  Prescriptive ──►  Case.x_inv  (MILP)
                             Maximize expected value within analyst hours, with a
                             cap per offence class. OPTIMAL; 2.6x naive at 400 h.
  ─────────────────────────────────────────────────────────────────
```

## Workflow

> **How to use this walkthrough.** Each section below is a Prompt that an analyst pastes into a fresh agent session loaded with the named `/rai-*` skill. Prompts are designed to run **in order, in a single session**: every step relies on enrichments the previous steps wrote back to the shared ontology. The data comes from the `BENEFICIAL_OWNERSHIP.DATA` Snowflake schema (load it with `python -m data.generator.snowflake_load data/sample BENEFICIAL_OWNERSHIP.DATA`); a HiGHS-enabled prescriptive engine is required, and a predictive engine for the optional GNN step.

### 1. Build ontology

**Prompt**

```
/rai-ontology Build an ontology from the BENEFICIAL_OWNERSHIP.DATA Snowflake schema: companies (with a bank flag) and persons as subtypes of one Entity keyed by eid; shareholdings (owner entity, owned company, share); CEO roles; known personal links between persons (partner, sibling, parent); accounts with their holder and bank; transfers between accounts (amount, timestamp, optional product); invoices (issuer, payee, product); loans (applicant, lending bank); and suspicious transaction reports that point to a loan or a transfer.
```

**Response**

Loads `Company` (5,000, including banks), `Person` (3,000), ownership (8,895 shareholdings), CEO roles, known links, `Account` (~14,700), `Transfer` (~33,000), `Invoice`, `Loan` and `STR` (460). Each STR links to its loan or transfer. Accounts whose holder is not in either register are kept, with no holder.

### 2. Examine ontology

**Prompt**

```
/rai-pyrel What concepts and relationships does the ontology have, and how many rows are in each?
```

**Response**

`Entity` with subtypes `Company` and `Person`; `owns` (owner, company, share); `is_ceo_at`; `link` (person, person, link type, confidence); `Account`, `Transfer`, `Invoice`, `Loan`, `STR`, with the counts above.

### 3. Discover reasoner questions

**Prompt**

```
/rai-discovery We receive suspicious transaction reports and need to know who really controls the banks and companies involved, including through family members the registry doesn't link, then decide which cases our analysts should take within a fixed number of hours. How should we break this down?
```

**Response**

Rules for control and accumulated ownership over the shareholding graph; graph plus rules to predict missing family links (block candidates with communities, score pairs); rules to lift control to families and score each STR; optionally a GNN on accounts using the rule outputs; and a prescriptive MILP to choose cases within the hours budget.

### 4. Derive company control

**Prompt**

```
/rai-pyrel Derive control: an entity controls a company if it holds more than 50% of it, or if together with the companies it already controls it holds more than 50%. Treat a company's CEO as holding 100% of it unless they own shares. Recursion through the sum is not supported, so compute it depth by depth up to 12 levels, check that the last level added nothing, record which holdings contributed to each new control fact, and the first depth at which each control appears.
```

**Response**

About 8,400 direct control pairs and about 14,200 in total. The last layer adds nothing, so control has converged. Each new control fact has `ControlStep` evidence (via whom, which share, at which depth).

### 5. Accumulated ownership and close links

**Prompt**

```
/rai-pyrel Compute accumulated ownership: for each person or company and each company, the sum over ownership paths of the product of the shares, up to 8 hops, ignoring terms below 0.005 and capped at 1.0. Then flag two companies as closely linked if either holds at least 20% of the other, or a third party holds at least 20% of both.
```

**Response**

`Entity.phi` for every reachable pair, and about 27,000 close-link pairs (ECB collateral definition).

### 6. Predict hidden family links

**Prompt**

```
/rai-graph-analysis Build an undirected weighted person-person graph from co-investment (two persons holding shares in the same company), known personal links and shared addresses (skipping addresses shared by more than 20 people), and run Louvain. Then, within each community, pair persons in the same province as partner candidates and persons with the same first three surname letters as sibling candidates, skipping pairs that are already linked.
```

**Response**

About 3,400 blocks with at most 6 persons each and about 450 candidate pairs, out of roughly 4.5 million possible pairs.

**Prompt**

```
/rai-pyrel For each candidate pair, compute features (similar surname, similar address, age gap, different sex for partners, same birth city for siblings, co-investment), combine the calibrated per-feature probabilities in data/sample/feature_probs.csv with Graham's formula p = Πp / (Πp + Π(1-p)), and add a predicted link where p exceeds the thresholds in data/sample/link_thresholds.json. Repeat with the new links until no new link appears (at most 3 rounds).
```

**Response**

About 340 predicted links in 3 rounds. Against the 277 links withheld from the registry: recall about 0.78 and precision about 0.90.

### 7. Families and family control

**Prompt**

```
/rai-pyrel Group persons into families: the closure of known and predicted links, depth by depth up to 12, flagging families that still grow at the limit as oversized. Give each family (2+ members) the summed holdings of its members, let it control whatever a member controls, and rerun control so families can control companies through what they collectively hold.
```

**Response**

About 830 families and about 5,200 family-level control pairs, including control that no single member has.

### 8. (Optional) Train the account classifier

**Prompt**

```
/rai-predictive-modeling Train a binary GNN classifier on accounts using account_labels_train and account_labels_val. Use the transfer graph and the ownership graph as structure, and give each account rule-derived features: structuring days, near-miss credits, cycles, PEP credits from high-risk countries, unregistered counterparties, and whether the holder or the holder's family controls a bank.
```

**Response**

A trained classifier with a validation ROC-AUC of about 0.65–0.8, depending on the run. On held-out STRs the rule features raise the GNN from about 0.64 to 0.79 AUC, but the rules alone reach about 0.93, so on this data the GNN adds little on top of them.

### 9. Score and explain every STR

**Prompt**

```
/rai-pyrel For each STR, record findings with a confidence: the loan applicant or their family controls the lending bank; that control runs through a pyramid of depth 3 or more; the subject or a company they control invoiced without being paid; a near-miss transfer just under 10,000; structuring days; PEP accounts credited from high-risk countries; unregistered counterparties; transfer cycles; fan-in or fan-out; a criminal record. Weight them with data/rule_catalog.csv, score each STR as 1 - Π(1 - weight × confidence), and classify the offence by its strongest finding.
```

**Response**

51 STRs score 0.8 or higher and 78 score between 0.5 and 0.8. Of the planted UBO self-loans, 96% score at least 0.8 with predicted links, against 76% without them. Explanations walk the `ControlStep` evidence from the bank back to the family.

### 10. Choose the cases to investigate

**Prompt**

```
/rai-prescriptive-problem Group related STRs into cases (same subject, same family, or banks controlled by the same family). Each case needs 6 setup hours plus 2 hours per STR and is worth its combined risk times its amount. Choose which cases to investigate to maximize total value within 400 analyst-hours, spending at most half the hours on any one offence class.
```

**Response**

OPTIMAL (HiGHS), 27 cases covering about **14.4M** of expected value within the 400 hours.

### 11. Compare to the naive queue

**Prompt**

```
/rai-prescriptive-results How much more value does the optimized plan cover than simply taking STRs in score order until the hours run out, and how does that change with 100, 200 and 800 hours?
```

**Response**

About **2.6×** the naive queue at 400 hours (14.4M vs 5.5M), 5.3× at 100 hours, 3.4× at 200 and 2.0× at 800. Opening a case once for all its related reports, and weighing value against hours, matters most when hours are scarce.

## Data

Source: the synthetic sample in `data/sample/` (generated by `data/generator/generate.py`; loaded to Snowflake by `data/generator/snowflake_load.py`). Thresholds, depths and the triage budget are in `config.py`; rule weights are in `data/rule_catalog.csv`; the link classifier's calibration is in `data/sample/feature_probs.csv` and `data/sample/link_thresholds.json`. The full chain is in `pipeline.py`, run by `beneficial_ownership_local.py`.
