"""Markdown Optimization - Set discount levels across weeks to maximize revenue while clearing inventory."""

from pathlib import Path
from time import time_ns

from pandas import read_csv
from relationalai.semantics import Float, Integer, Model, data, define, require, select, std, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel


def define_model(config=None):
    """Define base model with Product, Discount, TimePeriod concepts."""
    model = Model(f"markdown_{time_ns()}", config=config, use_lqp=False)
    Concept, Property = model.Concept, model.Property

    # Load data
    data_dir = Path(__file__).parent / "data"

    # Products with inventory and demand info
    Product = Concept("Product")
    Product.id = Property("{Product} has {id:int}")
    Product.name = Property("{Product} has {name:string}")
    Product.initial_price = Property("{Product} has {initial_price:float}")
    Product.cost = Property("{Product} has {cost:float}")
    Product.initial_inventory = Property("{Product} has {initial_inventory:int}")
    Product.base_demand = Property("{Product} has {base_demand:float}")
    Product.salvage_rate = Property("{Product} has {salvage_rate:float}")

    products_df = read_csv(data_dir / "products.csv")
    data(products_df).into(Product, keys=["id"])

    # Discount levels with demand lift
    Discount = Concept("Discount")
    Discount.id = Property("{Discount} has {id:int}")
    Discount.level = Property("{Discount} has {level:int}")
    Discount.discount_pct = Property("{Discount} has {discount_pct:float}")
    Discount.demand_lift = Property("{Discount} has {demand_lift:float}")

    discounts_df = read_csv(data_dir / "discounts.csv")
    data(discounts_df).into(Discount, keys=["id"])

    # TimePeriods - store as data for demand multipliers
    weeks_df = read_csv(data_dir / "weeks.csv")
    TimePeriod = Concept("TimePeriod")
    TimePeriod.week_num = Property("{TimePeriod} has {week_num:int}")
    TimePeriod.demand_multiplier = Property("{TimePeriod} has {demand_multiplier:float}")
    data(weeks_df).into(TimePeriod, keys=["week_num"])

    # Constants for time range
    model.week_start = 1
    model.week_end = 4

    # Store references
    model.Product = Product
    model.Discount = Discount
    model.TimePeriod = TimePeriod
    model.Concept = Concept
    model.Property = Property

    return model


def define_problem(model):
    """Define decision variables, constraints, and objective."""
    s = SolverModel(model, "cont", use_pb=True)

    Product = model.Product
    Discount = model.Discount
    TimePeriod = model.TimePeriod
    Property = model.Property
    week_start, week_end = model.week_start, model.week_end
    weeks = std.range(week_start, week_end + 1)

    # Helper refs
    t = Integer.ref()
    p = Product.ref()
    d = Discount.ref()

    # --- Decision Variables ---

    # Discount selection: binary for each product-week-discount combination
    Product.selected = Property("{Product} in week {t:int} at discount {d:Discount} is {selected:float}")
    x_sel = Float.ref()
    s.solve_for(
        Product.selected(t, d, x_sel),
        type="bin",
        name=["sel", Product.name, t, d.discount_pct],
        where=[t == weeks]
    )

    # Sales: continuous for each product-week-discount combination
    Product.sales = Property("{Product} in week {t:int} at discount {d:Discount} has {sales:float}")
    x_sales = Float.ref()
    s.solve_for(
        Product.sales(t, d, x_sales),
        lower=0,
        name=["sales", Product.name, t, d.discount_pct],
        where=[t == weeks]
    )

    # Cumulative sales: for inventory tracking
    Product.cum_sales = Property("{Product} through week {t:int} has {cum_sales:float}")
    x_cum = Float.ref()
    s.solve_for(
        Product.cum_sales(t, x_cum),
        lower=0,
        name=["cum", Product.name, t],
        where=[t == weeks]
    )

    # --- Constraints ---

    # 1. Exactly one discount level per product-week
    s.satisfy(where(
        Product.selected(t, d, x_sel)
    ).require(
        sum(x_sel).per(Product, t) == 1
    ))

    # 2. Price ladder: discounts can only increase (prices can only decrease)
    # If discount d1 is selected in week t, then in week t+1, only d2 with d2.level >= d1.level allowed
    d1, d2 = Discount.ref(), Discount.ref()
    x_sel1, x_sel2 = Float.ref(), Float.ref()
    s.satisfy(where(
        Product.selected(t, d1, x_sel1),
        Product.selected(t + 1, d2, x_sel2),
        d2.level < d1.level,
        t >= week_start,
        t < week_end
    ).require(
        x_sel1 + x_sel2 <= 1
    ))

    # 3. Sales can only occur at selected discount level
    # sales <= demand * selected, where demand = base_demand * demand_lift * demand_multiplier
    w = TimePeriod.ref()
    s.satisfy(where(
        Product.selected(t, d, x_sel),
        Product.sales(t, d, x_sales),
        w.week_num == t
    ).require(
        x_sales <= Product.base_demand * d.demand_lift * w.demand_multiplier * x_sel
    ))

    # 4. Cumulative sales definition
    # TimePeriod 1: cum_sales = sum of sales in week 1
    x_sales_w1, x_cum_w1 = Float.ref(), Float.ref()
    s.satisfy(where(
        Product.sales(week_start, d, x_sales_w1),
        Product.cum_sales(week_start, x_cum_w1)
    ).require(
        x_cum_w1 == sum(x_sales_w1).per(Product)
    ))

    # TimePeriods 2-4: cum_sales[t] = cum_sales[t-1] + sum(sales[t])
    x_sales_t, x_cum_t, x_cum_prev = Float.ref(), Float.ref(), Float.ref()
    s.satisfy(where(
        Product.sales(t, d, x_sales_t),
        Product.cum_sales(t, x_cum_t),
        Product.cum_sales(t - 1, x_cum_prev),
        t > week_start,
        t <= week_end
    ).require(
        x_cum_t == x_cum_prev + sum(x_sales_t).per(Product, t)
    ))

    # 5. Cumulative sales cannot exceed initial inventory
    s.satisfy(where(
        Product.cum_sales(t, x_cum)
    ).require(
        x_cum <= Product.initial_inventory
    ))

    # --- Objective ---
    # Maximize: revenue from sales + salvage value of unsold inventory

    # Revenue = sum(sales * price * (1 - discount_pct/100))
    revenue = sum(x_sales * Product.initial_price * (1 - d.discount_pct / 100)).where(
        Product.sales(t, d, x_sales)
    )

    # Salvage value = (initial_inventory - final_cum_sales) * price * salvage_rate
    x_cum_final = Float.ref()
    salvage = sum(
        (Product.initial_inventory - x_cum_final) * Product.initial_price * Product.salvage_rate
    ).where(
        Product.cum_sales(week_end, x_cum_final)
    )

    s.maximize(revenue + salvage)

    return s


def solve(config=None, solver_name="highs"):
    """Orchestrate model, problem, and solver execution."""
    model = define_model(config)
    solver_model = define_problem(model)
    solver = Solver(solver_name, resources=model._to_executor().resources)
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

    print(f"Status: {sol['status']}")
    print(f"Total revenue (sales + salvage): ${sol['objective']:.2f}")

    df = sol["variables"]

    # Show selected discounts
    print("\n=== Selected Discounts by Product-TimePeriod ===")
    selected = df[df["name"].str.startswith("sel") & (df["float"] > 0.5)]
    print(selected.to_string(index=False))

    # Show sales
    print("\n=== Sales by Product-TimePeriod ===")
    sales = df[df["name"].str.startswith("sales") & (df["float"] > 0.01)]
    print(sales.to_string(index=False))

    # Show cumulative sales
    print("\n=== Cumulative Sales by Product-TimePeriod ===")
    cum = df[df["name"].str.startswith("cum")]
    print(cum.to_string(index=False))
