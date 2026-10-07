# ML-enhanced transmission grid simulator

This project runs an AC power-flow planning screen on pandapower's IEEE 30-bus example, studies every in-service line outage, generates 1,000 randomized N-1 scenarios, and trains a Random Forest to predict voltage/solvability flags from information available **before** the outage study. It also retains scenario-level results, equipment inventories, detailed bus and line results, thresholds, software versions, and SHA-256 file hashes.

New to the project? Read [Project explained](docs/PROJECT_EXPLAINED.md), then the [documentation index](docs/README.md). The electrical model, data flow, and label choices are described in [Architecture](docs/ARCHITECTURE.md) and the [Data dictionary](docs/DATA_DICTIONARY.md).

## Run the study

Python 3.11 or newer is recommended. From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python nerc.py
python datagen.py --samples 1000 --seed 42
python train_model.py
```

To run the integration checks, install `requirements-dev.txt` and run `python -m pytest -q`. Run `python verify_evidence.py` to verify all retained file hashes and cross-file consistency. The equivalent Make targets are `make PYTHON=.venv/bin/python study`, `test`, and `verify`. The GitHub Actions workflow runs tests and evidence verification on changes.

The commands write:

| Path | Contents |
| --- | --- |
| `output/n1/contingencies.csv` | Base case plus one row per line outage, with status, voltage, loading, affected element IDs, and new violations versus base |
| `output/n1/bus_results.csv`, `line_results.csv` | Element-level results for converged deterministic cases |
| `output/n1/bus_inventory.csv`, `line_inventory.csv` | Case data and bus/line connectivity for checking study inputs |
| `output/n1/topology.md` | Mermaid connectivity diagram with bus and line indices |
| `output/n1/manifest.json` | Thresholds, solver settings, versions, and hashes |
| `generate_dataset.csv` | One row for each sampled, independent N-1 case |
| `output/dataset/manifest.json` | Random seed, sample count, labeling rule, statuses, and dataset hash |
| `output/model/metrics.json` | Held-out classifier metrics and confusion matrix |
| `output/model/test_predictions.csv`, `feature_importance.csv` | Individual predictions and model diagnostics |
| `output/model/manifest.json` | Dataset and model-output hashes |
| `output/model/model.joblib` | Trained pipeline for local use |

The equipment inventories and diagram serve as a **connectivity and data reference**, not an engineered substation one-line drawing. Bus and line IDs use pandapower's zero-based case indices. The `from_bus` and `to_bus` columns map each outage to the case data.

## Screening rules and interpretation

Defaults are 0.95-1.05 pu bus voltage and 100% line loading. They are configurable in `nerc.py` and `datagen.py`. `pp.runpp(..., enforce_q_lims=True)` applies generator reactive limits in solved cases. An islanded or nonconverged scenario receives `violation=1`; its voltage and thermal outputs remain blank because no valid complete solution exists. For converged scenarios, `violation` is the voltage threshold flag and `thermal_violation` is recorded separately. `any_screen_violation` combines them.

These are **demonstration study thresholds**, not a claim of NERC compliance. Determining compliance requires the applicable standard, facility ratings, approved models, study conditions, and an organization's documented process. The simulator does not model protection actions, sequential cascading outages, dynamic stability, or actual utility equipment. The classifier predicts the defined single-contingency screen outcome, not cascading failures.

The supplied case has a base-case line above the 100% loading threshold. This is why thermal findings are retained separately. `new_overloaded_lines` and `incremental_thermal_violation` identify overloads that were absent in the base case.

## Model evaluation

The classifier uses only the selected outaged line and scaled pre-study MW loads at each load bus. Solved voltages, line loadings, status, and total demand are excluded from features. A seeded stratified 80/20 holdout measures performance for **new load samples across the same set of line IDs**. A second, line-group holdout tests unseen line IDs in this same network. Neither tests transfer to a different grid. See `output/model/metrics.json` for the measured results; no accuracy number is hard-coded in the documentation.

## Study and evidence workflow

Follow [docs/STUDY_PROCEDURE.md](docs/STUDY_PROCEDURE.md) to rerun the screen, check exceptions, verify hashes, and retain a traceable study package. [docs/RESULTS.md](docs/RESULTS.md) records the current study findings and model limitations; update that snapshot after regenerating the outputs. This project supports engineering planning and technical documentation practice; it is not an operational or compliance system.
