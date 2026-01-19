# Code Implementation Outline - Open Questions

## Current State Analysis

### Style Spectrum Observed

| File | Lines | Style |
|------|-------|-------|
| `diet.py` (reference) | ~76 | Flat script, sectioned comments |
| `n_queens.py` | ~68 | Flat script, minimal |
| `portfolio.py` | ~86 | Flat script, parametrized loop |
| `supply_chain.py` | ~263 | Flat script, complex but no functions |
| `portfolio_optimization.py` | ~470 | Heavy structure, verbose docstrings, metadata dict |

### Tension

The instructions specify:
- **Code style**: "Minimal & functional - clean code in the style of `diet.py`"
- **Required functions**: `define_model()`, `define_problem()`, `solve()`, `extract_solution()`/`format_results()`

These are somewhat at odds. `diet.py` has no functions—it's a flat script.

---

## Open Questions

### Q1: How much function separation?

**Option A: Minimal functions (diet-inspired)**
```python
# Flat script with optional wrapper functions
# ~80-120 lines per template

def solve(config=None):
    """Run the complete optimization."""
    model = Model(...)

    # Define concepts/data
    Food = model.Concept("Food")
    data(csv).into(Food, ...)

    # Define variables
    Food.amount = model.Property(...)

    # Define constraints/objective
    total_cost = sum(Food.cost * Food.amount)
    constraint = require(...)

    # Solve
    s = SolverModel(model, "cont")
    s.solve_for(Food.amount, ...)
    s.minimize(total_cost)
    s.satisfy(constraint)

    solver = Solver("highs")
    s.solve(solver)

    # Return results
    return s.variable_values().to_df()

if __name__ == "__main__":
    print(solve())
```

**Option B: Separated functions (per instructions.md)**
```python
# Clear separation, ~150-200 lines per template

def define_model(config=None):
    """Define ontology/base model."""
    model = Model(...)
    Food = model.Concept("Food")
    data(csv).into(Food, ...)
    model.Food = Food  # Store for access
    return model

def define_problem(model):
    """Extend model with optimization problem."""
    Food = model.Food
    Food.amount = model.Property(...)

    s = SolverModel(model, "cont")
    s.solve_for(Food.amount, ...)
    s.minimize(sum(Food.cost * Food.amount))
    s.satisfy(require(...))
    return s

def solve(config=None):
    """Orchestrate model definition, problem setup, solver execution."""
    model = define_model(config)
    solver_model = define_problem(model)

    solver = Solver("highs")
    solver_model.solve(solver)
    return extract_solution(solver_model)

def extract_solution(solver_model):
    """Extract and format results."""
    df = solver_model.variable_values().to_df()
    # Format as needed
    return df

if __name__ == "__main__":
    result = solve()
    print(result)
```

**Option C: Hybrid (functions exist but inline-friendly)**
```python
# Functions defined but can also run as script
# ~100-150 lines per template

model = Model(...)

# === DEFINE MODEL ===
Food = model.Concept("Food")
data(csv).into(Food, ...)

# === DEFINE PROBLEM ===
Food.amount = model.Property(...)
total_cost = sum(Food.cost * Food.amount)
constraint = require(...)

# === SOLVE ===
def solve(solver_name="highs"):
    s = SolverModel(model, "cont")
    s.solve_for(Food.amount, ...)
    s.minimize(total_cost)
    s.satisfy(constraint)

    solver = Solver(solver_name)
    s.solve(solver)
    return s

def extract_solution(solver_model):
    return solver_model.variable_values().to_df()

if __name__ == "__main__":
    s = solve()
    print(extract_solution(s))
```

---

### Q2: What goes in `define_model()` vs `define_problem()`?

**Option A: Strict separation**
- `define_model()`: Only Concepts, Properties for data, data loading
- `define_problem()`: Decision variable properties, constraints, objectives, SolverModel setup

**Option B: Combined model+problem**
- Single function that does both (like diet.py style)
- Only separate the solve/execute step

---

### Q3: Return types and result format

**Option A: Return DataFrame directly**
```python
def solve():
    ...
    return s.variable_values().to_df()
```

**Option B: Return dict with metadata**
```python
def solve():
    ...
    return {
        "status": s.termination_status,
        "objective": s.objective_value,
        "variables": s.variable_values().to_df(),
    }
```

**Option C: Return solver_model for flexibility**
```python
def solve():
    ...
    return s  # User can call s.variable_values(), s.objective_value, etc.
```

---

### Q4: Docstrings and comments

**Option A: Minimal (diet.py style)**
- One-line comment at top explaining problem
- Section comments (`# --- Data ---`, `# --- Solve ---`)
- No docstrings

**Option B: Brief docstrings**
- One-line docstrings on main functions
- Section comments

**Option C: Moderate docstrings (per instructions.md "moderate depth")**
- Multi-line docstrings explaining Args/Returns
- But not as verbose as portfolio_optimization.py

---

### Q5: Error handling

**Option A: None (let exceptions propagate)**
- Clean, minimal
- User sees raw errors

**Option B: Basic status checks**
```python
if s.termination_status != "OPTIMAL":
    print(f"Warning: {s.termination_status}")
```

**Option C: Try/except with meaningful messages**
- More robust but more verbose

---

### Q6: Data loading pattern

**Option A: CSV next to Python file**
```python
csv = read_csv(Path(__file__).with_name("diet_nutrients.csv"))
```

**Option B: CSV in shared data/ folder**
```python
data_dir = Path(__file__).parent.parent / "data"
csv = read_csv(data_dir / "diet_nutrients.csv")
```

**Option C: Inline data for simple cases**
```python
# For small datasets, define inline
nutrients = [
    {"name": "calories", "min": 1800, "max": 2200},
    ...
]
```

---

## Recommendation

Based on "minimal & functional" guidance, I'd suggest:

| Question | Recommended |
|----------|-------------|
| Q1 | **Option B** - Separated functions (follows instructions.md structure) |
| Q2 | **Option A** - Strict separation (clearer teaching) |
| Q3 | **Option B** - Dict with metadata (useful but not over-engineered) |
| Q4 | **Option B** - Brief docstrings (one-liners) |
| Q5 | **Option B** - Basic status checks (minimal but informative) |
| Q6 | **Option A** - CSV next to Python file (self-contained templates) |

This yields ~120-180 lines per template, cleaner than `portfolio_optimization.py` (~470 lines) but more structured than `diet.py` (~76 lines).

---

## Proposed Template Structure

```python
"""
Problem Name

Brief description of what this optimization solves.
"""

from pathlib import Path
from time import time_ns
from pandas import read_csv
from relationalai.semantics import Model, data, require, sum
from relationalai.semantics.reasoners.optimization import Solver, SolverModel


def define_model(config=None):
    """Define the base model with concepts and data."""
    model = Model(f"problem_name_{time_ns()}", config=config, use_lqp=False)

    # Concepts
    Entity = model.Concept("Entity")

    # Load data
    csv = read_csv(Path(__file__).with_name("data.csv"))
    data(csv).into(Entity, keys=["id"])

    # Store for access
    model.Entity = Entity
    return model


def define_problem(model):
    """Define decision variables, constraints, and objective."""
    Entity = model.Entity

    # Decision variable
    Entity.amount = model.Property("{Entity} amount is {x:float}")

    # Constraints
    constraint = require(...)

    # Objective
    objective = sum(...)

    # Build solver model
    s = SolverModel(model, "cont")
    s.solve_for(Entity.amount, name=Entity.id, lower=0)
    s.minimize(objective)
    s.satisfy(constraint)

    return s


def solve(config=None, solver_name="highs"):
    """Run the complete optimization workflow."""
    model = define_model(config)
    solver_model = define_problem(model)

    solver = Solver(solver_name)
    solver_model.solve(solver, time_limit_sec=60)

    return {
        "status": solver_model.termination_status,
        "objective": solver_model.objective_value,
        "variables": solver_model.variable_values().to_df(),
    }


def format_results(result):
    """Format solution for display."""
    print(f"Status: {result['status']}")
    print(f"Objective: {result['objective']:.4f}")
    print(result["variables"].to_string(index=False))


if __name__ == "__main__":
    result = solve()
    format_results(result)
```

**Line count estimate: ~60-80 lines for simple problems, ~120-180 for complex**

---

## Decision Needed

Please confirm or adjust the recommendations above so we can finalize the template structure before generating files.
