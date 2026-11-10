"""seekdb / OceanBase 访问层。

统一使用 MySQL 协议访问数据库，因此同一套 SQL 既可以跑在嵌入式 seekdb
（pylibseekdb，通过 Unix socket 暴露 MySQL 协议）上，也可以跑在独立部署的
seekdb / OceanBase Server 上。

所有执行的 SQL 都会写入 ``sdd_query_log`` 表，作为"数据库真实参与"的证据。
"""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence

import pymysql
from pymysql.cursors import DictCursor

from .config import Config


class DatabaseError(RuntimeError):
    """数据库访问异常。"""


class Database:
    """seekdb / OceanBase 访问封装。"""

    def __init__(self, config: Config) -> None:
        self.config = config
        self._instance = None  # 嵌入式 seekdb 实例，需要保持引用
        self._connection = None
        self.session_id = datetime.now().strftime("%Y%m%d%H%M%S")
        self._statement_counter = 0

    # ------------------------------------------------------------------
    # 连接管理
    # ------------------------------------------------------------------
    def connect(self) -> "Database":
        """建立连接（嵌入式模式下会拉起本地 seekdb 实例）。"""

        if self.config.db_mode == "embedded":
            self._connect_embedded()
        else:
            self._connect_server()
        self.ensure_database()
        self.execute(f"USE `{self.config.db_name}`")
        return self

    def _connect_embedded(self) -> None:
        try:
            import pylibseekdb  # type: ignore
        except ImportError as exc:  # pragma: no cover - 依赖缺失时的提示
            raise DatabaseError(
                "嵌入式模式需要 pylibseekdb（pip install pyseekdb）；"
                "或在配置中设置 SDDCTX_DB_MODE=server 使用 seekdb/OceanBase Server"
            ) from exc

        self.config.db_dir.mkdir(parents=True, exist_ok=True)
        self._instance = pylibseekdb.open(str(self.config.db_dir))
        options = self._instance.connection_options()
        socket_path = options.get("unix_socket")
        if not socket_path:
            raise DatabaseError("嵌入式 seekdb 未返回 unix_socket，无法建立 MySQL 协议连接")
        self._connection = pymysql.connect(
            unix_socket=socket_path,
            user=options.get("user", self.config.db_user),
            password=self.config.db_password,
            autocommit=True,
            cursorclass=DictCursor,
            charset="utf8mb4",
        )

    def _connect_server(self) -> None:
        self._connection = pymysql.connect(
            host=self.config.db_host,
            port=self.config.db_port,
            user=self.config.db_user,
            password=self.config.db_password,
            autocommit=True,
            cursorclass=DictCursor,
            charset="utf8mb4",
            connect_timeout=10,
        )

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None
        if self._instance is not None:
            try:
                self._instance.close()
            except Exception:  # pragma: no cover - 关闭失败不影响结果
                pass
            self._instance = None

    def __enter__(self) -> "Database":
        return self.connect()

    def __exit__(self, *exc_info) -> None:
        self.close()

    @property
    def connection(self):
        if self._connection is None:
            raise DatabaseError("数据库尚未连接，请先调用 connect()")
        return self._connection

    # ------------------------------------------------------------------
    # SQL 执行
    # ------------------------------------------------------------------
    def execute(self, sql: str, params: Optional[Sequence[Any]] = None, *, log: bool = True) -> int:
        """执行写语句，返回影响行数。"""

        started = time.perf_counter()
        with self.connection.cursor() as cursor:
            affected = cursor.execute(sql, params or ())
        if log and self.config.query_log_enabled:
            self._log_query(sql, params, affected, (time.perf_counter() - started) * 1000)
        return affected

    def query(self, sql: str, params: Optional[Sequence[Any]] = None, *, log: bool = True) -> List[Dict[str, Any]]:
        """执行读语句，返回字典列表。"""

        started = time.perf_counter()
        with self.connection.cursor() as cursor:
            cursor.execute(sql, params or ())
            rows = list(cursor.fetchall())
        if log and self.config.query_log_enabled:
            self._log_query(sql, params, len(rows), (time.perf_counter() - started) * 1000)
        return rows

    def query_one(self, sql: str, params: Optional[Sequence[Any]] = None) -> Optional[Dict[str, Any]]:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def scalar(self, sql: str, params: Optional[Sequence[Any]] = None):
        row = self.query_one(sql, params)
        if not row:
            return None
        return list(row.values())[0]

    def executemany(self, sql: str, rows: Iterable[Sequence[Any]]) -> int:
        payload = list(rows)
        if not payload:
            return 0
        started = time.perf_counter()
        with self.connection.cursor() as cursor:
            affected = cursor.executemany(sql, payload)
        if self.config.query_log_enabled:
            self._log_query(sql, payload, affected, (time.perf_counter() - started) * 1000)
        return affected

    def _log_query(self, sql: str, params, affected: int, duration_ms: float) -> None:
        """把 SQL 写入 ``sdd_query_log``（写入动作本身不再记录，避免递归）。"""

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO sdd_query_log (session_id, seq, sql_text, params, row_count, duration_ms, created_at)"
                    " VALUES (%s, %s, %s, %s, %s, %s, NOW())",
                    (
                        self.session_id,
                        self._statement_counter,
                        " ".join(sql.split()),
                        json.dumps(_jsonable(params), ensure_ascii=False)[:4000],
                        affected,
                        round(duration_ms, 3),
                    ),
                )
            self._statement_counter += 1
        except Exception:  # pragma: no cover - 日志失败不影响主流程
            pass

    # ------------------------------------------------------------------
    # 便捷方法
    # ------------------------------------------------------------------
    def ensure_database(self) -> None:
        """确保目标数据库存在。"""

        self.execute(
            f"CREATE DATABASE IF NOT EXISTS `{self.config.db_name}` CHARACTER SET utf8mb4",
            log=False,
        )

    def server_version(self) -> str:
        try:
            return str(self.scalar("SELECT VERSION()"))
        except Exception:  # pragma: no cover
            return "unknown"

    def describe(self) -> Dict[str, Any]:
        return {
            "backend": self.config.describe_database(),
            "mode": self.config.db_mode,
            "database": self.config.db_name,
            "server_version": self.server_version(),
        }


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (int, float, str, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return str(value)


@contextmanager
def open_database(config: Config):
    """打开数据库连接的上下文管理器。"""

    database = Database(config)
    try:
        yield database.connect()
    finally:
        database.close()
