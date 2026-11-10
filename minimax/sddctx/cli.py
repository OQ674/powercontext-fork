"""命令行入口。

典型用法（完整流程见 ``docs/RUNBOOK.md``）::

    python -m sddctx db-init
    python -m sddctx import --kind all
    python -m sddctx context --task-id TASK-001 --title "为订单查询增加金额区间筛选" \\
        --description "..." --out artifacts/context_before.json
    python -m sddctx state-save --task-id TASK-001 --done "导入规格" --todo "实现筛选"
    python -m sddctx state-show --task-id TASK-001
    python -m sddctx agent-patch --task-id TASK-001 --context artifacts/context_before.json \\
        --patch-file artifacts/minimax_patch.diff --apply
    python -m sddctx verify --task-id TASK-001 --phase before --target tests/test_feature_amount_filter.py
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Sequence

from . import __version__
from .agent import MiniMaxAgent, MiniMaxError, extract_diff, normalize_prompt
from .config import Config, load_config
from .context import build_context_bundle, dump_json
from .db import Database, open_database
from .importer import import_code, import_specs, import_tests
from .patcher import apply_unified_diff, make_unified_diff
from .powercontext_client import PowerContextClient, PowerContextError
from .schema import apply_schema
from .state import TaskStateStore
from .verify import record_verification, run_pytest


# ----------------------------------------------------------------------
# 公共辅助
# ----------------------------------------------------------------------
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sddctx",
        description="面向软件持续演进的 SDD 上下文管理模块",
    )
    parser.add_argument("--version", action="version", version=f"sddctx {__version__}")
    parser.add_argument("--config", type=Path, help="配置文件（KEY=VALUE 形式）")
    parser.add_argument("--project-root", type=Path, help="工程根目录（默认取当前目录的 minimax/）")
    parser.add_argument("--sample-project", type=Path, help="业务工程目录（默认 <root>/sample_project）")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出结果")

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("db-init", help="初始化数据库表结构")

    importer = sub.add_parser("import", help="导入规格 / 代码 / 测试")
    importer.add_argument("--kind", choices=["specs", "code", "tests", "all"], default="all")
    importer.add_argument("--specs-dir", type=Path)
    importer.add_argument("--root", type=Path)

    context_cmd = sub.add_parser("context", help="根据任务生成上下文包")
    context_cmd.add_argument("--task-id", required=True)
    context_cmd.add_argument("--title", required=True)
    context_cmd.add_argument("--description", default="")
    context_cmd.add_argument("--out", type=Path, help="输出 JSON 文件")
    context_cmd.add_argument("--markdown-out", type=Path, help="输出 Markdown 文件")
    context_cmd.add_argument("--include-state", action="store_true", help="带上 PowerContext 中的历史状态")

    state_save = sub.add_parser("state-save", help="保存任务状态到 PowerContext")
    state_save.add_argument("--task-id", required=True)
    state_save.add_argument("--done", action="append", default=[])
    state_save.add_argument("--todo", action="append", default=[])
    state_save.add_argument("--note", action="append", default=[])
    state_save.add_argument("--verification", action="append", default=[])

    state_show = sub.add_parser("state-show", help="读取任务状态（优先 PowerContext）")
    state_show.add_argument("--task-id", required=True)

    agent_cmd = sub.add_parser("agent-patch", help="调用 MiniMax 生成并应用补丁")
    agent_cmd.add_argument("--task-id", required=True)
    agent_cmd.add_argument("--context", type=Path, help="上下文 JSON 文件")
    agent_cmd.add_argument("--patch-file", type=Path, help="离线回放用的补丁文件")
    agent_cmd.add_argument("--apply", action="store_true", help="把补丁应用到业务工程")
    agent_cmd.add_argument("--save-patch", type=Path, help="把生成的补丁保存到该文件")

    verify_cmd = sub.add_parser("verify", help="执行功能与回归测试")
    verify_cmd.add_argument("--task-id", required=True)
    verify_cmd.add_argument("--phase", required=True)
    verify_cmd.add_argument("--target", action="append", default=[])
    verify_cmd.add_argument("--log", type=Path)

    prompt_cmd = sub.add_parser("prompt", help="根据上下文包生成 MiniMax 提示词")
    prompt_cmd.add_argument("--context", type=Path, required=True)
    prompt_cmd.add_argument("--out", type=Path, help="提示词文本输出路径")
    prompt_cmd.add_argument("--meta-out", type=Path, help="提示词元信息（JSON）输出路径")
    prompt_cmd.add_argument("--model", default="MiniMax-M3.1-Flash")

    state_log = sub.add_parser("state-log", help="导出 PowerContext 任务状态记录（Markdown）")
    state_log.add_argument("--task-id", required=True)
    state_log.add_argument("--out", type=Path)

    evidence = sub.add_parser("evidence", help="导出数据库查询与检索记录")
    evidence.add_argument("--out", type=Path)

    doctor = sub.add_parser("doctor", help="检查依赖与外部服务状态")
    doctor.add_argument("--task-id", default="")

    return parser


def _resolve_paths(args) -> tuple[Path, Path]:
    project_root = args.project_root
    if project_root is None:
        here = Path(__file__).resolve().parent
        project_root = here.parent if (here.parent / "sample_project").exists() else Path.cwd()
    project_root = project_root.resolve()
    sample_project = args.sample_project or (project_root / "sample_project")
    return project_root, sample_project.resolve()


def _config(args) -> Config:
    project_root, _ = _resolve_paths(args)
    return load_config(project_root, args.config)


def _print(payload, args) -> None:
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for key, value in payload.items():
            print(f"{key}: {value}")


# ----------------------------------------------------------------------
# 子命令实现
# ----------------------------------------------------------------------
def cmd_db_init(args, config: Config) -> int:
    with open_database(config) as database:
        statements = apply_schema(database)
        payload = {
            "database": database.describe(),
            "tables": len(statements),
            "schema": statements,
        }
    _print(payload, args)
    return 0


def cmd_import(args, config: Config) -> int:
    project_root, sample_project = _resolve_paths(args)
    specs_dir = args.specs_dir or (sample_project / "specs")
    root = args.root or sample_project
    payload: dict = {}
    with open_database(config) as database:
        if args.kind in {"specs", "all"}:
            payload["specs"] = import_specs(database, specs_dir, project_root)
        if args.kind in {"code", "all"}:
            payload["code"] = import_code(database, root)
        if args.kind in {"tests", "all"}:
            payload["tests"] = import_tests(database, root)
    _print(payload, args)
    return 0


def cmd_context(args, config: Config) -> int:
    state = None
    if args.include_state:
        client = _client(config)
        store = TaskStateStore(_DummyDatabase(), config, client)
        state = store.load(args.task_id)
    with open_database(config) as database:
        bundle = build_context_bundle(
            database,
            args.task_id,
            args.title,
            args.description,
            state=state,
        )
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(dump_json(bundle), encoding="utf-8")
    if args.markdown_out:
        args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_out.write_text(bundle["markdown"], encoding="utf-8")
    summary = {
        "task_id": args.task_id,
        "specs": len(bundle["specs"]),
        "code": len(bundle["code"]),
        "tests": len(bundle["tests"]),
        "citations": len(bundle["citations"]),
        "state_origin": (bundle.get("task_state") or {}).get("origin", ""),
        "out": str(args.out) if args.out else "",
    }
    _print(summary, args)
    return 0


def cmd_state_save(args, config: Config) -> int:
    client = _client(config)
    entries: List[tuple] = []
    entries.extend(("done", item) for item in args.done)
    entries.extend(("todo", item) for item in args.todo)
    entries.extend(("note", item) for item in args.note)
    entries.extend(("verification", item) for item in args.verification)
    with open_database(config) as database:
        store = TaskStateStore(database, config, client)
        payload = store.save(args.task_id, entries)
    _print(payload, args)
    return 0


def cmd_state_show(args, config: Config) -> int:
    client = _client(config)
    with open_database(config) as database:
        store = TaskStateStore(database, config, client)
        state = store.load(args.task_id)
    _print(state.to_dict(), args)
    return 0


def cmd_agent_patch(args, config: Config) -> int:
    project_root, sample_project = _resolve_paths(args)
    agent = MiniMaxAgent(config)
    prompt = ""
    bundle: dict = {}
    if args.context and args.context.exists():
        bundle = json.loads(args.context.read_text(encoding="utf-8"))
        prompt = agent.build_prompt(bundle.get("markdown", ""))

    if agent.online:
        record = agent.request_patch(prompt)
    else:
        patch_file = args.patch_file or (project_root / "artifacts" / "minimax_patch.diff")
        record = agent.replay_patch(patch_file)
        prompt = record.get("prompt") or prompt

    diff_text = extract_diff(record.get("response", ""))
    recorded_prompt = str(record.get("prompt") or "")
    prompt_matches_context = None
    if recorded_prompt and prompt:
        prompt_matches_context = (
            normalize_prompt(recorded_prompt) == normalize_prompt(prompt)
        )
    save_path = args.save_patch or (project_root / "artifacts" / "minimax_patch.diff")
    save_path.parent.mkdir(parents=True, exist_ok=True)
    save_path.write_text(diff_text, encoding="utf-8")

    applied = None
    already_applied = False
    if args.apply:
        applied = apply_unified_diff(diff_text, sample_project)
        already_applied = bool(applied.get("skipped_files")) and not applied.get("changed_files")

    agent.write_dev_log(
        project_root / "artifacts" / "minimax_dev_log.jsonl",
        {
            "task_id": args.task_id,
            "stage": "code_generation",
            "mode": record.get("mode"),
            "model": record.get("model"),
            "context_file": str(args.context) if args.context else "",
            "context_sources": [c.get("ref") for c in bundle.get("citations", [])],
            "prompt": prompt,
            "response": diff_text,
            "recorded_prompt_matches_context": prompt_matches_context,
            "applied": bool(args.apply),
            "applied_files": applied["changed_files"] if applied else [],
            "skipped_files": applied.get("skipped_files", []) if applied else [],
            "already_applied": already_applied,
            "usage": record.get("usage", {}),
        },
    )

    payload = {
        "mode": record.get("mode"),
        "model": record.get("model"),
        "patch_file": str(save_path),
        "applied": applied,
    }
    _print(payload, args)
    return 0


def cmd_verify(args, config: Config) -> int:
    project_root, sample_project = _resolve_paths(args)
    targets = args.target or ["tests"]
    log_path = args.log or (project_root / "logs" / f"pytest_{args.phase}_{args.task_id}.log")
    result = run_pytest(sample_project, targets, log_path)
    with open_database(config) as database:
        record_verification(database, args.task_id, args.phase, result)
    _print(result.to_dict(), args)
    return 0 if result.exit_code == 0 else 1


def cmd_prompt(args, config: Config) -> int:
    """生成 MiniMax 提示词，并写出可回放的元信息。"""

    project_root, _ = _resolve_paths(args)
    bundle = json.loads(args.context.read_text(encoding="utf-8"))
    agent = MiniMaxAgent(config)
    prompt = agent.build_prompt(bundle.get("markdown", ""))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(prompt, encoding="utf-8")
    meta = {
        "model": args.model,
        "prompt": prompt,
        "context_file": str(args.context),
        "citations": [item.get("ref") for item in bundle.get("citations", [])],
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    if args.meta_out:
        args.meta_out.parent.mkdir(parents=True, exist_ok=True)
        args.meta_out.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    _print({"prompt_chars": len(prompt), "out": str(args.out) if args.out else ""}, args)
    return 0


def cmd_state_log(args, config: Config) -> int:
    """导出 PowerContext 中的任务状态记录，作为"状态能够复用"的证据。"""

    project_root, _ = _resolve_paths(args)
    out_path = args.out or (project_root / "artifacts" / "powercontext_state_log.md")
    client = _client(config)
    scope_id = client.ensure_scope(
        scope_title=config.powercontext_scope,
        summary="SDD 上下文模块：任务状态与验证结果",
        idempotency_key=f"sddctx-{config.powercontext_scope}",
    )
    items = client.list_memories(scope_id)
    raw = []
    for item in items:
        raw.append(
            {
                "artifact": item.get("artifact"),
                "kind": item.get("kind"),
                "state": item.get("state"),
                "text": item.get("text"),
            }
        )
    try:
        search = client.search_memories(scope_id, args.task_id, limit=20)
        search_summary = {
            "mode": search.get("mode"),
            "hits": len(search.get("hits", [])),
        }
    except PowerContextError as exc:
        search_summary = {"error": str(exc)}

    with open_database(config) as database:
        store = TaskStateStore(database, config, client)
        state = store.load(args.task_id)

    lines = [
        "# PowerContext 任务状态记录（状态保存与复用的证据）",
        "",
        f"- PowerContext 地址：`{config.powercontext_url}`",
        f"- Scope 标题：`{config.powercontext_scope}`",
        f"- Scope ID：`{scope_id}`",
        f"- 任务 ID：`{args.task_id}`",
        f"- 读取时间：{datetime.now().isoformat(timespec='seconds')}",
        "",
        "## 一、Scope 下的全部记忆条目（原始返回）",
        "",
        "```json",
        json.dumps(raw, ensure_ascii=False, indent=2),
        "```",
        "",
        "## 二、按任务 ID 检索",
        "",
        "```json",
        json.dumps(search_summary, ensure_ascii=False, indent=2),
        "```",
        "",
        "## 三、模块解析出的任务状态",
        "",
        "```json",
        json.dumps(state.to_dict(), ensure_ascii=False, indent=2),
        "```",
        "",
        f"- 状态来源：`{state.origin}`",
        "",
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    _print({"state_log": str(out_path), "scope_id": scope_id, "entries": len(items)}, args)
    return 0


def cmd_evidence(args, config: Config) -> int:
    project_root, _ = _resolve_paths(args)
    out_path = args.out or (project_root / "logs" / "db_query_log.md")
    with open_database(config) as database:
        queries = database.query(
            "SELECT id, session_id, seq, sql_text, row_count, duration_ms, created_at"
            " FROM sdd_query_log ORDER BY id ASC"
        )
        retrievals = database.query(
            "SELECT id, task_id, target_kind, item_ref, score, sql_text, created_at"
            " FROM sdd_retrieval_log ORDER BY id ASC"
        )
        verifications = database.query(
            "SELECT id, task_id, phase, command, exit_code, passed, failed, log_path, created_at"
            " FROM sdd_verification ORDER BY id ASC"
        )
    lines: List[str] = ["# seekdb 查询记录（数据库实际参与证据）", ""]
    lines.append(f"共 {len(queries)} 条 SQL，{len(retrievals)} 条检索命中，{len(verifications)} 条测试记录。")
    lines.append("")
    lines.append("## 一、SQL 执行记录")
    lines.append("")
    lines.append("| # | session | SQL | 影响行数 | 耗时(ms) |")
    lines.append("| --- | --- | --- | --- | --- |")
    for row in queries:
        sql = " ".join(str(row["sql_text"]).split())
        lines.append(f"| {row['id']} | {row['session_id']} | `{sql[:160]}` | {row['row_count']} | {row['duration_ms']} |")
    lines.append("")
    lines.append("## 二、上下文召回记录")
    lines.append("")
    lines.append("| # | 任务 | 类型 | 命中项 | 分数 |")
    lines.append("| --- | --- | --- | --- | --- |")
    for row in retrievals:
        lines.append(f"| {row['id']} | {row['task_id']} | {row['target_kind']} | `{row['item_ref']}` | {row['score']} |")
    lines.append("")
    lines.append("## 三、测试执行记录")
    lines.append("")
    lines.append("| # | 任务 | 阶段 | 命令 | 退出码 | 通过 | 失败 | 日志 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for row in verifications:
        lines.append(
            f"| {row['id']} | {row['task_id']} | {row['phase']} | `{row['command']}` | "
            f"{row['exit_code']} | {row['passed']} | {row['failed']} | `{row['log_path']}` |"
        )
    lines.append("")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    _print({"evidence": str(out_path), "queries": len(queries), "retrievals": len(retrievals)}, args)
    return 0


def cmd_doctor(args, config: Config) -> int:
    payload: dict = {"config": {
        "db_mode": config.db_mode,
        "db_dir": str(config.db_dir),
        "db_name": config.db_name,
        "powercontext_url": config.powercontext_url,
        "minimax_online": bool(config.minimax_api_key),
    }}
    try:
        with open_database(config) as database:
            payload["database"] = database.describe()
            payload["database"]["reachable"] = True
    except Exception as exc:  # pragma: no cover
        payload["database"] = {"reachable": False, "error": str(exc)}
    client = _client(config)
    try:
        payload["powercontext"] = {"reachable": True, "ready": client.ready()}
    except PowerContextError as exc:
        payload["powercontext"] = {"reachable": False, "error": str(exc)}
    _print(payload, args)
    return 0


class _DummyDatabase:
    """只读占位，用于在未连接数据库时读取 PowerContext 状态。"""

    def query(self, *args, **kwargs):  # pragma: no cover - 未使用
        return []


def _client(config: Config) -> PowerContextClient:
    return PowerContextClient(config.powercontext_url)


# ----------------------------------------------------------------------
def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    config = _config(args)

    handlers = {
        "db-init": cmd_db_init,
        "import": cmd_import,
        "context": cmd_context,
        "state-save": cmd_state_save,
        "state-show": cmd_state_show,
        "state-log": cmd_state_log,
        "agent-patch": cmd_agent_patch,
        "prompt": cmd_prompt,
        "verify": cmd_verify,
        "evidence": cmd_evidence,
        "doctor": cmd_doctor,
    }
    handler = handlers[args.command]
    try:
        return handler(args, config)
    except (PowerContextError, MiniMaxError) as exc:
        print(f"[sddctx] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
