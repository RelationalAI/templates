"""Load the sample return panels and map them to the semantic schema."""

from pathlib import Path

import pandas as pd
from relationalai.semantics import sum

from .schema import ReturnMonth, Sector, Stock, model

DATA_DIR = Path(__file__).parent.parent / "data"

stocks_csv = pd.read_csv(DATA_DIR / "stocks.csv")
index_returns_csv = pd.read_csv(DATA_DIR / "index_returns.csv")
stock_returns_csv = pd.read_csv(DATA_DIR / "stock_returns.csv")

model.define(Stock.new(model.data(stocks_csv).to_schema()))

model.define(Sector.new(sector_name=Stock.sector))
model.define(Stock.sector_ref(Sector)).where(Stock.sector == Sector.sector_name)
model.define(
    Sector.benchmark_weight(sum(Stock.benchmark_weight).where(Stock.sector_ref(Sector)).per(Sector))
)

model.define(ReturnMonth.new(model.data(index_returns_csv).to_schema()))


def map_stock_returns() -> None:
    stock_return_data = model.data(stock_returns_csv)
    model.define(Stock.monthly_return(ReturnMonth, stock_return_data["return"])).where(
        Stock.ticker(stock_return_data.ticker),
        ReturnMonth.date(stock_return_data.date),
    )


map_stock_returns()
