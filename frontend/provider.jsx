/* Auth plugin — RBAC state container. Owns users/roles/rolePerms/userPerms (persisted to localStorage
   exactly as Core did) and the mutation bundle the RBAC screens consume as `Sys`. Audit rows come from
   Core's real trail (GET /api/audit via ctx.api.raw), fetched on mount — a security screen must never
   fabricate rows, so on any fetch error the AuditLog screen renders its error state instead of a seed.
   Rendered per plugin route via a render-prop; state stays consistent across routes because every
   mutation persists immediately and each mount re-reads localStorage. Also renders the UserForm overlay
   (opened via Sys.openUserForm). */
import React from 'react';
const { useState, useEffect } = React;
import {
  USERS_SEED, ROLES_SEED, ROLE_PERMS_SEED, USER_PERMS_SEED,
  loadU, saveU,
} from './data-users.jsx';
import { UserForm } from './rbac.jsx';

export function AuthAdmin({ ctx, children }) {
  const { t, can, language, go } = ctx;
  const T = (en, th) => (language === 'en' ? en : th);

  const [users, setUsers] = useState(() => loadU('users', USERS_SEED));
  const [roles, setRoles] = useState(() => loadU('roles', ROLES_SEED));
  // Migration: seeds gained room.*/character.*/options.* perms after some users already had a
  // persisted rolePerms map; merge those seed-only keys into whatever was loaded so upgrades don't
  // silently drop newly-added permissions from existing role grants.
  const [rolePerms, setRolePerms] = useState(() => {
    const loaded = loadU('rolePerms', ROLE_PERMS_SEED);
    const out = { ...loaded };
    for (const rk of Object.keys(ROLE_PERMS_SEED)) {
      const cur = new Set(out[rk] || []);
      ROLE_PERMS_SEED[rk].filter(k => /^room\.|^character\.|^options\./.test(k)).forEach(k => cur.add(k));
      out[rk] = [...cur];
    }
    return out;
  });
  const [userPerms, setUserPerms] = useState(() => loadU('userPerms', USER_PERMS_SEED));
  // Real trail from Core's /api/audit (v2). No seed fallback — a security screen must never
  // render fabricated rows; on any fetch error the screen shows its error state instead.
  const [audit, setAudit] = useState([]);
  const [auditError, setAuditError] = useState(false);
  useEffect(() => {
    let alive = true;
    if (!ctx.api?.raw) { setAuditError(true); return undefined; }
    ctx.api.raw('/audit?limit=200')
      .then((rows) => { if (alive) setAudit(Array.isArray(rows) ? rows : []); })
      .catch(() => { if (alive) setAuditError(true); });
    return () => { alive = false; };
  }, []);
  const [userForm, setUserForm] = useState(null);

  useEffect(() => { saveU('users', users); }, [users]);
  useEffect(() => { saveU('roles', roles); }, [roles]);
  useEffect(() => { saveU('rolePerms', rolePerms); }, [rolePerms]);
  useEffect(() => { saveU('userPerms', userPerms); }, [userPerms]);

  const Sys = {
    users, roles, rolePerms, userPerms, audit, auditError, can, T, t, language, go,
    me: ctx.me || {},   // never null: RBAC screens read Sys.me.id (e.g. don't-suspend-self guard)
    openUserForm: (u) => setUserForm(u || {}),
    saveUser: (f, edit) => {
      if (edit) { setUsers(prev => prev.map(x => x.id === f.id ? { ...x, ...f } : x)); }
      else {
        const id = 'u_' + String(f.username || ('user' + Date.now())).toLowerCase();
        setUsers(prev => [...prev, { ...f, id, used: 0, lastLogin: T('never', 'ยังไม่เข้า'), joined: T('just now', 'เพิ่งสร้าง') }]);
      }
    },
    toggleSuspend: (u) => {
      const next = u.status === 'active' ? 'suspended' : 'active';
      setUsers(prev => prev.map(x => x.id === u.id ? { ...x, status: next } : x));
    },
    setRole: (u, role) => setUsers(prev => prev.map(x => x.id === u.id ? { ...x, role } : x)),
    setQuota: (u, q) => setUsers(prev => prev.map(x => x.id === u.id ? { ...x, quota: q } : x)),
    resetUsage: (u) => setUsers(prev => prev.map(x => x.id === u.id ? { ...x, used: 0 } : x)),
    setUserPerm: (u, key, effect) => {
      setUserPerms(prev => {
        const cur = { ...(prev[u.id] || {}) };
        if (effect == null) delete cur[key]; else cur[key] = effect;
        return { ...prev, [u.id]: cur };
      });
    },
    setRolePerm: (roleKey, key, on) => {
      setRolePerms(prev => {
        const cur = new Set(prev[roleKey] || []);
        if (on) cur.add(key); else cur.delete(key);
        return { ...prev, [roleKey]: [...cur] };
      });
    },
    addRole: () => {
      const key = 'role_' + Date.now();
      window.uiPrompt({ title: T('New role', 'เพิ่มบทบาท'), placeholder: T('Role name', 'ชื่อบทบาท') }).then(name => {
        if (!name) return;
        setRoles(prev => [...prev, { key, th: name, en: name, desc: '', system: false, color: '' }]);
        setRolePerms(prev => ({ ...prev, [key]: [] }));
      });
    },
  };

  return (
    <>
      {children(Sys)}
      {userForm && <UserForm Sys={Sys} initial={userForm.id ? userForm : null} onClose={() => setUserForm(null)} />}
    </>
  );
}
