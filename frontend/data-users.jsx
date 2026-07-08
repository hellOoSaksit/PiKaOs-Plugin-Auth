/* PiKaOs — ES module (migrated from PiKaOs-Core/data-users.jsx). */
import { PLUGIN_PERMISSIONS } from '../index.jsx';

/* ============================================================
   USERS / RBAC / AUDIT — real people who log in (distinct from agents).
   Mock data + permission resolver. Persisted to localStorage so
   edits (role, quota, suspend, permission overrides) survive reload.
   ============================================================ */

/* ---- KERNEL/CORE permission catalog ----
   Only the perms Core itself owns. Feature-plugin perms (codex.* → knowledge, room.* → world, …) are NO
   LONGER listed here: each plugin declares its own in its descriptor (`permissions`), and the effective
   catalog below merges them in. So installing a plugin adds its perms (RBAC screen + admin grant) and
   removing it drops them — no edit to this file (plugin-architecture §0, dynamic permissions). `workflow.
   manage` stays for now because Workflows isn't a plugin yet (moves to its descriptor in P5). */
const CORE_PERMISSIONS = [
  { key: "agent.create",     group: "Agents",    th: "สร้าง Agent",            en: "Create agents" },
  { key: "agent.appearance", group: "Agents",    th: "แก้รูปลักษณ์/คลาส Agent", en: "Edit appearance & class" },
  { key: "character.manage", group: "Agents",    th: "เพิ่ม/จัดการการ์ดตัวละคร", en: "Manage character cards" },
  { key: "options.manage",   group: "Agents",    th: "เพิ่มตัวเลือก ตำแหน่ง/ทักษะ/เครื่องมือ", en: "Add roster options" },
  { key: "rules.manage",     group: "Agents",    th: "แก้กฎหลัก (บังคับทุกตัว)", en: "Manage core rules" },
  { key: "agent.config",     group: "Agents",    th: "แก้ตั้งค่าขั้นสูง (ตำแหน่ง/หน้าที่/โมเดล/API)", en: "Edit advanced config" },
  { key: "profile.manage",   group: "Agents",    th: "สร้าง/จัดการโปรไฟล์ (Profile)", en: "Manage profiles" },
  { key: "agent.edit.any",   group: "Agents",    th: "แก้ Agent ของผู้อื่น",   en: "Edit any agent" },
  { key: "agent.delete.any", group: "Agents",    th: "ลบ Agent ของผู้อื่น",    en: "Delete any agent" },
  { key: "task.run",        group: "Work",      th: "สั่งรันงาน/งาน",        en: "Run quests" },
  { key: "task.delete",      group: "Work",      th: "ลบงาน (Task)",           en: "Delete tasks" },
  { key: "workflow.manage",  group: "Workflows", th: "จัดการ workflow",        en: "Manage workflows" },
  { key: "token.manage",     group: "Admin",     th: "ตั้งโควตาโทเคน",         en: "Manage token quota" },
  { key: "user.view.any",    group: "Admin",     th: "ดูข้อมูลสมาชิก",          en: "View any user" },
  { key: "user.manage",      group: "Admin",     th: "จัดการสมาชิก",            en: "Manage users" },
  { key: "role.manage",      group: "Admin",     th: "จัดการบทบาท/สิทธิ์",     en: "Manage roles" },
  { key: "audit.view",       group: "Admin",     th: "ดูบันทึกการตรวจสอบ",     en: "View audit log" },
  { key: "llm.view",         group: "Admin",     th: "ดูการตั้งค่า LLM/โมเดล", en: "View LLM provider config" },
  { key: "llm.manage",       group: "Admin",     th: "ตั้งค่า LLM/โมเดล (provider/API หรือ Local)", en: "Manage LLM provider config" },
  { key: "llm.assign",       group: "Admin",     th: "มอบหมายโมเดลให้ระบบ (engine/search/summarize)", en: "Assign LLM to system roles" },
  { key: "infra.manage",     group: "Admin",     th: "ดู/ทดสอบการเชื่อมต่อ Storage/ระบบ", en: "View/test infrastructure connections" },
  { key: "plugins.manage",   group: "Admin",     th: "ติดตั้ง/เปิด-ปิด/ถอนปลั๊กอิน",      en: "Install / enable / uninstall plugins" },
];
/* effective catalog = kernel perms + perms contributed by every installed plugin (dynamic, §0). */
const PERMISSIONS = [...CORE_PERMISSIONS, ...PLUGIN_PERMISSIONS];
const PERM_KEYS = PERMISSIONS.map(p => p.key);

/* ---- roles (admin can add more; the 4 below are system roles) ---- */
const ROLES_SEED = [
  { key: "admin",   th: "ผู้ดูแลระบบ", en: "Admin",   desc: "เข้าถึงและจัดการได้ทุกอย่าง",            system: true,  color: "magic" },
  { key: "manager", th: "ผู้จัดการ",   en: "Manager", desc: "ดูและจัดการงานของสมาชิก แต่ไม่จัดการบัญชี", system: true,  color: "info" },
  { key: "member",  th: "สมาชิก",      en: "Member",  desc: "สร้างและจัดการของตัวเอง รันงานได้",        system: true,  color: "on" },
  { key: "viewer",  th: "ผู้อ่าน",     en: "Viewer",  desc: "ดูอย่างเดียว ไม่มีสิทธิ์แก้ไข",            system: true,  color: "idle" },
];

/* ---- default role → permission set ---- */
const ROLE_PERMS_SEED = {
  admin:   [...PERM_KEYS],
  manager: ["agent.create", "agent.edit.any", "agent.delete.any", "task.run", "knowledge.view", "knowledge.manage", "knowledge.delete", "workflow.manage", "user.view.any", "audit.view", "room.build", "room.place", "room.move", "room.reset", "room.create", "room.delete", "room.template", "options.manage", "character.manage", "rules.manage", "agent.config", "task.delete"],
  member:  ["agent.create", "task.run", "knowledge.view", "knowledge.manage", "knowledge.delete", "workflow.manage", "room.build", "room.place", "room.move"],
  viewer:  ["knowledge.view"],
};

/* ---- users (real accounts) ---- */
const USERS_SEED = [
  { id: "u_somchai", username: "somchai", display: "สมชาย วีรกุล",  email: "somchai@guildos.io", role: "admin",   status: "active",
    quota: 500000, period: "weekly",  used: 318400, avatar: "🧙", lastLogin: "เมื่อสักครู่", joined: "ม.ค. 2026" },
  { id: "u_nicha",   username: "nicha",   display: "ณิชา ทองดี",    email: "nicha@guildos.io",   role: "manager", status: "active",
    quota: 300000, period: "weekly",  used: 184200, avatar: "🦉", lastLogin: "12 นาที", joined: "ก.พ. 2026" },
  { id: "u_kitt",    username: "kitt",    display: "กิตติ ศรีสุข",   email: "kitt@guildos.io",    role: "member",  status: "active",
    quota: 100000, period: "weekly",  used: 91800,  avatar: "🛠️", lastLogin: "1 ชม.",   joined: "มี.ค. 2026" },
  { id: "u_ploy",    username: "ploy",    display: "พลอย จันทร์",    email: "ploy@guildos.io",    role: "member",  status: "active",
    quota: 100000, period: "weekly",  used: 42600,  avatar: "📜", lastLogin: "3 ชม.",   joined: "มี.ค. 2026" },
  { id: "u_anan",    username: "anan",    display: "อนันต์ พรหม",    email: "anan@guildos.io",    role: "viewer",  status: "active",
    quota: 20000,  period: "monthly", used: 5400,   avatar: "👁️", lastLogin: "เมื่อวาน", joined: "เม.ย. 2026" },
  { id: "u_dao",     username: "dao",     display: "ดาว ประเสริฐ",   email: "dao@guildos.io",     role: "member",  status: "suspended",
    quota: 100000, period: "weekly",  used: 99200,  avatar: "🌙", lastLogin: "5 วัน",   joined: "ก.พ. 2026" },
];

/* ---- per-user permission overrides (grant beyond role / deny below role) ---- */
const USER_PERMS_SEED = {
  u_kitt: { "audit.view": "grant" },   // a trusted member who can see the audit log
  u_ploy: { "task.run": "deny" },     // temporarily blocked from running quests
};

/* ---- which user owns which seeded agent (agents = a1..a6) ---- */
const AGENT_OWNER = { a1: "u_nicha", a2: "u_kitt", a3: "u_somchai", a4: "u_somchai", a5: "u_ploy", a6: "u_somchai" };
function ownerOf(agentId) { return AGENT_OWNER[agentId] || "u_somchai"; }

/* ---- audit log seed (most recent first) ---- */
const AUDIT_SEED = [
  { id: "ev9", actor: "u_somchai", action: "user.suspend",     targetType: "user", target: "u_dao",   meta: "เกินโควตาต่อเนื่อง",        time: "2 ชม." },
  { id: "ev8", actor: "u_somchai", action: "quota.update",     targetType: "user", target: "u_nicha", meta: "200K → 300K / สัปดาห์",     time: "5 ชม." },
  { id: "ev7", actor: "u_somchai", action: "permission.grant", targetType: "user", target: "u_kitt",  meta: "+ audit.view",              time: "เมื่อวาน" },
  { id: "ev6", actor: "u_somchai", action: "role.update",      targetType: "role", target: "manager", meta: "+ workflow.manage",         time: "เมื่อวาน" },
  { id: "ev5", actor: "u_nicha",   action: "user.create",      targetType: "user", target: "u_anan",  meta: "บทบาท viewer",              time: "2 วัน" },
  { id: "ev4", actor: "u_somchai", action: "permission.deny",  targetType: "user", target: "u_ploy",  meta: "− task.run",               time: "3 วัน" },
  { id: "ev3", actor: "u_somchai", action: "user.create",      targetType: "user", target: "u_ploy",  meta: "บทบาท member",              time: "4 วัน" },
  { id: "ev2", actor: "u_somchai", action: "role.update",      targetType: "role", target: "member",  meta: "− user.view.any",           time: "5 วัน" },
  { id: "ev1", actor: "u_somchai", action: "user.create",      targetType: "user", target: "u_kitt",  meta: "บทบาท member",              time: "6 วัน" },
];

const ACTION_META = {
  "user.create":      { icon: "➕", tone: "ok",   th: "สร้างสมาชิก",      en: "Created user" },
  "user.suspend":     { icon: "⛔", tone: "warn", th: "ระงับสมาชิก",      en: "Suspended user" },
  "user.update":      { icon: "✎",  tone: "info", th: "แก้ไขสมาชิก",      en: "Edited user" },
  "quota.update":     { icon: "🔵", tone: "info", th: "ปรับโควตา",        en: "Updated quota" },
  "role.update":      { icon: "🔑", tone: "info", th: "แก้บทบาท",         en: "Updated role" },
  "permission.grant": { icon: "✅", tone: "ok",   th: "ให้สิทธิ์",         en: "Granted permission" },
  "permission.deny":  { icon: "🚫", tone: "warn", th: "ถอนสิทธิ์",         en: "Denied permission" },
  "workflow.toggle":  { icon: "⚗️", tone: "info", th: "สลับเวิร์กโฟลว์",    en: "Toggled workflow" },
};

/* ---- persistence ---- */
const U_KEYS = { users: "guildos-users-v2", rolePerms: "guildos-roleperms-v2", userPerms: "guildos-userperms-v2", roles: "guildos-roles-v2", audit: "guildos-audit-v2" };
function loadU(key, fallback) {
  try { const raw = localStorage.getItem(U_KEYS[key]); return raw === null ? fallback : JSON.parse(raw); }
  catch { return fallback; }
}
function saveU(key, val) { try { localStorage.setItem(U_KEYS[key], JSON.stringify(val)); } catch {} }

/* ---- permission resolver: role perms + grants − denies (deny wins) ---- */
function resolvePerms(roleKey, rolePermsMap, userOverride) {
  if (roleKey === "admin") return new Set(PERM_KEYS); // admin always has every permission
  const set = new Set(rolePermsMap[roleKey] || []);
  const ov = userOverride || {};
  for (const k of Object.keys(ov)) {
    if (ov[k] === "grant") set.add(k);
    else if (ov[k] === "deny") set.delete(k);
  }
  return set;
}

/* ---- token helpers ---- */
const fmtTok = (n) => n == null ? "∞" : n >= 1000 ? (n / 1000).toFixed(n >= 10000 ? 0 : 1) + "K" : String(n);
function usagePct(u) { return u.quota ? Math.min(100, Math.round(u.used / u.quota * 100)) : 0; }
function userById(users, id) { return users.find(u => u.id === id); }
function roleByKey(roles, key) { return roles.find(r => r.key === key) || { key, th: key, en: key, color: "" }; }

Object.assign(window, {
  PERMISSIONS, PERM_KEYS, ROLES_SEED, ROLE_PERMS_SEED, USERS_SEED, USER_PERMS_SEED, AUDIT_SEED,
  ACTION_META, AGENT_OWNER, ownerOf, loadU, saveU, resolvePerms, fmtTok, usagePct, userById, roleByKey,
});

export {
  ACTION_META,
  AGENT_OWNER,
  AUDIT_SEED,
  PERMISSIONS,
  PERM_KEYS,
  ROLES_SEED,
  ROLE_PERMS_SEED,
  USERS_SEED,
  USER_PERMS_SEED,
  U_KEYS,
  fmtTok,
  loadU,
  ownerOf,
  resolvePerms,
  roleByKey,
  saveU,
  usagePct,
  userById
};
