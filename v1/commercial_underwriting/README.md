---
title: "Commercial Underwriting"
description: "Run rules-based eligibility checks and risk-tier classification across a four-level commercial property/casualty hierarchy (insured entity, policy, location, coverage)."
featured: false
experience_level: intermediate
industry: "Financial Services"
reasoning_types:
  - Rules-based
tags:
  - Rules-Based Reasoning
  - Underwriting
  - Eligibility
  - Risk Classification
  - Hierarchical Ontology
  - Insurance to Value
---

# Commercial Underwriting

## What this template is for

This template uses **Rules-based** reasoning to underwrite a portfolio of commercial property/casualty submissions. It demonstrates how to express real-world insurance rules as declarative derived properties on a four-level hierarchy:

```text
InsuredEntity -> Policy -> Location -> Coverage
```

Each level carries its own eligibility checks. A coverage is checked for insurance-to-value (ITV) adequacy. A location is checked for fire-protection class, year-built, and occupancy class. An insured entity is checked for industry and operating history. Then those flags roll up: any decline factor at any level pushes the entity to the **Decline** tier; marginal factors push it to **Non-Standard**; clean entities are **Standard**, and clean long-tenured entities with the highest fire-protection grades are **Preferred**.

Everything is declarative — no procedural rule chains, no explicit ordering. PyRel resolves dependencies automatically. Rules at lower levels feed entity-level rollup rules, which in turn feed the tier classification.

## Who this is for

- Insurance carriers, MGAs, and brokers automating commercial underwriting triage
- Data scientists building rule engines on hierarchical ontologies
- Developers learning how to chain derived Relationships across multiple concept levels in PyRel

## What you'll build

- A four-level commercial property/casualty ontology with `InsuredEntity`, `Policy`, `Location`, and `Coverage`
- Eight underwriting rules expressed as derived `Relationship` flags on the appropriate level
- Two entity-level rollup rules (decline factors, marginal factors) that aggregate per-entity verdicts from lower-level flags
- Four mutually exclusive risk-tier subtype concepts (`RiskTier_Decline`, `RiskTier_NonStandard`, `RiskTier_Standard`, `RiskTier_Preferred`)
- Reporting that prints the eligibility flag matrix and the final per-entity tier classification

## What's included

- `commercial_underwriting.py` — main script (single end-to-end run)
- `data/insured_entities.csv` — 8 insured businesses across 5 industries
- `data/policies.csv` — 8 commercial property policies (one per insured)
- `data/locations.csv` — 11 scheduled locations across the policies (some entities have multiple)
- `data/coverages.csv` — 33 coverage lines (BUILDING / BUSINESS_PERSONAL_PROPERTY / BUSINESS_INTERRUPTION at every location)
- `pyproject.toml` — Python package configuration with dependencies

## Prerequisites

### Access

- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools

- Python >= 3.10
- RelationalAI Python SDK (`relationalai`) == 1.0.14

## Quickstart

1. Download the ZIP file for this template and extract it:

   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/commercial_underwriting.zip
   unzip commercial_underwriting.zip
   cd commercial_underwriting
   ```

   > [!TIP]
   > You can also download the template ZIP using the "Download ZIP" button at the top of this page.

2. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install -U pip
   ```

3. Install dependencies:

   ```bash
   python -m pip install .
   ```

4. Configure Snowflake connection and RAI profile:

   ```bash
   rai init
   ```

5. Run the template:

   ```bash
   python commercial_underwriting.py
   ```

6. Expected output (truncated):

   ```text
   Stage 1: Location- and coverage-level eligibility flags
   Locations with poor fire protection (FP > 6): 0
   Locations with old construction (year_built < 1950): 1
       location_id                      address  year_built
                 8  800 Foundry Rd Pittsburgh PA        1948
   Locations with high-risk occupancy: 3
       location_id                      address     occupancy
                 7  700 Cannabis Way Denver CO  CANNABIS_RETAIL
                10   900 Highway 10 Phoenix AZ      GAS_STATION
                11    910 Old US 80 Tucson AZ      GAS_STATION
   Underinsured BUILDING coverages (ITV < 80%): 1
       coverage_id           location_address      limit  replacement_value  itv_pct
                13 500 Industry Dr Detroit MI  7500000.0         10000000.0     75.0

   Stage 3: Risk-tier classification
                       name               industry  years         tier
       PreferredCorp Holdings                RETAIL     20    PREFERRED
                  GoodOps Inc  PROFESSIONAL_SERVICES      8     STANDARD
                 AutoFix Plus            AUTO_REPAIR     12 NON-STANDARD
                   ChemFab Co    MANUFACTURING_HEAVY     15 NON-STANDARD
               NewVenture LLC                 RETAIL      1      DECLINE
                    CannaCorp               CANNABIS      5      DECLINE
        OldFactory Industries    MANUFACTURING_LIGHT     25      DECLINE
             GasStation Group                 RETAIL     10 NON-STANDARD

   Tier counts:
       NON-STANDARD    3
       DECLINE         3
       PREFERRED       1
       STANDARD        1

   Premium by tier:
                  count       sum          mean
       DECLINE        3  149500.0  49833.333333
       NON-STANDARD   3  236000.0  78666.666667
       PREFERRED      1   42000.0  42000.000000
       STANDARD       1   18000.0  18000.000000
   ```

   Each entity falls into exactly one tier — the four tier concepts partition the `InsuredEntity` set. The premium-by-tier rollup is the underwriting business view: about $150K of bound premium is associated with submissions that today's rules would decline; about $236K is non-standard and could be repriced.

## Template structure

```text
.
├── README.md                       # this file
├── pyproject.toml                  # dependencies
├── commercial_underwriting.py      # main script (end-to-end)
└── data/
    ├── insured_entities.csv        # top of the hierarchy
    ├── policies.csv                # one policy per insured
    ├── locations.csv               # scheduled locations on the policy
    └── coverages.csv               # coverage lines at each location
```

**Start here:** `python commercial_underwriting.py`.

## Sample data

The eight insureds are designed so each tier is represented and every rule fires at least once:

| Entity | Industry | Years | Why this tier |
|---|---|---|---|
| PreferredCorp Holdings | RETAIL | 20 | Long history, single low-FP location at 100% ITV → **Preferred** |
| GoodOps Inc | PROFESSIONAL_SERVICES | 8 | Clean but only 8 years and FP class 4 → **Standard** |
| AutoFix Plus | AUTO_REPAIR | 12 | Marginal industry list → **Non-Standard** |
| ChemFab Co | MANUFACTURING_HEAVY | 15 | Marginal industry **and** underinsured BUILDING (75% ITV) → **Non-Standard** |
| NewVenture LLC | RETAIL | 1 | Insufficient history (< 3 years) → **Decline** |
| CannaCorp | CANNABIS | 5 | Restricted industry → **Decline** |
| OldFactory Industries | MANUFACTURING_LIGHT | 25 | One location built in 1948 (< 1950 floor) → **Decline** |
| GasStation Group | RETAIL | 10 | Both locations are GAS_STATION (high-risk occupancy) → **Non-Standard** |

## Model overview

### InsuredEntity

The named insured business at the top of the hierarchy.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | Integer | Yes | |
| `name` | String | No | |
| `industry_code` | String | No | Drives industry-based rules (RESTRICTED, MARGINAL) |
| `years_in_business` | Integer | No | Drives the insufficient-history and preferred-eligibility rules |
| `annual_revenue` | Float | No | Carried for reporting; not used by current rules |

### Policy

A commercial property policy bound to one insured entity. Acts as the connector between an entity and its scheduled locations.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | Integer | Yes | |
| `insured_entity` | InsuredEntity | No | Relationship to the named insured |
| `policy_type` | String | No | E.g., `COMMERCIAL_PROPERTY` |
| `effective_date` | String | No | ISO date |
| `total_premium` | Float | No | Used for the premium-by-tier rollup |

### Location

A physical location/building scheduled on a policy.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | Integer | Yes | |
| `policy` | Policy | No | Relationship to the parent policy |
| `address` | String | No | |
| `occupancy_class` | String | No | Drives the high-risk-occupancy rule |
| `year_built` | Integer | No | Drives the old-construction rule |
| `square_feet` | Integer | No | Carried for reporting |
| `fire_protection_class` | Integer | No | ISO Public Protection Class 1-10; drives multiple rules |
| `replacement_value` | Float | No | The denominator for the ITV calculation |

### Coverage

A coverage line scheduled on a location.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | Integer | Yes | |
| `location` | Location | No | Relationship to the parent location |
| `coverage_type` | String | No | One of `BUILDING`, `BUSINESS_PERSONAL_PROPERTY`, `BUSINESS_INTERRUPTION` |
| `coverage_limit` | Float | No | Drives the ITV rule (BUILDING coverages only) |
| `deductible` | Float | No | Carried for reporting |

## How it works

### 1. Lower-level eligibility flags

Boolean flags as unary `Relationship` declarations. Each rule is a single declarative `where(...).define(...)`.

```python
Location.has_poor_fire_protection = model.Relationship(
    f"{Location} has poor fire protection"
)
model.where(
    Location.fire_protection_class > MAX_FP_CLASS_FOR_ELIGIBILITY,
).define(Location.has_poor_fire_protection())
```

For list-based membership (industry, occupancy class), the same flag is defined once per list member — PyRel collects the union of matching rows:

```python
for occ in HIGH_RISK_OCCUPANCIES:
    model.where(Location.occupancy_class == occ).define(
        Location.has_high_risk_occupancy()
    )
```

The ITV check joins across two concept levels in a single `where()`:

```python
Coverage.is_underinsured = model.Relationship(f"{Coverage} is underinsured")
model.where(
    Coverage.coverage_type == "BUILDING",
    Coverage.coverage_limit < ITV_THRESHOLD * Coverage.location.replacement_value,
).define(Coverage.is_underinsured())
```

### 2. Entity-level rollups

Rollup rules traverse the four-level chain `InsuredEntity → Policy → Location → Coverage` to declare an entity-level flag if any descendant satisfies the lower-level rule:

```python
InsuredEntity.has_underinsured_coverage = model.Relationship(
    f"{InsuredEntity} has underinsured coverage"
)
model.where(
    Policy.insured_entity(InsuredEntity),
    Location.policy(Policy),
    Coverage.location(Location),
    Coverage.is_underinsured(),
).define(InsuredEntity.has_underinsured_coverage())
```

A single OR-style aggregator flag (`has_decline_factor`, `has_marginal_factor`) is then defined four times — once per contributing flag — using PyRel's set-union semantics for relationships:

```python
InsuredEntity.has_decline_factor = model.Relationship(
    f"{InsuredEntity} has any decline factor"
)
model.where(InsuredEntity.has_restricted_industry()).define(InsuredEntity.has_decline_factor())
model.where(InsuredEntity.has_insufficient_history()).define(InsuredEntity.has_decline_factor())
model.where(InsuredEntity.has_unprotected_location()).define(InsuredEntity.has_decline_factor())
model.where(InsuredEntity.has_old_construction_location()).define(InsuredEntity.has_decline_factor())
```

### 3. Risk-tier classification via subtype concepts

The four tiers are typed sub-concepts that extend `InsuredEntity`. Each rule populates exactly one of them, and the conditions are written so the four sets partition the `InsuredEntity` set:

```python
RiskTier_Decline = model.Concept("RiskTier_Decline", extends=[InsuredEntity])
RiskTier_NonStandard = model.Concept("RiskTier_NonStandard", extends=[InsuredEntity])
RiskTier_Standard = model.Concept("RiskTier_Standard", extends=[InsuredEntity])
RiskTier_Preferred = model.Concept("RiskTier_Preferred", extends=[InsuredEntity])

model.where(
    InsuredEntity.has_decline_factor(),
).define(RiskTier_Decline(InsuredEntity))

model.where(
    model.not_(InsuredEntity.has_decline_factor()),
    InsuredEntity.has_marginal_factor(),
).define(RiskTier_NonStandard(InsuredEntity))

model.where(
    model.not_(InsuredEntity.has_decline_factor()),
    model.not_(InsuredEntity.has_marginal_factor()),
    model.not_(InsuredEntity.has_non_preferred_location()),
    InsuredEntity.years_in_business >= PREFERRED_MIN_YEARS,
).define(RiskTier_Preferred(InsuredEntity))
```

The script then post-processes by subtracting the Preferred set from the Standard set, since Preferred is a tightened subset of "no decline, no marginal."

## Customize this template

### Use your own data

Replace the four CSVs with your own underwriting submissions. Required columns are listed in the *Model overview* section. The script's `Concept.new(...)` and `Relationship` definitions match the CSV column names exactly — keep the same headers or update the script's `model.data(...)` calls to match.

### Tune parameters

All thresholds are at the top of the script under `# Configure inputs`:

| Parameter | Default | Effect |
|---|---|---|
| `MIN_YEARS_IN_BUSINESS` | 3 | Below this → decline |
| `MAX_FP_CLASS_FOR_ELIGIBILITY` | 6 | Above this → decline |
| `MIN_YEAR_BUILT` | 1950 | Older → decline |
| `ITV_THRESHOLD` | 0.80 | Building coverage limit must reach this fraction of replacement value |
| `RESTRICTED_INDUSTRIES` | tuple | Industries that decline outright |
| `MARGINAL_INDUSTRIES` | tuple | Industries that flag the entity as marginal but acceptable |
| `HIGH_RISK_OCCUPANCIES` | tuple | Occupancy classes that flag the location as marginal |
| `PREFERRED_MIN_YEARS` | 15 | Years-in-business floor for the Preferred tier |
| `PREFERRED_MAX_FP_CLASS` | 3 | All locations must be at this FP class or better |

### Extend the model

- **Add a Driver/Operator concept** under `InsuredEntity` to model named individuals, license history, and MVR (motor vehicle record) checks. Same pattern as `Location`: declare the concept, add a Relationship to the parent, write rules.
- **Add a Catastrophe-Exposure rule** that flags locations in flood zones, earthquake zones, or hurricane-prone counties. Joins to a separate `CatastropheZone` concept.
- **Pricing factor derivation.** Currently the template only classifies risk tier. Add a derived `Property` (not `Relationship`) on `Policy` for `pricing_factor`, computed from a sum of additive multipliers per matched flag. See the `derivation` rule pattern in the [`shipment_compliance`](../shipment_compliance/) template.
- **Subline expansion.** Add `GENERAL_LIABILITY`, `UMBRELLA`, `WORKERS_COMP` policies alongside `COMMERCIAL_PROPERTY`. The four-level structure carries over directly.

## Troubleshooting

<details>
  <summary>Why does <code>OldFactory Industries</code> decline despite 25 years of history?</summary>

  Decline factors are OR-aggregated. The Pittsburgh location's `year_built` is 1948, which fails the construction-floor rule (`< 1950`). The rollup rule `InsuredEntity.has_old_construction_location` fires for OldFactory Industries on the Pittsburgh location alone, even though its Cleveland location built in 2000 is fine. One bad location pushes the entire entity to Decline.
</details>

<details>
  <summary>Why is <code>GoodOps Inc</code> Standard rather than Preferred?</summary>

  GoodOps Inc has only 8 years in business, which is below the `PREFERRED_MIN_YEARS=15` floor. It also has FP class 4 at its single location, which exceeds the `PREFERRED_MAX_FP_CLASS=3` cap. Either factor alone disqualifies it from Preferred. Lowering both thresholds (e.g., `PREFERRED_MIN_YEARS=5`, `PREFERRED_MAX_FP_CLASS=4`) would promote it.
</details>

<details>
  <summary>An entity isn't classified into any tier.</summary>

  The script verifies mutual exclusivity and prints a warning if any entity is unclassified. The most likely cause is a rule condition that doesn't match the data — verify with `model.select(InsuredEntity.id).where(InsuredEntity.has_decline_factor()).to_df()` and the analogous `has_marginal_factor` query that those flags fire as expected.
</details>

<details>
  <summary>Two tiers fire for the same entity.</summary>

  This indicates the tier conditions are not mutually exclusive. The script prints a warning if it finds any overlap. Check the `model.not_()` clauses on the lower-priority tier rules (NonStandard / Preferred / Standard) — each must explicitly exclude the higher-priority tier's flag.
</details>

<details>
  <summary>How do I add a new flag without writing a separate <code>has_decline_factor</code> rule?</summary>

  Decline-factor membership is the union of all `has_decline_factor()` definitions. Add a new flag rule on the appropriate level (e.g., `Location.has_seismic_exposure`), add an entity-level rollup (`InsuredEntity.has_seismic_exposure_location`), then add one more `model.where(InsuredEntity.has_seismic_exposure_location()).define(InsuredEntity.has_decline_factor())` line. PyRel automatically unions all definitions of the same Relationship.
</details>

## Related templates

- [`shipment_compliance`](../shipment_compliance/) — flat rules-based template (single-level entity, no hierarchy)
- [`portfolio_balancing`](../portfolio_balancing/) — uses rules + graph + prescriptive in a chained workflow; rules flag compliance violations that feed downstream optimization
- [`supply_chain_resilience`](../supply_chain_resilience/) — multi-reasoner with rules-based supplier risk classification feeding a network-flow optimizer
