/* Auth plugin — create-first-admin screen (auth enabled, zero users — 2026-07-14 spec).
   Shown when /api/setup/status reports needsFirstAdmin: this plugin booted ownerless and revived a
   console setup code. The operator proves console access (code) and hand-picks the owner account.
   On success the parent logs in through the NORMAL login flow (onDone → useAuth().login) — this
   screen never touches tokens. All copy via t(key) (firstadmin.* ×3 packs, shipped in ./i18n).

   Lives HERE, not in Core: creating the first owner is meaningless without an identity provider, so a
   kernel-only build must not carry the screen (zero-core). Core keeps only the generic seam — it
   decides WHEN the 'first-admin' stage is active (shell-mode.js, off /api/setup/status), this plugin
   supplies WHAT renders, exactly like postgres owns 'db-choice'. */
import React from 'react';
const { useState } = React;
import * as api from '../../lib/api.js';
import { DisconnectButton } from '../../components/ui/DisconnectButton.jsx';

export function FirstAdmin({ t, language, onLang, onDone }) {
  const [form, setForm] = useState({ setupCode: '', username: '', password: '', confirmPassword: '' });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [ok, setOk] = useState(false);

  const set = (k) => (e) => { setForm((f) => ({ ...f, [k]: e.target.value })); setError(''); };

  const submit = async (e) => {
    e.preventDefault();
    if (busy || ok) return;
    const { setupCode, username, password, confirmPassword } = form;
    if (!setupCode.trim() || !username.trim() || !password || !confirmPassword) { setError(t('firstadmin.errEmpty')); return; }
    if (password !== confirmPassword) { setError(t('firstadmin.errMismatch')); return; }
    if (!/^[a-zA-Z0-9_.-]{3,64}$/.test(username.trim())) { setError(t('firstadmin.errUsername')); return; }
    setBusy(true);
    try {
      await api.bootstrapAdmin({ setupCode: setupCode.trim(), username: username.trim(), password, confirmPassword });
      setOk(true);
      await onDone(username.trim(), password);   // normal login path — resolveShellMode flips to 'full'
    } catch (err) {
      if (err.status === 401) setError(t('firstadmin.errCode'));
      else if (err.status === 409) setError(t('firstadmin.errClosed'));
      else if (err.status === 422) setError(t('firstadmin.errWeak'));
      else if (err.status === 0) setError(t('firstadmin.errNetwork'));
      else setError(t('firstadmin.errNetwork'));
      setOk(false);
    } finally {
      setBusy(false);
    }
  };

  const field = (key, label, type, extra = {}) => (
    <div style={{ marginBottom: 14 }}>
      <label htmlFor={`fa-${key}`} style={{ display: 'block', fontFamily: 'var(--font-head)', fontWeight: 600, fontSize: 13, color: 'var(--ink-2)', marginBottom: 6 }}>{label}</label>
      <input id={`fa-${key}`} className="auth-input" type={type} value={form[key]} onChange={set(key)}
        disabled={busy || ok} autoComplete="off" spellCheck={false} {...extra} />
    </div>
  );

  return (
    <div className="auth-screen">
      {onLang && (
        <div className="auth-lang" role="group" aria-label="language">
          <button type="button" className={language === 'en' ? 'on' : ''} onClick={() => onLang('en')}>EN</button>
          <button type="button" className={language === 'th' ? 'on' : ''} onClick={() => onLang('th')}>ไทย</button>
        </div>
      )}
      <div className="auth-hero">
        <div style={{ display: 'flex', gap: 10, position: 'relative', zIndex: 2 }}>
          {['P', 'I', 'K', 'A'].map((ch, i) => (<span key={i} className="ltr" style={{ fontSize: 52 }}>{ch}</span>))}
        </div>
      </div>
      <div className="auth-formpane">
        <form onSubmit={submit} style={{ width: '100%', maxWidth: 384 }} noValidate>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7, fontFamily: 'var(--font-mono)', fontSize: 10.5, letterSpacing: '.2em', textTransform: 'uppercase', color: 'var(--ink-3)' }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--gold)' }} />{t('firstadmin.kicker')}
          </div>
          <h1 style={{ fontFamily: 'var(--font-head)', fontWeight: 700, fontSize: 29, margin: '14px 0 8px', color: 'var(--ink)' }}>{t('firstadmin.title')}</h1>
          <p style={{ margin: '0 0 22px', color: 'var(--ink-3)', fontSize: 14.5, lineHeight: 1.55 }}>{t('firstadmin.subtitle')}</p>

          {field('setupCode', t('firstadmin.code'), 'text', { placeholder: t('firstadmin.codePh'), autoCapitalize: 'characters', className: 'auth-input mono', autoFocus: true })}
          {field('username', t('firstadmin.username'), 'text')}
          {field('password', t('firstadmin.password'), 'password', { autoComplete: 'new-password' })}
          {field('confirmPassword', t('firstadmin.confirm'), 'password', { autoComplete: 'new-password' })}

          {error && (
            <div role="alert" style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 16, padding: '11px 14px', borderRadius: 'var(--radius-sm)', background: 'color-mix(in srgb, var(--crimson) 10%, transparent)', border: '1px solid color-mix(in srgb, var(--crimson) 35%, transparent)', color: 'var(--crimson-deep)', fontSize: 13.5 }}>
              <span style={{ fontWeight: 700 }}>!</span>{error}
            </div>
          )}
          {ok && (
            <div style={{ marginBottom: 16, padding: '11px 14px', borderRadius: 'var(--radius-sm)', background: 'color-mix(in srgb, var(--emerald) 10%, transparent)', border: '1px solid color-mix(in srgb, var(--emerald) 35%, transparent)', color: 'var(--emerald)', fontSize: 13.5 }}>
              {t('firstadmin.ok')}
            </div>
          )}

          <button type="submit" className="btn btn-gold" disabled={busy || ok} style={{ width: '100%', padding: 14, fontSize: 15.5 }}>
            {busy ? t('firstadmin.submitting') : t('firstadmin.submit')}
          </button>
          {!ok && (
            <div style={{ display: 'flex', justifyContent: 'center', marginTop: 18 }}>
              <DisconnectButton t={t} className="btn btn-ghost btn-sm" />
            </div>
          )}
        </form>
      </div>
    </div>
  );
}
