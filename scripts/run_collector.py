#!/usr/bin/env python3
"""
Continuously collect option-chain snapshots for one or more tickers, on a
fixed interval, during US market hours only. This is what actually builds
the historical archive ReplayEngine consumes -- yfinance has no history of
its own (see chain.py), so this loop *is* the history.

Usage:
    python scripts/run_collector.py AAPL MSFT SPY --interval 15 --max-expiries 6

Runs until interrupted (Ctrl+C). Designed to be left running for days: a
single failed fetch (network hiccup, a momentary yfinance hiccup) is logged
and skipped rather than killing the loop.

"""

import argparse
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from optionsurface.data.feed import YFinanceDataFeed
from optionsurface.data.snapshot_store import SnapshotStore

MARKET_TZ = ZoneInfo("America/New_York")
MARKET_OPEN = (9, 30)
MARKET_CLOSE = (16, 0)


def is_market_open(now_et: datetime = None) -> bool:
    now_et = now_et or datetime.now(MARKET_TZ)
    if now_et.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    open_t = now_et.replace(
        hour=MARKET_OPEN[0], minute=MARKET_OPEN[1], second=0, microsecond=0
    )
    close_t = now_et.replace(
        hour=MARKET_CLOSE[0], minute=MARKET_CLOSE[1], second=0, microsecond=0
    )
    return open_t <= now_et <= close_t


def collect_once(tickers, feed: YFinanceDataFeed, store: SnapshotStore) -> None:
    for ticker in tickers:
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        try:
            chain = feed.get_snapshot(ticker)
            path = store.save(chain)
            print(f"[{stamp}] {ticker}: saved {len(chain)} contracts -> {path.name}")
        except Exception:
            print(f"[{stamp}] {ticker}: FAILED")
            traceback.print_exc()


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "tickers", nargs="+", help="One or more ticker symbols, e.g. AAPL MSFT SPY"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=15,
        help="Minutes between snapshots (default: 15)",
    )
    parser.add_argument(
        "--max-expiries",
        type=int,
        default=6,
        help="Expiries to pull per snapshot (default: 6)",
    )
    parser.add_argument("--data-dir", default="data/snapshots")
    parser.add_argument(
        "--ignore-market-hours",
        action="store_true",
        help="Collect around the clock instead of only 9:30-16:00 America/New_York on weekdays",
    )
    args = parser.parse_args()

    feed = YFinanceDataFeed(max_expiries=args.max_expiries)
    store = SnapshotStore(args.data_dir)

    schedule_desc = (
        "around the clock"
        if args.ignore_market_hours
        else "market hours only (America/New_York)"
    )
    print(
        f"Collecting {', '.join(args.tickers)} every {args.interval} min, {schedule_desc}"
    )
    print(f"Writing to {Path(args.data_dir).resolve()}")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            if args.ignore_market_hours or is_market_open():
                collect_once(args.tickers, feed, store)
            else:
                now_et = datetime.now(MARKET_TZ)
                print(
                    f"[{now_et.isoformat(timespec='seconds')}] market closed, skipping"
                )
            time.sleep(args.interval * 60)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
