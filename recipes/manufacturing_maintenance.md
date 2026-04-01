# Recipe: Manufacturing Maintenance Scheduling

A multi-reasoner chain that discovers machine dependency clusters, flags overdue maintenance and parts reorder needs, and optimizes preventive maintenance scheduling across periods, technicians, and machines.

## Pattern

```
Predict (surface failure risk signals)
  -> Discover structure (identify dependency clusters)
    -> Classify (flag overdue maintenance + reorder triggers)
      -> Optimize (schedule maintenance to minimize total cost)
        -> Stress-test (explore scenarios)
```

## Stages

### Stage 1: Predict Machine Failures
**Reasoner:** Predictive (pre-computed)
**Question:** "Which machines are most likely to fail in the next maintenance window?"

**Inputs:**
- Machine failure probability -- pre-computed ML failure likelihood per machine
- Machine remaining useful life -- estimated hours before failure
- Machine criticality -- business impact score (1-5)

**Outputs:**
- Per-machine risk ranking combining failure probability, remaining useful life, and criticality
- Machines with high failure probability and low remaining useful life are priority candidates

**Notes:**
- Uses pre-computed predictions already present in the ontology
- No RAI predictive reasoner invocation needed -- this is a query over existing ML outputs
- Output feeds Stage 3 as an input signal for overdue maintenance classification
- Output feeds Stage 4 as a cost coefficient in the failure risk term of the objective

---

### Stage 2: Identify Dependency Clusters
**Reasoner:** Graph
**Template:** `machine_dependencies/`
**Question:** "Which machines share technicians or facilities, creating scheduling dependencies?"

**Inputs:**
- Machine concept as nodes
- Qualification relationships as edges (machines sharing a qualified technician)
- Machine facility and location as grouping attributes

**Graph construction:**
- Undirected graph over Machines via shared Technician qualifications
- Two machines are connected if they require the same qualified technician
- Additional edges for machines in the same facility/location (co-location cluster)
- Algorithm: weakly connected components (dependency clusters) + degree centrality (bottleneck machines)

**Outputs:**
- Machine dependency cluster -- group ID for machines that compete for the same technicians
- Machine scheduling centrality -- how many other machines a given machine's maintenance competes with
- High-centrality machines are bottlenecks: maintaining them blocks technicians from other work

**Notes:**
- Independent of Stage 1 -- can run in parallel
- Cluster information helps interpret Stage 4 results (why certain machines are deferred)

---

### Stage 3: Flag Compliance Issues
**Reasoner:** Rules
**Template:** `manufacturing_compliance/`
**Question:** "Which machines are overdue for maintenance and which parts need reorder?"

**Inputs:**
- Machine remaining useful life and maintenance duration hours (base ontology)
- Parts inventory stock level and minimum order quantity (base ontology)

**Rules:**
- Overdue maintenance: remaining useful life < maintenance duration hours (the machine may fail before maintenance can complete)
- Parts reorder: stock level <= minimum order quantity (parts will run out before next delivery)

**Outputs:**
- Per-machine overdue maintenance flag (boolean)
- Per-part reorder flag (boolean)
- Overdue machines become priority candidates in Stage 4
- Parts reorder flags surface supply risks that may block scheduled maintenance

**Notes:**
- Depends on Stage 1 output (failure risk signals contextualize which overdue flags are most urgent)
- Independent of Stage 2

---

### Stage 4: Optimize Maintenance Schedule
**Reasoner:** Prescriptive
**Template:** `machine_maintenance/`
**Question:** "How should we schedule maintenance across periods, technicians, and machines to minimize total expected cost?"

**Problem type:** Multi-period scheduling (mixed-integer program)

**Inputs (from ontology):**
- Machine failure probability, estimated parts cost, criticality -- failure cost coefficients
- Machine maintenance duration hours -- labor time per job
- Technician hourly rate -- labor cost
- Technician period capacity hours -- available hours per technician per period
- Technician-machine co-location flag -- travel cost trigger
- Qualification -- restricts which technicians can work on which machine types

**Inputs (from earlier stages):**
- Machine failure probability + remaining useful life (Stage 1) -- prioritizes high-risk machines
- Machine overdue maintenance flag (Stage 3) -- urgency signal for scheduling priority

**Decision variables:**
- x_maintain (binary) -- whether to maintain machine m in period t
- x_vulnerable (binary) -- whether machine m remains unmaintained through period t
- x_assigned (binary) -- whether technician k is assigned to machine m in period t

**Constraints:**
- Cumulative coverage: each machine is either maintained by period t or remains vulnerable
- Assignment linkage: if a machine is maintained in period t, exactly one qualified technician is assigned
- Technician capacity: total assigned hours per technician per period <= available hours
- Parts/bay capacity: at most N maintenance jobs per period (facility throughput limit)

**Objective:**
- Minimize: failure cost (probability * parts cost * criticality for vulnerable machines) + labor cost (duration * hourly rate for assignments) + travel cost (penalty for cross-location assignments)

**Outputs:**
- Period-by-period maintenance schedule with technician assignments
- Total cost breakdown: failure risk, labor, travel
- Identification of deferred machines and capacity bottlenecks

---

### Stage 5: Scenario Analysis
**Reasoner:** Prescriptive (re-solve)
**Question:** "How would the maintenance plan change under disruptions?"

**Scenarios:**

| Scenario | Parameter Change | What to Observe |
|----------|-----------------|-----------------|
| Key technician unavailable | Set capacity hours = 0 for a technician across all periods | Cost increase, deferred machines, feasibility |
| Parts supply delayed | Reduce parts capacity per period | Schedule stretching, vulnerability increase |
| New machine added | Add a high-criticality machine with high failure probability | Schedule compression, technician reallocation |
| Budget for training | Enable a training option (add new qualification) | Expanded technician coverage, potential cost reduction |

**Notes:**
- Each scenario is a parameter modification + re-solve of Stage 4
- Compare total cost, schedule timing, and vulnerability windows across scenarios
- High-centrality machines from Stage 2 are natural candidates for "what if this machine breaks before scheduled maintenance"

---

## Stage Dependencies

```
Stage 1 (Predict) -----> Stage 3 (Rules) -----> Stage 4 (Optimize) --> Stage 5 (Scenarios)
Stage 2 (Graph)   --------------------------------^
```

- Stages 1 and 2 are independent -- run in parallel
- Stage 3 depends on Stage 1
- Stage 4 depends on Stages 2 and 3
- Stage 5 depends on Stage 4

---

## Templates Used

| Stage | Template Directory | Purpose |
|-------|--------------------|---------|
| Stage 2 | `machine_dependencies/` | Weakly connected components and degree centrality over shared-technician graph |
| Stage 3 | `manufacturing_compliance/` | Overdue maintenance flags and parts reorder triggers |
| Stage 4 | `machine_maintenance/` | Multi-period maintenance scheduling with technician assignment |

---

## Adapting This Recipe

This pattern generalizes to any domain where you can:

1. **Surface risk/prediction signals** from pre-computed failure or degradation data
2. **Discover dependency structure** in a shared-resource network (technicians, facilities, tools)
3. **Classify entities** by combining signals into compliance flags (overdue, reorder)
4. **Optimize scheduling** informed by predictions, dependencies, and compliance
5. **Stress-test** by varying resource availability and re-solving

To adapt: replace the domain-specific concepts (Machine, Technician, Qualification, Period) with your equivalents, and adjust the constraints to match your operational rules. Each stage uses a standalone template that can also be run independently.
