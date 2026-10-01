"""
Employee directory ontology definition.

Defines the RAI model for an employee org-chart sourced from a single
Snowflake table where each row represents one employee with a reference
to their manager.

Import `initialize` into any script that needs to build or query the model.
"""
import os as _os

import relationalai.semantics as rai
from relationalai.semantics import String


def _read_source_table() -> str:
    _config_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "rai-agent-config.yaml")
    try:
        import yaml as _yaml
        with open(_config_path) as _f:
            return _yaml.safe_load(_f)["model"]["source_table"]
    except (FileNotFoundError, KeyError, ImportError):
        return "MY_DB.MY_SCHEMA.EMPLOYEES"   # fallback — update to match your config


SOURCE_TABLE = _read_source_table()


def initialize(model: rai.Model):
    """
    Employee org-chart model sourced from the EMPLOYEES table.

    Each row in the source table represents one employee. The model
    derives two concepts:

    - Employee: one instance per unique EMPLOYEE_ID. Has a department
      (e.g. Engineering, Product, Design) and a title (e.g. Senior Engineer).
    - ReportsTo: one instance per (manager, direct-report) pair, derived
      from the MANAGER_ID foreign key. Rows with a null MANAGER_ID (e.g.
      department heads) have no ReportsTo edge and are treated as root nodes.

    Use this model to answer questions about team size, reporting structure,
    and org hierarchy.
    """
    src = model.Table(SOURCE_TABLE)

    # -------------------------------------------------------------------------
    # Concepts
    # -------------------------------------------------------------------------
    Employee = model.Concept("Employee", identify_by={"id": String})

    # One edge per (manager, report) pair — null MANAGER_ID rows are silently
    # skipped by null propagation, so department heads have no ReportsTo entry.
    ReportsTo = model.Concept(
        "ReportsTo",
        identify_by={"manager_id": String, "employee_id": String},
    )

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------
    Employee.department = model.Property(f"{Employee} works in {String:department}")
    Employee.title      = model.Property(f"{Employee} has title {String:title}")
    Employee.name       = model.Property(f"{Employee} has name {String:name}")

    # -------------------------------------------------------------------------
    # Seed employees from source table
    # -------------------------------------------------------------------------
    # Each row contributes the employee themselves …
    model.define(
        emp := Employee.new(id=src.EMPLOYEE_ID),
        emp.department(src.DEPARTMENT),
        emp.title(src.TITLE),
        emp.name(src.NAME),
    )
    # … and, when MANAGER_ID is non-null, their manager as well.
    model.define(
        Employee.new(id=src.MANAGER_ID),
    )

    # -------------------------------------------------------------------------
    # Seed reporting edges
    # -------------------------------------------------------------------------
    # Null MANAGER_ID rows are dropped automatically — no sentinel needed.
    model.define(
        ReportsTo.new(manager_id=src.MANAGER_ID, employee_id=src.EMPLOYEE_ID)
    )

    return Employee, ReportsTo
