"""Sprint Scheduling (prescriptive optimization) template.

This script demonstrates a sprint assignment optimization in RelationalAI with
epoch-based temporal filtering (Pattern B):

- Load sample CSVs describing developers, sprints, issues, and developer-team skills.
- Model those entities as *concepts* with typed properties.
- Filter issues by epoch timestamp (created_at) to scope the planning horizon.
- Map each issue's created_at epoch to a target sprint via epoch-to-period mapping.
- Assign each issue to exactly one developer in one sprint (binary variables).
- Enforce developer capacity per sprint and skill-matching constraints.
- Minimize weighted completion time (high-priority issues penalized more for delay).

Temporal filtering pattern (epoch integers -- Pattern B):
- Convert date-range boundaries to Unix epoch seconds.
- Filter event rows by epoch BEFORE loading into the model.
- Map epochs to categorical periods (sprints) by comparing against sprint
  start/end epochs.
- Compare with Pattern A (native date strings) in the demand_planning_temporal
  template.

Run:
    `python sprint_scheduling.py`

Output:
    Prints the solver termination status, objective value, planning horizon
    summary, sprint assignments table, and sprint workload summary.
"""

from datetime import datetime
from pathlib import Path

from pandas import read_csv

from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("sprint_scheduling")
Concept, Property = model.Concept, model.Property

# --------------------------------------------------
# Parameters (editable planning horizon)
# --------------------------------------------------

# TEMPORAL PARAMETER: Planning horizon defined by date range
# Users adjust these to change the optimization window
planning_start = "2024-10-01"  # Start of planning horizon (Q4 2024)
planning_end = "2024-11-26"    # End of planning horizon (end of Sprint 4)

# Convert date strings to epoch integers for filtering
start_epoch = int(datetime.strptime(planning_start, "%Y-%m-%d").timestamp())
end_epoch = int(datetime.strptime(planning_end, "%Y-%m-%d").timestamp())

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Concept: developers with team affiliation and sprint capacity
Developer = Concept("Developer", identify_by={"id": Integer})
Developer.name = Property(f"{Developer} has {String:name}")
Developer.team = Property(f"{Developer} has {String:team}")
Developer.capacity_points_per_sprint = Property(f"{Developer} has {Integer:capacity_points_per_sprint}")
dev_csv = read_csv(data_dir / "developers.csv")
model.define(Developer.new(model.data(dev_csv).to_schema()))

# Concept: sprints (two-week periods with epoch start/end dates)
Sprint = Concept("Sprint", identify_by={"id": Integer})
Sprint.name = Property(f"{Sprint} has {String:name}")
Sprint.number = Property(f"{Sprint} has {Integer:number}")
Sprint.startdate = Property(f"{Sprint} has {Integer:startdate}")
Sprint.enddate = Property(f"{Sprint} has {Integer:enddate}")
sprints_csv = read_csv(data_dir / "sprints.csv")
model.define(Sprint.new(model.data(sprints_csv).to_schema()))

# Concept: issues (EVENT TABLE — has epoch created_at, needs filtering)
# Raw data spans Sept-Nov 2024. We filter to the planning horizon.
Issue = Concept("Issue", identify_by={"id": Integer})
Issue.key = Property(f"{Issue} has {String:key}")
Issue.summary = Property(f"{Issue} has {String:summary}")
Issue.story_points = Property(f"{Issue} has {Integer:story_points}")
Issue.created_at = Property(f"{Issue} has {Integer:created_at}")
Issue.priority = Property(f"{Issue} has {Integer:priority}")
Issue.team = Property(f"{Issue} has {String:team}")
Issue.target_sprint_number = Property(f"{Issue} has target sprint {Integer:target_sprint_number}")

issues_df = read_csv(data_dir / "issues.csv")

# EPOCH FILTERING: Only load issues created within (or before) the planning horizon
# This is the key epoch pattern — filter event rows by epoch BEFORE they enter the model
filtered_issues = issues_df[issues_df["created_at"] <= end_epoch].copy()

# EPOCH-TO-PERIOD MAPPING: Map each issue to its target sprint based on created_at epoch
# Issues created before planning_start are backlog -> assigned to Sprint 1
# Issues created during a sprint -> assigned to that sprint (earliest eligible)
sprints_df = read_csv(data_dir / "sprints.csv")

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

filtered_issues["target_sprint_number"] = filtered_issues["created_at"].apply(map_to_sprint)

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

# Concept: developer-team skill mapping (which teams a developer can work on)
Skill = Concept("Skill", identify_by={"id": Integer})
Skill.developer_id = Property(f"{Skill} has {Integer:developer_id}")
Skill.team = Property(f"{Skill} has {String:team}")
skills_csv = read_csv(data_dir / "skills.csv")
model.define(Skill.new(model.data(skills_csv).to_schema()))

# Decision concept: assignment of issue to developer in sprint
# Cross-product created from valid (developer, issue, sprint) combinations
# where the developer has the skill for the issue's team
Assignment = Concept("Assignment")
Assignment.developer = Property(f"{Assignment} has {Developer}", short_name="developer")
Assignment.issue = Property(f"{Assignment} has {Issue}", short_name="issue")
Assignment.sprint = Property(f"{Assignment} has {Sprint}", short_name="sprint")
Assignment.x_assigned = Property(f"{Assignment} is {Float:assigned}")

# Build assignment domain: developer can work on issue if they have the matching skill,
# and the sprint is >= the issue's target sprint (can't assign to earlier sprints)
model.define(
    Assignment.new(developer=Developer, issue=Issue, sprint=Sprint)
).where(
    Skill.developer_id == Developer.id,
    Skill.team == Issue.team,
    Sprint.number >= Issue.target_sprint_number,
)

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

s = Problem(model, Float)

# Variable: binary assignment (1 if issue assigned to developer in sprint, 0 otherwise)
s.solve_for(
    Assignment.x_assigned,
    type="bin",
    name=["assign", Assignment.issue.key, Assignment.developer.name, Assignment.sprint.name],
)

# Constraint: each issue must be assigned exactly once (to one developer in one sprint)
s.satisfy(model.require(
    sum(Assignment.x_assigned).per(Issue) == 1
).where(Assignment.issue == Issue))

# Constraint: developer capacity per sprint — total story points assigned <= scaled capacity
# capacity_multiplier allows scenario analysis (e.g., what if teams are understaffed?)
capacity_multiplier = 1.0
s.satisfy(model.require(
    sum(Assignment.x_assigned * Assignment.issue.story_points).per(Developer, Sprint)
    <= Developer.capacity_points_per_sprint * capacity_multiplier
).where(Assignment.developer == Developer, Assignment.sprint == Sprint))

# Objective: minimize weighted completion time (priority * sprint number)
# Lower priority number = higher urgency, so priority 1 issues cost more in later sprints
# Weight = (max_priority + 1 - priority) to make P1 issues most expensive to delay
max_priority = 3
s.minimize(
    sum(Assignment.x_assigned * (max_priority + 1 - Assignment.issue.priority) * Assignment.sprint.number)
)

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

s.display()
s.solve("highs", time_limit_sec=60, _server_side_import=False)
s.display_solve_info()

print(f"Status: {s.termination_status}")
print(f"Objective (weighted completion time): {s.objective_value:.1f}")
print(f"Planning horizon: {planning_start} to {planning_end}")
print(f"Issues in scope: {len(filtered_issues)} (of {len(issues_df)} total)")

# Assignment results
assignments = model.select(
    Assignment.issue.key.alias("issue"),
    Assignment.issue.summary.alias("summary"),
    Assignment.issue.story_points.alias("points"),
    Assignment.issue.priority.alias("priority"),
    Assignment.developer.name.alias("developer"),
    Assignment.sprint.name.alias("sprint"),
).where(Assignment.x_assigned >= 1).to_df()

print("\n=== Sprint Assignments ===")
if not assignments.empty:
    assignments = assignments.sort_values(["sprint", "developer", "priority"])
    print(assignments.to_string(index=False))

# Sprint workload summary
print("\n=== Sprint Workload Summary ===")
if not assignments.empty:
    assignments["points"] = assignments["points"].astype(float)
    summary = assignments.groupby(["sprint", "developer"]).agg(
        issues=("issue", "count"),
        total_points=("points", "sum")
    ).reset_index()
    print(summary.to_string(index=False))
