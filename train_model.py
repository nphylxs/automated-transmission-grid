"""Train and evaluate a voltage/solvability risk classifier from pre-outage inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (average_precision_score, confusion_matrix,
                             f1_score, precision_score, recall_score, roc_auc_score)
from sklearn.model_selection import GroupShuffleSplit, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


def validate_dataset(frame: pd.DataFrame) -> list[str]:
    loads = sorted((name for name in frame.columns if name.startswith("load_bus_")),
                   key=lambda name: int(name.removeprefix("load_bus_")))
    required = ["scenario_id", "outage_line", "total_demand_mw", "status", "violation", *loads]
    if not loads or any(name not in frame for name in required):
        raise ValueError("Dataset lacks required scenario, load, or label columns")
    if frame[required].isna().any().any() or frame.scenario_id.duplicated().any():
        raise ValueError("Dataset contains missing inputs/labels or duplicate scenario IDs")
    if not set(frame.violation.unique()).issubset({0, 1}) or frame.violation.nunique() != 2:
        raise ValueError("The violation label must contain both 0 and 1")
    if not np.allclose(frame[loads].sum(axis=1), frame.total_demand_mw, atol=1e-6):
        raise ValueError("Total demand does not match scaled bus loads; regenerate the dataset")
    if len(frame) < 20 or frame.violation.value_counts().min() < 3:
        raise ValueError("Need at least 20 scenarios and three cases in each class")
    return loads


def _scores(truth, probability) -> dict:
    prediction = (probability >= 0.5).astype(int)
    tn, fp, fn, tp = confusion_matrix(truth, prediction, labels=[0, 1]).ravel()
    both_classes = len(np.unique(truth)) == 2
    return {
        "rows": len(truth), "positive_rate": float(np.mean(truth)),
        "precision": float(precision_score(truth, prediction, zero_division=0)),
        "recall": float(recall_score(truth, prediction, zero_division=0)),
        "f1": float(f1_score(truth, prediction, zero_division=0)),
        "average_precision": float(average_precision_score(truth, probability)) if both_classes else None,
        "roc_auc": float(roc_auc_score(truth, probability)) if both_classes else None,
        "confusion_matrix": {"true_negative": int(tn), "false_positive": int(fp),
                             "false_negative": int(fn), "true_positive": int(tp)},
    }


def train(data: Path, output_dir: Path, seed: int = 42, test_size: float = 0.2) -> dict:
    frame = pd.read_csv(data)
    loads = validate_dataset(frame)
    features = ["outage_line", *loads]
    x = frame[features].copy()
    x["outage_line"] = x["outage_line"].astype(str)
    y = frame.violation.astype(int)
    train_index, test_index = train_test_split(
        np.arange(len(frame)), test_size=test_size, random_state=seed, stratify=y)
    prep = ColumnTransformer([
        ("outage", OneHotEncoder(handle_unknown="ignore"), ["outage_line"]),
        ("loads", "passthrough", loads),
    ])
    model = Pipeline([
        ("features", prep),
        ("classifier", RandomForestClassifier(n_estimators=300, min_samples_leaf=2,
                                              class_weight="balanced_subsample", random_state=seed,
                                              n_jobs=-1)),
    ])
    model.fit(x.iloc[train_index], y.iloc[train_index])
    truth = y.iloc[test_index]
    probability = model.predict_proba(x.iloc[test_index])[:, 1]
    prediction = (probability >= 0.5).astype(int)
    main_scores = _scores(truth, probability)

    group_train, group_test = next(GroupShuffleSplit(
        n_splits=1, test_size=test_size, random_state=seed).split(x, y, groups=frame.outage_line))
    group_model = clone(model)
    group_model.fit(x.iloc[group_train], y.iloc[group_train])
    group_probability = group_model.predict_proba(x.iloc[group_test])[:, 1]
    unseen_scores = _scores(y.iloc[group_test], group_probability)
    unseen_scores["held_out_lines"] = sorted(int(i) for i in frame.iloc[group_test].outage_line.unique())
    unseen_scores["method"] = "group holdout by outage_line; no held-out line ID occurs in training"
    metrics = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": str(data),
        "dataset_sha256": hashlib.sha256(data.read_bytes()).hexdigest(),
        "target": "violation: voltage threshold breach or islanded/nonconverged case",
        "features": features,
        "split": "stratified random scenario holdout; line IDs may occur in both splits",
        "seed": seed, "test_size": test_size,
        "train_rows": len(train_index), "test_rows": len(test_index),
        "train_positive_rate": float(y.iloc[train_index].mean()),
        "test_positive_rate": main_scores["positive_rate"],
        "precision": main_scores["precision"],
        "recall": main_scores["recall"],
        "f1": main_scores["f1"],
        "average_precision": main_scores["average_precision"],
        "roc_auc": main_scores["roc_auc"],
        "confusion_matrix": main_scores["confusion_matrix"],
        "unseen_line_holdout": unseen_scores,
        "versions": {"sklearn": sklearn.__version__, "pandas": pd.__version__},
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    pd.DataFrame({"scenario_id": frame.iloc[test_index].scenario_id.to_numpy(),
                  "outage_line": frame.iloc[test_index].outage_line.to_numpy(),
                  "actual": truth.to_numpy(), "predicted": prediction,
                  "risk_probability": probability}).to_csv(output_dir / "test_predictions.csv", index=False)
    names = model.named_steps["features"].get_feature_names_out()
    importance = model.named_steps["classifier"].feature_importances_
    pd.DataFrame({"feature": names, "importance": importance}).sort_values(
        "importance", ascending=False).to_csv(output_dir / "feature_importance.csv", index=False)
    joblib.dump(model, output_dir / "model.joblib")
    files = [output_dir / name for name in (
        "metrics.json", "test_predictions.csv", "feature_importance.csv", "model.joblib")]
    (output_dir / "manifest.json").write_text(json.dumps({
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_sha256": metrics["dataset_sha256"],
        "files_sha256": {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in files},
    }, indent=2) + "\n")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("generate_dataset.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("output/model"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--test-size", type=float, default=0.2)
    args = parser.parse_args()
    if not 0 < args.test_size < 1:
        parser.error("--test-size must be between 0 and 1")
    metrics = train(args.data, args.output_dir, args.seed, args.test_size)
    print(f"Test: {metrics['test_rows']} cases, precision={metrics['precision']:.3f}, "
          f"recall={metrics['recall']:.3f}, average precision={metrics['average_precision']:.3f}")


if __name__ == "__main__":
    main()
