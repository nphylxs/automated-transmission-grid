# Architecture and design decisions

## Data flow

```text
pandapower IEEE 30-bus case
       |
       +--> nerc.py --> grid_study.export_n1_study()
       |                    |--> base case + each of 41 line outages
       |                    |--> summary, bus/line results, inventories, diagram
       |                    +--> output/n1/manifest.json
       |
       +--> datagen.py --> grid_study.export_dataset()
       |                    |--> 1,000 independent load/outage cases
       |                    |--> generate_dataset.csv
       |                    +--> output/dataset/manifest.json
       |
       +--> train_model.py --> Random Forest pipeline
                            |--> scenario and line-group holdouts
                            |--> metrics, predictions, feature importance, model
                            +--> output/model/manifest.json

verify_evidence.py --> hash and consistency checks across all three packages
```

## Why each case uses a fresh network

`run_case()` copies the original model before changing load scaling or line service state. This guarantees that sample N+1 starts from the original 30-bus case rather than inheriting the outage from sample N. An older version of the project accidentally accumulated outages, so this isolation is a correctness requirement. The test suite checks repeatability and source-network preservation.

## Electrical model

For each line contingency, the script marks one line out of service, checks whether buses become unsupplied, and runs an AC power flow with `enforce_q_lims=True` if the topology remains supplied. It records bus voltage magnitudes and active-line loading percentages. Thresholds are user-selected study screens; the defaults are 0.95-1.05 pu and 100% loading. An unsupplied or nonconverged case is a flagged study outcome with blank solved measurements.

The deterministic study compares each outage with the base case, so an existing base-case overload is distinguishable from a new overload introduced by a contingency. The topology diagram is generated from line endpoints. It shows connectivity, not switchgear details, relays, physical placement, or a field-verified one-line.

## Prediction model

The Random Forest uses only the planned outage line ID and the scaled MW demand at each load bus. These inputs exist before solving a scenario. Solved voltages, line loadings, status, and total demand are excluded from the feature matrix, avoiding direct target leakage. Its target is `violation`: a voltage-limit breach or an islanded/nonconverged case. Thermal loading is a separate screen.

The stratified scenario holdout assesses new load samples on lines also represented during training. The line-group holdout assesses transfer to unseen line IDs in the same test network. The latter currently fails to identify positives; the model is a research demonstration and cannot replace the physics study. See [RESULTS.md](RESULTS.md) for exact figures.

## Traceability

Every export records a manifest with source, thresholds or model configuration, package versions, counts, and SHA-256 output hashes. `verify_evidence.py` verifies the hashes plus expected case coverage, demand arithmetic, labels, and model prediction references. A changed input or output requires regeneration of its manifest; retained manifests should never be edited to conceal a mismatch.
