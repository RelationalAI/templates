"""Semantic schema for the cicd_runner_allocation template: runners, workflows, compatibility, and assignments."""

from relationalai.semantics import Float, Integer, Model, String

model = Model("cicd_runner_allocation")

# Runner concept: CI/CD runner types with resource specs, cost, and capacity.
Runner = model.Concept("Runner", identify_by={"runner_id": Integer})
Runner.name = model.Property(f"{Runner} has {String:runner_name}")
Runner.os = model.Property(f"{Runner} has {String:runner_os}")
Runner.cpu = model.Property(f"{Runner} has {Integer:cpu}")
Runner.memory_gb = model.Property(f"{Runner} has {Integer:memory_gb}")
Runner.cost_per_minute = model.Property(f"{Runner} has {Float:cost_per_minute}")
Runner.max_concurrent = model.Property(f"{Runner} has {Integer:max_concurrent}")

# Workflow concept: CI/CD jobs with resource requirements and estimated duration.
Workflow = model.Concept("Workflow", identify_by={"workflow_id": Integer})
Workflow.name = model.Property(f"{Workflow} has {String:workflow_name}")
Workflow.event = model.Property(f"{Workflow} has {String:workflow_event}")
Workflow.required_os = model.Property(f"{Workflow} has {String:required_os}")
Workflow.min_cpu = model.Property(f"{Workflow} has {Integer:min_cpu}")
Workflow.min_memory_gb = model.Property(f"{Workflow} has {Integer:min_memory_gb}")
Workflow.estimated_minutes = model.Property(f"{Workflow} has {Integer:estimated_minutes}")

# Compatibility concept: which runners can execute which workflows.
# Pre-computed from OS match and resource requirements.
Compatibility = model.Concept("Compatibility", identify_by={"workflow": Workflow, "runner": Runner})

# Assignment concept: (workflow, runner) pairs -- the decision space.
# Only compatible pairs exist.
Assignment = model.Concept("Assignment", identify_by={"workflow": Workflow, "runner": Runner})
Assignment.x_assigned = model.Property(f"{Assignment} assigned {Float:x_assigned}")
