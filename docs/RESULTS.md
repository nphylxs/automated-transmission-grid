# Reproducible study results

Commands: `python nerc.py`, `python datagen.py --samples 1000 --seed 42`, and `python train_model.py`. The manifests in `output/` identify the software versions, thresholds, and file hashes used for these results.

## Deterministic N-1 screen

The IEEE 30-bus model contains 41 in-service lines. The output has 42 cases: one base case and 41 single-line outages. Of the outage cases, 38 converged and 3 were islanded. Fourteen received a voltage/solvability flag, and 38 converged outages had at least one line over the 100% loading threshold. Nine outages introduced at least one overload absent from the base case. The base case itself has a 111.83% maximum line loading, so absolute thermal flags must be read alongside `new_overloaded_lines`.

An islanded case has no complete solved voltage or loading result. It is included in the 14 voltage/solvability flags but is not counted as a thermal flag.

## Randomized scenarios

All 1,000 requested scenarios were retained. Every case starts from the original network, uses independent 0.8-1.2 load scaling at each load, trips one line, and enforces generator reactive power limits in the AC power flow. There are 922 converged and 78 islanded cases. The defined `violation` target is positive for 334 cases. Scaled total demand is recalculated from the per-load values for each row.

## Prediction and limits

The seeded 80/20 stratified scenario holdout contains 200 cases. Its positive-class precision is **0.980**, recall **0.746**, F1 **0.847**, average precision **0.948**, and ROC AUC **0.960**. The confusion matrix is 132 true negatives, 1 false positive, 17 false negatives, and 50 true positives. This estimates performance on new load samples involving outage lines represented during training.

A separate holdout of 9 line IDs contains 206 cases. It has **zero positive predictions**: 139 true negatives and 67 false negatives, with ROC AUC **0.570**. The current model should therefore **not** be used to screen unseen line outages without physics-based analysis and further model development. Neither holdout measures performance on a real utility grid. The exact held-out line IDs and full metrics are in `output/model/metrics.json`.

This project studies one line outage at a time. It does not simulate cascading trips, relay behavior, transient stability, or NERC compliance.
