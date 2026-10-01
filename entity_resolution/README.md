---
title: "Entity Resolution"
description: "Match policy records for the same person or household across insurance systems. Add up their coverage to spot totals above a risk limit, then choose which excess risk to transfer to another insurer within a budget."
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

**Full guide:** [Explore the Entity Resolution model, run the example, and follow the code](https://docs.relational.ai/build/templates/entity_resolution/).

## What this template is for

Insurers often store the same person or household as separate policyholder
records, hiding combined coverage and accumulation risk. This template scores
record matches, clusters high-confidence matches into resolved parties, and
holds uncertain pairs for review. It then totals coverage, flags parties above
a configurable limit, and selects reinsurance cessions within a premium
budget. Adapt the matching fields, thresholds, exposure rules, and decision
constraints for your workflow.

## Quickstart

Before you start, install Python 3.10 or later and get access to a Snowflake
account with the RAI Native App. Graph and Prescriptive reasoning are in Public
Preview; ask your RelationalAI support representative to enable Prescriptive
reasoning. Preview features are for evaluation and testing, not production
applications. The template pins `relationalai==1.13.0` in `pyproject.toml` and
uses HiGHS without a separate solver license.

Use this sequence to run the bundled example:

1. **Download the template**

   [Download the ZIP](https://docs.relational.ai/templates/zips/v1/entity_resolution.zip), unzip it, and enter the template directory:

   ```bash
   unzip entity_resolution.zip
   cd entity_resolution
   ```

2. **Create a Python environment**

   Create and activate a virtual environment, then update pip:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   ```

3. **Install the template**

   Install the dependencies pinned in `pyproject.toml`:

   ```bash
   python -m pip install .
   ```

4. **Configure your project**

   Use the configuration builder in [Start building with PyRel](https://docs.relational.ai/get-started/start-building-with-pyrel/#configure-your-project) to create `raiconfig.yaml` in the template directory and verify your connection.

5. **Run the template**

   Run the bundled script from the template directory:

   ```bash
   python entity_resolution.py
   ```

   ```text
   Auto-resolved 51 records into 31 insured parties.
   Households over the limit after RESOLUTION:       4
     -> ceded $927,000 of excess exposure for $111,240 premium (of $120,000)
   ```

   No single policy breaches the $1M limit, but resolution surfaces four
   over-limit households and the optimizer cedes the most excess it can afford
   within budget. See `runbook.md` for the full workflow.
