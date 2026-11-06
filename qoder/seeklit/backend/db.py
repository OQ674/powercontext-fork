"""pyseekdb 封装：文献集合的写入与三模式混合检索。"""
import os
import threading

import pyseekdb

DB_PATH = os.environ.get("SEEKLIT_DB_PATH", os.path.expanduser("~/seeklit-data"))
COLLECTION = "papers"

_client = None
_collection = None
_lock = threading.Lock()


def _init():
    global _client, _collection
    with _lock:
        if _collection is not None:
            return _collection
        admin = pyseekdb.AdminClient(path=DB_PATH)
        try:
            admin.create_database("seeklit")
        except Exception:
            pass
        _client = pyseekdb.Client(path=DB_PATH, database="seeklit")
        _collection = _client.get_or_create_collection(name=COLLECTION)
        return _collection


def _reset():
    """长驻进程中 seekdb 内嵌连接可能超时失效（MySQL 2006），重建客户端。"""
    global _client, _collection
    with _lock:
        _client = None
        _collection = None


def _retryable(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "gone away" in msg or "2006" in msg or "lost connection" in msg or "closed" in msg


def _run(fn):
    """执行 seekdb 操作，连接失效时重建一次并重试。"""
    try:
        return fn()
    except Exception as e:
        if _retryable(e):
            _reset()
            return fn()
        raise


def col():
    return _init()


def paper_document(title: str, abstract: str, tags_line: str = "") -> str:
    # WHY: FULLTEXT 索引只覆盖 document 列，而多数中文论文的检索词只出现在 tags
    # （如 缓存/分布式事务）；把标签行追加进文档文本，IK 分词后关键词检索才能命中。
    # display 侧由 main._abstract_from_document 依据 metadata.tags_csv 精确剥离该行。
    doc = f"{title}\n{abstract}"
    return f"{doc}\n{tags_line}" if tags_line else doc


def upsert(items: list[dict]) -> None:
    metas = [_meta(it) for it in items]
    _run(lambda: col().upsert(
        ids=[it["id"] for it in items],
        documents=[paper_document(it["title"], it.get("abstract", ""), m["tags_csv"])
                   for it, m in zip(items, metas)],
        metadatas=metas,
    ))


def _meta(it: dict) -> dict:
    return {
        "title": it.get("title", ""),
        "authors": it.get("authors", ""),
        "year": int(it.get("year", 0)),
        "venue": it.get("venue", ""),
        "tags_csv": ",".join(it.get("tags", [])) if isinstance(it.get("tags"), list) else str(it.get("tags", "")),
        "language": it.get("language", "zh"),
        "url": it.get("url", ""),
        "is_sample": bool(it.get("is_sample", False)),
    }


def delete(ids: list[str]) -> None:
    _run(lambda: col().delete(ids=ids))


def refresh_index() -> None:
    try:
        _run(lambda: col().refresh_index())
    except AttributeError:
        pass


def _flatten(results: dict) -> list[dict]:
    """pyseekdb 返回 Chroma 风格 {'ids': [[...]]}（query）或扁平列表（get），统一展平。"""
    rows = []
    if not results:
        return rows
    ids = results.get("ids") or []
    if ids and isinstance(ids[0], list):
        ids = ids[0] if ids else []
    for key, default in (("documents", []), ("metadatas", []), ("distances", [])):
        vals = results.get(key) or []
        if vals and isinstance(vals[0], list):
            results[key] = vals[0]
    docs = results.get("documents") or [None] * len(ids)
    metas = results.get("metadatas") or [None] * len(ids)
    dists = results.get("distances") or [None] * len(ids)
    for i, rid in enumerate(ids):
        rows.append({
            "id": rid,
            "document": docs[i] if i < len(docs) else None,
            "meta": metas[i] if i < len(metas) else None,
            "distance": dists[i] if i < len(dists) else None,
        })
    return rows


def get_one(paper_id: str) -> dict | None:
    rows = _flatten(_run(lambda: col().get(ids=[paper_id])))
    return rows[0] if rows else None


def list_all() -> list[dict]:
    return _flatten(_run(lambda: col().get()))


def _scalar_where(filters: dict | None) -> dict | None:
    """把 {year_min, year_max, tags, venue} 组成 Chroma 风格 where。"""
    if not filters:
        return None
    conds = []
    if filters.get("year_min") is not None:
        conds.append({"year": {"$gte": int(filters["year_min"])}})
    if filters.get("year_max") is not None:
        conds.append({"year": {"$lte": int(filters["year_max"])}})
    if filters.get("venue"):
        conds.append({"venue": {"$eq": filters["venue"]}})
    if not conds:
        return None
    return {"$and": conds} if len(conds) > 1 else conds[0]


INCLUDE = ["documents", "metadatas"]


def search_semantic(query: str, k: int, filters: dict | None = None):
    kwargs = {"query_texts": query, "n_results": k, "include": INCLUDE}
    where = _scalar_where(filters)
    if where:
        kwargs["where"] = where
    return _flatten(_run(lambda: col().query(**kwargs)))


def search_keyword(query_text: str, k: int, filters: dict | None = None):
    query_param = {"where_document": {"$contains": query_text}, "n_results": k}
    where = _scalar_where(filters)
    if where:
        query_param["where"] = where
    return _flatten(_run(lambda: col().hybrid_search(
        query=query_param, n_results=k, include=INCLUDE)))


def search_hybrid(query_text: str, k: int, filters: dict | None = None):
    query_param = {"where_document": {"$contains": query_text}, "n_results": k}
    where = _scalar_where(filters)
    if where:
        query_param["where"] = where
    return _flatten(_run(lambda: col().hybrid_search(
        query=query_param,
        knn={"query_texts": [query_text], "n_results": k},
        rank={"rrf": {}},
        n_results=k,
        include=INCLUDE,
    )))


def count() -> int:
    try:
        return int(_run(lambda: col().count()))
    except Exception:
        return -1
