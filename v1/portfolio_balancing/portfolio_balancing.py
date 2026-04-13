"""Portfolio Balancing — multi-reasoner (rules + prescriptive) template.

This template demonstrates two reasoning stages chained in a single RAI model:

STAGE 1 — RULES-BASED COMPLIANCE ANALYSIS:
  Define compliance flags on existing portfolio data using derived properties
  and Relationships:
  - Overconcentrated holdings: position value > 15% of account balance
  - Sector concentration: sector exposure > 30% of account balance
  - High-risk traders: risk_score > 0.8 AND >5 flagged transactions

STAGE 2 — PRESCRIPTIVE (bi-objective optimization via epsilon constraint):
  Build new portfolios that minimize risk while maximizing return, subject to
  concentration constraints (position limit and sector limit). The epsilon
  constraint method sweeps return targets across the feasible range, producing
  the **efficient frontier** (full tradeoff curve between risk and return).

  The template also demonstrates **Scenario Concept inside the epsilon loop**:
  budget levels are modeled as a Scenario Concept, so each epsilon solve handles
  all budget scenarios simultaneously (N epsilon solves, not N x M).

Run:
    `python portfolio_balancing.py`

Output:
    Stage 1: prints compliance violations from rules analysis
    Stage 2: anchor solve results, per-epsilon-point Pareto frontier for each
    budget scenario, marginal analysis with knee detection, and allocation shifts.
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.std import aggregates as aggs

# --------------------------------------------------
# Config constants
# --------------------------------------------------

POSITION_LIMIT = 0.15   # max fraction of budget per stock
SECTOR_LIMIT = 0.30     # max fraction of budget per sector

DATA_DIR = Path(__file__).parent / "data"
returns_csv = read_csv(DATA_DIR / "returns.csv")
covar_csv = read_csv(DATA_DIR / "covar.csv")

# ==================================================================
# RAI Model — shared by rules (Stage 1) and optimization (Stage 2)
# ==================================================================

model = Model("portfolio")

# --------------------------------------------------
# Stock concept (used by both stages)
# --------------------------------------------------

Stock = model.Concept("Stock", identify_by={"index": Integer})
Stock.ticker = model.Property(f"{Stock} has ticker {String:stock_ticker}")
Stock.sector = model.Property(f"{Stock} has sector {String:stock_sector}")
Stock.returns = model.Property(f"{Stock} has {Float:returns}")
model.define(Stock.new(model.data(returns_csv).to_schema()))

Stock.covar = model.Property(f"{Stock} and {Stock} have {Float:covar}")
PairedStock = Stock.ref()
covar_data = model.data(covar_csv)
model.where(Stock.index(covar_data.i), PairedStock.index(covar_data.j)).define(
    Stock.covar(Stock, PairedStock, covar_data.covar)
)

# Sector concept — derived from Stock sectors for aggregation in rules.
Sector = model.Concept("Sector", identify_by={"sector_name": String})
model.define(Sector.new(sector_name=Stock.sector))
Stock.sector_ref = model.Property(f"{Stock} in {Sector}")
model.define(Stock.sector_ref(Sector)).where(Stock.sector == Sector.sector_name)

# --------------------------------------------------
# Compliance concepts (Stage 1 data)
# --------------------------------------------------

# User concept: portfolio users with risk scores.
User = model.Concept("User", identify_by={"user_id": Integer})
User.user_name = model.Property(f"{User} has name {String:user_name}")
User.risk_score = model.Property(f"{User} has risk score {Float:risk_score}")

user_data = model.data(read_csv(DATA_DIR / "users.csv"))
model.define(
    u := User.new(user_id=user_data["id"]),
    u.user_name(user_data["name"]),
    u.risk_score(user_data["risk_score"]),
)

# Account concept: brokerage/retirement accounts with balances.
Account = model.Concept("Account", identify_by={"account_id": Integer})
Account.user_id = model.Property(f"{Account} has user id {Integer:acct_user_id}")
Account.account_type = model.Property(f"{Account} has type {String:account_type}")
Account.balance = model.Property(f"{Account} has balance {Float:balance}")
Account.user = model.Property(f"{Account} belongs to {User}")

acct_data = model.data(read_csv(DATA_DIR / "accounts.csv"))
model.define(
    a := Account.new(account_id=acct_data["id"]),
    a.user_id(acct_data["user_id"]),
    a.account_type(acct_data["account_type"]),
    a.balance(acct_data["balance"]),
)
model.define(Account.user(User)).where(Account.user_id == User.user_id)

# Holding concept: stock positions in accounts.
Holding = model.Concept("Holding", identify_by={"holding_id": Integer})
Holding.account_id = model.Property(
    f"{Holding} has account id {Integer:holding_account_id}"
)
Holding.stock_id = model.Property(
    f"{Holding} has stock id {Integer:holding_stock_id}"
)
Holding.quantity = model.Property(f"{Holding} has quantity {Float:holding_quantity}")
Holding.purchase_price = model.Property(
    f"{Holding} has purchase price {Float:purchase_price}"
)
Holding.account = model.Property(f"{Holding} in {Account}")
Holding.stock = model.Property(f"{Holding} of {Stock}")

h_data = model.data(read_csv(DATA_DIR / "holdings.csv"))
model.define(
    h := Holding.new(holding_id=h_data["id"]),
    h.account_id(h_data["account_id"]),
    h.stock_id(h_data["stock_id"]),
    h.quantity(h_data["quantity"]),
    h.purchase_price(h_data["purchase_price"]),
)
model.define(Holding.account(Account)).where(
    Holding.account_id == Account.account_id
)
model.define(Holding.stock(Stock)).where(Holding.stock_id == Stock.index)

# Transaction concept: user transactions with flagged indicator.
Transaction = model.Concept("Transaction", identify_by={"transaction_id": Integer})
Transaction.user_id = model.Property(
    f"{Transaction} has user id {Integer:txn_user_id}"
)
Transaction.amount = model.Property(f"{Transaction} has amount {Float:txn_amount}")
Transaction.category = model.Property(
    f"{Transaction} has category {String:txn_category}"
)
Transaction.is_flagged_val = model.Property(
    f"{Transaction} flagged {Float:is_flagged_val}"
)
Transaction.user = model.Property(f"{Transaction} by {User}")

transactions_df = read_csv(DATA_DIR / "transactions.csv")
transactions_df["is_flagged_int"] = (
    transactions_df["is_flagged"]
    .astype(str)
    .str.lower()
    .map({"true": 1.0, "false": 0.0})
)
t_data = model.data(transactions_df)
model.define(
    t := Transaction.new(transaction_id=t_data["id"]),
    t.user_id(t_data["user_id"]),
    t.amount(t_data["amount"]),
    t.category(t_data["category"]),
    t.is_flagged_val(t_data["is_flagged_int"]),
)
model.define(Transaction.user(User)).where(Transaction.user_id == User.user_id)

# --------------------------------------------------
# Stage 1: Rules — compliance flags
# --------------------------------------------------

# Derived property: holding value = quantity * purchase_price.
Holding.value = model.Property(f"{Holding} has value {Float:holding_value}")
model.define(Holding.value(Holding.quantity * Holding.purchase_price))

# Rule 1: Overconcentrated holdings — position value > POSITION_LIMIT of balance.
Holding.is_overconcentrated = model.Relationship(f"{Holding} is overconcentrated")
AccountR1 = Account.ref()
model.where(
    Holding.account(AccountR1),
    Holding.value > POSITION_LIMIT * AccountR1.balance,
).define(Holding.is_overconcentrated())

# Rule 2: Sector concentration — total sector exposure > SECTOR_LIMIT of balance.
Holding.is_sector_concentrated = model.Relationship(
    f"{Holding} is in a concentrated sector position"
)
HoldingSC = Holding.ref()
StockSC = Stock.ref()
AccountSC = Account.ref()
SectorSC = Sector.ref()

sector_exposure = sum(HoldingSC.value).where(
    HoldingSC.account(AccountSC),
    HoldingSC.stock(StockSC),
    StockSC.sector_ref(SectorSC),
).per(AccountSC, SectorSC)

StockR2 = Stock.ref()
model.where(
    Holding.account(AccountSC),
    Holding.stock(StockR2),
    StockR2.sector_ref(SectorSC),
    sector_exposure > SECTOR_LIMIT * AccountSC.balance,
).define(Holding.is_sector_concentrated())

# Rule 3: High-risk traders — risk_score > 0.8 AND >5 flagged transactions.
User.is_high_risk_trader = model.Relationship(f"{User} is high risk trader")
TransactionHR = Transaction.ref()
flagged_count = sum(TransactionHR.is_flagged_val).where(
    TransactionHR.user(User),
).per(User)

model.where(
    User.risk_score > 0.8,
    flagged_count > 5,
).define(User.is_high_risk_trader())

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

# Sector constraint ref — defined at module level (outside solve_epsilon)
s_sector_ref = Stock.ref()

# Lookup maps for Python-side objective evaluation
stock_returns_map = dict(zip(returns_csv["index"], returns_csv["returns"]))
covar_map = {(int(r["i"]), int(r["j"])): r["covar"]
             for _, r in covar_csv.iterrows()}

# Budget lookup
budget_map = {"budget_500": 500.0, "budget_1000": 1000.0, "budget_2000": 2000.0}


def _extract_allocations(var_df, scenario_name):
    """Extract {stock_index: quantity} for a scenario from a structured allocation df."""
    allocs = {}
    rows = var_df[(var_df["scenario"] == scenario_name) & (var_df["quantity"] > 1e-6)]
    for _, row in rows.iterrows():
        allocs[int(row["stock_index"])] = row["quantity"]
    return allocs


def evaluate_return(var_df, scenario_name):
    """Evaluate portfolio return for a given scenario from a structured allocation df."""
    allocs = _extract_allocations(var_df, scenario_name)
    total = 0.0
    for idx, qty in allocs.items():
        total += stock_returns_map.get(idx, 0) * qty
    return total


def evaluate_risk(var_df, scenario_name):
    """Evaluate portfolio risk (variance) for a given scenario from a structured allocation df.
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


def _add_compliance_constraints(problem):
    """Add position limit and sector limit constraints to a Problem."""
    # Position limit: each stock allocation <= POSITION_LIMIT * budget
    problem.satisfy(model.where(
        Stock.x_quantity(Scenario, x_qty),
    ).require(x_qty <= POSITION_LIMIT * Scenario.budget))

    # Sector limit: total allocation to stocks in same sector <= SECTOR_LIMIT * budget
    sector_alloc = sum(x_qty).where(
        Stock.x_quantity(Scenario, x_qty),
        Stock.sector == s_sector_ref.sector,
    ).per(Scenario, s_sector_ref.sector)
    problem.satisfy(model.where(
        Stock.x_quantity(Scenario, x_qty),
    ).require(sector_alloc <= SECTOR_LIMIT * Scenario.budget))


def solve_epsilon(eps_rate=None):
    """Solve risk minimization with optional return-rate constraint.

    eps_rate: if set, constrains return >= eps_rate * Scenario.budget per scenario.
              This scales the epsilon target with budget so all scenarios are
              handled in a single solve.
    Returns (solve_info, allocation_df) or None if infeasible.
    """
    problem = Problem(model, Float)

    quantity_var = problem.solve_for(
        Stock.x_quantity(Scenario, x_qty),
        name=["qty", Scenario.name, Stock.index],
        populate=False,
    )

    # Non-negative
    problem.satisfy(model.where(
        Stock.x_quantity(Scenario, x_qty),
    ).require(x_qty >= 0))

    # Budget per scenario
    problem.satisfy(model.where(
        Stock.x_quantity(Scenario, x_qty),
    ).require(sum(x_qty).per(Scenario) <= Scenario.budget))

    # Fully invested per scenario
    problem.satisfy(model.where(
        Stock.x_quantity(Scenario, x_qty),
    ).require(sum(x_qty).per(Scenario) >= Scenario.budget))

    # Compliance constraints (position + sector limits)
    _add_compliance_constraints(problem)

    # EPSILON CONSTRAINT: return rate >= target rate (scaled by budget)
    if eps_rate is not None:
        problem.satisfy(model.where(
            Stock.x_quantity(Scenario, x_qty),
        ).require(
            sum(Stock.returns * x_qty).per(Scenario) >= eps_rate * Scenario.budget
        ))

    # Primary objective: minimize risk (quadratic via covariance matrix)
    problem.minimize(
        sum(covar_value * x_qty * x_qty_paired)
        .where(Stock.covar(PairedStock, covar_value),
               Stock.x_quantity(Scenario, x_qty),
               PairedStock.x_quantity(Scenario, x_qty_paired))
    )

    problem.solve("ipopt", time_limit_sec=60)
    si = problem.solve_info()

    if si.termination_status not in ("OPTIMAL", "LOCALLY_SOLVED"):
        return None

    value_ref = Float.ref()
    var_df = model.select(
        quantity_var.scenario.name.alias("scenario"),
        quantity_var.stock.index.alias("stock_index"),
        value_ref.alias("quantity"),
    ).where(quantity_var.values(0, value_ref)).to_df()

    return si, var_df


# --------------------------------------------------
# Main execution
# --------------------------------------------------

if __name__ == "__main__":

    # ==================================================
    # STAGE 1: Rules — Compliance Analysis
    # ==================================================

    print("=" * 70)
    print("STAGE 1: COMPLIANCE ANALYSIS (rules)")
    print("=" * 70)

    # ---- Rule 1: Overconcentrated Holdings ----
    StockQ1 = Stock.ref()
    AccountQ1 = Account.ref()
    overconc_df = (
        model.select(
            Holding.holding_id.alias("holding_id"),
            StockQ1.ticker.alias("ticker"),
            AccountQ1.account_id.alias("account_id"),
            Holding.value.alias("value"),
            AccountQ1.balance.alias("balance"),
        )
        .where(
            Holding.is_overconcentrated(),
            Holding.stock(StockQ1),
            Holding.account(AccountQ1),
        )
        .to_df()
    )

    print(
        f"\n--- Rule 1: Overconcentrated Holdings "
        f"(position > {POSITION_LIMIT:.0%} of balance) ---\n"
    )
    if overconc_df.empty:
        print("  No overconcentrated holdings found.")
    else:
        for _, row in overconc_df.iterrows():
            print(
                f"  holding_id={int(row['holding_id'])}, ticker={row['ticker']}, "
                f"account_id={int(row['account_id'])}, "
                f"value={row['value']:.2f}, balance={row['balance']:.2f}, "
                f"pct={row['value'] / row['balance']:.1%}"
            )

    # ---- Rule 2: Sector Concentration ----
    StockQ2 = Stock.ref()
    AccountQ2 = Account.ref()
    SectorQ2 = Sector.ref()
    HoldingQ2 = Holding.ref()

    sector_df = (
        model.select(
            AccountQ2.account_id.alias("account_id"),
            SectorQ2.sector_name.alias("sector"),
            aggs.sum(HoldingQ2.value).per(AccountQ2, SectorQ2).alias("sector_value"),
            AccountQ2.balance.alias("balance"),
        )
        .where(
            HoldingQ2.is_sector_concentrated(),
            HoldingQ2.account(AccountQ2),
            HoldingQ2.stock(StockQ2),
            StockQ2.sector_ref(SectorQ2),
        )
        .to_df()
        .drop_duplicates(subset=["account_id", "sector"])
    )

    print(
        f"\n--- Rule 2: Sector Concentration "
        f"(sector > {SECTOR_LIMIT:.0%} of balance) ---\n"
    )
    if sector_df.empty:
        print("  No sector concentration violations found.")
    else:
        for _, row in sector_df.iterrows():
            print(
                f"  account_id={int(row['account_id'])}, sector={row['sector']}, "
                f"sector_value={row['sector_value']:.2f}, "
                f"balance={row['balance']:.2f}, "
                f"pct={row['sector_value'] / row['balance']:.1%}"
            )

    # ---- Rule 3: High-Risk Traders ----
    high_risk_df = (
        model.select(
            User.user_id.alias("user_id"),
            User.user_name.alias("name"),
            User.risk_score.alias("risk_score"),
        )
        .where(User.is_high_risk_trader())
        .to_df()
    )

    print(
        "\n--- Rule 3: High Risk Traders "
        "(risk_score > 0.8 AND >5 flagged txns) ---\n"
    )
    if high_risk_df.empty:
        print("  No high-risk traders found.")
    else:
        for _, row in high_risk_df.iterrows():
            print(
                f"  user_id={int(row['user_id'])}, name={row['name']}, "
                f"risk_score={row['risk_score']:.2f}"
            )

    # ==================================================
    # STAGE 2: Bi-Objective Optimization
    # ==================================================

    scenario_names = ["budget_500", "budget_1000", "budget_2000"]

    print(f"\n{'=' * 70}")
    print("STAGE 2: BI-OBJECTIVE OPTIMIZATION (with compliance constraints)")
    print("=" * 70)

    print("\nANCHOR SOLVE 1: Minimize risk (no return constraint)")
    print("-" * 50)
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

    print("\nANCHOR SOLVE 2: Maximize return (swap objective)")
    print("-" * 50)
    # One solve covers all scenarios — maximize aggregate return, then read per-scenario
    p2 = Problem(model, Float)
    quantity_var2 = p2.solve_for(
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

    # Compliance constraints on anchor solve 2
    _add_compliance_constraints(p2)

    p2.maximize(
        sum(Stock.returns * x_qty).where(Stock.x_quantity(Scenario, x_qty))
    )
    p2.solve("ipopt", time_limit_sec=60)
    si2 = p2.solve_info()
    if si2.termination_status not in ("OPTIMAL", "LOCALLY_SOLVED"):
        raise SystemExit("Anchor solve 2 (max return) is infeasible — check data and constraints.")
    value_ref = Float.ref()
    df2 = model.select(
        quantity_var2.scenario.name.alias("scenario"),
        quantity_var2.stock.index.alias("stock_index"),
        value_ref.alias("quantity"),
    ).where(quantity_var2.values(0, value_ref)).to_df()
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

        # ASCII Pareto plot: Risk (y) vs Return (x)
        if len(pts) >= 2:
            plot_h, plot_w = 12, 50
            rets = [pt['return_actual'] for pt in pts]
            risks = [pt['risk'] for pt in pts]
            ret_min, ret_max = min(rets), max(rets)
            rsk_min, rsk_max = min(risks), max(risks)
            ret_range = ret_max - ret_min if ret_max > ret_min else 1
            rsk_range = rsk_max - rsk_min if rsk_max > rsk_min else 1
            grid = [[" "] * plot_w for _ in range(plot_h)]
            for k, pt in enumerate(pts):
                col = int((pt['return_actual'] - ret_min) / ret_range * (plot_w - 1))
                row = int((pt['risk'] - rsk_min) / rsk_range * (plot_h - 1))
                row = plot_h - 1 - row
                col = max(0, min(plot_w - 1, col))
                row = max(0, min(plot_h - 1, row))
                grid[row][col] = str(k + 1)
            print("\n  Risk")
            for i, row in enumerate(grid):
                if i == 0:
                    label = f"{rsk_max:>10.1f}"
                elif i == plot_h - 1:
                    label = f"{rsk_min:>10.1f}"
                else:
                    label = " " * 10
                print(f"  {label} |{''.join(row)}|")
            print(f"  {' ' * 10} +{'-' * plot_w}+")
            print(f"  {' ' * 10}  {ret_min:<.2f}{ret_max:>{plot_w - len(f'{ret_min:.2f}')}.2f}")
            print(f"  {' ' * 10}  {'Return':^{plot_w}}")

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
