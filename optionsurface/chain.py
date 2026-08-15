"""
Option chain snapshot

Defines the foundational data structure representing a full set of contracts
at a specific moment in time.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Iterable, List, Optional

import pandas as pd
import yfinance as yf

from .contract import OptionContract


class OptionsChain:
    """A snapshot of every listed option contract for one underlying."""

    def __init__(
        self, underlying: str, snapshot_time: datetime, contracts: List[OptionContract]
    ):
        self.underlying = underlying
        self.snapshot_time = snapshot_time
        self.contracts = contracts

    # Construction ------------------------------------------------------------------------------------------------

    @classmethod
    def from_yfinance(
        cls, ticker_symbol: str, max_expiries: Optional[int] = None
    ) -> "OptionsChain":
        """Pulls a live snapshot from Yahoo Finance via the yfinance package."""
        tk = yf.Ticker(ticker_symbol)
        snapshot_time = datetime.now()
        underlying_price = cls._get_underlying_price(tk)

        expiries = list(tk.options)
        if max_expiries is not None:
            expiries = expiries[:max_expiries]
        if not expiries:
            raise ValueError(f"No listed option expiries found for {ticker_symbol!r}")

        contracts: List[OptionContract] = []
        for expiry_str in expiries:
            expiry = datetime.strptime(expiry_str, "%Y-%m-%d").date()
            try:
                oc = tk.option_chain(expiry_str)
            except Exception:
                continue

            contracts.extend(
                cls._rows_to_contracts(
                    oc.calls,
                    "call",
                    ticker_symbol,
                    underlying_price,
                    expiry,
                    snapshot_time,
                )
            )
            contracts.extend(
                cls._rows_to_contracts(
                    oc.puts,
                    "put",
                    ticker_symbol,
                    underlying_price,
                    expiry,
                    snapshot_time,
                )
            )

        return cls(ticker_symbol, snapshot_time, contracts)

    @staticmethod
    def _get_underlying_price(tk: yf.Ticker) -> float:
        for attr, key in (("fast_info", "last_price"), ("info", "regularMarketPrice")):
            try:
                obj = getattr(tk, attr)
                # Fixed typo: __gititem__ -> __getitem__
                val = obj[key] if hasattr(obj, "__getitem__") else getattr(obj, key)
                if val:
                    return float(val)
            except Exception:
                continue

        hist = tk.history(period="1d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
        raise ValueError(f"Could not determine underlying price for {tk.ticker}")

    @classmethod
    def _rows_to_contracts(
        cls,
        df: pd.DataFrame,
        option_type: str,
        underlying: str,
        underlying_price: float,
        expiry: date,
        snapshot_time: datetime,
    ) -> List[OptionContract]:
        out = []
        for _, row in df.iterrows():
            out.append(
                OptionContract(
                    contract_symbol=row.get("contractSymbol", ""),
                    underlying=underlying,
                    underlying_price=underlying_price,
                    strike=float(row["strike"]),
                    expiry=expiry,
                    option_type=option_type,
                    snapshot_time=snapshot_time,
                    # Added cls. prefix for _safe_float
                    bid=cls._safe_float(row.get("bid")),
                    ask=cls._safe_float(row.get("ask")),
                    last_price=cls._safe_float(row.get("lastPrice")),
                    volume=cls._safe_float(row.get("volume")),
                    open_interest=cls._safe_float(row.get("openInterest")),
                    implied_vol=cls._safe_float(row.get("impliedVolatility")),
                )
            )
        return out

    @classmethod
    def from_contracts(
        cls,
        underlying: str,
        snapshot_time: datetime,
        contracts: Iterable[OptionContract],
    ) -> "OptionsChain":
        return cls(underlying, snapshot_time, list(contracts))

    # Access / filtering ------------------------------------------------------------------------------------------

    def calls(self) -> List[OptionContract]:
        return [c for c in self.contracts if c.is_call]

    def puts(self) -> List[OptionContract]:
        return [c for c in self.contracts if c.is_put]

    def expiries(self) -> List[date]:
        return sorted({c.expiry for c in self.contracts})

    def filter(
        self,
        option_type: Optional[str] = None,
        min_volume: Optional[float] = None,
        min_open_interest: Optional[float] = None,
        max_spread_pct: Optional[float] = None,
        require_iv: bool = True,
    ) -> "OptionsChain":
        """Return a new OptionsChain with only contracts passing the given filters."""
        kept = []
        for c in self.contracts:
            if option_type is not None and c.option_type != option_type:
                continue
            if require_iv and (c.implied_vol is None or c.implied_vol <= 0):
                continue
            if min_volume is not None and (c.volume or 0) < min_volume:
                continue
            if (
                min_open_interest is not None
                and (c.open_interest or 0) < min_open_interest
            ):
                continue
            if max_spread_pct is not None:
                sp = c.spread_pct
                if sp is None or sp > max_spread_pct:
                    continue
            kept.append(c)
        return OptionsChain(self.underlying, self.snapshot_time, kept)

    # Conversion --------------------------------------------------------------------------------------------------

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame([c.to_dict() for c in self.contracts])

    @classmethod
    def from_dataframe(
        cls, df: pd.DataFrame, underlying: str, snapshot_time: datetime
    ) -> "OptionsChain":
        contracts = [
            OptionContract.from_dict(row) for row in df.to_dict(orient="records")
        ]
        return cls(underlying, snapshot_time, contracts)

    def __len__(self) -> int:
        return len(self.contracts)

    def __repr__(self) -> str:
        return (
            f"OptionsChain(underlying={self.underlying!r}, "
            f"snapshot_time={self.snapshot_time!r}, n_contracts={len(self)})"
        )


def _safe_float(x) -> Optional[float]:
    try:
        if x is None or (isinstance(x, float) and pd.isna(x)):
            return None
        return float(x)
    except (TypeError, ValueError):
        return None
