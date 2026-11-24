---
title: "Hospital Staffing"
description: "Explore the tradeoff between overtime cost and patient service level using bi-objective optimization with epsilon constraint."
featured: false
experience_level: intermediate
industry: "Healthcare & Life Sciences"
reasoning_types:
  - Prescriptive
tags:
  - Staffing
  - Scheduling
  - Healthcare
  - Multi-Objective
---

## What this template is for

This template uses **prescriptive reasoning (optimization)** to frame hospital nurse scheduling as a bi-objective problem with two competing objectives: minimize overtime cost versus minimize unmet patient demand. The original single-objective formulation bundled both goals into one weighted penalty sum, forcing the modeler to choose a penalty weight up front. This version unbundles them using the epsilon constraint method: it sweeps a range of caps on allowable unmet demand, and at each cap the solver minimizes overtime cost subject to that service-level constraint.

The result is a Pareto frontier that reveals exactly how much overtime cost each level of patient service requires -- making the tradeoff explicit and auditable rather than hidden inside a penalty weight.

## Who this is for

- Healthcare operations managers building nurse scheduling systems
- Data engineers integrating optimization into hospital workforce platforms
- Developers learning to model staffing problems with mixed binary and continuous variables
- Anyone exploring multi-objective optimization with coverage and skill constraints

## What you'll build

- A nurse-to-shift assignment model with binary decision variables
- Overtime tracking with continuous variables and cost multipliers
- Patient throughput and unmet demand calculations per shift
- Minimum staffing and skill-level coverage constraints
- Epsilon constraint method sweeping unmet demand caps to trace the cost-service frontier
- Pareto analysis with marginal cost per patient and knee detection

## What's included

- **Model**: nurse, shift, availability, and assignment concepts, the staffing constraints, two anchor solves, and an epsilon-constraint sweep between them — in the `model/` package (`schema.py` declares the concepts, `source.py` loads the sample data, `reasoning.py` states the decision problems), which `rai models deploy --path model` deploys to your Snowflake account, where each refresh runs every solve.
- **Query**: `queries/staffing_frontier.py`, which prints the report from the deployed model.
- **Runbook**: `runbook.md` — a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the model itself.
- **Sample data**: `data/nurses.csv` (nurse roster with skill levels, hourly costs, and overtime parameters), `data/shifts.csv` (shift definitions with timing, staffing requirements, and patient demand), and `data/availability.csv` (nurse-to-shift availability matrix).
- **Outputs**: the status and result of each solve, the efficient frontier of overtime cost against unmet demand, the marginal analysis with the knee, and the nurse assignments at the knee, printed to stdout.

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- The one-time model deployment setup on that account, done by an account administrator: follow [Set up model deployment](https://private.relational.ai/early-access/model-deploy-setup) through **Governed setup**, **PAT authentication**, and steps 1-2 of **Additional setup for the prescriptive reasoner** (the Quickstart covers this template's own schema). It gives you a model role, a programmatic access token (PAT) stored as a secret, an external access integration, a PAT user, and a warehouse.
- A Snowflake user that holds the model role.

### Tools
- Python 3.10 through 3.14 (the range relationalai 2.3.0 supports)

## Quickstart

Before you start, install Python 3.10 or later and complete the access prerequisites above: a Snowflake account with the RAI Native App, the one-time model deployment setup, and a Snowflake user that holds the model role.

Before the first deploy, create this template's internal schema as the model role, and have an administrator grant the RAI Native App caller access to it. The internal schema holds only this model's objects, so the grants cover all of it, including the solver's result tables that the deploy creates:

```sql
-- as the model role
CREATE SCHEMA IF NOT EXISTS <DB>.HOSPITAL_STAFFING_META;

-- as an administrator
GRANT CALLER USAGE ON DATABASE <DB> TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON SCHEMA <DB>.HOSPITAL_STAFFING_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON WAREHOUSE <PAT_WAREHOUSE> TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL TABLES IN SCHEMA <DB>.HOSPITAL_STAFFING_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL DYNAMIC TABLES IN SCHEMA <DB>.HOSPITAL_STAFFING_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL VIEWS IN SCHEMA <DB>.HOSPITAL_STAFFING_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER INSERT, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA <DB>.HOSPITAL_STAFFING_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER CREATE TABLE, CREATE STAGE ON SCHEMA <DB>.HOSPITAL_STAFFING_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER READ, WRITE ON ALL STAGES IN SCHEMA <DB>.HOSPITAL_STAFFING_META TO APPLICATION <RAI_APP_NAME>;
```

Use this sequence to deploy the model and query it:

1. **Download the template**

   [Download the ZIP](https://docs.relational.ai/templates/zips/v1/hospital_staffing.zip), unzip it, and enter the template directory:

   ```bash
   unzip hospital_staffing.zip
   cd hospital_staffing
   ```

2. **Create a Python environment**

   Create and activate a virtual environment, then update pip:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   ```

3. **Install the template**

   Install the dependencies pinned in `pyproject.toml`:

   ```bash
   python -m pip install .
   ```

4. **Configure your project**

   Use the configuration builder in [Install and run PyRel](https://docs.relational.ai/get-started/install-and-run-pyrel/#configure-your-project) to create `raiconfig.yaml` in the template directory and verify your connection.

   Set the connection `role` to the model role, then add the prescriptive reasoner and a `deployment` section. Give each template its own schema pair so two deployed templates never share one:

   ```yaml
   reasoners:
     prescriptive:
       name: hospital_staffing_solver            # created on first deploy if it doesn't exist
   deployment:
     role: <MODEL_ROLE>
     public_schema: <DB>.HOSPITAL_STAFFING               # published views and tables
     identity:
       internal_schema: <DB>.HOSPITAL_STAFFING_META      # solver inputs, results, refresh procedures
     schedules:
       standard:
         interval_s: 0              # refresh only on deploy or on demand
     schedule: standard
     pat_secret: <PAT_SECRET>       # these four come from the setup page
     pat_eai: <PAT_EAI>
     pat_user: <PAT_USER>
     pat_warehouse: <PAT_WAREHOUSE>
   ```

5. **Deploy the model**

   Deploy the model in `model/` to the schemas in `raiconfig.yaml`:

   ```bash
   rai models deploy --path model
   ```

   The deploy creates the public schema named in `raiconfig.yaml` if it doesn't exist and waits for the model's first refresh, which runs the solves: first the two anchors, then the five sweep points, whose unmet-demand caps are rules over the anchors' results. Each refresh of the deployed model runs them again.

   Deploying again without changing the model applies no updates and does not solve again. A change to the model or to `problem.configure(...)` redeploys, and the redeploy's refresh solves.

6. **Query the results**

   Print the report from the deployed model:

   ```bash
   python -m queries.staffing_frontier
   ```

   ```text
   ======================================================================
   ANCHOR SOLVE 1: Minimize overtime cost (no unmet demand constraint)
   ======================================================================
   Status: OPTIMAL
   Overtime cost: $0.00
   Unmet demand: 130.0 patients

   ======================================================================
   ANCHOR SOLVE 2: Minimize unmet demand (no overtime cost objective)
   ======================================================================
   Status: OPTIMAL
   Min unmet demand: 0.0 patients
   Overtime cost at best service: $2268.00

   Feasible unmet demand range: [0.0, 130.0]

   ======================================================================
   EPSILON SWEEP: 5 interior points
   Unmet demand targets: ['108.3', '86.7', '65.0', '43.3', '21.7']
   ======================================================================
     Point 1 (unmet<=108.3): overtime=$0.00, actual_unmet=108.3  [OPTIMAL]
     Point 2 (unmet<=86.7): overtime=$0.00, actual_unmet=86.7  [OPTIMAL]
     Point 3 (unmet<=65.0): overtime=$0.00, actual_unmet=65.0  [OPTIMAL]
     Point 4 (unmet<=43.3): overtime=$0.00, actual_unmet=43.3  [OPTIMAL]
     Point 5 (unmet<=21.7): overtime=$336.00, actual_unmet=21.7  [OPTIMAL]

   ======================================================================
   EFFICIENT FRONTIER: Overtime Cost vs Patient Service
   ======================================================================
     #          Label   Unmet Demand  Overtime Cost
   ------------------------------------------------
     1       cheapest          130.0 $         0.00
     2          eps_1          108.3 $         0.00
     3          eps_2           86.7 $         0.00
     4          eps_3           65.0 $         0.00
     5          eps_4           43.3 $         0.00
     6          eps_5           21.7 $       336.00
     7   best_service            0.0 $      2268.00

   Overtime Cost
   $ 2,268.00 |7                                                 |
              |                                                  |
              |                                                  |
              |                                                  |
              |                                                  |
              |                                                  |
              |                                                  |
              |                                                  |
              |                                                  |
              |                                                  |
              |        6                                         |
   $     0.00 |                5       4       3       2        1|
              +--------------------------------------------------+
               0                                              130 patients
                                  Unmet Demand

   Marginal analysis (cost of reducing unmet demand by 1 patient):
           cheapest → eps_1         : Δcost=$     +0.00, Δunmet= -21.7, marginal=$    0.00/patient
              eps_1 → eps_2         : Δcost=$     +0.00, Δunmet= -21.7, marginal=$    0.00/patient
              eps_2 → eps_3         : Δcost=$     +0.00, Δunmet= -21.7, marginal=$    0.00/patient
              eps_3 → eps_4         : Δcost=$     +0.00, Δunmet= -21.7, marginal=$    0.00/patient
              eps_4 → eps_5         : Δcost=$   +336.00, Δunmet= -21.7, marginal=$   15.51/patient
              eps_5 → best_service  : Δcost=$  +1932.00, Δunmet= -21.7, marginal=$   89.17/patient

     Knee: Point 5 (eps_4) -- marginal cost jumps 15.5x beyond this point
     Recommendation: Target 43 unmet patients at $0.00 overtime cost -- further service improvement costs significantly more per patient.

     Knee-point assignments:
       Afternoon: Nurse_C, Nurse_F
       Morning: Nurse_A, Nurse_D
       Night: Nurse_B, Nurse_E
   ```

   All seven solves are `OPTIMAL`. The frontier has a sharp knee at point 5: cutting unmet demand from 130 to 43 patients costs no overtime, the next 21.7 patients cost $15.51 each, and the last 21.7 cost $89.17 each ($2,268 in all at full service). See `runbook.md` for the step-by-step walkthrough.

   To solve again without changing the model, refresh the deployed model, then run the query again:

   ```sql
   CALL <DB>.HOSPITAL_STAFFING_META._INTERNAL_REFRESH_MODEL('standard', NULL);
   ```

7. **Tear down the deployment**

   Preview what the teardown removes, then remove it:

   ```bash
   rai models teardown
   rai models teardown --force
   ```

   The first command lists the model's objects without dropping anything; the second drops them and keeps the two schemas.

## Template structure

```text
.
├── README.md                  # this file
├── runbook.md                 # step-by-step analyst walkthrough
├── pyproject.toml             # dependencies
├── model/
│   ├── __init__.py            # exports of the deployed model
│   ├── schema.py              # concepts, properties, sweep and frontier points
│   ├── source.py              # sample data
│   └── reasoning.py           # anchor and sweep problems, published results
├── queries/
│   └── staffing_frontier.py   # report from the deployed model
└── data/
    ├── nurses.csv             # nurse roster
    ├── shifts.csv             # shift requirements and patient demand
    └── availability.csv       # nurse-to-shift availability
```

**Start here**: deploy with `rai models deploy --path model` and run `python -m queries.staffing_frontier` for the full anchor-solve, epsilon-sweep, and Pareto analysis end to end, or follow `runbook.md` to reproduce it step by step with the RAI skills.

## Sample data

The bundled data is small and illustrative — a single hospital day with a handful of nurses and shifts, sized so the whole epsilon sweep solves in seconds. It is designed to make the cost-service tradeoff visible, not to match a specific hospital's roster.

- **`nurses.csv`** — the nurse roster: skill level, hourly cost, regular-hour limit, and an overtime pay multiplier per nurse.
- **`shifts.csv`** — shift definitions: start hour, duration, minimum nurses, minimum skill, patient demand, and the patients each nurse-hour can serve.
- **`availability.csv`** — a nurse-to-shift availability matrix; `available = 1` means the nurse can work that shift.

## Model overview

The model is a small optimization ontology: two entities (nurses, shifts) linked by an availability matrix, with a per-availability assignment decision the solver fills in.

- **Key entities**: `Nurse` — a nurse with a skill level and cost parameters (the solver adds overtime hours); `Shift` — a shift with coverage requirements and patient demand (the solver adds patients-served and unmet-demand quantities); `Availability` — a nurse's eligibility for a shift; `Assignment` — the decision to staff a nurse on a shift, the MILP's decision space.
- **Primary identifiers**: `Nurse.id` and `Shift.id` (integers); `Availability` is keyed by the `(nurse_id, shift_id)` pair; `Assignment` is keyed by its `Availability`.
- **Important invariants**: overtime hours, patients served, and unmet demand are non-negative continuous quantities; each nurse works one to two shifts; every shift meets its minimum-nurse and minimum-skill floor; assignment decisions are binary.

For the full concept and property definitions, see `model/schema.py`; `runbook.md` builds them step by step with the RAI skills.

## How it works

**Define concepts and load CSV data.** The model defines three core concepts: nurses with skill levels and cost parameters, shifts with coverage requirements and patient demand, and an availability relationship linking nurses to shifts. A per-availability `Assignment` carries the binary staffing decision the solver fills in.

**Define decision variables, constraints, and objective.** A `staffing_problem` helper in `model/reasoning.py` declares one named Problem with the full formulation. It registers four variable types -- the binary assignment, each nurse's overtime hours, and each shift's patients-served and unmet-demand quantities -- and applies all constraints: availability, minimum staffing, skill coverage, overtime tracking, and patient-demand accounting (each nurse works one to two shifts; every shift meets its minimum-nurse floor). The original single-objective template bundled overtime cost and unmet demand into one weighted penalty sum, forcing the modeler to pick a penalty weight up front. The bi-objective version splits them: the primary objective minimizes overtime cost, while unmet demand is bounded by an epsilon constraint that caps total unmet demand across all shifts. This eliminates the arbitrary penalty weight and reveals the true tradeoff.

**Solve anchor points and run the epsilon sweep.** Two anchor solves establish the feasible unmet-demand range: anchor 1 minimizes overtime with no demand constraint (the cheapest schedule, which may leave patients unserved), and anchor 2 minimizes unmet demand (the best achievable service level). The epsilon sweep then traces interior points between the anchors, each solve minimizing overtime cost subject to a progressively tighter cap on unmet demand. Every solve is declared in the model: each sweep point's cap is a rule over the two anchors' results, so a refresh solves the anchors first and the sweep after them. Each solve publishes its status, overtime cost, unmet demand, and assignments as a `FrontierPoint`.

**Pareto analysis output.** The query prints the efficient frontier showing how overtime cost rises as the unmet-demand cap tightens. Marginal analysis computes the cost of reducing unmet demand by one patient, and a knee detector flags the point where that marginal cost jumps sharply -- recommending the best cost-service balance.

See `model/reasoning.py` for the implementation, and `runbook.md` for the skill-driven reproduction.

## Customize this template

Focus on the first changes most users will make.

### Use your own data

- Replace the CSVs in `data/` with your own roster, shifts, and availability; keep the column names listed in *Sample data* above.
- Ensure `availability.csv` only references valid nurse and shift IDs, and that available nurses provide enough coverage to meet each shift's `min_nurses` and `min_skill` requirements.
- Add more nurses or shifts simply by appending rows to the CSVs.

### Tune parameters

- **Frontier resolution** — increase `N_INTERIOR` in `model/reasoning.py` for a finer-grained Pareto frontier (more interior epsilon points between the two anchors).
- **Solve budget** — `time_limit_sec` on `problem.configure("highs", ...)` in `model/reasoning.py` caps each solve; raise it if larger rosters time out.

### Extend the model

- **Add shift preferences** by introducing a preference weight per nurse-shift pair and folding it into the objective.
- **Model consecutive-shift restrictions** by adding constraints that prevent nurses from working back-to-back shifts without rest.
- **Introduce part-time nurses** with different regular-hour limits and availability patterns.

### Scale up / productionize

- Swap the `read_csv(...)` loads for `model.data(snowflake_table)` calls to run against roster and demand tables maintained in Snowflake.
- Pin `relationalai` in `pyproject.toml` for reproducible solves, and set a refresh schedule in `raiconfig.yaml` to refresh the frontier as demand forecasts update.

## Troubleshooting

<details>
<summary>Solver returns INFEASIBLE</summary>

Check that nurse availability in `availability.csv` provides enough coverage to meet the minimum staffing requirements in `shifts.csv`. With the current data, each shift requires at least 2 nurses, so ensure enough nurses are available per shift.
</details>

<details>
<summary>High unmet demand in the solution</summary>

Tighten the epsilon constraint by reducing the unmet demand cap (or increase `N_INTERIOR` to explore finer gradations). If even the best-service anchor shows high unmet demand, the nurse roster may need more staff or broader availability.
</details>

<details>
<summary>Connection or authentication errors</summary>

Check the connection in `raiconfig.yaml` (Quickstart step 4). Verify that the RAI Native App is installed and your user holds the model role.
</details>

<details>
<summary>ModuleNotFoundError for relationalai</summary>

Ensure you activated the virtual environment and ran `python -m pip install .` to install all dependencies listed in `pyproject.toml`.
</details>

## Learn more

### Core concepts

- [Prescriptive reasoning](https://docs.relational.ai/) — the `Problem` API, decision variables, constraints, and objectives.
- [PyRel v1 modeling](https://docs.relational.ai/) — concepts, properties, and loading CSV data into relations.

### Modeling reference

- [Multi-objective optimization](https://docs.relational.ai/) — trading off competing objectives, including epsilon-constraint sweeps.

### Deeper dives

- [Sensitivity and marginal analysis](https://docs.relational.ai/) — reading shadow prices and marginal costs, as the Pareto knee detection does here.

## Support

- File issues at the RelationalAI templates repository.
