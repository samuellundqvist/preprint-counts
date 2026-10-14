#!/usr/bin/env python3
"""Fold freshly harvested months (data/<archive>/raw/months/) into the packed archive.

A month present in raw/months/ replaces that month in the archive outright;
this is how a new month is added and how the provisional trailing months are
refreshed with late-announced papers. raw/manifest.tsv is updated to match,
the new archive is named after its month range, and the packed months are
removed from raw/months/ so a later run cannot fold them in again. Only months
whose .done file is present (i.e. which passed the harvest's completeness
check) are used.

    python3 harvest.py 2026-07 2026-08 2026-09   # refresh + add
    python3 pack.py                              # dry run
    python3 pack.py --write
"""
import csv, glob, gzip, io, json, os, sys

from config import RAW
MO = os.path.join(RAW, "months")

old_arc = sorted(glob.glob(f"{RAW}/papers_*.jsonl.gz"))
if len(old_arc) > 1:
    sys.exit(f"expected at most one archive in {RAW}, found {old_arc}")
old_arc = old_arc[0] if old_arc else None       # None: the first pack of an archive

fresh = {}
for done in sorted(glob.glob(f"{MO}/*.done")):
    mo = os.path.basename(done)[:7]
    n = int(open(done).read().split()[0])
    method = "daily" if "daily" in open(done).read() else "monthly"
    recs = [json.loads(l) for l in open(f"{MO}/{mo}.jsonl")]
    assert len({r["id"] for r in recs}) == len(recs) == n, f"{mo}: count mismatch"
    fresh[mo] = (recs, method)
if not fresh:
    sys.exit(f"nothing to pack: no completed months in {MO}")

manifest = {}
if old_arc:
    with open(f"{RAW}/manifest.tsv") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            manifest[row["month"]] = (int(row["papers"]), row["method"])

kept, ids = [], set()
if old_arc:
    with gzip.open(old_arc, "rt") as f:
        for line in f:
            r = json.loads(line)
            if r["published"][:7] not in fresh:
                kept.append(r)
                ids.add(r["id"])
    print(f"archive {os.path.basename(old_arc)}: {len(kept)} records kept")
else:
    print(f"no archive in {RAW} yet: starting one")
for mo, (recs, method) in sorted(fresh.items()):
    clash = [r["id"] for r in recs if r["id"] in ids]
    assert not clash, f"{mo}: ids already in other months, e.g. {clash[:3]}"
    was = manifest.get(mo, (None,))[0]
    print(f"  {mo}: {len(recs):5d} papers ({method})"
          + (f", was {was} ({len(recs) - was:+d})" if was is not None else ", new"))
    kept.extend(recs)
    ids.update(r["id"] for r in recs)
    manifest[mo] = (len(recs), method)

months = sorted(manifest)
new_arc = f"{RAW}/papers_{months[0]}_{months[-1]}.jsonl.gz"
print(f"-> {os.path.basename(new_arc)}: {len(kept)} records, {len(months)} months")

if "--write" not in sys.argv:
    print("dry run -- pass --write to rewrite the archive and manifest")
    sys.exit(0)

kept.sort(key=lambda r: (r["published"], r["id"]))
buf = io.BytesIO()
with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as g:
    for r in kept:
        g.write((json.dumps(r) + "\n").encode())
tmp = new_arc + ".tmp"
open(tmp, "wb").write(buf.getvalue())
os.replace(tmp, new_arc)
if old_arc and new_arc != old_arc:
    os.remove(old_arc)
with open(f"{RAW}/manifest.tsv", "w", newline="") as f:
    w = csv.writer(f, delimiter="\t", lineterminator="\n")
    w.writerow(["month", "papers", "method"])
    for mo in months:
        w.writerow([mo, *manifest[mo]])
for mo in fresh:
    os.remove(f"{MO}/{mo}.jsonl")
    os.remove(f"{MO}/{mo}.done")
print(f"wrote {new_arc} and raw/manifest.tsv; cleared the packed months from {MO}")
