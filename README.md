# PiKaOs-Plugin-Auth

Authentication + RBAC as a PiKaOs plugin (id `auth`, kind `capability`). Binds the kernel's
`identity.Provider` contract (login/JWT/sessions + roles/permissions) and mounts `/api/auth`.

Drops into Core at `app/plugins/auth` (via `link-plugins.sh`). The kernel owns the identity
*interface* + FastAPI deps (`app/core/identity.py`); this plugin is the *implementation*.

Status: Phase B (service layer: auth_service, rbac_service, router, provider). The data layer
(User/Role models, users/rbac repositories, `security`, seed) still lives in the Base and moves into
this plugin's own schema + migration in a later phase.
