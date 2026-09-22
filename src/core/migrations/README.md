# Core Migrations

This directory holds the Alembic migration environment shared by the whole
application. Migrations are owned by `core` because database models are
owned by `core.models` — service packages under `src/washy_washy` (and any
future service package) do **not** get their own migration folders.

Layout:

```text
src/core/migrations/
├── README.md
├── env.py            # Alembic environment, wires up core.database.Base
├── script.py.mako     # Revision template
└── versions/           # Generated migration scripts
```

Common commands (run from the repository root, where `alembic.ini` lives):

```bash
alembic revision --autogenerate -m "message"
alembic upgrade head
alembic downgrade -1
```
