"""
Pre-defined queries and ToolRegistry for the employee directory Cortex agent.

Each query function must:
  - Return a rai.Fragment (a model.select(...) expression)
  - Have a clear docstring — shown to the LLM to decide when to call the query
  - Have a __name__ attribute — preserved by functools.wraps
"""
import functools

import relationalai.semantics as rai
from ontology import initialize
from relationalai.agent.cortex import (
    QueryCatalog,
    SourceCodeVerbalizer,
    ToolRegistry,
)
from relationalai.semantics import Model


def headcount_by_department(model: Model, Employee, ReportsTo) -> rai.Fragment:
    """
    Number of employees in each department.
    Use this to answer questions like 'how many people are in each team',
    'what is the headcount breakdown', or 'which department is largest'.
    Returns one row per department with an employee count.
    """
    emp = Employee.ref()
    g   = rai.per(emp.department)
    return model.select(
        emp.department.alias("department"),
        g.count(emp).alias("headcount"),
    )


def direct_reports(model: Model, Employee, ReportsTo) -> rai.Fragment:
    """
    Every employee and their direct manager — including both names, titles,
    and departments.
    Use this to answer questions like 'who does Alice report to', 'show me
    the reporting structure', or 'list all direct reports for a given manager'.
    Returns one row per (manager, direct-report) pair. Employees with no
    manager (e.g. department heads) are not included.
    """
    edge    = ReportsTo.ref()
    report  = Employee.ref()
    manager = Employee.ref()
    return model.select(
        manager.name.alias("manager_name"),
        manager.title.alias("manager_title"),
        manager.department.alias("department"),
        report.name.alias("report_name"),
        report.title.alias("report_title"),
    ).where(
        report.id   == edge.employee_id,
        manager.id  == edge.manager_id,
    )


def build_tool_registry(model: Model) -> ToolRegistry:
    """Build the ToolRegistry for the Cortex agent sproc."""
    Employee, ReportsTo = initialize(model)

    def _bind(fn, *args):
        @functools.wraps(fn)
        def wrapper():
            return fn(*args)
        return wrapper

    return ToolRegistry().add(
        model=model,
        description=(
            "Employee directory and org chart for the company. "
            "Contains all employees with their name, title, department, and "
            "reporting relationships. Use this model to answer questions about "
            "team size, headcount by department, reporting structure, and "
            "who reports to whom."
        ),
        verbalizer=SourceCodeVerbalizer(model, initialize),
        queries=QueryCatalog(
            _bind(headcount_by_department, model, Employee, ReportsTo),
            _bind(direct_reports,          model, Employee, ReportsTo),
        ),
    )
