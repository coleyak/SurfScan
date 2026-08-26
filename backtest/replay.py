"""
Replay

Walks a stored history of OptionsChain snapshots in chronological order,
fitting a fresh VolatilitySurface and running outlier detection at each
step. This is the v1 focus: prove the detection logic out against saved
data before ever worrying about a live polling loop.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from ..data.snapshot_store import SnapshotStore
from ..detection.outliers import Anomaly, SurfaceOutlierDetector
from ..surface import VolatilitySurface


@dataclass
class ReplayStepResult:
    snapshot_time: datetime
    anomalies: List[Anomaly]
    fit_quality: dict


@dataclass
class SkippedStep:
    snapshot_time: datetime
    reason: str


@dataclass
class ReplayResult:
    ticker: str
    steps: List[ReplayStepResult] = field(default_factory=list)
    skipped: List[SkippedStep] = field(default_factory=list)

    def all_anomalies(self) -> List[tuple[datetime, Anomaly]]:
        return [(s.snapshot_time, a) for s in self.steps for a in s.anomalies]

    def summary(self) -> str:
        n_steps = len(self.steps)
        n_skipped = len(self.skipped)
        n_anom = sum(len(s.anomalies) for s in self.steps)
        return (
            f"{self.ticker}: {n_steps} snapshots replayed, {n_skipped} skipped, "
            f"{n_anom} anomalies flagged"
        )


class ReplayEngine:
    def __init__(
        self,
        store: SnapshotStore,
        option_type: str = "call",
        min_volume: float = 0,
        z_threshold: float = 3.0,
    ):
        self.store = store
        self.option_type = option_type
        self.min_volume = min_volume
        self.z_threshold = z_threshold

    def run(
        self,
        ticker: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> ReplayResult:
        result = ReplayResult(ticker=ticker)

        for snapshot_time in self.store.list_snapshot_times(ticker):
            if start and snapshot_time < start:
                continue
            if end and snapshot_time > end:
                continue

            chain = self.store.load(ticker, snapshot_time)
            try:
                surface = VolatilitySurface(
                    chain, option_type=self.option_type, min_volume=self.min_volume
                ).fit()
            except ValueError as e:
                result.skipped.append(
                    SkippedStep(snapshot_time=snapshot_time, reason=str(e))
                )
                continue

            anomalies = SurfaceOutlierDetector(
                surface, z_threshold=self.z_threshold
            ).detect()
            result.steps.append(
                ReplayStepResult(
                    snapshot_time=snapshot_time,
                    anomalies=anomalies,
                    fit_quality=surface.fit_quality(),
                )
            )

        return result
