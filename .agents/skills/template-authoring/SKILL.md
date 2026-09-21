---
name: template-authoring
description: Create, update, or review RelationalAI templates, including the model package, README, template-docs sidecar, runbook, and validation.
---

# Template authoring

Use this skill for any request to create, refactor, document, or review a
template in this repository.

## Select the operation

- **Create**: start from `sample-template/`, use the v1 layout, and complete
  every required artifact.
- **Update**: preserve the existing command, behavior, and outputs while
  keeping code, README, runbook, and sidecar synchronized.
- **Review**: do not edit. Report reproducibility, structure, documentation,
  sidecar, and validation issues with exact file paths.

Legacy templates without `template-docs.yaml` may remain README-only. Do not
require migration merely because an existing template changed. New
`v1/<slug>/README.md` files require a sidecar, and an adopted sidecar must not
be removed while the template remains.

## Required workflow

1. Read the entire template directory, including its runner, `pyproject.toml`,
   README, runbook, data files, and existing sidecar.
1. Preserve the entrypoint, solver choices, constraints, thresholds, output
   labels, and data semantics unless the request explicitly changes them.
1. For new v1 templates and intentional migrations, use this layout:

   ```text
   v1/<slug>/
   ├── README.md
   ├── template-docs.yaml
   ├── model/
   │   ├── __init__.py
   │   ├── schema.py
   │   └── source.py
   ├── <runner>.py
   ├── runbook.md
   ├── pyproject.toml
   └── data/
   ```

1. Put only stable model declarations in `model/schema.py`: create the
   `Model`, then declare concepts, identity keys, properties, and
   relationships with direct `model.Concept`, `model.Property`, and
   `model.Relationship` calls.
1. Put source reads, normalization, and base-fact mappings in
   `model/source.py`. Keep solver declarations, derived reasoning, result
   queries, and reporting in the runner.
1. Re-export the model and stable schema symbols from `model/__init__.py`.
   A single-source template may load its source on import. A multi-source
   template must expose explicit loader functions and let each runner choose
   the correct one.
1. Keep README commands, code links, `runbook.md`, and `template-docs.yaml`
   aligned with the final paths and symbols.
1. Follow [the sidecar contract](./resources/template-docs.md) and select only
   routes from [the guide catalog](./resources/guide-links.md).
1. Run [focused validation](./resources/validation.md). Do not claim runtime
   verification if credentials, an engine, Snowflake, or other connected
   resources were unavailable.

## README contract

The README remains the complete GitHub quickstart and owns the title,
description, problem statement, prerequisites, runnable commands, expected
output, customization guidance, troubleshooting, and support information.

- Explain the problem before implementation details.
- Put the solution flow in **What you'll build**.
- Use **What's included** to identify the schema, source, runner, runbook,
  sample data, and outputs.
- Do not add a standalone **Template structure** section. The generated docs
  file browser already serves that purpose.
- Use small Markdown tables for representative sample rows. Keep large data
  sets out of the README.
- Keep **Model overview** and **How it works** concise for GitHub readers;
  enhanced docs can omit them through `page.omit_from_readme`.
- Keep the Quickstart copy/paste-friendly and include a small success signal.

## Completion

Report:

- Files changed.
- Behavior intentionally preserved or changed.
- Checks run and their exact outcomes.
- Any connected runtime command that remains unverified and why.
