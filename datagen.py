"""Generate reproducible stochastic N-1 scenarios and retained study evidence."""

from __future__ import annotations

import argparse
from pathlib import Path

from grid_study import Limits, export_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=Path("generate_dataset.csv"))
    parser.add_argument("--evidence-dir", type=Path, default=Path("output/dataset"))
    parser.add_argument("--min-v", type=float, default=0.95)
    parser.add_argument("--max-v", type=float, default=1.05)
    parser.add_argument("--max-loading", type=float, default=100.0)
    args = parser.parse_args()
    if args.samples < 1:
        parser.error("--samples must be positive")
    summary = export_dataset(args.samples, args.seed, args.output, args.evidence_dir,
                             Limits(args.min_v, args.max_v, args.max_loading))
    print(f"Wrote {len(summary)} scenarios to {args.output}")
    print(f"Voltage/solvability flags: {int(summary.violation.sum())}; thermal flags: {int(summary.thermal_violation.sum())}")


if __name__ == "__main__":
    main()
