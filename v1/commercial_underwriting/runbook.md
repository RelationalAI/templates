# Commercial Underwriting — Analyst Runbook

A commercial property & casualty carrier needs to triage a portfolio of submissions — write, decline, or flag for special handling — against the underwriting guardrails an analyst would otherwise apply by hand. Each insured business has policies, each policy schedules physical locations, and each location carries coverage lines. This template encodes the guardrails as declarative rules across that four-level hierarchy, rolls per-location and per-coverage flags up to the business, and sorts every insured into exactly one risk tier. The dataset is 8 insured entities, 8 policies, 11 locations, and 33 coverages.

```text
8 insured entities → 8 policies → 11 locations → 33 coverages
      │
      ▼
/rai-pyrel  (layered derived flags, then a risk tier, then the triage readout)
   • location/coverage flags: poor fire protection, old construction, high-risk occupancy, underinsured
   • roll up to the entity: has_decline_factor, has_marginal_factor
   • classify each insured into one tier: Decline / Non-Standard / Standard / Preferred
   • read the tier of each insured + premium by tier
     -> Decline 3 · Non-Standard 3 · Standard 1 · Preferred 1
```

Each prompt is pasted into a fresh agent session loaded with the named `/rai-*` skill (named at the start of each prompt). They run in order in a single session — the rules step writes flags and tiers back onto the concepts the build step created, then reads the triage out of them.

---

## 1. Build the ontology

**Prompt:** /rai-ontology Build an ontology from `data/insured_entities.csv` (each business has an industry code, years in business, and annual revenue), `data/policies.csv` (each policy is bound to an insured entity and has a total premium), `data/locations.csv` (each location is scheduled on a policy and has an occupancy class, a year built, a fire protection class, and a replacement value), and `data/coverages.csv` (each coverage is scheduled on a location with a coverage type and limit). Model the hierarchy: entity to policy to location to coverage.

**Response:** Loads `InsuredEntity` (8, with industry / years-in-business / revenue), `Policy` (8, one per entity, with premium), `Location` (11, with occupancy class, year built, fire protection class, replacement value), and `Coverage` (33, three lines per location) — a four-level entity-to-coverage hierarchy.

## 2. Examine the ontology

**Prompt:** /rai-pyrel What concepts and relationships does the ontology have, and how many rows are in each?

**Response:** Four concepts in a hierarchy — 8 `InsuredEntity`, 8 `Policy` (bound to entities), 11 `Location` (scheduled on policies), and 33 `Coverage` (scheduled on locations, three coverage lines each).

## 3. Author the underwriting rules and read the triage

**Prompt:** /rai-pyrel Encode the underwriting guardrails as layered flags. At the location level: poor fire protection (fire protection class above 6), old construction (built before 1950), high-risk occupancy (gas station, cannabis retail, fast-food, or habitational). At the coverage level: underinsured (a building coverage limit below 80% of the location's replacement value). Roll these up to each insured: a **decline factor** is a restricted industry, fewer than 3 years in business, or any unprotected/old-construction location; a **marginal factor** is a marginal industry, a high-risk-occupancy location, or an underinsured coverage. Then classify each insured into exactly one risk tier: **Decline** if it has any decline factor; otherwise **Non-Standard** if it has any marginal factor; otherwise **Preferred** if it's well-established (15+ years) with every location well-protected; otherwise **Standard**. How many insured entities fall in each tier, and what premium does each tier represent?

**Response:** Authors the location flags (`has_poor_fire_protection`, `has_old_construction`, `has_high_risk_occupancy`), the coverage flag (`is_underinsured`), the entity rollups (`has_decline_factor`, `has_marginal_factor`), and four mutually-exclusive risk-tier subtype concepts. The rules are declarative, so the reasoner resolves their dependency order automatically and every insured lands in exactly one tier. The 8 insureds partition cleanly: **3 Decline** (a cannabis business, one under 3 years old, one with pre-1950 construction), **3 Non-Standard** (marginal industries or a high-risk-occupancy/underinsured location), **1 Standard**, and **1 Preferred** (15+ years, every location well-protected). Premium concentrates in Non-Standard (~$236k across 3) versus Decline (~$150k) — so the book's exposure is mostly in the marginal tier, exactly the segment underwriting should price and monitor most closely.

## Data

Bundled CSVs in `data/`: 8 insured entities, 8 policies, 11 locations, 33 coverages. Full model in `commercial_underwriting.py`.
