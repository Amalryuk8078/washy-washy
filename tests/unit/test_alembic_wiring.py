"""Verifies Alembic is wired correctly without requiring a live database.

``core/migrations/env.py`` only runs its migration logic when invoked
through the ``alembic`` command itself (it reads ``alembic.context``,
which is unconfigured otherwise), so it cannot be safely imported
directly in a unit test. Instead these tests check the two things that
would break Alembic before it even gets that far: the script directory
resolving from ``alembic.ini``, and ``core.models`` (what ``env.py``
imports to populate ``Base.metadata``) being importable on its own,
without starting the FastAPI app or opening a database connection.
"""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_alembic_script_directory_loads() -> None:
    config = Config(str(REPO_ROOT / "alembic.ini"))
    script = ScriptDirectory.from_config(config)
    assert Path(script.dir).resolve() == REPO_ROOT / "src" / "core" / "migrations"


def test_core_models_import_without_starting_app_or_db() -> None:
    import core.models

    assert core.models.Base.metadata is not None
