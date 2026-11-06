import csv, sys
p = r"D:\文件\文档\Oceanbase大赛\速成\Qoder\seeklit\backend\seed\papers.csv"
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
    text = r[1] + abstract
    has_cn = any("\u4e00" <= c <= "\u9fff" for c in text)
    if has_cn and lang == "en":
        print("LANG(en but zh text):", r[0]); bad += 1
    if not has_cn and lang == "zh":
        print("LANG(zh but en text):", r[0]); bad += 1
print("total rows:", len(rows) - 1, "problems:", bad)
