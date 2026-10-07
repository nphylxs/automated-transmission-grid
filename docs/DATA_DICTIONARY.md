# Data dictionary

All bus and line identifiers are zero-based indices from `pandapower.networks.case30()`. `pu` is per-unit voltage magnitude, `MW` is active power, and loading is a percentage of the modeled line rating. A semicolon joins multiple element IDs in a CSV cell.

## Scenario summary: `output/n1/contingencies.csv` and `generate_dataset.csv`

| Column | Meaning |
| --- | --- |
| `scenario_id` | Stable identifier: `base`, `line_<id>`, or `sample_<number>`. |
| `outage_line` | Tripped line index; blank for the base case. |
| `from_bus`, `to_bus` | Endpoints of the tripped line in the model. |
| `total_demand_mw` | Sum of scaled active-power loads for this scenario. |
| `status` | `converged`, `islanded`, or `nonconverged`. |
| `failure_reason` | Reason a complete solved result is unavailable. |
| `min_v_pu`, `max_v_pu` | Minimum and maximum in-service bus voltages for a converged case. |
| `max_loading_percent` | Largest loading among in-service lines for a converged case. |
| `low_voltage_buses`, `high_voltage_buses` | Bus IDs outside the selected voltage range. |
| `overloaded_lines` | Line IDs above the selected loading threshold. |
| `unsupplied_buses` | Bus IDs disconnected from supply in an islanded case. |
| `voltage_violation` | 1 when a converged solution has a voltage threshold breach. |
| `thermal_violation` | 1 when a converged solution has a loading threshold breach. |
| `violation` | Model target: 1 for a voltage breach, islanded case, or nonconverged case. |
| `any_screen_violation` | 1 if `violation` or `thermal_violation` is 1. |
| `load_bus_<id>` | Scenario active-power demand in MW at a load bus. |

The deterministic N-1 file also has `new_overloaded_lines`, `new_low_voltage_buses`, `new_high_voltage_buses`, and `incremental_thermal_violation`. These compare a converged outage with the base case. Blank solved quantities in an islanded or nonconverged case mean **not calculated**, never zero or passing. `voltage_violation=0` for such a case does not mean its voltage is acceptable; use `violation` and `status` together.

## Detail and reference files

| File | Key columns and use |
| --- | --- |
| `output/n1/bus_results.csv` | `scenario_id`, `bus`, `vm_pu`, `below_min`, `above_max`; one row per in-service bus in each converged deterministic case. |
| `output/n1/line_results.csv` | `scenario_id`, `line`, `loading_percent`, `above_max`; tripped lines and unsolved cases have no result row. |
| `output/n1/bus_inventory.csv` | Source model bus attributes, including nominal voltage and in-service state. |
| `output/n1/line_inventory.csv` | Source model line endpoints, impedance, length, rating, and in-service state. |
| `output/n1/topology.md` | Renderable Mermaid network connectivity using the inventory IDs. |
| `output/model/test_predictions.csv` | Held-out `scenario_id`, actual/predicted label, and positive-class probability. |
| `output/model/feature_importance.csv` | Random Forest impurity-based feature importance; descriptive, not causal. |
| `output/*/manifest.json` | Run settings and SHA-256 hashes for evidence verification. |
