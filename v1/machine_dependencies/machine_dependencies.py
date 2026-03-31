"""Machine Dependencies (graph analysis) template.

This script demonstrates graph analysis in RelationalAI:

- Load machines, technicians, and qualifications from CSV.
- Build an undirected, unweighted graph where machine nodes are connected
  when they share a qualified technician (self-join on qualifications).
- Run weakly_connected_component() to identify dependency clusters.
- Run betweenness_centrality() to find bottleneck machines.
- Combine betweenness with failure probability to flag critical machines.

    Run:
        `python machine_dependencies.py`

    Output:
        Prints dependency clusters, betweenness centrality scores, and
        critical bottleneck machines.
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Float, Integer, Model, String, where, select
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.reasoners.graph import Graph

model = Model("machine_dependencies")

# --------------------------------------------------
# Load data & define semantic model
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"

# Machine concept: manufacturing machines with maintenance and risk attributes.
Machine = model.Concept("Machine", identify_by={"id": String})
Machine.name = model.Property(f"{Machine} has {String:name}")
Machine.machine_type = model.Property(f"{Machine} has type {String:machine_type}")
Machine.facility = model.Property(f"{Machine} at {String:facility}")
Machine.failure_probability = model.Property(
    f"{Machine} has failure probability {Float:failure_probability}"
)
Machine.criticality = model.Property(f"{Machine} has criticality {String:criticality}")

machine_data = model.data(read_csv(DATA_DIR / "machines.csv"))
model.define(
    m := Machine.new(id=machine_data.id),
    m.name(machine_data.name),
    m.machine_type(machine_data.machine_type),
    m.facility(machine_data.facility),
    m.failure_probability(machine_data.failure_probability),
    m.criticality(machine_data.criticality),
)

# Technician concept: maintenance personnel with skill levels.
Technician = model.Concept("Technician", identify_by={"id": String})
Technician.name = model.Property(f"{Technician} has {String:name}")
Technician.skill_level = model.Property(f"{Technician} has skill level {String:skill_level}")

tech_data = model.data(read_csv(DATA_DIR / "technicians.csv"))
model.define(
    t := Technician.new(id=tech_data.id),
    t.name(tech_data.name),
    t.skill_level(tech_data.skill_level),
)

# Qualification concept: technician-to-machine certification links.
Qualification = model.Concept(
    "Qualification", identify_by={"id": String}
)
Qualification.technician = model.Relationship(f"{Qualification} for {Technician}")
Qualification.machine = model.Relationship(f"{Qualification} covers {Machine}")

qual_data = model.data(read_csv(DATA_DIR / "qualifications.csv"))
model.define(
    q := Qualification.new(id=qual_data.id),
    q.technician(Technician.filter_by(id=qual_data.technician_id)),
    q.machine(Machine.filter_by(id=qual_data.machine_id)),
)

# --------------------------------------------------
# Build graph: Machine nodes, shared-technician edges
# Two machines are connected if the same technician is qualified
# for both (self-join on qualifications).
# --------------------------------------------------

dep_graph = Graph(model, directed=False, weighted=False, node_concept=Machine, aggregator="sum")

# Edge: shared qualified technician
m1, m2 = Machine.ref(), Machine.ref()
q1, q2 = Qualification.ref(), Qualification.ref()
tech = Technician.ref()

model.where(
    q1.technician(tech),
    q2.technician(tech),
    q1.machine(m1),
    q2.machine(m2),
    m1.id < m2.id,  # avoid self-loops and duplicates
).define(
    dep_graph.Edge.new(src=m1, dst=m2)
)

print("=== Machine Dependency Graph ===")
dep_graph.num_nodes().inspect()
dep_graph.num_edges().inspect()

# --------------------------------------------------
# 1. Weakly Connected Components -- dependency clusters
# --------------------------------------------------

wcc = dep_graph.weakly_connected_component()

node_ref = dep_graph.Node.ref("n")
comp_ref = dep_graph.Node.ref("comp")

wcc_df = (
    where(wcc(node_ref, comp_ref))
    .select(
        node_ref.id.alias("machine_id"),
        node_ref.name.alias("machine_name"),
        node_ref.machine_type.alias("machine_type"),
        node_ref.facility.alias("facility"),
        comp_ref.id.alias("component_id"),
        aggs.count(node_ref).per(comp_ref).alias("cluster_size"),
    )
    .to_df()
)

num_clusters = wcc_df["component_id"].nunique()
print(f"\n=== Dependency Clusters ===")
print(f"Clusters found: {num_clusters}")

for comp_id in sorted(wcc_df["component_id"].unique()):
    comp_df = wcc_df[wcc_df["component_id"] == comp_id]
    cluster_size = int(comp_df["cluster_size"].iloc[0])
    facilities = ", ".join(sorted(comp_df["facility"].unique()))
    print(f"\n  Cluster {comp_id}: {cluster_size} machines ({facilities})")
    for _, row in comp_df.sort_values(["facility", "machine_name"]).iterrows():
        print(f"    - {row['machine_name']} ({row['machine_type']}, {row['facility']})")

# --------------------------------------------------
# 2. Betweenness Centrality -- bottleneck machines
# --------------------------------------------------

betweenness = dep_graph.betweenness_centrality()

node_b = dep_graph.Node.ref("nb")
btwn_score = Float.ref("btwn")

betweenness_df = (
    where(betweenness(node_b, btwn_score))
    .select(
        node_b.id.alias("machine_id"),
        node_b.name.alias("machine_name"),
        node_b.machine_type.alias("machine_type"),
        node_b.facility.alias("facility"),
        node_b.failure_probability.alias("failure_probability"),
        btwn_score.alias("betweenness"),
    )
    .to_df()
    .sort_values("betweenness", ascending=False)
    .reset_index(drop=True)
)

print("\n=== Betweenness Centrality (bottleneck machines) ===")
print(betweenness_df.to_string(index=False))

# --------------------------------------------------
# 3. Most Critical Machines (high betweenness + high failure risk)
# --------------------------------------------------

critical = betweenness_df[
    (betweenness_df["betweenness"] > 0) & (betweenness_df["failure_probability"] > 0.3)
]

print("\n=== Critical Bottleneck Machines ===")
print("Machines that are both dependency bottlenecks and have high failure probability.\n")

if len(critical) > 0:
    for i, (_, row) in enumerate(critical.iterrows(), 1):
        print(f"  #{i}: {row['machine_name']} ({row['machine_type']}, {row['facility']})")
        print(f"      Betweenness: {row['betweenness']:.4f}")
        print(f"      Failure probability: {row['failure_probability']:.4f}")
else:
    print("  No machines found with both high betweenness and high failure probability.")

# --------------------------------------------------
# 4. Cluster summary
# --------------------------------------------------

print("\n--- Cluster Summary ---")
for comp_id in sorted(wcc_df["component_id"].unique()):
    comp_df = wcc_df[wcc_df["component_id"] == comp_id]
    cluster_size = int(comp_df["cluster_size"].iloc[0])
    machines = ", ".join(sorted(comp_df["machine_name"].values))
    print(f"  Cluster {comp_id} ({cluster_size} machines): {machines}")
