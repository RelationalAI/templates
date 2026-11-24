"""Load the sample developers, sprints, issues, and skills into the sprint_scheduling model."""

from pathlib import Path

from pandas import Timestamp, read_csv
from relationalai.semantics import Integer, String

from .schema import Developer, Issue, Skill, Sprint, model

# --------------------------------------------------
# Parameters (editable planning horizon)
# --------------------------------------------------

# TEMPORAL PARAMETER: Planning horizon defined by date range
# Users adjust these to change the optimization window
planning_start = "2024-10-01"  # Start of planning horizon (Q4 2024)
planning_end = "2024-11-26"  # End of planning horizon (end of Sprint 4)

# Convert date strings to epoch integers for filtering: midnight in US Pacific time, the zone
# the sprint boundaries in sprints.csv use, so the horizon does not depend on the machine's zone.
start_epoch = int(Timestamp(planning_start, tz="America/Los_Angeles").timestamp())
end_epoch = int(Timestamp(planning_end, tz="America/Los_Angeles").timestamp())

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


def map_to_sprint(created_at_epoch):
    """Map an issue's created_at epoch to its target sprint number."""
    for _, sprint in sprints_csv.iterrows():
        if created_at_epoch < sprint["startdate"]:
            # Created before this sprint starts -> eligible from this sprint
            return int(sprint["number"])
        if sprint["startdate"] <= created_at_epoch < sprint["enddate"]:
            # Created during this sprint -> target this sprint
            return int(sprint["number"])
    # Created after all sprints -> last sprint
    return int(sprints_csv["number"].max())


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

# The planning horizon and the number of input issues, which the deployed model publishes so the
# report describes the data its solves used.
PlanningHorizon = model.Relationship(
    f"planning horizon runs from {String:start} to {String:end} over {Integer:input_issues} input issues"
)
model.define(PlanningHorizon(planning_start, planning_end, len(issues_df)))
