#!/usr/bin/env python3
"""Repair months that failed the monthly completeness gate.

A month-wide query needs several 2000-record pages, and arXiv's index can
shift between page requests, returning duplicate ids and leaving the union
short of totalResults. Here each day of the month is queried on its own. A
day with more than LIMIT results (which happens in large archives such as cs)
is cut in half, and the halves again, until every window fits in one page.
No window paginates, so the union is exact.

Every request goes through arxiv_api.get(), which enforces arXiv's rate limit
(one request every three seconds, one connection at a time).
"""
import json, os, re, sys, time, calendar, urllib.parse
from datetime import datetime, timedelta

from arxiv_api import API, get
from config import RAW, query as search

SP = os.path.join(RAW, "months")
LOG = os.path.join(RAW, "repair.log")
LIMIT = 1900      # a window with more results than this would need two pages
os.makedirs(SP, exist_ok=True)

ENTRY = re.compile(r"<entry>(.*?)</entry>", re.S)
ID = re.compile(r"<id>http://arxiv\.org/abs/([^<]+)</id>")
PUB = re.compile(r"<published>([^<]+)</published>")
UPD = re.compile(r"<updated>([^<]+)</updated>")
PRIM = re.compile(r'<arxiv:primary_category[^>]*term="([^"]+)"')
CAT = re.compile(r'<category[^>]*term="([^"]+)"')
TOTAL = re.compile(r"totalResults[^>]*>(\d+)")


def log(m):
    line = f"[{datetime.now():%H:%M:%S}] {m}"
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")


def parse(xml):
    out = []
    for b in ENTRY.findall(xml):
        i, p = ID.search(b), PUB.search(b)
        if not (i and p):
            continue
        pr, u = PRIM.search(b), UPD.search(b)
        out.append({"id": i.group(1).split("v")[0], "published": p.group(1),
                    "updated": u.group(1) if u else None,
                    "primary": pr.group(1) if pr else None,
                    "cats": sorted(set(CAT.findall(b)))})
    return out


def query(ms, me, start=0, page=2000):
    url = (f"{API}?search_query={urllib.parse.quote(search(ms, me))}"
           f"&start={start}&max_results={page}")
    for a in range(8):
        try:
            xml = get(url)
            t = TOTAL.search(xml)
            total = int(t.group(1)) if t else None
            recs = parse(xml)
            if recs or total == 0:
                return recs, total
            log(f"      empty (attempt {a+1}) [{ms},{me}]")
        except Exception as e:
            log(f"      {type(e).__name__}: {e} (attempt {a+1})")
        time.sleep(5 * (a + 1))
    return None, None


def stamp(t):
    return f"{t:%Y%m%d%H%M}"


def window(a, b):
    """Every record submitted in [a, b], halving the window while it is too big."""
    got, tot = query(stamp(a), stamp(b))
    if got is None:
        log(f"  [{stamp(a)}, {stamp(b)}] FAILED")
        return None
    if tot is not None and tot > LIMIT:
        if b - a <= timedelta(minutes=2):
            log(f"  [{stamp(a)}, {stamp(b)}] has {tot} results -- cannot split further")
            return None
        mid = (a + (b - a) / 2).replace(second=0, microsecond=0)
        log(f"  [{stamp(a)}, {stamp(b)}] has {tot} results -- splitting at {stamp(mid)}")
        left = window(a, mid)
        right = window(mid, b) if left is not None else None
        return None if right is None else left + right
    return got


def repair(mo):
    y, m = int(mo[:4]), int(mo[5:])
    ndays = calendar.monthrange(y, m)[1]
    recs_all, seen = [], set()
    for d in range(1, ndays + 1):
        a = datetime(y, m, d)
        got = window(a, a + timedelta(days=1))
        if got is None:
            log(f"  {mo} day {d:02d} FAILED"); return None
        for r in got:
            if r["id"] not in seen:
                seen.add(r["id"]); recs_all.append(r)
    # sanity: every record's v1 month must be this month
    bad = [r["id"] for r in recs_all if r["published"][:7] != mo]
    if bad:
        log(f"  {mo} !! {len(bad)} records outside the month, e.g. {bad[:3]}")
        return None
    _, month_total = query(f"{y}{m:02d}010000",
                           f"{y + (1 if m == 12 else 0)}{m % 12 + 1:02d}010000",
                           start=0, page=1)
    log(f"  {mo}: {len(seen)} unique from {ndays} daily windows "
        f"(month-query totalResults says {month_total})")
    with open(f"{SP}/{mo}.jsonl", "w") as f:
        for r in recs_all:
            f.write(json.dumps(r) + "\n")
    with open(f"{SP}/{mo}.done", "w") as f:
        f.write(f"{len(seen)} {len(seen)} daily\n")
    return len(seen)


if __name__ == "__main__":
    targets = sys.argv[1:]
    if not targets:
        sys.exit("usage: repair.py YYYY-MM [YYYY-MM ...]")
    for mo in targets:
        log(f"repairing {mo} with daily windows")
        if repair(mo) is None:
            log(f"  {mo} REPAIR FAILED")
