"""Bundled HM_MINI and optimizer CSVs and the base-fact mappings."""

from pathlib import Path

from pandas import read_csv

from .schema import (
    Article,
    Customer,
    Discount,
    OptArticle,
    ProdCapacity,
    Test,
    TestTable,
    Train,
    TrainTable,
    Transaction,
    Val,
    ValTable,
    Week,
    model,
)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
HM_DIR = DATA_DIR / "hm_mini"

# The deploy writes each frame into its store view as inline rows, and Snowflake rejects a view
# definition past about 1 MB. Load only the columns the GNN reads: the full customer and article
# files are 1.2 MB and 2 MB inline.
CUSTOMER_COLUMNS = [
    "C_CUSTOMER_ID", "FN", "ACTIVE", "CLUB_MEMBER_STATUS", "FASHION_NEWS_FREQUENCY", "AGE",
]
ARTICLE_COLUMNS = [
    "A_ARTICLE_ID", "PROD_NAME", "PRODUCT_GROUP_NAME", "COLOUR_GROUP_NAME",
    "INDEX_GROUP_NAME", "GARMENT_GROUP_NAME",
]

customers_df = read_csv(HM_DIR / "customers.csv", usecols=CUSTOMER_COLUMNS)
articles_df = read_csv(HM_DIR / "articles.csv", usecols=ARTICLE_COLUMNS)
transactions_df = read_csv(HM_DIR / "transactions.csv")

model.define(Customer.new(model.data(customers_df).to_schema()))
model.define(Article.new(model.data(articles_df).to_schema()))
model.define(Transaction.new(model.data(transactions_df).to_schema()))

train_df = read_csv(HM_DIR / "train_sales.csv")
val_df = read_csv(HM_DIR / "val_sales.csv")
test_df = read_csv(HM_DIR / "test_sales.csv")

model.define(TrainTable.new(model.data(train_df).to_schema()))
model.define(ValTable.new(model.data(val_df).to_schema()))
model.define(TestTable.new(model.data(test_df).to_schema()))

model.define(
    Train(Transaction, TrainTable.timestamp, TrainTable.value)
).where(Transaction.transaction_id == TrainTable.transaction_id)
model.define(
    Val(Transaction, ValTable.timestamp, ValTable.value)
).where(Transaction.transaction_id == ValTable.transaction_id)
model.define(
    Test(Transaction, TestTable.timestamp)
).where(Transaction.transaction_id == TestTable.transaction_id)

inv_csv = read_csv(HM_DIR / "articles_inventory.csv", dtype={"article_id": int})
inv_data = model.data(inv_csv)
model.define(
    oa := OptArticle.new(opt_article_id=inv_data.article_id),
    oa.name(inv_data.name),
    oa.initial_price(inv_data.initial_price),
    oa.cost(inv_data.cost),
    oa.initial_inventory(inv_data.initial_inventory),
    oa.salvage_rate(inv_data.salvage_rate),
)

discount_csv = read_csv(DATA_DIR / "discounts.csv")
model.define(Discount.new(model.data(discount_csv).to_schema()))

week_csv = read_csv(DATA_DIR / "weeks.csv")
model.define(Week.new(model.data(week_csv).to_schema()))

prod_csv = read_csv(HM_DIR / "production_capacity.csv", dtype={"article_id": int})
prod_data = model.data(prod_csv)
model.define(
    pc := ProdCapacity.new(pc_article_id=prod_data.article_id),
    pc.max_production_per_week(prod_data.max_production_per_week),
    pc.production_cost(prod_data.production_cost),
    pc.holding_cost_per_week(prod_data.holding_cost_per_week),
    pc.pc_initial_inventory(prod_data.initial_inventory),
)
