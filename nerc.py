"""Run a documented N-1 planning screen for every IEEE 30-bus line."""

from __future__ import annotations

import argparse
from pathlib import Path

from grid_study import Limits, export_n1_study


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("output/n1"))
    parser.add_argument("--min-v", type=float, default=0.95)
    parser.add_argument("--max-v", type=float, default=1.05)
    parser.add_argument("--max-loading", type=float, default=100.0)
    args = parser.parse_args()
    summary = export_n1_study(args.output_dir, Limits(args.min_v, args.max_v, args.max_loading))
    print(f"Wrote {len(summary)} line-contingency results to {args.output_dir}")
    print(f"Voltage/solvability flags: {int(summary.violation.sum())}; thermal flags: {int(summary.thermal_violation.sum())}")


if __name__ == "__main__":
    main()
