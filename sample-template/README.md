---
title: "Template starter"
description: "A starter layout for a runnable RelationalAI template with generated documentation metadata."
private: false
experience_level: beginner
industry: General
reasoning_types:
  - Rules
tags:
  - starter
  - modeling
  - template-authoring
---

## What this template is for

Use this starter when you create a v1 template. Replace the example model,
source mapping, query, metadata, and prose with the behavior of your template.

The starter demonstrates RelationalAI's **rules-based reasoning** authoring
layout without prescribing a business domain.

## Who this is for

- Contributors creating a new v1 template.
- Authors who need a consistent boundary between schema, source loading, and
  runner logic.

## What you'll build

- A stable schema in `model/schema.py`.
- Source reads and base-fact mappings in `model/source.py`.
- A runner that owns reasoning, solves, queries, and reporting.
- A `template-docs.yaml` sidecar for the generated documentation experience.

## What's included

- **Model**: `model/schema.py` declares the concepts, identities, properties,
  and relationships.
- **Sources**: `model/source.py` reads or constructs source data and maps base
  facts into the shared model.
- **Runner**: `template.py` imports the model package and owns executable
  reasoning and reporting.
- **Documentation metadata**: `template-docs.yaml` selects the model subset,
  walkthrough, guide links, and optional sample tables for the docs site.

## Prerequisites

- Python 3.10 or later.
- A RelationalAI account and configured credentials.

## Quickstart

1. Copy this directory into `v1/` and rename it:

   ```bash
   cp -R sample-template v1/your_template_name
   cd v1/your_template_name
   ```

1. Update the package metadata, runner name, source files, README, and
   `template-docs.yaml`.

1. Create an environment and install the template:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install .
   ```

1. Run the renamed entrypoint:

   ```bash
   python template.py
   ```

The example prints the item loaded by `model/source.py`. Your template should
document a similarly small success signal.

## Sample data

The starter uses one in-memory record so the file layout stays compact. Add a
`data/` directory for local files, describe representative tables here, and
select their visible columns in `template-docs.yaml`.

## Model overview

- **Key concept**: `Item` represents the example business record.
- **Primary identifier**: `Item.id`.
- **Source mapping**: `load_sample_data` defines the base fact.

The generated docs extract identities and properties from `model/schema.py`;
do not duplicate them in `template-docs.yaml`.

## How it works

`model/schema.py` creates the model and stable vocabulary. Importing `model`
loads the single source in `model/source.py`. The runner then selects the
modeled records and prints them.

```text
source records -> model/source.py -> model/schema.py -> runner -> output
```

## Customize this template

1. Replace `Item` with the concepts and relationships for the business
   problem.
1. Replace the in-memory record with local or remote source mappings.
1. Add reasoning, solves, queries, and reporting to the runner.
1. Update every sidecar symbol, source path, walkthrough focus, and sample
   column after changing the code.

## Troubleshooting

<details>
<summary>Why does the model fail to connect?</summary>

- Confirm your RelationalAI profile and project configuration.
- Verify that the installed `relationalai` version matches `pyproject.toml`.
</details>

<details>
<summary>Why does the docs preview reject <code>template-docs.yaml</code>?</summary>

- Check for unknown keys, missing symbols, stale anchors, or invalid guide
  routes.
- Run the docs preview because it applies the authoritative strict schema and
  trusted AST extractor.
</details>

## Learn more

- [Declare concepts](https://docs.relational.ai/build/guides/modeling/declare-concepts/)
- [Define base facts](https://docs.relational.ai/build/guides/modeling/define-base-facts/)
- [Query a model](https://docs.relational.ai/build/guides/modeling/query-a-model/)

## Support

Open an issue in this repository with the template path, reproduction steps,
and the failing command or generated-docs error.
