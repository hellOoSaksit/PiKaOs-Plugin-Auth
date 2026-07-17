/* The first-admin window is this plugin's screen, so its strings and its claim on the bootstrap stage
   ship with the plugin — a kernel-only Core carries neither. Mirrors the i18n-key test Core keeps for
   its own packs (data/i18n/i18n-window.test.js), which is where these keys used to live. */
import { it, expect } from 'vitest';
import en from './i18n/en-formal.json';
import th from './i18n/th-formal.json';
import ja from './i18n/ja-formal.json';

const PACKS = [['en', en], ['th', th], ['ja', ja]];

// Every key FirstAdmin.jsx passes to t(). A missing one renders the raw key at the operator.
const KEYS = ['firstadmin.kicker', 'firstadmin.title', 'firstadmin.subtitle', 'firstadmin.code',
  'firstadmin.codePh', 'firstadmin.username', 'firstadmin.password', 'firstadmin.confirm',
  'firstadmin.submit', 'firstadmin.submitting', 'firstadmin.errEmpty', 'firstadmin.errMismatch',
  'firstadmin.errUsername', 'firstadmin.errCode', 'firstadmin.errWeak', 'firstadmin.errClosed',
  'firstadmin.errNetwork', 'firstadmin.ok'];

it('every pack defines the first-admin screen labels', () => {
  for (const [name, pack] of PACKS)
    for (const k of KEYS) expect(pack.translations[k], `${name} missing ${k}`).toBeTruthy();
});

it('every pack declares the plugin-pack shape i18n.jsx merges on (translations-only)', () => {
  for (const [name, pack] of PACKS) {
    expect(pack.lexiconCode, `${name} lexiconCode`).toBe('formal');
    expect(pack.languageCode, `${name} languageCode`).toBe(name);
  }
});
