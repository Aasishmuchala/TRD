export const config = { runtime: 'edge' };

export default async function handler() {
  return new Response(
    JSON.stringify({
      status: 'ok',
      service: 'gods-eye-opusmax-relay',
      upstream: 'https://api.opusmax.pro',
      timestamp: new Date().toISOString(),
    }),
    { status: 200, headers: { 'Content-Type': 'application/json' } }
  );
}
