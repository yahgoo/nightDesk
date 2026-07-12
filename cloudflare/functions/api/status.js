// Cloudflare Pages Function: proxies /api/status from the NightDesk FastAPI
// backend so the static dashboard (index.html) can read live status. Deploys
// automatically with the Pages project (see wrangler.toml). Returns an honest
// {staged:true} payload if the backend is unreachable rather than faking data.
export async function onRequestGet(context) {
  const backend = context.env.BACKEND_URL || "http://localhost:8000";
  try {
    const r = await fetch(backend + "/api/status");
    const data = await r.json();
    return new Response(JSON.stringify(data), {
      headers: { "content-type": "application/json", "access-control-allow-origin": "*" },
    });
  } catch (e) {
    return new Response(
      JSON.stringify({ error: String(e), staged: true, service: "nightdesk" }),
      { status: 502, headers: { "content-type": "application/json" } },
    );
  }
}
