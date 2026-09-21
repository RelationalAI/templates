---
name: create-template-readme
description: Create the README and generated-docs sidecar for a RelationalAI template.
tools: ['edit/createFile', 'edit/editFiles', 'read/readFile']
inputs:
  version:
    description: Template version folder.
    default: v1
  templateName:
    description: Template folder name.
---

# Create template documentation

VERSION=${{input:version:v1}}
TEMPLATE_NAME=${{input:templateName}}

Read `.agents/skills/template-authoring/SKILL.md` completely and follow its
**Create** workflow for `${VERSION}/${TEMPLATE_NAME}/`.

Read the entire template before writing. Create an accurate GitHub README and,
for a new v1 template, a strict `template-docs.yaml` in the same change.

- Keep the README complete and runnable from a fresh environment.
- Begin with the business problem and outcome.
- Keep the solution stages in **What you'll build**.
- Name the model schema, source mapping, runner, runbook, sample data, and
  outputs in **What's included**.
- Do not add a standalone **Template structure** section.
- Use compact Markdown tables for representative sample rows.
- Keep **Model overview** and **How it works** concise for GitHub readers.
- Use the exact entrypoint, install commands, expected output, and data paths.
- Add three to five semantic sidecar walkthrough steps with stable symbols
  whenever possible.
- Use only guide routes in the skill's public catalog.

Never invent behavior, output, credentials, limits, or source columns. Run the
skill's focused checks and report any connected runtime verification blocker.
