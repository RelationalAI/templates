"""Compliance report: reads the deployed shipment-compliance model.

Run after `rai models deploy --path model`:
    python -m queries.compliance_report

Prints which entities match each compliance rule: late shipments, at-risk
shipments, single-sourced BOM inputs, and escalated demands.
"""

from model import BOM, Demand, Shipment, model

if __name__ == "__main__":
    print("=== Rule 1: Late Shipments (delay_days > 0) ===\n")
    model.select(
        Shipment.id.alias("shipment_id"),
        Shipment.sku.name.alias("sku"),
        Shipment.supplier.name.alias("supplier"),
        Shipment.delay_days.alias("delay_days"),
    ).where(Shipment.is_late()).inspect()

    print("\n=== Rule 2: At-Risk Shipments (undelivered + unreliable supplier) ===\n")
    model.select(
        Shipment.id.alias("shipment_id"),
        Shipment.sku.name.alias("sku"),
        Shipment.supplier.name.alias("supplier"),
        Shipment.status.name.alias("status"),
        Shipment.supplier.reliability_score.alias("reliability"),
    ).where(Shipment.is_at_risk()).inspect()

    print("\n=== Rule 3: Single-Sourced BOM Inputs (only 1 operation route) ===\n")
    model.select(
        BOM.id.alias("bom_id"),
        BOM.input_sku.name.alias("input_sku"),
        BOM.input_quantity.alias("qty"),
    ).where(BOM.is_single_sourced()).inspect()

    print("\n=== Rule 4: Escalated Demands (HIGH or URGENT priority) ===\n")
    model.select(
        Demand.id.alias("demand_id"),
        Demand.sku.name.alias("sku"),
        Demand.quantity.alias("quantity"),
        Demand.priority.name.alias("priority"),
    ).where(Demand.is_escalated()).inspect()
