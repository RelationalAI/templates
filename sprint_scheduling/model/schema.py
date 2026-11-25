"""Semantic schema for the sprint_scheduling template: developers, sprints, issues, skills, and assignments."""

from relationalai.semantics import Float, Integer, Model, String

model = Model("sprint_scheduling")
Concept, Property = model.Concept, model.Property

# Concept: developers with team affiliation and sprint capacity
Developer = Concept("Developer", identify_by={"id": Integer})
Developer.name = Property(f"{Developer} has {String:name}")
Developer.team = Property(f"{Developer} has {String:team}")
Developer.capacity_points_per_sprint = Property(
    f"{Developer} has {Integer:capacity_points_per_sprint}"
)

# Concept: sprints (two-week periods with epoch start/end dates)
Sprint = Concept("Sprint", identify_by={"id": Integer})
Sprint.name = Property(f"{Sprint} has {String:name}")
Sprint.number = Property(f"{Sprint} has {Integer:number}")
Sprint.startdate = Property(f"{Sprint} has {Integer:startdate}")
Sprint.enddate = Property(f"{Sprint} has {Integer:enddate}")

# Concept: issues (EVENT TABLE — has epoch created_at, needs filtering)
# Raw data spans Sept-Nov 2024. `model/source.py` filters to the planning horizon.
Issue = Concept("Issue", identify_by={"id": Integer})
Issue.key = Property(f"{Issue} has {String:key}")
Issue.summary = Property(f"{Issue} has {String:summary}")
Issue.story_points = Property(f"{Issue} has {Integer:story_points}")
Issue.created_at = Property(f"{Issue} has {Integer:created_at}")
Issue.priority = Property(f"{Issue} has {Integer:priority}")
Issue.team = Property(f"{Issue} has {String:team}")
Issue.target_sprint_number = Property(
    f"{Issue} has target sprint {Integer:target_sprint_number}"
)

# Concept: developer-team skill mapping (which teams a developer can work on)
Skill = Concept("Skill", identify_by={"id": Integer})
Skill.developer_id = Property(f"{Skill} has {Integer:developer_id}")
Skill.team = Property(f"{Skill} has {String:team}")

# Decision concept: assignment of issue to developer in sprint
# Cross-product created from valid (developer, issue, sprint) combinations
# where the developer has the skill for the issue's team
Assignment = Concept("Assignment")
Assignment.developer = Property(f"{Assignment} has {Developer}", short_name="developer")
Assignment.issue = Property(f"{Assignment} has {Issue}", short_name="issue")
Assignment.sprint = Property(f"{Assignment} has {Sprint}", short_name="sprint")
Assignment.x_assigned = Property(f"{Assignment} is {Float:assigned}")
