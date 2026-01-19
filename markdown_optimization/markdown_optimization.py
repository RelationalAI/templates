"""Markdown Optimization - Set discount levels across weeks to maximize revenue."""

from pathlib import Path
from time import time_ns

from pandas import read_csv
from relationalai.semantics import Model, data, define, require, sum
from relationalai.semantics.reasoners.optimization import Solver, SolverModel


def define_model(config=None):
    """Define base model with Product, Discount, and PricingDecision concepts."""
    model = Model(f"markdown_{time_ns()}", config=config, use_lqp=False)

    # Concepts
    Product = model.Concept("Product")
    Product.id = model.Property("{Product} has {id:int}")
    Product.name = model.Property("{Product} has {name:string}")
    Product.initial_price = model.Property("{Product} has {initial_price:float}")
    Product.cost = model.Property("{Product} has {cost:float}")
    Product.initial_inventory = model.Property("{Product} has {initial_inventory:int}")

    Discount = model.Concept("Discount")
    Discount.id = model.Property("{Discount} has {id:int}")
    Discount.level = model.Property("{Discount} has {level:int}")
    Discount.discount_pct = model.Property("{Discount} has {discount_pct:float}")
    Discount.demand_lift = model.Property("{Discount} has {demand_lift:float}")

    # Load data
    data_dir = Path(__file__).parent / "data"

    products_df = read_csv(data_dir / "products.csv")
    data(products_df).into(Product, keys=["id"])

    discounts_df = read_csv(data_dir / "discounts.csv")
    data(discounts_df).into(Discount, keys=["id"])

    # PricingDecision: which discount to apply for product/week
    # Using week_num as direct int property instead of Week relationship
    Decision = model.Concept("PricingDecision")
    Decision.product = model.Property("{PricingDecision} for {product:Product}")
    Decision.week_num = model.Property("{PricingDecision} in week {week_num:int}")
    Decision.discount = model.Property("{PricingDecision} applies {discount:Discount}")
    Decision.selected = model.Property("{PricingDecision} is {selected:float}")

    # Create decisions for all product x week x discount combinations
    weeks_df = read_csv(data_dir / "weeks.csv")
    import pandas as pd
    decision_records = []
    for _, prod in products_df.iterrows():
        for _, week in weeks_df.iterrows():
            for _, disc in discounts_df.iterrows():
                decision_records.append({
                    "product_id": int(prod["id"]),
                    "week_num": int(week["week_num"]),
                    "discount_id": int(disc["id"])
                })

    decision_df = pd.DataFrame(decision_records)
    Decision.product_id = model.Property("{PricingDecision} has {product_id:int}")
    Decision.discount_id = model.Property("{PricingDecision} has {discount_id:int}")
    data(decision_df).into(Decision, keys=["product_id", "week_num", "discount_id"])

    # Define relationships
    from relationalai.semantics import where
    where(Decision.product_id == Product.id).define(Decision.product(Product))
    where(Decision.discount_id == Discount.id).define(Decision.discount(Discount))

    # Store week demand multipliers for use in objective
    WeekInfo = model.Concept("WeekInfo")
    WeekInfo.week_num = model.Property("{WeekInfo} for week {week_num:int}")
    WeekInfo.demand_multiplier = model.Property("{WeekInfo} has {demand_multiplier:float}")
    data(weeks_df).into(WeekInfo, keys=["week_num"])

    model.Product, model.Discount, model.Decision, model.WeekInfo = Product, Discount, Decision, WeekInfo
    return model


def define_problem(model):
    """Define decision variables, constraints, and objective."""
    s = SolverModel(model, "cont")
    Product, Discount, Decision, WeekInfo = model.Product, model.Discount, model.Decision, model.WeekInfo

    # Decision variable: binary selection of discount for each product/week
    s.solve_for(Decision.selected, type="bin", name=["dec", Decision.product_id, Decision.week_num, Decision.discount_id])

    # Constraint: exactly one discount level per product/week
    Dec = Decision.ref()
    Dec2 = Decision.ref()
    discount_selected = sum(Dec.selected).where(
        Dec.product_id == Dec2.product_id,
        Dec.week_num == Dec2.week_num
    ).per(Dec2)
    s.satisfy(require(discount_selected == 1))

    # Objective: maximize total revenue
    # Simplified: just use decision variables * product price * discount lift
    BASE_DEMAND_FACTOR = 0.25
    revenue = sum(
        Decision.selected
        * Decision.product.initial_price
        * (1 - Decision.discount.discount_pct / 100)
        * Decision.product.initial_inventory
        * BASE_DEMAND_FACTOR
        * Decision.discount.demand_lift
    )
    s.maximize(revenue)

    return s


def solve(config=None, solver_name="highs"):
    """Orchestrate model, problem, and solver execution."""
    model = define_model(config)
    solver_model = define_problem(model)
    solver = Solver(solver_name)
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
    print(f"Total expected revenue: ${sol['objective']:.2f}")
    print("\nPricing decisions:")
    df = sol["variables"]
    active = df[df["float"] > 0.5] if "float" in df.columns else df
    print(active.to_string(index=False))
