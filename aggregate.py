#!/usr/bin/env python3
"""Aggregate harvested papers of one archive into month x category counts.

Reads the raw archive in data/<archive>/raw/ (papers_*.jsonl.gz, or
months/*.jsonl if a fresh harvest is in progress) and writes
arxiv_<archive>_primary.csv, arxiv_<archive>_anycat.csv and viz_data.json
next to it.

Papers are counted in the month arXiv announced them, read from the YYMM of
the identifier. arXiv assigns the identifier at the 14:00 ET cutoff of the
batch a paper goes out in, so a paper held for moderation counts in the month
it is finally released, and a month's count is final once the month is over.

The harvest itself is by v1 submission month (the only date the API can be
queried by), from SUB_LO on: a few months before LO, so that papers submitted
late in 2017 and announced in 2018 are included. Refuses to write unless every
harvested submission month matches raw/manifest.tsv, which records the count
the arXiv API reported for that month. Pass --write to actually write; the
default is a dry run that only reports.
"""
import csv, glob, gzip, json, os, re, sys
from datetime import datetime, timezone
from collections import Counter, defaultdict

from config import ARCHIVE, LABEL, CATEGORIES, DATA, RAW, LO, HI, SUB_LO

PREFIX = ARCHIVE + "."


def month_range(lo, hi):
    y, m = int(lo[:4]), int(lo[5:])
    y1, m1 = int(hi[:4]), int(hi[5:])
    out = []
    while (y, m) <= (y1, m1):
        out.append(f"{y}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


months = month_range(LO, HI)
sub_months = month_range(SUB_LO, HI)
if HI >= f"{datetime.now(timezone.utc):%Y-%m}":
    sys.exit(f"HI={HI} has not ended yet; its count would not be final")
NEWID = re.compile(r"(\d{2})(\d{2})\.\d{4,5}")


def announced(r):
    """YYYY-MM of the batch the paper was announced in, from its identifier."""
    yy, mm = NEWID.fullmatch(r["id"]).groups()
    return f"20{yy}-{mm}"


def records():
    """Yield every harvested record, preferring the packed archive."""
    arc = sorted(glob.glob(f"{RAW}/papers_*.jsonl.gz"))
    if arc:
        with gzip.open(arc[-1], "rt") as f:
            for line in f:
                yield json.loads(line)
        return
    files = sorted(glob.glob(f"{RAW}/months/*.jsonl"))
    if not files:
        sys.exit(f"no raw data in {RAW} -- run harvest.py first")
    for p in files:
        with open(p) as f:
            for line in f:
                yield json.loads(line)


# ---------- manifest: the count the API reported per month ----------
expect = {}
mpath = f"{RAW}/manifest.tsv"
if os.path.exists(mpath):
    with open(mpath) as f:
        for row in csv.DictReader(f, delimiter="\t"):
            expect[row["month"]] = int(row["papers"])
else:
    print(f"warning: {mpath} missing -- completeness cannot be verified")

# ---------- tally ----------
prim = defaultdict(Counter)   # month -> cat -> count (primary category only)
anyc = defaultdict(Counter)   # month -> cat -> count (listed in any category)
total = Counter()             # month -> papers with a primary in ARCHIVE
per_month = Counter()         # submission month -> harvested papers
outside = Counter()           # announcement months outside LO..HI
seen, shown, badid = set(), 0, []
for r in records():
    if r["id"] in seen:
        continue
    seen.add(r["id"])
    per_month[r["published"][:7]] += 1    # v1 month: what the manifest counts
    if not NEWID.fullmatch(r["id"]):
        badid.append(r["id"])
        continue
    m = announced(r)
    if not (LO <= m <= HI):
        outside[m] += 1
        continue
    shown += 1
    p = r.get("primary")
    if p and p.startswith(PREFIX):
        prim[m][p] += 1
        total[m] += 1
    for c in r["cats"]:
        if c.startswith(PREFIX):
            anyc[m][c] += 1

# ---------- completeness gate ----------
problems = []
for m in sub_months:
    if m not in expect:
        problems.append(f"{m}: not in raw/manifest.tsv -- harvest it first")
    elif per_month[m] != expect[m]:
        problems.append(f"{m}: harvested {per_month[m]} vs API {expect[m]}")
stray = sorted(set(per_month) - set(sub_months))
if stray:
    problems.append(f"records submitted outside {SUB_LO}..{HI}: {stray}")
if badid:
    problems.append(f"{len(badid)} identifiers without a YYMM, e.g. {badid[:3]}")
if problems:
    print("COMPLETENESS GATE FAILED:")
    for p in problems:
        print("  " + p)
    sys.exit(1)
print(f"completeness gate passed: {len(sub_months)} submission months "
      f"({SUB_LO} .. {HI}) match raw/manifest.tsv")
print(f"announced outside {LO}..{HI}, not counted: {dict(sorted(outside.items()))}")

cats = sorted({c for m in months for c in anyc[m]})
print(f"unique papers: {len(seen)} harvested, {shown} announced in range")
print(f"announcement months: {len(months)} ({months[0]} .. {months[-1]})")
print(f"categories: {len(cats)}\n")

print(f"Monthly total ({PREFIX}* primary):")
for m in months:
    print(f"  {m}  {total[m]:5d}")

# Complete 12-month blocks running Aug..Jul. Months after the last block are
# reported separately below via a trailing-12-month window, not as a stub block.
last_y = int(HI[:4]) - (1 if HI[5:] >= "07" else 2)
blocks = [(f"{y}-08", f"{y+1}-07", f"Aug{str(y)[2:]}-Jul{str(y+1)[2:]}")
          for y in range(int(LO[:4]), last_y + 1)]
print(f"\n12-month blocks ({PREFIX}* primary):")
prev = None
for lo, hi, label in blocks:
    s = sum(total[m] for m in months if lo <= m <= hi)
    chg = f"  {100*(s/prev-1):+6.1f}%" if prev else ""
    print(f"  {label}: {s:6d}{chg}")
    prev = s

# Trailing 12 months ending at the data edge, so the newest month is not
# invisible just because it falls outside the Aug..Jul block grid.
def window12(end):
    i = months.index(end)
    return months[max(0, i - 11):i + 1]

for end in (months[-13], months[-1]):
    w = window12(end)
    print(f"  T12 {w[0]}..{w[-1]}: {sum(total[m] for m in w):6d}")
t_now, t_prev = (sum(total[m] for m in window12(e)) for e in (months[-1], months[-13]))
print(f"  trailing-12m change: {100*(t_now/t_prev-1):+.1f}%")

yr = {}
for lo, hi, label in blocks:
    yr[label] = Counter()
    for m in months:
        if lo <= m <= hi:
            yr[label].update(prim[m])

first, last = blocks[0][2], blocks[-1][2]
pre, post = blocks[4][2], blocks[-1][2]   # Aug22-Jul23 vs Aug25-Jul26
print(f"\nPer-category: {first} -> {last}, and {pre} -> {post} (primary)")
print(f"{'cat':10} {first:>10} {pre:>10} {post:>10} {'x vs 1st':>9} {'x vs pre':>9}")
for c in sorted(cats, key=lambda c: -yr[last][c]):
    a, b, d = yr[first][c], yr[pre][c], yr[last][c]
    r1 = f"{d/a:.2f}x" if a else "n/a"
    r2 = f"{d/b:.2f}x" if b else "n/a"
    print(f"{c:10} {a:10d} {b:10d} {d:10d} {r1:>9} {r2:>9}")

if "--write" not in sys.argv:
    print("\ndry run -- pass --write to rewrite the CSVs and viz_data.json")
    sys.exit(0)

# ---------- write CSVs ----------
for name, data in (("primary", prim), ("anycat", anyc)):
    with open(f"{DATA}/arxiv_{ARCHIVE}_{name}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["month"] + cats + ["TOTAL"])
        for m in months:
            row = [data[m].get(c, 0) for c in cats]
            w.writerow([m] + row + [total[m] if name == "primary" else sum(row)])
    print(f"wrote arxiv_{ARCHIVE}_{name}.csv")

# ---------- write viz_data.json (consumed by update_page.py) ----------
with open(CATEGORIES) as f:
    NAMES = {row["code"]: row["name"] for row in csv.DictReader(f, delimiter="\t")}
vp = f"{DATA}/viz_data.json"
b0 = months.index(LO)                             # 'base' = mean month in LO's year
viz = {"months": months, "total": [total[m] for m in months], "cats": [],
       "meta": {"baselineYear": LO[:4], "harvested": shown, "basis": "announced",
                "first": months[0], "last": months[-1],
                "archive": ARCHIVE, "label": LABEL}}
for c in cats:
    v = [prim[m].get(c, 0) for m in months]
    viz["cats"].append({"code": c, "name": NAMES.get(c, c), "v": v,
                        "base": round(sum(v[b0:b0 + 12]) / 12, 2),
                        "total": sum(v)})
with open(vp, "w") as f:
    json.dump(viz, f)
print(f"wrote viz_data.json ({len(months)} months, {len(cats)} cats, "
      f"last={months[-1]} total={total[months[-1]]})")
