"""
Data Feed
Pluggable source of OptionsChain snapshots. Swapping YFinanceDataFeed for
a different implementation (a paid real-time API, a broker feed, etc.)
later shouldn't require touching the surface/detection code at all --
that's the point of coding to this interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..chain import OptionsChain


class DataFeed(ABC):
    """Anything that can hand back a fresh OptionsChain for a ticker."""

    @abstractmethod
    def get_snapshot(self, ticker: str) -> OptionsChain: ...


class YFinanceDataFeed(DataFeed):
    """Free, delayed (typically 15-20 min) quotes via Yahoo Finance.

    Good for prototyping the pipeline end-to-end. NOTE: Yahoo does not
    provide historical options chains -- this only ever returns the
    *current* live chain. To build a history for backtesting, run this
    repeatedly over time via SnapshotStore (see scripts/collect_snapshot.py)
    and let the archive accumulate.
    """

    def __init__(self, max_expiries: int | None = None):
        self.max_expiries = max_expiries

    def get_snapshot(self, ticker: str) -> OptionsChain:
        return OptionsChain.from_yfinance(ticker, max_expiries=self.max_expiries)
