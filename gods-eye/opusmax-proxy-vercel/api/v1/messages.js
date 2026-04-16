// Vercel Node.js serverless proxy for api.opusmax.pro
// Retries transient 502/503/504 with jittered exponential backoff.
// 60-second budget; opus-4-6 takes ~3-5s so we fit 4-5 retries.

export const config = { maxDuration: 60 };

const UPSTREAM = 'https://api.opusmax.pro/v1/messages';
const RETRY_STATUSES = new Set([429, 502, 503, 504]);
const MAX_ATTEMPTS = 5;
const BASE_DELAY_MS = 400;
const MAX_DELAY_MS = 5000;
const PER_ATTEMPT_TIMEOUT_MS = 45000;

function jitteredBackoff(attempt) {
  const base = Math.min(BASE_DELAY_MS * Math.pow(2, attempt), MAX_DELAY_MS);
  return Math.round(base * (0.75 + Math.random() * 0.5));
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function fetchWithTimeout(url, init, timeoutMs) {
  const controller = new AbortController();
  const tid = setTimeout(() => controller.abort(), timeoutMs);
  try { return await fetch(url, { ...init, signal: controller.signal }); }
  finally { clearTimeout(tid); }
}

export default async function handler(req, res) {
  if (req.method === 'OPTIONS') {    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, x-api-key, anthropic-version, anthropic-beta');
    return res.status(204).end();
  }
  if (req.method !== 'POST') return res.status(405).json({ error: 'Only POST supported' });

  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  const body = Buffer.concat(chunks);

  const fwdHeaders = {};
  for (const [key, value] of Object.entries(req.headers)) {
    const k = key.toLowerCase();
    if (k === 'x-api-key' || k.startsWith('anthropic') || k === 'content-type' || k === 'accept') {
      fwdHeaders[key] = value;
    }
  }

  let lastStatus = 0, lastBody = null, lastError = null;

  for (let attempt = 0; attempt < MAX_ATTEMPTS; attempt++) {
    try {
      const upstreamRes = await fetchWithTimeout(UPSTREAM, { method: 'POST', headers: fwdHeaders, body }, PER_ATTEMPT_TIMEOUT_MS);

      if (RETRY_STATUSES.has(upstreamRes.status) && attempt < MAX_ATTEMPTS - 1) {
        lastStatus = upstreamRes.status;
        try { lastBody = await upstreamRes.arrayBuffer(); } catch (_) { lastBody = null; }
        const delay = jitteredBackoff(attempt);
        console.warn(`[proxy] upstream ${upstreamRes.status}, retry ${attempt + 1}/${MAX_ATTEMPTS} in ${delay}ms`);        await sleep(delay);
        continue;
      }

      res.status(upstreamRes.status);
      upstreamRes.headers.forEach((value, key) => {
        const k = key.toLowerCase();
        if (k !== 'content-encoding' && k !== 'transfer-encoding') res.setHeader(key, value);
      });
      res.setHeader('X-Proxy', 'gods-eye-vercel-relay');
      res.setHeader('X-Proxy-Attempts', String(attempt + 1));
      return res.send(Buffer.from(await upstreamRes.arrayBuffer()));
    } catch (err) {
      lastError = err;
      console.warn(`[proxy] network error attempt ${attempt + 1}/${MAX_ATTEMPTS}: ${err?.message || err}`);
      if (attempt < MAX_ATTEMPTS - 1) { await sleep(jitteredBackoff(attempt)); continue; }
    }
  }

  res.setHeader('X-Proxy', 'gods-eye-vercel-relay');
  res.setHeader('X-Proxy-Attempts', String(MAX_ATTEMPTS));
  if (lastStatus && lastBody) {
    res.status(lastStatus);
    return res.send(Buffer.from(lastBody));
  }
  return res.status(502).json({ error: 'Upstream unreachable after retries', detail: lastError ? String(lastError) : `last_status=${lastStatus}`, attempts: MAX_ATTEMPTS });
}
