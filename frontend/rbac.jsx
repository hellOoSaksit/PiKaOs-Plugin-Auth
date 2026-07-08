/* PiKaOs — ES module (migrated from PiKaOs-Core/screens-rbac.jsx). */
import React from 'react';
const { useState } = React;
import { Btn, Empty, HelpNote, Meter, PageHead, Panel, StatTile } from '../../components/components.jsx';
import { Select } from '../../components/ui/Dropdown.jsx';
import DatePicker from '../../components/ui/DatePicker.jsx';
import SaveBar from '../../components/ui/SaveBar.jsx';
import { ACTION_META, PERMISSIONS, fmtTok, resolvePerms, roleByKey, usagePct, userById } from './data-users.jsx';
import { AVATAR_PRESETS } from './profile.jsx';
import { Admin, RoleBadge, StatusPill } from './admin.jsx';

/* ============================================================
   RBAC SCREENS — User detail, Roles & Permissions, Audit log,
   and the User form modal. All bilingual via Sys.T, data-no-lex.
   ============================================================ */

function Field({ label, hint, children }) {
  return (
    <div className="bf">
      <label className="bf-label">{label}{hint && <span className="bf-hint">{hint}</span>}</label>
      {children}
    </div>
  );
}

/* ---------------- USER FORM (create / edit) ---------------- */
function UserForm({ Sys, initial, onClose }) {
  const { roles, T } = Sys;
  const edit = !!(initial && initial.id);
  const [f, setF] = useState(() => ({
    display: "", username: "", email: "", role: "member", status: "active",
    quota: 100000, period: "weekly", avatar: "🙂",
    ...(initial || {}),
  }));
  const set = (k, v) => setF(p => ({ ...p, [k]: v }));
  const unlimited = f.quota == null;
  const canSave = f.display.trim() && f.username.trim();

  const submit = () => {
    if (!canSave) return;
    Sys.saveUser(f, edit);
    onClose();
  };

  return (
    <div className="drawer-overlay" data-no-lex onClick={onClose} style={{ justifyContent: "center", alignItems: "center", padding: 24 }}>
      <div className="userform ornate" onClick={e => e.stopPropagation()}>
        <div className="builder-head">
          <span className="ph-icon" style={{ fontSize: 18 }}>{edit ? "✎" : "➕"}</span>
          <div>
            <div className="kicker">{edit ? T("Edit user", "แก้ไขสมาชิก") : T("New user", "เพิ่มสมาชิก")}</div>
            <h2 style={{ fontFamily: "var(--font-head)", fontSize: 19, margin: "2px 0 0", color: "var(--ink)" }}>
              {edit ? f.display || T("User", "สมาชิก") : T("Create an account", "สร้างบัญชีใหม่")}
            </h2>
          </div>
          <button className="drawer-close" onClick={onClose} style={{ marginLeft: "auto" }}>✕</button>
        </div>

        <div className="userform-body">
          <Field label={T("Avatar", "รูปแทนตัว")}>
            <div className="avatar-pick">
              {AVATAR_PRESETS.map(a => (
                <button key={a} type="button" className={`avatar-opt ${f.avatar === a ? "on" : ""}`} onClick={() => set("avatar", a)}>{a}</button>
              ))}
            </div>
          </Field>
          <div className="grid cols-2" style={{ gap: 12 }}>
            <Field label={T("Display name", "ชื่อที่แสดง")}>
              <input className="bf-input" value={f.display} onChange={e => set("display", e.target.value)} placeholder={T("e.g. Nicha Thongdee", "เช่น ณิชา ทองดี")} />
            </Field>
            <Field label={T("Username", "ชื่อผู้ใช้")}>
              <input className="bf-input" value={f.username} onChange={e => set("username", e.target.value.replace(/\s/g, ""))} placeholder="nicha" />
            </Field>
          </div>
          <Field label={T("Email", "อีเมล")}>
            <input className="bf-input" value={f.email} onChange={e => set("email", e.target.value)} placeholder="name@guildos.io" />
          </Field>
          <div className="grid cols-2" style={{ gap: 12 }}>
            <Field label={T("Role", "บทบาท")}>
              <Select block value={f.role} onChange={v => set("role", v)}
                options={roles.map(r => ({ value: r.key, label: T(r.en, r.th) }))} />
            </Field>
            <Field label={T("Status", "สถานะ")}>
              <Select block value={f.status} onChange={v => set("status", v)}
                options={[{ value: "active", label: T("Active", "ใช้งาน") }, { value: "suspended", label: T("Suspended", "ระงับ") }]} />
            </Field>
          </div>
          <Field label={T("Token quota", "โควตาโทเคน")} hint={T("per reset period", "ต่อรอบ")}>
            <div className="row" style={{ gap: 10 }}>
              <label className="ck-inline" data-no-lex>
                <input type="checkbox" checked={unlimited} onChange={e => set("quota", e.target.checked ? null : 100000)} />
                {T("Unlimited", "ไม่จำกัด")}
              </label>
              {!unlimited && (
                <>
                  <input className="bf-input" type="number" style={{ width: 130 }} value={f.quota} onChange={e => set("quota", Math.max(0, +e.target.value))} />
                  <Select value={f.period} minWidth={120} onChange={v => set("period", v)}
                    options={[{ value: "daily", label: T("daily", "รายวัน") }, { value: "weekly", label: T("weekly", "รายสัปดาห์") }, { value: "monthly", label: T("monthly", "รายเดือน") }]} />
                </>
              )}
            </div>
          </Field>
        </div>

        <div className="userform-foot">
          <Btn kind="ghost" onClick={onClose}>{T("Cancel", "ยกเลิก")}</Btn>
          <Btn kind="gold" onClick={submit} style={{ opacity: canSave ? 1 : .5, pointerEvents: canSave ? "auto" : "none" }}>
            {edit ? T("Save changes", "บันทึก") : T("Create user", "สร้างสมาชิก")}
          </Btn>
        </div>
      </div>
    </div>
  );
}

/* ---------------- USER DETAIL (admin view of one member) ---------------- */
function UserDetail({ Sys, userId }) {
  const { users, roles, can, T } = Sys;
  const u = userById(users, userId);
  if (!u) return <div className="content-pad" data-no-lex><Empty icon="👤" title={T("User not found", "ไม่พบสมาชิก")} /></div>;

  const role = roleByKey(roles, u.role);
  const override = (Sys.userPerms[u.id]) || {};
  const effective = resolvePerms(u.role, Sys.rolePerms, override);
  const manageUsers = can("user.manage");
  const manageRoles = can("role.manage");
  const manageTokens = can("token.manage");
  const pct = usagePct(u);

  const LEDGER = [
    { t: T("Quest run · auth-service", "รันงาน · auth-service"), tok: 4200, when: T("2h ago", "2 ชม.") },
    { t: T("Codex embed · 6 docs", "ฝังคลังความรู้ · 6 เอกสาร"), tok: 1850, when: T("5h ago", "5 ชม.") },
    { t: T("Recall query", "ค้นความรู้"), tok: 640, when: T("yesterday", "เมื่อวาน") },
  ];

  return (
    <div className="content-pad fade-in" data-no-lex>
      <button className="back-link" onClick={() => Sys.go("admin")}>← {T("Back to users", "กลับไปรายชื่อสมาชิก")}</button>

      <div className="udetail-head">
        <span className="udetail-avatar">{u.avatar}</span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="row" style={{ gap: 10, alignItems: "center" }}>
            <h1 style={{ fontFamily: "var(--font-head)", fontSize: 24, margin: 0, color: "var(--ink)" }}>{u.display}</h1>
            <RoleBadge roleKey={u.role} roles={roles} T={T} />
            <StatusPill status={u.status} T={T} />
          </div>
          <div className="mono faint" style={{ fontSize: 12, marginTop: 4 }}>@{u.username} · {u.email} · {T("joined", "เข้าร่วม")} {u.joined}</div>
        </div>
        {manageUsers && (
          <div className="row" style={{ gap: 8 }}>
            <Btn kind="ghost" sm icon="✎" onClick={() => Sys.openUserForm(u)}>{T("Edit", "แก้ไข")}</Btn>
            {u.id !== Sys.me.id && (
              <Btn kind="ghost" sm onClick={() => Sys.toggleSuspend(u)}>{u.status === "active" ? T("Suspend", "ระงับ") : T("Restore", "คืนสถานะ")}</Btn>
            )}
          </div>
        )}
      </div>

      <div className="grid cols-4 stagger" style={{ margin: "18px 0" }}>
        <StatTile label={T("Tokens used", "โทเคนที่ใช้")} value={fmtTok(u.used)} unit="token" delta={u.quota ? `${pct}% ${T("of quota", "ของโควตา")}` : T("unlimited", "ไม่จำกัด")} deltaTone={pct >= 90 ? "down" : "up"} icon="🔵" />
        <StatTile label={T("Quota", "โควตา")} value={u.quota == null ? "∞" : fmtTok(u.quota)} unit={u.quota == null ? "" : "token"} delta={T(u.period, u.period)} icon="📊" />
        <StatTile label={T("Last seen", "ใช้งานล่าสุด")} value={u.lastLogin} icon="🕑" />
      </div>

      <div className="grid" style={{ gridTemplateColumns: "1fr 320px", gap: 16, alignItems: "start" }}>
        <div className="col" style={{ gap: 16 }}>
          <Panel title={T("Recent token usage", "การใช้โทเคนล่าสุด")} en="LEDGER" icon="🔵" bodyPad={false}>
            <div style={{ padding: 6 }}>
              {LEDGER.map((l, i) => (
                <div key={i} className="row" style={{ gap: 12, padding: "11px 12px", borderBottom: i < LEDGER.length - 1 ? "1px solid var(--line-soft)" : "none" }}>
                  <span style={{ flex: 1, fontSize: 13, color: "var(--ink)" }}>{l.t}</span>
                  <span className="mono" style={{ fontSize: 12.5, color: "var(--sapphire)" }}>−{fmtTok(l.tok)}</span>
                  <span className="mono faint" style={{ fontSize: 11, width: 64, textAlign: "right" }}>{l.when}</span>
                </div>
              ))}
            </div>
          </Panel>
        </div>

        <div className="col" style={{ gap: 16 }}>
          {manageTokens && u.quota != null && (
            <Panel title={T("Quota usage", "การใช้โควตา")} en="QUOTA" icon="📊">
              <div className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
                <span className="muted" style={{ fontSize: 13 }}>{fmtTok(u.used)} / {fmtTok(u.quota)}</span>
                <span className={`mono ${pct >= 90 ? "" : "gold-text"}`} style={{ fontSize: 13, color: pct >= 90 ? "var(--crimson)" : undefined }}>{pct}%</span>
              </div>
              <Meter kind="mana" val={pct} />
              <div className="row" style={{ gap: 8, marginTop: 12, flexWrap: "wrap" }}>
                {[50000, 100000, 300000, null].map(qn => (
                  <button key={String(qn)} className={`quota-chip ${u.quota === qn ? "on" : ""}`} onClick={() => Sys.setQuota(u, qn)}>
                    {qn == null ? T("Unlimited", "ไม่จำกัด") : fmtTok(qn)}
                  </button>
                ))}
                <button className="quota-chip reset" onClick={() => Sys.resetUsage(u)}>↺ {T("Reset usage", "รีเซ็ตการใช้")}</button>
              </div>
            </Panel>
          )}

          <Panel title={T("Role", "บทบาท")} en="ROLE" icon="🔑">
            {manageRoles ? (
              <Select block value={u.role} disabled={u.id === Sys.me.id} onChange={v => Sys.setRole(u, v)}
                options={roles.map(r => ({ value: r.key, label: T(r.en, r.th) }))} />
            ) : <RoleBadge roleKey={u.role} roles={roles} T={T} />}
            <div className="muted" style={{ fontSize: 12, marginTop: 8, lineHeight: 1.5 }}>{T(role.en, role.th)} — {T(role.descEn || role.desc, role.desc)}</div>
            {u.id === Sys.me.id && <div className="perm-hint mono" style={{ marginTop: 8 }}>{T("you can't change your own role", "เปลี่ยนบทบาทตัวเองไม่ได้")}</div>}
          </Panel>

          <Panel title={T("Permission overrides", "สิทธิ์เฉพาะราย")} en="OVERRIDES" icon="⚙️">
            <div className="muted" style={{ fontSize: 11.5, marginBottom: 10, lineHeight: 1.5 }}>
              {T("Final = role permissions + grants − denies (deny wins).", "สิทธิ์สุดท้าย = ของบทบาท + grant − deny (deny ชนะ)")}
            </div>
            <div className="col" style={{ gap: 6 }}>
              {PERMISSIONS.map(p => {
                const fromRole = (Sys.rolePerms[u.role] || []).includes(p.key);
                const ov = override[p.key]; // grant | deny | undefined
                const has = effective.has(p.key);
                const cycle = () => {
                  if (!manageRoles) return;
                  const next = ov === "grant" ? "deny" : ov === "deny" ? null : (fromRole ? "deny" : "grant");
                  Sys.setUserPerm(u, p.key, next);
                };
                return (
                  <div key={p.key} className={`perm-row ${manageRoles ? "editable" : ""}`} onClick={cycle}>
                    <span className={`perm-state ${has ? "on" : "off"}`}>{has ? "✓" : "✕"}</span>
                    <span className="perm-name">{T(p.en, p.th)}</span>
                    {ov && <span className={`perm-tag ${ov}`}>{ov === "grant" ? "+grant" : "−deny"}</span>}
                  </div>
                );
              })}
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}

/* ---------------- ROLES & PERMISSIONS (matrix) ---------------- */
function RolesPermissions({ Sys }) {
  const { roles, can, T } = Sys;
  const editable = can("role.manage");
  const groups = [...new Set(PERMISSIONS.map(p => p.group))];

  // batched edits: stage toggles in a draft, commit on Save
  const base = Sys.rolePerms;
  const [draft, setDraft] = useState(null);   // null = in sync with Sys
  const cur = draft || base;
  const toggle = (rk, pk, on) => setDraft(d => {
    const src = d || base; const set = new Set(src[rk] || []);
    if (on) set.add(pk); else set.delete(pk);
    return { ...src, [rk]: [...set] };
  });
  const diffKeys = (rk) => {
    const a = new Set(base[rk] || []), b = new Set((draft || base)[rk] || []);
    return [...new Set([...a, ...b])].filter(k => a.has(k) !== b.has(k));
  };
  const changes = draft ? roles.reduce((n, r) => r.key === "admin" ? n : n + diffKeys(r.key).length, 0) : 0;
  const saveAll = () => {
    if (!draft) return;
    roles.forEach(r => { if (r.key === "admin") return; diffKeys(r.key).forEach(k => Sys.setRolePerm(r.key, k, (draft[r.key] || []).includes(k))); });
    setDraft(null);
  };
  const cancelAll = () => setDraft(null);

  return (
    <div className="content-pad fade-in" data-no-lex>
      <PageHead kicker={T("Administration · Access", "ผู้ดูแลระบบ · สิทธิ์")} title={T("Roles & Permissions", "บทบาทและสิทธิ์")} tag="local"
        desc={T("Each role is a preset bundle of permissions. Toggle cells to change what a role can do, then Save your changes.",
                "แต่ละบทบาทคือชุดสิทธิ์สำเร็จรูป · กดที่ช่องเพื่อปรับว่าบทบาทนั้นทำอะไรได้ แล้วกดบันทึก")}
        actions={editable ? <Btn kind="gold" sm icon="➕" onClick={() => Sys.addRole()}>{T("New role", "เพิ่มบทบาท")}</Btn> : <span className="perm-hint mono">{T("view only", "ดูอย่างเดียว")}</span>} />

      <HelpNote tag="local">{T("Admin always has every permission (locked). System roles can be tuned but not deleted.",
        "ผู้ดูแลระบบมีทุกสิทธิ์เสมอ (ล็อกไว้) · บทบาทระบบปรับได้แต่ลบไม่ได้")}</HelpNote>

      <Panel bodyPad={false} className="rbac-panel">
        <div className="rbac-scroll">
          <table className="rbac-matrix">
            <thead>
              <tr>
                <th className="rbac-permcol">{T("Permission", "สิทธิ์")}</th>
                {roles.map(r => (
                  <th key={r.key} className="rbac-rolecol">
                    <RoleBadge roleKey={r.key} roles={roles} T={T} />
                    <span className="rbac-rolecount mono faint">{Sys.users.filter(u => u.role === r.key).length} {T("users", "คน")}</span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {groups.map(g => (
                <React.Fragment key={g}>
                  <tr className="rbac-grouprow"><td colSpan={roles.length + 1}>{g}</td></tr>
                  {PERMISSIONS.filter(p => p.group === g).map(p => (
                    <tr key={p.key}>
                      <td className="rbac-permcol">
                        <div className="rbac-permname">{T(p.en, p.th)}</div>
                        <div className="mono faint" style={{ fontSize: 10 }}>{p.key}</div>
                      </td>
                      {roles.map(r => {
                        const locked = r.key === "admin"; // admin = all, locked
                        const on = locked ? true : (cur[r.key] || []).includes(p.key);
                        const changed = !locked && draft && (new Set(base[r.key] || []).has(p.key) !== on);
                        return (
                          <td key={r.key} className="rbac-cell">
                            <button className={`rbac-toggle ${on ? "on" : ""} ${locked || !editable ? "locked" : ""} ${changed ? "changed" : ""}`}
                              onClick={() => editable && !locked && toggle(r.key, p.key, !on)}
                              title={locked ? T("admin always has all", "admin มีทุกสิทธิ์เสมอ") : ""}>
                              {on ? "✓" : ""}
                            </button>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <SaveBar count={changes} onSave={saveAll} onCancel={cancelAll}
        saveLabel={T("Save changes", "บันทึก")} cancelLabel={T("Cancel", "ยกเลิก")}
        label={T(changes + " unsaved change" + (changes === 1 ? "" : "s"), "แก้ไข " + changes + " รายการ ยังไม่บันทึก")} />
    </div>
  );
}

/* ---------------- AUDIT LOG ---------------- */
function AuditLog({ Sys }) {
  const { audit, users, roles, T } = Sys;
  const [filter, setFilter] = useState("all");
  const [q, setQ] = useState("");
  const [date, setDate] = useState(null);   // วันที่เลือกจาก DatePicker (null = ทุกวัน)
  const name = (id, type) => type === "role"
    ? (() => { const r = roleByKey(roles, id); return T(r.en, r.th); })()
    : (userById(users, id) || { display: id }).display;

  // relative time strings → a real Date (now − parsed offset) so the DatePicker can match a day
  const deriveDate = (s) => {
    s = String(s || ""); const now = new Date();
    if (/เมื่อวาน|yesterday/i.test(s)) { const d = new Date(now); d.setDate(d.getDate() - 1); return d; }
    const dm = s.match(/(\d+)\s*(?:วัน|day)/i);
    if (dm) { const d = new Date(now); d.setDate(d.getDate() - (+dm[1])); return d; }
    return now;   // นาที/ชม./เมื่อสักครู่ = วันนี้
  };
  const sameDay = (a, b) => a && b && a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();

  const ACTION_PILL = {
    user: ["User", "สมาชิก"], quota: ["Quota", "โควตา"], role: ["Role", "บทบาท"],
    permission: ["Permission", "สิทธิ์"], workflow: ["Workflow", "เวิร์กโฟลว์"],
  };
  const actionTypes = ["all", "user", "quota", "role", "permission", "workflow"];

  const query = q.trim().toLowerCase();
  const list = audit.filter(e => {
    if (filter !== "all" && !e.action.startsWith(filter)) return false;
    if (date && !sameDay(deriveDate(e.time), date)) return false;
    if (query) {
      const m = ACTION_META[e.action] || { th: e.action, en: e.action };
      const hay = [name(e.actor, "user"), name(e.target, e.targetType), e.meta, T(m.en, m.th), e.action, e.time]
        .join(" ").toLowerCase();
      if (!hay.includes(query)) return false;
    }
    return true;
  });
  const hasFilter = filter !== "all" || !!date || !!query;

  return (
    <div className="content-pad fade-in" data-no-lex>
      <PageHead kicker={T("Administration · Audit", "ผู้ดูแลระบบ · ตรวจสอบ")} title={T("Audit Log", "บันทึกการตรวจสอบ")} tag="local"
        desc={T("Every change to users, roles, quota and permissions — who did what, and when.",
                "ทุกการเปลี่ยนแปลงเรื่องสมาชิก บทบาท โควตา และสิทธิ์ — ใครทำอะไรเมื่อไหร่")} />

      <div className="audit-filters">
        <div className="audit-search">
          <span className="as-ic">🔍</span>
          <input value={q} onChange={e => setQ(e.target.value)}
            placeholder={T("Search actor, target, detail…", "ค้นหาผู้ทำ · เป้าหมาย · รายละเอียด…")} />
          {q && <button className="as-clear" title={T("Clear", "ล้าง")} onClick={() => setQ("")}>✕</button>}
        </div>
        <DatePicker value={date} onChange={setDate} />
        {date && <button className="audit-date-clear" title={T("All dates", "ทุกวัน")} onClick={() => setDate(null)}>✕</button>}
      </div>

      <div className="audit-pills">
        {actionTypes.map(a => (
          <button key={a} className={`tab-pill ${filter === a ? "on" : ""}`} onClick={() => setFilter(a)}>
            {a === "all" ? T("All", "ทั้งหมด") : T(ACTION_PILL[a][0], ACTION_PILL[a][1])}
          </button>
        ))}
        <span className="audit-count mono">{list.length} {T("entries", "รายการ")}</span>
        {hasFilter && <button className="audit-clear-all" onClick={() => { setFilter("all"); setDate(null); setQ(""); }}>{T("Clear filters", "ล้างตัวกรอง")}</button>}
      </div>

      <Panel bodyPad={false}>
        <div style={{ padding: 6 }}>
          {list.length === 0 ? <Empty icon="📋" title={T("No matching entries", "ไม่มีรายการที่ตรง")} sub={hasFilter ? T("Try clearing the filters", "ลองล้างตัวกรอง") : null} /> :
            list.map(e => {
              const m = ACTION_META[e.action] || { icon: "•", tone: "info", th: e.action, en: e.action };
              return (
                <div key={e.id} className="audit-row">
                  <span className={`audit-ic`} data-tone={m.tone}>{m.icon}</span>
                  <div className="audit-body">
                    <div className="audit-line">
                      <span className="audit-actor">{name(e.actor, "user")}</span>
                      <span className="muted"> {T(m.en, m.th).toLowerCase()} </span>
                      <span className="audit-target">{name(e.target, e.targetType)}</span>
                    </div>
                    <div className="mono faint" style={{ fontSize: 11 }}>{e.meta}</div>
                  </div>
                  <span className="mono faint audit-time">{e.time}</span>
                </div>
              );
            })}
        </div>
      </Panel>
    </div>
  );
}

/* ---------------- PERMISSIONS CATALOG (read-only) ----------------
   A reference view of every permission in the system, grouped by area, showing which roles
   currently hold each. Read-only on purpose — assignments are edited in RolesPermissions; this
   page is gated wider (user.view.any) so managers can see what exists without edit rights. */
function PermissionsCatalog({ Sys }) {
  const { roles, rolePerms, T } = Sys;
  const groups = [...new Set(PERMISSIONS.map(p => p.group))];
  // admin implicitly holds every permission, so it always counts as holding one
  const rolesWith = (pk) => roles.filter(r => r.key === "admin" || (rolePerms[r.key] || []).includes(pk));

  return (
    <div className="content-pad fade-in" data-no-lex>
      <PageHead kicker={T("Administration · Access", "ผู้ดูแลระบบ · สิทธิ์")}
        title={T("Permissions catalog", "แคตตาล็อกสิทธิ์")} tag="local"
        desc={T("Every permission in the system, grouped by area, with the roles that hold each. Read-only — change who gets what in Roles & Permissions.",
                "สิทธิ์ทั้งหมดในระบบ จัดกลุ่มตามส่วนงาน พร้อมบทบาทที่ถืออยู่ · อ่านอย่างเดียว — แก้การมอบสิทธิ์ได้ที่หน้าบทบาทและสิทธิ์")} />

      <HelpNote tag="local">{T("Admin implicitly holds every permission. A permission with only the Admin badge is not yet granted to any other role.",
        "ผู้ดูแลระบบมีทุกสิทธิ์โดยปริยาย · สิทธิ์ที่มีเฉพาะป้าย Admin แปลว่ายังไม่มี role อื่นได้รับ")}</HelpNote>

      {groups.map(g => {
        const perms = PERMISSIONS.filter(p => p.group === g);
        return (
          <Panel key={g} className="permcat-block">
            <div className="navmgr-grouphead">{g} <span className="mono faint">· {perms.length}</span></div>
            {perms.map(p => (
              <div key={p.key} className="tool-row">
                <div className="tool-bd">
                  <div className="tool-name">{T(p.en, p.th)}</div>
                  <div className="tool-meta mono faint">{p.key}</div>
                </div>
                <div className="navmgr-badges">
                  {rolesWith(p.key).map(r => <RoleBadge key={r.key} roleKey={r.key} roles={roles} T={T} />)}
                </div>
              </div>
            ))}
          </Panel>
        );
      })}
    </div>
  );
}

Object.assign(window, { UserForm, UserDetail, RolesPermissions, AuditLog, PermissionsCatalog });

export {
  AuditLog,
  PermissionsCatalog,
  RolesPermissions,
  UserDetail,
  UserForm
};
