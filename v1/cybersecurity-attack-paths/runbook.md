# Cybersecurity Attack Paths — Analyst Runbook

A security team wants to see how an external attacker could chain techniques to reach a crown-jewel system, not just a list of isolated vulnerabilities. The dataset is a 12-asset enterprise estate (perimeter hosts, internal services and workstations, two restricted crown jewels) connected by 16 directed attack steps, each tagged with a technique. The analysis enumerates end-to-end attack chains and ranks the ones that reach a crown jewel so the team knows which routes to cut first.

```text
Asset graph  (12 assets, 16 technique-tagged steps: exploit / cred / pivot)
      │
      ▼
/rai-graph-analysis  — Path enumeration (multi-edge, relationalai>=1.15)
   • kill-chain signature: exploit (from an internet-facing asset),
     then credential reuse, then 1-2 lateral pivots, into a crown jewel   -> 3 chains
   • point query: every route from Public Web Server to Customer Database
     (any technique, <= 6 hops, no asset revisited)                       -> 7 routes
   • rank kill-chains by total Asset.exposure_score along each            -> top = 28
   • persist Asset.on_attack_path                                         -> 11 of 12 assets
```

Each prompt is pasted into a fresh agent session loaded with the named `/rai-*` skill (named at the start of each prompt). They run in order in a single session — later questions read ontology state (the technique edges, the persisted flags) written by earlier ones.

---

## 1. Build the ontology

**Prompt:** /rai-ontology Build a RelationalAI ontology from `data/assets.csv` and `data/attack_steps.csv`. Each asset has an id, name, zone, whether it is internet-facing, whether it is a crown jewel, and an exposure score. Each attack step is a directed move from one asset to another tagged with a technique (`exploit`, `cred`, or `pivot`). Model one relationship per technique between assets, plus a technique-agnostic `can_reach` relationship populated from every step.

**Response:** Loads 12 `Asset` nodes and four asset-to-asset relationships — `exploit_to`, `cred_to`, `pivot_to` (one per technique), and the union `can_reach`. The 16 steps split into the three typed edges and all 16 populate `can_reach`.

## 2. Examine the ontology

**Prompt:** /rai-pyrel What concepts and relationships does the ontology have, and how many of each?

**Response:** One concept, `Asset`, with properties `name`, `zone`, `internet_facing`, `crown_jewel`, and `exposure_score`; and four self-relationships (`exploit_to`, `cred_to`, `pivot_to`, `can_reach`).

## 3. Kill-chain attack paths into crown jewels

**Prompt:** /rai-graph-analysis Which attack chains follow the full kill-chain signature — an exploit step starting from an internet-facing asset, then a credential-reuse step, then one or two lateral pivots — and end at a crown jewel (an asset flagged `crown_jewel`)? Show the technique used at each hop.

**Response:** 3 kill-chains reach a crown jewel. VPN Gateway —exploit→ Jump Host —cred→ File Server —pivot→ Customer Database; Mail Relay —exploit→ Finance Workstation —cred→ Engineer Workstation —pivot→ Domain Controller; and a 4-hop chain Public Web Server —exploit→ Application Server —cred→ Jump Host —pivot→ Backup Server —pivot→ Customer Database. The technique order is enforced by the path pattern, so chains that move in a different order are correctly excluded.

## 4. All routes between one entry and one crown jewel

**Prompt:** /rai-graph-analysis Treating any technique as a possible move, what are all the routes an attacker on the Public Web Server (`web-01`) could take to reach the Customer Database (`db-01`) in at most six hops, without revisiting an asset?

**Response:** 7 routes connect `web-01` to `db-01`, ranging from 3 hops (web-01, app-01, app-02, db-01) to 5 hops. Both endpoints are pinned by id, so this is a point query that returns the actual route sequences, not just whether a path exists.

## 5. Which kill-chain to remediate first

**Prompt:** /rai-graph-analysis Rank the crown-jewel kill-chains by the total exposure of the assets along each chain (the sum of each distinct asset's `exposure_score`), highest first, so we can prioritize remediation.

**Response:** Highest total exposure is the Public Web Server chain at 28, then the Mail Relay chain at 26, then the VPN Gateway chain at 25. The Public Web Server chain is the first remediation target.

## 6. Persist the assets on an attack path

**Prompt:** /rai-graph-analysis Flag every asset that lies on one of the crown-jewel kill-chains by setting `Asset.on_attack_path` to `yes`, and list the flagged assets.

**Response:** 11 of 12 assets are flagged on a crown-jewel kill-chain and persisted as `Asset.on_attack_path`. Only the API Backend (`app-02`) is not on a kill-chain — it appears in `web-01`-to-`db-01` routes but never in a chain that follows the exploit-then-credential-then-pivot order.
