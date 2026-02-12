---
title: "Hello World"
description: "A minimal template that prints hello world."
featured: false
experience_level: beginner
industry: "General"
tags:
  - Demo
  - Basics
---

## What this template is for

A tiny starter template to verify your environment and show the basic layout of a RelationalAI template.

## Who this is for

- Anyone who wants a minimal “it runs” example.

## What you’ll build

- A single Python script that prints `hello world`.

## Prerequisites

### Tools

- Python >= 3.10

## Quickstart

1. Download the ZIP file for this template and extract it:

   ```bash
   curl -O https://private.relational.ai/templates/zips/v0.13/hello_world.zip
   unzip hello_world.zip
   cd hello_world
   ```

2. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install -U pip
   ```

3. Install dependencies:

   ```bash
   python -m pip install .
   ```

4. Run the template:

   ```bash
   python hello_world.py
   ```

5. Expected output:

   ```text
   hello world
   ```

## Template structure

```text
.
├─ README.md
├─ pyproject.toml
└─ hello_world.py
```

**Start here**: `python hello_world.py`
