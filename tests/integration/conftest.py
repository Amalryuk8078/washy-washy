"""Shared fixture for database integration tests.

These tests need a real, migrated PostgreSQL database (``alembic upgrade
head`` — see docker-compose.yml for a local Postgres). ``db_session``
skips the test cleanly, instead of failing, when that isn't available so
the default ``pytest`` run stays self-contained (same pattern as
``tests/integration/test_database_connection.py``).

Each test runs inside its own outer transaction that is always rolled
back on teardown, via SQLAlchemy's documented "join a session into an
external transaction" recipe (``join_transaction_mode="create_savepoint"``)
— so tests never leave residue in a shared dev database, and a
``session.commit()``/``session.rollback()`` inside the code under test
operates on a savepoint rather than ending the real transaction early.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.engine import get_engine


@pytest.fixture
async def db_session():
    engine = get_engine()
    try:
        connection = await engine.connect()
    except Exception as exc:
        pytest.skip(f"PostgreSQL is not reachable: {exc}")

    try:
        # Must start the outer transaction before running any query on this
        # connection — SQLAlchemy 2.0 "autobegin" means the first execute()
        # implicitly opens a transaction, and a later explicit begin() on a
        # connection that already has one raises InvalidRequestError.
        transaction = await connection.begin()

        has_users_table = await connection.scalar(text("SELECT to_regclass('public.users')"))
        if has_users_table is None:
            await transaction.rollback()
            pytest.skip("RBAC tables not migrated — run `alembic upgrade head` first")

        session = AsyncSession(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()
    finally:
        await connection.close()
