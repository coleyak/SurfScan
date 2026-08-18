"""
Option contract snapshot

Defines the foundational data structure representing a single option quote
at a specific moment in time.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Optional

import numpy as np


@dataclass
class OptionContract:
    """A single option quote, snapshotted at a moment in time.

    All price-like fields may be None if the source didn't provide them
    (e.g. an illiquid strike with no bid/ask).
    """

    contract_symbol: str
    underlying: str
    underlying_price: float
    strike: float
    expiry: date
    option_type: str
    snapshot_time: datetime

    bid: Optional[float] = None
    ask: Optional[float] = None
    last_price: Optional[float] = None
    volume: Optional[float] = None
    open_interest: Optional[float] = None
    implied_vol: Optional[float] = None

    def __post_init__(self) -> None:
        ot = self.option_type.lower().strip()
        if ot in ("call", "c"):
            self.option_type = "call"
        elif ot in ("put", "p"):
            self.option_type = "put"
        else:
            raise ValueError(f"option_type must be call/put, got {self.option_type!r}")

        if self.snapshot_time.tzinfo is None:
            self.snapshot_time = self.snapshot_time.replace(tzinfo=timezone.utc)

    # ------------------------------------------------------------------
    # Derived quantities
    # ------------------------------------------------------------------
    @property
    def is_call(self) -> bool:
        return self.option_type == "call"

    @property
    def is_put(self) -> bool:
        return self.option_type == "put"

    @property
    def mid_price(self) -> Optional[float]:
        """Bid/ask midpoint, falling back to last trade price."""
        if (
            self.bid is not None
            and self.ask is not None
            and self.bid > 0
            and self.ask > 0
        ):
            return (self.bid + self.ask) / 2.0
        return self.last_price

    @property
    def spread(self) -> Optional[float]:
        if self.bid is not None and self.ask is not None:
            return self.ask - self.bid
        return None

    @property
    def spread_pct(self) -> Optional[float]:
        """Spread as a fraction of mid price -- useful for filtering junk quotes."""
        mid = self.mid_price
        sp = self.spread
        if mid and sp is not None and mid > 0:
            return sp / mid
        return None

    @property
    def invalid_reason(self) -> Optional[str]:
        """Why this quote looks corrupted/unusable, or None if it looks fine.

        Deliberately a property that reports a reason rather than an
        exception raised in __post_init__: one bad row (a crossed market, a
        stale zero price) should not abort loading an entire chain of
        otherwise-good contracts. Callers decide what to do with invalid
        contracts -- OptionsChain.filter() drops them by default.
        """
        if self.strike <= 0:
            return "non-positive strike"
        if self.underlying_price <= 0:
            return "non-positive underlying price"
        if self.bid is not None and self.bid < 0:
            return "negative bid"
        if self.ask is not None and self.ask < 0:
            return "negative ask"
        if (
            self.bid is not None
            and self.ask is not None
            and self.bid > 0
            and self.ask > 0
            and self.bid > self.ask
        ):
            return "crossed market (bid > ask)"
        if (self.expiry - self.snapshot_time.date()).days < 0:
            return "already expired as of snapshot_time"
        if self.implied_vol is not None and self.implied_vol < 0:
            return "negative implied vol"
        return None

    @property
    def is_valid(self) -> bool:
        return self.invalid_reason is None

    @property
    def time_to_expiry(self) -> float:
        """Time to expiry in years (ACT/365), floored at a tiny positive number
        so log/divide operations never blow up on expiry day."""
        days = (self.expiry - self.snapshot_time.date()).days
        return max(days, 0) / 365.0 + 1e-6

    @property
    def moneyness(self) -> float:
        """K / S"""
        return self.strike / self.underlying_price

    @property
    def log_moneyness(self) -> float:
        """ln(K / S) -- the standard x-coordinate for a vol surface."""
        return float(np.log(self.strike / self.underlying_price))

    def to_dict(self) -> dict:
        return {
            "contract_symbol": self.contract_symbol,
            "underlying": self.underlying,
            "underlying_price": self.underlying_price,
            "strike": self.strike,
            "expiry": self.expiry.isoformat(),
            "option_type": self.option_type,
            "snapshot_time": self.snapshot_time.isoformat(),
            "bid": self.bid,
            "ask": self.ask,
            "last_price": self.last_price,
            "volume": self.volume,
            "open_interest": self.open_interest,
            "implied_vol": self.implied_vol,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "OptionContract":
        d = dict(d)
        d["expiry"] = (
            date.fromisoformat(d["expiry"])
            if isinstance(d["expiry"], str)
            else d["expiry"]
        )
        d["snapshot_time"] = (
            datetime.fromisoformat(d["snapshot_time"])
            if isinstance(d["snapshot_time"], str)
            else d["snapshot_time"]
        )
        return cls(**d)
