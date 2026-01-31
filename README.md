# RelationalAI Templates

A collection of templates demonstrating how to use RelationalAI's semantic modeling and reasoning capabilities. Templates are organized by **reasoner type**—specialized engines that answer different kinds of questions about your data.

## Reasoners

RelationalAI provides multiple reasoners, each designed for different analytical tasks:

| Reasoner | Purpose | Question Answered |
|----------|---------|-------------------|
| **Prescriptive** | Optimization & decision-making | "What should we do?" |
| *Predictive* | *Forecasting & classification* | *"What will happen?"* |
| *Rules* | *Business logic & inference* | *"What follows from this?"* |
| *Graph* | *Relationship analysis & traversal* | *"How are things connected?"* |

*Italicized reasoners are planned for future templates.*

---

## Prescriptive Reasoner Templates

The Prescriptive Reasoner solves optimization problems: given constraints and objectives, it finds the best decision. Use it when you need to answer "What should we do?"

| Template | Problem Type | Sector | Method | Complexity |
|----------|--------------|--------|--------|------------|
| [ad_spend_allocation](./ad_spend_allocation/) | Allocation | Marketing & Revenue | MILP | Intermediate |
| [diet](./diet/) | Allocation | Healthcare | LP | Beginner |
| [factory_production](./factory_production/) | Allocation | Supply Chain & Manufacturing | LP | Beginner |
| [grid_interconnection](./grid_interconnection/) | Design | Energy & Utilities | MILP | Intermediate |
| [hospital_staffing](./hospital_staffing/) | Allocation | Healthcare | MILP | Intermediate |
| [inventory_rebalancing](./inventory_rebalancing/) | Allocation | Supply Chain & Manufacturing | LP | Beginner |
| [machine_maintenance](./machine_maintenance/) | Scheduling | Supply Chain & Manufacturing | MILP | Intermediate |
| [retail_markdown](./retail_markdown/) | Pricing | Retail | MILP | Intermediate |
| [network_flow](./network_flow/) | Allocation | Supply Chain & Manufacturing | LP | Beginner |
| [order_fulfillment](./order_fulfillment/) | Allocation | Supply Chain & Manufacturing | MILP | Beginner |
| [portfolio_balancing](./portfolio_balancing/) | Allocation | Finance & Financial Services | QP | Intermediate |
| [production_planning](./production_planning/) | Allocation | Supply Chain & Manufacturing | MILP | Beginner |
| [shift_assignment](./shift_assignment/) | Allocation | Retail | CSP | Beginner |
| [supplier_reliability](./supplier_reliability/) | Allocation | Supply Chain & Manufacturing | LP | Beginner |
| [supply_chain_transport](./supply_chain_transport/) | Scheduling | Supply Chain & Manufacturing | MILP | Intermediate |
| [traveling_salesman](./traveling_salesman/) | Routing | Transportation | MILP | Intermediate |
| [vehicle_scheduling](./vehicle_scheduling/) | Scheduling | Transportation | MILP | Intermediate |
| [test_data_generation](./test_data_generation/) | Design | Data Engineering | LP | Intermediate |
| [water_allocation](./water_allocation/) | Design | Energy & Utilities | LP | Beginner |

---

## Prerequisites

### Python Environment

- Python 3.10+
- RelationalAI v0.13+
- pandas

### RelationalAI SDK

```bash
pip install relationalai
```

### RAI Configuration

You need a valid RAI configuration. Set up your credentials:

```bash
rai init
```

Or configure programmatically by passing a `config` object to the templates.

---

## Using Prescriptive Templates

Each template is self-contained in its own folder with:
- `*.py` - Main Python file with entry point function
- `data/*.csv` - Sample data files
- `README.md` - Problem description, business context, and usage

### Quick Start

```python
# Example: Run the diet optimization
from diet.diet import solve, extract_solution

solver_model = solve()
result = extract_solution(solver_model)
print(f"Status: {result['status']}")
print(f"Optimal cost: {result['objective']:.2f}")
print(result['variables'])
```

Or run directly:

```bash
cd diet
python diet.py
```

### Using Snowflake Tables

The templates use CSV files by default, but can be adapted to use Snowflake tables as input and output.

#### Loading Data from Snowflake

Replace CSV loading with Snowflake table access:

```python
# Instead of:
# df = read_csv("data.csv")
# data(df).into(Concept, keys=["id"])

# Use Snowflake tables:
from relationalai.semantics import snowflake

# Load from Snowflake table
snowflake("DATABASE.SCHEMA.TABLE_NAME").into(Concept, keys=["id"])
```

#### Exporting Results to Snowflake

After solving, export the solution back to Snowflake:

```python
from relationalai.semantics import snowflake

# Get solution as DataFrame
result = extract_solution(solver_model)
solution_df = result['variables']

# Write to Snowflake table
snowflake("DATABASE.SCHEMA.RESULTS_TABLE").write(solution_df)
```

#### Full Snowflake Integration Example

```python
from relationalai.semantics import Model, snowflake
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

def solve_with_snowflake(config=None, solver_name="highs"):
    """Run optimization using Snowflake tables for input/output."""
    model = Model("my_optimization", config=config)

    # Define concepts
    Item = model.Concept("Item")
    Item.id = model.Property("{Item} has {id:int}")
    Item.value = model.Property("{Item} has {value:float}")

    # Load data from Snowflake
    snowflake("MY_DB.MY_SCHEMA.ITEMS").into(Item, keys=["id"])

    # Define and solve problem
    Item.selected = model.Property("{Item} is {selected:int}")
    s = SolverModel(model, "int")
    s.solve_for(Item.selected, type="bin", name=Item.id)
    s.maximize(sum(Item.selected * Item.value))

    solver = Solver(solver_name)
    s.solve(solver)

    # Export results to Snowflake
    results_df = s.variable_values().to_df()
    snowflake("MY_DB.MY_SCHEMA.OPTIMIZATION_RESULTS").write(results_df)

    return s
```

### Template Structure

Each prescriptive template follows a consistent 3-section structure:

```python
# problem name:
# brief description of what the optimization does

from pathlib import Path
from pandas import read_csv
from relationalai.semantics import Model, data, ...
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

model = Model("name", config=globals().get("config", None), use_lqp=False)

# --------------------------------------------------
# Define ontology & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Concept: description
Concept = model.Concept("Concept")
Concept.property = model.Property("{Concept} has {property:type}")
data(read_csv(data_dir / "file.csv")).into(Concept, keys=["key"])

# Relationship: description (joins multiple concepts)
Relationship = model.Concept("Relationship")
...

# --------------------------------------------------
# Model the problem
# --------------------------------------------------

# Decision concept: description (created to hold decision variables)
Decision = model.Concept("Decision")
...

# Parameters
param = value

s = SolverModel(model, "cont")

# Variable: description
s.solve_for(...)

# Constraint: description
s.satisfy(...)

# Objective: description
s.minimize(...) / s.maximize(...)

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

solver = Solver("highs")
s.solve(solver, time_limit_sec=60)

print(f"Status: {s.termination_status}")
print(f"Objective: {s.objective_value:.2f}")
# ... extract and display results
```

#### Section Details

**Section 1: Define ontology & load data** — *What EXISTS?*

This section describes the domain data model: the real-world entities, their attributes, and how they relate. Everything here is fixed input data that the optimizer cannot change.

| Element | Description |
|---------|-------------|
| **Concepts** | Domain entities (e.g., `Product`, `Warehouse`, `Customer`) |
| **Properties** | Data attributes on concepts (e.g., `Product.cost`, `Warehouse.capacity`) |
| **Relationships** | How concepts connect (e.g., `Order` links `Customer` to `Product`) |
| **Rules** | Derived facts or business logic computed from data |

**Section 2: Model the problem** — *What to DECIDE?*

This section formulates the optimization: what decisions the solver can make, what rules those decisions must follow, and what goal to optimize toward.

| Element | Description |
|---------|-------------|
| **Decision concepts** | New concepts created to hold decision variables (e.g., `Allocation`, `Assignment`) |
| **Parameters** | Constants and scalar values used in the formulation |
| **Variables** | `s.solve_for(...)` — quantities the solver determines |
| **Constraints** | `s.satisfy(...)` — rules decisions must obey |
| **Objective** | `s.minimize(...)` or `s.maximize(...)` — the goal |

**Section 3: Solve and check solution** — *Execute and extract*

This section runs the solver and inspects the results.

| Element | Description |
|---------|-------------|
| **Solver instantiation** | `Solver("highs")` — choose the solver backend |
| **Solve call** | `s.solve(solver, time_limit_sec=60)` — run optimization |
| **Result extraction** | Query decision variable values and display results |

#### Comment Prefixes

| Prefix | Section | Meaning |
|--------|---------|---------|
| `# Concept:` | Ontology | Base data entity with properties |
| `# Relationship:` | Ontology | Entity joining multiple concepts |
| `# Rule:` | Ontology | Derived fact or business logic |
| `# Decision concept:` | Problem | Concept created to hold decision variables |
| `# Parameters` | Problem | Constants and scalar values |
| `# Variable:` | Problem | `solve_for` declaration |
| `# Constraint:` | Problem | `s.satisfy` call |
| `# Objective:` | Problem | `s.minimize` or `s.maximize` call |

### Classification Schema

Each prescriptive template README includes classification metadata:

| Dimension | Description |
|-----------|-------------|
| **Reasoner** | Prescriptive (all templates) |
| **Problem Type** | Allocation, Scheduling, Routing, Pricing, Design |
| **Sector** | Healthcare, Finance & Financial Services, Supply Chain & Manufacturing, Retail, etc. |
| **Method** | LP, MILP, QP, CSP |
| **Complexity** | Beginner, Intermediate |

### Reference

#### Problem Types

| Type | Core Decision | Example Templates |
|------|---------------|-------------------|
| **Allocation** | How much/which resource goes where? | diet, portfolio_balancing, order_fulfillment |
| **Scheduling** | When does each activity occur? | machine_maintenance, vehicle_scheduling |
| **Routing** | What path through a network? | traveling_salesman |
| **Pricing** | What price/discount to set? | retail_markdown |
| **Design** | What infrastructure to build? | grid_interconnection, water_allocation |

#### Solution Methods

| Method | Variables | Best For |
|--------|-----------|----------|
| **LP** (Linear Programming) | Continuous | Proportional scaling, constant costs |
| **MILP** (Mixed-Integer LP) | Continuous + integer/binary | Yes/no decisions, indivisible units |
| **QP** (Quadratic Programming) | Continuous | Minimizing variance (e.g., portfolio risk) |
| **CSP** (Constraint Satisfaction) | Discrete | Feasibility problems, "all different" constraints |

#### Supported Solvers

| Solver | Methods | Notes |
|--------|---------|-------|
| **HiGHS** | LP, MILP, QP | Integrated with RAI SDK |
| **Ipopt** | NLP | Integrated with RAI SDK |
| **MiniZinc** | CSP | Integrated with RAI SDK |
| **Gurobi** | LP, MILP, QP | Integrated with RAI SDK; requires [separate license](https://www.gurobi.com/downloads/) |

#### Variable Types

| Type | Use When | Examples |
|------|----------|----------|
| **cont** | Divisible quantities | Rates, percentages, monetary amounts |
| **int** | Countable physical items | Units produced, trucks dispatched |
| **bin** | Yes/no decisions | Assign, select, open/close |

#### Common Constraint Patterns

| Pattern | Form | Use For |
|---------|------|---------|
| **Capacity** | `usage <= limit` | Resource limits, budget caps |
| **Requirement** | `supply >= demand` | Minimum service levels |
| **Balance** | `inflow == outflow` | Flow conservation, inventory |
| **Linking** | `x <= M * y` | Conditional activation (Big-M) |
| **Assignment** | `sum(x) == 1` | Exactly-one selection |

---

## Contributing

To add a new template:

1. Create a folder with a simple, descriptive name (e.g., `warehouse_location`)
2. Include the Python file following the standard structure
3. Add sample CSV data files in a `data/` subdirectory
4. Write a README.md with problem description and classification
5. Update this index

## License

[Add license information]
