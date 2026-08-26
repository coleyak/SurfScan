from datetime import date, datetime, timezone

import numpy as np

from optionsurface.chain import OptionsChain
from optionsurface.contract import OptionContract
from optionsurface.detection.outliers import SurfaceOutlierDetector
from optionsurface.surface import VolatilitySurface
from tests.helpers import build_synthetic_chain


def test_detects_large_planted_anomalies(synthetic_chain):
    chain, planted = synthetic_chain
    surface = VolatilitySurface(chain, option_type="call").fit()
    anomalies = SurfaceOutlierDetector(surface, z_threshold=3.0).detect()

    detected = {a.contract.contract_symbol for a in anomalies}
    caught = detected & set(planted)
    false_positives = detected - set(planted)

    assert len(caught) >= 2
    assert len(false_positives) <= 1


def test_no_anomalies_on_a_perfectly_clean_surface():
    chain, _ = build_synthetic_chain(anomaly_bump_range=(0.0, 0.0), noise_std=0.003)
    surface = VolatilitySurface(chain, option_type="call").fit()
    anomalies = SurfaceOutlierDetector(surface, z_threshold=4.0).detect()
    assert len(anomalies) == 0


def _near_zero_dispersion_chain(bump: float = 0.0):
    """Every point sits exactly on a surface the quadratic basis can
    represent perfectly (no noise, no y-dependence) -- residuals collapse
    toward zero everywhere except the one optionally-bumped point. This is
    the scenario where an unfloored MAD estimate breaks (see outliers.py)."""
    snapshot_time = datetime(2026, 8, 14, 15, 30, tzinfo=timezone.utc)
    expiries = [date(2026, 9, 18), date(2026, 10, 16), date(2026, 11, 20)]
    strikes = np.linspace(80, 120, 10)

    contracts = []
    for expiry in expiries:
        for i, strike in enumerate(strikes):
            x = np.log(strike / 100.0)
            iv = 0.20 - 0.10 * x + 0.40 * x**2
            contracts.append(
                OptionContract(
                    contract_symbol=f"K{strike:.0f}_{expiry.isoformat()}",
                    underlying="T",
                    underlying_price=100.0,
                    strike=float(strike),
                    expiry=expiry,
                    option_type="call",
                    snapshot_time=snapshot_time,
                    bid=1.0,
                    ask=1.1,
                    volume=100,
                    open_interest=100,
                    implied_vol=iv,
                )
            )

    bumped_symbol = None
    if bump:
        target = contracts[len(contracts) // 2]
        target.implied_vol += bump
        bumped_symbol = target.contract_symbol

    return OptionsChain.from_contracts("T", snapshot_time, contracts), bumped_symbol


def test_mad_floor_keeps_zscores_finite_under_near_zero_dispersion():
    chain, bumped_symbol = _near_zero_dispersion_chain(bump=0.015)
    surface = VolatilitySurface(chain, option_type="call").fit()
    anomalies = SurfaceOutlierDetector(
        surface, z_threshold=3.0, min_scale=0.0025
    ).detect()
    assert all(np.isfinite(a.z_score) and abs(a.z_score) < 10_000 for a in anomalies)
    detected = {a.contract.contract_symbol for a in anomalies}
    assert bumped_symbol in detected


def test_detection_rate_increases_with_anomaly_size():
    """Calibration-style check: bigger mispricings should be caught at
    least as often as smaller ones, averaged over several random seeds --
    not just "it catches the one huge anomaly we hand-picked"."""
    bump_sizes = [0.01, 0.03, 0.06, 0.10]
    seeds = range(5)
    detection_rates = []

    for bump in bump_sizes:
        hits = 0
        for seed in seeds:
            chain, planted = build_synthetic_chain(
                anomaly_bump_range=(bump, bump), seed=seed, noise_std=0.005
            )
            surface = VolatilitySurface(chain, option_type="call").fit()
            anomalies = SurfaceOutlierDetector(surface, z_threshold=3.0).detect()
            detected = {a.contract.contract_symbol for a in anomalies}
            hits += len(detected & set(planted))
        detection_rates.append(hits / (len(seeds) * len(planted)))
