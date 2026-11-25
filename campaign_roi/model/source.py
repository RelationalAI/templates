"""Load the sample campaigns into the campaign ROI model."""

from pathlib import Path

from pandas import read_csv

from .schema import Campaign, model

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# Load campaigns from CSV.
campaign_csv = read_csv(DATA_DIR / "campaigns.csv")
model.define(Campaign.new(model.data(campaign_csv).to_schema()))
