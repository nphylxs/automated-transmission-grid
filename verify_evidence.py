"""Verify generated study artifacts and internal consistency."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


def verify_hashes(manifest_path: Path, base_dir: Path | None = None) -> dict:
    manifest = json.loads(manifest_path.read_text())
    files = manifest.get("files_sha256")
    if not isinstance(files, dict) or not files:
        raise ValueError(f"Missing file hashes in {manifest_path}")
    for name, expected in files.items():
        path = Path(name)
        if not path.is_absolute():
            path = (base_dir or Path.cwd()) / path
        if not path.is_file():
            raise ValueError(f"Missing evidence file: {path}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"Hash mismatch: {path}")
    return manifest


def verify_project(root: Path) -> dict:
    """Check hashes, scenario coverage, demand arithmetic, and model traceability."""
    root = root.resolve()
    n1 = verify_hashes(root / "output/n1/manifest.json", root)
    dataset_manifest = verify_hashes(root / "output/dataset/manifest.json", root)
    model_manifest = verify_hashes(root / "output/model/manifest.json", root)

    contingencies = pd.read_csv(root / "output/n1/contingencies.csv")
    lines = pd.read_csv(root / "output/n1/line_inventory.csv")
    active_lines = set(lines.loc[lines.in_service, "line"].astype(int))
    studied_lines = contingencies.loc[contingencies.scenario_id != "base", "outage_line"]
    if len(contingencies) != len(active_lines) + 1 or contingencies.scenario_id.iloc[0] != "base":
        raise ValueError("N-1 table does not contain the base case and every active line")
    if studied_lines.isna().any() or set(studied_lines.astype(int)) != active_lines or studied_lines.duplicated().any():
        raise ValueError("N-1 table has missing, extra, or duplicate line outages")
    if len(contingencies) != n1["scenarios"]:
        raise ValueError("N-1 manifest scenario count differs from the table")

    dataset_path = root / "generate_dataset.csv"
    dataset = pd.read_csv(dataset_path)
    loads = [column for column in dataset if column.startswith("load_bus_")]
    if len(dataset) != dataset_manifest["samples"] or dataset.scenario_id.duplicated().any():
        raise ValueError("Dataset count or scenario identifiers are inconsistent")
    if not loads or not np.allclose(dataset[loads].sum(axis=1), dataset.total_demand_mw, atol=1e-6):
        raise ValueError("Dataset scaled loads do not sum to total demand")
    if not set(dataset.status.unique()).issubset({"converged", "islanded", "nonconverged"}):
        raise ValueError("Dataset contains an unknown study status")
    if (dataset.loc[dataset.status != "converged", "violation"] != 1).any():
        raise ValueError("Unsolved cases must carry a violation flag")
    if model_manifest["dataset_sha256"] != hashlib.sha256(dataset_path.read_bytes()).hexdigest():
        raise ValueError("Model manifest points to a different dataset")

    metrics = json.loads((root / "output/model/metrics.json").read_text())
    predictions = pd.read_csv(root / "output/model/test_predictions.csv")
    if metrics["dataset_sha256"] != model_manifest["dataset_sha256"]:
        raise ValueError("Model metrics point to a different dataset")
    if len(predictions) != metrics["test_rows"] or predictions.scenario_id.duplicated().any():
        raise ValueError("Held-out prediction count or identifiers are inconsistent")
    if not set(predictions.scenario_id).issubset(set(dataset.scenario_id)):
        raise ValueError("Held-out predictions reference unknown scenarios")
    reference = dataset.set_index("scenario_id").loc[predictions.scenario_id]
    if not np.array_equal(predictions.actual.to_numpy(), reference.violation.to_numpy()):
        raise ValueError("Held-out labels differ from the source scenarios")
    if not np.array_equal(predictions.outage_line.to_numpy(), reference.outage_line.to_numpy()):
        raise ValueError("Held-out outage IDs differ from the source scenarios")
    if not np.all((predictions.risk_probability >= 0) & (predictions.risk_probability <= 1)):
        raise ValueError("Predicted probabilities are outside [0, 1]")
    if not np.array_equal(predictions.predicted.to_numpy(),
                          (predictions.risk_probability >= 0.5).astype(int).to_numpy()):
        raise ValueError("Predicted labels differ from the 0.5 decision threshold")
    cm = metrics["confusion_matrix"]
    actual = predictions.actual.to_numpy()
    predicted = predictions.predicted.to_numpy()
    calculated_cm = {
        "true_negative": int(((actual == 0) & (predicted == 0)).sum()),
        "false_positive": int(((actual == 0) & (predicted == 1)).sum()),
        "false_negative": int(((actual == 1) & (predicted == 0)).sum()),
        "true_positive": int(((actual == 1) & (predicted == 1)).sum()),
    }
    if cm != calculated_cm:
        raise ValueError("Confusion matrix differs from held-out predictions")
    return {"n1_cases": len(contingencies), "dataset_cases": len(dataset),
            "test_cases": len(predictions), "verified_manifests": 3}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    result = verify_project(args.root)
    print("Evidence verified: " + ", ".join(f"{key}={value}" for key, value in result.items()))


if __name__ == "__main__":
    main()
