"""Render a contribution activity graph SVG from the GitHub GraphQL API."""
import datetime as dt
import json
import os
import sys
import urllib.request

USER = os.environ.get("GH_USER", "maydaythecoder")
TOKEN = os.environ.get("GH_TOKEN", "")
DAYS = int(os.environ.get("DAYS", "31"))
OUT = sys.argv[1] if len(sys.argv) > 1 else "activity-graph.svg"

# merko-like palette
BG, TITLE, AXIS, LINE, AREA, POINT, GRID = "#0a0f0b", "#b7d364", "#b7d364", "#b7d364", "#5eab35", "#abd200", "#1e2a1f"
W, H, PAD_L, PAD_R, PAD_T, PAD_B = 1000, 360, 60, 30, 60, 50

QUERY = """query($login:String!,$from:DateTime!,$to:DateTime!){user(login:$login){
contributionsCollection(from:$from,to:$to){contributionCalendar{weeks{contributionDays{date contributionCount}}}}}}"""


def fetch(days):
    to = dt.datetime.now(dt.timezone.utc)
    frm = to - dt.timedelta(days=days - 1)
    body = json.dumps({"query": QUERY, "variables": {
        "login": USER, "from": frm.strftime("%Y-%m-%dT00:00:00Z"), "to": to.strftime("%Y-%m-%dT%H:%M:%SZ")}}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=body,
                                 headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errors" in data:
        raise SystemExit(f"GraphQL error: {data['errors']}")
    weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return [(d["date"], d["contributionCount"]) for w in weeks for d in w["contributionDays"]][-days:]


def render(points):
    n, peak = len(points), max(c for _, c in points)
    top = max(4, peak + (-peak % 4))  # round up to a multiple of 4 for clean gridlines
    pw, ph = W - PAD_L - PAD_R, H - PAD_T - PAD_B
    xy = [(PAD_L + i * pw / max(n - 1, 1), PAD_T + ph - c / top * ph) for i, (_, c) in enumerate(points)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in xy)
    area = f"{PAD_L},{PAD_T + ph} {line} {PAD_L + pw},{PAD_T + ph}"
    total = sum(c for _, c in points)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
           f'font-family="Segoe UI, Ubuntu, sans-serif">',
           f'<rect width="{W}" height="{H}" rx="6" fill="{BG}" stroke="#e4e2e2" stroke-opacity="0.2"/>',
           f'<text x="{W / 2}" y="34" fill="{TITLE}" font-size="20" text-anchor="middle">'
           f'{USER}\'s Contribution Graph · {total} in the last {n} days</text>']
    for i in range(5):
        v = top * i / 4
        y = PAD_T + ph - v / top * ph
        out.append(f'<line x1="{PAD_L}" x2="{PAD_L + pw}" y1="{y:.1f}" y2="{y:.1f}" stroke="{GRID}"/>')
        out.append(f'<text x="{PAD_L - 10}" y="{y + 4:.1f}" fill="{AXIS}" font-size="12" text-anchor="end">{v:g}</text>')
    for i, (date, _) in enumerate(points):
        if i % 2 == 0:
            out.append(f'<text x="{xy[i][0]:.1f}" y="{H - PAD_B + 20}" fill="{AXIS}" font-size="11" '
                       f'text-anchor="middle">{int(date[-2:])}</text>')
    out.append(f'<text x="{W / 2}" y="{H - 8}" fill="{AXIS}" font-size="12" text-anchor="middle">Days</text>')
    out.append(f'<polygon points="{area}" fill="{AREA}" fill-opacity="0.35"/>')
    out.append(f'<polyline points="{line}" fill="none" stroke="{LINE}" stroke-width="2" stroke-linejoin="round"/>')
    for (x, y), (date, c) in zip(xy, points):
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{POINT}"><title>{date}: {c}</title></circle>')
    out.append("</svg>")
    return "\n".join(out)


if __name__ == "__main__":
    pts = json.loads(os.environ["FAKE_DATA"]) if os.environ.get("FAKE_DATA") else fetch(DAYS)
    with open(OUT, "w") as f:
        f.write(render(pts))
    print(f"wrote {OUT} ({len(pts)} days)")
