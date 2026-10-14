"""Settings shared by every script.

ARCHIVE is the arXiv archive to count, given by its prefix: "math" counts
math.AC, math.AG, ...; "cs" counts cs.AI, cs.CL, ... Set it for one run with
the environment variable, e.g.

    ARXIV_ARCHIVE=cs python3 harvest.py

Only archives that have subject classes (math, cs, stat, eess, econ, q-bio,
q-fin, physics, astro-ph, cond-mat, nlin) work; the query is "cat:<archive>.*".
Each archive keeps its own files under data/<archive>/.

HI is the last announcement month on the page. Raise it by one after each
month has ended (see README.md).
"""
import os

ARCHIVE = os.environ.get("ARXIV_ARCHIVE", "math")

SUB_LO = "2017-11"      # first harvested submission month
LO = "2018-01"          # first announcement month shown
HI = "2026-09"          # last announcement month shown

# How the page names the field: "New papers in every <label> subject class".
LABELS = {
    "math": "mathematics", "cs": "computer science", "stat": "statistics",
    "eess": "electrical engineering and systems science", "econ": "economics",
    "q-bio": "quantitative biology", "q-fin": "quantitative finance",
    "physics": "physics", "astro-ph": "astrophysics",
    "cond-mat": "condensed matter", "nlin": "nonlinear sciences",
}
LABEL = LABELS.get(ARCHIVE, ARCHIVE)
TITLES = {"math": "Math Announcements on arXiv", "cs": "CS Announcements on arXiv"}
TITLE = TITLES.get(ARCHIVE, f"{ARCHIVE} Announcements on arXiv")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.environ.get("ARXIV_DATA", os.path.join(HERE, "data")), ARCHIVE)
RAW = os.path.join(DATA, "raw")
PAGE = os.path.join(DATA, f"arxiv_{ARCHIVE}_submissions.html")
TEMPLATE = os.path.join(HERE, "data", "math", "arxiv_math_submissions.html")
CATEGORIES = os.path.join(HERE, "categories.tsv")


def query(start, end):
    """arXiv API search for every paper in ARCHIVE submitted in [start, end]."""
    return f"cat:{ARCHIVE}.* AND submittedDate:[{start} TO {end}]"
