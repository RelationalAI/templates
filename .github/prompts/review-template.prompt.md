---
name: review-template
description: Review a RelationalAI template for reproducibility, model boundaries, and documentation integrity.
argument-hint: version, templateName
inputs:
  version:
    description: Template version folder.
    default: v1
  templateName:
    description: Template folder name.
---

# Review a template

VERSION=${{input:version:v1}}
TEMPLATE_NAME=${{input:templateName}}

Read `.agents/skills/template-authoring/SKILL.md` completely and follow its
**Review** workflow for `${VERSION}/${TEMPLATE_NAME}/`. Do not edit files.

Check:

- Required files, entrypoint, pinned dependencies, and complete sample data.
- README commands, paths, headings, expected output, and troubleshooting.
- `model/schema.py`, `model/source.py`, `model/__init__.py`, and runner
  responsibility boundaries when the template uses the v1 layout.
- `runbook.md` consistency with the final code paths.
- Every existing `template-docs.yaml` key, symbol, source, reference, anchor,
  sample column, and public guide route.
- New-v1-template sidecar policy without treating legacy README-only templates
  as failures.
- Lint, compilation, generated-index, changed-template, docs-preview, and
  connected runtime evidence.

Return a concise summary, a PASS/FAIL checklist, and ordered issues. For every
issue, include severity, exact path, evidence, and the smallest correct fix.
Do not treat linting or compilation as proof that a connected template ran.
