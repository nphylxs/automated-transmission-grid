import json

import numpy as np
import pandas as pd
import pandapower.networks as pn
import pytest

from grid_study import Limits, export_dataset, export_n1_study, run_case
from train_model import validate_dataset
from verify_evidence import verify_hashes


def test_cases_are_independent_and_islands_are_recorded():
    net = pn.case30()
    original_lines = net.line.in_service.copy()
    limits = Limits()
    first, _, _ = run_case(net, "first", 6, limits, details=True)
    island, _, _ = run_case(net, "island", 12, limits)
    repeated, _, _ = run_case(net, "repeated", 6, limits)

    assert net.line.in_service.equals(original_lines)
    assert first["status"] == repeated["status"] == "converged"
    assert first["min_v_pu"] == pytest.approx(repeated["min_v_pu"])
    assert first["violation"] == repeated["violation"] == 1
    assert island["status"] == "islanded"
    assert island["unsupplied_buses"]
    assert np.isnan(island["min_v_pu"])


def test_dataset_is_reproducible_and_demand_uses_scaling(tmp_path):
    path = tmp_path / "dataset.csv"
    evidence = tmp_path / "evidence"
    a = export_dataset(12, 42, path, evidence, Limits())
    first_bytes = path.read_bytes()
    b = export_dataset(12, 42, path, evidence, Limits())
    pd.testing.assert_frame_equal(a, b)
    assert path.read_bytes() == first_bytes
    assert len(a) == 12
    load_columns = [column for column in a if column.startswith("load_bus_")]
    assert np.allclose(a[load_columns].sum(axis=1), a.total_demand_mw)
    assert a.total_demand_mw.nunique() > 1
    assert json.loads((evidence / "manifest.json").read_text())["samples"] == 12


def test_n1_export_covers_every_line_and_distinguishes_new_overloads(tmp_path):
    summary = export_n1_study(tmp_path, Limits())
    case = pd.read_csv(tmp_path / "contingencies.csv")
    assert len(summary) == len(pn.case30().line) == 41
    assert len(case) == 42
    assert case.iloc[0].scenario_id == "base"
    assert case.iloc[0].incremental_thermal_violation == 0
    assert case.thermal_violation.sum() > case.incremental_thermal_violation.sum()
    assert (tmp_path / "topology.md").read_text().count("---|") == 41
    assert len(json.loads((tmp_path / "manifest.json").read_text())["files_sha256"]) == 6


def test_model_rejects_inconsistent_demand():
    frame = pd.DataFrame({
        "scenario_id": [f"s{i}" for i in range(20)],
        "outage_line": [i % 2 for i in range(20)],
        "load_bus_1": [1.0] * 20,
        "total_demand_mw": [2.0] * 20,
        "status": ["converged"] * 20,
        "violation": [i % 2 for i in range(20)],
    })
    with pytest.raises(ValueError, match="Total demand"):
        validate_dataset(frame)


def test_evidence_verifier_detects_tampering(tmp_path):
    import hashlib

    evidence = tmp_path / "result.csv"
    evidence.write_text("value\n1\n")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"files_sha256": {
        str(evidence): hashlib.sha256(evidence.read_bytes()).hexdigest()}}))
    verify_hashes(manifest)
    evidence.write_text("value\n2\n")
    with pytest.raises(ValueError, match="Hash mismatch"):
        verify_hashes(manifest)
