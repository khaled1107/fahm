// netlify/functions/track-section.js
//
// Two responsibilities:
//   1. Record a section-view or activity event in Supabase (fahm_reading_sessions).
//   2. When activity:true and provider=qf, call the QF Activity Days API then
//      the QF Streaks API and return the current streak count to the frontend.
//
// Required Supabase table:
//   create table public.fahm_reading_sessions (
//     id            bigserial primary key,
//     user_id       text        not null,
//     provider      text        not null check (provider in ('qf','supabase')),
//     surah_number  int         not null,
//     section_id    text,
//     completed_at  timestamptz not null default now()
//   );
//   create index on public.fahm_reading_sessions (user_id, completed_at desc);
//
// Required env vars:
//   SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY
//   QF_CLIENT_ID
//   QF_OAUTH_BASE_URL  (default: https://prelive-oauth2.quran.foundation)
//
// POST /api/track-section
// Authorization: Bearer <qf or supabase access token>
// Body: {
//   provider:     'qf' | 'supabase',
//   surah_number: int,
//   section_id?:  string,
//   activity?:    boolean,   // true → also call QF Activity Days + Streaks APIs
//   verse_count?: int,       // last verse of the surah, needed for activity range
//   timezone?:    string     // IANA tz, e.g. "America/New_York"
// }
// Response: { ok: true, streak?: number }

const SUPABASE_URL              = process.env.SUPABASE_URL;
const SUPABASE_ANON_KEY         = process.env.SUPABASE_ANON_KEY;
const SUPABASE_SERVICE_ROLE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;
const QF_CLIENT_ID              = process.env.QF_CLIENT_ID;
const QF_OAUTH_BASE             = process.env.QF_OAUTH_BASE_URL || 'https://prelive-oauth2.quran.foundation';
const QF_ACTIVITY_DAYS_URL      = 'https://apis-prelive.quran.foundation/auth/v1/activity-days';
const QF_STREAKS_URL            = 'https://apis-prelive.quran.foundation/auth/v1/streaks/current-streak-days?type=QURAN';

const CORS = {
  'Access-Control-Allow-Origin':  'https://tryfahm.com',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Authorization, Content-Type',
  'Content-Type': 'application/json',
};

function json(statusCode, body) {
  return { statusCode, headers: CORS, body: JSON.stringify(body) };
}

function resolveQFUserId(token) {
  // Decode the JWT payload without verifying the signature.
  // Safe here because sub is only used as a DB key, not for authorization.
  const payload = JSON.parse(Buffer.from(token.split('.')[1], 'base64url').toString());
  const userId = payload.sub;
  console.log('[track-section] resolveQFUserId sub=%s', userId);
  return userId || null;
}

async function resolveSupabaseUserId(token) {
  const r = await fetch(`${SUPABASE_URL}/auth/v1/user`, {
    headers: { apikey: SUPABASE_ANON_KEY, Authorization: `Bearer ${token}` },
  });
  if (!r.ok) return null;
  const u = await r.json();
  return u.id || null;
}

async function postQFActivityDay(token, surahNumber, verseCount, timezone) {
  const range = `${surahNumber}:1-${surahNumber}:${verseCount}`;
  console.log('[track-section] POST QF activity-days range=%s tz=%s client_id_set=%s token_len=%d',
    range, timezone, !!QF_CLIENT_ID, token?.length ?? 0);
  if (!QF_CLIENT_ID) {
    console.error('[track-section] QF_CLIENT_ID env var is not set — aborting activity-days POST');
    return false;
  }
  const r = await fetch(QF_ACTIVITY_DAYS_URL, {
    method: 'POST',
    headers: {
      'Content-Type':  'application/json',
      'x-auth-token':  token,
      'x-client-id':   QF_CLIENT_ID,
      'x-timezone':    timezone || 'UTC',
    },
    body: JSON.stringify({
      type:     'QURAN',
      seconds:  60,
      ranges:   [range],
      mushafId: 4,
    }),
  });
  const bodyText = (await r.text()).slice(0, 300);
  console.log('[track-section] QF activity-days → status=%d body=%s', r.status, bodyText);
  return r.ok;
}

async function getQFStreak(token) {
  console.log('[track-section] GET QF streaks token_len=%d', token?.length ?? 0);
  const r = await fetch(QF_STREAKS_URL, {
    headers: {
      'x-auth-token': token,
      'x-client-id':  QF_CLIENT_ID,
    },
  });
  const bodyText = (await r.text()).slice(0, 300);
  console.log('[track-section] QF streaks → status=%d body=%s', r.status, bodyText);
  if (!r.ok) return null;
  try {
    const data = JSON.parse(bodyText);
    return data?.data?.days ?? null;
  } catch {
    return null;
  }
}

exports.handler = async (event) => {
  console.log('[track-section] invoked');
  try {
    if (event.httpMethod === 'OPTIONS') return { statusCode: 200, headers: CORS, body: '' };
    if (event.httpMethod !== 'POST')    return json(405, { error: 'Method not allowed' });

    let body;
    try { body = JSON.parse(event.body || '{}'); }
    catch { return json(400, { error: 'Invalid JSON' }); }

    const provider     = body.provider;
    const surah_number = Number(body.surah_number);
    const section_id   = body.section_id   ? String(body.section_id)   : null;
    const isActivity   = !!body.activity;
    const verse_count  = Number(body.verse_count) || 7;
    const timezone     = String(body.timezone  || 'UTC');

    if (!['qf', 'supabase'].includes(provider))
      return json(400, { error: 'Invalid provider' });
    if (!Number.isInteger(surah_number) || surah_number < 1 || surah_number > 114)
      return json(400, { error: 'Invalid surah_number' });

    const auth  = event.headers.authorization || event.headers.Authorization || '';
    const token = auth.replace(/^Bearer\s+/i, '').trim();
    console.log('[track-section] provider=%s activity=%s auth_header_present=%s token_len=%d',
      provider, isActivity, auth.length > 0, token.length);
    if (!token) return json(401, { error: 'Missing bearer token' });

    const user_id = provider === 'qf'
      ? resolveQFUserId(token)
      : await resolveSupabaseUserId(token);
    if (!user_id) return json(401, { error: 'Token validation failed' });

    // Always record the session in Supabase.
    const insertRes = await fetch(`${SUPABASE_URL}/rest/v1/fahm_reading_sessions`, {
      method: 'POST',
      headers: {
        apikey:         SUPABASE_SERVICE_ROLE_KEY,
        Authorization:  `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
        'Content-Type': 'application/json',
        Prefer:         'return=minimal',
      },
      body: JSON.stringify({ user_id, provider, surah_number, section_id,
        completed_at: new Date().toISOString() }),
    });

    if (!insertRes.ok) {
      const detail = (await insertRes.text()).slice(0, 200);
      console.error('[track-section] DB insert failed status=%d body=%s', insertRes.status, detail);
      return json(500, { error: 'Insert failed' });
    }
    console.log('[track-section] session recorded user=%s provider=%s surah=%d activity=%s',
      user_id, provider, surah_number, isActivity);

    // QF Activity Days + Streak (QF users only, triggered after 60 s on reader).
    if (isActivity && provider === 'qf') {
      let streak = null;
      try {
        const activityOk = await postQFActivityDay(token, surah_number, verse_count, timezone);
        if (activityOk) {
          streak = await getQFStreak(token);
        }
      } catch (e) {
        console.error('[track-section] QF activity/streak threw:', e.message);
      }
      console.log('[track-section] returning streak=%s', streak);
      return json(200, { ok: true, streak });
    }

    return json(200, { ok: true });
  } catch (err) {
    console.error('[track-section] fatal error:', err);
    return json(500, { error: 'Internal server error' });
  }
};
