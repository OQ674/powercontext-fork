"""PowerContext Server 启动入口（Windows 本地环境兜底）

背景：官方推荐 `powercontext server run --env-file .env`（uv 安装 1.5.0）。
本机 HTTPS 出网被阻断，只能从 HTTP 镜像装包，且沙箱不允许在系统临时目录写文件，
导致 `jieba`（仅源码分发）无法构建、`powercontext[server]` 依赖装不全。
这里直接用 PowerContext 1.5.0 的公开 API 组装出同样的 Server：

    open_builtin_runtime(BuiltinConfig(...))  +  create_app(...)

存储用 SQLite；接口（/v1/scopes、/v1/memory/remember、/v1/context/prepare、
/health/live）与官方 Server 一致。正式环境请优先使用 `powercontext server run`。

用法（Windows PowerShell，在项目根目录）：
    .venv-pc\\Scripts\\python.exe scripts\\pc_server.py
    # 默认监听 127.0.0.1:8000
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn

os.environ.setdefault("POWERCONTEXT_SCHEDULER_DISABLED", "1")

from powercontext.builtin.runtime.composition import open_builtin_runtime  # noqa: E402
from powercontext.builtin.runtime.config import BuiltinConfig  # noqa: E402
from powercontext.server.app import create_app  # noqa: E402

HOST = os.getenv("POWERCONTEXT_HOST", "127.0.0.1")
PORT = int(os.getenv("POWERCONTEXT_PORT", "8000"))
DATA_DIR = Path(os.getenv("POWERCONTEXT_DATA_DIR", "powercontext-data")).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_URL = f"sqlite+aiosqlite:///{(DATA_DIR / 'powercontext.db').as_posix()}"


@asynccontextmanager
async def lifespan(app):
    config = BuiltinConfig.model_validate(
        {"database": {"kind": "sqlite", "url": DB_URL}}
    )
    async with open_builtin_runtime(
        config, scheduler_path=str(DATA_DIR / "scheduler.db")
    ) as runtime:
        app.state.application = runtime
        yield


app = create_app(lifespan=lifespan, allow_insecure_remote_http=True)


if __name__ == "__main__":
    print(f"[powercontext] db={DB_URL}")
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
