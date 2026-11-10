"""测试执行与结果记录。

``run_pytest`` 会真实执行 pytest 命令，记录命令、退出码、通过/失败数量，
并把结果写入 seekdb 的 ``sdd_verification`` 表与日志文件。
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Sequence

from .db import Database

_PASSED = re.compile(r"(\d+) passed")
_FAILED = re.compile(r"(\d+) failed")
_ERRORS = re.compile(r"(\d+) error")
_SKIPPED = re.compile(r"(\d+) skipped")


@dataclass
class TestRunResult:
    """一次测试执行的结果。"""

    command: str
    exit_code: int
    passed: int
    failed: int
    errors: int
    skipped: int
    log_path: str
    stdout: str

    def to_dict(self) -> dict:
        return {
            "command": self.command,
            "exit_code": self.exit_code,
            "passed": self.passed,
            "failed": self.failed,
            "errors": self.errors,
            "skipped": self.skipped,
            "log_path": self.log_path,
        }


def run_pytest(
    project_dir: Path,
    targets: Sequence[str],
    log_path: Path,
    *,
    python_executable: Optional[str] = None,
    extra_args: Optional[Sequence[str]] = None,
) -> TestRunResult:
    """执行 pytest 并解析结果。"""

    project_dir = Path(project_dir)
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    command: List[str] = [python_executable or sys.executable, "-m", "pytest"]
    command.extend(extra_args or ["-q"])
    command.extend(targets)

    completed = subprocess.run(
        command,
        cwd=str(project_dir),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = (completed.stdout or "") + (completed.stderr or "")
    header = (
        f"# command: {' '.join(command)}\n"
        f"# cwd: {project_dir}\n"
        f"# started_at: {datetime.now().isoformat(timespec='seconds')}\n"
        f"# exit_code: {completed.returncode}\n"
        f"{'-' * 72}\n"
    )
    log_path.write_text(header + output, encoding="utf-8")

    def _count(pattern: re.Pattern) -> int:
        match = pattern.search(output)
        return int(match.group(1)) if match else 0

    return TestRunResult(
        command=" ".join(command),
        exit_code=completed.returncode,
        passed=_count(_PASSED),
        failed=_count(_FAILED),
        errors=_count(_ERRORS),
        skipped=_count(_SKIPPED),
        log_path=str(log_path),
        stdout=output,
    )


def record_verification(
    database: Database,
    task_id: str,
    phase: str,
    result: TestRunResult,
) -> None:
    """把测试结果写入数据库。"""

    database.execute(
        """
        INSERT INTO sdd_verification
            (task_id, phase, command, exit_code, passed, failed, log_path, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        """,
        (
            task_id,
            phase,
            result.command,
            result.exit_code,
            result.passed,
            result.failed,
            result.log_path,
        ),
    )
