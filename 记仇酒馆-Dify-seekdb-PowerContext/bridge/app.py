"""记仇酒馆 · Bridge Service

职责边界（刻意做薄，把编排留给 Dify）：
  1. seekdb：道具库混合检索（向量 + 全文 + 结构化）、玩家档案、权威状态账本、回合流水。
  2. PowerContext：把每一回合写成长期记忆，并在下一回合/下一次会话召回。
  3. 不在这里写任何剧情或角色台词 —— 台词由 Dify 里的 LLM 节点生成。

对外接口：
  GET  /healthz
  POST /v1/props/search      {user_id, query, scene?, max_danger?, limit?}
  POST /v1/memory/prepare    {user_id, query, max_bytes?}
  POST /v1/memory/commit     {user_id, action, reply, ledger, prop_used, grudge, mood, ending}
  GET  /v1/state/{user_id}
  GET  /v1/turns/{user_id}?limit=10
  POST /v1/reset             {user_id}

启动：
  uvicorn app:app --host 0.0.0.0 --port 8099
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

import httpx
import pymysql
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("tavern-bridge")

try:  # 本地开发时允许用 bridge/.env 提供配置；生产环境请直接用环境变量
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # noqa: BLE001
    pass

# ----------------------------------------------------------------------------
# 配置
# ----------------------------------------------------------------------------
SEEKDB = dict(
    host=os.getenv("SEEKDB_HOST", "127.0.0.1"),
    port=int(os.getenv("SEEKDB_PORT", "2881")),
    user=os.getenv("SEEKDB_USER", "root"),
    password=os.getenv("SEEKDB_PASSWORD", ""),
    database=os.getenv("SEEKDB_DATABASE", "tavern"),
    charset="utf8mb4",
    autocommit=True,
    cursorclass=pymysql.cursors.DictCursor,
)

POWERCONTEXT_URL = os.getenv("POWERCONTEXT_URL", "http://127.0.0.1:8000").rstrip("/")
POWERCONTEXT_TOKEN = os.getenv("POWERCONTEXT_TOKEN", "")

EMBED_BASE_URL = os.getenv("EMBED_BASE_URL", "").rstrip("/")
EMBED_API_KEY = os.getenv("EMBED_API_KEY", "")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-v3")
EMBED_DIM = int(os.getenv("EMBED_DIM", "1024"))

PROP_TABLE = "props"
DEFAULT_MAX_BYTES = 2000

app = FastAPI(title="Grudge Tavern Bridge", version="1.0.0")


# ----------------------------------------------------------------------------
# 基础工具
# ----------------------------------------------------------------------------
def db() -> pymysql.connections.Connection:
    return pymysql.connect(**SEEKDB)


def query_all(sql: str, args: tuple = ()) -> list[dict[str, Any]]:
    with db() as conn, conn.cursor() as cur:
        cur.execute(sql, args)
        return list(cur.fetchall())


def query_one(sql: str, args: tuple = ()) -> dict[str, Any] | None:
    rows = query_all(sql, args)
    return rows[0] if rows else None


def execute(sql: str, args: tuple = ()) -> int:
    with db() as conn, conn.cursor() as cur:
        return cur.execute(sql, args)


def embed(text: str) -> list[float] | None:
    """调用 OpenAI 兼容 Embedding 接口；失败返回 None，检索自动降级为全文模式。"""
    if not EMBED_BASE_URL or not EMBED_MODEL:
        return None
    payload: dict[str, Any] = {"model": EMBED_MODEL, "input": [text]}
    if EMBED_DIM:
        payload["dimensions"] = EMBED_DIM
    headers = {"Content-Type": "application/json"}
    if EMBED_API_KEY:
        headers["Authorization"] = f"Bearer {EMBED_API_KEY}"
    try:
        with httpx.Client(timeout=20) as client:
            resp = client.post(f"{EMBED_BASE_URL}/embeddings", json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()["data"][0]["embedding"]
    except Exception as exc:  # noqa: BLE001
        log.warning("embedding unavailable, fallback to fulltext: %s", exc)
        return None


def pc_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if POWERCONTEXT_TOKEN:
        headers["Authorization"] = f"Bearer {POWERCONTEXT_TOKEN}"
    return headers


def pc_post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    with httpx.Client(timeout=12) as client:
        resp = client.post(f"{POWERCONTEXT_URL}{path}", json=payload, headers=pc_headers())
        resp.raise_for_status()
        return resp.json()


def pc_create_scope(user_id: str, generation: int = 1) -> str:
    key = f"tavern-{user_id}" + ("" if generation == 1 else f"-g{generation}")
    data = pc_post(
        "/v1/scopes",
        {
            "title": key,
            "summary": f"记仇酒馆：玩家 {user_id} 的恶作剧、老陈的反应与记仇账",
            "idempotency_key": key,
        },
    )
    return str(data["scope_id"])


def pc_prepare(scope_id: str, text: str, max_bytes: int) -> str:
    data = pc_post(
        "/v1/context/prepare",
        {"scope_id": scope_id, "query": text, "max_bytes": max_bytes},
    )
    return str(data.get("content") or "")


def pc_remember(scope_id: str, text: str, kind: str = "fact") -> None:
    payload = {
        "scope_id": scope_id,
        "kind": kind,
        "text": text,
        "reason": "记仇酒馆 · 回合结算",
    }
    try:
        pc_post("/v1/memory/remember", payload)
    except httpx.HTTPStatusError as exc:
        # 不同版本的 Memory kind 枚举可能不同，4xx 时退回最通用的 decision
        if exc.response.status_code in (400, 404, 422):
            log.warning("memory kind=%s 被拒绝，改用 decision 重试", kind)
            payload["kind"] = "decision"
            pc_post("/v1/memory/remember", payload)
        else:
            raise


# ----------------------------------------------------------------------------
# 玩家 / 状态
# ----------------------------------------------------------------------------
def get_state(user_id: str) -> dict[str, Any]:
    row = query_one(
        "SELECT grudge, mood, turn_no, ending FROM player_state WHERE user_id = %s",
        (user_id,),
    )
    if row:
        return {
            "grudge": int(row["grudge"]),
            "mood": int(row["mood"]),
            "turn_no": int(row["turn_no"]),
            "ending": bool(row["ending"]),
        }
    execute("INSERT IGNORE INTO player_state (user_id) VALUES (%s)", (user_id,))
    return {"grudge": 0, "mood": 60, "turn_no": 0, "ending": False}


def get_player(user_id: str) -> dict[str, Any]:
    row = query_one(
        "SELECT scope_id, scope_generation FROM players WHERE user_id = %s", (user_id,)
    )
    if row:
        return row
    execute("INSERT IGNORE INTO players (user_id) VALUES (%s)", (user_id,))
    execute("INSERT IGNORE INTO player_state (user_id) VALUES (%s)", (user_id,))
    return {"scope_id": "", "scope_generation": 1}


def ensure_scope(user_id: str) -> tuple[str, bool]:
    """确保玩家有 PowerContext scope；失败不阻塞游戏，只让记忆功能降级。"""
    player = get_player(user_id)
    if player["scope_id"]:
        return str(player["scope_id"]), True
    try:
        scope_id = pc_create_scope(user_id, int(player["scope_generation"]))
    except Exception as exc:  # noqa: BLE001
        log.warning("PowerContext scope 创建失败（记忆降级）：%s", exc)
        return "", False
    execute("UPDATE players SET scope_id = %s WHERE user_id = %s", (scope_id, user_id))
    return scope_id, True


# ----------------------------------------------------------------------------
# seekdb 检索
# ----------------------------------------------------------------------------
def structured_ids(scene: str | None, max_danger: int | None) -> set[int] | None:
    """结构化条件先落 SQL，得到候选 id 集合；无过滤条件时返回 None。"""
    if scene is None and max_danger is None:
        return None
    sql = "SELECT id FROM props WHERE 1 = 1"
    args: list[Any] = []
    if scene:
        sql += " AND scene = %s"
        args.append(scene)
    if max_danger is not None:
        sql += " AND danger <= %s"
        args.append(int(max_danger))
    return {int(r["id"]) for r in query_all(sql, tuple(args))}


def hybrid_search(text: str, vector: list[float], k: int) -> list[dict[str, Any]]:
    """seekdb DBMS_HYBRID_SEARCH：query_string + knn 一次调用。"""
    params = {
        "query": {
            "query_string": {
                "fields": ["search_text"],
                "query": text,
                "boost": 1.0,
            }
        },
        "knn": {
            "field": "embedding",
            "k": k,
            "query_vector": vector,
            "boost": 1.2,
        },
    }
    with db() as conn, conn.cursor() as cur:
        cur.execute("SET @p = %s", (json.dumps(params, ensure_ascii=False),))
        cur.execute(f"SELECT DBMS_HYBRID_SEARCH.SEARCH('{PROP_TABLE}', @p) AS r")
        raw = cur.fetchone()["r"]
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")
    rows = json.loads(raw) if isinstance(raw, str) else raw
    return list(rows or [])


def fulltext_search(
    text: str, scene: str | None, max_danger: int | None, limit: int
) -> list[dict[str, Any]]:
    """降级路径：全文 + 结构化，不依赖 Embedding。"""
    sql = (
        "SELECT id, name, category, scene, danger, mess, description, tags, "
        "MATCH(search_text) AGAINST (%s) AS _score "
        "FROM props WHERE MATCH(search_text) AGAINST (%s)"
    )
    args: list[Any] = [text, text]
    if scene:
        sql += " AND scene = %s"
        args.append(scene)
    if max_danger is not None:
        sql += " AND danger <= %s"
        args.append(int(max_danger))
    sql += " ORDER BY _score DESC LIMIT %s"
    args.append(limit)
    return query_all(sql, tuple(args))


def search_props(
    text: str,
    scene: str | None = None,
    max_danger: int | None = None,
    limit: int = 6,
) -> dict[str, Any]:
    started = time.perf_counter()
    vector = embed(text)
    allowed = structured_ids(scene, max_danger)

    if allowed is not None and not allowed:
        return {
            "props": [],
            "meta": {
                "mode": "structured-empty",
                "filters": {"scene": scene, "max_danger": max_danger},
                "count": 0,
                "took_ms": int((time.perf_counter() - started) * 1000),
            },
        }

    mode = "hybrid"
    rows: list[dict[str, Any]] = []
    if vector is not None:
        try:
            rows = hybrid_search(text, vector, max(limit * 4, 20))
        except Exception as exc:  # noqa: BLE001
            log.warning("hybrid search failed, fallback: %s", exc)
            rows = fulltext_search(text, None, None, max(limit * 4, 20))
            mode = "fulltext-fallback"
    else:
        rows = fulltext_search(text, None, None, max(limit * 4, 20))
        mode = "fulltext"

    if allowed is not None:
        rows = [r for r in rows if int(r.get("id", -1)) in allowed]

    rows.sort(key=lambda r: float(r.get("_score") or 0), reverse=True)
    picked = []
    for r in rows[:limit]:
        picked.append(
            {
                "id": int(r["id"]),
                "name": r["name"],
                "category": r["category"],
                "scene": r["scene"],
                "danger": int(r["danger"]),
                "mess": int(r["mess"]),
                "description": r["description"],
                "tags": r.get("tags", ""),
                "score": round(float(r.get("_score") or 0), 4),
            }
        )

    meta = {
        "mode": mode,
        "filters": {"scene": scene, "max_danger": max_danger},
        "count": len(picked),
        "took_ms": int((time.perf_counter() - started) * 1000),
    }
    log.info("props.search mode=%s filters=%s hits=%s", mode, meta["filters"], len(picked))
    return {"props": picked, "meta": meta}


def pick_revenge(grudge: int) -> dict[str, Any] | None:
    """按记仇区间结构化筛选剧本，再随机挑一条——老陈的报复是有据可查的。"""
    row = query_one(
        "SELECT title, plan, prop_hint FROM revenge_plans "
        "WHERE band_min <= %s AND band_max >= %s ORDER BY RAND() LIMIT 1",
        (grudge, grudge),
    )
    if not row:
        return None
    return {"title": row["title"], "plan": row["plan"], "prop_hint": row["prop_hint"]}


# ----------------------------------------------------------------------------
# 请求模型
# ----------------------------------------------------------------------------
class SearchReq(BaseModel):
    user_id: str = "demo-user"
    query: str = Field(min_length=1)
    scene: str | None = None
    max_danger: int | None = None
    limit: int = 6


class PrepareReq(BaseModel):
    user_id: str = "demo-user"
    query: str = Field(min_length=1)
    max_bytes: int = DEFAULT_MAX_BYTES


class CommitReq(BaseModel):
    user_id: str = "demo-user"
    action: str = ""
    reply: str = ""
    ledger: str = ""
    prop_used: str = ""
    grudge: int = 0
    mood: int = 60
    ending: str = "no"


class ResetReq(BaseModel):
    user_id: str = "demo-user"


# ----------------------------------------------------------------------------
# 路由
# ----------------------------------------------------------------------------
@app.get("/healthz")
def healthz() -> dict[str, Any]:
    seekdb_ok, seekdb_err = True, ""
    try:
        query_one("SELECT 1 AS ok")
    except Exception as exc:  # noqa: BLE001
        seekdb_ok, seekdb_err = False, str(exc)

    pc_ok = True
    try:
        with httpx.Client(timeout=3) as client:
            client.get(f"{POWERCONTEXT_URL}/health/live")
    except Exception:  # noqa: BLE001
        pc_ok = False

    return {
        "ok": seekdb_ok,
        "seekdb": {"ok": seekdb_ok, "error": seekdb_err},
        "powercontext": {"ok": pc_ok, "url": POWERCONTEXT_URL},
        "embedding": {
            "configured": bool(EMBED_BASE_URL),
            "model": EMBED_MODEL,
            "dim": EMBED_DIM,
        },
    }


@app.post("/v1/props/search")
def api_props_search(req: SearchReq) -> dict[str, Any]:
    result = search_props(req.query, req.scene, req.max_danger, max(1, min(req.limit, 12)))
    result["user_id"] = req.user_id
    return result


@app.post("/v1/memory/prepare")
def api_memory_prepare(req: PrepareReq) -> dict[str, Any]:
    user_id = req.user_id
    state = get_state(user_id)
    scope_id, pc_ok = ensure_scope(user_id)

    context = ""
    if scope_id:
        try:
            context = pc_prepare(scope_id, req.query, req.max_bytes)
        except Exception as exc:  # noqa: BLE001
            log.warning("PowerContext prepare 失败（降级为无记忆）：%s", exc)

    revenge = None
    if state["grudge"] >= 60 and not state["ending"]:
        revenge = pick_revenge(state["grudge"])

    return {
        "state": state,
        "context": context,
        "memory_hits": 1 if context else 0,
        "revenge_hint": revenge,
        "scope_id": scope_id,
        "powercontext_ok": pc_ok,
    }


@app.post("/v1/memory/commit")
def api_memory_commit(req: CommitReq) -> dict[str, Any]:
    user_id = req.user_id
    state = get_state(user_id)
    turn_no = state["turn_no"] + 1

    grudge = max(0, min(100, int(req.grudge)))
    mood = max(0, min(100, int(req.mood)))
    ending = 1 if (grudge >= 100 or req.ending == "yes") else 0

    execute(
        "UPDATE player_state SET grudge = %s, mood = %s, turn_no = %s, ending = %s "
        "WHERE user_id = %s",
        (grudge, mood, turn_no, ending, user_id),
    )
    execute(
        "INSERT INTO turn_log "
        "(user_id, turn_no, action, reply, ledger, prop_used, grudge_after, mood_after, ending) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (
            user_id, turn_no, req.action[:1000], req.reply[:2000], req.ledger[:250],
            req.prop_used[:64], grudge, mood, ending,
        ),
    )

    warnings: list[str] = []
    memory_saved = False
    scope_id, pc_ok = ensure_scope(user_id)
    if scope_id:
        memory = (
            f"第{turn_no}回合｜玩家做了：{req.action[:200]}｜"
            f"老陈的反应：{req.reply[:200]}｜记在账上：{req.ledger}｜"
            f"记仇值 {grudge}/100，心情 {mood}/100"
        )
        try:
            pc_remember(scope_id, memory, kind="fact")
            memory_saved = True
        except Exception as exc:  # noqa: BLE001
            log.warning("PowerContext remember 失败：%s", exc)
            warnings.append("PowerContext 写入失败，本回合记忆未保存")
    else:
        warnings.append("PowerContext 不可用，记忆功能已降级")

    if ending:
        try:
            if scope_id:
                pc_remember(
                    scope_id,
                    f"结局触发：第{turn_no}回合，记仇值达到 {grudge}，老陈执行了「打烊后的清算」。",
                    kind="state",
                )
        except Exception:  # noqa: BLE001
            pass

    return {
        "ok": True,
        "turn_no": turn_no,
        "grudge": grudge,
        "mood": mood,
        "ending": bool(ending),
        "memory_saved": memory_saved,
        "powercontext_ok": pc_ok,
        "warnings": warnings,
    }


@app.get("/v1/state/{user_id}")
def api_state(user_id: str) -> dict[str, Any]:
    return {"user_id": user_id, "state": get_state(user_id), "player": get_player(user_id)}


@app.get("/v1/turns/{user_id}")
def api_turns(user_id: str, limit: int = 10) -> dict[str, Any]:
    rows = query_all(
        "SELECT turn_no, action, ledger, prop_used, grudge_after, mood_after, created_at "
        "FROM turn_log WHERE user_id = %s ORDER BY turn_no DESC LIMIT %s",
        (user_id, max(1, min(limit, 50))),
    )
    return {"user_id": user_id, "turns": rows}


@app.post("/v1/reset")
def api_reset(req: ResetReq) -> dict[str, Any]:
    user_id = req.user_id
    player = get_player(user_id)
    generation = int(player["scope_generation"]) + 1

    scope_id = ""
    try:
        scope_id = pc_create_scope(user_id, generation)
        execute(
            "UPDATE players SET scope_id = %s, scope_generation = %s WHERE user_id = %s",
            (scope_id, generation, user_id),
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("重置时创建新 scope 失败：%s", exc)

    execute("DELETE FROM turn_log WHERE user_id = %s", (user_id,))
    execute(
        "UPDATE player_state SET grudge = 0, mood = 60, turn_no = 0, ending = 0 WHERE user_id = %s",
        (user_id,),
    )
    execute("INSERT IGNORE INTO player_state (user_id) VALUES (%s)", (user_id,))

    return {
        "ok": True,
        "user_id": user_id,
        "scope_id": scope_id,
        "scope_generation": generation,
        "state": get_state(user_id),
    }


@app.exception_handler(Exception)
def unhandled(_request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled error: %s", exc)
    return JSONResponse(status_code=500, content={"ok": False, "detail": str(exc)})
