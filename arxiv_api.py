"""Rate-limited access to the arXiv API, shared by harvest.py and repair.py.

arXiv's API terms of use (https://info.arxiv.org/help/api/tou.html) allow at
most one request every three seconds, over a single connection at a time,
counted across all machines under your control. Every request goes through
get() below, which enforces both limits on this machine, across processes as
well as within one:

  * an exclusive lock on .api.lock, in the repository root and shared by all
    archives, serialises requests, so two scripts running at once (also for
    different archives) still use one connection;
  * the lock file records when the previous request finished, and get() waits
    until GAP seconds have passed since then, so a script started right after
    another one still waits.

The gap is measured from the end of the previous request, which is stricter
than the terms require. It cannot see other machines: run the harvest from one
machine only.
"""
import fcntl, os, time, urllib.request

API = "https://export.arxiv.org/api/query"
GAP = 3.0       # seconds between requests (arXiv API terms of use)
LOCK = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".api.lock")


def get(url, timeout=180):
    """Fetch url and return the body as text, respecting arXiv's rate limit."""
    with open(LOCK, "a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)          # one request at a time
        try:
            f.seek(0)
            try:
                last = float(f.read().strip() or 0)
            except ValueError:
                last = 0.0
            wait = last + GAP - time.time()
            if wait > 0:
                time.sleep(wait)
            try:
                with urllib.request.urlopen(url, timeout=timeout) as r:
                    return r.read().decode("utf-8", "replace")
            finally:                            # failed requests count too
                f.seek(0)
                f.truncate()
                f.write(f"{time.time():.3f}\n")
                f.flush()
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
