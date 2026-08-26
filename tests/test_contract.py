from datetime import date, datetime

import pytest

from tests.helpers import make_contract


def test_option_type_normalization():
    assert make_contract(option_type="C").option_type == "call"
    assert make_contract(option_type="Put").option_type == "put"
    assert make_contract(option_type="call").is_call
    assert make_contract(option_type="put").is_put


def test_invalid_option_type_raises():
    with pytest.raises(ValueError):
        make_contract(option_type="banana")


def test_naive_snapshot_time_is_normalized_to_utc():
    c = make_contract(snapshot_time=datetime(2026, 8, 17, 15, 0))  # naive, no tzinfo
    assert c.snapshot_time.tzinfo is not None
    assert c.snapshot_time.utcoffset().total_seconds() == 0


def test_aware_snapshot_time_is_left_alone():
    from datetime import timezone

    aware = datetime(2026, 8, 17, 15, 0, tzinfo=timezone.utc)
    c = make_contract(snapshot_time=aware)
    assert c.snapshot_time is aware


def test_mid_price_uses_bid_ask_when_valid():
    c = make_contract(bid=1.0, ask=1.2)
    assert c.mid_price == pytest.approx(1.1)


def test_mid_price_falls_back_to_last_when_bid_ask_are_zero():
    c = make_contract(bid=0, ask=0, last_price=1.05)
    assert c.mid_price == 1.05


def test_valid_contract_has_no_invalid_reason():
    c = make_contract()
    assert c.is_valid
    assert c.invalid_reason is None


def test_crossed_market_is_invalid():
    c = make_contract(bid=10.0, ask=5.0)
    assert not c.is_valid
    assert "crossed" in c.invalid_reason.lower()


def test_negative_strike_is_invalid():
    c = make_contract(strike=-10.0)
    assert not c.is_valid


def test_non_positive_underlying_price_is_invalid():
    c = make_contract(underlying_price=0.0)
    assert not c.is_valid


def test_negative_bid_or_ask_is_invalid():
    assert not make_contract(bid=-1.0).is_valid
    assert not make_contract(ask=-1.0).is_valid


def test_already_expired_contract_is_invalid():
    c = make_contract(
        expiry=date(2020, 1, 1),
        snapshot_time=datetime(2026, 8, 17, 15, 0),
    )
    assert not c.is_valid
    assert "expired" in c.invalid_reason.lower()


def test_time_to_expiry_is_never_zero_or_negative():
    c = make_contract(
        expiry=date(2026, 8, 17),
        snapshot_time=datetime(2026, 8, 17, 9, 30),
    )
    assert c.time_to_expiry > 0


def test_log_moneyness_zero_at_the_money():
    c = make_contract(strike=100.0, underlying_price=100.0)
    assert c.log_moneyness == pytest.approx(0.0, abs=1e-12)


def test_to_dict_from_dict_round_trip():
    c = make_contract()
    restored = type(c).from_dict(c.to_dict())
    assert restored.strike == c.strike
    assert restored.expiry == c.expiry
    assert restored.option_type == c.option_type
    assert restored.implied_vol == c.implied_vol
