#!/usr/bin/env python3
"""THE PAGE (the plan's step 2): one static HTML page per subject and an index,
from one run's output and the history -- no scripts needed to read it.

    tools/site.py out/<date>        # writes out/<date>/site/

Every number on it is a library tool's, copied: the scorecard's line for the
subject (`scorecard.txt`), and the per-band sheet's numbers
(`<subject>/sheet-bands.json`, `tools/rung-sheet.py` in the library). Nothing
here scores, ranks or decides what a band is. A missing file is named on the
page, never hidden. Images are re-encoded under 100 KB for a phone.
"""
import csv
import html
import io
import json
import sys
from pathlib import Path

from PIL import Image

MAX_BYTES = 100_000
CSS = """
:root { --bg: #fff; --fg: #111; --mute: #666; --line: #ddd; --ok: #0a6e0a; --warn: #b36b00; --bad: #b00; }
@media (prefers-color-scheme: dark) { :root { --bg: #111; --fg: #eee; --mute: #999; --line: #333;
  --ok: #5c5; --warn: #e9a23b; --bad: #f66; } }
* { box-sizing: border-box; }
body { margin: 0 auto; padding: 16px; max-width: 900px; background: var(--bg); color: var(--fg);
  font: 15px/1.45 system-ui, sans-serif; }
h1 { font-size: 1.3em; margin: 0 0 4px; } h2 { font-size: 1.05em; margin: 24px 0 8px; }
.mute { color: var(--mute); } .ok { color: var(--ok); } .warn { color: var(--warn); } .bad { color: var(--bad); }
.wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }
table { border-collapse: collapse; font-size: 13px; white-space: nowrap; }
th, td { border-bottom: 1px solid var(--line); padding: 4px 8px; text-align: right; }
th:first-child, td:first-child { text-align: left; }
pre { overflow-x: auto; font-size: 12px; background: rgba(127,127,127,.08); padding: 8px; }
img { max-width: 100%; height: auto; display: block; margin: 8px 0; }
a { color: inherit; }
"""


def page(title, body):
    return ("<!doctype html><html lang=en><head><meta charset=utf-8>"
            "<meta name=viewport content='width=device-width,initial-scale=1'>"
            "<title>%s</title><style>%s</style></head><body>%s</body></html>" % (html.escape(title), CSS, body))


def small_jpeg(src, dst):
    """`src` as a JPEG under MAX_BYTES: lower quality first, then smaller."""
    im = Image.open(src).convert("RGB")
    for scale in (1.0, 0.8, 0.64, 0.5, 0.4):
        sized = im if scale == 1.0 else im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS)
        for q in (85, 75, 65, 55, 45):
            buf = io.BytesIO()
            sized.save(buf, "JPEG", quality=q, optimize=True, progressive=True)
            if buf.tell() <= MAX_BYTES:
                dst.write_bytes(buf.getvalue())
                return True
    dst.write_bytes(buf.getvalue())
    return False


def fmt(v, spec="%d"):
    return "--" if v is None else spec % v


def tone(multiple):
    if multiple is None:
        return ""
    return "ok" if multiple <= 1.5 else ("warn" if multiple <= 4 else "bad")


def band_table(bands):
    rows = ["<tr><th>band</th><th>from m</th><th>today</th><th>cost</th><th>x ceiling</th><th>err px</th>"
            "<th>derived</th><th>cost</th><th>x ceiling</th><th>err px</th><th>saved</th></tr>"]
    for b in bands:
        d = b.get("derived", {})
        m = b["cost"] / b["ceiling"] if b.get("ceiling") else None
        dm = d["cost"] / b["ceiling"] if d.get("cost") is not None and b.get("ceiling") else None
        rows.append("<tr><td>%d</td><td>%.2f</td><td>r%d %s</td><td>%d</td><td class=%s>%s</td><td>%.2f</td>"
                    "<td>%s</td><td>%s</td><td class=%s>%s</td><td>%s</td><td>%s</td></tr>" % (
                        b["band"], b["from_m"], b["rung"], html.escape(b["how"]), b["cost"], tone(m), fmt(m, "%.2fx"),
                        b["error_px"], html.escape(d.get("verdict", "")), fmt(d.get("cost")), tone(dm),
                        fmt(dm, "%.2fx"), fmt(d.get("error_px"), "%.2f"), fmt(b.get("saved"))))
    return "<div class=wrap><table>%s</table></div>" % "".join(rows)


TREND = [("covered_hand", "covered by hand", "var(--ok)"), ("covered_library", "by the library", "var(--warn)"),
         ("uncovered", "uncovered", "var(--bad)")]


def trend_svg(history):
    """The totals over the runs that finished, as lines: drawn from history.csv's
    numbers only, the y axis 0 to the bands the newest row counts."""
    rows = [h for h in history if h.get("status") == "ok" and h.get("bands")]
    if len(rows) < 2:
        return "<p class=mute>one run so far; the trend starts with the second</p>"
    w, h, pad = 600, 160, 24
    top = max(int(r["bands"]) for r in rows) or 1
    xs = [pad + i * (w - 2 * pad) / (len(rows) - 1) for i in range(len(rows))]
    y = lambda v: h - pad - (h - 2 * pad) * v / top
    parts = ["<svg viewBox='0 0 %d %d' width='100%%' role=img aria-label='the totals by run'>" % (w, h),
             "<line x1=%d y1=%.1f x2=%d y2=%.1f stroke='var(--line)'/>" % (pad, y(0), w - pad, y(0)),
             "<text x=%d y=%.1f font-size=10 fill='var(--mute)'>%d</text>" % (2, y(top) + 4, top),
             "<text x=%d y=%.1f font-size=10 fill='var(--mute)'>0</text>" % (2, y(0) + 4)]
    for key, _, colour in TREND:
        pts = " ".join("%.1f,%.1f" % (x, y(int(r[key]))) for x, r in zip(xs, rows))
        parts.append("<polyline fill=none stroke='%s' stroke-width=2 points='%s'/>" % (colour, pts))
    parts.append("<text x=%d y=%d font-size=10 fill='var(--mute)'>%s</text>" % (pad, h - 6, html.escape(rows[0]["date"])))
    parts.append("<text x=%d y=%d font-size=10 fill='var(--mute)' text-anchor=end>%s</text>"
                 % (w - pad, h - 6, html.escape(rows[-1]["date"])))
    parts.append("</svg>")
    legend = " ".join("<span style='color:%s'>&#9632;</span> %s" % (c, html.escape(n)) for _, n, c in TREND)
    return "".join(parts) + "<p class=mute>%s, of %d bands</p>" % (legend, top)


def subject_history(root, sid):
    """The subject's scorecard line on every run whose output is still on disk,
    newest first -- the library's line copied, never re-scored."""
    out = []
    for card in sorted((root / "out").glob("*/scorecard.txt"), reverse=True):
        line = next((l for l in card.read_text().splitlines() if l.split()[:1] == [sid]), None)
        out.append((card.parent.name, line))
    return out


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    run = Path(argv[1]).resolve()
    root = run.parent.parent
    site = run / "site"
    (site / "img").mkdir(parents=True, exist_ok=True)
    manifest = json.loads((run / "manifest.json").read_text()) if (run / "manifest.json").exists() else []
    card = (run / "scorecard.txt").read_text() if (run / "scorecard.txt").exists() else ""
    card_lines = card.splitlines()
    history = list(csv.DictReader(open(root / "history.csv"))) if (root / "history.csv").exists() else []

    index_rows = []
    for entry in manifest:
        sid = entry["id"]
        slug = sid.replace("/", "_")
        d = run / slug
        body = ["<p><a href=index.html>&larr; all subjects</a></p><h1>%s</h1>" % html.escape(sid)]
        line = next((l for l in card_lines if l.split()[:1] == [sid]), None)
        body.append("<h2>scorecard</h2>" + ("<pre>%s</pre>" % html.escape(line) if line
                    else "<p class=bad>no scorecard line for this subject</p>"))
        bands = json.loads((d / "sheet-bands.json").read_text()) if (d / "sheet-bands.json").exists() else None
        if entry["status"] != "ok":
            body.append("<p class=bad>this run: %s (see %s)</p>" % (html.escape(entry["status"]), html.escape(slug)))
        if bands:
            body.append("<h2>bands</h2><p>%s</p>%s" % (html.escape(bands["summary"]), band_table(bands["bands"])))
        else:
            body.append("<p class=bad>no per-band numbers: the sheet did not write sheet-bands.json</p>")
        body.append("<h2>the sheet and the close-up</h2>")
        images = [i for i in entry.get("images", []) if i.endswith((".jpg", ".png"))]
        if not images:
            body.append("<p class=bad>no images this run</p>")
        for name in sorted(images):
            src = d / name
            if not src.exists():
                body.append("<p class=bad>missing: %s</p>" % html.escape(name))
                continue
            out = site / "img" / ("%s-%s.jpg" % (slug, Path(name).stem))
            small_jpeg(src, out)
            body.append("<img src='img/%s' alt='%s' loading=lazy>" % (out.name, html.escape(name)))
        past = subject_history(root, sid)
        body.append("<h2>history</h2>")
        if len(past) > 1:
            body.append("<div class=wrap><table><tr><th>run</th><th>scorecard line</th></tr>%s</table></div>" % "".join(
                "<tr><td>%s</td><td style='text-align:left'><code>%s</code></td></tr>" % (
                    html.escape(day), html.escape(" ".join(l.split()[1:])) if l else "<span class=bad>not on the card</span>")
                for day, l in past))
        else:
            body.append("<p class=mute>this is the first run on disk for this subject</p>")
        (site / ("%s.html" % slug)).write_text(page(sid, "".join(body)))
        today = bands.get("today_total") if bands else None
        lib = bands.get("derived_total") if bands else None
        index_rows.append("<tr><td><a href='%s.html'>%s</a></td><td class=%s>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            slug, html.escape(sid), "ok" if entry["status"] == "ok" else "bad", html.escape(entry["status"]),
            fmt(today), fmt(lib),
            ("%.0f%%" % (100.0 * (today - lib) / today)) if today and lib is not None else "--"))

    hist = ["<tr>%s</tr>" % "".join("<th>%s</th>" % html.escape(k) for k in ["date", "status", "subjects", "bands",
            "covered_hand", "covered_library", "uncovered", "fully_covered", "fully_from_rung0"])]
    for h in reversed(history[-30:]):
        hist.append("<tr>%s</tr>" % "".join("<td>%s</td>" % html.escape(h.get(k, "")) for k in ["date", "status",
                    "subjects", "bands", "covered_hand", "covered_library", "uncovered", "fully_covered", "fully_from_rung0"]))
    pin = history[-1]["pin"][:12] if history else "?"
    index = ["<h1>the pulse</h1><p class=mute>%s, library at %s</p>" % (html.escape(run.name), html.escape(pin)),
             "<h2>the trend</h2>" + trend_svg(history),
             "<h2>the library's totals, newest first</h2><div class=wrap><table>%s</table></div>" % "".join(hist),
             "<h2>subjects</h2>",
             ("<div class=wrap><table><tr><th>subject</th><th>run</th><th>drawn today</th><th>derived</th><th>saving</th></tr>%s</table></div>"
              % "".join(index_rows)) if index_rows else "<p class=bad>no renders this run</p>",
             "<h2>the scorecard</h2><pre>%s</pre>" % html.escape(card) if card else "<p class=bad>no scorecard this run</p>"]
    (site / "index.html").write_text(page("the pulse", "".join(index)))
    print("site: %d subject page(s) and the index in %s" % (len(manifest), site))


if __name__ == "__main__":
    main(sys.argv)
