---
title: "Disease Outbreak Prevention Network"
description: "Use degree centrality to identify the most connected healthcare facilities in a public health network, helping prioritize resource deployment during disease outbreaks."
experience_level: beginner
industry: Healthcare
reasoning_types:
  - Graph
tags:
  - graph-analytics
  - degree-centrality
  - public-health
---

## What this template is for

During a disease outbreak, public health officials must quickly decide where to deploy limited resources like vaccines, testing equipment, and emergency response teams. This template demonstrates how to use **degree centrality** — a graph algorithm that measures how connected each node is in a network — to identify the most strategically important healthcare facilities.

By analyzing a network of hospitals, clinics, testing centers, and community organizations, this template helps you prioritize facilities that are most connected to others. These highly connected facilities act as critical hubs in the health network, making them ideal locations for maximum resource reach and rapid information dissemination during an outbreak response.

## Who this is for
- **Beginners** who want to learn degree centrality with a real-world use case
- **Data scientists** new to RelationalAI looking for a simple graph analytics example
- **Public health analysts** planning outbreak response strategies
- **Healthcare network planners** optimizing resource allocation

## What you'll build

- Load a public health network with 10 facilities and 15 directed connections from CSV files
- Use RelationalAI's Graph API to model the healthcare network
- Calculate degree centrality for each facility (normalized connectivity score)
- Track incoming and outgoing connections (indegree and outdegree)
- Rank facilities by their centrality scores
- Identify top priority facilities for resource deployment
- Generate a detailed prioritized list to guide outbreak response decisions

This template uses **RelationalAI's graph modeling** capabilities with the Graph class to represent the network, and built-in graph algorithms to compute degree centrality, indegree, and outdegree efficiently.

## What's included

- **Model + script**: `disease_outbreak_prevention_network.py`
- **Data**: `data/facilities.csv` and `data/connections.csv`

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools
- Python >= 3.10
- pandas library

## Quickstart

Follow these steps to run the template with the included sample data.
You can customize the data and model as needed after you have it running end-to-end.

1. Download the ZIP file for this template and extract it:

   ```bash
   curl -O https://private.relational.ai/templates/zips/v1/disease_outbreak_prevention_network.zip
   unzip disease_outbreak_prevention_network.zip
   cd disease_outbreak_prevention_network
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

   From this folder:

   ```bash
   python -m pip install .
   ```

4. **Configure Snowflake connection and RAI profile**

   ```bash
   rai init
   ```

5. **Run the template**

   ```bash
   python disease_outbreak_prevention_network.py
   ```

6. **Expected output**

   ```
   ====================================================================================================
   DISEASE OUTBREAK PREVENTION NETWORK - DEGREE CENTRALITY ANALYSIS
   ====================================================================================================

   Facilities ranked by degree centrality (most connected first):

   Degree Centrality: Normalized score (0-1) indicating relative connectivity in the network
   Higher scores indicate more critical facilities for outbreak response coordination

   These facilities should receive priority for:
   • Vaccine and medical supply deployment
   • Testing station setup
   • Emergency response team positioning

   ----------------------------------------------------------------------------------------------------
   rank                    name               type   region  degree_centrality  incoming_connections  outgoing_connections  total_connections
      1        Central Hospital           Hospital Downtown             0.4444                     0                     4                  4
      2         Westside Clinic             Clinic     West             0.4444                     2                     2                  4
      3      Public Health Dept         Government Downtown             0.4444                     2                     2                  4
      4 Community Health Center      Community Org    North             0.3333                     2                     1                  3
      5    Regional Testing Lab     Testing Center Downtown             0.3333                     1                     2                  3
      6   North Valley Hospital           Hospital    North             0.3333                     2                     1                  3
      7  Emergency Response Hub Emergency Services Downtown             0.3333                     3                     0                  3
      8        Eastside Medical             Clinic     East             0.2222                     1                     1                  2
      9     Mobile Testing Unit     Testing Center     West             0.2222                     1                     1                  2
      10  South Community Clinic             Clinic    South             0.2222                     1                     1                  2
   ----------------------------------------------------------------------------------------------------

   🎯 TOP 3 PRIORITY FACILITIES FOR IMMEDIATE RESOURCE DEPLOYMENT:

   #1 - Central Hospital
         Type: Hospital
         Region: Downtown
         Degree Centrality: 0.4444
         Total Connections: 4 (0 incoming, 4 outgoing)

   #2 - Westside Clinic
         Type: Clinic
         Region: West
         Degree Centrality: 0.4444
         Total Connections: 4 (2 incoming, 2 outgoing)

   #3 - Public Health Dept
         Type: Government
         Region: Downtown
         Degree Centrality: 0.4444
         Total Connections: 4 (2 incoming, 2 outgoing)

      📊 NETWORK SUMMARY:
      • Total facilities analyzed: 10
      • Average degree centrality: 0.3333
      • Average connections per facility: 3.0
      • Most connected facility: Central Hospital (4 connections)
   ✅ Analysis complete!
   ```

## Template structure

```text
.
├─ README.md                                        # this file
├─ pyproject.toml                                   # dependencies
├─ disease_outbreak_prevention_network.py           # main script (run this!)
└─ data/
   ├─ facilities.csv                                # 10 healthcare facilities
   └─ connections.csv                               # 15 network connections
```

**Start here**: Run `python disease_outbreak_prevention_network.py` to see the complete analysis.

## Sample data

The sample data represents a simplified public health network in a metropolitan area:

- **facilities.csv**: 10 facilities including hospitals, clinics, testing centers, community organizations, government agencies, and emergency services. Each has a unique ID, name, type, and geographic region.
- **connections.csv**: 15 directed connections representing relationships like patient referral pathways, data sharing agreements, and coordination partnerships. Each connection has a source (from) and target (to) facility.

The network is intentionally small (10 nodes, 15 edges) to make it easy to understand and verify the centrality calculations manually.

## Model overview

This model represents a public health network as a directed graph where facilities are nodes and connections are edges.

- **Key entities**: `Facility` (healthcare facilities) with a `connects_to` relationship
- **Primary identifiers**: Facility ID (integer)
- **Graph structure**: Directed, unweighted graph using RelationalAI's Graph API

### Facility Concept

The `Facility` concept represents healthcare facilities, testing centers, and community organizations in the network.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | Integer | Yes | Unique facility identifier from `data/facilities.csv` |
| `name` | String | No | Facility name (e.g., "Central Hospital") |
| `type` | String | No | Category: Hospital, Clinic, Testing Center, Community Org, Government, Emergency Services |
| `region` | String | No | Geographic region: Downtown, North, South, East, West |

### Facility Relationship

The `connects_to` relationship represents directed connections between facilities (patient referrals, data sharing, coordination partnerships).

| Property | Type | Notes |
|---|---|---|
| `from_facility` | Facility | Source facility in the connection |
| `connects_to` | Facility | Target facility in the connection |

### Graph Metrics

The template calculates three key metrics using RelationalAI's Graph API:

| Metric | Type | Description |
|---|---|---|
| `degree_centrality` | Float | Normalized score (0-1) indicating relative connectivity. Higher = more central |
| `incoming_connections` | Integer | Indegree: number of facilities that connect TO this facility |
| `outgoing_connections` | Integer | Outdegree: number of facilities this facility connects TO |

## How it works

The template follows this flow:

```text
CSV files → Load network → Define graph → Calculate metrics → Rank facilities → Display results
```

### 1. Load facilities from CSV

```python
from relationalai.semantics import Model, data

# Create a Semantics model container
model = Model("disease_outbreak_prevention", config=globals().get("config", None))

# Define Facility concept with properties
Facility = model.Concept("Facility")
Facility.id = model.Property(f"{Facility} has {Integer:id}")
Facility.name = model.Property(f"{Facility} has {String:name}")
Facility.type = model.Property(f"{Facility} has {String:type}")
Facility.region = model.Property(f"{Facility} has {String:region}")

# Load facilities from CSV
facility_df = pd.read_csv(DATA_DIR / "facilities.csv")
facility_data = data(facility_df)

model.define(
    Facility.new(
        id=facility_data.id,
        name=facility_data.name,
        type=facility_data.type,
        region=facility_data.region
    )
)
```

### 2. Create directed connections

Load connections from CSV and create the relationship:

```python
from relationalai.semantics import define

# Define the connects_to relationship
Facility.connects_to = model.Relationship(
    f"{Facility:from_facility} connects to {Facility:connects_to}"
)

# Load connections from CSV
connections_data = data(pd.read_csv(DATA_DIR / "connections.csv"))

# Create connections (directed edges from -> to)
f_from, f_to = Facility.ref("f_from"), Facility.ref("f_to")

define(Facility.connects_to(f_from, f_to)).where(
    f_from.id == connections_data.from_facility_id,
    f_to.id == connections_data.to_facility_id
)
```

### 3. Define the graph and edges

Use RelationalAI's Graph API to create a directed, unweighted graph:

```python
from relationalai.semantics.reasoners.graph import Graph

# Define directed graph with Facility nodes
graph = Graph(model, directed=True, weighted=False, node_concept=Facility)

# Define edges based on the connects_to relationship
define(graph.Edge.new(
    src=Facility,
    dst=Facility.connects_to,
))
```

### 4. Calculate graph metrics

Use built-in graph algorithms to compute centrality metrics:

```python
# Calculate degree centrality (normalized connectivity score)
degree_centrality = graph.degree_centrality()

# Calculate incoming edges (indegree)
incoming_edges = graph.indegree()

# Calculate outgoing edges (outdegree)
outgoing_edges = graph.outdegree()
```

### 5. Query and rank facilities

Query the graph to retrieve all metrics and rank facilities:

```python
from relationalai.semantics import where, select

# Create variable references
facility = graph.Node.ref("facility")
centr_score = Float.ref("d_score")
in_edges = Integer.ref("in_edges")
out_edges = Integer.ref("out_edges")

# Query the graph
results = where(
    degree_centrality(facility, centr_score),
    incoming_edges(facility, in_edges),
    outgoing_edges(facility, out_edges)
).select(
    facility.id,
    facility.name,
    facility.type,
    facility.region,
    centr_score.alias("degree_centrality"),
    in_edges.alias("incoming_connections"),
    out_edges.alias("outgoing_connections")
).to_df()

# Sort by degree centrality (descending)
results = results.sort_values("degree_centrality", ascending=False)
results.insert(0, "rank", range(1, len(results) + 1))
```

### 6. Display formatted results

The script prints a comprehensive analysis including:
- A ranked table of all facilities with their metrics
- Detailed breakdown of the top 3 priority facilities
- Network-wide summary statistics

## Customize this template

### Use your own data

- Replace the CSV files in the `data/` directory with your own network, keeping the same column names (or update the logic in disease_outbreak_prevention_network.py).
- Make sure that the facilities in **connections.csv** only references valid facility IDs.


### Extend the model

**Add weighted connections**: To weight edges by transfer volume or relationship strength. Don't forget to update the `weighted` property of the graph to `true` and to set the weight of the edges.

## Troubleshooting

<details>
  <summary>Why does authentication/configuration fail?</summary>

- Run `rai init` to create/update `raiconfig.toml`.
- If you have multiple profiles, set `RAI_PROFILE` or switch profiles in your config.

</details>

<details>
  <summary>Why does the script fail to connect to the RAI Native App?</summary>

- Verify the Snowflake account/role/warehouse and `rai_app_name` are correct in `raiconfig.toml`.
- Ensure the RAI Native App is installed and you have access.

</details>