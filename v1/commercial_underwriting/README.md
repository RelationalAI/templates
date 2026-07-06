---
title: "Commercial Underwriting"
description: "Eligibility checks and risk-tier classification across a four-level commercial property/casualty hierarchy (insured entity, policy, location, coverage)."
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

## What this template is for

Commercial property and casualty carriers triage every submission against a book of underwriting rules — insurance-to-value adequacy, fire-protection class, year-built floors, occupancy restrictions, industry appetite, operating history — and the answer for each account depends on the worst thing found anywhere beneath it. One old building or one restricted industry can decline an otherwise clean insured. Encoding that judgment as maintainable, auditable logic (rather than a tangle of procedural if-checks) is the hard part.

This template shows how to express that rulebook as declarative logic on a four-level hierarchy of insured entity, policy, location, and coverage, so lower-level eligibility checks roll up automatically into a per-entity risk tier. The result is an underwriting view that says not just which tier each account lands in, but exactly which rule put it there.

**The reasoning approach is rules-based: every eligibility check and rollup is a declarative derived property, and PyRel resolves the dependencies between levels automatically — no procedural rule chains, no explicit ordering.**

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

- **Model**: the four-level `InsuredEntity` / `Policy` / `Location` / `Coverage` ontology, eight lower-level eligibility rules, two entity-level rollup rules (decline factors, marginal factors), and four mutually exclusive risk-tier subtype concepts — all as declarative derived Relationships.
- **Runner**: `commercial_underwriting.py` — a single Python script that loads the CSVs, applies the rules, and prints results end to end.
- **Runbook**: `runbook.md` — a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the script itself.
- **Sample data**: four CSVs under `data/` — 8 insured businesses across 5 industries (`insured_entities.csv`), 8 commercial property policies one per insured (`policies.csv`), 11 scheduled locations (`locations.csv`), and 33 coverage lines at every location (`coverages.csv`).
- **Outputs**: the printed eligibility flag matrix, the final per-entity tier classification, and the premium-by-tier business rollup.

## Prerequisites

### Access

- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools

- Python >= 3.10
- RelationalAI Python SDK (`relationalai`) == 1.11.0

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

**Start here:** run `python commercial_underwriting.py` for the full run end to end, or follow `runbook.md` to reproduce it step by step with the RAI skills.

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

- **Key entities**: `InsuredEntity`, `Policy`, `Location`, and `Coverage` — a four-level property/casualty hierarchy, plus four mutually exclusive risk-tier subtype concepts (`RiskTier_Decline`, `RiskTier_NonStandard`, `RiskTier_Standard`, `RiskTier_Preferred`) that extend `InsuredEntity`.
- **Primary identifiers**: each level has an integer `id`; the hierarchy is threaded by relationships (`Policy.insured_entity`, `Location.policy`, `Coverage.location`) rather than by shared keys.
- **Important invariants**: every policy belongs to exactly one insured entity, every location to one policy, every coverage to one location; the ITV check applies to `BUILDING` coverages only; the four risk tiers partition the `InsuredEntity` set (each entity lands in exactly one).

For the full concept and property definitions, see `commercial_underwriting.py`; `runbook.md` builds them step by step with the RAI skills.

## How it works

Rules run at three altitudes on the hierarchy and feed each other. A coverage is checked for insurance-to-value (ITV) adequacy; a location for fire-protection class, year-built, and occupancy class; an insured entity for industry and operating history. Each check is a declarative flag: a single `where(...).define(...)`, defined once per member for list-based checks (industry, occupancy) so PyRel unions the matches, and joining across concept levels in one clause for the ITV check.

Those lower-level flags then roll up. Entity-level rollup rules traverse the `InsuredEntity → Policy → Location → Coverage` chain to raise a flag on the entity if any descendant matches, and an OR-style aggregator (`has_decline_factor`, `has_marginal_factor`) unions the contributing flags via PyRel's set-union semantics. The tiers themselves are typed sub-concepts that extend `InsuredEntity`: any decline factor pushes the entity to **Decline**, marginal factors to **Non-Standard**, clean entities are **Standard**, and clean long-tenured entities with the highest fire-protection grades are **Preferred**. The tier conditions are written with explicit exclusions so the four sets partition the `InsuredEntity` set — Preferred being a tightened subset of "no decline, no marginal." Everything is declarative: lower-level rules feed entity-level rollups, which feed the tier classification, and PyRel resolves the ordering.

```text
InsuredEntity -> Policy -> Location -> Coverage
```

See `commercial_underwriting.py` for the implementation and `runbook.md` to reproduce it step by step with the RAI skills.

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

### Scale up / productionize

- **Point at Snowflake tables.** Swap the CSV `model.data(...)` calls for `model.Table(...)` references to your submission tables; the ontology, rules, and tier classification are unchanged. Size the RAI engine to the submission volume — rules-based classification is lightweight, so a small engine handles large books.
- **Schedule triage runs.** Wire the script into your submission-intake pipeline (nightly batch or on-submission trigger) so every new account is scored as it arrives, and persist the per-entity tier and flag matrix for downstream underwriting review.
- **Pin dependencies for reproducibility.** Keep the `relationalai` version pinned in `pyproject.toml` so rule outcomes stay stable across runs, and version-control your threshold constants (top of the script) as auditable underwriting parameters.

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

## Learn more

### Core concepts

- [PyRel v1 modeling](https://docs.relational.ai/) — concepts, properties, and derived Relationships, the building blocks this template uses at every level.
- [Rules-based reasoning](https://docs.relational.ai/) — authoring declarative business rules and letting the engine resolve their dependencies.

### Language / modeling reference

- [Derived Relationships and set-union semantics](https://docs.relational.ai/) — how defining the same Relationship multiple times unions the matches, the pattern behind the OR-style rollups.
- [Subtype concepts (`extends`)](https://docs.relational.ai/) — modeling mutually exclusive risk tiers as sub-concepts of `InsuredEntity`.

### CLI / SDK guides

- [`rai init` and `raiconfig.yaml`](https://docs.relational.ai/) — connecting the template to your RelationalAI account.

## Support

- File issues at the RelationalAI templates repository.

## Related templates

- [`shipment_compliance`](../shipment_compliance/) — flat rules-based template (single-level entity, no hierarchy)
- [`portfolio_balancing`](../portfolio_balancing/) — uses rules + graph + prescriptive in a chained workflow; rules flag compliance violations that feed downstream optimization
- [`supply_chain_resilience`](../supply_chain_resilience/) — multi-reasoner with rules-based supplier risk classification feeding a network-flow optimizer
