---
title: "Portfolio Re-balancing"
description: "Flag holdings that exceed concentration limits, group stocks that tend to move together, and compare rebalanced portfolios by expected return and risk under normal and stressed markets."
featured: false
experience_level: intermediate
industry: "Financial Services"
reasoning_types:
  - Prescriptive
  - Rules-based
  - Graph
tags:
  - Multi-Reasoner
  - Portfolio Optimization
  - Quadratic Programming
  - Community Detection
  - Sensitivity Analysis
  - Stress Testing
---

Explore the [model](https://docs.relational.ai/build/templates/portfolio_balancing/#explore-the-model) and [guided walkthrough](https://docs.relational.ai/build/templates/portfolio_balancing/#see-how-it-works) in the documentation.

## What this template is for

Investment managers need to keep client portfolios within concentration and compliance limits while weighing expected return against risk. A portfolio can look diversified across many stocks yet still carry hidden risk when holdings share a sector or tend to move together, especially during market stress.

This template combines portfolio holdings, expected returns, and covariance data to flag concentration problems, group correlated stocks, and calculate rebalanced allocations under portfolio constraints. Use it as a starting point for adapting the investment universe, limits, objectives, or stress scenarios to your own portfolio.

## Quickstart

Before you start, install Python 3.10 or later. You need a Snowflake account
with the RAI Native App, user access to the app, and an engine enabled for
Prescriptive reasoning. Graph and Prescriptive reasoning are in Public Preview,
and Prescriptive reasoning is available by request. Preview features are for
evaluation and testing, not production applications. The template installs the
SDK version pinned in `pyproject.toml`: `relationalai==1.9.0`.

Use this sequence to run the bundled example:

1. **Download the template**

   [Download the ZIP](https://docs.relational.ai/templates/zips/v1/portfolio_balancing.zip). Unzip it and enter the template directory:

   ```bash
   unzip portfolio_balancing.zip
   cd portfolio_balancing
   ```

2. **Create a Python environment**

   Create and activate a virtual environment, then update pip:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   ```

3. **Install the template**

   Install the template and its dependencies in the active environment:

   ```bash
   python -m pip install .
   ```

4. **Configure your project**

   Use the configuration builder in [Start building with PyRel](https://docs.relational.ai/get-started/start-building-with-pyrel/#configure-your-project) to create `raiconfig.yaml` in the template directory. Follow that guide to save the file and verify your connection.

5. **Run the template**

   Run the bundled script from the template directory:

   ```bash
   python portfolio_balancing.py
   ```

   ```text
   ======================================================================
   STAGE 1: COMPLIANCE ANALYSIS (rules)
   ======================================================================

   --- Rule 1: Overconcentrated Holdings (position > 15% of balance) ---

     holding_id=1, ticker=AAPL, account_id=1, value=18000.00, balance=100000.00, pct=18.0%
     holding_id=2, ticker=MSFT, account_id=1, value=16000.00, balance=100000.00, pct=16.0%
     holding_id=13, ticker=JNJ, account_id=4, value=12800.00, balance=80000.00, pct=16.0%
     holding_id=14, ticker=PFE, account_id=4, value=13000.00, balance=80000.00, pct=16.2%

   --- Rule 2: Sector Concentration (sector > 30% of balance) ---

     account_id=1, sector=Technology, sector_value=34000.00, balance=100000.00, pct=34.0%
     account_id=4, sector=Healthcare, sector_value=25800.00, balance=80000.00, pct=32.2%

   --- Rule 3: High Risk Traders (risk_score > 0.8 AND >5 flagged txns) ---

     user_id=1, name=Alice Chen, risk_score=0.85
     user_id=5, name=Eve Taylor, risk_score=0.92

   ======================================================================
   STAGE 2: GRAPH -- Covariance Clustering (Louvain)
   ======================================================================

     Correlation graph: 4 edges (|correlation| >= 0.3)
     Louvain communities: 5 cluster(s)
       Cluster 1 (size 3): AAPL (Technology), MSFT (Technology), GOOGL (Technology)
       Cluster 2 (size 2): JNJ (Healthcare), PFE (Healthcare)
       Cluster 3 (size 1): XOM (Energy)
       Cluster 4 (size 1): PG (Consumer Staples)
       Cluster 5 (size 1): JPM (Financials)

     Avg correlation: intra-cluster = +0.683, inter-cluster = +0.131

     Cluster representatives (5 of 8 stocks, picked by highest Sharpe):
       Cluster 1: GOOGL (Technology) -- Sharpe = 0.605
       Cluster 2: PFE (Healthcare) -- Sharpe = 0.530
       Cluster 3: XOM (Energy) -- Sharpe = 0.588
       Cluster 4: PG (Consumer Staples) -- Sharpe = 0.444
       Cluster 5: JPM (Financials) -- Sharpe = 0.500

   ======================================================================
   STAGE 3: BI-OBJECTIVE OPTIMIZATION
   (position + sector limits on representative universe; base & crisis regimes)
   ======================================================================

   ANCHOR SOLVE 1: Minimize risk (no return constraint)
   --------------------------------------------------
   Status: OPTIMAL
     base_500: return = 32.4336, risk = 1160.392619
     base_1000: return = 64.8673, risk = 4641.570478
     base_2000: return = 129.7346, risk = 18566.281910
     crisis_500: return = 31.6873, risk = 1913.599530
     crisis_1000: return = 63.3745, risk = 7654.398122
     crisis_2000: return = 126.7490, risk = 30617.592488

   ANCHOR SOLVE 2: Maximize return (swap objective)
   --------------------------------------------------
   Status: OPTIMAL
     base_500: return = 42.0000
     base_1000: return = 84.0000
     base_2000: return = 168.0000
     crisis_500: return = 42.0000
     crisis_1000: return = 84.0000
     crisis_2000: return = 168.0000

   Reference scenario 'base_1000': frontier spans expected return [64.8673, 84.0000]

   ======================================================================
   SENSITIVITY-GUIDED FRONTIER  (reference 'base_1000', 6-solve budget per method)
   ======================================================================
     running grid driver ...
     running adaptive driver ...
     running dichotomic driver ...

   Frontier approximation quality (same solve budget, lower gap = better):
     method        solves     max chord-gap
     --------------------------------------
     grid               6          557.9250
     adaptive           6          415.1730
     dichotomic         6          202.2972  <- tightest

   Shadow price = frontier slope (exact dual vs finite-difference secant):
     (dual = extra variance incurred per unit of additional required return)
         return      variance   dual (lambda)        secant
     ------------------------------------------------------
        64.8673     4641.5705            0.00            --
        71.2734     5181.9733          134.83         84.36
        75.9396     5946.0980          192.68        163.75
        80.4605     6944.2401          250.64        220.79
        83.1779     7809.1748          650.79        318.29
        84.0000     8528.0000         1098.00        874.39

   ======================================================================
   STAGE 4: CRISIS REGIME STRESS TEST
   (PSD-preserving correlation shrinkage, alpha = 0.7)
   ======================================================================
      scenario_label fp_k   fp_return       fp_risk  fp_marginal
   0       base_1000    0   64.867294   4641.570478     0.000000
   1       base_1000    1   71.273353   5181.973349   134.831681
   2       base_1000    2   75.939644   5946.098016   192.676821
   3       base_1000    3   80.460453   6944.240101   250.641612
   4       base_1000    4   83.177915   7809.174802   650.786176
   5       base_1000    5   84.000000   8528.000000  1098.002000
   6       base_2000    0  129.734588  18566.281910     0.000000
   7       base_2000    1  142.546706  20727.893397   269.663362
   8       base_2000    2  151.879288  23784.392064   385.353641
   9       base_2000    3  160.920906  27776.960404   501.283224
   10      base_2000    4  166.355830  31236.699206  1301.572353
   11      base_2000    5  168.000000  34112.000000  2196.004000
   12       base_500    0   32.433647   1160.392619     0.000000
   13       base_500    1   35.636676   1295.493337    67.415840
   14       base_500    2   37.969822   1486.524504    96.338410
   15       base_500    3   40.230227   1736.060025   125.320806
   16       base_500    4   41.588958   1952.293700   325.393088
   17       base_500    5   42.000000   2132.000000   549.001000
   18    crisis_1000    0   63.374518   7654.398122     0.000000
   19    crisis_1000    1   71.273353   8698.490325   193.732272
   20    crisis_1000    2   75.939644   9707.569504   238.765193
   21    crisis_1000    3   80.460453  10898.552372   291.626535
   22    crisis_1000    4   83.177915  11923.002284   692.003538
   23    crisis_1000    5   84.000000  12622.027506  1008.614487
   24    crisis_2000    0  126.749037  30617.592488     0.000000
   25    crisis_2000    1  142.546706  34793.961301   387.464545
   26    crisis_2000    2  151.879288  38830.278015   477.530386
   27    crisis_2000    3  160.920906  43594.209487   583.253070
   28    crisis_2000    4  166.355830  47692.009136  1384.007076
   29    crisis_2000    5  168.000000  50488.110022  2017.228973
   30     crisis_500    0   31.687259   1913.599530     0.000000
   31     crisis_500    1   35.636676   2174.622581    96.866136
   32     crisis_500    2   37.969822   2426.892376   119.382596
   33     crisis_500    3   40.230227   2724.638093   145.813267
   34     crisis_500    4   41.588958   2980.750571   346.001769
   35     crisis_500    5   42.000000   3155.506876   504.307243


   ======================================================================
   EFFICIENT FRONTIER: Risk vs Return (per scenario, exact dual marginals)
   ======================================================================

     base_500 (budget=500, regime=base):
       #     Label     Return         Risk    Marginal   Knee
     --------------------------------------------------------
       1  min_risk      32.43    1160.3926        0.00
       2        p1      35.64    1295.4933       67.42
       3        p2      37.97    1486.5245       96.34
       4        p3      40.23    1736.0600      125.32  <--
       5        p4      41.59    1952.2937      325.39
       6        p5      42.00    2132.0000      549.00

     base_1000 (budget=1000, regime=base):
       #     Label     Return         Risk    Marginal   Knee
     --------------------------------------------------------
       1  min_risk      64.87    4641.5705        0.00
       2        p1      71.27    5181.9733      134.83
       3        p2      75.94    5946.0980      192.68
       4        p3      80.46    6944.2401      250.64  <--
       5        p4      83.18    7809.1748      650.79
       6        p5      84.00    8528.0000     1098.00

     base_2000 (budget=2000, regime=base):
       #     Label     Return         Risk    Marginal   Knee
     --------------------------------------------------------
       1  min_risk     129.73   18566.2819        0.00
       2        p1     142.55   20727.8934      269.66
       3        p2     151.88   23784.3921      385.35
       4        p3     160.92   27776.9604      501.28  <--
       5        p4     166.36   31236.6992     1301.57
       6        p5     168.00   34112.0000     2196.00

     crisis_500 (budget=500, regime=crisis):
       #     Label     Return         Risk    Marginal   Knee
     --------------------------------------------------------
       1  min_risk      31.69    1913.5995        0.00
       2        p1      35.64    2174.6226       96.87
       3        p2      37.97    2426.8924      119.38
       4        p3      40.23    2724.6381      145.81  <--
       5        p4      41.59    2980.7506      346.00
       6        p5      42.00    3155.5069      504.31

     crisis_1000 (budget=1000, regime=crisis):
       #     Label     Return         Risk    Marginal   Knee
     --------------------------------------------------------
       1  min_risk      63.37    7654.3981        0.00
       2        p1      71.27    8698.4903      193.73
       3        p2      75.94    9707.5695      238.77
       4        p3      80.46   10898.5524      291.63  <--
       5        p4      83.18   11923.0023      692.00
       6        p5      84.00   12622.0275     1008.61

     crisis_2000 (budget=2000, regime=crisis):
       #     Label     Return         Risk    Marginal   Knee
     --------------------------------------------------------
       1  min_risk     126.75   30617.5925        0.00
       2        p1     142.55   34793.9613      387.46
       3        p2     151.88   38830.2780      477.53
       4        p3     160.92   43594.2095      583.25  <--
       5        p4     166.36   47692.0091     1384.01
       6        p5     168.00   50488.1100     2017.23

     Volatility (sqrt risk) -- base vs crisis at each frontier point:

     Budget 500:
         Label     vol_base   vol_crisis        gap    gap_%
     -------------------------------------------------------
      min_risk      34.0645      43.7447    +9.6802   +28.4%
            p1      35.9930      46.6328   +10.6399   +29.6%
            p2      38.5555      49.2635   +10.7080   +27.8%
            p3      41.6661      52.1981   +10.5320   +25.3%
            p4      44.1848      54.5963   +10.4115   +23.6%
            p5      46.1736      56.1739   +10.0003   +21.7%

     Budget 1000:
         Label     vol_base   vol_crisis        gap    gap_%
     -------------------------------------------------------
      min_risk      68.1291      87.4894   +19.3603   +28.4%
            p1      71.9859      93.2657   +21.2798   +29.6%
            p2      77.1109      98.5270   +21.4161   +27.8%
            p3      83.3321     104.3961   +21.0640   +25.3%
            p4      88.3695     109.1925   +20.8230   +23.6%
            p5      92.3472     112.3478   +20.0006   +21.7%

     Budget 2000:
         Label     vol_base   vol_crisis        gap    gap_%
     -------------------------------------------------------
      min_risk     136.2581     174.9788   +38.7207   +28.4%
            p1     143.9718     186.5314   +42.5595   +29.6%
            p2     154.2219     197.0540   +42.8321   +27.8%
            p3     166.6642     208.7923   +42.1280   +25.3%
            p4     176.7391     218.3850   +41.6459   +23.6%
            p5     184.6943     224.6956   +40.0013   +21.7%

     Expected pattern: crisis vol > base vol at every point; the gap peaks in the
     middle of the frontier and narrows toward the concentrated (high-return) end.
     Because Stage 2 already deduplicated the universe, the concentrated end picks
     the highest-Sharpe distinct bet per cluster rather than stacking near-
     duplicates, so the crisis gap shrinks there instead of widening.

   ======================================
   KNEE PORTFOLIO ALLOCATIONS BY SCENARIO
   ======================================

     base_500 (budget=500, regime=base, point=p3)
     expected return=40.23, volatility=41.67
     Ticker        Amount    Weight
     ------------------------------
     GOOGL         150.00    30.0%
     XOM           139.29    27.9%
     PFE           117.04    23.4%
     JPM            67.74    13.5%
     PG             25.93     5.2%

     base_1000 (budget=1000, regime=base, point=p3)
     expected return=80.46, volatility=83.33
     Ticker        Amount    Weight
     ------------------------------
     GOOGL         300.00    30.0%
     XOM           278.57    27.9%
     PFE           234.07    23.4%
     JPM           135.49    13.5%
     PG             51.87     5.2%

     base_2000 (budget=2000, regime=base, point=p3)
     expected return=160.92, volatility=166.66
     Ticker        Amount    Weight
     ------------------------------
     GOOGL         600.00    30.0%
     XOM           557.15    27.9%
     PFE           468.15    23.4%
     JPM           270.97    13.5%
     PG            103.74     5.2%

     crisis_500 (budget=500, regime=crisis, point=p3)
     expected return=40.23, volatility=52.20
     Ticker        Amount    Weight
     ------------------------------
     GOOGL         150.00    30.0%
     XOM           143.22    28.6%
     PFE           129.96    26.0%
     JPM            51.27    10.3%
     PG             25.56     5.1%

     crisis_1000 (budget=1000, regime=crisis, point=p3)
     expected return=80.46, volatility=104.40
     Ticker        Amount    Weight
     ------------------------------
     GOOGL         300.00    30.0%
     XOM           286.44    28.6%
     PFE           259.92    26.0%
     JPM           102.53    10.3%
     PG             51.11     5.1%

     crisis_2000 (budget=2000, regime=crisis, point=p3)
     expected return=160.92, volatility=208.79
     Ticker        Amount    Weight
     ------------------------------
     GOOGL         600.00    30.0%
     XOM           572.87    28.6%
     PFE           519.84    26.0%
     JPM           205.06    10.3%
     PG            102.23     5.1%

     Each knee is a candidate portfolio, not a recommendation. The amounts apply to
     the sample scenario, not to a specific account.
   ```

   The template first groups stocks that tend to move together and uses one stock from each group. This reduces the chance that a portfolio will appear diversified while holding several stocks that behave alike.

   It then compares portfolios for six combinations of budget and market conditions. For each combination, it selects a portfolio where requiring more expected return would begin to increase risk much faster. In this sample, that selected option is labeled `p3`.

   `base` uses normal market assumptions, while `crisis` uses stressed assumptions. Under the stressed assumptions, estimated volatility is 22% to 30% higher. Volatility measures how much the portfolio's value may vary. In the final tables, `Amount` shows how much of the budget is assigned to each stock, and `Weight` shows that stock's share of the budget.

   These results are starting points for review, not recommendations or trades for a specific account. To adapt one for an account, use an appropriate budget and market assumptions, then compare the target amounts with the account's current holdings. The walkthrough below explains how the template calculates these results.
