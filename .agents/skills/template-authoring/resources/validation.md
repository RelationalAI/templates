# Focused validation

Run the smallest checks that cover the changed template and repository policy.
From the repository root:

```bash
ruff check <template-path> sample-template scripts tests
python -m compileall -q <template-path> sample-template
python -m unittest tests/test_validate_changed_templates.py
python scripts/generate_version_indexes.py --check
```

For a committed branch, run the pull-request policy against its base:

```bash
python scripts/validate_changed_templates.py --base-ref origin/main
```

The changed-template check:

- Requires `template-docs.yaml` when a `v1/<slug>/README.md` is newly added or
  moved into a new template directory.
- Allows changes to existing README-only templates without forcing migration.
- Rejects removing an adopted sidecar while that template's README remains.

For any new or changed sidecar, use the docs preview workflow as the
authoritative strict-schema, source-symbol, anchor, CSV, and public-guide-link
validation.

Finally, run the exact README command in a fresh environment. If it needs
customer credentials, a RelationalAI engine, Snowflake, or another unavailable
connected resource, report the command as unverified. Linting and compilation
are not runtime proof.
