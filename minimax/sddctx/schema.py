"""数据库表结构。

表设计围绕"规格驱动开发"的四类资产展开：

* ``sdd_spec_item``   —— 规格条目（含版本号，规格更新后重新导入即产生新版本）。
* ``sdd_code_symbol`` —— 代码文件与符号（函数 / 类 / 方法）。
* ``sdd_test_case``   —— 测试用例（pytest node id）。
* ``sdd_task`` / ``sdd_task_progress`` / ``sdd_verification`` —— 任务与进展。
* ``sdd_retrieval_log`` / ``sdd_query_log`` —— 检索记录与全部 SQL 执行记录。
"""

from __future__ import annotations

from typing import List

from .db import Database

SCHEMA_STATEMENTS: List[str] = [
    """
    CREATE TABLE IF NOT EXISTS sdd_spec_item (
        id            INT AUTO_INCREMENT PRIMARY KEY,
        spec_id       VARCHAR(64)  NOT NULL,
        title         VARCHAR(256) NOT NULL,
        module        VARCHAR(128) NOT NULL DEFAULT '',
        status        VARCHAR(32)  NOT NULL DEFAULT '生效',
        body          MEDIUMTEXT   NOT NULL,
        keywords      TEXT,
        related_code  TEXT,
        related_tests TEXT,
        source_file   VARCHAR(512) NOT NULL,
        content_hash  CHAR(64)     NOT NULL,
        revision      INT          NOT NULL DEFAULT 1,
        updated_at    DATETIME     NOT NULL,
        UNIQUE KEY uk_spec_id (spec_id),
        KEY idx_spec_module (module),
        KEY idx_spec_hash (content_hash)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS sdd_code_symbol (
        id           INT AUTO_INCREMENT PRIMARY KEY,
        file_path    VARCHAR(512) NOT NULL,
        symbol       VARCHAR(256) NOT NULL,
        kind         VARCHAR(32)  NOT NULL,
        signature    TEXT,
        docstring    MEDIUMTEXT,
        line_start   INT NOT NULL DEFAULT 0,
        line_end     INT NOT NULL DEFAULT 0,
        source_file  VARCHAR(512) NOT NULL,
        content_hash CHAR(64)     NOT NULL,
        updated_at   DATETIME     NOT NULL,
        UNIQUE KEY uk_symbol (file_path, symbol, line_start),
        KEY idx_symbol_name (symbol),
        KEY idx_symbol_file (file_path)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS sdd_test_case (
        id           INT AUTO_INCREMENT PRIMARY KEY,
        node_id      VARCHAR(512) NOT NULL,
        file_path    VARCHAR(512) NOT NULL,
        test_name    VARCHAR(256) NOT NULL,
        purpose      TEXT,
        markers      VARCHAR(256) NOT NULL DEFAULT '',
        source_file  VARCHAR(512) NOT NULL,
        content_hash CHAR(64)     NOT NULL,
        updated_at   DATETIME     NOT NULL,
        UNIQUE KEY uk_test_node (node_id),
        KEY idx_test_file (file_path)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS sdd_task (
        task_id     VARCHAR(64)  NOT NULL PRIMARY KEY,
        title       VARCHAR(256) NOT NULL,
        description MEDIUMTEXT,
        status      VARCHAR(32)  NOT NULL DEFAULT 'in_progress',
        created_at  DATETIME     NOT NULL,
        updated_at  DATETIME     NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS sdd_task_progress (
        id         INT AUTO_INCREMENT PRIMARY KEY,
        task_id    VARCHAR(64) NOT NULL,
        kind       VARCHAR(32) NOT NULL,
        content    MEDIUMTEXT  NOT NULL,
        origin     VARCHAR(32) NOT NULL DEFAULT 'local',
        created_at DATETIME    NOT NULL,
        KEY idx_progress_task (task_id),
        KEY idx_progress_kind (kind)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS sdd_verification (
        id         INT AUTO_INCREMENT PRIMARY KEY,
        task_id    VARCHAR(64) NOT NULL,
        phase      VARCHAR(32) NOT NULL,
        command    TEXT,
        exit_code  INT,
        passed     INT NOT NULL DEFAULT 0,
        failed     INT NOT NULL DEFAULT 0,
        log_path   VARCHAR(512),
        created_at DATETIME     NOT NULL,
        KEY idx_verify_task (task_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS sdd_retrieval_log (
        id         INT AUTO_INCREMENT PRIMARY KEY,
        task_id    VARCHAR(64),
        query_text TEXT,
        target_kind VARCHAR(32) NOT NULL,
        item_ref   VARCHAR(512) NOT NULL,
        score      DOUBLE NOT NULL DEFAULT 0,
        sql_text   MEDIUMTEXT,
        created_at DATETIME     NOT NULL,
        KEY idx_retrieval_task (task_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS sdd_query_log (
        id         INT AUTO_INCREMENT PRIMARY KEY,
        session_id VARCHAR(64) NOT NULL,
        seq        INT NOT NULL DEFAULT 0,
        sql_text   MEDIUMTEXT NOT NULL,
        params     MEDIUMTEXT,
        row_count  INT NOT NULL DEFAULT 0,
        duration_ms DOUBLE NOT NULL DEFAULT 0,
        created_at DATETIME NOT NULL,
        KEY idx_query_session (session_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
]


def apply_schema(database: Database) -> List[str]:
    """建表，返回实际执行的语句列表。"""

    executed: List[str] = []
    for statement in SCHEMA_STATEMENTS:
        database.execute(statement, log=False)
        executed.append(" ".join(statement.split()))
    return executed
