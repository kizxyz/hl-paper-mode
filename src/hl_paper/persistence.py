from __future__ import annotations

import json
import logging
from typing import Any

import aiosqlite

from hl_paper.models import AccountState, Fill

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY,
    data TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


class StateStore:
    """SQLite persistence — batched writes, snapshot every ~60s."""

    def __init__(self, db_path: str = "hl_paper.db") -> None:
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def init(self) -> None:
        self._db = await aiosqlite.connect(self.db_path)
        await self._db.executescript(SCHEMA)
        await self._db.commit()

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None

    async def save_snapshot(self, state: AccountState) -> None:
        """Save account state snapshot. Overwrites previous."""
        data = state.model_dump_json()
        await self._db.execute("DELETE FROM snapshots")
        await self._db.execute("INSERT INTO snapshots (id, data) VALUES (1, ?)", (data,))
        await self._db.commit()
        logger.debug("Snapshot saved")

    async def load_snapshot(self) -> AccountState | None:
        """Load most recent snapshot. Returns None if no snapshot exists."""
        cursor = await self._db.execute("SELECT data FROM snapshots WHERE id = 1")
        row = await cursor.fetchone()
        if row is None:
            return None
        return AccountState.model_validate_json(row[0])

    async def log_fill(self, fill: Fill) -> None:
        """Append a fill to the log (batched — caller controls commit timing)."""
        data = fill.model_dump_json()
        await self._db.execute("INSERT INTO fills (data) VALUES (?)", (data,))
        await self._db.commit()

    async def get_fills(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent fills."""
        cursor = await self._db.execute(
            "SELECT data FROM fills ORDER BY id DESC LIMIT ?", (limit,)
        )
        rows = await cursor.fetchall()
        return [json.loads(row[0]) for row in rows]
