"""Install-time schema step for the auth plugin.

The kernel migration runner (`scripts.migrate_plugins`) calls `migrate(engine, session_factory)` for
each enabled plugin after Core's own Alembic baseline. Auth owns its tables on its own `Base` metadata
(models.py), so here we create them + seed the base roles/permissions/users.

Functional/fresh-DB model (locked decision): plain `create_all` on the plugin's metadata, not a
versioned Alembic history yet — per-plugin Alembic is a later hardening step.
"""
from __future__ import annotations

from ...core import setup_state
from . import users_repo
from .models import Base
from .seed import seed


async def migrate(engine, session_factory) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed(session_factory)
    # Runs after seeding so a SEED_DEV_USERS=1 dev stack (users already exist) never opens the window.
    await ensure_bootstrap_window(session_factory)


async def ensure_bootstrap_window(session_factory) -> None:
    """Auth enabled but ZERO users → revive a console setup code so the operator can create the first
    admin (POST /api/auth/bootstrap-admin). Runs in the entrypoint after generate_setup_code cleared
    the first-run code (auth enabled ⇒ mode "login"), still before any uvicorn worker — one code per
    boot, every worker reads it from kernel state. With an owner present this is a no-op, so the code
    stays cleared forever after bootstrap."""
    async with session_factory() as db:
        if await users_repo.count_users(db) > 0:
            return
    code = setup_state.generate_code()
    setup_state.write(code, setup_state.generate_session_token())
    rule = "═" * 66
    print(rule)
    for line in ("PiKaOs — auth is installed but has no users yet", "",
                 code, "",
                 "Enter this code to create the first admin account.",
                 "It rotates on every restart and dies once the admin exists."):
        print(line.center(66) if line else "")
    print(rule)
