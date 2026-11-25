"""Load the sample runners, workflows, and compatibility pairs, and check the outage's runners exist."""

from pathlib import Path

from pandas import read_csv

from .schema import Compatibility, Runner, Workflow, model

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# Maintenance outage: take two well-connected Linux runners offline. Every high-CPU
# Linux job (min_cpu >= 4) is compatible only with runners in {ubuntu-large,
# ubuntu-xlarge, self-hosted-linux} (the two min_cpu=8 jobs with just the latter
# two); with ubuntu-large and self-hosted-linux down, all seven funnel onto the one
# survivor -- whose concurrency cap cannot hold them.
OFFLINE_RUNNERS = ["ubuntu-large", "self-hosted-linux"]

runner_csv = read_csv(DATA_DIR / "runners.csv")
runner_data = model.data(runner_csv)
model.define(
    r := Runner.new(runner_id=runner_data["id"]),
    r.name(runner_data["name"]),
    r.os(runner_data["os"]),
    r.cpu(runner_data["cpu"]),
    r.memory_gb(runner_data["memory_gb"]),
    r.cost_per_minute(runner_data["cost_per_minute"]),
    r.max_concurrent(runner_data["max_concurrent"]),
)

workflow_csv = read_csv(DATA_DIR / "workflows.csv")
wf_data = model.data(workflow_csv)
model.define(
    w := Workflow.new(workflow_id=wf_data["id"]),
    w.name(wf_data["name"]),
    w.event(wf_data["event"]),
    w.required_os(wf_data["required_os"]),
    w.min_cpu(wf_data["min_cpu"]),
    w.min_memory_gb(wf_data["min_memory_gb"]),
    w.estimated_minutes(wf_data["estimated_minutes"]),
)

compat_csv = read_csv(DATA_DIR / "compatibility.csv")
compat_data = model.data(compat_csv)
CompatWorkflow = Workflow.ref()
CompatRunner = Runner.ref()
model.define(Compatibility.new(workflow=CompatWorkflow, runner=CompatRunner)).where(
    CompatWorkflow.workflow_id == compat_data["workflow_id"],
    CompatRunner.runner_id == compat_data["runner_id"],
)

# Guard against CSV drift: the offline runners (and ubuntu-xlarge, the survivor) must exist
# in runners.csv, or the outage's where= exclusion silently excludes nothing and the outage
# stays feasible.
if not set(OFFLINE_RUNNERS) | {"ubuntu-xlarge"} <= set(runner_csv["name"]):
    raise ValueError(
        f"runners.csv changed: expected {sorted(set(OFFLINE_RUNNERS) | {'ubuntu-xlarge'})} "
        f"among {sorted(runner_csv['name'])}"
    )
