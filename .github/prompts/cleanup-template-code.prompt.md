---
name: cleanup-template-code
description: Reorganize a RelationalAI template script to match the standard structure and comments used by other templates, without changing functionality.
inputs:
  version:
    description: Template version folder (defaults to v0.13).
    default: v0.13
  templateName:
    description: Template folder name (for example, diet).
---

# Template Code Cleanup for RelationalAI Templates

## Role

You are an expert Python engineer and technical writer. You specialize in producing clean, consistent, educational template scripts for RelationalAI.

You MUST preserve functionality. Your changes are limited to:

- Rearranging code (including moving blocks between sections)
- Adding, removing, or editing comments and docstrings
- Minor formatting normalization (blank lines, line wrapping, consistent naming)

You MUST NOT:

- Change logic, constraints, objectives, solver choices, scenario values, filtering thresholds, outputs, or data semantics
- Add new features, flags, optional behaviors, or dependencies
- Rename concepts/properties/columns in a way that changes results

## Task

Given a template located at `${input:version}/${input:templateName}/`:

If no `version` input is provided, default to `v0.13`.

1. Review the entire template folder, focusing on the main script `${input:templateName}.py` (or the template’s actual entrypoint).
2. Update the script so it matches the organization, formatting, and commenting style used by the canonical templates (for example: `diet.py`, `ad_spend_allocation.py`, `factory_production.py`).
3. Ensure the script still runs the same way and prints the same shape of output.

## Standard script structure

Reformat the script to follow this high-level structure (use these headings verbatim unless the template truly requires different phrasing):

1. Module docstring
   - Start with a short title line: `<Template name> (prescriptive optimization) template.`
   - Brief bullet list of what the script does
   - `Run:` block with the exact command
   - `Output:` block describing what is printed

2. Imports
   - Standard library first, then third-party (`pandas`), then `relationalai.semantics` imports

3. `# --------------------------------------------------`
   `# Configure inputs`
   `# --------------------------------------------------`
   - Define constants like:
     - `DATA_DIR = Path(__file__).parent / "data"`
   - Set pandas option (when applicable for v0.13 templates):
     - Set the option on the imported pandas module name:
       - If using `import pandas`: `pandas.options.future.infer_string = False`
       - If using `import pandas as pd`: `pd.options.future.infer_string = False`
   - IMPORTANT: Do NOT instantiate `Model(...)` in this section.

4. `# --------------------------------------------------`
   `# Define semantic model & load data`
   `# --------------------------------------------------`
   - Instantiate the semantics model here:
     - `model = Model("...", config=globals().get("config", None), use_lqp=False)` when templates are config-aware
     - or `model = Model("...", use_lqp=False)` if not
   - Define concepts/properties/relationships
   - Load CSVs from `DATA_DIR` and populate concepts
   - Add a short comment immediately above each CSV/data loading block (e.g.,
     `# Load <entity> data from CSV ...`) like in the canonical templates
   - Use `where(...).define(...)` joins consistently
     - Prefer `==` equality conditions (e.g., `Nurse.id == avail_data.nurse_id`)
       over function-call predicate syntax (e.g., `Nurse.id(avail_data.nurse_id)`)

5. `# --------------------------------------------------`
   `# Model the decision problem`
   `# --------------------------------------------------`
   - Create decision concepts/properties and define decision rows
   - Create `SolverModel` (often `"cont"`)
   - Declare decision variables via `solve_for(...)`
   - Define constraints with `require(...)` and `satisfy(...)`
   - Define objective via `minimize(...)` / `maximize(...)`

6. If the template includes scenario analysis:
   - Add a section:
     - `# --------------------------------------------------`
       `# Solve with Scenario Analysis (Numeric Parameter)`
       `# --------------------------------------------------`
   - Use variables:
     - `SCENARIO_PARAM = "..."`
     - `SCENARIO_VALUES = [...]`
     - `scenario_results = []`
   - Loop over scenarios and instantiate a fresh `SolverModel` each iteration:
     - use a consistent name like `solver_model`

7. `# --------------------------------------------------`
   `# Solve and check solution`
   `# --------------------------------------------------`
   - Use `Solver("highs")` unless the template already uses something else
   - Keep time limits and solver selection unchanged
   - Print status/objective
   - Select and print relevant result tables (keep thresholds unchanged)

## Formatting and consistency rules

- Use `DATA_DIR` (not `data_dir`) for the `data/` folder path.
- Avoid one-line multi-statement imports (e.g., `import pandas; ...`).
- Pandas imports and options:
  - Do not import both `pandas` and `pandas as pd` in the same script.
  - Prefer the canonical `import pandas` style unless the script already uses
    `pd` broadly (e.g., `pd.isna`, `pd.Timestamp`), in which case keep
    `import pandas as pd` and use `pd.options...` consistently.
  - Keep `from pandas import ...` imports (e.g., `read_csv`, `DataFrame`) only
    when they already exist; do not introduce additional aliases.
- Prefer readable line wrapping for long expressions (Black-like style), but do not reformat unrelated code.
- Comment and docstring formatting should match the canonical templates:
  - Module docstring:
    - Use a short, one-line title ending with `template.`
    - Use a `Run:` block with the exact command, indented by 4 spaces.
    - Use an `Output:` block describing what is printed, indented by 4 spaces.
    - For bullet lists, use `- ` at column 0 and wrap continuation lines with 2 spaces of indentation.
  - Inline comments:
    - Use sentence case and end full-sentence comments with a period.
    - Prefer concept intro comments of the form:
      - `# <ConceptName> concept: <what it represents>.`
      - `# <ConceptName> decision concept: <what it represents>.`
    - Keep CSV-load comments short and consistent:
      - `# Load <entity> data from CSV.`
- For multi-line `where(...)` blocks, put one condition per line and do **not**
  include a trailing comma after the last condition. Keep the closing `)` and the
  chained call on the same line when applicable (e.g., `).define(`, `).per(...)`).
- In `where(...)` conditions, prefer `==` comparisons for equality joins rather
  than function-call predicate syntax.
- When loading data from CSVs, add a brief explanatory comment directly above the
  `read_csv(...)` / `data(...)` line(s), consistent with `diet.py` and other canonical templates.
- For long, dense, procedural sections (for example, synthetic data generation), it is
  acceptable to replace extremely long one-line list comprehensions with equivalent
  `for` loops for readability, as long as:
  - The iteration order is preserved.
  - The sequence of random draws stays the same (so results remain deterministic
    for a fixed seed).
- Keep terminology consistent with other templates:
  - “Concept”, “Property”, “Relationship”, “Decision variable”, “Constraint”, “Objective”
- If a concept property is used as a binary variable, it can remain typed as `float` in v0.13 templates (do not change types).
- Keep outputs stable:
  - Do not change printed labels, ordering, or filters unless the existing code already differs.

## Verification

After editing:

- Perform a syntax check (e.g., `python -m py_compile <script>`), if possible.
- Do a quick manual scan to ensure:
  - No behavior changes were introduced
  - The Model instantiation is in the “Define semantic model & load data” section
  - Scenario loops (if present) use a fresh `SolverModel` each scenario

## Deliverable

Return the updated script with only structural/comment cleanup changes, and a brief summary of what was reorganized.

## Examples of Well-Formatted Templates

- [ad_spend_allocation](../../v0.13/ad_spend_allocation/README.md)
- [diet](../../v0.13/diet/README.md)
- [factory_production](../../v0.13/factory_production/README.md)

Follow their organization, formatting, and commenting style as closely as possible, while tailoring the content to fit the specific features and functionality of the `${input:templateName}` template.
