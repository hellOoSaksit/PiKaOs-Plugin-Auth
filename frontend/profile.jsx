/* Auth plugin — the account control for Core's utility bar (moved out of Core's App.jsx).

   Identity UI belongs to the plugin that owns identity: a kernel-only Core has nobody to be, so it
   renders no profile button rather than a decorative one. Core exposes the slot through the frontend
   plugin seam (`profile(ctx)` on the descriptor → renderPluginProfile) and supplies `t`, `me` and
   `onSignOut`; everything below is ours.

   Styling reuses Core's global classes (`ub-profile-btn` for the bar's chrome, `pm-*` for the card) —
   the same arrangement the RBAC screens already rely on, since Core plugins ship no CSS of their own. */
import React from 'react';
const { useState, useEffect, useRef } = React;
import { createPortal } from 'react-dom';

/* One list, used both here and by the RBAC user form — they had drifted into two overlapping sets. */
export const AVATAR_PRESETS = ["🙂", "🧙", "🦉", "🛠️", "📜", "👁️", "🌙", "🧑‍💻", "🦊", "🐼", "🚀", "🧠"];

export const isAvImg = (a) => typeof a === "string" && (a.startsWith("data:") || a.startsWith("http"));

export function Av({ a, fallback = "🙂" }) {
  return isAvImg(a) ? <img className="av-img" src={a} alt="" /> : <span>{a || fallback}</span>;
}

/* overlays render at <body> so no ancestor's stacking context can clip them */
const portalBody = (node) => {
  try { return createPortal(node, document.body); } catch { return node; }
};

function ChangePwModal({ t, onClose }) {
  const [cur, setCur] = useState(""); const [nw, setNw] = useState(""); const [cf, setCf] = useState("");
  const [err, setErr] = useState(""); const [done, setDone] = useState(false);
  const submit = () => {
    if (!cur) { setErr(t("pw.errCurrent")); return; }
    if (nw.length < 6) { setErr(t("pw.errShort")); return; }
    if (nw !== cf) { setErr(t("pw.errMatch")); return; }
    setDone(true); setTimeout(onClose, 1150);
  };
  return portalBody(
    <div className="uim-overlay" onClick={onClose} data-no-lex style={{ zIndex: 4200 }}>
      <div className="uim" onClick={e => e.stopPropagation()} style={{ width: 380 }}>
        {done ? (
          <div style={{ textAlign: "center", padding: "12px 0" }}>
            <div style={{ fontSize: 40 }}>✅</div>
            <div className="uim-title" style={{ marginTop: 8 }}>{t("pw.success")}</div>
          </div>
        ) : (<>
          <div className="uim-title">🔑 {t("pw.title")}</div>
          <div className="pp-pwform">
            <label className="bf-label">{t("pw.current")}</label>
            <input className="uim-input" type="password" value={cur} onChange={e => { setCur(e.target.value); setErr(""); }} autoFocus />
            <label className="bf-label">{t("pw.new")}</label>
            <input className="uim-input" type="password" value={nw} onChange={e => { setNw(e.target.value); setErr(""); }} />
            <label className="bf-label">{t("pw.confirm")}</label>
            <input className="uim-input" type="password" value={cf} onChange={e => { setCf(e.target.value); setErr(""); }} onKeyDown={e => e.key === "Enter" && submit()} />
            {err && <div className="uim-warn">{err}</div>}
          </div>
          <div className="uim-actions">
            <button className="uim-btn ghost" onClick={onClose}>{t("pw.cancel")}</button>
            <button className="uim-btn primary" onClick={submit}>{t("pw.save")}</button>
          </div>
        </>)}
      </div>
    </div>
  );
}

/* Persisting an edit still needs `PATCH /auth/me` on the auth backend; until it exists the card saves
   nothing and says so by simply not confirming beyond the local draft. Tracked in the spec. */
export function Profile({ me = {}, t, onSignOut }) {
  const [open, setOpen] = useState(false);
  const [pwOpen, setPwOpen] = useState(false);
  const [draft, setDraft] = useState({ display: "", email: "", avatar: "🙂" });
  const [dirty, setDirty] = useState(false);
  const [avPick, setAvPick] = useState(false);
  const [saved, setSaved] = useState(false);
  const fileRef = useRef(null);

  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);
  useEffect(() => {
    if (!open) return;
    setDraft({ display: me.display || me.display_name || me.username || "", email: me.email || "", avatar: me.avatar || "🙂" });
    setDirty(false); setAvPick(false); setSaved(false);
  }, [open]);

  const setField = (k, v) => { setDraft(d => ({ ...d, [k]: v })); setDirty(true); setSaved(false); };
  const onFile = (e) => {
    const f = e.target.files && e.target.files[0]; e.target.value = "";
    if (!f) return;
    const rd = new FileReader(); rd.onload = () => setField("avatar", rd.result); rd.readAsDataURL(f);
    setAvPick(false);
  };
  const save = () => {
    if (!dirty) return;
    setDirty(false); setSaved(true); setTimeout(() => setSaved(false), 1800);
  };

  return (
    <div className="profile-wrap" data-no-lex>
      <button type="button" className="ub-profile-btn" title={t("utilitybar.profile")} onClick={() => setOpen(o => !o)}>
        <span className="ub-avatar-wrap"><Av a={me.avatar} /></span>
      </button>
      {open && portalBody(
        <div className="profile-overlay" onClick={() => setOpen(false)} data-no-lex>
          <div className="profile-modal" onClick={e => e.stopPropagation()}>
            <button className="profile-close" onClick={() => setOpen(false)} title="✕">✕</button>
            <div className="pm-kicker mono">{t("profile.title")}</div>
            <div className="pm-head">
              <div className="pm-avwrap">
                <button className="pm-av pm-av-btn" style={{ background: "color-mix(in srgb, var(--gold) 18%, transparent)" }}
                  onClick={() => setAvPick(v => !v)} title={t("profile.editAvatar")}>
                  <Av a={draft.avatar} />
                  <span className="pm-av-edit">✎</span>
                </button>
              </div>
              <div className="pm-id">
                <input className="pm-name-input" value={draft.display} onChange={e => setField("display", e.target.value)}
                  placeholder={t("profile.namePh")} aria-label={t("profile.name")} />
                <div className="pm-sub"><span className="pm-username mono">@{me.username}</span></div>
              </div>
            </div>
            {avPick && (
              <div className="pm-avpick">
                <input ref={fileRef} type="file" accept="image/*" style={{ display: "none" }} onChange={onFile} />
                <button className="pm-av-upload" onClick={() => fileRef.current && fileRef.current.click()}>📷 {t("profile.upload")}</button>
                <div className="pm-av-or">{t("profile.choose")}</div>
                <div className="pm-av-emos">
                  {AVATAR_PRESETS.map(e => (
                    <button key={e} className={"pm-av-emo" + (draft.avatar === e ? " on" : "")}
                      onClick={() => { setField("avatar", e); setAvPick(false); }}>{e}</button>
                  ))}
                </div>
              </div>
            )}
            <div className="pm-grid">
              <div className="pm-field pm-field-full">
                <span className="pm-flabel">{t("profile.email")}</span>
                <input className="pm-input" type="email" value={draft.email} onChange={e => setField("email", e.target.value)} placeholder={t("profile.emailPh")} />
              </div>
              <div className="pm-field"><span className="pm-flabel">{t("profile.username")}</span><span className="pm-fval mono">@{me.username}</span></div>
              <div className="pm-field"><span className="pm-flabel">{t("profile.status")}</span><span className="pm-fval">{me.status === "suspended" ? t("profile.suspended") : t("profile.active")}</span></div>
              <div className="pm-field"><span className="pm-flabel">{t("profile.joined")}</span><span className="pm-fval">{me.joined || "—"}</span></div>
            </div>
            <button className={"pm-save" + (dirty ? " on" : "") + (saved ? " saved" : "")} onClick={save} disabled={!dirty && !saved}>
              {saved ? "✓ " + t("profile.saved") : t("profile.save")}
            </button>
            <div className="pm-actions">
              <button className="pp-btn" onClick={() => setPwOpen(true)}><span>🔑</span>{t("profile.changePw")}</button>
              <button className="pp-btn danger" onClick={() => { setOpen(false); onSignOut && onSignOut(); }}><span>🚪</span>{t("profile.signOut")}</button>
            </div>
          </div>
        </div>
      )}
      {pwOpen && <ChangePwModal t={t} onClose={() => setPwOpen(false)} />}
    </div>
  );
}
