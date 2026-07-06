---
title: "<YOUR TEMPLATE TITLE>"
description: "<YOUR TEMPLATE DESCRIPTION>"
private: false
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

## What this template is for

Problem statement and motivation (1–2 paragraphs).
Focus on the “why” and the value of RelationalAI, not on the technical details of the model or code.
Use language that’s accessible to a broad audience.

**NOTE:** You do not need to add a H1 title at the top of the README.

## Who this is for

- Target audience
- Assumed knowledge

## What you’ll build

- Bullet list of outcomes (3–6)
- Mention the main RelationalAI features used (high level)

## What’s included

- **Model**: (what logic/relations are implemented)
- **Runner**: (how to execute: Python script / CLI commands / notebook)
- **Runbook**: `runbook.md` — a paste-testable walkthrough that reproduces the template step by step with the RAI skills. The recommended way to learn how it is built; as important a reference as the script itself.
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

## Template structure

Provide a short annotated tree. Keep it to the top level and the most important subfolders.

```text
.
├─ README.md                  # this file
├─ pyproject.toml             # dependencies (if present)
├─ <template>.py              # main runner / entrypoint
├─ data/                      # sample input data
└─ ...
```

**Start here**: name the one command/script that runs end-to-end, and point to `runbook.md` to reproduce the template step by step with the RAI skills.

## Sample data

Describe what the sample data represents, and any important notes about its structure or contents.

## Model overview

Give the reader the shape of the model at a glance — the README is the map, not the schema. Keep this to the three intro bullets; the full concept-and-property definitions live in the script, so don't restate them here.

- **Key entities**: (e.g., `product`, `warehouse`, `lane`) — name the concepts and, in a phrase each, what they represent
- **Primary identifiers**: what uniquely identifies each entity
- **Important invariants**: (e.g., demand non-negative; capacity limits)

For the full concept and property definitions, read `<template>.py`; to see them built step by step with the RAI skills, follow `runbook.md`.

## How it works

Give a short, plain-language walkthrough of the chain — what each stage reads and produces and why — so a reader understands the flow without opening the code. Keep code out of this section: point to the script for the implementation and to `runbook.md` for the skill-driven reproduction. One small flow diagram is welcome:

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
