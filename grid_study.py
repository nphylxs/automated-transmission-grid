"""Physics-based IEEE 30-bus screening and traceable exports.

The limits are user-selected study thresholds. This is a planning demonstration,
not a determination of compliance with a NERC Reliability Standard.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pandapower as pp
import pandapower.networks as pn
from pandapower.topology import unsupplied_buses


@dataclass(frozen=True)
class Limits:
    min_v_pu: float = 0.95
    max_v_pu: float = 1.05
    max_loading_percent: float = 100.0

    def __post_init__(self) -> None:
        if not (0 < self.min_v_pu < self.max_v_pu):
            raise ValueError("Voltage limits must be positive and increasing")
        if self.max_loading_percent <= 0:
            raise ValueError("Maximum line loading must be positive")


def _ids(values) -> str:
    return ";".join(str(int(i)) for i in values)


def run_case(base_net, scenario_id: str, outage_line: int | None, limits: Limits,
             scaling: np.ndarray | None = None, details: bool = False):
    """Study an independent case; return summary and optional bus/line detail rows."""
    net = copy.deepcopy(base_net)
    if scaling is not None:
        if len(scaling) != len(net.load):
            raise ValueError("Load-scaling vector length does not match case")
        net.load.loc[:, "scaling"] = scaling
    if outage_line is not None:
        if outage_line not in net.line.index:
            raise ValueError(f"Unknown line index: {outage_line}")
        net.line.at[outage_line, "in_service"] = False

    demand_by_load = net.load.p_mw.to_numpy(dtype=float) * net.load.scaling.to_numpy(dtype=float)
    row = {
        "scenario_id": scenario_id,
        "outage_line": "" if outage_line is None else int(outage_line),
        "from_bus": "" if outage_line is None else int(net.line.at[outage_line, "from_bus"]),
        "to_bus": "" if outage_line is None else int(net.line.at[outage_line, "to_bus"]),
        "total_demand_mw": float(demand_by_load.sum()),
        "status": "converged",
        "failure_reason": "",
        "min_v_pu": np.nan,
        "max_v_pu": np.nan,
        "max_loading_percent": np.nan,
        "low_voltage_buses": "",
        "high_voltage_buses": "",
        "overloaded_lines": "",
        "unsupplied_buses": "",
        "voltage_violation": 0,
        "thermal_violation": 0,
        "violation": 0,
        "any_screen_violation": 0,
    }
    for bus, value in zip(net.load.bus, demand_by_load):
        row[f"load_bus_{int(bus)}"] = float(value)

    bus_rows: list[dict] = []
    line_rows: list[dict] = []
    unsupplied = sorted(int(bus) for bus in unsupplied_buses(net))
    if unsupplied:
        row.update(status="islanded", failure_reason="Unsupplied buses", unsupplied_buses=_ids(unsupplied), violation=1, any_screen_violation=1)
        return row, bus_rows, line_rows

    try:
        pp.runpp(net, enforce_q_lims=True, numba=False)
        if not net.converged:
            raise pp.LoadflowNotConverged("Power flow did not converge")
        voltages = net.res_bus.loc[net.bus.index[net.bus.in_service], "vm_pu"]
        loadings = net.res_line.loc[net.line.index[net.line.in_service], "loading_percent"]
        if not np.isfinite(voltages).all() or not np.isfinite(loadings).all():
            raise pp.LoadflowNotConverged("Non-finite bus voltage or line loading")
    except (pp.LoadflowNotConverged, FloatingPointError) as exc:
        row.update(status="nonconverged", failure_reason=str(exc), violation=1, any_screen_violation=1)
        return row, bus_rows, line_rows

    low = voltages.index[voltages < limits.min_v_pu].tolist()
    high = voltages.index[voltages > limits.max_v_pu].tolist()
    overloaded = loadings.index[loadings > limits.max_loading_percent].tolist()
    voltage_flag = int(bool(low or high))
    thermal_flag = int(bool(overloaded))
    row.update(
        min_v_pu=float(voltages.min()), max_v_pu=float(voltages.max()),
        max_loading_percent=float(loadings.max()),
        low_voltage_buses=_ids(low), high_voltage_buses=_ids(high),
        overloaded_lines=_ids(overloaded),
        voltage_violation=voltage_flag, thermal_violation=thermal_flag,
        violation=voltage_flag, any_screen_violation=int(bool(voltage_flag or thermal_flag)),
    )
    if details:
        for bus, voltage in voltages.items():
            bus_rows.append({"scenario_id": scenario_id, "bus": int(bus), "vm_pu": float(voltage),
                             "below_min": int(voltage < limits.min_v_pu), "above_max": int(voltage > limits.max_v_pu)})
        for line, loading in loadings.items():
            line_rows.append({"scenario_id": scenario_id, "line": int(line), "loading_percent": float(loading),
                              "above_max": int(loading > limits.max_loading_percent)})
    return row, bus_rows, line_rows


def _write_manifest(path: Path, kind: str, limits: Limits, files: list[Path], **metadata) -> None:
    manifest = {
        "study": kind,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "network": "pandapower.networks.case30()",
        "solver": {"function": "pandapower.runpp", "enforce_q_lims": True},
        "thresholds": asdict(limits),
        "versions": {"pandapower": pp.__version__, "pandas": pd.__version__, "numpy": np.__version__},
        "files_sha256": {str(file): hashlib.sha256(file.read_bytes()).hexdigest() for file in files},
        **metadata,
    }
    path.write_text(json.dumps(manifest, indent=2) + "\n")


def export_n1_study(output_dir: Path, limits: Limits) -> pd.DataFrame:
    output_dir.mkdir(parents=True, exist_ok=True)
    net = pn.case30()
    summaries, buses, lines = [], [], []
    base, base_buses, base_lines = run_case(net, "base", None, limits, details=True)
    summaries.append(base)
    buses.extend(base_buses)
    lines.extend(base_lines)
    for line in net.line.index[net.line.in_service]:
        row, bus_rows, line_rows = run_case(net, f"line_{line}", int(line), limits, details=True)
        summaries.append(row)
        buses.extend(bus_rows)
        lines.extend(line_rows)

    def element_set(value: str) -> set[str]:
        return set(value.split(";")) if value else set()

    base_overloads = element_set(base["overloaded_lines"])
    base_low = element_set(base["low_voltage_buses"])
    base_high = element_set(base["high_voltage_buses"])
    for row in summaries:
        row["new_overloaded_lines"] = _ids(sorted(
            int(i) for i in element_set(row["overloaded_lines"]) - base_overloads))
        row["new_low_voltage_buses"] = _ids(sorted(
            int(i) for i in element_set(row["low_voltage_buses"]) - base_low))
        row["new_high_voltage_buses"] = _ids(sorted(
            int(i) for i in element_set(row["high_voltage_buses"]) - base_high))
        row["incremental_thermal_violation"] = int(bool(row["new_overloaded_lines"]))

    paths = [output_dir / name for name in (
        "contingencies.csv", "bus_results.csv", "line_results.csv", "bus_inventory.csv", "line_inventory.csv",
        "topology.md")]
    pd.DataFrame(summaries).to_csv(paths[0], index=False)
    pd.DataFrame(buses).to_csv(paths[1], index=False)
    pd.DataFrame(lines).to_csv(paths[2], index=False)
    net.bus.to_csv(paths[3], index_label="bus")
    net.line.to_csv(paths[4], index_label="line")
    diagram = ["# IEEE 30-bus model connectivity", "", "Connectivity schematic using pandapower bus and line indices.",
               "This is not a field-verified transmission or substation one-line drawing.", "", "```mermaid", "graph LR"]
    diagram.extend(f'  b{bus}["Bus {bus}"]' for bus in net.bus.index)
    diagram.extend(f'  b{int(item.from_bus)} ---|"Line {line}"| b{int(item.to_bus)}'
                   for line, item in net.line.iterrows() if item.in_service)
    diagram.extend(["```", ""])
    paths[5].write_text("\n".join(diagram))
    _write_manifest(output_dir / "manifest.json", "deterministic N-1 line screen", limits, paths,
                    scenarios=len(summaries), line_outages=len(net.line.index[net.line.in_service]),
                    nonconverged_or_islanded=int((pd.DataFrame(summaries).status != "converged").sum()))
    return pd.DataFrame(summaries).query("scenario_id != 'base'")


def export_dataset(samples: int, seed: int, output: Path, evidence_dir: Path, limits: Limits) -> pd.DataFrame:
    if samples < 1:
        raise ValueError("samples must be positive")
    output.parent.mkdir(parents=True, exist_ok=True)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    net = pn.case30()
    rng = np.random.default_rng(seed)
    line_ids = net.line.index[net.line.in_service].to_numpy()
    rows = []
    for sample in range(samples):
        scaling = rng.uniform(0.8, 1.2, size=len(net.load))
        line = int(rng.choice(line_ids))
        row, _, _ = run_case(net, f"sample_{sample:05d}", line, limits, scaling)
        rows.append(row)
    frame = pd.DataFrame(rows)
    frame.to_csv(output, index=False)
    _write_manifest(evidence_dir / "manifest.json", "stochastic N-1 dataset", limits, [output],
                    seed=seed, samples=samples, load_scaling="independent uniform [0.8, 1.2] per load",
                    status_counts=frame.status.value_counts().to_dict(),
                    label="violation = voltage limit breach or islanded/nonconverged case; thermal_violation is separate")
    return frame
