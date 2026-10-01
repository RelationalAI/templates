# Traveling Salesman — Analyst Runbook

A route planner wants the shortest round-trip that visits every stop exactly once and returns to the start — the classic Traveling Salesman Problem behind delivery routing, service-technician scheduling, and last-mile logistics. The dataset is 4 locations with the distance between every ordered pair (a complete directed graph, 12 edges). The analysis formulates a mixed-integer program with subtour elimination and returns the single minimum-distance tour.

```text
4 locations, 12 directed distance edges (complete graph), symmetric distances
      │
      ▼
/rai-prescriptive-problem
   • decision: a binary "use this edge?" per edge + an integer position per node (MTZ)
   • constraints: each node has exactly one edge in and one out; MTZ subtour elimination; anchor node 1
   • objective: minimize total distance of the selected edges
   • HiGHS mixed-integer program                 -> OPTIMAL, tour distance 8.5
      │
      ▼
/rai-prescriptive-results
   • optimal tour: 1 → 2 → 4 → 3 → 1   (4 edges, total distance 8.5)
```

Each prompt is pasted into a fresh agent session loaded with the named `/rai-*` skill (named at the start of each prompt). They run in order in a single session — the formulate step reads the `Edge`/`Node` concepts the build step created, and the interpret step reads the `Edge.x` selections the solve wrote back to the ontology.

---

## 1. Build the ontology

**Prompt:** /rai-ontology Build an ontology from `data/edges.csv` — each row is a directed edge with a source node `i`, a destination node `j`, and a distance `dist`. Derive the set of nodes from the edge endpoints.

**Response:** Loads `Edge` (12 directed edges, properties `i`, `j`, `dist`) and derives a `Node` concept (4 nodes) from the edge endpoints. The data is a complete directed graph on 4 nodes with symmetric distances (e.g. 1↔2 = 2.0, 2↔4 = 1.5, 3↔4 = 2.5, 1↔4 = 4.0).

## 2. Examine the ontology

**Prompt:** /rai-pyrel What concepts and relationships does the ontology have, and how many of each?

**Response:** Two concepts — 12 `Edge` (each with `i`, `j`, `dist`) and 4 `Node` (derived from the endpoints) — forming a complete directed graph where every ordered pair of distinct nodes has an edge.

## 3. Find the shortest tour

**Prompt:** /rai-prescriptive-problem What's the shortest round-trip that visits every node exactly once and returns to the start, as one connected tour with no disconnected subtours? Use a binary decision per edge for whether it's in the tour, require every node to have exactly one selected edge in and one out, and eliminate subtours with MTZ ordering variables — one integer position per node, anchored at node 1. Minimize total distance, and persist the edge selection to the ontology.

**Response:** OPTIMAL (HiGHS mixed-integer program), shortest tour distance **8.5** (relative gap 0.0). The model has 16 variables (12 binary edge selections + 4 integer MTZ positions) and 15 constraints; the edge decision is written back as `Edge.x` and the position as `Node.u`.

## 4. Read the optimal route

**Prompt:** /rai-prescriptive-results Which edges form the optimal tour, in what order, and what's the total distance?

**Response:** Four edges are selected — 1 → 2 (2.0), 2 → 4 (1.5), 4 → 3 (2.5), 3 → 1 (2.5) — forming the single tour **1 → 2 → 4 → 3 → 1** with total distance **8.5**. Exactly one edge enters and leaves each node, and the MTZ positions confirm no disconnected subtours.

## Data

Bundled CSV in `data/`: 12 directed edges (distances among 4 nodes). Full model in `traveling_salesman.py`.
