"""Load the sample developers, sprints, issues, and skills into the sprint_scheduling model."""

from datetime import datetime
from pathlib import Path

from pandas import read_csv

from .schema import Developer, Issue, Skill, Sprint, model

# --------------------------------------------------
# Parameters (editable planning horizon)
# --------------------------------------------------

# TEMPORAL PARAMETER: Planning horizon defined by date range
# Users adjust these to change the optimization window
planning_start = "2024-10-01"  # Start of planning horizon (Q4 2024)
planning_end = "2024-11-26"  # End of planning horizon (end of Sprint 4)

# Convert date strings to epoch integers for filtering
start_epoch = int(datetime.strptime(planning_start, "%Y-%m-%d").timestamp())
end_epoch = int(datetime.strptime(planning_end, "%Y-%m-%d").timestamp())

# --------------------------------------------------
# Load data
# --------------------------------------------------

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

dev_csv = read_csv(DATA_DIR / "developers.csv")
model.define(Developer.new(model.data(dev_csv).to_schema()))

sprints_csv = read_csv(DATA_DIR / "sprints.csv")
model.define(Sprint.new(model.data(sprints_csv).to_schema()))

issues_df = read_csv(DATA_DIR / "issues.csv")

# EPOCH FILTERING: Only load issues created within the planning horizon
# This is the key epoch pattern — filter event rows by epoch BEFORE they enter the model
filtered_issues = issues_df[
    (issues_df["created_at"] >= start_epoch) & (issues_df["created_at"] <= end_epoch)
].copy()

# EPOCH-TO-PERIOD MAPPING: Map each issue to its target sprint based on created_at epoch
# Issues created during a sprint -> assigned to that sprint (earliest eligible)
sprints_df = read_csv(DATA_DIR / "sprints.csv")


def map_to_sprint(created_at_epoch):
    """Map an issue's created_at epoch to its target sprint number."""
    for _, sprint in sprints_df.iterrows():
        if created_at_epoch < sprint["startdate"]:
            # Created before this sprint starts -> eligible from this sprint
            return int(sprint["number"])
        if sprint["startdate"] <= created_at_epoch < sprint["enddate"]:
            # Created during this sprint -> target this sprint
            return int(sprint["number"])
    # Created after all sprints -> last sprint
    return int(sprints_df["number"].max())


filtered_issues["target_sprint_number"] = filtered_issues["created_at"].apply(
    map_to_sprint
)

issue_data = model.data(filtered_issues)
model.define(
    i := Issue.new(id=issue_data.id),
    i.key(issue_data.key),
    i.summary(issue_data.summary),
    i.story_points(issue_data.story_points),
    i.created_at(issue_data.created_at),
    i.priority(issue_data.priority),
    i.team(issue_data.team),
    i.target_sprint_number(issue_data.target_sprint_number),
)

skills_csv = read_csv(DATA_DIR / "skills.csv")
model.define(Skill.new(model.data(skills_csv).to_schema()))
