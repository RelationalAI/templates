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

Use this starter when you create a template. Replace the example model,
source mapping, query, metadata, and prose with the behavior of your template.

The starter demonstrates RelationalAI's **rules-based reasoning** authoring
layout without prescribing a business domain.

## Who this is for

- Contributors creating a new template.
- Authors who need a consistent boundary between schema, source loading, and
  queries.

## What you'll build

- A stable schema in `model/schema.py`.
- Source reads and base-fact mappings in `model/source.py`.
- Reasoning and solves declared at module level in the model package, so one
  deploy publishes them.
- A query module that reads the deployed model and prints the report.
- A `template-docs.yaml` sidecar for the generated documentation experience.

## What's included

- **Model**: `model/schema.py` declares the concepts, identities, properties,
  and relationships.
- **Sources**: `model/source.py` reads or constructs source data and maps base
  facts into the shared model.
- **Query**: `queries/item_report.py` imports the model package, reads the
  deployed model, and prints the report.
- **Documentation metadata**: `template-docs.yaml` selects the model subset,
  walkthrough, guide links, and optional sample tables for the docs site.

## Prerequisites

- Python 3.10 or later.
- A Snowflake account that has the RAI Native App installed.
- A role that can deploy models, set up once by an account administrator: follow [Set up model deployment](https://private.relational.ai/early-access/model-deploy-setup) (**Try it out**, or **Governed setup** for a shared account). This starter has no prescriptive solve, so it needs no PAT setup.
- A Snowflake user that holds that role.

## Quickstart

Before you start, install Python 3.10 or later and get a Snowflake role that can deploy models, as described under Prerequisites. This starter has no prescriptive solve, so it needs no setup beyond that role.

Run these steps from a terminal:

1. **Download the template**

   [Download the ZIP](https://docs.relational.ai/templates/zips/v1/sample-template.zip). Unzip it and enter the template directory:

   ```bash
   unzip sample-template.zip
   cd sample-template
   ```

2. **Create a Python environment**

   Create and activate a virtual environment, then update pip:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   ```

3. **Install the template**

   Install the template's dependencies, including the `rai` CLI, in the active environment:

   ```bash
   python -m pip install .
   ```

4. **Configure your project**

   Use the configuration builder in [Install and run PyRel](https://docs.relational.ai/get-started/install-and-run-pyrel/#configure-your-project) to create `raiconfig.yaml` in the template directory, with the model role as the connection `role`.

   Then add a `deployment` section. Give each template its own schema pair so two deployed templates never share one; the deploy creates both schemas if they don't exist:

   ```yaml
   deployment:
     role: <MODEL_ROLE>
     public_schema: <DB>.SAMPLE_TEMPLATE              # published views and tables
     identity:
       internal_schema: <DB>.SAMPLE_TEMPLATE_META     # refresh procedures and metadata
     schedules:
       standard:
         interval_s: 0           # refresh only on deploy or on demand
     schedule: standard
   ```

5. **Deploy the model**

   Deploy the model in `model/` to the schemas in `raiconfig.yaml`:

   ```bash
   rai models deploy --path model
   ```

   The deploy waits for the model's first refresh. Without the `deployment` section, it stops with an error naming the missing setting.

   Deploying again without changing the model applies no updates. A change to the model redeploys it.

6. **Query the results**

   Print the report from the deployed model:

   ```bash
   python -m queries.item_report
   ```

   ```text
      id          name
   0   1  Example item
   ```

   The example prints the item loaded by `model/source.py`. Your template should document a similarly small success signal.

7. **Tear down the deployment**

   Preview what the teardown removes, then remove it:

   ```bash
   rai models teardown
   rai models teardown --force
   ```

   The teardown removes the deployed objects and keeps the two schemas.

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
loads the single source in `model/source.py`. `rai models deploy --path model`
deploys the model and waits for its first refresh. The query module then selects
the modeled records from the deployed model and prints them.

```text
source records -> model/source.py -> model/schema.py -> deploy -> queries/item_report.py -> output
```

## Customize this template

1. Copy this directory to a new root-level template directory and rename it
   (`cp -R sample-template your_template_name`). Update the package metadata,
   the name of the query module, the Quickstart download link and directory
   name, the README, and `template-docs.yaml`.
1. Replace `Item` with the concepts and relationships for the business
   problem.
1. Replace the in-memory record with local or remote source mappings.
1. Declare reasoning and solves at the top level of the `model/` package, which
   the deploy publishes, and put queries and reporting in modules under
   `queries/` that only read the deployed model.
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
