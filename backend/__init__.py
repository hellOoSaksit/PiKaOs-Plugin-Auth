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

Package surface the Loader looks for (plugin-architecture.md §5/§10):
  router    — mounted by the Loader when this plugin is enabled
  register  — binds the `identity.Provider` contract into the DI container
  migrate   — install-time schema step (create_all + seed), run by scripts.migrate_plugins
"""
from .router import router


def register(ctx) -> None:
    """Bind the auth identity provider (JWT decode + user/permission lookup) into the DI container under
    the IDENTITY token, so the kernel's identity deps resolve real users instead of the deny-all
    bootstrap fallback."""
    from ...core.contracts import IDENTITY
    from .provider import AuthIdentityProvider

    ctx.container.bind(IDENTITY, AuthIdentityProvider(ctx.session_factory))


__all__ = ["router", "register"]
