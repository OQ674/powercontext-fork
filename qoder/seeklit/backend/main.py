"""SeekLit 后端：科研文献混合检索 API（FastAPI + pyseekdb/seekdb）。"""
import csv
import os
import re

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import db

app = FastAPI(title="SeekLit API")

ALLOWED_ORIGINS = [
    "http://localhost:5173", "http://127.0.0.1:5173",
    "http://localhost:4173", "http://127.0.0.1:4173",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"https://.*\.qoder\.site",
    allow_methods=["*"],
    allow_headers=["*"],
)

TOKEN = os.environ.get("SEEKLIT_TOKEN", "")


def check_token(x_api_token: str | None):
    if TOKEN and x_api_token != TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")


class PaperIn(BaseModel):
    id: str | None = None
    title: str
    authors: str = ""
    year: int = 0
    venue: str = ""
    tags: list[str] | str = Field(default="")
    language: str = "zh"
    abstract: str = ""
    url: str = ""
    is_sample: bool = False


class SearchFilters(BaseModel):
    year_min: int | None = None
    year_max: int | None = None
    venue: str | None = None
    tags: list[str] | None = None


class SearchRequest(BaseModel):
    query: str
    mode: str = "hybrid"
    n_results: int = 10
    filters: SearchFilters | None = None


def _to_out(row: dict) -> dict:
    m = row.get("meta") or {}
    tags_csv = str(m.get("tags_csv", ""))
    return {
        "id": row["id"],
        "title": m.get("title", ""),
        "authors": m.get("authors", ""),
        "year": m.get("year", 0),
        "venue": m.get("venue", ""),
        "tags": [t for t in re.split(r"[,;]", tags_csv) if t],
        "language": m.get("language", ""),
        "url": m.get("url", ""),
        "is_sample": bool(m.get("is_sample", False)),
        "abstract": _abstract_from_document(row.get("document"), m.get("title", ""),
                                            str(m.get("tags_csv", ""))),
        "distance": row.get("distance"),
    }


def _abstract_from_document(document: str | None, title: str, tags_csv: str = "") -> str:
    # document 末行是供全文检索用的标签行（见 db.paper_document），展示前剥离。
    if not document:
        return ""
    if tags_csv and document.endswith("\n" + tags_csv):
        document = document[: -(len(tags_csv) + 1)]
    if document.startswith(title):
        return document[len(title):].lstrip("\n")
    return document


def _hit(row: dict, rank: int, sources: list[str], v_rank: int | None, f_rank: int | None) -> dict:
    return {
        "paper": _to_out(row),
        "rank": rank,
        "sources": sources,
        "vector_rank": v_rank,
        "fulltext_rank": f_rank,
    }


def _match_tags(paper: dict, tags: list[str] | None) -> bool:
    if not tags:
        return True
    return any(t in paper["tags"] for t in tags)


def _filter_rows_by_tags(rows: list[dict], tags: list[str] | None) -> list[dict]:
    if not tags:
        return rows
    return [r for r in rows if _match_tags(_to_out(r), tags)]


@app.get("/api/health")
def health():
    return {"status": "ok", "papers": db.count()}


@app.post("/api/search")
def search(req: SearchRequest, x_api_token: str | None = Header(default=None)):
    check_token(x_api_token)
    k = max(1, min(req.n_results, 20))
    filters = req.filters.model_dump(exclude_none=True) if req.filters else {}
    tags = filters.pop("tags", None)
    try:
        if req.mode == "semantic":
            rows = _filter_rows_by_tags(db.search_semantic(req.query, k, filters), tags)
            return {"mode": req.mode, "hits": [
                _hit(r, i + 1, ["vector"], i + 1, None) for i, r in enumerate(rows)
            ]}
        if req.mode == "keyword":
            rows = _filter_rows_by_tags(db.search_keyword(req.query, k, filters), tags)
            return {"mode": req.mode, "hits": [
                _hit(r, i + 1, ["fulltext"], None, i + 1) for i, r in enumerate(rows)
            ]}
        rows = _filter_rows_by_tags(db.search_hybrid(req.query, k, filters), tags)
        try:
            sem_rows = db.search_semantic(req.query, k * 2, filters)
            kw_rows = db.search_keyword(req.query, k * 2, filters)
        except Exception:
            sem_rows, kw_rows = [], []
        sem_rank = {r["id"]: i + 1 for i, r in enumerate(sem_rows)}
        kw_rank = {r["id"]: i + 1 for i, r in enumerate(kw_rows)}
        hits = []
        for i, r in enumerate(rows):
            vr, fr = sem_rank.get(r["id"]), kw_rank.get(r["id"])
            sources = [s for s, present in (("vector", vr), ("fulltext", fr)) if present]
            if not sources:
                sources = ["hybrid"]
            hits.append(_hit(r, i + 1, sources, vr, fr))
        return {"mode": "hybrid", "hits": hits}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"search failed: {e}")


@app.get("/api/papers")
def list_papers(
    x_api_token: str | None = Header(default=None),
    year_min: int | None = Query(default=None),
    year_max: int | None = Query(default=None),
    venue: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    q: str | None = Query(default=None),
    page: int = Query(default=1),
    page_size: int = Query(default=20, le=100),
):
    check_token(x_api_token)
    try:
        if q:
            rows = db.search_hybrid(q, 100, {})
        else:
            rows = db.list_all()
        out = [_to_out(r) for r in rows]
        if year_min is not None:
            out = [p for p in out if p["year"] >= year_min]
        if year_max is not None:
            out = [p for p in out if p["year"] <= year_max]
        if venue:
            out = [p for p in out if p["venue"] == venue]
        if tag:
            out = [p for p in out if tag in p["tags"]]
        out.sort(key=lambda p: p["year"], reverse=True)
        total = len(out)
        start = (page - 1) * page_size
        return {"total": total, "papers": out[start:start + page_size]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"list failed: {e}")


@app.get("/api/papers/{paper_id}")
def get_paper(paper_id: str, x_api_token: str | None = Header(default=None)):
    check_token(x_api_token)
    paper = db.get_one(paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="not found")
    return paper


@app.post("/api/papers", status_code=201)
def create_paper(p: PaperIn, x_api_token: str | None = Header(default=None)):
    check_token(x_api_token)
    item = p.model_dump()
    item["id"] = item["id"] or _gen_id(item["title"])
    db.upsert([item])
    db.refresh_index()
    meta = db._meta(item)
    return _to_out({"id": item["id"], "meta": meta,
                    "document": db.paper_document(item["title"], item.get("abstract", ""), meta["tags_csv"])})


@app.put("/api/papers/{paper_id}")
def update_paper(paper_id: str, p: PaperIn, x_api_token: str | None = Header(default=None)):
    check_token(x_api_token)
    item = p.model_dump()
    item["id"] = paper_id
    db.delete([paper_id])
    db.upsert([item])
    db.refresh_index()
    meta = db._meta(item)
    return _to_out({"id": paper_id, "meta": meta,
                    "document": db.paper_document(item["title"], item.get("abstract", ""), meta["tags_csv"])})


@app.delete("/api/papers/{paper_id}")
def delete_paper(paper_id: str, x_api_token: str | None = Header(default=None)):
    check_token(x_api_token)
    db.delete([paper_id])
    db.refresh_index()
    return {"deleted": paper_id}


@app.post("/api/import")
def import_papers(payload: dict, x_api_token: str | None = Header(default=None)):
    check_token(x_api_token)
    items = payload.get("items", [])
    if not items or len(items) > 200:
        raise HTTPException(status_code=400, detail="items must be 1..200")
    for it in items:
        it.setdefault("id", _gen_id(it.get("title", "")))
    db.upsert(items)
    db.refresh_index()
    return {"imported": len(items)}


@app.post("/api/reindex")
def reindex(x_api_token: str | None = Header(default=None)):
    check_token(x_api_token)
    db.refresh_index()
    return {"status": "reindexed"}


def _gen_id(title: str) -> str:
    import hashlib
    return hashlib.md5((title + str(os.urandom(8))).encode("utf-8")).hexdigest()[:16]
