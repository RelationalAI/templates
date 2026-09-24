# `template-docs.yaml` contract

The sidecar is inert data consumed by the documentation build. It must contain
no HTML, MDX, imports, exports, expressions, JavaScript, or executable code.
Unknown keys are errors.

## Top-level shape

```yaml
version: 1

page:
  lead_from_readme: []
  omit_from_readme: []

model_explorer:
  title: Plain-text title
  description: Plain-text description
  concepts: []
  relationships: []
  sources: []

guided_walkthrough:
  title: Plain-text title
  description: Plain-text description
  steps: []

sample_data:
  default_rows: 4
  tables: []
```

`sample_data` is optional. Every other top-level key is required.

## Page composition

- `lead_from_readme`: zero or more unique lowercase README heading IDs.
- `omit_from_readme`: zero or more unique lowercase README heading IDs.
- A heading ID cannot appear in both lists.
- Both lists must reference headings still present in the README. Use
  `omit_from_readme: []` when a shorter README removes those sections.
- Use the IDs produced by GitHub-style heading slugs, such as
  `what-this-template-is-for` and `what-youll-build`.
- `download_and_run_from_readme: true` (optional) extracts the README Quickstart
  into a generated "Download and run the template" section. State access and
  Python requirements before the first step, include any required SQL setup
  there, then provide five ordered steps: download, Python environment,
  install, configure with the Start building with PyRel configuration builder,
  and run. Keep any representative output directly after its runner command.
  Templates without this flag retain their existing rendering.
- `omit_readme_preamble: true` (optional) excludes the text before the first
  README `##` heading from the enhanced HTML and Markdown pages. Use it when
  the README opens with links to its own generated model explorer and
  walkthrough. Without the flag, existing preamble text remains visible.

## Model explorer

`concepts` contains 1-50 entries:

```yaml
- symbol: Account
  description: A customer account evaluated by the model.
```

The symbol must be a top-level concept declared in `model/schema.py`. Identity
keys and properties are extracted from Python and must not be repeated.

`relationships` contains up to 100 entries:

```yaml
- symbol: Transaction.sender
  label: sent by
  reading: Transaction is sent by Account
  description: Connects each transfer to its sending account.
```

The relationship symbol must resolve in `model/schema.py`. Endpoints are
extracted; the sidecar supplies the reader-facing label, reading, and
description.

`sources` contains up to 50 entries:

```yaml
- path: data/accounts.csv
  description: Account identifiers and attributes.
```

Use repository-relative paths. The extractor infers mappings from
`model/source.py`. Add `populates` only when dynamic code makes the mapping
ambiguous:

```yaml
  populates:
    - Account
    - Transaction.sender
```

Every override must name a concept or relationship selected by
`model_explorer`.

## Guided walkthrough

Provide 1-6 semantic steps. One or two steps may be present while a walkthrough
is under editorial review; a complete walkthrough should normally have 3-6
steps. Each step has one canonical Python file, one focus form, and 1-2 public
guide links:

```yaml
- id: load-inputs
  title: Load account records
  explanation: >-
    load_accounts maps account rows into the shared Account concept.
  focus:
    file: model/source.py
    symbols:
      - load_accounts
  references:
    load_accounts:
      symbol: load_accounts
    Account:
      symbol: Account
  links:
    - title: Define base facts
      href: /build/guides/modeling/define-base-facts/
```

- Prefer `focus.symbols`; use 1-25 unique Python symbols.
- Use `focus.anchors` only for a meaningful span without a stable symbol:

  ```yaml
  focus:
    file: runner.py
    anchors:
      - start: "# Stage 3: Optimize"
        end: "# Stage 4: Report"
  ```

- Anchor text must occur exactly once, in order, in the selected file.
- Reference keys must appear verbatim in the explanation.
- Reference values contain only `symbol`.
- IDs use lowercase words separated by hyphens.
- Update the sidecar whenever a referenced path, symbol, or anchor changes.

## Sample data

Select only local CSV files and representative columns:

```yaml
sample_data:
  default_rows: 4
  tables:
    - path: data/accounts.csv
      title: Accounts
      description: Representative account records.
      columns:
        - id
        - status
      rows: 3
```

- `default_rows` and per-table `rows` must be integers from 1 through 10.
- A table needs at least one unique column and may select at most 50.
- The docs build reads headers, counts all rows, and emits only the bounded
  sample. Do not copy data rows into YAML.
- Order tables by the reader's workflow rather than alphabetically.

Use `sample-template/template-docs.yaml` as the copyable minimal example.
