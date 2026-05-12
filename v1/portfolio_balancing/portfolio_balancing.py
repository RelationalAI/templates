"""Portfolio Balancing -- multi-reasoner (rules + graph + prescriptive) template.

Four-stage pipeline on a single shared ontology:
- Stage 1 -- Rules: derived flags on existing portfolio data (overconcentrated
  holdings, sector concentration, high-risk traders).
- Stage 2 -- Graph: correlation graph over stocks + Louvain clustering,
  then per-cluster representative selection by highest Sharpe. Collapses
  redundant bets before the optimizer sees them.
- Stage 3 -- Prescriptive: bi-objective QP via epsilon constraint on the
  representative-only universe. Position and sector limits apply; non-reps
  are forced to zero. Budget x regime as Scenario Concept so all
  combinations solve in one call.
- Stage 4 -- Crisis stress: compare base vs crisis frontiers. Crisis
  covariance via PSD-preserving correlation shrinkage, derived in PyRel.

Volatility, correlation, and regime covariance are all PyRel derived
properties on Stock -- no numpy precomputation -- so the ontology is the
single source of truth for every solver input.

Run:
    python portfolio_balancing.py

Output:
    Stage 1: compliance violations.
    Stage 2: cluster count/sizes, intra- vs inter-cluster avg correlation.
    Stage 3: anchor solves, epsilon sweep, marginal analysis + knee.
    Stage 4: base-vs-crisis vol table per (budget, lambda).
"""

from pathlib import Path

from pandas import DataFrame, read_csv
from relationalai.semantics import Boolean, Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std.math import abs as math_abs
from relationalai.semantics.std.math import sqrt

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

POSITION_LIMIT = 0.15        # max fraction per stock in Stage 1 compliance rules
REP_POSITION_LIMIT = 0.30    # max fraction per representative in Stage 3 optimization
                             # (reps carry combined cluster exposure, so cap is higher;
                             # also required for feasibility: 5 reps x 0.20 = 1.00)
SECTOR_LIMIT = 0.30          # max fraction of budget per sector (both stages)
CORR_THRESHOLD = 0.3         # |correlation| >= threshold to create a graph edge (Stage 2)
CRISIS_ALPHA = 0.7           # shrinkage weight for base correlation in crisis regime (Stage 4)

DATA_DIR = Path(__file__).parent / "data"
returns_csv = read_csv(DATA_DIR / "returns.csv")
covar_csv = read_csv(DATA_DIR / "covar.csv")

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

model = Model("portfolio")

# --------------------------------------------------
# Stock concept (used by all stages)
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

# Sector concept -- derived from Stock sectors for aggregation in rules.
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
# Stage 1: Rules -- compliance flags
# --------------------------------------------------

# Derived property: holding value = quantity * purchase_price.
Holding.value = model.Property(f"{Holding} has value {Float:holding_value}")
model.define(Holding.value(Holding.quantity * Holding.purchase_price))

# Rule 1: Overconcentrated holdings -- position value > POSITION_LIMIT of balance.
Holding.is_overconcentrated = model.Relationship(f"{Holding} is overconcentrated")
AccountR1 = Account.ref()
model.where(
    Holding.account(AccountR1),
    Holding.value > POSITION_LIMIT * AccountR1.balance,
).define(Holding.is_overconcentrated())

# Rule 2: Sector concentration -- total sector exposure > SECTOR_LIMIT of balance.
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

# Rule 3: High-risk traders -- risk_score > 0.8 AND >5 flagged transactions.
User.is_high_risk_trader = model.Relationship(f"{User} is high risk trader")
TransactionHR = Transaction.ref()
flagged_count = sum(TransactionHR.is_flagged_val).where(
    TransactionHR.user(User),
).per(User)

model.where(
    User.risk_score > 0.8,
    flagged_count > 5,
).define(User.is_high_risk_trader())


# ==================================================
# STAGE 1: Rules -- Compliance Analysis
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


# --------------------------------------------------
# Stage 2: Graph -- covariance clustering
# --------------------------------------------------

# Derived per-stock variance (covar diagonal, i == j).
Stock.variance = model.Property(f"{Stock} has {Float:stock_variance}")
PairedStockVar = Stock.ref()
var_ref = Float.ref()
model.where(
    Stock.covar(PairedStockVar, var_ref),
    Stock.index == PairedStockVar.index,
).define(Stock.variance(var_ref))

# Derived per-stock volatility (sqrt of variance). Used downstream to derive
# correlation and the crisis regime covariance -- no numpy, no precompute.
Stock.volatility = model.Property(f"{Stock} has {Float:stock_volatility}")
model.define(Stock.volatility(sqrt(Stock.variance)))

# Derived pairwise correlation: corr(i, j) = covar(i, j) / (vol_i * vol_j).
# Stored as a two-argument property on Stock (keyed by the paired Stock).
Stock.correlation = model.Property(
    f"{Stock} and {Stock} have correlation {Float:stock_correlation}"
)
PairedStockCorr = Stock.ref()
cov_ij_ref = Float.ref()
model.where(
    Stock.covar(PairedStockCorr, cov_ij_ref),
).define(
    Stock.correlation(
        PairedStockCorr,
        cov_ij_ref / (Stock.volatility * PairedStockCorr.volatility),
    )
)

# Build the undirected correlation graph. Nodes are Stocks; edges link stocks
# with |correlation| >= CORR_THRESHOLD. Correlations are filtered in PyRel
# against the derived Stock.correlation property.
corr_graph = Graph(
    model,
    directed=False,
    weighted=False,
    node_concept=Stock,
    aggregator="sum",
)

stock_i_ref = Stock.ref()
stock_j_ref = Stock.ref()
corr_ref = Float.ref()
model.define(corr_graph.Edge.new(src=stock_i_ref, dst=stock_j_ref)).where(
    stock_i_ref.correlation(stock_j_ref, corr_ref),
    stock_i_ref.index < stock_j_ref.index,
    math_abs(corr_ref) >= CORR_THRESHOLD,
)

# Louvain community detection -- stored as Stock.cluster (integer id).
community = corr_graph.louvain()
cluster_label = Integer.ref("cluster_label")
Stock.cluster = model.Property(f"{Stock} in cluster {Integer:cluster_id}")
stock_clust_ref = Stock.ref()
model.define(stock_clust_ref.cluster(cluster_label)).where(
    community(stock_clust_ref, cluster_label)
)

# Representative selection: for each cluster, the single stock with the
# highest Sharpe (return / volatility) is the cluster representative. If
# several stocks co-move strongly they carry near-identical exposure --
# prefer the best risk-adjusted one and drop the rest from the investable
# universe. This collapses redundant bets instead of merely capping them.
Stock.sharpe = model.Property(f"{Stock} has Sharpe {Float:stock_sharpe}")
model.define(Stock.sharpe(Stock.returns / Stock.volatility))

# Per-cluster maximum Sharpe, written back onto each Stock.
peer_for_max = Stock.ref()
Stock.cluster_max_sharpe = model.Property(
    f"{Stock} has cluster max Sharpe {Float:cluster_max_sharpe}"
)
model.define(
    Stock.cluster_max_sharpe(
        aggs.max(peer_for_max.sharpe)
        .where(peer_for_max.cluster == Stock.cluster)
        .per(Stock)
    )
)

# Representative Relationship: stock whose Sharpe equals its cluster's max.
Stock.is_representative = model.Relationship(f"{Stock} is cluster representative")
model.where(Stock.sharpe == Stock.cluster_max_sharpe).define(
    Stock.is_representative()
)

# Complementary Relationship used positively in solver constraints
# (the prescriptive rewriter doesn't accept `model.not_(...)` in a .where()).
Stock.is_non_representative = model.Relationship(f"{Stock} is not cluster representative")
model.where(Stock.sharpe < Stock.cluster_max_sharpe).define(
    Stock.is_non_representative()
)


# ==================================================
# STAGE 2: Graph -- Covariance Clustering
# ==================================================

print(f"\n{'=' * 70}")
print("STAGE 2: GRAPH -- Covariance Clustering (Louvain)")
print("=" * 70)

StockQ3 = Stock.ref()
cluster_df = (
    model.select(
        StockQ3.index.alias("stock_index"),
        StockQ3.ticker.alias("ticker"),
        StockQ3.sector.alias("sector"),
        StockQ3.cluster.alias("cluster_id"),
    )
    .to_df()
)
cluster_df["cluster_id"] = cluster_df["cluster_id"].astype(int)
num_clusters = cluster_df["cluster_id"].nunique()

# Query the derived correlation property for stats and edge count.
StockCQ = Stock.ref()
PairedCQ = Stock.ref()
corr_q_ref = Float.ref()
corr_df = (
    model.select(
        StockCQ.index.alias("i"),
        PairedCQ.index.alias("j"),
        corr_q_ref.alias("correlation"),
    )
    .where(StockCQ.correlation(PairedCQ, corr_q_ref))
    .to_df()
)
corr_df["i"] = corr_df["i"].astype(int)
corr_df["j"] = corr_df["j"].astype(int)
corr_df["correlation"] = corr_df["correlation"].astype(float)
# Upper triangle only (i < j) -- correlation is symmetric.
upper_corr = corr_df[corr_df["i"] < corr_df["j"]].copy()
num_edges = int((upper_corr["correlation"].abs() >= CORR_THRESHOLD).sum())

print(
    f"\n  Correlation graph: {num_edges} edges "
    f"(|correlation| >= {CORR_THRESHOLD})"
)
print(f"  Louvain communities: {num_clusters} cluster(s)")
for cid, group in cluster_df.sort_values("cluster_id").groupby("cluster_id"):
    members = ", ".join(
        f"{row['ticker']} ({row['sector']})"
        for _, row in group.iterrows()
    )
    print(f"    Cluster {cid} (size {len(group)}): {members}")

# Intra- vs inter-cluster average correlation (from the derived property).
# Built with pandas because `sum` is shadowed by the PyRel aggregator import.
cluster_map = dict(zip(cluster_df["stock_index"], cluster_df["cluster_id"]))
is_intra = upper_corr.apply(
    lambda r: cluster_map.get(int(r["i"])) == cluster_map.get(int(r["j"])), axis=1
)
intra_series = upper_corr.loc[is_intra, "correlation"]
inter_series = upper_corr.loc[~is_intra, "correlation"]
intra_avg = float(intra_series.mean()) if len(intra_series) else 0.0
inter_avg = float(inter_series.mean()) if len(inter_series) else 0.0
print(
    f"\n  Avg correlation: intra-cluster = {intra_avg:+.3f}, "
    f"inter-cluster = {inter_avg:+.3f}"
)

# Cluster representatives -- the investable universe after redundancy removal.
RepStock = Stock.ref()
rep_df = (
    model.select(
        RepStock.cluster.alias("cluster_id"),
        RepStock.ticker.alias("ticker"),
        RepStock.sector.alias("sector"),
        RepStock.sharpe.alias("sharpe"),
    )
    .where(RepStock.is_representative())
    .to_df()
    .sort_values("cluster_id")
)
print(
    f"\n  Cluster representatives ({len(rep_df)} of {len(cluster_df)} stocks, "
    f"picked by highest Sharpe):"
)
for _, row in rep_df.iterrows():
    print(
        f"    Cluster {int(row['cluster_id'])}: {row['ticker']} "
        f"({row['sector']}) -- Sharpe = {float(row['sharpe']):.3f}"
    )


# --------------------------------------------------
# Stage 3: Prescriptive -- bi-objective QP with epsilon constraint
# (Scenarios encode budget x regime; epsilon loop traces the frontier.
# Stage 4's crisis regime reuses this stage's solver via the crisis_* scenarios.)
# --------------------------------------------------

# Regime concept -- two instances ("base", "crisis") feed regime-conditioned covariance.
Regime = model.Concept("Regime", identify_by={"regime_name": String})
model.define(Regime.new(regime_name="base"))
model.define(Regime.new(regime_name="crisis"))

Scenario = model.Concept("Scenario", identify_by={"name": String})
Scenario.budget = model.Property(f"{Scenario} has {Float:budget}")
Scenario.regime = model.Property(f"{Scenario} in {Regime}")
scenario_data = model.data(
    [
        ("base_500", 500, "base"),
        ("base_1000", 1000, "base"),
        ("base_2000", 2000, "base"),
        ("crisis_500", 500, "crisis"),
        ("crisis_1000", 1000, "crisis"),
        ("crisis_2000", 2000, "crisis"),
    ],
    columns=["name", "budget", "regime"],
)
model.define(
    s := Scenario.new(name=scenario_data["name"]),
    s.budget(scenario_data["budget"]),
)
# Link Scenario to Regime by matching the regime name from the data.
scenario_link_ref = Scenario.ref()
regime_link_ref = Regime.ref()
model.where(
    scenario_link_ref.name == scenario_data["name"],
    regime_link_ref.regime_name == scenario_data["regime"],
).define(scenario_link_ref.regime(regime_link_ref))

# Regime-conditioned covariance is derived in PyRel from the base covariance
# and the derived volatilities:
#   base:   Sigma(i, j)
#   crisis: alpha * Sigma(i, j) + (1 - alpha) * vol_i * vol_j
# The crisis formula is equivalent to correlation shrinkage toward all-ones
# (rho_crisis = alpha * rho + (1 - alpha) * J) re-expressed in covariance
# units. PSD is preserved because the construction is a convex combination of
# PSD matrices.
Stock.regime_covar = model.Property(
    f"{Stock} and {Stock} in {Regime} have {Float:regime_covar}"
)

# Base regime: covariance unchanged.
PairedStockBase = Stock.ref()
base_cov_ref = Float.ref()
base_regime_ref = Regime.ref()
model.where(
    Stock.covar(PairedStockBase, base_cov_ref),
    base_regime_ref.regime_name == "base",
).define(Stock.regime_covar(PairedStockBase, base_regime_ref, base_cov_ref))

# Crisis regime: convex combination of base covariance and vol_i * vol_j.
PairedStockCrisis = Stock.ref()
crisis_cov_ref = Float.ref()
crisis_regime_ref = Regime.ref()
model.where(
    Stock.covar(PairedStockCrisis, crisis_cov_ref),
    crisis_regime_ref.regime_name == "crisis",
).define(
    Stock.regime_covar(
        PairedStockCrisis,
        crisis_regime_ref,
        CRISIS_ALPHA * crisis_cov_ref
        + (1 - CRISIS_ALPHA) * Stock.volatility * PairedStockCrisis.volatility,
    )
)

# --------------------------------------------------
# Decision variable -- indexed by Scenario
# --------------------------------------------------

Stock.x_quantity = model.Property(f"{Stock} in {Scenario} has {Float:quantity}")
x_qty = Float.ref()
x_qty_paired = Float.ref()
regime_cov_val = Float.ref()

# Sector constraint ref -- defined at module level.
s_sector_ref = Stock.ref()

# Python-side lookup maps for per-scenario evaluation (post-solve analysis).
# stock_returns_map is fine to build from the returns CSV since it's the raw
# data. covar_map and scenario_meta are hydrated from the ontology (so the
# derived crisis covariance comes from PyRel, not numpy).
stock_returns_map = dict(zip(returns_csv["index"], returns_csv["returns"]))
_covar_map_cache: dict | None = None
_scenario_meta_cache: dict | None = None


def _load_covar_map():
    """Query the ontology for Stock.regime_covar and cache as a dict."""
    global _covar_map_cache
    if _covar_map_cache is not None:
        return _covar_map_cache
    s_i = Stock.ref()
    s_j = Stock.ref()
    reg = Regime.ref()
    cov = Float.ref()
    df = (
        model.select(
            reg.regime_name.alias("regime"),
            s_i.index.alias("i"),
            s_j.index.alias("j"),
            cov.alias("regime_covar"),
        )
        .where(s_i.regime_covar(s_j, reg, cov))
        .to_df()
    )
    _covar_map_cache = {
        (row["regime"], int(row["i"]), int(row["j"])): float(row["regime_covar"])
        for _, row in df.iterrows()
    }
    return _covar_map_cache


def _load_scenario_meta():
    """Query the ontology for Scenario budget and regime and cache as a dict."""
    global _scenario_meta_cache
    if _scenario_meta_cache is not None:
        return _scenario_meta_cache
    sc = Scenario.ref()
    rg = Regime.ref()
    df = (
        model.select(
            sc.name.alias("name"),
            sc.budget.alias("budget"),
            rg.regime_name.alias("regime"),
        )
        .where(sc.regime(rg))
        .to_df()
    )
    _scenario_meta_cache = {
        row["name"]: {"budget": float(row["budget"]), "regime": row["regime"]}
        for _, row in df.iterrows()
    }
    return _scenario_meta_cache


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
    """Evaluate portfolio risk (variance) under the scenario's regime covariance."""
    allocs = _extract_allocations(var_df, scenario_name)
    if not allocs:
        return 0.0
    meta = _load_scenario_meta()
    covar_map = _load_covar_map()
    regime = meta[scenario_name]["regime"]
    risk = 0.0
    for (reg, i, j), cov in covar_map.items():
        if reg != regime:
            continue
        qi = allocs.get(i, 0.0)
        qj = allocs.get(j, 0.0)
        risk += cov * qi * qj
    return risk


def _add_compliance_constraints(problem):
    """Add position, sector, and representative-only constraints to a Problem."""
    # Position limit: each representative allocation <= REP_POSITION_LIMIT * budget.
    # This is higher than Stage 1's POSITION_LIMIT because a representative
    # carries its whole cluster's exposure (the cluster's other members are
    # forced to zero below).
    problem.satisfy(model.where(
        Stock.x_quantity(Scenario, x_qty),
    ).require(x_qty <= REP_POSITION_LIMIT * Scenario.budget))

    # Sector limit: total allocation to stocks in same sector <= SECTOR_LIMIT * budget.
    sector_alloc = sum(x_qty).where(
        Stock.x_quantity(Scenario, x_qty),
        Stock.sector == s_sector_ref.sector,
    ).per(Scenario, s_sector_ref.sector)
    problem.satisfy(model.where(
        Stock.x_quantity(Scenario, x_qty),
    ).require(sector_alloc <= SECTOR_LIMIT * Scenario.budget))

    # Representative-only: non-representative stocks are forced to zero.
    # The cluster's representative (highest Sharpe, picked in Stage 2) is
    # the sole carrier of its exposure in the portfolio. This collapses
    # redundant bets rather than capping within a redundant set.
    problem.satisfy(model.where(
        Stock.x_quantity(Scenario, x_qty),
        Stock.is_non_representative(),
    ).require(x_qty == 0))


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

    # Compliance constraints (position + sector limits; non-reps forced to 0)
    _add_compliance_constraints(problem)

    # EPSILON CONSTRAINT: return rate >= target rate (scaled by budget)
    if eps_rate is not None:
        problem.satisfy(model.where(
            Stock.x_quantity(Scenario, x_qty),
        ).require(
            sum(Stock.returns * x_qty).per(Scenario) >= eps_rate * Scenario.budget
        ))

    # Primary objective: minimize risk (quadratic via regime-conditioned covariance).
    # Each Scenario picks its matching regime covariance, so base and crisis
    # scenarios solve against different covariances in the same call.
    problem.minimize(
        sum(regime_cov_val * x_qty * x_qty_paired)
        .where(
            Stock.regime_covar(PairedStock, Scenario.regime, regime_cov_val),
            Stock.x_quantity(Scenario, x_qty),
            PairedStock.x_quantity(Scenario, x_qty_paired),
        )
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


# Hydrate scenario metadata from the ontology for post-solve evaluation.
scenario_meta = _load_scenario_meta()

# ==================================================
# STAGE 3: Bi-Objective Optimization (base + crisis)
# ==================================================

scenario_names = [
    "base_500", "base_1000", "base_2000",
    "crisis_500", "crisis_1000", "crisis_2000",
]
budgets = [500, 1000, 2000]

print(f"\n{'=' * 70}")
print("STAGE 3: BI-OBJECTIVE OPTIMIZATION")
print("(position + sector limits on representative universe; base & crisis regimes)")
print("=" * 70)

print("\nANCHOR SOLVE 1: Minimize risk (no return constraint)")
print("-" * 50)
result1 = solve_epsilon(eps_rate=None)
if result1 is None:
    raise SystemExit(
        "Anchor solve 1 (min risk) is infeasible -- check data and constraints."
    )
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
# One solve covers all scenarios -- maximize aggregate return, then read per-scenario.
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

_add_compliance_constraints(p2)

p2.maximize(
    sum(Stock.returns * x_qty).where(Stock.x_quantity(Scenario, x_qty))
)
p2.solve("ipopt", time_limit_sec=60)
si2 = p2.solve_info()
if si2.termination_status not in ("OPTIMAL", "LOCALLY_SOLVED"):
    raise SystemExit(
        "Anchor solve 2 (max return) is infeasible -- check data and constraints."
    )
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

# Return range as rate (per unit invested) -- tightest across scenarios.
# Return rates don't depend on regime (Stock.returns is regime-independent),
# so base and crisis scenarios at the same budget yield identical rates.
return_rate_min = min(
    anchor1_returns[sn] / scenario_meta[sn]["budget"] for sn in scenario_names
)
return_rate_max = max(
    anchor2_returns[sn] / scenario_meta[sn]["budget"] for sn in scenario_names
)
print(
    f"\nReturn rate range: [{return_rate_min:.4f}, {return_rate_max:.4f}] "
    "per unit invested"
)

# --------------------------------------------------
# Epsilon sweep -- trace the efficient frontier
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

pareto = {sn: [] for sn in scenario_names}

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
        print(f"  Point {i+1} (rate={rate:.4f}): INFEASIBLE -- stopping sweep")
        break
    si, df = result
    for sn in scenario_names:
        budget = scenario_meta[sn]["budget"]
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
# Pareto analysis -- per scenario
# --------------------------------------------------

print(f"\n{'=' * 70}")
print("EFFICIENT FRONTIER: Risk vs Return (per scenario)")
print(f"{'=' * 70}")

for sn in scenario_names:
    pts = pareto[sn]
    if len(pts) < 2:
        continue
    meta = scenario_meta[sn]
    print(f"\n  {sn} (budget={meta['budget']:.0f}, regime={meta['regime']}):")
    print(f"  {'#':>3} {'Label':>10} {'Return':>10} {'Risk':>12}")
    print(f"  {'-' * 38}")
    for j, pt in enumerate(pts):
        print(
            f"  {j+1:>3} {pt['label']:>10} "
            f"{pt['return_actual']:>10.2f} {pt['risk']:>12.4f}"
        )

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
                print(
                    f"    {pts[j]['label']:>10} -> {pts[j+1]['label']:<10}: "
                    f"delta_risk={dr:>+10.4f}, delta_return={dret:>+8.4f}, "
                    f"marginal={rate_val:>8.2f} risk/return"
                )
            else:
                rates.append(0)

        # Knee detection: where marginal cost jumps most.
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
            print(
                f"\n    Knee: Point {knee_idx + 1} ({pts[knee_idx]['label']}) "
                f"-- marginal cost jumps {max_jump:.1f}x beyond this point"
            )


# --------------------------------------------------
# Stage 4: Crisis regime stress test
# (Reuses Stage 3's pareto results; compares base vs crisis vol.)
# --------------------------------------------------

# ==================================================
# STAGE 4: Crisis Regime Stress Test
# ==================================================

print(f"\n{'=' * 70}")
print("STAGE 4: CRISIS REGIME STRESS TEST")
print(f"(PSD-preserving correlation shrinkage, alpha = {CRISIS_ALPHA})")
print("=" * 70)

# Build the per-(scenario, eps_label) frontier table and materialize it as
# the `FrontierPoint` Concept. Each Pareto point's metadata -- return, risk,
# inter-row marginals, the knee flag, and the base/crisis vol comparison --
# becomes ontology data instead of stdout.
fp_rows = []
for sn in scenario_names:
    pts = pareto[sn]
    if not pts:
        continue
    rates = []
    for j, pt in enumerate(pts):
        if j == 0:
            marginal = None
        else:
            dr = pt["risk"] - pts[j - 1]["risk"]
            dret = pt["return_actual"] - pts[j - 1]["return_actual"]
            marginal = (dr / dret) if abs(dret) > 1e-6 else 0.0
        rates.append(marginal)
        fp_rows.append({
            "scenario_label": sn,
            "eps_label": pt["label"],
            "return": pt["return_actual"],
            "risk": pt["risk"],
            "marginal_risk_per_return": marginal,
            "is_knee": False,
        })

    # Knee = the eps point with the largest jump in marginal vs the prior
    # point (per scenario). rates[0] is None (min_risk has no marginal),
    # so we start scanning from index 2 against rates[1..].
    knee_idx = None
    max_jump = 0.0
    for j in range(2, len(rates)):
        prev = rates[j - 1]
        curr = rates[j]
        if prev is None or curr is None:
            continue
        if abs(prev) > 1e-6:
            jump = curr / prev
        else:
            jump = curr if curr and curr > 0 else 0.0
        if jump > max_jump:
            max_jump = jump
            knee_idx = j
    if knee_idx is not None:
        # fp_rows for this scenario starts at len(fp_rows) - len(pts).
        scenario_start = len(fp_rows) - len(pts)
        fp_rows[scenario_start + knee_idx]["is_knee"] = True

# Pair base and crisis rows by (budget, eps_label) so vol_base / vol_crisis
# carry on BOTH the base-regime row and its matching crisis-regime row.
risk_by_key = {
    (r["scenario_label"], r["eps_label"]): r["risk"] for r in fp_rows
}
for r in fp_rows:
    sn = r["scenario_label"]
    eps = r["eps_label"]
    # Strip "base_" / "crisis_" prefix to get the budget suffix.
    budget_suffix = sn.split("_", 1)[1]
    base_risk = risk_by_key.get((f"base_{budget_suffix}", eps))
    crisis_risk = risk_by_key.get((f"crisis_{budget_suffix}", eps))
    vol_base = base_risk ** 0.5 if base_risk is not None else 0.0
    vol_crisis = crisis_risk ** 0.5 if crisis_risk is not None else 0.0
    vol_gap = vol_crisis - vol_base
    vol_gap_pct = (vol_gap / vol_base * 100.0) if vol_base > 1e-9 else 0.0
    r["vol_base"] = vol_base
    r["vol_crisis"] = vol_crisis
    r["vol_gap"] = vol_gap
    r["vol_gap_pct"] = vol_gap_pct

fp_df = DataFrame(fp_rows)

# FrontierPoint Concept -- one row per (Scenario, eps_label).
FrontierPoint = model.Concept(
    "FrontierPoint",
    identify_by={"scenario_label": String, "eps_label": String},
)
FrontierPoint.scenario = model.Property(f"{FrontierPoint} for {Scenario}")
FrontierPoint.return_value = model.Property(
    f"{FrontierPoint} has return {Float:fp_return}"
)
FrontierPoint.risk = model.Property(f"{FrontierPoint} has risk {Float:fp_risk}")
FrontierPoint.marginal_risk_per_return = model.Property(
    f"{FrontierPoint} has marginal {Float:fp_marginal}"
)
FrontierPoint.is_knee = model.Property(
    f"{FrontierPoint} is knee {Boolean:fp_is_knee}"
)
FrontierPoint.vol_base = model.Property(
    f"{FrontierPoint} has vol_base {Float:fp_vol_base}"
)
FrontierPoint.vol_crisis = model.Property(
    f"{FrontierPoint} has vol_crisis {Float:fp_vol_crisis}"
)
FrontierPoint.vol_gap = model.Property(
    f"{FrontierPoint} has vol_gap {Float:fp_vol_gap}"
)
FrontierPoint.vol_gap_pct = model.Property(
    f"{FrontierPoint} has vol_gap_pct {Float:fp_vol_gap_pct}"
)

# Two-pass load: marginal_risk_per_return is null at min_risk, so it
# can't sit on the same model.data() frame as the all-rows columns
# (NaN breaks model.data()).
fp_main_df = fp_df[[
    "scenario_label", "eps_label", "return", "risk", "is_knee",
    "vol_base", "vol_crisis", "vol_gap", "vol_gap_pct",
]].reset_index(drop=True)
fp_data = model.data(fp_main_df)
model.define(
    fp := FrontierPoint.new(
        scenario_label=fp_data["scenario_label"],
        eps_label=fp_data["eps_label"],
    ),
    fp.return_value(fp_data["return"]),
    fp.risk(fp_data["risk"]),
    fp.is_knee(fp_data["is_knee"]),
    fp.vol_base(fp_data["vol_base"]),
    fp.vol_crisis(fp_data["vol_crisis"]),
    fp.vol_gap(fp_data["vol_gap"]),
    fp.vol_gap_pct(fp_data["vol_gap_pct"]),
)

# Link FrontierPoint to its Scenario by matching scenario_label == Scenario.name.
fp_link_ref = FrontierPoint.ref()
sc_link_ref = Scenario.ref()
model.where(
    fp_link_ref.scenario_label == sc_link_ref.name,
).define(fp_link_ref.scenario(sc_link_ref))

# Second pass: marginal_risk_per_return (only the 30 non-min_risk rows).
fp_marg_df = (
    fp_df[fp_df["marginal_risk_per_return"].notna()][
        ["scenario_label", "eps_label", "marginal_risk_per_return"]
    ]
    .reset_index(drop=True)
)
fp_marg_data = model.data(fp_marg_df)
fp_marg_ref = FrontierPoint.ref()
model.where(
    fp_marg_ref.scenario_label == fp_marg_data["scenario_label"],
    fp_marg_ref.eps_label == fp_marg_data["eps_label"],
).define(
    fp_marg_ref.marginal_risk_per_return(fp_marg_data["marginal_risk_per_return"])
)

# Side-by-side vol (sqrt variance) by budget x lambda -- now sourced from
# the FrontierPoint Concept rather than the in-memory pareto dict.
print("\n  Volatility comparison (sqrt risk) -- base vs crisis at each lambda:")
fp_q = FrontierPoint.ref()
fp_query_df = (
    model.select(
        fp_q.scenario_label.alias("scenario_label"),
        fp_q.eps_label.alias("eps_label"),
        fp_q.vol_base.alias("vol_base"),
        fp_q.vol_crisis.alias("vol_crisis"),
        fp_q.vol_gap.alias("vol_gap"),
        fp_q.vol_gap_pct.alias("vol_gap_pct"),
    )
    .to_df()
)

eps_order = ["min_risk", "eps_1", "eps_2", "eps_3", "eps_4", "eps_5"]
for budget in budgets:
    base_sn = f"base_{budget}"
    crisis_sn = f"crisis_{budget}"
    base_rows = fp_query_df[fp_query_df["scenario_label"] == base_sn]
    crisis_rows = fp_query_df[fp_query_df["scenario_label"] == crisis_sn]
    if base_rows.empty or crisis_rows.empty:
        continue
    print(f"\n  Budget {budget}:")
    print(
        f"  {'Label':>10} {'vol_base':>12} {'vol_crisis':>12} "
        f"{'gap':>10} {'gap_%':>8}"
    )
    print(f"  {'-' * 56}")
    base_by_eps = {row["eps_label"]: row for _, row in base_rows.iterrows()}
    for eps in eps_order:
        if eps not in base_by_eps:
            continue
        row = base_by_eps[eps]
        print(
            f"  {eps:>10} {float(row['vol_base']):>12.4f} "
            f"{float(row['vol_crisis']):>12.4f} "
            f"{float(row['vol_gap']):>+10.4f} "
            f"{float(row['vol_gap_pct']):>+7.1f}%"
        )

print(
    "\n  Expected pattern: crisis vol > base vol at every lambda; "
    "the gap peaks\n  in the middle of the frontier (eps_1..eps_2) and "
    "narrows toward the\n  concentrated (high-return) end. Because the "
    "investable universe was\n  already deduplicated in Stage 2, the "
    "concentrated end picks the highest-\n  Sharpe distinct bet per cluster "
    "rather than stacking near-duplicates, so\n  the crisis gap shrinks "
    "there instead of widening."
)
