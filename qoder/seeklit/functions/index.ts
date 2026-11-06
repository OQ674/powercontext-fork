/** SeekLit Sites Function：把 /functions/v1/app/* 白名单转发到 seekdb 后端（FastAPI + pyseekdb）。 */

const TIMEOUT_MS = 8000;
// 后端公网隧道地址（cloudflared 快速隧道）。优先读 Secret SEEKLIT_BACKEND_URL，未配置时用此默认值。
const DEFAULT_BACKEND_URL = "https://shopper-visiting-prayers-reference.trycloudflare.com";

const ROUTES: Array<{ method: string; sub: RegExp; target: string }> = [
  { method: "GET", sub: /^\/health$/, target: "/api/health" },
  { method: "POST", sub: /^\/search$/, target: "/api/search" },
  { method: "GET", sub: /^\/papers$/, target: "/api/papers" },
  { method: "GET", sub: /^\/papers\/([^\/]+)$/, target: "/api/papers/$1" },
  { method: "POST", sub: /^\/papers$/, target: "/api/papers" },
  { method: "PUT", sub: /^\/papers\/([^\/]+)$/, target: "/api/papers/$1" },
  { method: "DELETE", sub: /^\/papers\/([^\/]+)$/, target: "/api/papers/$1" },
  { method: "POST", sub: /^\/import$/, target: "/api/import" },
  { method: "POST", sub: /^\/reindex$/, target: "/api/reindex" },
];

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}

async function forward(request: Request, targetPath: string, method: string): Promise<Response> {
  const backendUrl = (Deno.env.get("SEEKLIT_BACKEND_URL") || DEFAULT_BACKEND_URL).replace(/\/+$/, "");
  const backendToken = Deno.env.get("SEEKLIT_BACKEND_TOKEN") || "";
  if (!backendUrl) {
    return jsonResponse(503, { code: "BACKEND_OFFLINE", message: "后端地址未配置。" });
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const headers: Record<string, string> = { "content-type": "application/json" };
    if (backendToken) headers["x-api-token"] = backendToken;
    const init: RequestInit = { method, headers, signal: controller.signal };
    if (method !== "GET" && method !== "DELETE") {
      init.body = await request.text();
    }
    const resp = await fetch(`${backendUrl}${targetPath}`, init);
    const text = await resp.text();
    const ctype = resp.headers.get("content-type") || "";
    // 隧道存活但源站已挂时，cloudflared 会返回 502/504 的 HTML 页面；统一降级为 BACKEND_OFFLINE，
    // 否则前端会拿到非 JSON 响应而无法展示离线横幅。
    if (!ctype.includes("json") && (resp.status === 502 || resp.status === 503 || resp.status === 504)) {
      return jsonResponse(503, {
        code: "BACKEND_OFFLINE",
        message: "演示服务当前离线：本地 seekdb 后端未启动或隧道中断。",
      });
    }
    return new Response(text, {
      status: resp.status,
      headers: { "content-type": ctype || "application/json; charset=utf-8" },
    });
  } catch {
    return jsonResponse(503, {
      code: "BACKEND_OFFLINE",
      message: "演示服务当前离线：本地 seekdb 后端未启动或隧道中断。",
    });
  } finally {
    clearTimeout(timer);
  }
}

async function handler(request: Request): Promise<Response> {
  const url = new URL(request.url);
  // 边缘会按部署改写前缀（/functions/v1/app/…、/app-<rev>/…），逐段剥掉路由名之前的前缀段。
  const segs = decodeURIComponent(url.pathname).split("/").filter((s) => s !== "");
  while (segs.length && /^(functions|v1|app([-_.a-z0-9]*)?)$/i.test(segs[0])) segs.shift();
  const sub = "/" + segs.join("/");
  const method = request.method.toUpperCase();

  for (const r of ROUTES) {
    if (r.method === method) {
      const m = sub.match(r.sub);
      if (m) {
        const target = sub.replace(r.sub, r.target);
        return await forward(request, target, method);
      }
    }
  }
  return jsonResponse(404, { code: "NOT_FOUND", message: "未知接口。" });
}

export { handler };

if (import.meta.main) {
  Deno.serve(handler);
}
