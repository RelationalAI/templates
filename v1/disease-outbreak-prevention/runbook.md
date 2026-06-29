# Disease Outbreak Prevention — Analyst Runbook

When an outbreak spreads, public-health officials have to deploy limited resources — vaccines, testing kits, response teams — where they will contain the most transmission. The dataset is a regional health network of 10 facilities connected by 15 directed transfer links, each weighted by transmission risk (patient transfer volume times contact intensity). The analysis ranks facilities by their cumulative transmission risk so the highest-risk hubs get priority.

```text
10 facilities (type, region) · 15 connections (directed, weighted = transfer volume x contact intensity)
      │
      ▼
/rai-graph-analysis
   • weighted degree centrality (cumulative transmission risk) -> Central Hospital & Public Health Dept (28.89)
   • indegree / outdegree for context (who feeds whom)
   • Downtown facilities hold ranks 1–4 → priority resource deployment
```

Each prompt is pasted into a fresh agent session loaded with the named `/rai-*` skill (named at the start of each prompt). They run in order in a single session — the graph step reads the `Facility`/`FacilityConnection` graph the build step created.

---

## 1. Build the ontology

**Prompt:** /rai-build-starter-ontology Build an ontology from `data/facilities.csv` (each facility has a type and a region) and `data/connections.csv` (each directed connection links two facilities and has a patient transfer volume and a contact intensity). Derive a risk weight as transfer volume times contact intensity, and model the connection as a directed relationship from one facility to another carrying that risk weight.

**Response:** Loads `Facility` (10: hospitals, clinics, testing centers, government and emergency services across 5 regions) and `FacilityConnection` (15 directed links, each with `transfer_volume`, `contact_intensity`, and a derived `risk_weight`) — a directed, risk-weighted transmission graph.

## 2. Examine the ontology

**Prompt:** /rai-querying What concepts and relationships does the ontology have, and how many of each?

**Response:** One node concept, `Facility` (10), connected by `FacilityConnection` (15 directed, risk-weighted edges) — about 3 connections per facility.

## 3. Rank facilities by transmission risk

**Prompt:** /rai-graph-analysis Which facilities carry the greatest cumulative transmission risk — the highest total risk across their direct transfer links, weighting each link by its transmission risk? Rank them so we can prioritize resource deployment, and include each facility's incoming and outgoing connection counts for context.

**Response:** By weighted degree centrality, the top hubs are **Central Hospital and Public Health Dept, tied at 28.89**, then **Regional Testing Lab at 24.22** and Emergency Response Hub at 20.89. Indegree/outdegree add nuance — Central Hospital is a pure source (4 out, 0 in) while Emergency Response Hub is a pure sink (3 in, 0 out).

## 4. Read the priority list

**Prompt:** /rai-graph-analysis Which facilities should get priority resource deployment, and what pattern do the top-ranked facilities share?

**Response:** The top three priority facilities are **Central Hospital, Public Health Dept, and Regional Testing Lab**. The clear pattern is geographic: **all four Downtown facilities occupy ranks 1–4**, far above the regional clinics (the lowest-ranked facilities sit near 2.7). Concentrating vaccines, testing, and response capacity on the Downtown cluster covers the highest-risk transfer pathways first.

## Data

Bundled CSVs in `data/`: 10 facilities, 15 connections. Entry point `disease_outbreak_prevention_network.py` (shared model in `model_setup.py`; `app.py` is an optional Streamlit UI).
