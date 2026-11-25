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

# EPOCH FILTERING: Only issues created within the planning horizon enter the model.
# This is the key epoch pattern -- the rule filters event rows by their epoch column as
# they are loaded. The epoch-to-period mapping is in `target_sprints.py`.
issue_data = model.data(issues_df)
model.where(
    issue_data.created_at >= start_epoch,
    issue_data.created_at <= end_epoch,
).define(
    i := Issue.new(id=issue_data.id),
    i.key(issue_data.key),
    i.summary(issue_data.summary),
    i.story_points(issue_data.story_points),
    i.created_at(issue_data.created_at),
    i.priority(issue_data.priority),
    i.team(issue_data.team),
)

skills_csv = read_csv(DATA_DIR / "skills.csv")
model.define(Skill.new(model.data(skills_csv).to_schema()))

# The planning horizon and the number of input issues, which the deployed model publishes so the
# report describes the data its solves used.
PlanningHorizon = model.Relationship(
    f"planning horizon runs from {String:start} to {String:end} over {Integer:input_issues} input issues"
)
model.define(PlanningHorizon(planning_start, planning_end, len(issues_df)))
