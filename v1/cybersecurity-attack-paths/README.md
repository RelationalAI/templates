---
title: "Cybersecurity Attack Paths"
description: "Trace multi-step cyber attack chains across an enterprise asset graph by composing attacker techniques in order, then rank the routes that reach crown-jewel systems by their total exposure."
experience_level: intermediate
industry: "Technology & Telecom"
featured: false
reasoning_types:
  - Graph
tags:
  - graph-analytics
  - paths
  - multi-edge
  - attack-paths
  - lateral-movement
  - cybersecurity
sidebar:
  order: 7
---

## What this template is for

Attackers rarely reach a crown-jewel system in one move. They chain techniques: exploit an internet-facing host to get a foothold, reuse harvested credentials to move inward, then pivot laterally across the network until they reach a domain controller or a customer database. Security teams need to see those end-to-end chains, not just a list of individual vulnerabilities, so they can cut the routes that actually matter.

This template enumerates multi-step attack paths across an enterprise asset graph and ranks the ones that reach a crown jewel. **It uses graph path enumeration with multi-edge patterns: a single path can compose distinct relationships in a fixed order, so the analysis follows the real kill-chain sequence (exploit, then credential reuse, then lateral movement) rather than treating every move as interchangeable.**

## Who this is for

- **Security analysts and threat modelers** who want to reason about attack paths, not just isolated findings
- **Detection and remediation teams** prioritizing which assets to harden first
- **Assumed knowledge**: comfortable reading Python; graph and path terms (nodes, edges, path enumeration) are explained inline, so no prior RelationalAI experience is required to follow along

## What you'll build

- An enterprise asset graph (perimeter hosts, internal services and workstations, restricted crown jewels) with three distinct attacker techniques — vulnerability exploitation, credential reuse, and network pivoting — modeled as separate directed edges between assets
- An enumerated set of kill-chain attack paths, produced by RelationalAI multi-relationship path enumeration (a multi-edge pattern that fixes the technique order)
- A point-query result listing every route between one named entry point and one named crown jewel over the technique-agnostic union edge
- A ranking of the kill-chains by the asset exposure summed along each one
- An `Asset.on_attack_path` flag persisted back onto the ontology, marking every asset that lies on a crown-jewel-reaching chain

## What's included

- **Self-contained script**: `cybersecurity_attack_paths.py` runs the full analysis end-to-end
- **Runbook**: `runbook.md` — a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the script itself.
- **Data**: `data/assets.csv` (12 assets) and `data/attack_steps.csv` (16 technique-tagged edges)

## Prerequisites

### Access

- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools

- Python >= 3.10.
- `relationalai` SDK >= 1.15 (path enumeration with multi-edge patterns is a preview capability) and the `rai` CLI, both installed by the Quickstart steps below.
- OS notes: works on macOS, Linux, and Windows; the Quickstart's virtual-environment activation command assumes macOS or Linux.

## Quickstart

1. Download and extract this template:

   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/cybersecurity-attack-paths.zip
   unzip cybersecurity-attack-paths.zip
   cd cybersecurity-attack-paths
   ```

   > [!TIP]
   > You can also download the template ZIP using the "Download ZIP" button at the top of this page.

2. **Create and activate a virtual environment**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install -U pip
   ```

3. **Install dependencies**

   ```bash
   python -m pip install .
   ```

4. **Configure Snowflake connection and RAI profile**

   ```bash
   rai init
   ```

5. **Run the template**

   ```bash
   python cybersecurity_attack_paths.py
   ```

   Expected output starts with the kill-chains that reach a crown jewel:

   ```text
   3 kill-chain attack path(s) reach a crown jewel (exploit -> cred -> 1-2 pivots, from an internet-facing asset):
     [3 hops] VPN Gateway  --[exploit]-->  Jump Host  --[cred]-->  File Server  --[pivot]-->  Customer Database
   ```

   See the runbook for the full output.

## Template structure

```text
cybersecurity-attack-paths/
├── cybersecurity_attack_paths.py
├── pyproject.toml
├── README.md
├── runbook.md
└── data/
    ├── assets.csv
    └── attack_steps.csv
```

**Start here**: run `python cybersecurity_attack_paths.py` for the full analysis end to end, or follow `runbook.md` to rebuild it step by step.

## Sample data

`data/assets.csv` holds 12 assets that make up a small enterprise estate, spanning a perimeter (`dmz`), an `internal` zone of services and workstations, and a `restricted` zone of high-value systems. Each row carries `id`, `name`, `zone`, an `internet_facing` flag (`yes`/`no`), a `crown_jewel` flag (`yes`/`no`), and an `exposure_score` (an integer stand-in for a CVSS or attack-surface metric). Two assets are crown jewels (the Domain Controller and the Customer Database); three sit internet-facing on the perimeter.

`data/attack_steps.csv` holds 16 directed attack steps, one per row, with `src`, `dst`, and a `technique` tag. The technique splits the steps into the three attacker moves the kill-chain composes in order: `exploit` (vulnerability exploitation), `cred` (credential reuse), and `pivot` (network lateral movement). Each step reads as "an attacker on `src` can reach `dst` by this technique".

## Model overview

- **Key entities**: `Asset` — one host, service, or account in the enterprise estate.
- **Primary identifiers**: `Asset` by `id`.
- **Important invariants**: the three technique edges are directed (`src` reaches `dst`, not the reverse); `internet_facing` and `crown_jewel` are `yes`/`no` flags that pin the kill-chain endpoints; `on_attack_path` is set only on assets that lie on a crown-jewel-reaching chain.

For the full concept and property definitions — including the four directed self-relationships (`exploit_to`, `cred_to`, `pivot_to`, and the technique-agnostic `can_reach` union edge) — see `cybersecurity_attack_paths.py`; `runbook.md` builds them step by step with the RAI skills.

## How it works

```text
CSV files --> Define Asset + technique edges --> Kill-chain enumeration (multi-edge)
          --> Point query (entry to crown jewel) --> Exposure ranking --> Persist Asset.on_attack_path
```

The analysis starts by modeling each attacker technique as its own directed relationship between assets — `exploit_to`, `cred_to`, `pivot_to` — plus a technique-agnostic `can_reach` union edge that the point query uses.

The centerpiece is a multi-edge path pattern (which needs `relationalai>=1.15`) that composes the techniques in series: an exploit first, then credential reuse, then one or more lateral pivots, ending at an explicit destination. Filtering the source to an internet-facing asset and the destination to a crown jewel pins the threat model. Enforcing edge order is the whole point — a single union edge or a flat join cannot express "exploit first, then credentials, then pivots," which is exactly the kill-chain signature analysts care about, and each hop records the technique it used.

A separate point query pins both endpoints by id to enumerate every route between a chosen entry point and a chosen crown jewel over the union edge. The kill-chains are then ranked by the exposure summed along each one. Finally, the assets lying on any crown-jewel chain are flagged back onto the ontology as `Asset.on_attack_path`, so a later query can pull them without re-enumerating paths.

See `cybersecurity_attack_paths.py` for the implementation and `runbook.md` to reproduce it step by step with the RAI skills.

## Customize this template

### Use your own data

- Replace the CSVs in `data/` with your own assets and attack steps, keeping the same column names. Tag each step with the technique an attacker would use (`exploit`, `cred`, `pivot`, or your own taxonomy).
- Mark internet-facing assets and crown jewels with `yes` or `no` so the kill-chain endpoints match your environment.
- Feed `Asset.exposure_score` from a real vulnerability or attack-surface feed so the ranking reflects live risk.

### Tune parameters

- Raise `MAX_PIVOTS` or `MAX_ROUTE_HOPS` for larger estates with deeper lateral movement (these bound the kill-chain pivot repeat and the point-query hop count).
- Adjust how `Asset.exposure_score` is weighted in the ranking so the chains that surface first match your prioritization (raw sum, per-hop average, or a max along the path).

### Extend the model

- Add more techniques (for example `phish` or `escalate`) as additional edges and lengthen the multi-edge pattern.

### Scale up / productionize

- Size the RAI engine to the estate: path enumeration grows with the number of assets and edges, so larger graphs want a larger engine.
- Schedule the run (cron, Airflow, or your orchestrator of choice) to re-enumerate paths as the asset and attack-step feeds refresh.
- Pin `relationalai` to a known-good version in `pyproject.toml` for reproducible runs across environments.

## Troubleshooting

<details>
  <summary>Why do I see <code>relationalai</code> version or path import errors?</summary>

- Path enumeration with multi-edge patterns requires `relationalai` 1.15 or newer. Confirm your installed version with `python -m pip show relationalai`.

</details>

<details>
  <summary>Why does authentication or configuration fail?</summary>

- Run `rai init` to create or update `raiconfig.yaml`.
- If you have multiple profiles, set `RAI_PROFILE` or switch profiles in your config.

</details>

## Learn more

- [RelationalAI documentation](https://docs.relational.ai/) — language, modeling, and reasoner reference.
- [Template gallery](https://docs.relational.ai/build/templates) — other runnable templates, including graph, rules, and prescriptive examples.

## Support

- Questions or issues: [support.relational.ai](https://support.relational.ai).
