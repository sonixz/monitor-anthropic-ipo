// antipo.watch → the dashboard on Fly.io (Loop 005).
//
// Cloudflare terminates TLS for antipo.watch. Fly.io holds no certificate for that name, so this
// Worker calls the app at its fly.dev address and returns the answer unchanged. www and any other
// name redirect permanently to the apex. No secret lives here: the file is public.

const ORIGIN = "https://agmgd-on-ipo-monitor-ba4eccd0.fly.dev";
const APEX = "antipo.watch";

export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (url.hostname !== APEX || url.protocol !== "https:") {
      url.hostname = APEX;
      url.protocol = "https:";
      return Response.redirect(url.toString(), 301);
    }
    const target = new URL(url.pathname + url.search, ORIGIN);
    const headers = new Headers(request.headers);
    headers.set("X-Forwarded-Host", APEX);
    const answer = await fetch(target, {
      method: request.method,
      headers,
      body: ["GET", "HEAD"].includes(request.method) ? undefined : request.body,
      redirect: "manual",
      // Files under /static/ carry a version in their address and are sent as immutable:
      // Cloudflare may keep them at the edge. The page itself is never kept (no-cache).
      cf: url.pathname.startsWith("/static/") ? { cacheEverything: true } : undefined,
    });
    const out = new Response(answer.body, answer);
    // A redirect from the app names the fly.dev address: point it back at the domain.
    const location = answer.headers.get("Location");
    if (location && location.startsWith(ORIGIN)) {
      out.headers.set("Location", "https://" + APEX + location.slice(ORIGIN.length));
    }
    // The page must reach the reader as the app wrote it: no analytics beacon, no rewritten
    // e-mail links. Cloudflare leaves a response alone when it says no-transform.
    const cache = answer.headers.get("Cache-Control");
    if (!cache || !cache.includes("no-transform")) {
      out.headers.set("Cache-Control", cache ? cache + ", no-transform" : "no-transform");
    }
    return out;
  },
};
