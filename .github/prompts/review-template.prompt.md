---
name: review-template
description: Review a RelationalAI template folder for completeness and common issues (dependencies, sample data, README quality, and consistency).
argument-hint: version, templateName
---

# Template Review for RelationalAI Templates

## Configuration Options

VERSION=${{input:version:v0.13}}
TEMPLATE_NAME=${{input:templateName}}

## Role

You are an expert Python engineer and technical writer reviewing RelationalAI templates for correctness, reproducibility, and contributor quality.

You MUST NOT change any files. Your output is a review report only.

## Task

Review the entire contents of the template located at `${VERSION}/${TEMPLATE_NAME}/`.

If no `version` input is provided, default to `v0.13`.

Identify any issues that would prevent someone from successfully running the template from a fresh environment, especially:

- Unpinned or missing `relationalai` dependency
- Missing dependencies for imported modules
- Missing sample data files referenced by the script or README
- README sections that still contain placeholders or are inconsistent with the code
- Broken/incorrect commands in Quickstart
- Mismatch between folder name, script entrypoint name, and `pyproject.toml` metadata

## What to check

### 1) Required files and basic structure

- `README.md` exists.
- `pyproject.toml` exists.
- The main runner exists:
  - Prefer `${TEMPLATE_NAME}.py`.
  - If a different entrypoint is used, identify it and flag the mismatch.
- `data/` directory exists when the script reads sample files from `DATA_DIR`.

### 2) `pyproject.toml` correctness and reproducibility

Check that:

- `relationalai` is pinned with an exact version using `==` (for example `relationalai==0.13.3`).
  - Flag ranges like `>=`, `~=`, or unpinned `relationalai`.
- `requires-python` is present and reasonable for the repo (typically `>=3.10` for v0.13).
- The declared dependencies cover imports used by the runner.
  - Example: if the script imports `pandas`, ensure `pandas` is in dependencies.
  - If an import is optional or only used in a narrow path, call that out explicitly.
- `name` matches the folder (`rai-template-${TEMPLATE_NAME}` is the usual convention).
- If a `[build-system]` table is present, ensure it is minimal and consistent with other templates.

### 3) Sample data completeness

- Read the runner and list every file path under `DATA_DIR` (or other relative paths) that the script loads.
- Verify each referenced file exists under `data/`.
- Cross-check the README “What’s included” and “Sample data” sections list the same files.
- If the template is expected to include sample outputs (CSV export, etc.), verify the described paths match what the script actually writes.

### 4) README quality and consistency (based on `template-outline.md`)

Check that:

- Front matter fields are present and filled in (no `<PLACEHOLDER>` strings):
  - `title`, `description`, `experience_level`, `industry`, `reasoning_types`, `tags`
- “What this template is for” includes a sentence that explicitly names the reasoning type(s) in **bold** and matches `reasoning_types`.
- Quickstart is copy/paste friendly:
  - Step 1 should be the ZIP download/extract snippet used across templates.
  - Dependency install commands match `pyproject.toml` (for example, `python -m pip install .` in a venv).
  - The run command matches the actual entrypoint.
- “Template structure” tree matches what’s actually in the folder.
- Any mentioned files (`*.py`, CSVs, configs) exist and have correct names.

### 5) Runner script sanity checks

Without changing behavior, verify:

- The module docstring includes:
  - A one-line title ending with `template.`
  - A brief bullet list of what the script does
  - `Run:` block with the exact command
  - `Output:` block describing what is printed
- `DATA_DIR = Path(__file__).parent / "data"` (or an equivalent correct relative path) is present when data is loaded.
- For v0.13 templates using pandas CSV loading, ensure the pandas string inference option is set consistently when applicable.

## Deliverable (your response format)

Produce a review report with these sections:

1. **Summary**
   - One paragraph: whether the template is runnable as-is and the top 1–3 issues.

2. **Checklist**
   - A short checklist with PASS/FAIL for:
     - Required files
     - Dependencies pinned
     - Dependencies complete vs imports
     - Sample data present
     - README filled in (no placeholders)
     - Quickstart commands correct

3. **Issues and fixes**
   - For each issue:
     - Severity: `BLOCKER`, `WARN`, or `NICE-TO-HAVE`
     - File path(s)
     - What’s wrong
     - Exact suggested fix (show the minimal snippet to change)

Be specific and actionable. Prefer concrete file paths and exact strings over general guidance.
