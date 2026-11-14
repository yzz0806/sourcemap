"""Writes one self-contained HTML file with the Samsung Electronics marketing org chart (from DART).

Output: web/dist/samsung-marketing-orgchart.html — data, styles and chart code inline, so it opens
directly in any browser (no search step, no other files). Run after scripts/build_web.py.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "web/dist"


def main():
    data = (DIST / "data.js").read_text()
    answer = json.loads(data[data.index("=") + 1:].rstrip().rstrip(";"))["samsung_answer"]
    css = (ROOT / "web/style.css").read_text() + "\n" + (ROOT / "web/dartchart.css").read_text()
    js = (ROOT / "web/dartchart.js").read_text()
    n = sum(len(u["people"]) for u in answer["units"])
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Samsung Electronics marketing org chart</title>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@600&display=swap" rel="stylesheet">
<style>{css}</style></head>
<body>
<header class="top"><div class="wrap bar"><span class="brand">sourcemap</span></div></header>
<main class="wrap">
  <section class="hero" style="border-bottom:0;padding-bottom:0">
    <p class="label">ORG CHART · FROM DART</p>
    <h1>Samsung Electronics — marketing org chart</h1>
    <p class="lede">{n} marketing executives in {len(answer['units'])} units, from Samsung Electronics' 2025 annual report filed with
      DART (<a href="{answer['url']}">{answer['rcept_no']}</a>), as of 2025-12-31. The structure comes from each executive's
      responsibility (담당업무). English names: a source's own spelling, otherwise romanized (marked *).</p>
  </section>
  <div id="chart"></div>
</main>
<footer class="wrap foot">sourcemap · data: DART (official filing) · LinkedIn links found by search, not verified</footer>
<script>window.ANSWER = {json.dumps(answer, ensure_ascii=False)};</script>
<script>{js}</script>
<script>window.renderDartChart(document.getElementById("chart"), window.ANSWER);</script>
</body></html>"""
    out = DIST / "samsung-marketing-orgchart.html"
    out.write_text(html)
    print(out)


if __name__ == "__main__":
    main()
