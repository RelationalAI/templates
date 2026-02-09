---
title: "<YOUR TEMPLATE TITLE>"
description: "<YOUR TEMPLATE DESCRIPTION>"
experience_level: <beginner|intermediate|advanced>
industry: <YOUR TARGET INDUSTRY/SECTOR> (use "General" if broadly applicable)
reasoning_types:
  - Prescriptive
  - Predictive
  - Graph
tags:
  - <KEYWORD_1>
  - <KEYWORD_2>
  - <KEYWORD_3>
---

Problem statement and motivation (1–2 paragraphs).
Focus on the “why” and the value of RelationalAI, not on the technical details of the model or code.
Use language that’s accessible to a broad audience.

**NOTE:** You do not need to add a H1 title at the top of the README.

## Who this is for

- Target audience
- Assumed knowledge

## What you’ll build / learn

- Bullet list of outcomes (3–6)
- Mention the main RelationalAI features used (high level)

## What’s included

- **Model**: (what logic/relations are implemented)
- **Runner**: (how to execute: Python script / CLI commands / notebook)
- **Sample data**: (what it represents)
- **Outputs**: (what results are produced and where)

## Prerequisites

### Access

- RelationalAI account and access to an org/project
- Permissions needed: (if relevant)

### Tools

- Runtime: (Python/Node/etc.) and versions
- RelationalAI tooling used: (CLI / SDK)
- OS notes: (if any)

### Configuration

- Environment variables required (list them)
- Auth setup steps (where/how)

## Quickstart

This section should be copy/paste-friendly and get users to a successful run with minimal reading.

1. **Download or clone**
	- (ZIP instructions if you want, but keep it short)

2. **Install dependencies**

	```bash
	# example
	python -m venv .venv
	source .venv/bin/activate
	pip install -r requirements.txt
	```

3. **Configure credentials**

	```bash
	# example
	export RAI_PROFILE=...
	```

4. **Create/select database + engine** (if applicable)

	```bash
	# example
	rai db create ...
	rai engine create ...
	```

5. **Load sample data**

	```bash
	# example
	python load_data.py
	```

6. **Run the template**

	```bash
	# example
	python run.py
	```

7. **Expected output**

	Show a tiny snippet (a few lines) so users can confirm success.

## Repository structure

Provide a short annotated tree. Keep it to the top level and the most important subfolders.

```text
.
├─ README.md                  # this file
├─ pyproject.toml             # dependencies (if present)
├─ <template>.py              # main runner / entrypoint
├─ data/                      # sample input data
└─ ...
```

**Start here**: point to the one command/script that runs end-to-end.

## Sample data

Describe what the sample data represents, and any important notes about its structure or contents.

## Model overview

Describe the main entities and the most important relationships.

- **Key entities**: (e.g., `product`, `warehouse`, `lane`)
- **Primary identifiers**: what uniquely identifies each entity
- **Important invariants**: (e.g., demand non-negative; capacity limits)

Document the data model concept-by-concept.

### Concepts (one table per concept)

For each key concept/type:

1. Write a brief sentence *outside the table* describing what the concept represents and how it’s used.
2. Add a table with **one row per property**.

Suggested table shape:

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `product_id` | int | Yes | Loaded from `data/products.csv` |
| `name` | string | No | Human-readable name |
| `category` | string | No | Used for grouping/filters |

Repeat this table for each concept (e.g., `product`, `warehouse`, `lane`).

### Relationships (only if there are non-property relations)

Only include a Relationships table if the model defines relations **beyond concept properties** (e.g., standalone predicates like `demand(product, date, units)` or recursive relations).

| Relationship | Schema (reading string fields) | Notes |
|---|---|---|
| `demand(product, date, units)` | `product`, `date`, `units` | Units are weekly; non-negative |
| `lane(source, destination, capacity)` | `source`, `destination`, `capacity` | Capacity is per day |

## How it works

Give a short, end-to-end walkthrough of the template, with relevant code examples. Example:

- Ingest sample CSVs into relations
- Derive intermediate relations (feature engineering / aggregations)
- Apply constraints/objective (if optimization)
- Compute outputs (recommended actions / assignments)
- Export results to CSV / print summary

If helpful, add a small diagram:

```text
CSV inputs → load → base relations → model logic → results → export
```

## Customize this template

Focus on the first changes most users will make.

### Use your own data

- Where to put files / how to change inputs
- Expected schema and example headers
- Validation checks / common mistakes

### Tune parameters

- Where key parameters live
- Suggested defaults and what they change

### Extend the model

- Where to add new relations/logic
- How to add a new constraint/metric/output

### Scale up / productionize

- Engine sizing guidance (if applicable)
- How to schedule runs / integrate into pipelines
- Notes on reproducibility (pin dependencies, deterministic outputs)

## Troubleshooting

Include the top 5–8 failure modes with specific fixes.
Here are some examples:

<details>
	<summary>Why did dependency installation fail?</summary>

	- Confirm you’re using the recommended runtime version (Python/Node) for this template.
	- Use a fresh virtual environment and re-install dependencies.
	- On macOS/Linux, check for missing system libraries if you see compiler/build errors.
</details>

<details>
	<summary>Why did data loading fail (schema/format issues)?</summary>

	- Verify input files match the expected headers and types.
	- Check delimiter/quoting/encoding (CSV UTF-8 is the safest default).
	- Confirm required columns are present and not entirely null/empty.
</details>

<details>
	<summary>Why are my results empty or unexpected?</summary>

	- Sanity-check the input data (row counts, key coverage, date ranges).
	- Check that join keys line up (IDs/codes match across files).
	- Start from the smallest query/output and work forward through the pipeline.
</details>

## Learn more

This section is the “map” into the RelationalAI docs. Keep it curated.

Group links by purpose, and add a one-line description for each.

### Core concepts

- (Link) — What it teaches and how it relates to this template
- (Link)

### Language / modeling reference

- (Link)
- (Link)

### CLI / SDK guides

- (Link)
- (Link)

### Deeper dives (optional)

- (Link) — “If you want to extend X, read this next”

## Support

- Where to ask questions / file issues
