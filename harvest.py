#!/usr/bin/env python3
"""Harvest one arXiv archive (config.ARCHIVE) by submission month, SUB_LO .. HI.

With YYYY-MM arguments, harvest only those months (used to add a new month
and to refresh the months before it). A month whose pages do not add up to
the API's totalResults is reported INCOMPLETE; fetch it with repair.py.

Two safeguards:
  * a short page is retried, and a month is only accepted when the number of
    unique papers fetched equals the API's totalResults;
  * each month is written to its own file so a month can be re-run in isolation.

Every request goes through arxiv_api.get(), which enforces arXiv's rate limit
(one request every three seconds, one connection at a time).
"""
import json, os, re, sys, time, urllib.parse
from datetime import datetime

from arxiv_api import API, get
from config import RAW, SUB_LO, HI, query

SP = os.path.join(RAW, "months")
LOG = os.path.join(RAW, "harvest.log")
PAGE = 2000
os.makedirs(SP, exist_ok=True)

ENTRY = re.compile(r"<entry>(.*?)</entry>", re.S)
ID = re.compile(r"<id>http://arxiv\.org/abs/([^<]+)</id>")
PUB = re.compile(r"<published>([^<]+)</published>")
UPD = re.compile(r"<updated>([^<]+)</updated>")
PRIM = re.compile(r'<arxiv:primary_category[^>]*term="([^"]+)"')
CAT = re.compile(r'<category[^>]*term="([^"]+)"')
TOTAL = re.compile(r"totalResults[^>]*>(\d+)")


def log(msg):
    line = f"[{datetime.now():%H:%M:%S}] {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")


def months(y0, m0, y1, m1):
    y, m = y0, m0
    while (y, m) <= (y1, m1):
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def fetch(ms, me, start, want):
    """One page. Retries on error, empty, AND short-but-not-final pages."""
    url = (f"{API}?search_query={urllib.parse.quote(query(ms, me))}"
           f"&start={start}&max_results={PAGE}")
    for attempt in range(8):
        try:
            xml = get(url)
            t = TOTAL.search(xml)
            total = int(t.group(1)) if t else None
            recs = parse(xml)
            expect = min(PAGE, (want if want is not None else total or 0) - start)
            if recs and (len(recs) >= expect or total == 0):
                return recs, total
            if total == 0:
                return [], 0
            log(f"      short page: got {len(recs)}, expected {expect} "
                f"(attempt {attempt+1}) -- retrying")
        except Exception as e:
            log(f"      {type(e).__name__}: {e} (attempt {attempt+1})")
        time.sleep(5 * (attempt + 1))
    return None, None


def parse(xml):
    out = []
    for body in ENTRY.findall(xml):
        i, p = ID.search(body), PUB.search(body)
        if not (i and p):
            continue
        prim, u = PRIM.search(body), UPD.search(body)
        out.append({
            "id": i.group(1).split("v")[0],
            "published": p.group(1),
            "updated": u.group(1) if u else None,
            "primary": prim.group(1) if prim else None,
            "cats": sorted(set(CAT.findall(body))),
        })
    return out


def harvest_month(y, m):
    out = f"{SP}/{y}-{m:02d}.jsonl"
    done = f"{SP}/{y}-{m:02d}.done"
    if os.path.exists(done):
        return int(open(done).read().split()[0]), True   # resume: already good
    ms = f"{y}{m:02d}010000"
    em, ey = m % 12 + 1, y + (1 if m == 12 else 0)
    me = f"{ey}{em:02d}010000"

    recs_all, seen, start, total = [], set(), 0, None
    while True:
        recs, t = fetch(ms, me, start, total)
        if recs is None:
            log(f"  {y}-{m:02d} FAILED at start={start}")
            return None, False
        if total is None:
            total = t
        for r in recs:
            if r["id"] not in seen:
                seen.add(r["id"])
                recs_all.append(r)
        start += len(recs)
        if start >= (total or 0):
            break

    if total is not None and len(seen) != total:
        log(f"  {y}-{m:02d} INCOMPLETE: {len(seen)} unique vs totalResults {total}")
        return None, False

    with open(out, "w") as f:
        for r in recs_all:
            f.write(json.dumps(r) + "\n")
    with open(done, "w") as f:
        f.write(f"{len(seen)} {total}\n")
    return len(seen), False


def main():
    grand, failed = 0, []
    todo = ([(int(a[:4]), int(a[5:])) for a in sys.argv[1:]]
            or list(months(int(SUB_LO[:4]), int(SUB_LO[5:]), int(HI[:4]), int(HI[5:]))))
    for y, m in todo:
        n, cached = harvest_month(y, m)
        if n is None:
            failed.append(f"{y}-{m:02d}")
            continue
        grand += n
        log(f"  {y}-{m:02d}: {n:5d} papers{'  (cached)' if cached else ''} | cumulative {grand}")
    log(f"DONE. {grand} papers across months. failures: {failed or 'none'}")
    if failed:
        log(f"next: python3 repair.py {' '.join(failed)}")


if __name__ == "__main__":
    main()
