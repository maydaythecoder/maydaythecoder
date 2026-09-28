"""Pick a random snippet from the user's public repos (stable per day) and render it as an SVG."""
import base64
import datetime as dt
import json
import os
import random
import re
import sys
import urllib.parse
import urllib.request
from xml.sax.saxutils import escape

USER = os.environ.get("GH_USER", "maydaythecoder")
TOKEN = os.environ.get("GH_TOKEN", "")
OUT = sys.argv[1] if len(sys.argv) > 1 else "code-snippet.svg"
LINES, MAX_COLS = 16, 88

LANGS = {".ts": "TypeScript", ".tsx": "TypeScript", ".js": "JavaScript", ".jsx": "JavaScript", ".py": "Python",
         ".rs": "Rust", ".dart": "Dart", ".java": "Java", ".go": "Go", ".kt": "Kotlin", ".swift": "Swift",
         ".c": "C", ".cpp": "C++", ".cs": "C#", ".rb": "Ruby", ".php": "PHP"}
SKIP_PATH = re.compile(r"(^|/)(node_modules|dist|build|out|vendor|\.next|coverage|generated|migrations)/|\.min\.|\.d\.ts$")
SECRET = re.compile(r"(api[_-]?key|secret|token|passw(or)?d|private[_-]?key|bearer)\s*[:=]", re.I)
KEYWORDS = set("""abstract as async await break case catch class const continue def default del do elif else enum export
extends final finally fn for from func function if impl implements import in interface is lambda let match mod mut new
not or and pass private protected pub public raise return self static struct super switch this throw trait try type
typeof use var void while with yield None True False null undefined true false""".split())

# github-dark palette
BG, BORDER, FG, DIM, TITLE = "#0d1117", "#30363d", "#c9d1d9", "#6e7681", "#58a6ff"
KW, STR, COM, NUM = "#ff7b72", "#a5d6ff", "#8b949e", "#79c0ff"


def api(path):
    req = urllib.request.Request(f"https://api.github.com{path}", headers={
        "Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def pick_window(lines, rng):
    starts = list(range(0, max(1, len(lines) - LINES + 1)))
    rng.shuffle(starts)
    for s in starts:
        win = lines[s:s + LINES]
        if sum(1 for l in win if l.strip()) < LINES * 0.6 or not win[0].strip():
            continue
        if any(SECRET.search(l) for l in win):
            continue
        return s, win
    return None


def fetch():
    rng = random.Random(dt.date.today().isoformat())
    repos = [r for r in api(f"/users/{USER}/repos?type=owner&per_page=100&sort=pushed")
             if not (r["fork"] or r["archived"] or r["private"]) and r["size"] > 0]
    rng.shuffle(repos)
    for repo in repos[:25]:
        try:
            tree = api(f"/repos/{repo['full_name']}/git/trees/{urllib.parse.quote(repo['default_branch'])}?recursive=1")
        except Exception:
            continue
        files = [t for t in tree.get("tree", []) if t["type"] == "blob" and 300 < t.get("size", 0) < 60000
                 and os.path.splitext(t["path"])[1] in LANGS and not SKIP_PATH.search(t["path"])]
        rng.shuffle(files)
        for f in files[:5]:
            blob = api(f"/repos/{repo['full_name']}/git/blobs/{f['sha']}")
            try:
                text = base64.b64decode(blob["content"]).decode("utf-8")
            except (UnicodeDecodeError, KeyError):
                continue
            found = pick_window(text.expandtabs(4).splitlines(), rng)
            if found:
                start, win = found
                return {"repo": repo["full_name"], "path": f["path"], "start": start + 1, "lines": win,
                        "lang": LANGS[os.path.splitext(f["path"])[1]]}
    raise SystemExit("no suitable snippet found")


TOKEN_RE = re.compile(r"(?P<com>//.*|#.*)|(?P<str>\"(?:\\.|[^\"\\])*\"?|'(?:\\.|[^'\\])*'?|`[^`]*`?)"
                      r"|(?P<num>\b\d[\d_.xa-fA-F]*\b)|(?P<word>[A-Za-z_]\w*)|(?P<other>.)")


def highlight(line, lang):
    out = []
    for m in TOKEN_RE.finditer(line):
        kind, text = m.lastgroup, m.group()
        if kind == "com" and text.startswith("#") and lang not in ("Python", "Ruby"):
            kind = "other"
        color = {"com": COM, "str": STR, "num": NUM}.get(kind)
        if kind == "word" and text in KEYWORDS:
            color = KW
        out.append(f'<tspan fill="{color}">{escape(text)}</tspan>' if color else escape(text))
    return "".join(out)


def render(s):
    body = s["lines"]
    indent = min((len(l) - len(l.lstrip()) for l in body if l.strip()), default=0)
    body = [l[indent:] for l in body]
    body = [l if len(l) <= MAX_COLS else l[:MAX_COLS - 1] + "…" for l in body]
    lh, top, w = 19, 78, 820
    h = top + lh * len(body) + 20
    end = s["start"] + len(body) - 1
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
           f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="6" fill="{BG}" stroke="{BORDER}"/>',
           f'<text x="20" y="32" fill="{TITLE}" font-family="Segoe UI, Ubuntu, sans-serif" font-size="17" '
           f'font-weight="600">Code snippet of the day</text>',
           f'<text x="20" y="54" fill="{DIM}" font-family="Segoe UI, Ubuntu, sans-serif" font-size="13">'
           f'{escape(s["repo"])} · {escape(s["path"])} · L{s["start"]}–{end} · {escape(s["lang"])}</text>',
           f'<line x1="0" x2="{w}" y1="66" y2="66" stroke="{BORDER}"/>',
           '<g font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" font-size="13" '
           'style="white-space:pre">']
    for i, line in enumerate(body):
        y = top + lh * i + 13
        out.append(f'<text x="50" y="{y}" fill="{DIM}" text-anchor="end">{s["start"] + i}</text>')
        out.append(f'<text x="64" y="{y}" fill="{FG}" xml:space="preserve">{highlight(line, s["lang"])}</text>')
    out.append("</g></svg>")
    return "\n".join(out)


if __name__ == "__main__":
    snippet = json.loads(os.environ["FAKE_DATA"]) if os.environ.get("FAKE_DATA") else fetch()
    with open(OUT, "w") as f:
        f.write(render(snippet))
    print(f"wrote {OUT}: {snippet['repo']}/{snippet['path']} L{snippet['start']}")
