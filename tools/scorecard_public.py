#!/usr/bin/env python3
"""THE SCORECARD, PUBLIC (the library's row 658; the owner, 10-29: "Can we just
publish the scorecard info as json or something and I can read it in my
private pulse page?").

    tools/scorecard_public.py out/<date> [run URL] [public URL]

Writes out/<date>/public/scorecard.json -- the library scorecard's own `--json`,
verbatim, and its `--read` lines, with the date, the pin and the run that made
them -- and prints the run's summary as Markdown (the workflow appends it to
$GITHUB_STEP_SUMMARY). The workflow serves the file beside the catalog at
/scorecard.json, and the private pulse page (tools/site.py) reads it from there.

Counts and the read only: no image, no geometry. Every number is the library
tool's; nothing here scores or decides.
"""
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "library"
TOTALS = ["subjects", "bands", "covered_hand", "covered_library", "uncovered", "fully", "fully_from_rung0"]


def scorecard(*args):
    return subprocess.run([sys.executable, "tools/scorecard.py", *args], cwd=LIB, check=True,
                          capture_output=True, text=True).stdout


def pin():
    lock = (ROOT / "library.lock").read_text()
    return next((l.split("=", 1)[1].strip() for l in lock.splitlines() if l.startswith("commit=")), "")


def summary(doc, public_url):
    t = doc["scorecard"].get("totals", {})
    out = ["### the scorecard (library %s)" % doc["pin"][:12], "",
           "| %s |" % " | ".join(TOTALS), "|%s" % ("---:|" * len(TOTALS)),
           "| %s |" % " | ".join(str(t.get(k, "")) for k in TOTALS), ""]
    split = t.get("split")
    if split:
        out += ["bands: " + ", ".join("%s %s" % (k.replace("_", " "), v) for k, v in split.items()), ""]
    out += ["the read (`tools/scorecard.py --read`):", "", "```"] + doc["read"] + ["```", ""]
    if public_url:
        out += ["served with this run's catalog at %s" % public_url, ""]
    return "\n".join(out)


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    run = Path(argv[1])
    doc = {
        "written": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "date": run.name,
        "pin": pin(),
        "run": argv[2] if len(argv) > 2 else None,
        "scorecard": json.loads(scorecard("--json")),
        "read": scorecard("--read").rstrip("\n").splitlines(),
    }
    dst = run / "public" / "scorecard.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(doc, separators=(",", ":")) + "\n")
    print(summary(doc, argv[3] if len(argv) > 3 else None))


if __name__ == "__main__":
    main(sys.argv)
