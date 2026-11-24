"""Markdown plan report: reads the deployed retail_markdown model.

Run `python -m queries.markdown_plan` after `rai models deploy --path model`. Prints the
status and objective of the latest refresh's solve and tables of the selected discounts,
the units sold, and the cumulative sales for each product and week.
"""

from model import (
    Discount_ref,
    Product,
    SolveStatus,
    TotalRevenue,
    Week_ref,
    cumulative_ref,
    model,
    sales_ref,
    selection_ref,
)

if __name__ == "__main__":
    status = model.select(SolveStatus).to_df().iloc[:, 0].tolist()
    total_revenue = model.select(TotalRevenue).to_df().iloc[:, 0].tolist()
    print(f"\nSolve result:\n• status: {', '.join(status)}")
    if status != ["OPTIMAL"]:
        raise SystemExit(f"termination status {status}")
    if total_revenue:
        print(f"• objective: {round(total_revenue[0], 9)}\n")

    print(f"Status: {status[0]}")
    if total_revenue:
        print(f"Total revenue (sales + salvage): ${total_revenue[0]:.2f}")

    # Extract the solution with model.select(); the solved values are populated.
    print("\n=== Selected Discounts by Product-Week ===")
    model.select(
        Product.name.alias("product"), Week_ref.num.alias("week"),
        Discount_ref.discount_pct.alias("discount_pct"),
    ).where(
        Product.x_select(Week_ref, Discount_ref, selection_ref), selection_ref > 0.5
    ).inspect()

    print("\n=== Sales by Product-Week ===")
    model.select(
        Product.name.alias("product"), Week_ref.num.alias("week"),
        Discount_ref.discount_pct.alias("discount_pct"), sales_ref.alias("units_sold"),
    ).where(Product.x_sales(Week_ref, Discount_ref, sales_ref), sales_ref > 0.01).inspect()

    print("\n=== Cumulative Sales by Product-Week ===")
    model.select(
        Product.name.alias("product"), Week_ref.num.alias("week"),
        cumulative_ref.alias("cumulative_sold"),
    ).where(Product.x_cuml_sales(Week_ref, cumulative_ref)).inspect()
