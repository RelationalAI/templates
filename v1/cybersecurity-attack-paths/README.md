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

- Load a 12-asset enterprise estate (perimeter hosts, internal services and workstations, restricted crown jewels) and 16 directed attack steps from CSV
- Model three distinct attacker techniques as separate edges between assets: vulnerability exploitation, credential reuse, and network pivoting
- Enumerate kill-chain attack paths with RelationalAI multi-relationship path enumeration, a multi-edge pattern that fixes the technique order
- Run a point query that lists every route between one named entry point and one named crown jewel
- Rank the kill-chains by the asset exposure summed along each one
- Persist which assets lie on a crown-jewel attack path back onto the ontology

## What's included

- **Self-contained script**: `cybersecurity_attack_paths.py` runs the full analysis end-to-end
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

## Sample data

`data/assets.csv` holds 12 assets that make up a small enterprise estate, spanning a perimeter (`dmz`), an `internal` zone of services and workstations, and a `restricted` zone of high-value systems. Each row carries `id`, `name`, `zone`, an `internet_facing` flag (`yes`/`no`), a `crown_jewel` flag (`yes`/`no`), and an `exposure_score` (an integer stand-in for a CVSS or attack-surface metric). Two assets are crown jewels (the Domain Controller and the Customer Database); three sit internet-facing on the perimeter.

`data/attack_steps.csv` holds 16 directed attack steps, one per row, with `src`, `dst`, and a `technique` tag. The technique splits the steps into the three attacker moves the kill-chain composes in order: `exploit` (vulnerability exploitation), `cred` (credential reuse), and `pivot` (network lateral movement). Each step reads as "an attacker on `src` can reach `dst` by this technique".

## Model overview

- **Key entities**: `Asset` — one host, service, or account in the enterprise estate.
- **Primary identifiers**: `Asset` by `id`.
- **Important invariants**: the three technique edges are directed (`src` reaches `dst`, not the reverse); `internet_facing` and `crown_jewel` are `yes`/`no` flags that pin the kill-chain endpoints; `on_attack_path` is set only on assets that lie on a crown-jewel-reaching chain.

### `Asset`

A host, service, or account in the enterprise estate. Its flags mark where attack paths can start (`internet_facing`) and end (`crown_jewel`), and `on_attack_path` is persisted back onto the asset after the kill-chains are enumerated.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | string | Yes | Loaded from `data/assets.csv` |
| `name` | string | No | Human-readable asset name |
| `zone` | string | No | `dmz`, `internal`, or `restricted` |
| `internet_facing` | string | No | `yes`/`no`; a kill-chain source must be `yes` |
| `crown_jewel` | string | No | `yes`/`no`; a kill-chain destination must be `yes` |
| `exposure_score` | int | No | Per-asset risk score summed along each chain for ranking |
| `on_attack_path` | string | No | `yes`, persisted onto assets that lie on a crown-jewel chain |

### Relationships

Four directed self-relationships between assets. The first three are the technique-tagged kill-chain edges; `can_reach` is the technique-agnostic union used by the point query.

| Relationship | Schema (reading string fields) | Notes |
|---|---|---|
| `exploit_to(Asset, Asset)` | `src`, `dst` | Vulnerability exploitation step |
| `cred_to(Asset, Asset)` | `src`, `dst` | Credential-reuse step |
| `pivot_to(Asset, Asset)` | `src`, `dst` | Network lateral-movement step |
| `can_reach(Asset, Asset)` | `src`, `dst` | Union of all steps (any technique); used by the point query |

## How it works

```text
CSV files --> Define Asset + technique edges --> Kill-chain enumeration (multi-edge)
          --> Point query (entry to crown jewel) --> Exposure ranking --> Persist Asset.on_attack_path
```

### 1. Model assets and one edge per technique

Each attacker technique is its own directed relationship between assets, plus a technique-agnostic union edge for the point query:

```python
Asset.exploit_to = model.Relationship(f"{Asset} exploits to {Asset}", short_name="exploit_to")
Asset.cred_to = model.Relationship(f"{Asset} reuses credentials to {Asset}", short_name="cred_to")
Asset.pivot_to = model.Relationship(f"{Asset} pivots to {Asset}", short_name="pivot_to")
# Technique-agnostic union edge: an attacker can move from src to dst by SOME
# technique. Used for the point query (any route between two named assets).
Asset.can_reach = model.Relationship(f"{Asset} can reach {Asset}", short_name="can_reach")
```

### 2. Enumerate kill-chain attack paths (multi-edge, requires `relationalai>=1.15`)

The path pattern composes the three techniques in series. The first hop is an exploit, the second is credential reuse, then one or more lateral pivots, ending at an explicit destination. Filtering the source to an internet-facing asset and the destination to a crown jewel pins the threat model:

```python
a, b, c, dst = Asset.ref(), Asset.ref(), Asset.ref(), Asset.ref()
kill = model.path(a.exploit_to, b.cred_to, c.pivot_to.repeat(1, MAX_PIVOTS), dst).all_paths()
kill_df = (
    model.where(
        kill,
        a.internet_facing == "yes",
        dst.crown_jewel == "yes",
    )
    .select(
        kill.alias("path_id"),
        kill.nodes["index"].alias("step"),
        Asset(kill.nodes).id.alias("asset_id"),
        Asset(kill.nodes).name.alias("asset_name"),
    )
    .to_df()
)
```

The edge order is enforced by the pattern. A single "can move" union edge or a flat join cannot express "exploit first, then credentials, then pivots", which is exactly the kill-chain signature analysts care about. `kill.relationships["relationship"]` reads the technique used at each hop.

### 3. Point query between two named assets

Pinning both endpoints by id enumerates every route between a chosen entry point and a chosen crown jewel over the union edge:

```python
src_pt, dst_pt = Asset.ref(), Asset.ref()
route = model.path(src_pt.can_reach.repeat(1, MAX_ROUTE_HOPS), dst_pt).all_paths()
route_df = (
    model.where(
        route,
        src_pt.id == ENTRY_ASSET,
        dst_pt.id == TARGET_ASSET,
    )
    .select(
        route.alias("path_id"),
        route.nodes["index"].alias("step"),
        Asset(route.nodes).id.alias("asset_id"),
    )
    .to_df()
)
```

### 4. Persist the assets on a crown-jewel attack path

The assets along the kill-chains are flagged back onto the ontology so a later query can pull them without re-enumerating paths:

```python
Asset.on_attack_path = model.Property(f"{Asset} on attack path {String:on_attack_path}")
on_path_ids = sorted({i for ch in chains for i in ch["asset_ids"]})
flag_data = model.data(pd.DataFrame({"id": on_path_ids}))
fa = Asset.ref()
model.where(fa.id == flag_data["id"]).define(fa.on_attack_path("yes"))
```

## Customize this template

**Use your own data:**
- Replace the CSVs in `data/` with your own assets and attack steps, keeping the same column names. Tag each step with the technique an attacker would use (`exploit`, `cred`, `pivot`, or your own taxonomy).
- Mark internet-facing assets and crown jewels with `yes` or `no` so the kill-chain endpoints match your environment.

**Extend the analysis:**
- Add more techniques (for example `phish` or `escalate`) as additional edges and lengthen the multi-edge pattern.
- Raise `MAX_PIVOTS` or `MAX_ROUTE_HOPS` for larger estates with deeper lateral movement.
- Feed `Asset.exposure_score` from a real vulnerability or attack-surface feed so the ranking reflects live risk.

## Troubleshooting

<details>
  <summary>Why do I see <code>relationalai</code> version or path import errors?</summary>

- Path enumeration with multi-edge patterns requires `relationalai` 1.15 or newer. Confirm your installed version with `python -m pip show relationalai`.

</details>

<details>
  <summary>Why does authentication or configuration fail?</summary>

- Run `rai init` to create or update `raiconfig.toml`.
- If you have multiple profiles, set `RAI_PROFILE` or switch profiles in your config.

</details>

## Learn more

- [RelationalAI documentation](https://docs.relational.ai/) — language, modeling, and reasoner reference.
- [Template gallery](https://docs.relational.ai/build/templates) — other runnable templates, including graph, rules, and prescriptive examples.

## Support

- Questions or issues: [support.relational.ai](https://support.relational.ai).
