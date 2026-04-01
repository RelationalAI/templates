"""Portfolio Balancing (prescriptive optimization) template.

This template demonstrates **multi-objective optimization** via epsilon constraint
in RelationalAI. The portfolio has two competing objectives:

- **Primary**: Minimize portfolio risk (variance via covariance matrix)
- **Secondary**: Maximize expected return

Instead of fixing a single return target, the epsilon constraint method sweeps
return targets across the feasible range, producing the **efficient frontier** —
the full tradeoff curve between risk and return. Each point on the frontier is a
valid portfolio; no point is strictly better than another.

The template also demonstrates **Scenario Concept inside the epsilon loop**:
budget levels are modeled as a Scenario Concept, so each epsilon solve handles
all budget scenarios simultaneously (N epsilon solves, not N × M).

TRANSFORMATION FROM SINGLE-OBJECTIVE:
  The original template had return as a constraint (>= threshold) with a fixed
  Scenario Concept sweeping return targets. The bi-objective version:
  1. Moves the return target from Scenario Concept to epsilon loop parameter
  2. Adds budget levels as the new Scenario Concept dimension
  3. Each epsilon solve: minimize risk .per(Scenario) s.t. return >= eps .per(Scenario)
  This exposes the full risk-return frontier at each budget level.

Run:
    `python portfolio_balancing.py`

Output:
    Prints anchor solve results, per-epsilon-point Pareto frontier for each budget
    scenario, marginal analysis with knee detection, and allocation shifts.
"""

import builtins
from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("portfolio")

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

Stock = model.Concept("Stock", identify_by={"index": Integer})
Stock.returns = model.Property(f"{Stock} has {Float:returns}")
returns_csv = read_csv(data_dir / "returns.csv")
model.define(Stock.new(model.data(returns_csv).to_schema()))

Stock.covar = model.Property(f"{Stock} and {Stock} have {Float:covar}")
PairedStock = Stock.ref()
covar_data = model.data(read_csv(data_dir / "covar.csv"))
model.where(Stock.index(covar_data.i), PairedStock.index(covar_data.j)).define(
    Stock.covar(Stock, PairedStock, covar_data.covar)
)

# --------------------------------------------------
# Scenario Concept — budget parameter variations
# (Scenarios handle parameter variations; epsilon loop handles the tradeoff)
# --------------------------------------------------

Scenario = model.Concept("Scenario", identify_by={"name": String})
Scenario.budget = model.Property(f"{Scenario} has {Float:budget}")
scenario_data = model.data(
    [("budget_500", 500), ("budget_1000", 1000), ("budget_2000", 2000)],
    columns=["name", "budget"],
)
model.define(Scenario.new(scenario_data.to_schema()))

# --------------------------------------------------
# Decision variable — indexed by Scenario
# --------------------------------------------------

Stock.x_quantity = model.Property(f"{Stock} in {Scenario} has {Float:quantity}")
x_qty = Float.ref()
covar_value = Float.ref()
x_qty_paired = Float.ref()

# Stock returns for Python-side secondary objective evaluation
# (RAI `sum` is imported; use builtins.sum for Python-side aggregation)
stock_returns_map = dict(zip(returns_csv["index"], returns_csv["returns"]))


def evaluate_return(var_df, scenario_name):
    """Evaluate portfolio return from variable_values df for a given scenario.
    Solver only reports the primary objective (risk). Must compute secondary
    (return) from the solution variables on the Python side."""
    total = 0.0
    prefix = f"qty_{scenario_name}_"
    for _, row in var_df.iterrows():
        name = str(row.iloc[0])
        val = float(row.iloc[1])
        if name.startswith(prefix) and val > 1e-6:
            stock_idx = int(name.replace(prefix, ""))
            total += stock_returns_map.get(stock_idx, 0) * val
    return total


def solve_epsilon(eps_value=None):
    """Solve risk minimization with optional return >= eps constraint.
    Returns (solve_info, variable_values_df) or None if infeasible."""
    p = Problem(model, Float)

    p.solve_for(
        Stock.x_quantity(Scenario, x_qty),
        name=["qty", Scenario.name, Stock.index],
        populate=False,
    )

    # Non-negative
    p.satisfy(model.where(
        Stock.x_quantity(Scenario, x_qty),
    ).require(x_qty >= 0))

    # Budget per scenario
    p.satisfy(model.where(
        Stock.x_quantity(Scenario, x_qty),
    ).require(sum(x_qty).per(Scenario) <= Scenario.budget))

    # Fully invested per scenario
    p.satisfy(model.where(
        Stock.x_quantity(Scenario, x_qty),
    ).require(sum(x_qty).per(Scenario) >= Scenario.budget))

    # EPSILON CONSTRAINT: return >= target per scenario
    # SINGLE-OBJECTIVE: this was a fixed threshold (Scenario.min_return)
    # BI-OBJECTIVE: this becomes a parameterized bound swept by the loop
    if eps_value is not None:
        p.satisfy(model.where(
            Stock.x_quantity(Scenario, x_qty),
        ).require(
            sum(Stock.returns * x_qty).per(Scenario) >= eps_value
        ))

    # Primary objective: minimize risk (quadratic via covariance matrix)
    p.minimize(
        sum(covar_value * x_qty * x_qty_paired)
        .where(Stock.covar(PairedStock, covar_value),
               Stock.x_quantity(Scenario, x_qty),
               PairedStock.x_quantity(Scenario, x_qty_paired))
    )

    p.solve("ipopt", time_limit_sec=60)
    si = p.solve_info()

    if si.termination_status not in ("OPTIMAL", "LOCALLY_SOLVED"):
        return None

    return si, p.variable_values().to_df()


# --------------------------------------------------
# Anchor solves — establish feasible return range
# --------------------------------------------------

if __name__ == "__main__":
    scenario_names = ["budget_500", "budget_1000", "budget_2000"]

    print("=" * 70)
    print("ANCHOR SOLVE 1: Minimize risk (no return constraint)")
    print("=" * 70)
    result1 = solve_epsilon(eps_value=None)
    si1, df1 = result1
    print(f"Status: {si1.termination_status}, total risk: {si1.objective_value:.6f}")

    # Compute return at min-risk portfolio for each scenario
    anchor1_returns = {}
    for sn in scenario_names:
        ret = evaluate_return(df1, sn)
        anchor1_returns[sn] = ret
        print(f"  {sn}: return = {ret:.4f}")

    print(f"\n{'=' * 70}")
    print("ANCHOR SOLVE 2: Maximize return (swap objective)")
    print("=" * 70)
    # For anchor 2, we solve max return separately per scenario
    # (can't mix minimize risk + maximize return in one Problem)
    anchor2_returns = {}
    for sn in scenario_names:
        p2 = Problem(model, Float)
        p2.solve_for(
            Stock.x_quantity(Scenario, x_qty),
            name=["qty", Scenario.name, Stock.index],
            populate=False,
        )
        p2.satisfy(model.where(
            Stock.x_quantity(Scenario, x_qty),
        ).require(x_qty >= 0))
        p2.satisfy(model.where(
            Stock.x_quantity(Scenario, x_qty),
        ).require(sum(x_qty).per(Scenario) <= Scenario.budget))
        p2.satisfy(model.where(
            Stock.x_quantity(Scenario, x_qty),
        ).require(sum(x_qty).per(Scenario) >= Scenario.budget))
        p2.maximize(
            sum(Stock.returns * x_qty).where(Stock.x_quantity(Scenario, x_qty))
        )
        p2.solve("ipopt", time_limit_sec=60)
        si2 = p2.solve_info()
        df2 = p2.variable_values().to_df()
        for sn2 in scenario_names:
            ret = evaluate_return(df2, sn2)
            anchor2_returns[sn2] = ret
        print(f"Status: {si2.termination_status}, max return: {si2.objective_value:.4f}")
        for sn2 in scenario_names:
            print(f"  {sn2}: return = {anchor2_returns[sn2]:.4f}")
        break  # one solve covers all scenarios

    # Return range: use the tightest across scenarios
    # (min-risk return varies by budget; max return = budget * max_stock_return)
    return_rate_min = min(anchor1_returns[sn] / float(sn.split("_")[1])
                         for sn in scenario_names)
    return_rate_max = max(anchor2_returns[sn] / float(sn.split("_")[1])
                         for sn in scenario_names)
    print(f"\nReturn rate range: [{return_rate_min:.4f}, {return_rate_max:.4f}] per unit invested")

    # --------------------------------------------------
    # Epsilon sweep — trace the efficient frontier
    # --------------------------------------------------

    n_interior = 5
    # Sweep return RATE (per unit invested) so epsilon scales with budget
    epsilon_rates = [
        return_rate_min + i * (return_rate_max - return_rate_min) / (n_interior + 1)
        for i in range(1, n_interior + 1)
    ]

    print(f"\n{'=' * 70}")
    print(f"EPSILON SWEEP: {n_interior} interior points")
    print(f"Return rates: {[f'{r:.4f}' for r in epsilon_rates]}")
    print(f"{'=' * 70}")

    # Collect all Pareto points per scenario
    # pareto[scenario_name] = [{"return_target", "return_actual", "risk", "alloc"}, ...]
    pareto = {sn: [] for sn in scenario_names}

    # Add anchor 1 (min risk)
    for sn in scenario_names:
        budget = float(sn.split("_")[1])
        pareto[sn].append({
            "label": "min_risk",
            "return_target": anchor1_returns[sn],
            "return_actual": anchor1_returns[sn],
            "risk": si1.objective_value,  # total across scenarios
        })

    for i, rate in enumerate(epsilon_rates):
        # Each scenario gets eps = rate * budget
        # But epsilon constraint is per-Scenario, and we pass a single scalar.
        # Since budgets differ, we use the rate * budget for the smallest budget
        # as a common floor. Actually — the constraint is per-Scenario and
        # sum(returns * x).per(Scenario) >= eps. With fully-invested constraint,
        # return = sum(returns * x) = budget * weighted_avg_return.
        # So eps = rate * Scenario.budget would need Scenario.budget in the expression.
        # Simpler: just use the rate as eps and scale by budget in the constraint.
        # Let's use a per-scenario epsilon via Scenario property.

        # Actually, simplest: set eps as a return RATE and constrain:
        # sum(returns * x).per(Scenario) >= rate * Scenario.budget
        p = Problem(model, Float)
        p.solve_for(
            Stock.x_quantity(Scenario, x_qty),
            name=["qty", Scenario.name, Stock.index],
            populate=False,
        )
        p.satisfy(model.where(
            Stock.x_quantity(Scenario, x_qty),
        ).require(x_qty >= 0))
        p.satisfy(model.where(
            Stock.x_quantity(Scenario, x_qty),
        ).require(sum(x_qty).per(Scenario) <= Scenario.budget))
        p.satisfy(model.where(
            Stock.x_quantity(Scenario, x_qty),
        ).require(sum(x_qty).per(Scenario) >= Scenario.budget))

        # Epsilon constraint: return rate >= target rate (scaled by budget)
        p.satisfy(model.where(
            Stock.x_quantity(Scenario, x_qty),
        ).require(
            sum(Stock.returns * x_qty).per(Scenario) >= rate * Scenario.budget
        ))

        p.minimize(
            sum(covar_value * x_qty * x_qty_paired)
            .where(Stock.covar(PairedStock, covar_value),
                   Stock.x_quantity(Scenario, x_qty),
                   PairedStock.x_quantity(Scenario, x_qty_paired))
        )

        p.solve("ipopt", time_limit_sec=60)
        si = p.solve_info()

        if si.termination_status not in ("OPTIMAL", "LOCALLY_SOLVED"):
            print(f"  Point {i+1} (rate={rate:.4f}): INFEASIBLE — stopping sweep")
            break

        df = p.variable_values().to_df()
        for sn in scenario_names:
            budget = float(sn.split("_")[1])
            ret = evaluate_return(df, sn)
            pareto[sn].append({
                "label": f"eps_{i+1}",
                "return_target": rate * budget,
                "return_actual": ret,
                "risk": si.objective_value,
            })

        print(f"  Point {i+1} (rate={rate:.4f}): {si.termination_status}, risk={si.objective_value:.4f}")

    # --------------------------------------------------
    # Pareto analysis — per scenario
    # --------------------------------------------------

    print(f"\n{'=' * 70}")
    print("EFFICIENT FRONTIER: Risk vs Return (per budget scenario)")
    print(f"{'=' * 70}")

    for sn in scenario_names:
        pts = pareto[sn]
        if len(pts) < 2:
            continue
        budget = float(sn.split("_")[1])
        print(f"\n  {sn} (budget={budget:.0f}):")
        print(f"  {'#':>3} {'Label':>10} {'Return':>10} {'Risk':>12}")
        print(f"  {'-' * 38}")
        for j, pt in enumerate(pts):
            print(f"  {j+1:>3} {pt['label']:>10} {pt['return_actual']:>10.2f} {pt['risk']:>12.4f}")

        # Marginal analysis
        if len(pts) >= 3:
            print(f"\n  Marginal analysis:")
            rates = []
            for j in range(len(pts) - 1):
                dr = pts[j+1]['risk'] - pts[j]['risk']
                dret = pts[j+1]['return_actual'] - pts[j]['return_actual']
                if abs(dret) > 1e-6:
                    rate_val = dr / dret
                    rates.append(rate_val)
                    print(f"    {pts[j]['label']:>10} → {pts[j+1]['label']:<10}: "
                          f"Δrisk={dr:>+10.4f}, Δreturn={dret:>+8.4f}, "
                          f"marginal={rate_val:>8.2f} risk/return")
                else:
                    rates.append(0)

            # Knee detection
            if len(rates) >= 2:
                max_jump = 0
                knee_idx = 1
                for j in range(len(rates) - 1):
                    if rates[j] > 1e-6:
                        jump = rates[j+1] / rates[j]
                    else:
                        jump = rates[j+1] if rates[j+1] > 0 else 0
                    if jump > max_jump:
                        max_jump = jump
                        knee_idx = j + 1
                print(f"\n    Knee: Point {knee_idx + 1} ({pts[knee_idx]['label']}) "
                      f"— marginal cost jumps {max_jump:.1f}x beyond this point")
