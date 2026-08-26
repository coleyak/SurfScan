from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from optionsurface.backtest.replay import ReplayEngine
from optionsurface.chain import OptionsChain
from optionsurface.data.snapshot_store import SnapshotStore
from tests.helpers import build_synthetic_chain


@pytest.fixture(autouse=True)
def csv_backed_parquet(monkeypatch):
    """See test_snapshot_store.py's identical fixture for why."""
    monkeypatch.setattr(
        pd.DataFrame,
        "to_parquet",
        lambda self, path, index=False: self.to_csv(path, index=index),
    )
    monkeypatch.setattr(pd, "read_parquet", lambda path: pd.read_csv(path))


def test_replay_runs_over_stored_snapshots(tmp_path):
    store = SnapshotStore(tmp_path)
    chain, _ = build_synthetic_chain()
    chain.underlying = "SYN"
    store.save(chain)

    result = ReplayEngine(store).run("SYN")
    assert len(result.steps) == 1
    assert len(result.skipped) == 0
    assert result.steps[0].fit_quality["r_squared"] > 0.85


def test_replay_skips_and_records_reason_for_sparse_snapshot(tmp_path):
    store = SnapshotStore(tmp_path)
    good_chain, _ = build_synthetic_chain()
    good_chain.underlying = "SYN"
    store.save(good_chain)

    sparse = OptionsChain.from_contracts(
        "SYN",
        good_chain.snapshot_time + timedelta(minutes=1),
        good_chain.contracts[:3],
    )
    store.save(sparse)

    result = ReplayEngine(store).run("SYN")
    assert len(result.steps) == 1
    assert len(result.skipped) == 1
    assert "need at least 6" in result.skipped[0].reason


def test_replay_respects_start_end_bounds(tmp_path):
    store = SnapshotStore(tmp_path)
    chain, _ = build_synthetic_chain()
    chain.underlying = "SYN"
    t0 = datetime.now(timezone.utc)
    chain.snapshot_time = t0
    store.save(chain)

    chain.snapshot_time = t0 + timedelta(days=1)
    store.save(chain)

    result = ReplayEngine(store).run("SYN", start=t0 + timedelta(hours=1))
    assert len(result.steps) == 1


def test_summary_reports_steps_skipped_and_anomalies(tmp_path):
    store = SnapshotStore(tmp_path)
    chain, planted = build_synthetic_chain()
    chain.underlying = "SYN"
    store.save(chain)

    result = ReplayEngine(store).run("SYN")
    text = result.summary()
    assert "1 snapshots replayed" in text
    assert "0 skipped" in text
