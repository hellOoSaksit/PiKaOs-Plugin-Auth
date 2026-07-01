"""Install-time schema step for the auth plugin.

The kernel migration runner (`scripts.migrate_plugins`) calls `migrate(engine, session_factory)` for
each enabled plugin after Core's own Alembic baseline. Auth owns its tables on its own `Base` metadata
(models.py), so here we create them + seed the base roles/permissions/users.

Functional/fresh-DB model (locked decision): plain `create_all` on the plugin's metadata, not a
versioned Alembic history yet — per-plugin Alembic is a later hardening step.
"""
from __future__ import annotations

from .models import Base
from .seed import seed


async def migrate(engine, session_factory) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed(session_factory)
