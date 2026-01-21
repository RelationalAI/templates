# Diet Optimization

Select foods to satisfy daily nutritional requirements at minimum cost.

## Classification

| Dimension | Value |
|-----------|-------|
| **Reasoner** | Prescriptive |
| **Problem Type** | Allocation |
| **Industry** | Healthcare / Nutrition |
| **Method** | LP (Linear Programming) |
| **Complexity** | Beginner |

## What is this problem?

Meal planning services, hospitals, and institutional food services need to design menus that meet nutritional requirements without overspending. This template models selecting from 9 common foods (hamburger, chicken, hot dog, fries, macaroni, pizza, salad, milk, ice cream) to satisfy daily limits on calories, protein, fat, and sodium at minimum cost.

The classic "diet problem" was one of the first practical applications of linear programming, originally formulated by economist George Stigler in 1945.

## Why is optimization valuable?

- **Cost reduction**: Finds the cheapest food combination that meets all nutrition targets—manual planning often overspends or misses requirements
- **Compliance guarantee**: Mathematically ensures dietary guidelines are satisfied, eliminating guesswork and audit risk
- **Scalability**: Same approach works whether planning for 10 foods or 10,000 menu items across multiple facilities

## What are similar problems?

- **Animal feed formulation**: Minimize feed cost while meeting livestock nutritional requirements
- **Fertilizer blending**: Combine raw materials to achieve target soil nutrient levels at minimum cost
- **Pharmaceutical compounding**: Mix ingredients to meet drug specifications while minimizing production cost
- **Alloy mixing**: Blend metals to achieve target material properties at minimum cost

## Problem Details

### Model

**Concepts:**
- `Food`: Available food items with cost and nutritional content
- `Nutrient`: Nutritional requirements with min/max bounds
- `Contains`: Links foods to nutrients with quantity per serving

**Relationships:**
- `Contains` connects `Food` → `Nutrient` with quantity values

### Decision Variables

- `Food.amount` (continuous): Servings of each food to include

### Objective

Minimize total cost:
```
minimize sum(Food.cost * Food.amount)
```

### Constraints

1. **Nutrient bounds**: Total intake must be within min/max for each nutrient
2. **Non-negative**: Food amounts must be >= 0

## Data

Data files are located in the `data/` subdirectory.

### nutrients.csv

| Column | Description |
|--------|-------------|
| name | Nutrient name (calories, protein, fat, sodium) |
| min | Minimum daily requirement |
| max | Maximum daily allowance |

### foods.csv

| Column | Description |
|--------|-------------|
| name | Food name |
| cost | Cost per serving ($) |
| calories | Calories per serving |
| protein | Protein per serving (g) |
| fat | Fat per serving (g) |
| sodium | Sodium per serving (mg) |

## Usage

```python
from diet import solve, extract_solution

# Run optimization
solver_model = solve()
result = extract_solution(solver_model)

print(f"Status: {result['status']}")
print(f"Minimum cost: ${result['objective']:.2f}")
print(result['diet'])
```

Or run directly:

```bash
python diet.py
```

## Expected Output

```
Status: OPTIMAL
Minimum cost: $11.83

Optimal diet:
     name    amount
hamburger  0.604514
 icecream  2.591319
     milk  6.970139
```

The optimal diet minimizes cost while satisfying all nutritional constraints. Note that hotdog (1800mg sodium) is excluded because it exceeds the daily sodium limit (1779mg) in a single serving. The solution demonstrates how tight nutritional bounds naturally guide the optimizer toward feasible food combinations.
