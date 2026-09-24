---
name: cleanup-template-code
description: Refactor a RelationalAI template into the standard model package without changing behavior.
inputs:
  version:
    description: Template version folder.
    default: v1
  templateName:
    description: Template folder name.
---

# Refactor template code

VERSION=${{input:version:v1}}
TEMPLATE_NAME=${{input:templateName}}

Read `.agents/skills/template-authoring/SKILL.md` completely and follow its
**Update** workflow for `${VERSION}/${TEMPLATE_NAME}/`.

Preserve the existing entrypoint, data semantics, reasoning, solver
configuration, constraints, thresholds, result ordering, output labels, and
dependencies. For a v1 migration:

- Move model creation and stable declarations to `model/schema.py`.
- Move reads, normalization, and base-fact mappings to `model/source.py`.
- Re-export stable symbols through `model/__init__.py`.
- Keep derived reasoning, solves, queries, and reporting in the runner.
- Update README, runbook, and any existing `template-docs.yaml` references.
- Do not force an existing README-only template to adopt the sidecar unless
  the request explicitly includes migration.

Run the focused validation selected by the skill. Return changed files,
behavior-preservation evidence, check results, and connected runtime blockers.
