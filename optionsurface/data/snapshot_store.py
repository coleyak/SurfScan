"""
Snapshot store

Turns a series of one-off yfinance pulls into a backtestable history:
run collect_snapshot.py on a schedule (cron, task scheduler, a simple
while-loop) and this accumulates the archive that ReplayEngine walks
through later.

Layout on disk:
    <base_dir>/<TICKER>/<YYYY-MM-DDTHH-MM-SS-ffffff>.parquet

Timestamps carry microsecond precision specifically to avoid same-second
collisions once collection moves from occasional manual runs to an
automated polling loop -- two snapshots half a second apart would
otherwise silently overwrite one another.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import pandas as pd

from ..chain import OptionsChain

_TIME_FMT = "%Y-%m-%dT%H-%M-%S-%f"


def _normalize(dt: Optional[datetime]) -> Optional[datetime]:
    """Naive datetimes are assumed UTC (matching OptionContract's behavior)
    so comparisons against stored (always UTC-aware) timestamps don't
    raise "can't compare naive and aware datetimes"."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class SnapshotStore:
    def __init__(self, base_dir: str | Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _ticker_dir_for_write(self, ticker: str) -> Path:
        """Creates the ticker directory if needed. Use only when actually
        about to write -- see _existing_ticker_dir for the read-only version."""
        d = self.base_dir / ticker.upper()
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _existing_ticker_dir(self, ticker: str) -> Optional[Path]:
        """Read-only lookup: returns the directory if it exists, else None.
        Deliberately does NOT create it -- a read like list_snapshot_times()
        for a ticker with no history yet shouldn't have the side effect of
        creating an empty directory on disk."""
        d = self.base_dir / ticker.upper()
        return d if d.exists() else None

    # ------------------------------------------------------------------
    def save(self, chain: OptionsChain) -> Path:
        d = self._ticker_dir_for_write(chain.underlying)
        path = d / f"{chain.snapshot_time.strftime(_TIME_FMT)}.parquet"
        chain.to_dataframe().to_parquet(path, index=False)
        return path

    def load(self, ticker: str, snapshot_time: datetime) -> OptionsChain:
        d = self._existing_ticker_dir(ticker)
        if d is None:
            raise FileNotFoundError(
                f"No stored snapshots for {ticker!r} in {self.base_dir}"
            )
        path = d / f"{snapshot_time.strftime(_TIME_FMT)}.parquet"
        df = pd.read_parquet(path)
        return OptionsChain.from_dataframe(
            df, underlying=ticker, snapshot_time=_normalize(snapshot_time)
        )

    def list_snapshot_times(self, ticker: str) -> List[datetime]:
        d = self._existing_ticker_dir(ticker)
        if d is None:
            return []
        times = []
        for f in d.glob("*.parquet"):
            try:
                times.append(
                    datetime.strptime(f.stem, _TIME_FMT).replace(tzinfo=timezone.utc)
                )
            except ValueError:
                continue
        return sorted(times)

    def load_range(
        self,
        ticker: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> List[OptionsChain]:
        start, end = _normalize(start), _normalize(end)
        chains = []
        for t in self.list_snapshot_times(ticker):
            if start and t < start:
                continue
            if end and t > end:
                continue
            chains.append(self.load(ticker, t))
        return chains

    def tickers(self) -> List[str]:
        return sorted(p.name for p in self.base_dir.iterdir() if p.is_dir())
