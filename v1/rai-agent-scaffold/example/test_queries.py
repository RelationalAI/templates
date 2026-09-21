"""
Quick smoke test: run both agent queries locally against the EMPLOYEES table.

Copy this file to the parent directory (alongside si_agent.py) and run:
    RAI_CONFIG_FILE_PATH=raiconfig.yaml python test_queries.py
"""
import relationalai.semantics as rai
from ontology import initialize
from relationalai.config import SnowflakeConnection, create_config

print("Connecting to Snowflake...")
session = create_config().get_session(SnowflakeConnection)
print(f"Connected: {session.get_current_account()} / {session.get_current_role()}\n")

model = rai.Model("EMPLOYEE_DIRECTORY_TEST")
Employee, ReportsTo = initialize(model)

# ---- Query 1: headcount by department --------------------------------------
print("=" * 60)
print("QUERY 1: headcount_by_department")
print("=" * 60)
emp = Employee.ref()
g   = rai.per(emp.department)
# Note: local .to_df() may return one row per (emp, department) because `emp`
# remains a free variable. .drop_duplicates() gives the correct per-department
# summary. The deployed sproc returns correctly aggregated results.
df1 = model.select(
    emp.department.alias("department"),
    g.count(emp).alias("headcount"),
).to_df().drop_duplicates()
print(df1.to_string(index=False))
print()

# ---- Query 2: direct reports -----------------------------------------------
print("=" * 60)
print("QUERY 2: direct_reports")
print("=" * 60)
edge    = ReportsTo.ref()
report  = Employee.ref()
manager = Employee.ref()

df2 = model.select(
    manager.name.alias("manager_name"),
    manager.title.alias("manager_title"),
    manager.department.alias("department"),
    report.name.alias("report_name"),
    report.title.alias("report_title"),
).where(
    report.id   == edge.employee_id,
    manager.id  == edge.manager_id,
).to_df()
print(df2.to_string(index=False))
print()
print("Done.")
