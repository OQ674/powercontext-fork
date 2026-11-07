// 本地开发入口：读取 dev/.env，监听 127.0.0.1:8000，转发逻辑与 functions/index.ts 完全一致。
// 不进入发布包。运行：deno run --allow-net --allow-env dev/function-local.ts
import { handler } from "../functions/index.ts";

if (!Deno.env.get("SEEKLIT_BACKEND_URL")) {
  try {
    const envPath = new URL("./.env", import.meta.url);
    const env = await Deno.readTextFile(envPath);
    for (const line of env.split(/\r?\n/)) {
      const m = line.match(/^([A-Z_][A-Z0-9_]*)=(.*)$/);
      if (m) Deno.env.set(m[1], m[2].trim());
    }
  } catch { /* .env 可选 */
    console.warn("dev/.env not found; set SEEKLIT_BACKEND_URL manually");
  }
}

Deno.serve({ hostname: "127.0.0.1", port: 8000 }, handler);
