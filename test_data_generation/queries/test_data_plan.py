"""Test data plan report: reads the deployed test_data_generation model.

Run `python -m queries.test_data_plan` after `rai models deploy --path model`. Prints the
formulation, the termination status and total weighted deviation of the latest refresh's
solve, the optimal row count per table, and a small sample of generated rows for each table.
"""

import random
import string as string_module
from datetime import date, timedelta

from model import SolveStatus, Table, TotalDeviation, model, problem
from pandas import DataFrame


def generate_test_data(row_counts, seed=42):
    """Generate actual test data records based on optimal row counts."""
    random.seed(seed)

    def random_email(i):
        domains = ['gmail.com', 'yahoo.com', 'outlook.com', 'company.com']
        return f"user{i}_{''.join(random.choices(string_module.ascii_lowercase, k=4))}@{random.choice(domains)}"

    def random_date(start_year=2020, end_year=2024):
        start = date(start_year, 1, 1)
        end = date(end_year, 12, 31)
        delta = (end - start).days
        return start + timedelta(days=random.randint(0, delta))

    def random_float(min_val, max_val):
        return round(random.uniform(min_val, max_val), 2)

    generated = {}

    # Customer table
    n_customers = row_counts.get('Customer', {}).get('actual', 100)
    regions = ['North', 'South', 'East', 'West', 'Central']
    customers = [{'customer_id': i, 'email': random_email(i), 'region': random.choice(regions), 'created_date': random_date(2018, 2023)} for i in range(1, n_customers + 1)]
    generated['Customer'] = DataFrame(customers)

    # Product table
    n_products = row_counts.get('Product', {}).get('actual', 50)
    categories = ['Electronics', 'Clothing', 'Home', 'Sports', 'Books']
    products = [{'product_id': i, 'name': f"{random.choice(categories)} Item {i}", 'category': random.choice(categories), 'price': random_float(0.99, 999.99)} for i in range(1, n_products + 1)]
    generated['Product'] = DataFrame(products)

    # Order table
    n_orders = row_counts.get('Order', {}).get('actual', 500)
    statuses = ['pending', 'shipped', 'delivered', 'cancelled']
    orders = [{'order_id': i, 'customer_id': random.randint(1, max(1, n_customers)), 'order_date': random_date(2023, 2024), 'status': random.choice(statuses)} for i in range(1, n_orders + 1)]
    generated['Order'] = DataFrame(orders)

    # OrderLine table
    n_orderlines = row_counts.get('OrderLine', {}).get('actual', 1500)
    orderlines = [{'orderline_id': i, 'order_id': random.randint(1, max(1, n_orders)), 'product_id': random.randint(1, max(1, n_products)), 'quantity': random.randint(1, 10), 'unit_price': random_float(0.99, 999.99)} for i in range(1, n_orderlines + 1)]
    generated['OrderLine'] = DataFrame(orderlines)

    # Supplier table
    n_suppliers = row_counts.get('Supplier', {}).get('actual', 50)
    countries = ['USA', 'China', 'Germany', 'Japan', 'UK']
    suppliers = [{'supplier_id': i, 'name': f"Supplier_{i}", 'country': random.choice(countries), 'reliability_score': random_float(50.0, 100.0)} for i in range(1, n_suppliers + 1)]
    generated['Supplier'] = DataFrame(suppliers)

    # SupplierProduct table
    n_supplier_products = row_counts.get('SupplierProduct', {}).get('actual', 200)
    supplier_products = [{'supplierproduct_id': i, 'supplier_id': random.randint(1, max(1, n_suppliers)), 'product_id': random.randint(1, max(1, n_products)), 'lead_time_days': random.randint(1, 90), 'unit_cost': random_float(0.50, 500.0)} for i in range(1, n_supplier_products + 1)]
    generated['SupplierProduct'] = DataFrame(supplier_products)

    return generated


if __name__ == "__main__":
    problem.display()

    # Status and objective of the latest refresh's solve. A refresh records any
    # termination status, so the report checks it.
    status = model.select(SolveStatus).to_df().iloc[:, 0].tolist()
    deviation = model.select(TotalDeviation).to_df().iloc[:, 0].tolist()
    if status != ["OPTIMAL"]:
        raise SystemExit(f"No optimal row counts: termination status {status}")

    print(f"Status: {status[0]}")
    print(f"Total weighted deviation: {deviation[0]:.2f}")

    # Extract row counts
    row_counts = {}
    results_df = model.select(Table.table_name, Table.x_actual_rows, Table.target_rows).to_df()
    for _, row in results_df.iterrows():
        actual = int(round(row['actual_rows']))
        target = int(row['target_rows'])
        row_counts[row['table_name']] = {'actual': actual, 'target': target}

    print("\nOptimal row counts:")
    for table, counts in row_counts.items():
        dev = abs(counts['actual'] - counts['target'])
        print(f"  {table}: {counts['actual']} rows (target: {counts['target']}, deviation: {dev})")

    # Generate data and show samples
    print("\n" + "=" * 50)
    print("GENERATED TEST DATA")
    print("=" * 50)

    generated_data = generate_test_data(row_counts)
    for table, df in generated_data.items():
        print(f"\n{table}: {len(df)} rows")
        print(df.head(3).to_string(index=False))
