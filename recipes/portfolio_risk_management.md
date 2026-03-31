# Recipe: Portfolio Risk Management

A multi-reasoner chain that detects fraud communities via identity graphs, enforces concentration and risk rules, and optimizes portfolio allocation using Markowitz mean-variance optimization.

## Pattern

```
Predict (surface default and fraud risk signals)
  -> Discover structure (identify fraud communities via identity graph)
    -> Classify (flag overconcentrated positions + high-risk traders)
      -> Optimize (rebalance portfolio to minimize variance)
        -> Stress-test (explore scenarios)
```

## Stages

### Stage 1: Predict Default and Fraud Risk
**Reasoner:** Predictive (pre-computed)
**Question:** "Which users have the highest risk scores and which transactions are flagged as suspicious?"

**Inputs:**
- User risk score -- pre-computed ML risk likelihood per user (0.0-1.0)
- Transaction is_flagged -- boolean flag indicating suspicious transaction activity

**Outputs:**
- Per-user risk rankings based on risk score
- Flagged transactions linked to specific users and accounts
- Users with high risk score and multiple flagged transactions are priority investigation targets

**Notes:**
- Uses pre-computed risk signals already present in the ontology
- No RAI predictive reasoner invocation needed -- this is a query over existing ML outputs
- Output feeds Stage 3 as an input signal for high-risk trader classification
- Flagged transaction patterns feed Stage 2 as additional context for community interpretation

---

### Stage 2: Detect Fraud Communities via Identity Graph
**Reasoner:** Graph
**Template:** `fraud-detection/`
**Question:** "Which users share identifiers (address, phone, email, credit card) in suspicious patterns?"

**Inputs:**
- User concept as nodes
- Address relationship as edges (users sharing the same address)
- User phone, email, credit card number as shared-identifier edges (users with matching values)

**Graph construction:**
- Undirected, unweighted identity graph over Users
- Edge types: shared address, shared phone, shared email, shared credit card number
- Algorithm: weakly connected components (WCC) for community detection

**Outputs:**
- User community -- community ID grouping users connected by shared identifiers
- User is_in_large_group -- flag for users in communities with 4+ members
- User is_suspicious -- flag for users in large groups with differing addresses but shared contact info
- Large communities with mixed addresses suggest identity fraud rings

**Notes:**
- Independent of Stage 1 -- can run in parallel
- Users flagged as suspicious AND with high risk score (from Stage 1) represent compounding risk
- Community structure reveals exposure concentration: if multiple accounts in the same fraud ring hold the same stocks, portfolio risk is correlated

---

### Stage 3: Flag Concentration and Risk Violations
**Reasoner:** Rules
**Template:** `portfolio_compliance/`
**Question:** "Which positions are overconcentrated, which sectors are overweighted, and which traders carry excessive risk?"

**Inputs:**
- Holding quantity, purchase price (base ontology)
- Stock sector, expected return (base ontology)
- Account balance (base ontology)
- User risk score (from Stage 1)
- User is_suspicious (from Stage 2)

**Rules:**
- Position concentration: any single holding exceeding a threshold percentage of account balance
- Sector concentration: total exposure to a single sector exceeding a portfolio-level limit
- High-risk trader: user with risk score > threshold AND linked to flagged transactions or suspicious community membership

**Outputs:**
- Per-holding concentration flags
- Per-sector overweight flags
- Per-user high-risk trader flags
- Concentration flags feed Stage 4 as constraints (position limits) or penalties (overconcentration surcharge)

**Notes:**
- Depends on Stage 1 (risk scores) and Stage 2 (suspicious user flags)
- Rule thresholds are configurable business parameters

---

### Stage 4: Optimize Portfolio Allocation
**Reasoner:** Prescriptive
**Template:** `portfolio_balancing/`
**Question:** "How should we allocate across stocks to minimize portfolio variance while meeting return targets, budget limits, and no short-selling constraints?"

**Problem type:** Quadratic program (Markowitz mean-variance optimization)

**Inputs (from ontology):**
- Stock expected return -- mean return per stock
- Stock covariance -- pairwise covariance matrix between stocks
- Portfolio budget -- total investable amount per portfolio scenario
- Portfolio minimum return target -- minimum acceptable return fraction per portfolio

**Inputs (from earlier stages):**
- User is_suspicious (Stage 2) -- could exclude or limit exposure to stocks heavily held by suspicious users
- Concentration flags (Stage 3) -- could add position-level caps to the formulation

**Decision variables:**
- Allocation quantity of each stock in each portfolio scenario

**Constraints:**
- No short selling: allocation >= 0 for all stock-portfolio pairs
- Budget: sum of allocations per portfolio <= portfolio budget
- Minimum return: sum of (expected return * allocation) per portfolio >= minimum return target * budget

**Objective:**
- Minimize: portfolio variance = sum over all (i, j) stock pairs of covariance(i,j) * allocation(i) * allocation(j)

**Outputs:**
- Optimal allocation per stock per portfolio scenario
- Portfolio-level expected return and variance
- Identification of which stocks are selected and their relative weights

---

### Stage 5: Scenario Analysis
**Reasoner:** Prescriptive (re-solve)
**Question:** "How would the portfolio change under different market conditions?"

**Scenarios:**

| Scenario | Parameter Change | What to Observe |
|----------|-----------------|-----------------|
| Higher return target | Increase minimum return target from baseline to baseline + 2% | Variance increase, allocation shift toward higher-return stocks |
| Sector crash | Set expected return = -10% for all stocks in a sector | Reallocation away from crashed sector, feasibility under return constraint |
| Budget reduction | Reduce portfolio budget by 30% | Proportional scaling vs. selective trimming, return constraint binding |
| Exclude flagged stocks | Add constraint excluding stocks heavily held by suspicious users (Stage 2) | Diversification impact, return reduction, variance change |

**Notes:**
- Each scenario is a parameter modification + re-solve of Stage 4
- Compare portfolio variance, expected return, and stock selection across scenarios
- Suspicious user communities from Stage 2 identify which stock positions carry correlated fraud exposure
- Concentration flags from Stage 3 can be converted to hard position limits in scenario variants

---

## Stage Dependencies

```
Stage 1 (Predict) -----> Stage 3 (Rules) -----> Stage 4 (Optimize) --> Stage 5 (Scenarios)
Stage 2 (Graph)   --------^  ^-----------------/
```

- Stages 1 and 2 are independent -- run in parallel
- Stage 3 depends on Stages 1 and 2
- Stage 4 depends on Stage 3 (and directly on ontology data)
- Stage 5 depends on Stage 4

---

## Templates Used

| Stage | Template Directory | Purpose |
|-------|--------------------|---------|
| Stage 2 | `fraud-detection/` | Weakly connected components over shared-identifier identity graph |
| Stage 3 | `portfolio_compliance/` | Position concentration, sector overweight, and high-risk trader flags |
| Stage 4 | `portfolio_balancing/` | Markowitz mean-variance portfolio optimization |

---

## Adapting This Recipe

This pattern generalizes to any domain where you can:

1. **Surface risk/prediction signals** from pre-computed credit, fraud, or default data
2. **Discover exposure structure** in an identity or relationship graph
3. **Classify entities** by combining signals into concentration and risk flags
4. **Optimize allocation** informed by predictions, exposure, and risk classifications
5. **Stress-test** by varying market conditions, return targets, or risk limits and re-solving

To adapt: replace the domain-specific concepts (User, Stock, Portfolio, Holding, Account) with your equivalents, and adjust the constraints to match your investment policy and regulatory rules. Each stage uses a standalone template that can also be run independently.
