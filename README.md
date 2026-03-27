# RelationalAI Templates

This repository contains runnable RelationalAI templates that demonstrate end-to-end solution patterns across optimization, graph analytics, fraud detection, supply chain planning, and other decision intelligence workflows.

Each template lives in its own folder with code, sample data, and a template-specific README. Templates are grouped into versioned directories so the repository can support multiple generations of examples side by side.

## Repository layout

| Path | Purpose |
| --- | --- |
| [`sample-template/`](sample-template/) | Starting point for authoring a new template. Includes the expected file layout and README template. |
| [`v0.13/`](v0.13/) | Older templates for version `0.13` of the `relationalai` Python package. Included for reference, only. |
| [`v0.14/`](v0.14/) | Older templates for version `0.14` of the `relationalai` Python package. Included for reference, only. |
| [`v1/`](v1/) | Newer templates for versions `>=1.0` of the `relationalai` Python package. **Use these for new development.** |

Within a template folder, you will usually find:

- `README.md` with the problem statement, prerequisites, and run instructions
- `pyproject.toml` for template-local dependencies
- a main runner such as `<template>.py` or a notebook
- `data/` containing sample input data when the template uses local files

## Choose a template

Use the version folder and template README to pick the example that matches your goal.

- If you want a minimal onboarding example, start with [`v1/simple-start/`](v1/simple-start/).
- If you want to create a new template, start from [`sample-template/`](sample-template/).

For a full list of templates and their descriptions, check out the [`v1/README.md`](v1/README.md) file.

## Getting started with a template

The exact setup is documented in each template's README, but the workflow is consistent:

1. Pick a template folder.
2. Create a virtual environment inside that folder.
3. Install the template's dependencies.
4. Configure RelationalAI access if the template connects to a live environment.
5. Run the script or notebook described in the template README.

Example workflow:

```bash
cd v1/simple-start
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install .
```

After installation, continue with the template-specific instructions in that folder's README.

## What a template includes

Most templates are designed to be runnable and inspectable without additional repository-level setup.

- **Code**: a small, focused implementation of the use case
- **Sample data**: enough data to exercise the model end to end
- **Documentation**: problem framing, prerequisites, quickstart, and customization notes
- **Metadata**: template metadata used by the [RelationalAI Docs](https://docs.relational.ai/) site to surface the template in the [template gallery](https://docs.relational.ai/templates).

## Contributing

To add or update a template:

1. Copy [`sample-template/`](sample-template/) into the version folder you are targeting.
2. Implement the model, runner, sample data, and metadata.
3. Replace the README placeholders with template-specific content.
4. Review the result before opening a pull request.

Repository-level linting for template Python code uses Ruff:

```bash
ruff check path/to/my/template
```

The same check runs in CI via `.github/workflows/lint.yml`.

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the full contribution workflow.
