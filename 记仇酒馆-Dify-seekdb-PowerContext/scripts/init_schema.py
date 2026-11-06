"""执行 seed/00_schema.sql（给没有 mysql 客户端的 Windows 环境用）。

用法：
    python scripts/init_schema.py
"""

from __future__ import annotations

import os
from pathlib import Path

import pymysql

SQL_FILE = Path(__file__).resolve().parent.parent / "seed" / "00_schema.sql"

conn = pymysql.connect(
    host=os.getenv("SEEKDB_HOST", "127.0.0.1"),
    port=int(os.getenv("SEEKDB_PORT", "2881")),
    user=os.getenv("SEEKDB_USER", "root"),
    password=os.getenv("SEEKDB_PASSWORD", ""),
    charset="utf8mb4",
    autocommit=True,
)

raw = SQL_FILE.read_text(encoding="utf-8")
statements: list[str] = []
for chunk in raw.split(";"):
    lines = [line for line in chunk.splitlines() if not line.strip().startswith("--")]
    stmt = "\n".join(lines).strip()
    if stmt:
        statements.append(stmt)

with conn, conn.cursor() as cur:
    for stmt in statements:
        cur.execute(stmt)
        head = " ".join(stmt.split())[:72]
        print(f"[ok] {head}")

print(f"[done] 已执行 {len(statements)} 条语句，数据库 tavern 初始化完成。")
