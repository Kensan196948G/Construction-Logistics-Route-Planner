// The backend is a FastAPI service (systemd/Docker) reachable over HTTPS; it
// cannot live inside the Worker. Deployments MUST set BACKEND_ORIGIN to the
// backend's public URL (e.g. https://route-planner-api.example.com). Leaving
// it empty makes /api/* fail with a clear 502 instead of silently proxying to
// a non-existent localhost inside Cloudflare's network.
const BACKEND_ORIGIN = (typeof BACKEND_ORIGIN !== "undefined" ? BACKEND_ORIGIN : null) || "";
const ALLOWED_ORIGINS = [
  "https://mirai-dx-platform.com",
  "https://staging.mirai-dx-platform.com",
  "http://localhost:5173",
  "http://localhost:3000",
];
const EXCLUDED_HEADERS = new Set(["cf-", "x-forwarded-", "x-real-ip", "content-encoding", "transfer-encoding"]);

function buildApiUrl(pathname, search) {
  const backend = String(BACKEND_ORIGIN || "").trim().replace(/\/+$/, "");
  if (!/^https?:\/\/.+/i.test(backend)) {
    return null;
  }
  return backend + pathname + (search || "");
}

function isOriginAllowed(origin) {
  if (!origin) return false;
  return ALLOWED_ORIGINS.includes(origin) || ALLOWED_ORIGINS.some((o) => o === "*");
}

function corsHeaders(request) {
  const origin = request.headers.get("Origin");
  const headers = new Headers();

  if (origin && isOriginAllowed(origin)) {
    headers.set("Access-Control-Allow-Origin", origin);
  }

  headers.set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, PATCH, OPTIONS");
  headers.set("Access-Control-Allow-Headers", "Authorization, Content-Type");
  headers.set("Access-Control-Max-Age", "86400");
  return headers;
}

function passthroughHeaders(request) {
  const headers = new Headers();
  for (const [key, value] of request.headers) {
    if (EXCLUDED_HEADERS.has(key.toLowerCase()) || key.toLowerCase().startsWith("cf-")) {
      continue;
    }
    headers.set(key, value);
  }
  headers.set("X-Forwarded-Host", new URL(request.url).hostname);
  headers.set("X-Forwarded-Proto", "https");
  return headers;
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const pathname = url.pathname;

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders(request) });
    }

    if (pathname === "/api/health") {
      return new Response(
        JSON.stringify({
          status: "ok",
          service: "construction-logistics-route-planner",
          version: "0.1.0",
          proxy: "cloudflare-worker",
          backend: BACKEND_ORIGIN,
          timestamp: new Date().toISOString(),
        }),
        { status: 200, headers: { "Content-Type": "application/json", ...Object.fromEntries(corsHeaders(request)) } }
      );
    }

    if (!pathname.startsWith("/api/")) {
      return new Response("Not Found", { status: 404, headers: corsHeaders(request) });
    }

    try {
      const backendUrl = buildApiUrl(pathname, url.search);
      if (!backendUrl) {
        return new Response(
          JSON.stringify({
            detail: "BACKEND_ORIGIN is not configured",
            service: "construction-logistics-route-planner",
            timestamp: new Date().toISOString(),
          }),
          {
            status: 502,
            headers: { "Content-Type": "application/json", ...Object.fromEntries(corsHeaders(request)) },
          }
        );
      }
      const response = await fetch(backendUrl, {
        method: request.method,
        headers: passthroughHeaders(request),
        body: request.method !== "GET" && request.method !== "HEAD"
          ? await request.text().catch(() => null)
          : undefined,
        redirect: "manual",
      });

      const responseHeaders = new Headers(corsHeaders(request));
      for (const [key, value] of response.headers) {
        if (EXCLUDED_HEADERS.has(key.toLowerCase())) continue;
        responseHeaders.set(key, value);
      }

      return new Response(response.body, {
        status: response.status,
        statusText: response.statusText,
        headers: responseHeaders,
      });
    } catch (err) {
      return new Response(
        JSON.stringify({
          detail: "Backend unreachable",
          service: "construction-logistics-route-planner",
          timestamp: new Date().toISOString(),
        }),
        {
          status: 502,
          headers: { "Content-Type": "application/json", ...Object.fromEntries(corsHeaders(request)) },
        }
      );
    }
  },
};
