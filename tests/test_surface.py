import numpy as np
import pytest

from optionsurface.chain import OptionsChain
from optionsurface.surface import VolatilitySurface
from tests.helpers import make_contract


def test_raises_with_too_few_points():
    t_contracts = [
        make_contract(contract_symbol=f"K{i}", strike=90 + i, volume=100)
        for i in range(4)
    ]
    chain = OptionsChain.from_contracts(
        "TEST", t_contracts[0].snapshot_time, t_contracts
    )
    with pytest.raises(ValueError, match="need at least 6"):
        VolatilitySurface(chain, option_type="call")


def test_fit_quality_is_high_on_clean_synthetic_data(synthetic_chain):
    chain, _ = synthetic_chain
    surface = VolatilitySurface(chain, option_type="call").fit()
    quality = surface.fit_quality()
    assert quality["r_squared"] > 0.85
    assert quality["n_points"] == len(chain.filter(option_type="call").contracts)


def test_leverage_is_between_zero_and_one(synthetic_chain):
    chain, _ = synthetic_chain
    surface = VolatilitySurface(chain, option_type="call").fit()
    for p in surface.points():
        assert 0.0 <= p.leverage < 1.0


def test_loo_residual_is_at_least_as_large_as_raw_residual(synthetic_chain):
    chain, _ = synthetic_chain
    surface = VolatilitySurface(chain, option_type="call").fit()
    for p in surface.points():
        assert abs(p.loo_residual) >= abs(p.residual) - 1e-9


def test_predict_matches_points_at_original_coordinates(synthetic_chain):
    chain, _ = synthetic_chain
    surface = VolatilitySurface(chain, option_type="call").fit()
    pts = surface.points()
    xs = np.array([p.x for p in pts])
    ys = np.array([p.y for p in pts])
    predicted = surface.predict(xs, ys)
    fitted_from_points = np.array([p.fitted_iv for p in pts])
    assert np.allclose(predicted, fitted_from_points)


def test_predict_before_fit_raises():
    contracts = [
        make_contract(contract_symbol=f"K{i}", strike=90 + i, volume=100)
        for i in range(8)
    ]
    chain = OptionsChain.from_contracts("TEST", contracts[0].snapshot_time, contracts)
    surface = VolatilitySurface(chain, option_type="call")
    with pytest.raises(RuntimeError):
        surface.predict(0.0, 0.1)
