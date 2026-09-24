---
name: update-template-readme
description: Keep a template README, runbook, and generated-docs sidecar aligned with its code.
tools: ['edit/createFile', 'edit/editFiles', 'read/readFile']
inputs:
  version:
    description: Template version folder.
    default: v1
  templateName:
    description: Template folder name.
---

# Update template documentation

VERSION=${{input:version:v1}}
TEMPLATE_NAME=${{input:templateName}}

Read `.agents/skills/template-authoring/SKILL.md` completely and follow its
**Update** workflow for `${VERSION}/${TEMPLATE_NAME}/`.

Compare the current code, data files, `pyproject.toml`, README, runbook, and
sidecar. Make only the changes needed to restore accuracy.

- Preserve valid README content and the existing copy/paste Quickstart.
- Update commands, paths, symbols, sample columns, expected output, and
  troubleshooting affected by the code change.
- Keep **What you'll build** focused on the solution flow if the README has it;
  do not reintroduce removed sections in a short enhanced README.
- Do not add a standalone **Template structure** section.
- If `template-docs.yaml` exists, update every affected model symbol, source,
  walkthrough focus, reference, anchor, and sample table.
- Do not remove an adopted sidecar.
- Do not force an existing README-only template to migrate unless requested.

Run the focused checks selected by the skill and distinguish static validation
from connected runtime verification.
