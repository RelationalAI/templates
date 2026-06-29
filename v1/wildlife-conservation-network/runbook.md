# Wildlife Conservation Network — Analyst Runbook

A conservation coordinator wants to see how a network of independent organizations — NGOs, research stations, reserves, veterinary and community programs — actually collaborates, so they know where coordination is already strong and who is best placed to lead it. The dataset is 12 organizations connected by 19 partnership edges (an undirected collaboration graph). The analysis detects the natural collaboration clusters and the hub organization within each.

```text
12 organizations (type, region, focus species) · 19 partnerships (undirected collaboration graph)
      │
      ▼
/rai-graph-analysis
   • Louvain community detection        -> 3 collaboration clusters (5 / 4 / 3 organizations)
   • degree centrality per organization -> the hub of each cluster
   • global hub: Serengeti Wildlife Trust — 5 partnerships, centrality 0.4545
```

Each prompt is pasted into a fresh agent session loaded with the named `/rai-*` skill (named at the start of each prompt). They run in order in a single session — the graph steps read the `Organization`/`Partnership` graph the build step created.

---

## 1. Build the ontology

**Prompt:** /rai-build-starter-ontology Build an ontology from `data/organizations.csv` (each organization has a type, a region, and a focus species) and `data/partnerships.csv` (each row is a collaboration partnership between two organizations). Model the partnership as an undirected relationship between organizations.

**Response:** Loads `Organization` (12, with `type`, `region`, `focus_species`) and a `Partnership` relationship (19 undirected collaboration edges between organizations) — forming a collaboration network across East and Southern Africa.

## 2. Examine the ontology

**Prompt:** /rai-querying What concepts and relationships does the ontology have, and how many of each?

**Response:** One concept, `Organization` (12, with type / region / focus species), connected by `Partnership` (19 undirected edges) — an average of about 3.2 partnerships per organization.

## 3. Find the collaboration clusters

**Prompt:** /rai-graph-analysis Which organizations form tight collaboration clusters — groups that partner densely within the group more than across groups? Run community detection on the partnership graph and report how many clusters there are and which organizations fall in each.

**Response:** Louvain community detection finds **3 collaboration clusters** of sizes 5, 4, and 3. They line up with mission and geography: a Southern Africa rhino-focused cluster (5 orgs), an East Africa elephant-focused cluster (4 orgs), and an East Africa big-cats cluster (3 orgs). (The numeric cluster labels are arbitrary, but the partition is stable.)

## 4. Identify the hubs

**Prompt:** /rai-graph-analysis Within each cluster, which organization is the hub — the one with the most partnerships (highest degree centrality) — and which organization is the most connected across the whole network?

**Response:** **Serengeti Wildlife Trust is the clear hub of the elephant cluster and the most connected organization overall** — 5 partnerships, degree centrality 0.4545 — making it the strongest candidate to lead cross-organization coordination. The rhino and big-cats clusters are flatter: their members tie at 3 partnerships each (degree centrality 0.2727), so no single hub stands out and coordination there is more distributed. Leadership is concentrated in one cluster and shared in the other two.

## Data

Bundled CSVs in `data/`: 12 organizations, 19 partnerships. Entry point `wildlife_conservation_network.py` (shared model in `model_setup.py`; `app.py` is an optional Streamlit UI).
