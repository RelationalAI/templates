# Underwriting Audit — Analyst Runbook

A model-risk or RegTech reviewer needs to verify that an underwriting ruleset actually enforces its stated policies — e.g. "every frail applicant must go through manual review." Hand-checking and sampled test cases miss failures that aren't in the sample. This template treats the audit as formal verification: encode the rule pack as constraints, then ask the solver whether any valid applicant can *falsify* each property, returning concrete counterexample applicants when one can. The dataset is two small reference dimensions (age buckets, coverage bands); an applicant is a set of attributes the solver varies. The analysis audits 3 properties against a ruleset that contains a deliberate bug.

```text
underwriting rule pack (senior / frail / manual-review rules) · applicant attributes (age, coverage, chronic flag)
      │
      ▼
/rai-prescriptive-problem
   • encode the rules as constraints over an applicant's attributes
   • per audited property: search for a counterexample — an applicant that obeys the rules
     but violates the property — enumerating up to 16 distinct witnesses (multi-solution mode)
   • MiniZinc constraint solver                  -> 3 properties audited
      │
      ▼
/rai-prescriptive-results
   • 1 PASS, 2 FAIL: "frail ⇒ review" fails (12 witnesses), "chronic under-50 ⇒ review" fails (8)
   • root cause: manual-review keys only off senior, missing the chronic arm of frailty
```

Each prompt is pasted into a fresh agent session loaded with the named `/rai-*` skill (named at the start of each prompt). They run in order in a single session — the formulate step reads the reference dimensions the build step created, and the interpret step reads the audit verdicts and counterexamples the solve produced.

---

## 1. Build the ontology

**Prompt:** /rai-ontology Build an ontology from `data/age_buckets.csv` (each bucket is an id and an age in years) and `data/coverage_bands.csv` (each band is an id and a coverage amount). These are the reference dimensions for an applicant, who is described by an age bucket, a coverage band, and a chronic-condition flag.

**Response:** Loads `AgeBucket` (4: ages 28, 45, 55, 72) and `CoverageBand` (4: $100k, $250k, $500k, $1M). These define the space of possible applicants; the applicant's attributes and the underwriting rules are added in the audit step.

## 2. Examine the ontology

**Prompt:** /rai-pyrel What concepts and relationships does the ontology have, and how many rows are in each?

**Response:** Two reference concepts — 4 `AgeBucket` (28/45/55/72 years) and 4 `CoverageBand` ($100k/$250k/$500k/$1M). Together they bound the applicant space the audit searches over.

## 3. Audit the ruleset for counterexamples

**Prompt:** /rai-prescriptive-problem Encode the underwriting rules as constraints over an applicant's attributes: an applicant is senior if their age is at least 70; frail if senior or chronically ill; and the ruleset flags an applicant for manual review if they are senior. Then audit three properties — (a) every senior is flagged for review, (b) every frail applicant is flagged for review, (c) every chronically-ill applicant under 50 is flagged for review — by searching for a counterexample for each: an applicant who satisfies the rules but violates the property. Enumerate up to 16 distinct counterexample applicants per property (multi-solution mode). A property passes only if no counterexample exists.

**Response:** Each property is audited as a fresh constraint problem (MiniZinc) over 6 applicant decision variables. A property with no feasible counterexample is INFEASIBLE — meaning it holds (PASS); a property with feasible counterexamples FAILS, and each witness is a concrete applicant exhibiting the gap.

## 4. Read the audit report

**Prompt:** /rai-prescriptive-results Which properties pass, which fail, how many counterexamples does each failure have, and what do they reveal about the rule pack?

**Response:** **1 PASS, 2 FAIL.** "Every senior is reviewed" **passes** (no counterexample exists). "Every frail applicant is reviewed" **fails with 12 counterexamples**, and "every chronically-ill applicant under 50 is reviewed" **fails with 8** (a strict subset — the under-50 chronic cases). The witnesses share a shape: chronically-ill, non-senior applicants who are frail but never flagged. The root cause is a one-line gap — manual review is keyed only off *senior*, so it misses the chronic arm of frailty. The audit names the exact failure population rather than just reporting "a test failed."

## Data

Bundled CSVs in `data/`: 4 age buckets, 4 coverage bands. The rule pack, the audited properties, and the witness cap (16) are defined in the script. Full model in `underwriting_audit.py`.
