/* Auth plugin — frontend descriptor. Contributes the RBAC/identity management screens (User Management,
   Roles, Permissions, Audit) to Core through the plugin seam (import.meta.glob discovery). Present only
   when this plugin is linked; a kernel-only Core ships none of it. render(ctx) gets Core seams
   { t, can, language, go }; the plugin owns all RBAC state via AuthAdmin. User detail is INTERNAL to the
   admin route (list<->detail), not a Core route. */
import React from 'react';
const { useState } = React;
import { AuthAdmin } from './provider.jsx';
import { Admin } from './admin.jsx';
import { UserDetail, RolesPermissions, PermissionsCatalog, AuditLog } from './rbac.jsx';

// Admin list <-> user detail, kept internal to the plugin (Core no longer holds userSel).
function AdminRoute({ Sys }) {
  const [userId, setUserId] = useState(null);
  const sys = { ...Sys, go: (r) => (r === 'admin' ? setUserId(null) : Sys.go(r)) };
  return userId
    ? <UserDetail Sys={sys} userId={userId} />
    : <Admin Sys={sys} onUser={setUserId} />;
}

const wrap = (Screen) => (ctx) => <AuthAdmin ctx={ctx}>{(Sys) => <Screen Sys={Sys} />}</AuthAdmin>;

// `icon` names come from Core's design-system set (components/ui/icons.jsx) and stay plain
// strings — the shell resolves them, so this descriptor never imports Core.
export default {
  id: 'auth',
  routes: [
    { id: 'admin',       meta: { icon: 'members', title: 'จัดการผู้ใช้',   en: 'User Management' }, render: (ctx) => <AuthAdmin ctx={ctx}>{(Sys) => <AdminRoute Sys={Sys} />}</AuthAdmin> },
    { id: 'roles',       meta: { icon: 'key', title: 'บทบาทและสิทธิ์', en: 'Roles & Access' },  render: wrap(RolesPermissions) },
    { id: 'permissions', meta: { icon: 'security', title: 'แคตตาล็อกสิทธิ์', en: 'Permissions' },     render: wrap(PermissionsCatalog) },
    { id: 'audit',       meta: { icon: 'clipboard-list', title: 'บันทึกการตรวจสอบ', en: 'Audit Log' },       render: wrap(AuditLog) },
  ],
  // Sidebar items merge into Core's existing "ผู้ดูแลระบบ" group (labels resolve from Core's nav.* keys).
  nav: [
    {
      group: 'ผู้ดูแลระบบ',
      items: [
        { id: 'admin', icon: 'members', perm: 'user.view.any' },
        { id: 'permissions', icon: 'security', perm: 'user.view.any', children: [
          { id: 'roles', icon: 'key', perm: 'role.manage' },
        ]},
        { id: 'audit', icon: 'clipboard-list', perm: 'audit.view' },
      ],
    },
  ],
  // CORE_PERMISSIONS (incl. the identity perms) moved with data-users.jsx and is shown by the
  // Permissions screen directly; re-contributing it here would double the catalog. Proper per-plugin
  // permission ownership (splitting CORE_PERMISSIONS across plugins) is a follow-up.
  permissions: [],
};
