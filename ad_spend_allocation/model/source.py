"""Load the sample channels, campaigns, effectiveness rates, and budget scenarios."""

from pathlib import Path

from pandas import read_csv

from .schema import Campaign, Channel, Effectiveness, Scenario, model

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# Load channels from CSV.
channel_csv = read_csv(DATA_DIR / "channels.csv")
model.define(Channel.new(model.data(channel_csv).to_schema()))

# Load campaigns from CSV.
campaign_csv = read_csv(DATA_DIR / "campaigns.csv")
model.define(Campaign.new(model.data(campaign_csv).to_schema()))

# Load effectiveness pairs from CSV and link to Channel/Campaign.
eff_csv = read_csv(DATA_DIR / "effectiveness.csv")
eff_data = model.data(eff_csv)
model.define(
    e := Effectiveness.new(channel_id=eff_data.channel_id, campaign_id=eff_data.campaign_id),
    e.conversion_rate(eff_data.conversion_rate),
)
model.define(Effectiveness.channel(Channel)).where(Effectiveness.channel_id == Channel.id)
model.define(Effectiveness.campaign(Campaign)).where(Effectiveness.campaign_id == Campaign.id)

# Budget scenarios: three total-budget levels.
scenario_data = model.data(
    [("budget_35k", 35000), ("budget_45k", 45000), ("budget_55k", 55000)],
    columns=["name", "total_budget"],
)
model.define(Scenario.new(scenario_data.to_schema()))
