"""
Option Surface

Treats the options chain as a literal surface: z = IV(x, y)
where x = log-moneyness ln(K/S) and y = time to expiry (years).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
import numpy as np

from .chain import OptionsChain
from .contract import OptionContract


@dataclass
class SurfacePoint:
    """One (contract, coordinate, actual vs fitted IV) record."""

    contract: OptionContract
    x: float
    y: float
    actual_iv: float
    fitted_iv: float

    @property
    def residual(self) -> float:
        return self.actual_iv - self.fitted_iv


class VolatilitySurface:
    """A smoothed IV surface fit to one option type of one chain."""

    def __init__(
        self, chain: OptionsChain, option_type: str = "call", min_volume: float = 0
    ):
        if option_type not in ("call", "put"):
            raise ValueError("option_type must be 'call' or 'put'")

        self.chain = chain
        self.option_type = option_type

        filtered = chain.filter(
            option_type=option_type, min_volume=min_volume, require_iv=True
        )
        self._contracts = filtered.contracts

        if len(self._contracts) < 6:
            raise ValueError(
                f"Only {len(self._contracts)} usable {option_type} contracts with IV data. "
                "Need at least 6 to fit a quadratic surface."
            )

        self._x = np.array([c.log_moneyness for c in self._contracts])
        self._y = np.array([c.time_to_expiry for c in self._contracts])
        self._z = np.array([c.implied_vol for c in self._contracts])

        self.degree = 2
        self._coeffs: Optional[np.ndarray] = None
        self._weights: Optional[np.ndarray] = None

    # Fitting ------------------------------------------------------------------------------------------------------

    def _design_matrix(self, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        """Quadratic surface basis: [1, x, y, x^2, y^2, x*y]."""
        return np.column_stack([np.ones_like(x), x, y, x**2, y**2, x * y])

    def fit(
        self, n_irls_iters: int = 8, huber_delta: float = 0.03
    ) -> "VolatilitySurface":
        """Fit the quadratic surface with Huber-weighted IRLS. Residuals smaller
        than huber_delta are treated as normal noise. Larger residuals are down-weighted
        so a handful of outliers can't pull the fitted surface toward themselves.
        """
        A = self._design_matrix(self._x, self._y)
        weights = np.ones_like(self._z)

        for _ in range(n_irls_iters):
            W = np.sqrt(weights)
            coeffs, *_ = np.linalg.lstsq(A * W[:, None], self._z * W, rcond=None)

            fitted = A @ coeffs
            resid = self._z - fitted
            abs_resid = np.abs(resid)
            weights = np.where(
                abs_resid <= huber_delta,
                1.0,
                huber_delta / np.maximum(abs_resid, 1e-12),
            )

        self._coeffs = coeffs
        self._weights = weights
        return self

    def predict(self, x, y) -> np.ndarray:
        """Evaluate the fitted surface at arbitrary (log-moneyness, time-to-expiry) points."""
        if self._coeffs is None:
            raise RuntimeError("Call .fit() before .predict()")

        x = np.atleast_1d(np.asarray(x, dtype=float))
        y = np.atleast_1d(np.asarray(y, dtype=float))
        A = self._design_matrix(x, y)
        return A @ self._coeffs

    # Residuals / diagnostics --------------------------------------------------------------------------------------

    def points(self) -> List[SurfacePoint]:
        """All fitted points paired with their actual vs. fitted IV."""
        if self._coeffs is None:
            raise RuntimeError("Call .fit() before .points()")

        fitted = self.predict(self._x, self._y)
        return [
            SurfacePoint(contract=c, x=x, y=y, actual_iv=z, fitted_iv=f)
            for c, x, y, z, f in zip(self._contracts, self._x, self._y, self._z, fitted)
        ]

    def fit_quality(self) -> dict:
        """Simple diagnostics: R^2 and RMSE of the fit against raw data."""
        pts = self.points()
        resid = np.array([p.residual for p in pts])
        z = np.array([p.actual_iv for p in pts])

        ss_res = float(np.sum(resid**2))
        ss_tot = float(np.sum((z - z.mean()) ** 2))

        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")
        rmse = float(np.sqrt(np.mean(resid**2)))

        return {"r_squared": r2, "rmse": rmse, "n_points": len(pts)}

    def __repr__(self) -> str:
        fitted = "fitted" if self._coeffs is not None else "unfitted"
        return (
            f"VolatilitySurface(underlying={self.chain.underlying!r}, "
            f"option_type={self.option_type!r}, n_points={len(self._contracts)}, {fitted})"
        )
