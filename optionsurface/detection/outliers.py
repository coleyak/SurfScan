"""
Outlier detection

Flags contracts whose implied vol deviates from the smoothed surface by
more than a robust z-score threshold. This is the "irregularity" detector:
it doesn't know about arbitrage math, it just knows what "normal" looks
like for this surface right now and flags what doesn't fit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np

from ..contract import OptionContract
from ..surface import VolatilitySurface


@dataclass
class Anomaly:
    contract: OptionContract
    actual_iv: float
    fitted_iv: float
    residual: float
    z_score: float

    def __repr__(self) -> str:
        return (
            f"Anomaly({self.contract.option_type} K={self.contract.strike} "
            f"exp={self.contract.expiry} actual_iv={self.actual_iv:.4f} "
            f"fitted_iv={self.fitted_iv:.4f} z={self.z_score:+.2f})"
        )


class SurfaceOutlierDetector:
    """Robust statistical outlier detector on a fitted VolatilitySurface.

    Uses the median absolute deviation (MAD) rather than the plain std dev
    to estimate the "typical" residual size, since std dev itself is
    dragged around by the very outliers we're trying to find. Scores
    leave-one-out (LOO) residuals rather than raw in-sample ones -- see
    surface.py's module docstring -- so a point can't look artificially
    normal just because it had leverage over its own fitted value.
    """

    def __init__(
        self,
        surface: VolatilitySurface,
        z_threshold: float = 3.0,
        min_scale: float = 0.0025,
    ):
        """
        min_scale: floor on the residual-dispersion estimate, in IV units
        (default 0.0025 = a quarter of a vol point). Without this, a
        snapshot where residuals happen to be unusually tight would make
        `robust_sigma` collapse toward zero, and every point -- including a
        genuine anomaly -- would score as z~0 or blow up on noise. This
        floor says: don't claim to resolve differences finer than realistic
        quote noise, whatever the data happens to look like this snapshot.
        """
        self.surface = surface
        self.z_threshold = z_threshold
        self.min_scale = min_scale

    def detect(self) -> List[Anomaly]:
        points = self.surface.points()
        residuals = np.array([p.loo_residual for p in points])

        median = np.median(residuals)
        mad = np.median(np.abs(residuals - median))
        robust_sigma = max(mad * 1.4826, self.min_scale)

        anomalies = []
        for p, r in zip(points, residuals):
            z = (r - median) / robust_sigma
            if abs(z) >= self.z_threshold:
                anomalies.append(
                    Anomaly(
                        contract=p.contract,
                        actual_iv=p.actual_iv,
                        fitted_iv=p.fitted_iv,
                        residual=r,
                        z_score=float(z),
                    )
                )

        anomalies.sort(key=lambda a: -abs(a.z_score))
        return anomalies
