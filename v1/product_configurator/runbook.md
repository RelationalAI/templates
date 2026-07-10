# Product Configurator — Analyst Runbook

A sales or product team configuring a complex product (here, a car) needs more than one valid build — a quote tool, a sales playbook, and a trade-off slider all need the full *population* of legal configurations. Options sit in slots (engine, trim, wheels…), some options require or exclude others, regional rules remove some choices, and the total price has to stay under a ceiling. The dataset is 6 slots, 16 options, and the implies/excludes/regional rules. The analysis enumerates every legal build for one region (EU) under a $20,000 ceiling.

```text
6 slots · 16 options (priced) · 4 implies + 3 excludes rules · regional availability (EU/US)
      │
      ▼
/rai-prescriptive-problem
   • decision: binary "pick this option?" over the region-allowed options
   • constraints: exactly one option per slot; implies (A ⇒ B); excludes (not both);
     total price ≤ $20,000
   • no objective — enumerate the full feasible set (multi-solution mode)
   • MiniZinc constraint solver                  -> 63 legal EU builds
      │
      ▼
/rai-prescriptive-results
   • 63 distinct buildable configurations, $1,500 (cheapest) to $18,200 (loaded)
   • dropping V6 (not EU-allowed) also removes the V6/Manual exclusion from play
```

Each prompt is pasted into a fresh agent session loaded with the named `/rai-*` skill (named at the start of each prompt). They run in order in a single session — the formulate step reads the `Slot`/`Option` concepts and rule relationships the build step created, and the interpret step reads the enumerated solutions.

---

## 1. Build the ontology

**Prompt:** /rai-ontology Build an ontology from `data/slots.csv` (option slots), `data/options.csv` (each option belongs to a slot and has a price in cents), `data/implies.csv` (head option requires tail option), `data/excludes.csv` (two options that can't both be chosen), and `data/regional_rules.csv` (which options are allowed in which region). Model implies and excludes as relationships between options, and region availability as a relationship from an option to the regions it's allowed in.

**Response:** Loads `Slot` (6: Engine, Transmission, Trim, Sound, Wheels, Roof), `Option` (16, each priced and linked to a slot), an `Implies` relationship (4 rules, e.g. Premium Audio → Premium Trim), an `Excludes` relationship (3 symmetric pairs, e.g. V6 / Manual), and option-to-region availability (US allows all 16; EU allows 15 — the V6 is not EU-allowed).

## 2. Examine the ontology

**Prompt:** /rai-pyrel What concepts and relationships does the ontology have, and how many of each? Does every slot have at least one EU-allowed option, and do the implies rules point to EU-allowed options?

**Response:** Concepts: 6 `Slot`, 16 `Option` (priced, slotted). Rule relationships: 4 `Implies`, 3 `Excludes`, plus regional availability. Every slot has at least one EU-allowed option and every implies rule's target is EU-allowed, so the EU catalog is well-formed — the region filter won't silently make a slot unfillable.

## 3. Enumerate the legal EU builds

**Prompt:** /rai-prescriptive-problem Enumerate every legal configuration for the EU region that costs at most $20,000. Use a binary "pick this option" decision over the EU-allowed options, require exactly one option per slot, enforce the implies rules (if the head is picked, the tail must be) and the excludes rules (the two can't both be picked), and keep total price within the ceiling. There's no objective — return the full set of feasible builds in multi-solution mode.

**Response:** OPTIMAL — search exhausted (MiniZinc constraint solver in multi-solution mode). **63 distinct feasible builds** found. Because the EU filter drops the V6, the model has 15 binary option variables and 13 constraints (the V6/Manual exclusion drops out with the V6). The selection is `Option.selected`, with the first solution persisted to the ontology for verification.

## 4. Read the configuration population

**Prompt:** /rai-prescriptive-results How many buildable configurations are there, and what's the price range from the cheapest to the most loaded build?

**Response:** There are **63 buildable EU configurations** under the ceiling, spanning **$1,500 to $18,200**. The cheapest pairs the 1.6L Inline-4, manual transmission, base trim, steel roof, standard sound, and 16-inch alloys; the most loaded build is the 2.0L Turbo with DCT, premium trim, premium audio, panoramic glass, and 18-inch sport wheels. The full population — one row per build — is what feeds a quote tool or trade-off slider, rather than a single "optimal" car.

## Data

Bundled CSVs in `data/`: 6 slots, 16 options, 4 implies rules, 3 excludes rules, regional availability. The target region (EU) and price ceiling ($20,000) are constants in the script. Full model in `product_configurator.py`.
