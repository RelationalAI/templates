# Full-Scale Machine Maintenance Data

Original dataset before reduction for RAI query size limits.

- 50 machines, 40 technicians, 12 periods, 480 availability rows
- Cross-product: 50 x 40 x 12 = 24,000 TechnicianMachinePeriod entities

To use: copy these CSVs to parent directory and set `PERIOD_HORIZON = 12` in the base model / template.

Reduced to 10 x 10 x 4 = 400 entities to stay under RAI AST size threshold (~20K nodes).
