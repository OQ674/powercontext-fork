"""幂等导入种子数据到 seekdb。用法：python seed_import.py"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db


def load_items(path):
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    items = []
    for r in rows:
        items.append({
            "id": r["id"],
            "title": r["title"],
            "authors": r["authors"],
            "year": int(r["year"]),
            "venue": r["venue"],
            "tags": r["tags"],
            "language": r["language"],
            "abstract": r["abstract"],
            "url": r["url"],
            "is_sample": r.get("is_sample", "true").lower() == "true",
        })
    return items


def main():
    csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "papers.csv")
    items = load_items(csv_path)
    db.upsert(items)
    db.refresh_index()
    print(f"imported {len(items)} papers; total={db.count()}")


if __name__ == "__main__":
    main()
