"""Target sprints: the first sprint each issue can be assigned to, from when the issue was created."""

from relationalai.semantics.std import aggregates as aggs

from .schema import Issue, Sprint, model

# An issue created before a sprint starts is eligible from that sprint, and one created during a
# sprint targets it, so the target is the first sprint that ends after the issue was created. An
# issue created after the last sprint ended targets the last sprint.
_ending_after, _last = Sprint.ref(), Sprint.ref()
model.define(
    Issue.target_sprint_number(
        aggs.min(_ending_after.number).per(Issue).where(Issue.created_at < _ending_after.enddate)
        | aggs.max(_last.number)
    )
)
