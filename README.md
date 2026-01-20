# RelationalAI Templates

A collection of templates demonstrating how to use RelationalAI's semantic modeling and reasoning capabilities. Templates are organized by **reasoner type**—specialized engines that answer different kinds of questions about your data.

## Reasoners

RelationalAI provides multiple reasoners, each designed for different analytical tasks:

| Reasoner | Purpose | Question Answered |
|----------|---------|-------------------|
| **Prescriptive** | Optimization & decision-making | "What should we do?" |
| *Predictive* | *Forecasting & classification* | *"What will happen?"* |
| *Descriptive* | *Pattern discovery & analytics* | *"What happened?"* |

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
| [markdown_optimization](./markdown_optimization/) | Pricing | Retail | MILP | Intermediate |
| [network_flow](./network_flow/) | Allocation | Supply Chain & Manufacturing | LP | Beginner |
| [order_fulfillment](./order_fulfillment/) | Allocation | Supply Chain & Manufacturing | MILP | Beginner |
| [portfolio_optimization](./portfolio_optimization/) | Allocation | Finance & Financial Services | QP | Intermediate |
| [production_planning](./production_planning/) | Allocation | Supply Chain & Manufacturing | MILP | Beginner |
| [shift_assignment](./shift_assignment/) | Allocation | Retail | CSP | Beginner |
| [supplier_reliability](./supplier_reliability/) | Allocation | Supply Chain & Manufacturing | LP | Beginner |
| [supply_chain_transport](./supply_chain_transport/) | Scheduling | Supply Chain & Manufacturing | MILP | Intermediate |
| [traveling_salesman](./traveling_salesman/) | Routing | Transportation | MILP | Intermediate |
| [vehicle_scheduling](./vehicle_scheduling/) | Scheduling | Transportation | MILP | Intermediate |
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

Each prescriptive template follows a consistent code pattern:

```python
"""Problem Name - Brief description."""

def define_model(config=None):
    """Define base model with concepts and data."""
    # Create model, load data, define concepts
    return model

def define_problem(model):
    """Define decision variables, constraints, and objective."""
    # Set up SolverModel with variables, constraints, objective
    return solver_model

def solve(config=None, solver_name="highs"):
    """Orchestrate model, problem, and solver execution."""
    model = define_model(config)
    solver_model = define_problem(model)
    solver = Solver(solver_name)
    solver_model.solve(solver, time_limit_sec=60)
    return solver_model

def extract_solution(solver_model):
    """Extract solution as dict with metadata."""
    return {
        "status": solver_model.termination_status,
        "objective": solver_model.objective_value,
        "variables": solver_model.variable_values().to_df(),
    }

if __name__ == "__main__":
    sm = solve()
    sol = extract_solution(sm)
    # Print results
```

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
| **Allocation** | How much/which resource goes where? | diet, portfolio_optimization, order_fulfillment |
| **Scheduling** | When does each activity occur? | machine_maintenance, vehicle_scheduling |
| **Routing** | What path through a network? | traveling_salesman |
| **Pricing** | What price/discount to set? | markdown_optimization |
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
| **HiGHS** | LP, MILP, QP | Included with RAI SDK |
| **MiniZinc** | CSP | Requires [separate installation](https://www.minizinc.org/software.html) |
| **Ipopt** | NLP | Requires [separate installation](https://coin-or.github.io/Ipopt/INSTALL.html) |

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
