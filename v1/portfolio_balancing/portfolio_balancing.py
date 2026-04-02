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

# Lookup maps for Python-side objective evaluation
# (RAI `sum` is imported; solver only reports the primary objective)
stock_returns_map = dict(zip(returns_csv["index"], returns_csv["returns"]))
covar_map = {(int(r["i"]), int(r["j"])): r["covar"]
             for _, r in read_csv(data_dir / "covar.csv").iterrows()}

# Budget lookup — avoids fragile float(name.split("_")[1]) parsing
budget_map = {"budget_500": 500.0, "budget_1000": 1000.0, "budget_2000": 2000.0}


def _extract_allocations(var_df, scenario_name):
    """Extract {stock_index: quantity} for a scenario from variable_values df."""
    allocs = {}
    prefix = f"qty_{scenario_name}_"
    for _, row in var_df.iterrows():
        name = str(row.iloc[0])
        val = float(row.iloc[1])
        if name.startswith(prefix) and val > 1e-6:
            stock_idx = int(name.replace(prefix, ""))
            allocs[stock_idx] = val
    return allocs


def evaluate_return(var_df, scenario_name):
    """Evaluate portfolio return for a given scenario from variable_values df."""
    allocs = _extract_allocations(var_df, scenario_name)
    total = 0.0
    for idx, qty in allocs.items():
        total += stock_returns_map.get(idx, 0) * qty
    return total


def evaluate_risk(var_df, scenario_name):
    """Evaluate portfolio risk (variance) for a given scenario from variable_values df.
    The solver objective aggregates risk across ALL scenarios; this computes the
    per-scenario quadratic form x' * Cov * x."""
    allocs = _extract_allocations(var_df, scenario_name)
    if not allocs:
        return 0.0
    risk = 0.0
    for (i, j), cov in covar_map.items():
        qi = allocs.get(i, 0.0)
        qj = allocs.get(j, 0.0)
        risk += cov * qi * qj
    return risk


def solve_epsilon(eps_rate=None):
    """Solve risk minimization with optional return-rate constraint.

    eps_rate: if set, constrains return >= eps_rate * Scenario.budget per scenario.
              This scales the epsilon target with budget so all scenarios are
              handled in a single solve.
    Returns (solve_info, variable_values_df) or None if infeasible.
    """
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

    # EPSILON CONSTRAINT: return rate >= target rate (scaled by budget)
    # SINGLE-OBJECTIVE: this was a fixed threshold (Scenario.min_return)
    # BI-OBJECTIVE: this becomes a parameterized bound swept by the loop
    if eps_rate is not None:
        p.satisfy(model.where(
            Stock.x_quantity(Scenario, x_qty),
        ).require(
            sum(Stock.returns * x_qty).per(Scenario) >= eps_rate * Scenario.budget
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
    result1 = solve_epsilon(eps_rate=None)
    if result1 is None:
        raise SystemExit("Anchor solve 1 (min risk) is infeasible — check data and constraints.")
    si1, df1 = result1
    print(f"Status: {si1.termination_status}")

    anchor1_returns = {}
    anchor1_risks = {}
    for sn in scenario_names:
        ret = evaluate_return(df1, sn)
        risk = evaluate_risk(df1, sn)
        anchor1_returns[sn] = ret
        anchor1_risks[sn] = risk
        print(f"  {sn}: return = {ret:.4f}, risk = {risk:.6f}")

    print(f"\n{'=' * 70}")
    print("ANCHOR SOLVE 2: Maximize return (swap objective)")
    print("=" * 70)
    # One solve covers all scenarios — maximize aggregate return, then read per-scenario
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
    if si2.termination_status not in ("OPTIMAL", "LOCALLY_SOLVED"):
        raise SystemExit("Anchor solve 2 (max return) is infeasible — check data and constraints.")
    df2 = p2.variable_values().to_df()
    anchor2_returns = {}
    for sn in scenario_names:
        ret = evaluate_return(df2, sn)
        anchor2_returns[sn] = ret
    print(f"Status: {si2.termination_status}")
    for sn in scenario_names:
        print(f"  {sn}: return = {anchor2_returns[sn]:.4f}")

    # Return range as rate (per unit invested) — tightest across scenarios
    return_rate_min = min(anchor1_returns[sn] / budget_map[sn]
                         for sn in scenario_names)
    return_rate_max = max(anchor2_returns[sn] / budget_map[sn]
                         for sn in scenario_names)
    print(f"\nReturn rate range: [{return_rate_min:.4f}, {return_rate_max:.4f}] per unit invested")

    # --------------------------------------------------
    # Epsilon sweep — trace the efficient frontier
    # --------------------------------------------------

    n_interior = 5
    epsilon_rates = [
        return_rate_min + i * (return_rate_max - return_rate_min) / (n_interior + 1)
        for i in range(1, n_interior + 1)
    ]

    print(f"\n{'=' * 70}")
    print(f"EPSILON SWEEP: {n_interior} interior points")
    print(f"Return rates: {[f'{r:.4f}' for r in epsilon_rates]}")
    print(f"{'=' * 70}")

    # pareto[scenario_name] = [{"label", "return_target", "return_actual", "risk", "df"}, ...]
    pareto = {sn: [] for sn in scenario_names}

    # Add anchor 1 (min risk)
    for sn in scenario_names:
        pareto[sn].append({
            "label": "min_risk",
            "return_target": anchor1_returns[sn],
            "return_actual": anchor1_returns[sn],
            "risk": anchor1_risks[sn],
            "df": df1,
        })

    for i, rate in enumerate(epsilon_rates):
        result = solve_epsilon(eps_rate=rate)

        if result is None:
            print(f"  Point {i+1} (rate={rate:.4f}): INFEASIBLE — stopping sweep")
            break

        si, df = result
        for sn in scenario_names:
            budget = budget_map[sn]
            ret = evaluate_return(df, sn)
            risk = evaluate_risk(df, sn)
            pareto[sn].append({
                "label": f"eps_{i+1}",
                "return_target": rate * budget,
                "return_actual": ret,
                "risk": risk,
                "df": df,
            })

        print(f"  Point {i+1} (rate={rate:.4f}): {si.termination_status}")

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
        budget = budget_map[sn]
        print(f"\n  {sn} (budget={budget:.0f}):")
        print(f"  {'#':>3} {'Label':>10} {'Return':>10} {'Risk':>12}")
        print(f"  {'-' * 38}")
        for j, pt in enumerate(pts):
            print(f"  {j+1:>3} {pt['label']:>10} {pt['return_actual']:>10.2f} {pt['risk']:>12.4f}")

        # Marginal analysis
        if len(pts) >= 3:
            print("\n  Marginal analysis:")
            rates = []
            for j in range(len(pts) - 1):
                dr = pts[j+1]['risk'] - pts[j]['risk']
                dret = pts[j+1]['return_actual'] - pts[j]['return_actual']
                if abs(dret) > 1e-6:
                    rate_val = dr / dret
                    rates.append(rate_val)
                    print(f"    {pts[j]['label']:>10} -> {pts[j+1]['label']:<10}: "
                          f"delta_risk={dr:>+10.4f}, delta_return={dret:>+8.4f}, "
                          f"marginal={rate_val:>8.2f} risk/return")
                else:
                    rates.append(0)

            # Knee detection: find where marginal cost jumps most
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
                      f"-- marginal cost jumps {max_jump:.1f}x beyond this point")

                # Print allocations at the knee point
                knee_df = pts[knee_idx]["df"]
                knee_allocs = _extract_allocations(knee_df, sn)
                if knee_allocs:
                    print(f"\n    Knee-point allocations ({sn}):")
                    for idx in sorted(knee_allocs):
                        print(f"      Stock {idx}: {knee_allocs[idx]:.2f} units "
                              f"(return rate={stock_returns_map.get(idx, 0):.4f})")
