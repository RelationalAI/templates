# Contributing

This repository contains versioned, runnable RelationalAI templates. Each template is a small, self-contained example with code, sample data, and documentation.

This guide covers the expected workflow for adding a new template or updating an existing one.

## Choose the right version folder

- Put new templates in `v1/` unless you are intentionally contributing to an older SDK generation.
- Treat `v0.13/` and `v0.14/` as legacy branches for maintenance, fixes, and backports.
- Keep the version folder aligned with the `relationalai` package version pinned in the template's `pyproject.toml`.

Examples:

```bash
cp -R sample-template v1/<your_template_name>
```

```bash
cp -R sample-template v0.13/<your_template_name>
```

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
  ruff check sample-template v0.13 v0.14 v1
  ```

- Pre-commit hook (configured in `.pre-commit-config.yaml`):

  ```bash
  pre-commit run ruff-check --all-files
  ```

- CI workflow: `.github/workflows/lint.yml` runs the same Ruff check on pull requests and on pushes to `main`.

## Add a new template

1. Copy `sample-template/` into the target version folder and rename it to your template name.
2. Rename the main runner, package metadata, and any placeholder identifiers so they match the folder name.
3. Implement the template code, sample data, and outputs.
4. Replace the README placeholders with template-specific content.
5. Run the template from a fresh environment and verify that the README Quickstart works as written.

The sample template is the source of truth for the expected file layout and README structure.

At a minimum, make sure your template includes:

- `README.md` with complete front matter and no placeholder text
- `pyproject.toml` with a pinned `relationalai` dependency
- a runnable entrypoint such as `<template_name>.py` or a notebook
- `data/` when the template reads local sample files
- sample data and output paths that match both the code and the README

## Update an existing template

When changing an existing template:

- keep the README, code, and sample data in sync
- keep dependency changes minimal and explicit
- verify that any renamed files, commands, or outputs are reflected in the README
- rerun any local validation steps that the change affects

### Prescriptive templates: bumping the `relationalai` pin past 1.28

`Problem.display()` changes in 1.29. If your template calls it, check these when you bump the pin:

- `display()` no longer accepts `part` or `where`; both raise `TypeError`. Select the `Expression.display_string` property instead and filter it with an ordinary `where`.
- `display(limit=n)` still works, but only for the whole problem — it caps each printed table at its first `n` rows and can no longer be scoped to a part. `n` must be a positive integer.
- `display_string` is declared whether or not its rules are installed, so a select that skips `install_display_strings()` returns nulls with no error saying why. Call `problem.install_display_strings()` once, after the model is fully declared, and before deploying under Deploy Mode. `display()` installs the rules itself; a direct select does not.
- `display()` raises `ValueError` if any decision variable is unnamed, so pass `name=` to every `solve_for(...)`.
- The client-side depth cap is gone. A deeply nested expression no longer prints `<expression too deep>`; it renders on the engine instead. Render time climbs steeply with nesting depth, so a template that builds very deep expressions will spend real time on the first query after an install.

```python
from relationalai.semantics.std import aggregates as aggs

problem.install_display_strings()  # once, after the last define/require
c = problem.Constraint

model.select(c.name, c.display_string).inspect()                             # whole problem
model.select(c.name, c.display_string).where(c.name == "cap_3").inspect()    # in place of where=
model.where(aggs.limit(10, c.name)).select(c.name, c.display_string).inspect()  # in place of a scoped limit=
```

## README expectations

An authentic template contribution is mostly about reproducibility. The README should let someone unfamiliar with the template run it successfully from scratch.

Reviewers will expect the README to:

- explain what the template is for and who it is for
- include complete front matter metadata
- provide a copy/paste-friendly Quickstart
- use the correct entrypoint and install commands
- describe the sample data and outputs accurately
- match the current top-level file structure

> [!TIP]
> Use the `create-template-readme` prompt in Copilot Chat to draft a README from the template code, then edit it for accuracy and style.
> After code changes, use `update-template-readme` to refresh the README and review the result manually.

## Use VS Code prompts to help development

This repo includes prompt files under `.github/prompts/` that you can run from VS Code to speed up documentation and reviews.

Useful prompts:

- `create-template-readme` - generate a README from the template code
- `update-template-readme` - update an existing README after code changes
- `review-template` - review a template folder for common issues such as pinned dependencies, missing data files, and README drift

### How to run a prompt in Copilot Chat

In VS Code, open Copilot Chat, then run one of the repo prompts from `.github/prompts/` and provide its inputs.

These prompts accept the same inputs:

- `templateName` (required): the template folder name, for example `ad_spend_allocation`
- `version` (optional): the version folder; for new templates, prefer `v1`

Examples:

```text
/review-template templateName=ad_spend_allocation version=v1

/create-template-readme templateName=ad_spend_allocation version=v1

/update-template-readme templateName=ad_spend_allocation version=v1
```

> [!NOTE]
> `create-template-readme` overwrites `${version}/${templateName}/README.md`. Run `review-template` afterwards to sanity-check the result.

## Local validation before opening a pull request

Before opening a PR, make sure you can complete this checklist from a clean environment.

1. Create a fresh virtual environment in the template folder.
1. Install the template locally.
1. Run the template end to end using the exact command documented in the README.
1. Lint template Python code from the repository root:

  ```bash
  ruff check sample-template v0.13 v0.14 v1
  ```

1. Run repository hooks:

  ```bash
  pre-commit run --all-files
  ```

1. If you changed template descriptions or added a template, regenerate the version indexes:

  ```bash
  python scripts/generate_version_indexes.py
  ```

1. Verify the generated indexes are clean:

  ```bash
  python scripts/generate_version_indexes.py --check
  ```

## Keep template indexes in sync

The template index is generated from each template README's front matter — the `description`, `industry`, and `reasoning_types` fields. It is written to each version README (`v0.13/README.md`, `v0.14/README.md`, `v1/README.md`) and to the repository root `README.md`, between its `<!-- BEGIN TEMPLATE INDEX -->` / `<!-- END TEMPLATE INDEX -->` markers.

If you add a template or change a template's `description`, `industry`, or `reasoning_types`, regenerate the indexes and commit the resulting README changes.

```bash
python scripts/generate_version_indexes.py
```

To validate without writing changes:

```bash
python scripts/generate_version_indexes.py --check
```

## Open a pull request

Open a PR once the template is runnable, the README is accurate, and local validation passes.

The lint workflow in `.github/workflows/lint.yml` runs on pull requests that touch template code or lint configuration and will fail the PR if Ruff checks fail.

The docs preview workflow in `.github/workflows/docs-preview.yml` runs on pull requests and posts a Vercel preview URL in the PR comments.

Use that preview to confirm that your template renders correctly on the docs site before merging.
