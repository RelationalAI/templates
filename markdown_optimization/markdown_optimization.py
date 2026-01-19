"""Markdown Optimization - Set discount levels across weeks to maximize revenue."""

from pathlib import Path
from time import time_ns

from pandas import read_csv
from relationalai.semantics import Model, data, define, require, sum
from relationalai.semantics.reasoners.optimization import Solver, SolverModel


def define_model(config=None):
    """Define base model with Product, Week, and Discount concepts."""
    model = Model(f"markdown_{time_ns()}", config=config, use_lqp=False)
    Concept, Property, Relationship = model.Concept, model.Property, model.Relationship

    data_dir = Path(__file__).parent / "data"

    # Product: items to sell with pricing info
    Product = Concept("Product")
    Product.name = Property("{Product} has name {name:String}")
    Product.initial_price = Property("{Product} has initial_price {initial_price:float}")
    Product.cost = Property("{Product} has cost {cost:float}")
    Product.initial_inventory = Property("{Product} has initial_inventory {initial_inventory:int}")
    products_df = read_csv(data_dir / "products.csv")
    data(products_df).into(Product, id="id", properties=["name", "initial_price", "cost", "initial_inventory"])

    # Week: time periods in the selling season
    Week = Concept("Week")
    Week.week_num = Property("{Week} has week_num {week_num:int}")
    Week.demand_multiplier = Property("{Week} has demand_multiplier {demand_multiplier:float}")
    weeks_df = read_csv(data_dir / "weeks.csv")
    data(weeks_df).into(Week, id="id", properties=["week_num", "demand_multiplier"])

    # Discount: available markdown levels
    Discount = Concept("Discount")
    Discount.level = Property("{Discount} has level {level:int}")
    Discount.discount_pct = Property("{Discount} has discount_pct {discount_pct:float}")
    Discount.demand_lift = Property("{Discount} has demand_lift {demand_lift:float}")
    discounts_df = read_csv(data_dir / "discounts.csv")
    data(discounts_df).into(Discount, id="id", properties=["level", "discount_pct", "demand_lift"])

    # PricingDecision: which discount to apply for product/week
    Decision = Concept("PricingDecision")
    Decision.product = Relationship("{PricingDecision} for {product:Product}")
    Decision.week = Relationship("{PricingDecision} in {week:Week}")
    Decision.discount = Relationship("{PricingDecision} applies {discount:Discount}")
    Decision.selected = Property("{PricingDecision} is selected {selected:float}")
    define(Decision.new(product=Product, week=Week, discount=Discount))

    model.Product, model.Week, model.Discount, model.Decision = Product, Week, Discount, Decision
    return model


def define_problem(model):
    """Define decision variables, constraints, and objective."""
    s = SolverModel(model, "cont")
    Product, Week, Discount, Decision = model.Product, model.Week, model.Discount, model.Decision

    # Decision variable: binary selection of discount for each product/week
    s.solve_for(Decision.selected, type="bin", name=[Decision.product, Decision.week, Decision.discount])

    # Constraint: exactly one discount level per product/week
    Dec = Decision.ref()
    Pr = Product.ref()
    Wk = Week.ref()
    discount_selected = sum(Dec.selected).where(Dec.product == Pr, Dec.week == Wk).per(Pr, Wk)
    s.satisfy(require(discount_selected == 1).where(Pr, Wk))

    # Constraint: discount level cannot decrease (no price increase after markdown)
    # For consecutive weeks, if discount d is selected in week w,
    # only discounts >= d can be selected in week w+1
    Dec1 = Decision.ref()
    Dec2 = Decision.ref()
    s.satisfy(
        require(Dec1.selected + Dec2.selected <= 1).where(
            Dec1.product == Dec2.product,
            Dec1.week.week_num + 1 == Dec2.week.week_num,
            Dec1.discount.level > Dec2.discount.level,
        )
    )

    # Objective: maximize total revenue (price after discount * estimated demand)
    # Revenue = (initial_price * (1 - discount_pct/100)) * base_demand * demand_lift * demand_multiplier
    # Simplified: use initial_inventory/4 as base weekly demand
    BASE_DEMAND_FACTOR = 0.25  # 25% of inventory as base weekly demand
    revenue = sum(
        Decision.selected
        * Decision.product.initial_price
        * (1 - Decision.discount.discount_pct / 100)
        * Decision.product.initial_inventory
        * BASE_DEMAND_FACTOR
        * Decision.discount.demand_lift
        * Decision.week.demand_multiplier
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
