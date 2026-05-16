// netlify/functions/qf-auth.js
//
// Quran Foundation (QF) OAuth2 handler — pre-live.
//
// Endpoints (all hit at /api/qf-auth via netlify.toml redirect):
//   GET  /api/qf-auth?action=start              — kicks off the OAuth flow (PKCE + state cookie, 302 to QF)
//   GET  /api/qf-auth?code=...&state=...        — OAuth callback. Exchanges code, redirects to /reader.html with
//                                                  tokens + user info in the URL fragment.
//   POST /api/qf-auth?action=refresh            — body { refresh_token } → returns new tokens JSON.
//
// Required env vars in Netlify (already configured per user):
//   QF_CLIENT_ID
//   QF_CLIENT_SECRET
//   QF_OAUTH_BASE_URL   (e.g. https://prelive-oauth2.quran.foundation)
//   QF_REDIRECT_URI     (e.g. https://tryfahm.com/oauth/callback)  — must match what was registered with QF
//   QF_SCOPES           (default: "openid offline_access user collection activity_day streak")
//   APP_ORIGIN          (default: https://tryfahm.com)          — where to send the user after callback

const crypto = require('crypto');

const QF_CLIENT_ID     = process.env.QF_CLIENT_ID;
const QF_CLIENT_SECRET = process.env.QF_CLIENT_SECRET;
const QF_OAUTH_BASE    = process.env.QF_OAUTH_BASE_URL || 'https://prelive-oauth2.quran.foundation';
const QF_REDIRECT_URI  = process.env.QF_REDIRECT_URI  || 'https://tryfahm.com/oauth/callback';
const QF_SCOPES        = process.env.QF_SCOPES        || 'openid offline_access user collection activity_day streak';
const APP_ORIGIN       = process.env.APP_ORIGIN       || 'https://tryfahm.com';

const AUTHORIZE_URL = `${QF_OAUTH_BASE}/oauth2/auth`;
const TOKEN_URL     = `${QF_OAUTH_BASE}/oauth2/token`;
const USERINFO_URL  = `${QF_OAUTH_BASE}/oauth2/userinfo`;

function base64url(buf) {
  return Buffer.from(buf).toString('base64')
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function randomToken(bytes = 32) {
  return base64url(crypto.randomBytes(bytes));
}

function sha256(s) {
  return crypto.createHash('sha256').update(s).digest();
}

function buildCookie(name, value, maxAge) {
  // SameSite=None is required for OAuth state cookies: the callback arrives as a
  // cross-site redirect from QF's domain, and Lax cookies are silently dropped by
  // Chrome/Firefox in that context. PKCE + state verification keeps this safe.
  const parts = [`${name}=${value}`, 'Path=/', 'HttpOnly', 'Secure', 'SameSite=None'];
  if (maxAge !== undefined) parts.push(`Max-Age=${maxAge}`);
  return parts.join('; ');
}

function parseCookies(header) {
  const out = {};
  if (!header) return out;
  for (const part of header.split(';')) {
    const eq = part.indexOf('=');
    if (eq < 0) continue;
    out[part.slice(0, eq).trim()] = part.slice(eq + 1).trim();
  }
  return out;
}

function redirectToReader(fragmentParams, extraHeaders = {}) {
  const fragment = new URLSearchParams(fragmentParams).toString();
  return {
    statusCode: 302,
    headers: { Location: `${APP_ORIGIN}/reader.html#${fragment}`, ...extraHeaders },
    body: '',
  };
}

exports.handler = async (event) => {
  const qs = event.queryStringParameters || {};

  // QF sends ?code=...&state=... on success and ?error=...&state=... on failure.
  // Both are callback signals. Checking only `code` caused error responses (no code)
  // to fall through to 'start', creating an infinite redirect loop.
  const action = qs.action || (qs.code || qs.state || qs.error ? 'callback' : 'start');

  console.log('[qf-auth] path=%s method=%s action=%s qs=%s',
    event.path, event.httpMethod, action, JSON.stringify(qs));

  // ── START ──────────────────────────────────────────────────
  if (action === 'start') {
    if (!QF_CLIENT_ID) return { statusCode: 500, body: 'QF_CLIENT_ID not configured' };

    const state = randomToken(24);
    const verifier = randomToken(48);
    const challenge = base64url(sha256(verifier));

    const url = new URL(AUTHORIZE_URL);
    url.searchParams.set('client_id', QF_CLIENT_ID);
    url.searchParams.set('redirect_uri', QF_REDIRECT_URI);
    url.searchParams.set('response_type', 'code');
    url.searchParams.set('scope', QF_SCOPES);
    url.searchParams.set('state', state);
    url.searchParams.set('code_challenge', challenge);
    url.searchParams.set('code_challenge_method', 'S256');

    console.log('[qf-auth] start: redirecting to QF authorize, state_prefix=%s', state.slice(0, 12));
    return {
      statusCode: 302,
      headers: {
        Location: url.toString(),
        'Set-Cookie': buildCookie('qf_oauth', `${state}.${verifier}`, 600),
        // Prevent Netlify CDN from caching this response — a cached 302 strips
        // the Set-Cookie header, so the browser never stores the state cookie.
        'Cache-Control': 'no-store, no-cache',
      },
      body: '',
    };
  }

  // ── CALLBACK ───────────────────────────────────────────────
  if (action === 'callback') {
    const { code, state, error, error_description } = qs;

    if (error) {
      console.log('[qf-auth] callback: QF returned error=%s description=%s', error, error_description);
      return redirectToReader({ qf_error: error_description || error });
    }
    if (!code || !state) {
      console.log('[qf-auth] callback: missing code=%s state=%s — rejecting', code, state);
      return { statusCode: 400, body: 'Missing code or state' };
    }

    const rawCookieHeader = event.headers.cookie || event.headers.Cookie || '';
    const cookies = parseCookies(rawCookieHeader);
    const stored = cookies.qf_oauth;

    console.log('[qf-auth] callback: state_from_qf=%s cookie_header_present=%s qf_oauth_present=%s qf_oauth_prefix=%s',
      state,
      rawCookieHeader.length > 0,
      !!stored,
      stored ? stored.slice(0, 12) + '…' : 'none');

    if (!stored) {
      console.log('[qf-auth] callback: no qf_oauth cookie — all cookies: %s',
        rawCookieHeader.replace(/=[^;]{8,}/g, '=<redacted>'));
      return redirectToReader({ qf_error: 'oauth_state_expired' });
    }
    const sepIdx = stored.indexOf('.');
    const cookieState = sepIdx > 0 ? stored.slice(0, sepIdx) : '';
    const verifier    = sepIdx > 0 ? stored.slice(sepIdx + 1) : '';

    console.log('[qf-auth] callback: cookie_state_prefix=%s state_match=%s verifier_present=%s',
      cookieState.slice(0, 12) + '…',
      cookieState === state,
      verifier.length > 0);

    if (cookieState !== state || !verifier) {
      console.log('[qf-auth] callback: state mismatch or missing verifier');
      return redirectToReader({ qf_error: 'state_mismatch' });
    }

    let tokens;
    try {
      const tokenRes = await fetch(TOKEN_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'Accept': 'application/json',
          'Authorization': 'Basic ' + Buffer.from(`${QF_CLIENT_ID}:${QF_CLIENT_SECRET}`).toString('base64'),
        },
        body: new URLSearchParams({
          grant_type:    'authorization_code',
          code,
          redirect_uri:  QF_REDIRECT_URI,
          code_verifier: verifier,
          client_id:     QF_CLIENT_ID,
        }).toString(),
      });
      if (!tokenRes.ok) {
        const detail = (await tokenRes.text()).slice(0, 200);
        console.error('QF token exchange failed', tokenRes.status, detail);
        return redirectToReader({ qf_error: 'token_exchange_failed' }, {
          'Set-Cookie': buildCookie('qf_oauth', '', 0),
        });
      }
      tokens = await tokenRes.json();
    } catch (e) {
      console.error('QF token exchange threw', e);
      return redirectToReader({ qf_error: 'token_exchange_threw' });
    }

    // Userinfo is best-effort — if QF doesn't expose it or returns minimal data,
    // the client falls back to whatever it gets.
    let user = null;
    try {
      const uiRes = await fetch(USERINFO_URL, {
        headers: { Authorization: `Bearer ${tokens.access_token}`, Accept: 'application/json' },
      });
      if (uiRes.ok) user = await uiRes.json();
    } catch (e) {
      console.warn('QF userinfo fetch failed (non-fatal)', e?.message);
    }

    return redirectToReader(
      {
        qf_access_token:  tokens.access_token || '',
        qf_refresh_token: tokens.refresh_token || '',
        qf_expires_in:    String(tokens.expires_in || 3600),
        qf_token_type:    tokens.token_type || 'Bearer',
        qf_id_token:      tokens.id_token || '',
        qf_user:          user ? base64url(JSON.stringify(user)) : '',
      },
      { 'Set-Cookie': buildCookie('qf_oauth', '', 0) },
    );
  }

  // ── REFRESH ────────────────────────────────────────────────
  if (action === 'refresh') {
    if (event.httpMethod !== 'POST') {
      return { statusCode: 405, body: 'Method not allowed' };
    }
    let refresh_token;
    try {
      refresh_token = JSON.parse(event.body || '{}').refresh_token;
    } catch {
      return { statusCode: 400, body: 'Invalid body' };
    }
    if (!refresh_token) return { statusCode: 400, body: 'Missing refresh_token' };

    const r = await fetch(TOKEN_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json',
        'Authorization': 'Basic ' + Buffer.from(`${QF_CLIENT_ID}:${QF_CLIENT_SECRET}`).toString('base64'),
      },
      body: new URLSearchParams({
        grant_type:    'refresh_token',
        refresh_token,
        client_id:     QF_CLIENT_ID,
      }).toString(),
    });
    if (!r.ok) return { statusCode: 401, body: 'Refresh failed' };
    const tokens = await r.json();
    return {
      statusCode: 200,
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': APP_ORIGIN,
      },
      body: JSON.stringify(tokens),
    };
  }

  return { statusCode: 400, body: 'Unknown action' };
};
