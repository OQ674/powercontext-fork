import csv
import os
import sys

p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "papers.csv")
with open(p, encoding="utf-8-sig") as f:
    rows = list(csv.reader(f))
header = rows[0]
print("cols:", len(header))
bad = 0
for r in rows[1:]:
    if len(r) != len(header):
        print("BAD len", len(r), r[0], r[:3]); bad += 1
    lang = r[6] if len(r) > 6 else "?"
    abstract = r[7][:30] if len(r) > 7 else ""
    # language 表示摘要正文语言；标题可能是中文翻译，不参与语言一致性检查。
    text = r[7] if len(r) > 7 else ""
    has_cn = any("\u4e00" <= c <= "\u9fff" for c in text)
    if has_cn and lang == "en":
        print("LANG(en but zh text):", r[0]); bad += 1
    if not has_cn and lang == "zh":
        print("LANG(zh but en text):", r[0]); bad += 1
print("total rows:", len(rows) - 1, "problems:", bad)
sys.exit(1 if bad else 0)
