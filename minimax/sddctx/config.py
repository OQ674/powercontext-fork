"""模块配置。

所有配置项都可以用 ``SDDCTX_*`` 环境变量覆盖；``--config`` 指定的文件使用
``KEY=VALUE`` 形式，优先级低于环境变量。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict

DEFAULT_DB_NAME = "sddctx"
DEFAULT_POWERCONTEXT_URL = "http://127.0.0.1:8000"


@dataclass
class Config:
    """一次运行所需的全部配置。"""

    project_root: Path
    db_mode: str = "embedded"
    db_dir: Path = field(default_factory=lambda: Path(".sddctx/seekdb"))
    db_host: str = "127.0.0.1"
    db_port: int = 2881
    db_user: str = "root"
    db_password: str = ""
    db_name: str = DEFAULT_DB_NAME
    powercontext_url: str = DEFAULT_POWERCONTEXT_URL
    powercontext_scope: str = "sdd-context-module"
    minimax_api_key: str = ""
    minimax_base_url: str = "https://api.minimax.chat/v1"
    minimax_model: str = "MiniMax-M2"
    query_log_enabled: bool = True

    @property
    def artifacts_dir(self) -> Path:
        return self.project_root / "artifacts"

    @property
    def logs_dir(self) -> Path:
        return self.project_root / "logs"

    def describe_database(self) -> str:
        if self.db_mode == "embedded":
            return f"embedded seekdb (data dir: {self.db_dir})"
        return f"seekdb/OceanBase server {self.db_host}:{self.db_port} (database: {self.db_name})"


def _read_env_file(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_config(project_root: Path, config_file: Path | None = None) -> Config:
    """按"文件 < 环境变量"的优先级组装配置。"""

    file_values: Dict[str, str] = {}
    if config_file is not None:
        file_values = _read_env_file(config_file)

    def pick(key: str, default: str) -> str:
        return os.environ.get(f"SDDCTX_{key}", file_values.get(f"SDDCTX_{key}", default))

    root = Path(pick("PROJECT_ROOT", str(project_root))).resolve()
    db_dir = Path(pick("SEEKDB_DIR", str(root / ".sddctx" / "seekdb")))

    config = Config(
        project_root=root,
        db_mode=pick("DB_MODE", "embedded").lower(),
        db_dir=db_dir,
        db_host=pick("DB_HOST", "127.0.0.1"),
        db_port=int(pick("DB_PORT", "2881")),
        db_user=pick("DB_USER", "root"),
        db_password=pick("DB_PASSWORD", ""),
        db_name=pick("DB_NAME", DEFAULT_DB_NAME),
        powercontext_url=pick("POWERCONTEXT_URL", DEFAULT_POWERCONTEXT_URL).rstrip("/"),
        powercontext_scope=pick("POWERCONTEXT_SCOPE", "sdd-context-module"),
        minimax_api_key=pick("MINIMAX_API_KEY", ""),
        minimax_base_url=pick("MINIMAX_BASE_URL", "https://api.minimax.chat/v1"),
        minimax_model=pick("MINIMAX_MODEL", "MiniMax-M2"),
        query_log_enabled=pick("QUERY_LOG", "1") not in {"0", "false", "False"},
    )
    return config
