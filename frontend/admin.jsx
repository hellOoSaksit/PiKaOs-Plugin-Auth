/* PiKaOs — ES module (migrated from PiKaOs-Core/screens-admin.jsx). */
import React from 'react';
const { useState } = React;
import { Btn, Empty, HelpNote, Meter, PageHead, Panel, StatTile } from '../../components/components.jsx';
import { Select } from '../../components/ui/Dropdown.jsx';
import { fmtTok, roleByKey, usagePct } from './data-users.jsx';

/* ============================================================
   ADMIN · USER MANAGEMENT — real user accounts (not agents).
   Table of users with role, status, token quota/usage. Actions
   gated by permissions (can). Phase-4 screen: bilingual via T(),
   container marked data-no-lex so the global lexicon leaves it.
   ============================================================ */

function RoleBadge({ roleKey, roles, T }) {
  const r = roleByKey(roles, roleKey);
  return <span className={`badge ${r.color}`} data-no-lex>{T(r.en, r.th)}</span>;
}

function StatusPill({ status, T }) {
  const on = status === "active";
  return <span className={`badge ${on ? "on" : "warn"}`} data-no-lex><span className="dot" />{on ? T("Active", "ใช้งาน") : T("Suspended", "ระงับ")}</span>;
}

function QuotaCell({ u, T }) {
  const pct = usagePct(u);
  const tone = u.quota == null ? "ok" : pct >= 90 ? "crit" : pct >= 70 ? "warn" : "ok";
  return (
    <span className="quota-cell" data-no-lex>
      <span className="quota-meter"><i className={`q-${tone}`} style={{ width: Math.max(3, pct) + "%" }} /></span>
      <span className="quota-num mono faint">{u.quota == null ? T("unlimited", "ไม่จำกัด") : `${fmtTok(u.used)} / ${fmtTok(u.quota)}`}</span>
    </span>
  );
}

function Admin({ Sys, onUser }) {
  const { users, roles, can, T } = Sys;
  const [q, setQ] = useState("");
  const [sortKey, setSortKey] = useState("used");
  const [roleFilter, setRoleFilter] = useState("all");

  const active = users.filter(u => u.status === "active").length;
  const totalUsed = users.reduce((s, u) => s + (u.used || 0), 0);
  const top = [...users].sort((a, b) => b.used - a.used)[0];

  const ql = q.trim().toLowerCase();
  const rows = users
    .filter(u => roleFilter === "all" || u.role === roleFilter)
    .filter(u => !ql || u.display.toLowerCase().includes(ql) || u.username.toLowerCase().includes(ql) || u.email.toLowerCase().includes(ql))
    .sort((a, b) => {
      if (sortKey === "used") return b.used - a.used;
      if (sortKey === "name") return a.display.localeCompare(b.display, "th");
      if (sortKey === "role") return a.role.localeCompare(b.role);
      if (sortKey === "status") return a.status.localeCompare(b.status);
      return 0;
    });

  const manage = can("user.manage");

  return (
    <div className="content-pad fade-in" data-no-lex>
      <PageHead kicker={T("Administration · Users", "ผู้ดูแลระบบ · สมาชิก")} title={T("User Management", "จัดการสมาชิก")} tag="local"
        desc={T("Manage real user accounts — roles, status, and token quota per person. Distinct from AI agents.",
                "จัดการบัญชีผู้ใช้จริง — บทบาท สถานะ และโควตาโทเคนรายคน (แยกจาก AI agent)")}
        actions={manage
          ? <Btn kind="gold" sm icon="➕" onClick={() => Sys.openUserForm()}>{T("New user", "เพิ่มสมาชิก")}</Btn>
          : <span className="perm-hint mono">{T("view only", "ดูอย่างเดียว")}</span>} />

      <HelpNote tag="local">{T("Edits (role, quota, suspend) are saved on your device. Token usage figures are demo estimates. Use the role switcher (top-right) to test what each role can do.",
        "การแก้ไข (บทบาท/โควตา/ระงับ) ถูกบันทึกในเครื่อง · ตัวเลขการใช้โทเคนเป็นค่าสาธิต · ใช้ตัวสลับบทบาทมุมขวาบนเพื่อทดสอบสิทธิ์ของแต่ละบทบาท")}</HelpNote>

      <div className="grid cols-4 stagger" style={{ margin: "16px 0 18px" }}>
        <StatTile label={T("Total users", "สมาชิกทั้งหมด")} value={users.length} unit={T("accounts", "บัญชี")} icon="👥" />
        <StatTile label={T("Active now", "ใช้งานอยู่")} value={`${active}/${users.length}`} delta={T("accounts enabled", "บัญชีที่เปิดใช้")} deltaTone="up" icon="🟢" />
        <StatTile label={T("Tokens used", "โทเคนที่ใช้รวม")} value={fmtTok(totalUsed)} unit="token" delta={T("this period", "รอบนี้")} icon="🔵" />
        <StatTile label={T("Top spender", "ใช้มากสุด")} value={top ? top.display.split(" ")[0] : "—"} delta={top ? fmtTok(top.used) + " token" : ""} deltaTone="down" icon="🏆" />
      </div>

      <div className="grid" style={{ gridTemplateColumns: "1fr 300px", gap: 16, alignItems: "start" }}>
        <Panel title={T("User directory", "รายชื่อสมาชิก")} en="DIRECTORY" icon="👥" bodyPad={false}
          right={<span className="mono faint" style={{ fontSize: 11 }}>{rows.length} {T("shown", "รายการ")}</span>}>
          <div style={{ padding: 14 }}>
            <div className="row" style={{ gap: 10, marginBottom: 12, flexWrap: "wrap" }}>
              <div className="search-bar" style={{ flex: 1, minWidth: 180, padding: "9px 13px" }}>
                <span>🔍</span><input value={q} onChange={e => setQ(e.target.value)} placeholder={T("Search name, username or email…", "ค้นชื่อ ชื่อผู้ใช้ หรืออีเมล…")} />
              </div>
              <Select value={roleFilter} minWidth={130} onChange={setRoleFilter}
                options={[{ value: "all", label: T("All roles", "ทุกบทบาท") },
                  ...roles.map(r => ({ value: r.key, label: T(r.en, r.th) }))]} />
              <Select value={sortKey} minWidth={140} onChange={setSortKey}
                options={[{ value: "used", label: T("Sort: most tokens", "เรียง: โทเคนมากสุด") },
                  { value: "name", label: T("Sort: name", "เรียง: ชื่อ") },
                  { value: "role", label: T("Sort: role", "เรียง: บทบาท") },
                  { value: "status", label: T("Sort: status", "เรียง: สถานะ") }]} />
            </div>

            {rows.length === 0 ? (
              <Empty icon="👥" title={T("No users found", "ไม่พบสมาชิก")} sub={T("Try a different search or filter", "ลองคำค้นหรือตัวกรองอื่น")} />
            ) : (
              <div className="utable">
                <div className="utable-th">
                  <span className="uc-user">{T("User", "สมาชิก")}</span>
                  <span className="uc-role">{T("Role", "บทบาท")}</span>
                  <span className="uc-status">{T("Status", "สถานะ")}</span>
                  <span className="uc-quota">{T("Token usage", "การใช้โทเคน")}</span>
                  <span className="uc-seen">{T("Last seen", "ใช้งานล่าสุด")}</span>
                  <span className="uc-act"></span>
                </div>
                {rows.map(u => (
                  <div key={u.id} className={`utable-tr ${u.status === "suspended" ? "is-suspended" : ""}`} onClick={() => onUser(u.id)}>
                    <span className="uc-user">
                      <span className="uavatar" data-no-lex>{u.avatar}</span>
                      <span style={{ minWidth: 0 }}>
                        <span className="uu-name">{u.display}</span>
                        <span className="uu-sub mono">@{u.username}</span>
                      </span>
                    </span>
                    <span className="uc-role"><RoleBadge roleKey={u.role} roles={roles} T={T} /></span>
                    <span className="uc-status"><StatusPill status={u.status} T={T} /></span>
                    <span className="uc-quota"><QuotaCell u={u} T={T} /></span>
                    <span className="uc-seen mono faint">{u.lastLogin}</span>
                    <span className="uc-act" onClick={e => e.stopPropagation()}>
                      <button className="admin-iconbtn" title={T("View", "ดู")} onClick={() => onUser(u.id)}>↗</button>
                      {manage && <button className="admin-iconbtn" title={T("Edit", "แก้ไข")} onClick={() => Sys.openUserForm(u)}>✎</button>}
                      {manage && u.id !== Sys.me.id && (
                        <button className="admin-iconbtn danger" title={u.status === "active" ? T("Suspend", "ระงับ") : T("Restore", "คืนสถานะ")}
                          onClick={() => Sys.toggleSuspend(u)}>{u.status === "active" ? "⛔" : "↺"}</button>
                      )}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </Panel>

        <div className="col" style={{ gap: 16 }}>
          <Panel title={T("Token usage by user", "การใช้โทเคนรายคน")} en="USAGE" icon="🔵">
            <div className="col" style={{ gap: 10 }}>
              {[...users].sort((a, b) => b.used - a.used).slice(0, 6).map(u => {
                const pct = totalUsed ? Math.round(u.used / totalUsed * 100) : 0;
                return (
                  <div key={u.id} className="stat-line">
                    <span className="sl-label" style={{ display: "flex", alignItems: "center", gap: 7, width: 110, flexBasis: 110 }}>
                      <span style={{ fontSize: 13 }} data-no-lex>{u.avatar}</span>
                      <span style={{ fontSize: 12, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{u.display.split(" ")[0]}</span>
                    </span>
                    <Meter kind="mana" val={pct} /><span className="sl-num">{fmtTok(u.used)}</span>
                  </div>
                );
              })}
            </div>
          </Panel>

          <Panel title={T("Roles", "บทบาท")} en="ROLES" icon="🔑"
            right={can("role.manage") ? <Btn kind="ghost" sm onClick={() => Sys.go("roles")}>{T("Manage →", "จัดการ →")}</Btn> : null}>
            <div className="col" style={{ gap: 9 }}>
              {roles.map(r => {
                const count = users.filter(u => u.role === r.key).length;
                return (
                  <div key={r.key} className="role-line">
                    <RoleBadge roleKey={r.key} roles={roles} T={T} />
                    <span className="muted" style={{ fontSize: 12, flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{T(r.en, r.th)}</span>
                    <span className="mono faint" style={{ fontSize: 11 }}>{count}</span>
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

Object.assign(window, { Admin, RoleBadge, StatusPill, QuotaCell });

export {
  Admin,
  QuotaCell,
  RoleBadge,
  StatusPill
};
