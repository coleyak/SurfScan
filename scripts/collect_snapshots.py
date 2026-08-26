#!/usr/bin/env python3
"""
Pull one live options-chain snapshot for a ticker and save it to the
local archive. Run this on a schedule (cron, Windows Task Scheduler, or
just a `while True: sleep(...)` loop) to build up history over time --
yfinance itself has no historical options data, so this script IS the
history.

Usage:
    python scripts/collect_snapshot.py AAPL
    python scripts/collect_snapshot.py AAPL --max-expiries 6 --data-dir data/snapshots
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from optionsurface.data.feed import YFinanceDataFeed
from optionsurface.data.snapshot_store import SnapshotStore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ticker", help="Underlying ticker symbol, e.g. AAPL")
    parser.add_argument(
        "--max-expiries", type=int, default=None, help="Limit number of expiries pulled"
    )
    parser.add_argument(
        "--data-dir", default="data/snapshots", help="Where to store the archive"
    )
    args = parser.parse_args()

    feed = YFinanceDataFeed(max_expiries=args.max_expiries)
    store = SnapshotStore(args.data_dir)

    print(f"Fetching live chain for {args.ticker}...")
    chain = feed.get_snapshot(args.ticker)
    path = store.save(chain)
    print(f"Saved {len(chain)} contracts to {path}")


if __name__ == "__main__":
    main()
