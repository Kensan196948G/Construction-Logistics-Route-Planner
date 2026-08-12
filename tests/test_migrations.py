from __future__ import annotations

import os
import tempfile
from pathlib import Path

from alembic import command
from alembic.config import Config


def _config() -> Config:
    repo_root = Path(__file__).resolve().parents[1]
    config = Config(str(repo_root / "alembic.ini"))
    config.set_main_option("script_location", str(repo_root / "alembic"))
    return config


def test_alembic_migrations_apply_and_downgrade(monkeypatch) -> None:
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    Path(db_path).unlink()
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")

    try:
        config = _config()
        command.upgrade(config, "head")
        command.downgrade(config, "base")
    finally:
        Path(db_path).unlink(missing_ok=True)
