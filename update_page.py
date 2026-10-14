#!/usr/bin/env python3
"""Swap the embedded data blob in data/<archive>/arxiv_<archive>_submissions.html
for the current contents of viz_data.json, and set the page title.
Layout/CSS/JS are untouched. An archive without a page yet starts from a copy
of the math page; the page reads the archive's name from the data."""
import json, os, re, sys

from config import DATA, PAGE, TEMPLATE, TITLE

viz = json.load(open(f"{DATA}/viz_data.json"))
assert "meta" in viz, "viz_data.json is missing its meta block -- run aggregate.py --write first"

src = PAGE if os.path.exists(PAGE) else TEMPLATE
s = open(src, encoding="utf-8").read()
pat = re.compile(r'(<script id="data" type="application/json">)(.*?)(</script>)', re.S)
m = pat.search(s)
if not m:
    sys.exit("could not find the embedded data script")

old = json.loads(m.group(2))
print(f"old: {len(old['months'])} months, {old['months'][0]}..{old['months'][-1]}, "
      f"last total {old['total'][-1]}")
print(f"new: {len(viz['months'])} months, {viz['months'][0]}..{viz['months'][-1]}, "
      f"last total {viz['total'][-1]}")

# the page keys off these; fail loudly rather than render a broken chart
assert viz["months"] == sorted(viz["months"]), "months not sorted"
assert len(viz["total"]) == len(viz["months"])
for c in viz["cats"]:
    assert len(c["v"]) == len(viz["months"]), f"{c['code']} series length mismatch"
    assert c["base"], f"{c['code']} has no baseline"
assert "2025-08" in viz["months"], "page's MARK month is missing"
assert viz["meta"]["baselineYear"] + "-01" in viz["months"]
assert viz["meta"].get("archive"), "viz_data.json predates the archive field -- rerun aggregate.py --write"

blob = json.dumps(viz)
s = s[:m.start(2)] + blob + s[m.end(2):]
s = re.sub(r"<title>.*?</title>", f"<title>{TITLE}</title>", s, count=1)
open(PAGE, "w", encoding="utf-8").write(s)
print(f"rewrote {PAGE} ({len(s):,} bytes)")
