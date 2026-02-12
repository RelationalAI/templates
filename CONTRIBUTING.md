# Contributing

This repo contains versioned, runnable RelationalAI templates (for example under `v0.13/`).

## Contribute a new template

1. Start from the sample template

- Copy `sample-template/` into the version folder you’re targeting, and rename it to your template name.
- Example:

  ```bash
  cp -R sample-template v0.13/<your_template_name>
  ```

1. Implement your template

- Update the runner script, sample data, and `pyproject.toml` as needed.
- Update `README.md` by replacing placeholders (front matter + sections) and ensuring the Quickstart run command matches your entrypoint.

  > [!TIP]
  > Use the `create-template-readme` prompt in Copilot Chat to automatically generate a README draft based on your code, then review and edit it for accuracy and style.
  > You can also use the `update-template-readme` prompt after making changes to your code to keep the README in sync.

## Use VS Code prompts to help development

This repo includes prompt files under `.github/prompts/` that you can run from VS Code to speed up documentation and reviews.

Useful prompts:

- `create-template-readme` — generate a README from the template code.
- `update-template-readme` — update an existing README after code changes.
- `review-template` — review a template folder for common issues (pinned dependencies, missing data files, README placeholders, etc.).

### How to run a prompt in Copilot Chat

In VS Code, open **Copilot Chat**, then run one of the repo prompts from `.github/prompts/` and provide its inputs.

These prompts all accept the same inputs:

- `templateName` (required): the template folder name (for example, `ad_spend_allocation`).
- `version` (optional): the version folder (defaults to `v0.13`).

Examples you can paste into Copilot Chat (adjust values as needed):

```text
/review-template templateName=ad_spend_allocation/

/create-template-readme templateName=ad_spend_allocation/

/update-template-readme templateName=ad_spend_allocation
```

> [!NOTE]
> `create-template-readme` overwrites `${version}/${templateName}/README.md`. Run `review-template` afterwards to sanity-check the result.

## Preview your template on the docs site

Open a pull request with your changes. The **Docs preview** GitHub Action (`.github/workflows/docs-preview.yml`) runs on PRs and will post (or update) a comment on the PR with a Vercel preview URL.

Use that preview to confirm your template renders correctly on the website before merging.
