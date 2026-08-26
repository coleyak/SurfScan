from datetime import date, datetime, timezone

from optionsurface.chain import OptionsChain
from tests.helpers import make_contract


def _mixed_chain():
    t = datetime(2026, 8, 17, 15, 0, tzinfo=timezone.utc)
    contracts = [
        make_contract(
            contract_symbol="good_call",
            option_type="call",
            strike=100,
            volume=500,
            snapshot_time=t,
        ),
        make_contract(
            contract_symbol="good_put",
            option_type="put",
            strike=100,
            volume=500,
            snapshot_time=t,
        ),
        make_contract(
            contract_symbol="crossed",
            option_type="call",
            strike=105,
            bid=10,
            ask=5,
            snapshot_time=t,
        ),
        make_contract(
            contract_symbol="illiquid",
            option_type="call",
            strike=110,
            volume=0,
            snapshot_time=t,
        ),
    ]
    return OptionsChain.from_contracts("TEST", t, contracts)


def test_calls_and_puts_split_correctly():
    chain = _mixed_chain()
    assert {c.contract_symbol for c in chain.calls()} == {
        "good_call",
        "crossed",
        "illiquid",
    }
    assert {c.contract_symbol for c in chain.puts()} == {"good_put"}


def test_filter_drops_invalid_contracts_by_default():
    chain = _mixed_chain()
    filtered = chain.filter()
    symbols = {c.contract_symbol for c in filtered.contracts}
    assert "crossed" not in symbols
    assert "good_call" in symbols


def test_filter_can_keep_invalid_contracts_if_asked():
    chain = _mixed_chain()
    filtered = chain.filter(require_valid=False, require_iv=False)
    symbols = {c.contract_symbol for c in filtered.contracts}
    assert "crossed" in symbols


def test_invalid_contracts_reports_the_crossed_market():
    chain = _mixed_chain()
    invalid = chain.invalid_contracts()
    assert [c.contract_symbol for c in invalid] == ["crossed"]


def test_filter_by_min_volume():
    chain = _mixed_chain()
    filtered = chain.filter(min_volume=1)
    symbols = {c.contract_symbol for c in filtered.contracts}
    assert "illiquid" not in symbols
    assert "good_call" in symbols


def test_filter_returns_new_object_without_mutating_original():
    chain = _mixed_chain()
    original_len = len(chain)
    chain.filter(min_volume=1)
    assert len(chain) == original_len  # unchanged


def test_expiries_are_sorted_and_deduplicated():
    t = datetime(2026, 8, 17, 15, 0, tzinfo=timezone.utc)
    contracts = [
        make_contract(strike=100, expiry=date(2026, 10, 16), snapshot_time=t),
        make_contract(strike=105, expiry=date(2026, 9, 18), snapshot_time=t),
        make_contract(strike=110, expiry=date(2026, 9, 18), snapshot_time=t),
    ]
    chain = OptionsChain.from_contracts("TEST", t, contracts)
    assert chain.expiries() == [date(2026, 9, 18), date(2026, 10, 16)]


def test_dataframe_round_trip_preserves_contract_count():
    chain = _mixed_chain()
    df = chain.to_dataframe()
    restored = OptionsChain.from_dataframe(
        df, underlying=chain.underlying, snapshot_time=chain.snapshot_time
    )
    assert len(restored) == len(chain)
