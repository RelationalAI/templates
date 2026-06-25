# IT Dependency Mapping — Analyst Runbook

A platform engineer wants the downstream blast radius of any component in a software / data-pipeline estate — when a pipeline changes or fails, what is downstream of it, how far the chains reach, and who owns each step along the worst-case path. The dataset is a 14-feature estate (raw sources, pipelines, feature jobs, services, dashboards) wired by 15 `contributes_to` dependency edges into an acyclic DAG. The analysis enumerates every downstream dependency path, reduces them to the maximal end-to-end chains, and traces the owners along the single longest chain.

```text
Dependency DAG  (14 features: sources -> pipelines -> jobs -> services -> dashboards, 15 edges)
      │
      ▼
/rai-graph-analysis  — Variable-length path enumeration (paths: relationalai>=1.15)
   • every downstream dependency path (1-8 hops, all_paths)     -> 46 paths
   • per-feature reach + persist Feature.max_downstream_depth   -> Clickstream Ingest: 7 paths / depth 5
   • maximal end-to-end chains (sub-chains dropped)             -> 6 of 46
   • longest chain = worst-case blast radius + owners along it  -> 5 hops, 6 features / 5 owners
```

These prompts are designed to run in order in a single session: each step reads the `contributes_to` graph the build step established, and the reach step persists `Feature.max_downstream_depth` back onto the ontology.

---

## 1. Build the ontology

**Prompt:** Build a RelationalAI ontology from `data/features.csv` and `data/dependencies.csv`. Each feature is a node in a software / data-pipeline estate — a raw source, pipeline, feature job, service, or dashboard — with an owner and a deploy tier. Each dependency edge says an upstream feature contributes to (feeds) a downstream one. Model `contributes_to` as a self-relationship between features.

**Response:** Loads 14 `Feature` nodes (properties `name`, `owner`, `deploy_tier`) and a `contributes_to` self-relationship populated from the 15 dependency edges, forming an acyclic dependency DAG from raw sources down to dashboards.

## 2. Examine the ontology

**Prompt:** What concepts and relationships does the ontology have, and what does the dependency estate look like end to end?

**Response:** One concept, `Feature`, with a single `contributes_to` self-relationship. The 14 features flow from two critical raw sources (Clickstream Ingest, Transaction CDC Stream) and a CRM sync, through enrichment and feature-engineering pipelines, into services (Churn Scoring API, Billing API, Recommendation Service), and finally two leaf dashboards (Retention Dashboard, Executive Revenue Dashboard). 15 edges, no cycles.

## 3. Downstream reach of every feature (paths, requires `relationalai>=1.15`)

**Prompt:** For every feature, how far does its blast radius reach downstream? Enumerate all downstream dependency paths of any length, count how many start at each feature, and record each feature's longest downstream depth so we can rank features by reach.

**Response:** Variable-length path enumeration (`.all_paths()` over 1–8 `contributes_to` hops) finds 46 downstream paths in total; because the estate is acyclic, every path is a simple chain. Transaction CDC Stream spawns the most downstream paths (9, reaching depth 4), while Clickstream Ingest reaches the deepest (7 paths, depth 5) — "most paths" and "furthest reach" are different questions with different answers. The two leaf dashboards start none. Each feature's longest depth is persisted as `Feature.max_downstream_depth` so a later query can rank by reach without re-enumerating.

## 4. Maximal end-to-end chains

**Prompt:** The path set repeats every sub-chain. Reduce it to the maximal chains — the end-to-end propagation routes not contained inside a longer one.

**Response:** 6 of the 46 paths are maximal; the rest are sub-chains inside them. They are the end-to-end routes from a root source to a leaf dashboard — one 5-hop chain (Clickstream Ingest → Events Enrichment Pipeline → Session Feature Job → Churn Feature Store → Churn Scoring API → Retention Dashboard), four 4-hop chains, and one 3-hop chain into the Executive Revenue Dashboard.

## 5. Worst-case blast radius and the owners along it

**Prompt:** What is the single worst-case propagation path — the longest end-to-end chain — and who owns each step along it? That's the set of people a change at the root would have to clear before it reaches the final consumer.

**Response:** The longest chain is 5 hops: Clickstream Ingest → Events Enrichment Pipeline → Session Feature Job → Churn Feature Store → Churn Scoring API → Retention Dashboard. It spans 6 features and 5 distinct owners — Maya Chen (Clickstream Ingest, critical), Sofia Rossi, Liang Wu (who owns two consecutive steps), Priya Nair, and Hana Kim (Retention Dashboard). A change at Clickstream Ingest propagates through 5 downstream features before reaching the Retention Dashboard, making it the highest-coordination-cost change in the estate.
