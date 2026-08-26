from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from optionsurface.data.snapshot_store import SnapshotStore
from tests.helpers import build_synthetic_chain


@pytest.fixture(autouse=True)
def csv_backed_parquet(monkeypatch):
    """SnapshotStore is written against pandas' to_parquet/read_parquet, but
    a parquet engine (pyarrow/fastparquet) isn't always available in every
    test environment. Swap in CSV under the hood for these tests -- it
    exercises the same store logic (paths, collisions, tz handling)
    without depending on which parquet engine happens to be installed.
    Real usage should install pyarrow (see requirements.txt) and get real
    parquet files; this fixture only affects this test module.
    """
    monkeypatch.setattr(
        pd.DataFrame,
        "to_parquet",
        lambda self, path, index=False: self.to_csv(path, index=index),
    )
    monkeypatch.setattr(pd, "read_parquet", lambda path: pd.read_csv(path))


def test_reading_unknown_ticker_does_not_create_its_directory(tmp_path):
    store = SnapshotStore(tmp_path)
    assert not (tmp_path / "AAPL").exists()
    assert store.list_snapshot_times("AAPL") == []
    assert not (tmp_path / "AAPL").exists()


def test_save_and_load_round_trip(tmp_path):
    store = SnapshotStore(tmp_path)
    chain, _ = build_synthetic_chain()
    chain.underlying = "SYN"
    store.save(chain)

    times = store.list_snapshot_times("SYN")
    assert len(times) == 1
    loaded = store.load("SYN", times[0])
    assert len(loaded) == len(chain)


def test_same_second_snapshots_do_not_collide(tmp_path):
    store = SnapshotStore(tmp_path)
    chain, _ = build_synthetic_chain()
    chain.underlying = "SYN"

    t0 = datetime.now(timezone.utc)
    chain.snapshot_time = t0
    path1 = store.save(chain)
    chain.snapshot_time = t0 + timedelta(milliseconds=250)
    path2 = store.save(chain)

    assert path1 != path2
    assert len(store.list_snapshot_times("SYN")) == 2


def test_stored_timestamps_are_utc_aware(tmp_path):
    store = SnapshotStore(tmp_path)
    chain, _ = build_synthetic_chain()
    chain.underlying = "SYN"
    store.save(chain)
    times = store.list_snapshot_times("SYN")
    assert all(t.tzinfo is not None for t in times)


def test_load_range_accepts_naive_datetimes(tmp_path):
    store = SnapshotStore(tmp_path)
    chain, _ = build_synthetic_chain()
    chain.underlying = "SYN"
    store.save(chain)

    naive_start = datetime.utcnow() - timedelta(minutes=5)  # no tzinfo
    chains = store.load_range("SYN", start=naive_start)  # should not raise
    assert len(chains) == 1


def test_tickers_lists_only_directories_with_data(tmp_path):
    store = SnapshotStore(tmp_path)
    chain, _ = build_synthetic_chain()
    chain.underlying = "SYN"
    store.save(chain)
    assert store.tickers() == ["SYN"]
