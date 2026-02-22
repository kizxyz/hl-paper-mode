import asyncio
import os
import tempfile

import pytest

from hl_paper.models import AccountState, Position, Side
from hl_paper.persistence import StateStore


@pytest.fixture
def db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    os.unlink(path)


@pytest.fixture
def state_with_position():
    state = AccountState(balance=9500.0)
    state.positions["BTC"] = Position(
        symbol="BTC", side=Side.BUY, size=0.1,
        entry_price=50000.0, leverage=10, mmr=0.05,
    )
    return state


class TestStateStore:
    def test_save_and_load(self, db_path, state_with_position):
        async def run():
            store = StateStore(db_path)
            await store.init()
            await store.save_snapshot(state_with_position)

            loaded = await store.load_snapshot()
            assert loaded is not None
            assert loaded.balance == pytest.approx(9500.0)
            assert "BTC" in loaded.positions
            assert loaded.positions["BTC"].size == pytest.approx(0.1)
            await store.close()

        asyncio.run(run())

    def test_load_empty_db(self, db_path):
        async def run():
            store = StateStore(db_path)
            await store.init()
            loaded = await store.load_snapshot()
            assert loaded is None
            await store.close()

        asyncio.run(run())

    def test_save_overwrites(self, db_path, state_with_position):
        async def run():
            store = StateStore(db_path)
            await store.init()

            await store.save_snapshot(state_with_position)

            state2 = AccountState(balance=8000.0)
            await store.save_snapshot(state2)

            loaded = await store.load_snapshot()
            assert loaded.balance == pytest.approx(8000.0)
            assert len(loaded.positions) == 0
            await store.close()

        asyncio.run(run())

    def test_save_fill_log(self, db_path):
        async def run():
            from hl_paper.models import Fill

            store = StateStore(db_path)
            await store.init()

            fill = Fill(
                symbol="BTC", side=Side.BUY, size=0.1,
                price=50000.0, fee=2.25, timestamp=1000,
            )
            await store.log_fill(fill)

            fills = await store.get_fills()
            assert len(fills) == 1
            assert fills[0]["symbol"] == "BTC"
            await store.close()

        asyncio.run(run())
