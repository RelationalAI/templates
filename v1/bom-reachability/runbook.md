# BOM Reachability — Analyst Runbook

A supply-chain analyst wants the full multi-tier dependency picture of a product line — not just each finished good's direct inputs, but every raw material it ultimately relies on, and which components are structural bottlenecks whose disruption would ripple across the most products. The dataset is a 9-SKU consumer-electronics product structure (raw materials, components, two finished goods) wired by 14 site-specific bill-of-materials entries. The analysis traces transitive dependencies, ranks bottleneck components, and enumerates the end-to-end assembly chains that build each finished good.

```text
BOM graph  (9 SKUs across 3 tiers, 10 dependency edges from 14 site-specific BOM rows)
      │
      ▼
/rai-graph-analysis  — Reachability, betweenness, path enumeration (paths: relationalai>=1.15)
   • transitive dependencies per finished good (reachable)       -> 7 each
   • structural bottleneck component (betweenness centrality)    -> Mobile Processor A15 = 4.0
   • every raw-material to finished-good assembly chain (paths)  -> 18 paths
   • maximal chains + persist SKU.assembly_depth                 -> 8 maximal, depth 2
```

These prompts are designed to run in order in a single session: the assembly-path and depth steps read the `BillOfMaterials` relationships the build step established, and the final step persists `SKU.assembly_depth` back onto the ontology.

---

## 1. Build the ontology

**Prompt:** Build a RelationalAI ontology from `data/skus.csv` and `data/bill_of_materials.csv`. Each SKU has an id, name, type (`RAW_MATERIAL`, `COMPONENT`, or `FINISHED_GOOD`), and category. Each bill-of-materials entry links an output SKU (what is produced) to an input SKU (what it requires), and may be site-specific. Model `BillOfMaterials` as an edge between SKUs so we can trace what depends on what.

**Response:** Loads 9 `SKU` nodes (properties `name`, `type`, `category`) and a `BillOfMaterials` edge concept with `output_sku` / `input_sku` relationships from the 14 BOM rows. Several rows are site-specific duplicates (e.g. SKU001 is assembled at both S001 and S012), so the 14 entries collapse to 10 distinct output→input dependency edges; the duplicate-edge warning is informational.

## 2. Examine the ontology

**Prompt:** What concepts and relationships does the ontology have, and how is the product structure tiered?

**Response:** One concept, `SKU`, with properties `name`, `type`, and `category`, plus the `BillOfMaterials` edge carrying `output_sku` / `input_sku`. The 9 SKUs span three tiers — 4 raw materials (wafer, display glass, lithium cells, NAND die), 3 components (Mobile Processor A15, OLED Display Panel 6.1, Lithium Battery Pack 4500mAh), and 2 finished goods (ProPhone X1, ProTab T1) — joined by 10 "produces → requires" edges that always point a higher tier down to a lower one.

## 3. Transitive dependencies of each finished good

**Prompt:** For each finished good, what does it ultimately depend on — every component and raw material reachable through the bill of materials, not just its direct inputs? Break the dependencies down by type.

**Response:** Both finished goods depend on the same 7 SKUs: 3 components (Mobile Processor A15, OLED Display Panel 6.1, Lithium Battery Pack 4500mAh) and 4 raw materials (Silicon Wafer 300mm, Display Glass Panel 6.5in, Lithium Ion Cells 18650, NAND Flash Memory Die). Transitive reachability surfaces the raw materials a direct-inputs list would miss — ProPhone X1 lists the processor as a direct input, and reachability adds the wafer and flash die two tiers down. Across the whole graph there are 27 reachable (product, dependency) pairs.

## 4. Structural bottleneck components

**Prompt:** Which components are the structural bottlenecks — the ones sitting on the most dependency paths between finished goods and raw materials, so disrupting them would ripple across the most products? Contrast that with which SKUs are simply depended on by the most others.

**Response:** Betweenness centrality ranks Mobile Processor A15 highest at 4.0 — it lies on every path from both finished goods down to the wafer and flash die, so it is the single most disruptive component. OLED Display Panel 6.1 and Lithium Battery Pack 4500mAh follow at 2.0; raw materials and finished goods score 0 because they are the ends of every chain, never the middle. By raw count the four raw materials are each depended on by 3 SKUs and the three components by 2 — but "most depended-on" (a sink) is not the same as "bottleneck" (a node on the most paths), which is why betweenness, not the dependency count, points at the processor.

## 5. Assembly chains that build each finished good (paths, requires `relationalai>=1.15`)

**Prompt:** Reachability gives dependency pairs, but we want the actual build sequences. Enumerate every bottom-up assembly chain — each ordered route from a raw material up through its components to a finished good. Treat an input that feeds an output as a step in the chain.

**Response:** Where reachability returns pairs, path enumeration returns the ordered build routes. Deriving a SKU→SKU "feeds into" edge from the `BillOfMaterials` intermediary (input feeds output — the reverse of "depends on") and enumerating it with `.all_paths()` yields 18 assembly paths (up to 4 hops). Because the BOM is acyclic, every enumerated path is already a simple chain — no cycle risk. They range from 1-hop direct feeds (e.g. Mobile Processor A15 → ProPhone X1) to 2-hop chains like NAND Flash Memory Die → Mobile Processor A15 → ProPhone X1.

## 6. Maximal chains and assembly depth

**Prompt:** The full path set repeats every sub-chain. Reduce it to just the maximal end-to-end chains — the longest routes not contained inside a longer one — and record each finished good's assembly depth, the length of the deepest chain that builds it.

**Response:** 8 of the 18 paths are maximal; the other 10 are shorter sub-chains contained inside them. All 8 maximal chains are 2-hop raw-material → component → finished-good routes (e.g. Silicon Wafer 300mm → Mobile Processor A15 → ProTab T1). Both finished goods have an assembly depth of 2, persisted back onto the ontology as `SKU.assembly_depth` so a later query can rank products by build complexity without re-enumerating paths.
