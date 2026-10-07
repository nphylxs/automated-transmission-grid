# Project explained

## What problem does it explore?

A transmission planner asks whether a network can still operate acceptably after one component is removed. This is an **N-1 contingency** study: N is the normal collection of in-service elements; minus 1 means one line is out. Here the network is the IEEE 30-bus example supplied with pandapower. It is a teaching and research model, not Seminole Electric's network.

The project has two layers. The AC power-flow layer calculates what happens to voltages and line loading after an outage. The machine-learning layer learns from many such solved cases and estimates whether a new scenario will be flagged. The physics-based results are the evidence; the classifier is an experimental shortcut.

## What happens in one study case?

1. Start with an untouched copy of the 30-bus model. A bus is a connection point; a line links two buses. Generators and loads are attached to buses.
2. Optionally scale each load between 80% and 120% of its modeled MW value. Record the actual scaled demand, not the original nominal demand.
3. Switch one line out of service. Check whether any buses are disconnected from supply. If so, mark the case `islanded` and retain those bus IDs.
4. Otherwise run pandapower's AC power flow with generator reactive-power limits enforced. Reactive power supports voltage; respecting its limits makes the screen more realistic than assuming unlimited voltage support.
5. For a converged solution, compare each bus voltage with 0.95-1.05 pu and each line loading with 100%. A voltage of 1.00 pu means the modeled nominal level; 0.95 pu is 5% below it. A loading of 110% means the model reports 10% above the selected rating threshold.
6. Export the summary and, for the deterministic study, detailed results at each bus and active line. Compare outage results with the base case to identify newly introduced violations.

The script repeats this for all 41 lines. It also runs 1,000 randomized load-and-outage scenarios using a fixed random seed so another analyst can reproduce the same dataset. Each scenario gets a fresh network copy; this matters because an earlier version accidentally kept old outages active.

## What does the model learn?

Its inputs are the outaged line ID and 20 scaled load values. Its label is `violation=1` for a voltage threshold breach, islanded case, or nonconverged solution. It does **not** predict thermal overloads or a sequence of cascading trips. It uses a Scikit-Learn Random Forest, which combines many decision trees and returns a probability-like risk score.

On a 200-case test set containing familiar line IDs, the model had 0.980 precision and 0.746 recall: when it flagged a case it was usually right, but it missed 17 of 67 actual flagged cases. On a separate holdout containing unseen line IDs, it missed all 67 flagged cases. This is the key limitation: outage identity is very important, and the learned pattern does not transfer reliably to new lines. For a new line, run the power flow rather than relying on the classifier.

## What makes this an engineering project?

The project keeps the network input inventory, a connectivity diagram, selected limits, solver configuration, per-element measurements, all attempted scenarios, exception reasons, software versions, test predictions, and cryptographic file hashes. The technical procedure explains how to review exceptions and verify the package. Tests check case independence, demand arithmetic, outage coverage, and tamper detection. These practices make results repeatable and reviewable, while keeping clear that the example model and thresholds are not a NERC compliance determination.

## A 45-second interview explanation

> I built a Python and pandapower planning study on the IEEE 30-bus test network. It runs the base case and all 41 single-line outages, flags voltage, line-loading, and islanding conditions, and identifies new overloads compared with the base case. I then generated 1,000 reproducible cases with varied loads and enforced generator reactive-power limits. The outputs include equipment inventories, a network diagram, detailed results, and hashed manifests so another engineer can review the study. I trained a Random Forest on pre-study inputs and evaluated it on both familiar and unseen outage lines. The unseen-line test exposed a serious generalization limit, so I treat the model as a research aid and keep the AC power flow as the engineering basis.

## Where to look next

Start with `output/n1/contingencies.csv`. Pick one `scenario_id`, inspect its buses or overloaded line IDs, then look up their measured values in `bus_results.csv` or `line_results.csv` and their connectivity in `line_inventory.csv` or `topology.md`. Read [DATA_DICTIONARY.md](DATA_DICTIONARY.md) for each field and [STUDY_PROCEDURE.md](STUDY_PROCEDURE.md) for the review workflow.
