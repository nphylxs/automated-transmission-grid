# N-1 study procedure and evidence checklist

## 1. Scope and inputs

1. Record the network source (`pandapower.networks.case30()`), package versions, study date, and analyst. The scripts record date and versions in manifests; the analyst must add their own identity to any formal work package.
2. Review `output/n1/bus_inventory.csv` and `line_inventory.csv` for bus IDs, line endpoints, ratings, and in-service status. Treat these as model inputs, not as field-verified equipment records or a substation drawing.
3. Choose and document voltage and loading thresholds before running the study. The defaults (0.95-1.05 pu, 100%) are example screens. Keep any changed command line with the package.

## 2. Execute

Run `python nerc.py` for the base case and every in-service line outage. Each case starts from a fresh copy of the network. The solver enforces generator reactive limits. Run `python datagen.py --samples 1000 --seed 42` for independent load samples, then `python train_model.py` for the predictive study.

## 3. Review engineering exceptions

1. Confirm that `contingencies.csv` contains one `base` row and one row per in-service line. Match every `outage_line` to the line inventory's endpoints.
2. Investigate each `status` other than `converged`. `islanded` records unsupplied bus IDs; `nonconverged` records the solver reason. Blank solved values are **unknown**, not passes.
3. For converged cases, review `low_voltage_buses`, `high_voltage_buses`, and `overloaded_lines`. Use `bus_results.csv` and `line_results.csv` for measured values. `new_overloaded_lines`, `new_low_voltage_buses`, and `new_high_voltage_buses` compare each case with the base case.
4. Review generator and line input ratings for suitability before using a finding in an operational decision. The example case and generic thresholds are not substitutes for approved utility data.

## 4. Retain and verify evidence

Keep the case inventories, scenario and element results, dataset, model metrics, test predictions, commands, and all three manifests together. Each manifest contains SHA-256 hashes of its output files. To verify the package, recalculate a file hash with `sha256sum <path>` and compare it with `files_sha256` in its manifest. Store any review comments, corrections, and approval records with the package under the organization's normal retention procedure. Re-run after changing inputs or software and keep the new package distinct from the old one.

The model metrics include the dataset hash and the scenario IDs in the held-out predictions. Do not infer compliance from a machine-learning score; the physics-based scenario results remain the study evidence.
