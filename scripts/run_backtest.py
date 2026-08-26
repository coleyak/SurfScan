#!/usr/bin/env python3
"""
Replay stored snapshots for a ticker: fit a surface at each snapshot and
report the statistical anomalies found.

Usage:
    python scripts/run_backtest.py AAPL
    python scripts/run_backtest.py AAPL --option-type put --z-threshold 2.5
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from optionsurface.backtest.replay import ReplayEngine
from optionsurface.data.snapshot_store import SnapshotStore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ticker")
    parser.add_argument("--option-type", choices=["call", "put"], default="call")
    parser.add_argument("--min-volume", type=float, default=0)
    parser.add_argument("--z-threshold", type=float, default=3.0)
    parser.add_argument("--data-dir", default="data/snapshots")
    args = parser.parse_args()

    store = SnapshotStore(args.data_dir)
    n_snapshots = len(store.list_snapshot_times(args.ticker))
    if n_snapshots == 0:
        print(f"No stored snapshots for {args.ticker} in {args.data_dir}.")
        print(
            "Run scripts/collect_snapshot.py first (repeatedly, over time) to build history."
        )
        return

    engine = ReplayEngine(
        store,
        option_type=args.option_type,
        min_volume=args.min_volume,
        z_threshold=args.z_threshold,
    )
    result = engine.run(args.ticker)

    print(result.summary())
    if result.skipped:
        print("Skipped:")
        for s in result.skipped:
            print(f"  [{s.snapshot_time}] {s.reason}")
    print()
    for step in result.steps:
        q = step.fit_quality
        print(
            f"[{step.snapshot_time}] fit R^2={q['r_squared']:.3f} "
            f"RMSE={q['rmse']:.4f} on {q['n_points']} points "
            f"-- {len(step.anomalies)} anomalies"
        )
        for a in step.anomalies:
            print(f"    {a}")


if __name__ == "__main__":
    main()
