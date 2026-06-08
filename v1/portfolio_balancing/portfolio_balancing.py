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
    Stage 3: anchor solves, then a sensitivity-guided frontier -- three drivers
        (grid / adaptive / dichotomic) compared by approximation quality, plus a
        shadow-price-vs-secant table showing each dual equals the frontier slope.
    Stage 4: per-scenario efficient frontier with exact dual marginals and knee,
        then a base-vs-crisis volatility table per frontier point.
"""

import heapq
import warnings
from dataclasses import dataclass
from pathlib import Path

from pandas import DataFrame, read_csv
from relationalai.semantics import Boolean, Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std.math import abs as math_abs
from relationalai.semantics.std.math import sqrt

# The epsilon sweep re-solves a fresh Problem per return target -- a loop of
# independent optimizations (the epsilon-constraint method), not an accidental rule
# explosion. Silence the "rules created in a loop" perf heuristic for these solves.
warnings.filterwarnings("ignore", message=r"\[Rules created in a loop\]")

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
    """Minimize portfolio variance, optionally under a per-scenario return floor.

    One solve prices every (budget, regime) Scenario at once. When ``eps_rate`` is
    set, the floor ``sum(returns * qty).per(Scenario) >= eps_rate * budget`` is declared
    with ``keyed_by={"scenario": Scenario}`` and the solve runs with ``sensitivity=True``,
    so the solver returns each scenario's SHADOW PRICE -- the dual of its floor. By the
    envelope theorem that dual IS the local slope of the efficient frontier,
    ``shadow_price = d(min variance) / d(return target)`` (HiGHS convention for a minimize
    objective against a ``>=`` floor: the dual is non-negative). No finite differencing
    required.

    Returns ``(solve_info, allocation_df, shadow_by_scenario)`` or ``None`` if infeasible.
    ``shadow_by_scenario`` is empty when ``eps_rate is None`` (no floor to price).
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

    # EPSILON CONSTRAINT: per-scenario return floor (target scaled by budget).
    # keyed_by Scenario attaches an entity back-pointer so the shadow price joins
    # back to its scenario by KEY, never by parsing the constraint name.
    ret_con = None
    if eps_rate is not None:
        ret_con = problem.satisfy(
            model.where(
                Stock.x_quantity(Scenario, x_qty),
            ).require(sum(Stock.returns * x_qty).per(Scenario) >= eps_rate * Scenario.budget),
            name=["return_floor", Scenario.name],
            keyed_by={"scenario": Scenario},
        )

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

    # HiGHS solves this convex QP (the covariance is PSD-preserving) and, unlike the
    # earlier ipopt path, returns sensitivity duals. sensitivity is requested only when
    # there is a return floor to price.
    problem.solve("highs", time_limit_sec=60, sensitivity=eps_rate is not None)
    si = problem.solve_info()

    # "LOCALLY_SOLVED" is kept for non-HiGHS solver back ends; HiGHS itself reports "OPTIMAL".
    if si.termination_status not in ("OPTIMAL", "LOCALLY_SOLVED"):
        return None

    value_ref = Float.ref()
    var_df = model.select(
        quantity_var.scenario.name.alias("scenario"),
        quantity_var.stock.index.alias("stock_index"),
        value_ref.alias("quantity"),
    ).where(quantity_var.values(0, value_ref)).to_df()

    # Per-scenario shadow prices, joined to the scenario by the constraint's key.
    shadow_by_scenario = {}
    if ret_con is not None:
        sp_df = model.select(
            ret_con.scenario.name.alias("scenario"),
            ret_con.shadow_price.alias("shadow_price"),
        ).to_df()
        shadow_by_scenario = {
            row["scenario"]: max(0.0, float(row["shadow_price"])) for _, row in sp_df.iterrows()
        }
        if not shadow_by_scenario:
            warnings.warn(
                "Solver returned no sensitivity duals for the return floor (e.g. a "
                "time-limit exit); shadow prices default to 0, so the adaptive and "
                "dichotomic drivers degrade to blind spacing.",
                stacklevel=2,
            )

    return si, var_df, shadow_by_scenario


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
si1, df1, _ = result1
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
p2.solve("highs", time_limit_sec=60)
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

# --------------------------------------------------
# Sensitivity-guided efficient frontier
# --------------------------------------------------
# Every solve prices ALL scenarios at once, but the smart drivers (adaptive,
# dichotomic) need a single frontier to steer by. We steer by a REFERENCE scenario
# (mid-budget, base regime); each driver's chosen return targets are then applied to
# every scenario in one solve apiece -- keeping the Scenario-Concept "all combinations
# in one solve" efficiency while getting dual-guided sampling. (Return rates are
# regime- and budget-independent, so one scenario's target range is valid for all.)
#
# The steering signal is the return floor's SHADOW PRICE: by the envelope theorem it
# equals d(variance)/d(return), the exact local slope of the frontier, so a driver that
# uses it can place its limited solves where the frontier actually bends instead of on
# a blind uniform grid.

REFERENCE_SCENARIO = "base_1000"
ref_budget = scenario_meta[REFERENCE_SCENARIO]["budget"]


@dataclass(frozen=True)
class Point:
    """One efficient-frontier portfolio for the reference scenario."""

    ret: float  # achieved expected return (absolute level, not a rate) -- frontier x-coordinate
    variance: float  # portfolio variance -- the value function at this return target
    shadow_price: float  # dual of the return floor = local frontier slope d(variance)/d(return)
    rate: float  # the return-rate target that produced it (return / budget)


# Cache solves by return rate: the three drivers share endpoints and the production
# frontier below reuses the dichotomic driver's solves (each already priced every
# scenario), so no rate is ever solved twice.
_solve_cache: dict[float, tuple | None] = {}


def _solve_rate(rate):
    key = round(rate, 10)
    if key not in _solve_cache:
        _solve_cache[key] = solve_epsilon(eps_rate=rate)
    return _solve_cache[key]


def solve_at(r):
    """min variance s.t. reference-scenario return >= r. Reads the reference scenario's
    variance and the shadow price (its frontier slope) off ONE all-scenario solve."""
    rate = r / ref_budget
    result = _solve_rate(rate)
    if result is None:
        raise SystemExit(f"Frontier solve at return={r:.4f} (rate={rate:.4f}) is infeasible.")
    _si, df, shadow = result
    return Point(
        evaluate_return(df, REFERENCE_SCENARIO),
        evaluate_risk(df, REFERENCE_SCENARIO),
        max(0.0, shadow.get(REFERENCE_SCENARIO, 0.0)),
        rate,
    )


# Frontier anchors (solved once, shared by all three drivers). The min-variance
# anchor declares no return floor (eps_rate=None), so its shadow price is 0 by definition.
RETURN_LO = anchor1_returns[REFERENCE_SCENARIO]  # min-variance portfolio's return
RETURN_HI = anchor2_returns[REFERENCE_SCENARIO]  # max achievable return
lo = Point(RETURN_LO, anchor1_risks[REFERENCE_SCENARIO], 0.0, RETURN_LO / ref_budget)
hi = solve_at(RETURN_HI)
print(
    f"\nReference scenario '{REFERENCE_SCENARIO}': frontier spans expected return "
    f"[{RETURN_LO:.4f}, {RETURN_HI:.4f}]"
)


def pair_gap(a, b):
    """Chord-vs-tangent gap between two points on the convex frontier, and the tangent
    crossover eps* where it peaks. The value function lies below the chord between two
    points and above each point's supporting tangent (slope = its shadow price), so the
    gap = chord - tangent-envelope >= 0. eps* is also the best place to sample next."""
    de = b.ret - a.ret
    if de <= 1e-9:
        return 0.0, 0.5 * (a.ret + b.ret)
    dl = b.shadow_price - a.shadow_price
    if dl <= 1e-9:  # locally linear: tangents ~parallel, chord hugs them -> ~0 gap
        estar = 0.5 * (a.ret + b.ret)
    else:
        estar = (a.variance - a.shadow_price * a.ret - b.variance + b.shadow_price * b.ret) / dl
        estar = min(max(estar, a.ret), b.ret)
    chord = a.variance + (b.variance - a.variance) / de * (estar - a.ret)
    tangent = a.variance + a.shadow_price * (estar - a.ret)
    return max(chord - tangent, 0.0), estar


def max_gap(points):
    return max(
        (pair_gap(points[i], points[i + 1])[0] for i in range(len(points) - 1)),
        default=0.0,
    )


def dedupe(points):
    """Sort by return; drop points that collapse onto a neighbour so the frontier is
    strictly increasing in return."""
    out = []
    for p in sorted(points, key=lambda q: q.ret):
        if not out or p.ret - out[-1].ret > 1e-6:
            out.append(p)
    return out


# Three drivers, each the SAME solve budget N (2 shared anchors + N-2 interior); they
# differ only in how they pick the next return target.
def frontier_grid(n):
    """Control: evenly spaced returns, blind to the frontier's shape."""
    if RETURN_HI - RETURN_LO <= 1e-9:  # degenerate (single-point) frontier
        return dedupe([lo, hi])
    step = (RETURN_HI - RETURN_LO) / (n - 1)
    interior = [solve_at(RETURN_LO + i * step) for i in range(1, n - 1)]
    return dedupe([lo] + interior + [hi])


def frontier_adaptive(n):
    """Pointwise dual use: size each step by the current slope so points land evenly in
    variance space -- d(return) = target_dvar / lambda."""
    if RETURN_HI - RETURN_LO <= 1e-9:  # degenerate (single-point) frontier
        return dedupe([lo, hi])
    target_dvar = (hi.variance - lo.variance) / (n - 1)
    min_step = (RETURN_HI - RETURN_LO) / (4 * (n - 1))
    max_step = (RETURN_HI - RETURN_LO) / (n - 2)
    lam = (hi.variance - lo.variance) / (hi.ret - lo.ret)  # bootstrap: chord slope
    pts, e = [lo], RETURN_LO
    for _ in range(n - 2):
        step = min(max(target_dvar / max(lam, 1e-9), min_step), max_step)
        e = min(e + step, RETURN_HI)
        p = solve_at(e)
        pts.append(p)
        lam = p.shadow_price
    pts.append(hi)
    return dedupe(pts)


def frontier_dichotomic(n):
    """Global dual use: repeatedly split the interval with the largest chord-vs-tangent
    gap, sampling at the crossover point where the two endpoints' tangents (their shadow
    prices) meet -- the non-inferior-set estimation (NISE) scheme."""
    pts = {lo.ret: lo, hi.ret: hi}
    g0, _ = pair_gap(lo, hi)
    heap, ctr = [(-g0, 0, lo, hi)], 1
    for _ in range(n - 2):
        if not heap:
            break
        _, _, a, b = heapq.heappop(heap)
        _, estar = pair_gap(a, b)
        p = solve_at(estar)
        pts[p.ret] = p
        for x, y in ((a, p), (p, b)):
            g, _ = pair_gap(x, y)
            heapq.heappush(heap, (-g, ctr, x, y))
            ctr += 1
    return dedupe(list(pts.values()))


N_SOLVES = 6
print(f"\n{'=' * 70}")
print(
    f"SENSITIVITY-GUIDED FRONTIER  (reference '{REFERENCE_SCENARIO}', "
    f"{N_SOLVES}-solve budget per method)"
)
print(f"{'=' * 70}")
# Each driver shares the same solve cache, so the second and third runs mostly hit
# cached points; the per-driver print keeps the (otherwise silent) solve phase legible.
methods = {}
for _name, _driver in (
    ("grid", frontier_grid),
    ("adaptive", frontier_adaptive),
    ("dichotomic", frontier_dichotomic),
):
    print(f"  running {_name} driver ...", flush=True)
    methods[_name] = _driver(N_SOLVES)

# The headline result: at equal solve budget, using the dual to place samples shrinks
# the worst chord-vs-tangent gap. Using it globally (dichotomic) is the guaranteed win.
gaps = {m: max_gap(pts) for m, pts in methods.items()}
print("\nFrontier approximation quality (same solve budget, lower gap = better):")
print(f"  {'method':<12}{'solves':>8}{'max chord-gap':>18}")
print("  " + "-" * 38)
best = min(gaps.values())
for m, pts in methods.items():
    flag = "  <- tightest" if gaps[m] == best else ""
    print(f"  {m:<12}{len(pts):>8}{gaps[m]:>18.4f}{flag}")
if gaps["dichotomic"] > gaps["grid"] + 1e-9:
    raise SystemExit(
        f"dichotomic gap ({gaps['dichotomic']:.3e}) should not exceed grid "
        f"({gaps['grid']:.3e}) at equal budget -- check the frontier driver inputs"
    )

# The shadow price IS the frontier slope: show each point's exact dual next to the
# finite-difference secant between consecutive points. The secant is bracketed by the
# two duals -- which is why no finite differencing is needed to recover each point's slope.
print("\nShadow price = frontier slope (exact dual vs finite-difference secant):")
print("  (dual = extra variance incurred per unit of additional required return)")
print(f"  {'return':>10}{'variance':>14}{'dual (lambda)':>16}{'secant':>14}")
print("  " + "-" * 54)
dpts = methods["dichotomic"]
for j, p in enumerate(dpts):
    if j == 0:
        secant_str = f"{'--':>14}"
    else:
        sec = (p.variance - dpts[j - 1].variance) / (p.ret - dpts[j - 1].ret)
        secant_str = f"{sec:>14.2f}"
    print(f"  {p.ret:>10.4f}{p.variance:>14.4f}{p.shadow_price:>16.2f}{secant_str}")


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

# Production frontier: evaluate the dual-guided (dichotomic) sample points for EVERY
# scenario, reusing those solves (each already priced all scenarios), then materialize
# the whole thing as the `FrontierPoint` Concept. The marginals (exact shadow prices)
# drove the search; now the model verifies and reasons over the result relationally.
prod_points = methods["dichotomic"]  # already deduped + sorted by return (reference scenario)

# (eps_label, allocation_df, shadow_by_scenario) per production point. k=0 is the
# min-variance anchor (solved as eps_rate=None -> df1, zero dual); the rest reuse the
# cached dual-guided solves.
prod_solves = []
for k, p in enumerate(prod_points):
    if k == 0:
        prod_solves.append(("min_risk", df1, {sn: 0.0 for sn in scenario_names}))
    else:
        result = _solve_rate(p.rate)
        assert result is not None, f"frontier point p{k} (rate={p.rate}) had no cached solve"
        _si, df, shadow = result
        prod_solves.append((f"p{k}", df, shadow))

fp_rows = []
for sn in scenario_names:
    slopes = []
    rows_for_sn = []
    for k, (label, df, shadow) in enumerate(prod_solves):
        marginal = float(shadow.get(sn, 0.0))  # EXACT dual; 0 at the min-risk anchor
        slopes.append(marginal)
        rows_for_sn.append(
            {
                "scenario_label": sn,
                "eps_label": label,
                "k": k,
                "return": evaluate_return(df, sn),
                "risk": evaluate_risk(df, sn),
                "marginal_risk_per_return": marginal,
                "is_knee": False,
            }
        )
    # Knee = the point where the exact slope (shadow price) jumps most vs the prior.
    knee_idx, max_jump = None, 0.0
    for j in range(1, len(slopes)):
        prev, curr = slopes[j - 1], slopes[j]
        jump = (curr / prev) if prev > 1e-9 else (curr if curr > 0 else 0.0)
        if jump > max_jump:
            max_jump, knee_idx = jump, j
    if knee_idx is not None:
        rows_for_sn[knee_idx]["is_knee"] = True
    fp_rows.extend(rows_for_sn)

# Pair base and crisis rows by (budget, eps_label) so vol_base / vol_crisis carry on
# BOTH the base-regime row and its matching crisis-regime row.
risk_by_key = {(r["scenario_label"], r["eps_label"]): r["risk"] for r in fp_rows}
for r in fp_rows:
    budget_suffix = r["scenario_label"].split("_", 1)[1]
    base_risk = risk_by_key.get((f"base_{budget_suffix}", r["eps_label"]))
    crisis_risk = risk_by_key.get((f"crisis_{budget_suffix}", r["eps_label"]))
    vol_base = base_risk ** 0.5 if base_risk is not None else 0.0
    vol_crisis = crisis_risk ** 0.5 if crisis_risk is not None else 0.0
    vol_gap = vol_crisis - vol_base
    r["vol_base"] = vol_base
    r["vol_crisis"] = vol_crisis
    r["vol_gap"] = vol_gap
    r["vol_gap_pct"] = (vol_gap / vol_base * 100.0) if vol_base > 1e-9 else 0.0

fp_df = DataFrame(fp_rows)

# FrontierPoint Concept -- one row per (scenario, point). The marginal is the exact
# dual everywhere (0 at the min-risk anchor), so a single-pass load works (no NaN).
FrontierPoint = model.Concept(
    "FrontierPoint",
    identify_by={"scenario_label": String, "eps_label": String},
)
FrontierPoint.scenario = model.Property(f"{FrontierPoint} for {Scenario}")
FrontierPoint.k = model.Property(f"{FrontierPoint} has order {Integer:fp_k}")
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

fp_data = model.data(
    fp_df[
        [
            "scenario_label",
            "eps_label",
            "k",
            "return",
            "risk",
            "marginal_risk_per_return",
            "is_knee",
            "vol_base",
            "vol_crisis",
            "vol_gap",
            "vol_gap_pct",
        ]
    ].reset_index(drop=True)
)
model.define(
    fp := FrontierPoint.new(
        scenario_label=fp_data["scenario_label"],
        eps_label=fp_data["eps_label"],
    ),
    fp.k(fp_data["k"]),
    fp.return_value(fp_data["return"]),
    fp.risk(fp_data["risk"]),
    fp.marginal_risk_per_return(fp_data["marginal_risk_per_return"]),
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

# Relational verification: the defining property of a Pareto-efficient frontier --
# neither coordinate decreases along it, so no point dominates another -- stated as
# integrity constraints per scenario (self-join on consecutive order k), not a Python
# post-check. A violation would surface at the next query.
#
# The interior return targets are picked off the reference scenario only, then applied
# to every scenario; under a shrunk crisis covariance two adjacent targets can price
# out to (near-)equal risk or return. So the checks are non-decreasing with a small
# relative slack rather than strictly increasing -- a genuine dominance violation
# (an actual decrease beyond the slack) still trips them.
MONOTONIC_TOL = 1e-4  # relative slack for the non-decreasing checks (~0.01%)
P = FrontierPoint
Q = FrontierPoint.ref()
consecutive = model.where(P.scenario_label == Q.scenario_label, Q.k == P.k + 1)
consecutive.require(Q.return_value >= (1.0 - MONOTONIC_TOL) * P.return_value)
consecutive.require(Q.risk >= (1.0 - MONOTONIC_TOL) * P.risk)
# Force the ICs + the materialization to evaluate now.
model.select(P.scenario_label, P.k, P.return_value, P.risk, P.marginal_risk_per_return).inspect()

# --------------------------------------------------
# Efficient frontier per scenario (exact dual marginals)
# --------------------------------------------------
print(f"\n{'=' * 70}")
print("EFFICIENT FRONTIER: Risk vs Return (per scenario, exact dual marginals)")
print(f"{'=' * 70}")
fp_view = FrontierPoint.ref()
frontier_df = (
    model.select(
        fp_view.scenario_label.alias("scenario_label"),
        fp_view.k.alias("k"),
        fp_view.eps_label.alias("eps_label"),
        fp_view.return_value.alias("return"),
        fp_view.risk.alias("risk"),
        fp_view.marginal_risk_per_return.alias("marginal"),
        fp_view.is_knee.alias("is_knee"),
    )
    .to_df()
    .sort_values(["scenario_label", "k"])
)
for sn in scenario_names:
    sub = frontier_df[frontier_df["scenario_label"] == sn]
    if len(sub) < 2:
        continue
    meta = scenario_meta[sn]
    print(f"\n  {sn} (budget={meta['budget']:.0f}, regime={meta['regime']}):")
    print(f"  {'#':>3} {'Label':>9} {'Return':>10} {'Risk':>12} {'Marginal':>11} {'Knee':>6}")
    print(f"  {'-' * 56}")
    for _, row in sub.iterrows():
        knee = "  <--" if bool(row["is_knee"]) else ""
        print(
            f"  {int(row['k']) + 1:>3} {row['eps_label']:>9} "
            f"{float(row['return']):>10.2f} {float(row['risk']):>12.4f} "
            f"{float(row['marginal']):>11.2f}{knee}"
        )

# --------------------------------------------------
# Volatility comparison: base vs crisis at each frontier point
# --------------------------------------------------
print("\n  Volatility (sqrt risk) -- base vs crisis at each frontier point:")
fp_q = FrontierPoint.ref()
fp_query_df = model.select(
    fp_q.scenario_label.alias("scenario_label"),
    fp_q.eps_label.alias("eps_label"),
    fp_q.k.alias("k"),
    fp_q.vol_base.alias("vol_base"),
    fp_q.vol_crisis.alias("vol_crisis"),
    fp_q.vol_gap.alias("vol_gap"),
    fp_q.vol_gap_pct.alias("vol_gap_pct"),
).to_df()

for budget in budgets:
    base_rows = fp_query_df[fp_query_df["scenario_label"] == f"base_{budget}"].sort_values("k")
    if base_rows.empty:
        continue
    print(f"\n  Budget {budget}:")
    print(f"  {'Label':>9} {'vol_base':>12} {'vol_crisis':>12} {'gap':>10} {'gap_%':>8}")
    print(f"  {'-' * 55}")
    for _, row in base_rows.iterrows():
        print(
            f"  {row['eps_label']:>9} {float(row['vol_base']):>12.4f} "
            f"{float(row['vol_crisis']):>12.4f} {float(row['vol_gap']):>+10.4f} "
            f"{float(row['vol_gap_pct']):>+7.1f}%"
        )

print(
    "\n  Expected pattern: crisis vol > base vol at every point; the gap peaks in the\n"
    "  middle of the frontier and narrows toward the concentrated (high-return) end.\n"
    "  Because Stage 2 already deduplicated the universe, the concentrated end picks\n"
    "  the highest-Sharpe distinct bet per cluster rather than stacking near-\n"
    "  duplicates, so the crisis gap shrinks there instead of widening."
)
