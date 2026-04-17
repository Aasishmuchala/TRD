/**
 * Cloudflare Worker: OpusMax Proxy Relay
 * 
 * Sits between Railway (US) and OpusMax proxy to avoid geo/IP blocking.
 * Forwards /v1/messages requests with all headers intact.
 * Free tier: 100k requests/day — more than enough for God's Eye.
 */

export default {
  async fetch(request, env) {
    // CORS preflight
    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "POST, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type, x-api-key, anthropic-version, anthropic-beta",
          "Access-Control-Max-Age": "86400",
        },
      });
    }

    const url = new URL(request.url);
    if (request.method !== "POST" || !url.pathname.startsWith("/v1/")) {
      return new Response(JSON.stringify({ error: "Only POST /v1/* is supported" }), {
        status: 405,
        headers: { "Content-Type": "application/json" },
      });
    }

    const upstream = env.UPSTREAM_URL || "https://api.opusmax.pro";
    const targetUrl = `${upstream}${url.pathname}`;

    // Buffer body so we can retry
    const bodyBuffer = await request.arrayBuffer();

    // Forward relevant headers
    const fwdHeaders = new Headers();
    for (const [key, value] of request.headers.entries()) {
      if (
        key === "x-api-key" ||
        key.startsWith("anthropic") ||
        key === "content-type" ||
        key === "accept"
      ) {
        fwdHeaders.set(key, value);
      }
    }

    // Retry logic: 3 attempts with exponential backoff
    const maxRetries = 3;
    let lastResponse = null;
    let lastError = null;

    for (let attempt = 0; attempt < maxRetries; attempt++) {
      try {
        lastResponse = await fetch(targetUrl, {
          method: "POST",
          headers: fwdHeaders,
          body: bodyBuffer,
        });

        if (lastResponse.status < 500) {
          break; // Success or client error — done
        }

        // 5xx — retry
        if (attempt < maxRetries - 1) {
          await new Promise((r) => setTimeout(r, (attempt + 1) * 2000));
        }
      } catch (err) {
        lastError = err;
        if (attempt < maxRetries - 1) {
          await new Promise((r) => setTimeout(r, (attempt + 1) * 2000));
        }
      }
    }

    if (!lastResponse && lastError) {
      return new Response(
        JSON.stringify({ error: "Upstream unreachable", detail: lastError.message }),
        { status: 502, headers: { "Content-Type": "application/json" } }
      );
    }

    // Stream response back with CORS
    const resHeaders = new Headers(lastResponse.headers);
    resHeaders.set("Access-Control-Allow-Origin", "*");
    resHeaders.set("X-Proxy", "gods-eye-cf-relay");

    return new Response(lastResponse.body, {
      status: lastResponse.status,
      headers: resHeaders,
    });
  },
};
