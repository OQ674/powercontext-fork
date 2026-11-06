"""把 seed/*.json 写入 seekdb，并为每条素材生成 1024 维向量。

依赖：
    pip install -r bridge/requirements.txt

用法：
    # 1) 用真实 Embedding 服务（推荐）
    set EMBED_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
    set EMBED_API_KEY=sk-xxx
    python seed/load_seed.py

    # 2) 没有 Embedding Key 时，只灌数据、不写向量（检索自动降级为全文+结构化）
    python seed/load_seed.py --skip-embed

说明：
    - 向量维度由 EMBED_DIM 控制，默认 1024，必须与 seed/00_schema.sql 中 VECTOR(1024) 一致。
    - 脚本可重复执行：每次先清空 props / revenge_plans 再写入。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx
import pymysql

ROOT = Path(__file__).resolve().parent.parent
SEED_DIR = ROOT / "seed"

SEEKDB = dict(
    host=os.getenv("SEEKDB_HOST", "127.0.0.1"),
    port=int(os.getenv("SEEKDB_PORT", "2881")),
    user=os.getenv("SEEKDB_USER", "root"),
    password=os.getenv("SEEKDB_PASSWORD", ""),
    database=os.getenv("SEEKDB_DATABASE", "tavern"),
    charset="utf8mb4",
    autocommit=True,
)

EMBED_BASE_URL = os.getenv("EMBED_BASE_URL", "").rstrip("/")
EMBED_API_KEY = os.getenv("EMBED_API_KEY", "")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-v3")
EMBED_DIM = int(os.getenv("EMBED_DIM", "1024"))


def embed_batch(texts: list[str]) -> list[list[float]]:
    """调用 OpenAI 兼容的 /embeddings 接口。"""
    base_payload: dict = {"model": EMBED_MODEL, "input": texts}
    headers = {"Content-Type": "application/json"}
    if EMBED_API_KEY:
        headers["Authorization"] = f"Bearer {EMBED_API_KEY}"

    with httpx.Client(timeout=60) as client:
        payload = dict(base_payload)
        if EMBED_DIM:
            payload["dimensions"] = EMBED_DIM
        resp = client.post(f"{EMBED_BASE_URL}/embeddings", json=payload, headers=headers)
        if resp.status_code >= 400 and "dimensions" in payload:
            # 部分兼容服务不支持 dimensions 参数，退回默认维度再试一次
            print("[embed] 服务不接受 dimensions 参数，改用模型默认维度")
            resp = client.post(f"{EMBED_BASE_URL}/embeddings", json=base_payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()["data"]

    data = sorted(data, key=lambda item: item.get("index", 0))
    vectors = [item["embedding"] for item in data]
    for vec in vectors:
        if len(vec) != EMBED_DIM:
            raise SystemExit(
                f"向量维度 {len(vec)} 与 EMBED_DIM={EMBED_DIM} 不一致。"
                f"请把 EMBED_DIM 改成 {len(vec)} 并同步修改 seed/00_schema.sql 的 VECTOR 维度后重建表。"
            )
    return vectors


def vec_literal(vec: list[float] | None) -> str | None:
    if not vec:
        return None
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-embed", action="store_true", help="跳过向量生成，仅灌结构化+全文数据")
    parser.add_argument("--embed-batch", type=int, default=8)
    args = parser.parse_args()

    use_embed = not args.skip_embed
    if use_embed and not EMBED_BASE_URL:
        raise SystemExit("未配置 EMBED_BASE_URL。请配置 Embedding 服务，或加 --skip-embed 降级运行。")

    props = json.loads((SEED_DIR / "props.json").read_text(encoding="utf-8"))
    plans = json.loads((SEED_DIR / "revenge_plans.json").read_text(encoding="utf-8"))

    prop_texts = [
        f"{p['name']} {p['category']} {p['description']} {p['tags']}" for p in props
    ]
    plan_texts = [
        f"{r['title']} {r['plan']} {r['prop_hint']} {r['tags']}" for r in plans
    ]

    prop_vecs: list[list[float] | None] = [None] * len(props)
    plan_vecs: list[list[float] | None] = [None] * len(plans)

    if use_embed:
        print(f"[embed] model={EMBED_MODEL} dim={EMBED_DIM} props={len(props)} plans={len(plans)}")
        for start in range(0, len(props), args.embed_batch):
            chunk = prop_texts[start : start + args.embed_batch]
            prop_vecs[start : start + len(chunk)] = embed_batch(chunk)
        for start in range(0, len(plans), args.embed_batch):
            chunk = plan_texts[start : start + args.embed_batch]
            plan_vecs[start : start + len(chunk)] = embed_batch(chunk)
        print("[embed] ok")
    else:
        print("[embed] skipped —— 检索将自动降级为『全文 + 结构化』模式")

    conn = pymysql.connect(**SEEKDB, cursorclass=pymysql.cursors.DictCursor)
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM props")
            cur.execute("DELETE FROM revenge_plans")
            cur.executemany(
                """
                INSERT INTO props
                    (id, name, category, scene, danger, mess, description, tags, search_text, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    (
                        p["id"], p["name"], p["category"], p["scene"], p["danger"],
                        p["mess"], p["description"], p["tags"], text, vec_literal(vec),
                    )
                    for p, text, vec in zip(props, prop_texts, prop_vecs)
                ],
            )
            cur.executemany(
                """
                INSERT INTO revenge_plans
                    (id, band_min, band_max, title, plan, prop_hint, tags, search_text, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    (
                        r["id"], r["band_min"], r["band_max"], r["title"], r["plan"],
                        r["prop_hint"], r["tags"], text, vec_literal(vec),
                    )
                    for r, text, vec in zip(plans, plan_texts, plan_vecs)
                ],
            )
            cur.execute("SELECT COUNT(*) AS n FROM props")
            n_props = cur.fetchone()["n"]
            cur.execute("SELECT COUNT(*) AS n FROM revenge_plans")
            n_plans = cur.fetchone()["n"]
        print(f"[seekdb] props={n_props} revenge_plans={n_plans}")

        if use_embed:
            smoke_query = "黏糊糊、甜得拉丝的东西"
            with conn.cursor() as cur:
                vec = embed_batch([smoke_query])[0]
                param = json.dumps(
                    {"knn": {"field": "embedding", "k": 3, "query_vector": vec}},
                    ensure_ascii=False,
                )
                cur.execute("SET @p = %s", (param,))
                cur.execute("SELECT DBMS_HYBRID_SEARCH.SEARCH('props', @p) AS r")
                rows = cur.fetchone()["r"]
                if isinstance(rows, (bytes, bytearray)):
                    rows = rows.decode("utf-8")
                hits = json.loads(rows) if isinstance(rows, str) else rows
            print(f"[selftest] query={smoke_query!r}")
            for hit in hits[:3]:
                print(f"  - {hit.get('name')}  score={hit.get('_score')}")
    finally:
        conn.close()

    print("[done] 数据就绪。下一步：启动 bridge，再导入 Dify DSL。")


if __name__ == "__main__":
    try:
        main()
    except pymysql.MySQLError as exc:  # noqa: PERF203
        print(f"[error] seekdb 连接/写入失败：{exc}", file=sys.stderr)
        raise SystemExit(1) from exc
