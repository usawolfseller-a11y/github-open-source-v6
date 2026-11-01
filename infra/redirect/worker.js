/**
 * Click measurement for GitHub Open Source.
 *
 * GET /r/<code>  → 302 to the GitHub repo, one KV counter increment.
 * GET /stats     → JSON {"<code>": <clicks>, ...} behind a shared token.
 *
 * Free tier: Cloudflare Workers (100k requests/day) + KV. One write per
 * click, so this fits a channel of this size; at 10x traffic move the
 * counter to a Durable Object.
 *
 * Deploy:   wrangler deploy   (see README.md in this folder)
 * Bindings: REPOS (KV, code → url), STATS (KV, code → count), STATS_TOKEN.
 */
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const match = url.pathname.match(/^\/r\/([a-z0-9]{4,32})$/i);
    if (match) {
      const code = match[1].toLowerCase();
      const target = await env.REPOS.get(code);
      if (!target) return new Response("unknown link", { status: 404 });
      const current = parseInt((await env.STATS.get(code)) || "0", 10) + 1;
      await env.STATS.put(code, String(current));
      return Response.redirect(target, 302);
    }
    if (url.pathname === "/stats") {
      if (url.searchParams.get("token") !== env.STATS_TOKEN) {
        return new Response("forbidden", { status: 403 });
      }
      const list = await env.STATS.list();
      const out = {};
      for (const key of list.keys) {
        out[key.name] = parseInt((await env.STATS.get(key.name)) || "0", 10);
      }
      return Response.json(out);
    }
    return new Response("GitHub Open Source redirect layer", { status: 200 });
  },
};
