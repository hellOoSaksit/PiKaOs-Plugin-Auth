"""Auth + RBAC plugin — authentication (login/JWT/sessions) + authorization (roles/permissions).

Binds the `identity.Provider` contract so the kernel's identity dependencies (get_current_user /
require_perm / require_role in app/core/identity.py) resolve real users + permissions, and mounts
`/api/auth`. The kernel owns the identity *interface* + FastAPI deps; this plugin is the
*implementation*.

Data layer (Phase C): the User/Role/Permission/Department models, the users/rbac repositories,
`security` (JWT/argon2), and the seed all live IN this plugin now, on its own declarative `Base`
(models.py). The plugin's tables are created + seeded by `migrate.migrate()`, invoked per enabled
plugin by the kernel's `scripts.migrate_plugins` at boot — Core's Alembic no longer owns auth tables.
Cross-plugin refs are logical UUIDs (no FK across the boundary).

Redis: the refresh-token / deny-list / perms-cache session store (`session_store.py`) left the kernel
with the Redis extraction — it resolves the aioredis client from the `redis.Connection` contract (bound
by the redis tool, a declared `dependency`) at register(), so auth reaches Redis through DI, not a kernel
import.

Package surface the Loader looks for (plugin-architecture.md §5/§10):
  router    — mounted by the Loader when this plugin is enabled
  register  — binds `identity.Provider` + wires the Redis session store from `redis.Connection`
  migrate   — install-time schema step (create_all + seed), run by scripts.migrate_plugins
"""
from .router import router


def register(ctx) -> None:
    """Bind the auth identity provider (JWT decode + user/permission lookup) under the IDENTITY token, and
    wire the Redis session store from the `redis.Connection` contract so refresh tokens / the deny-list /
    the perms cache work. Redis boots first (a declared dependency); if it is somehow absent the store
    degrades exactly like a Redis outage (fail-open reads)."""
    from ...core.contracts import IDENTITY, POSTGRES_CONNECTION, REDIS_CONNECTION
    from .provider import AuthIdentityProvider
    from . import login_throttle, session_store

    redis_client = ctx.container.resolve(REDIS_CONNECTION)
    session_store.bind(redis_client)
    login_throttle.bind(redis_client)  # the login brute-force guard shares the same Redis client
    # Zero-datastore kernel: the session factory comes from the postgres Tool's contract (a declared
    # dependency, so it registered first), not a kernel SessionLocal passed on ctx.
    sf = ctx.container.resolve(POSTGRES_CONNECTION)["session_factory"]
    ctx.container.bind(IDENTITY, AuthIdentityProvider(sf))


__all__ = ["router", "register"]
