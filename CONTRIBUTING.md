# Contributing

This repository contains runnable RelationalAI templates. Each template is a small, self-contained example with code, sample data, and documentation.

This guide covers the expected workflow for adding a new template or updating an existing one.

## Create a template directory

Put each template in a root-level directory named for its slug. Keep the
`relationalai` package version pinned in the template's `pyproject.toml`.

Examples:

```bash
cp -R sample-template <your_template_name>
```

The starter demonstrates the current `model/` package and
`template-docs.yaml` contract.

## Repository setup

Use one environment for repository-level maintenance tasks such as hooks and generated indexes.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements-dev.txt
pre-commit install
```

Template runtime dependencies are managed separately inside each template folder.

## Linting

This repository uses Ruff to lint Python template code.

- Local command from the repository root:

  ```bash
  ruff check */
  ```

- Pre-commit hook (configured in `.pre-commit-config.yaml`):

  ```bash
  pre-commit run ruff-check --all-files
  ```

- CI workflow: `.github/workflows/lint.yml` runs the same Ruff check on pull requests and on pushes to `main`.

## Add a new template

1. Copy `sample-template/` to a new root-level directory named for your template.
2. Rename the main runner, package metadata, and starter identifiers so they match the folder name.
3. Implement the schema, source mappings, runner logic, sample data, and outputs.
4. Replace the starter README content and update every field in `template-docs.yaml`.
5. Run focused lint, compilation, policy, and index checks.
6. Run the template from a fresh environment and verify that the README Quickstart works as written.

The sample template is the source of truth for the expected file layout and README structure.

At a minimum, make sure your template includes:

- `README.md` with complete front matter and no placeholder text
- `template-docs.yaml` with valid model, walkthrough, guide, and sample-data references
- `pyproject.toml` with a pinned `relationalai` dependency
- `model/schema.py` for model creation and stable declarations
- `model/source.py` for source reads, normalization, and base-fact mappings
- `model/__init__.py` for stable exports
- a runnable entrypoint such as `<template_name>.py` or a notebook
- `runbook.md` that uses the same paths, symbols, and commands
- `data/` when the template reads local sample files
- sample data and output paths that match both the code and the README

Keep solver declarations, derived reasoning, result queries, and reporting in
the runner. A template with one source mode may load it when `model` is
imported. A template with multiple source modes must expose explicit loader
functions and let each runner choose one.

## Generated documentation sidecars

`template-docs.yaml` opts a template into the enhanced generated documentation
page. The docs build treats it as inert data, validates it with a strict schema,
and resolves its paths and Python symbols without importing the template.

Contributor policy is incremental:

- Every newly added `<slug>/README.md` must be accompanied by
  `<slug>/template-docs.yaml`.
- Existing README-only templates may be updated without adopting a sidecar.
- Once a template has a sidecar, do not delete it while the template remains.
- A present sidecar must stay valid after source or documentation changes.

Use `sample-template/template-docs.yaml` as the minimal example. Read
`.agents/skills/template-authoring/SKILL.md` for the exact field contract,
model-package boundaries, guide-link catalog, and focused validation workflow.

## Update an existing template

When changing an existing template:

- keep the README, code, and sample data in sync
- keep the runbook and any `template-docs.yaml` paths, symbols, anchors, and columns in sync
- keep dependency changes minimal and explicit
- verify that any renamed files, commands, or outputs are reflected in the README
- rerun any local validation steps that the change affects

## README expectations

An authentic template contribution is mostly about reproducibility. The README should let someone unfamiliar with the template run it successfully from scratch.

Reviewers will expect the README to:

- include complete front matter metadata
- explain what the template is for and who it is for
- provide a copy/paste-friendly Quickstart
- use the correct entrypoint and install commands
- describe the sample data and outputs accurately
- omit a standalone **Template structure** section

For an enhanced template whose sidecar sets `page.download_and_run_from_readme: true`,
the README can contain only **What this template is for** and **Quickstart**,
with a link before the first section to its generated model explorer and
walkthrough. Set `page.omit_readme_preamble: true` so that link does not
reappear on the docs page. Keep prerequisites, pinned dependencies, runnable
commands, expected results, and any required data attribution in Quickstart.
The README and generated run steps must agree.

For a longer README, use **What's included** to name the schema, source,
runner, runbook, sample data, and outputs. Use small Markdown tables for
representative sample rows where helpful.

> [!TIP]
> Use the `create-template-readme` prompt in Copilot Chat to draft the README
> and sidecar from the template code, then edit both for accuracy.
> After code changes, use `update-template-readme` to refresh all affected
> documentation and review the result manually.

## Use VS Code prompts to help development

This repo includes prompt files under `.github/prompts/` that you can run from VS Code to speed up documentation and reviews.

Useful prompts:

- `cleanup-template-code` - refactor a template into the standard model package without changing behavior
- `create-template-readme` - create a README and sidecar from the template code
- `update-template-readme` - keep a README, runbook, and sidecar aligned after code changes
- `review-template` - review code, dependencies, data, README, runbook, sidecar, and validation evidence

Each prompt defers to `.agents/skills/template-authoring/SKILL.md`, which is the
canonical authoring workflow.

### How to run a prompt in Copilot Chat

In VS Code, open Copilot Chat, then run one of the repo prompts from `.github/prompts/` and provide its inputs.

These prompts accept `templateName`, the required root-level template folder
name, for example `ad_spend_allocation`.

Examples:

```text
/review-template templateName=ad_spend_allocation

/create-template-readme templateName=ad_spend_allocation

/update-template-readme templateName=ad_spend_allocation
```

> [!NOTE]
> `create-template-readme` may create or replace both `README.md` and
> `template-docs.yaml`. Run `review-template` afterwards to check the result.

## Local validation before opening a pull request

Before opening a PR, make sure you can complete this checklist from a clean environment.

1. Create a fresh virtual environment in the template folder.
1. Install the template locally.
1. Run the template end to end using the exact command documented in the README.
1. Lint template Python code from the repository root:

  ```bash
  ruff check */
  ```

1. Compile the changed runner and model package:

  ```bash
  python -m compileall -q <your_template_name> sample-template
  ```

1. Test the changed-template policy:

  ```bash
  python -m unittest tests/test_validate_changed_templates.py
  ```

1. On a committed branch, validate its changed templates against the base:

  ```bash
  python scripts/validate_changed_templates.py --base-ref origin/main
  ```

1. Run repository hooks:

  ```bash
  pre-commit run --all-files
  ```

1. If you changed template descriptions or added a template, regenerate the root index:

  ```bash
  python scripts/generate_template_index.py
  ```

1. Verify the generated index is clean:

  ```bash
  python scripts/generate_template_index.py --check
  ```

## Keep the template index in sync

The template index is generated from each root-level template README's front
matter — the `description`, `industry`, and `reasoning_types` fields. It is
written to the repository root `README.md`, between its
`<!-- BEGIN TEMPLATE INDEX -->` / `<!-- END TEMPLATE INDEX -->` markers.

If you add a template or change a template's `description`, `industry`, or `reasoning_types`, regenerate the indexes and commit the resulting README changes.

```bash
python scripts/generate_template_index.py
```

To validate without writing changes:

```bash
python scripts/generate_template_index.py --check
```

## Open a pull request

Open a PR once the template is runnable, the README is accurate, and local validation passes.

The lint workflow in `.github/workflows/lint.yml` runs Ruff, tests the
changed-template validator, and applies the new-template/adopted-sidecar policy on
pull requests.

The docs preview workflow in `.github/workflows/docs-preview.yml` runs on pull requests and posts a Vercel preview URL in the PR comments.

Use that preview to apply the authoritative sidecar schema and source extractor,
then confirm that the model explorer, walkthrough, sample tables, README
sections, download, and source links render correctly before merging.
