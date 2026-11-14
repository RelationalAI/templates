"""Shipment Compliance (logic reasoning) template.

This model declares derived business rules in RelationalAI:

- Load sample CSVs describing suppliers, SKUs, shipments, operations, BOMs, and demand.
- Define four rules as derived Relationships (boolean flags) on existing concepts.
- Query and display which entities match each rule.

Closed vocabularies (shipment status, demand priority) are modelled as
`model.Enum` types (requires relationalai>=1.12): CSV strings map to enum
members on load, rules compare against members instead of raw strings, and
queries read the member name back.

Rules defined:
  1. Shipment.is_late -- shipment arrived after expected date (delay_days > 0)
  2. Shipment.is_at_risk -- undelivered shipment from an unreliable supplier
  3. BillOfMaterials.is_single_sourced -- only one operation produces the input SKU
  4. Demand.is_escalated -- demand priority is HIGH or URGENT

No optimization solver is used. Rules are pure logic derivations.

Run:
    `rai models deploy --path model` deploys this package to the schemas in
    raiconfig.yaml and waits for its first refresh; `python -m
    queries.compliance_report` then prints the report from the deployed model.
"""

from . import reasoning
from .schema import BOM, Demand, Shipment, model
from .source import DATA_DIR

__all__ = ["BOM", "DATA_DIR", "Demand", "Shipment", "model", "reasoning"]
