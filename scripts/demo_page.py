"""Builds the one-page demo (docs/plan/demo-samsung-marketing.md) from data/demo/*.json.

Run: .venv/bin/python scripts/demo_page.py  → data/demo/sourcemap_demo.html (no network, no keys)
"""

import csv
import html
import json
import re
from collections import defaultdict
from pathlib import Path

from sourcemap.pipeline.demo_search import KNOWN, leaderboard, pool

D = Path("data/demo")
esc = html.escape


def load(name):
    return json.loads((D / name).read_text())


def review_sets():
    kept, reviewed = set(), set()
    p = D / "review.csv"
    if p.exists():
        for row in csv.DictReader(p.open()):
            d = (row.get("decision (keep/reject)") or "").strip().lower()
            if d in ("keep", "reject"):
                reviewed.add(row["candidate"])
                if d == "keep":
                    kept.add(row["candidate"])
    return kept, reviewed


def fmt_metric(m):
    if m is None:
        return '<span class="muted">–</span>'
    if m.state == "failed":
        return '<span class="state">failed</span>'
    if m.lo90 is not None:
        cls = "nd" if m.state == "not_enough_data" else ""
        mean = f"{m.num / m.den:.0%}" if m.den else "–"
        return (f'<span class="{cls}"><b>{int(m.num)}/{int(m.den)}</b> <span class="muted">{mean} · 90% '
                f'[{m.lo90:.2f}, {m.hi90:.2f}]</span></span>')
    if m.metric == "usd_per_good_find":
        return f"${m.mean:.3f}" if m.mean is not None else "–"
    if m.metric == "latency_ms":
        return f"{m.mean / 1000:.1f}s" if m.mean is not None else "–"
    return f"{m.mean if m.mean is not None else m.num}"


def score_cell(s):
    if s["state"] == "unmeasured":
        return '<span class="state">unmeasured</span>'
    lo, hi = s["interval"]
    mean = f"{s['mean']:.2f}" if s["mean"] is not None else "interval only"
    return (f"<b>{mean}</b> <span class='muted'>90% [{lo:.2f}, {hi:.2f}] · n={s['n_decisive']} "
            f"({s['n_correct']} correct, {s['n_wrong']} wrong) · unverifiable {s['unverifiable_share']:.0%}</span>")


def unit_of(resp: str) -> str:
    m = re.match(r"(.*?(?:마케팅실|마케팅팀|마케팅센터|마케팅실|센터|팀|실))", resp)
    u = m.group(1) if m else resp
    return re.sub(r"(장|담당임원)$", "", u).strip()


def main():
    plan = load("plan.json")
    search = load("search.json")
    meas = load("measure.json")
    dart = load("dart_execs.json")
    doc = load("dart_doc.json")
    theorg_raw = load("theorg_raw.json")
    cands = pool(search)
    kept, reviewed = review_sets()
    ms = leaderboard(search, cands, kept, reviewed)
    by = defaultdict(dict)
    for m in ms:
        by[m.provider][m.metric] = m
    spent = search.get("spent_usd", 0)

    # --- planner -----------------------------------------------------------------------------
    plan_html = "".join(
        f"<li><b>{esc(c['name'])}</b> <span class='muted'>— lineage: {esc(c.get('lineage', ''))}</span>"
        f"<ul>{''.join(f'<li><code>{esc(q)}</code></li>' for q in c['queries'])}</ul></li>"
        for c in plan["categories"])
    skipped = "".join(f"<li>{esc(s['name'])} — <span class='muted'>{esc(s['why'])}</span></li>"
                      for s in plan.get("skipped", []))

    # --- leaderboard -------------------------------------------------------------------------
    order = sorted(by, key=lambda p: -(by[p].get("known_hit_rate").num if by[p].get("known_hit_rate") else 0))
    lb_rows = "".join(
        f"<tr><td><b>{esc(p)}</b></td><td>{fmt_metric(by[p].get('known_hit_rate'))}</td>"
        f"<td>{fmt_metric(by[p].get('known_recall'))}</td><td>{fmt_metric(by[p].get('precision'))}</td>"
        f"<td>{fmt_metric(by[p].get('usd_per_good_find'))}</td><td>{fmt_metric(by[p].get('latency_ms'))}</td></tr>"
        for p in order)
    found = "".join(
        f"<tr><td><b>{esc(k)}</b></td><td>{esc(', '.join(sorted(cands[k]['providers'])) if k in cands else 'nobody')}</td></tr>"
        for k in KNOWN)
    review_note = (f"{len(reviewed)} candidates reviewed blind ({len(kept)} kept)." if reviewed else
                   "Blind review not yet filled in: precision counts only the three known sources.")

    # --- source map + drill-down -------------------------------------------------------------
    cov = meas["coverage"]
    sc = meas["scores"]
    checks = sorted(meas["checks"], key=lambda c: (c["dart_index"] is None, c["person"]["name"]))
    rows = []
    for c in checks:
        p = c["person"]
        dr = c["dart_row"]
        dart_txt = f"{dr['name']} · {dr['title']} · {dr['responsibility']}" if dr else "—"
        rows.append(
            f"<tr class='{'' if dr else 'unv'}'><td>{esc(p['name'])}"
            f"{' <span class=tag>marketing</span>' if c['marketing'] else ''}</td>"
            f"<td>{esc(p.get('role') or '')}</td><td lang='ko'>{esc(dart_txt)}</td>"
            f"<td class='v-{c['employment']}'>{c['employment']}</td><td class='v-{c['title']}'>{c['title']}</td>"
            f"<td class='muted'>{esc(c['reason'])}</td></tr>")
    on_theorg = {c["dart_index"]: c["person"]["name"] for c in meas["checks"] if c["marketing"]}

    # --- marketing org chart from DART -------------------------------------------------------
    units = defaultdict(list)
    for r in dart["marketing"]:
        units[unit_of(r["responsibility"])].append(r)
    rank = {"사장": 0, "부사장": 1, "상무": 2}
    idx_of = {json.dumps(r, ensure_ascii=False): i for i, r in enumerate(dart["all"])}
    unit_html = []
    for u, people in sorted(units.items(), key=lambda kv: -len(kv[1])):
        people.sort(key=lambda r: (not r["responsibility"].endswith(("장",)) or "담당임원" in r["responsibility"],
                                   rank.get(r["title"], 9), r["name"]))
        lis = []
        for r in people:
            i = idx_of[json.dumps(r, ensure_ascii=False)]
            head = r["responsibility"].endswith("장") and "담당임원" not in r["responsibility"]
            t = f" <span class=tag>on theorg as {esc(on_theorg[i])}</span>" if i in on_theorg else ""
            lis.append(f"<li class='{'head' if head else ''}'>{esc(r['name'])} <span class='muted'>{esc(r['title'])}"
                       f" · {esc(r['responsibility'])}</span>{t}</li>")
        unit_html.append(f"<details {'open' if len(unit_html) < 2 else ''}><summary><b lang='ko'>{esc(u)}</b> "
                         f"<span class='muted'>{len(people)} executives</span></summary><ul>{''.join(lis)}</ul></details>")

    page = TEMPLATE.format(
        question=esc(plan["question"]), planner_model=esc(plan.get("model", "")), plan_html=plan_html,
        skipped=skipped, n_queries=sum(len(c["queries"]) for c in plan["categories"]),
        n_providers=len(search["providers"]), n_cands=len(cands), spent=f"{spent:.2f}", found=found,
        lb_rows=lb_rows, review_note=esc(review_note),
        emp=score_cell(sc["employment"]), title=score_cell(sc["title"]),
        cov_mk=f"{cov['on_theorg']}/{cov['dart_marketing_execs']}", theorg_people=cov["theorg_people"],
        matched=cov["theorg_matched_to_dart"], dart_execs=cov["dart_execs"], n_mk=cov["dart_marketing_execs"],
        rows="".join(rows), units="".join(unit_html),
        dart_url=esc(doc["viewer_url"]), dart_sha=esc(doc["sha256"][:16]), rcept=esc(doc["rcept_no"]),
        theorg_url=esc(theorg_raw["url"]), theorg_sha=esc(theorg_raw["sha256"][:16]))
    out = D / "sourcemap_demo.html"
    out.write_text(page)
    print(out.resolve())


TEMPLATE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>sourcemap: Samsung marketing</title>
<style>
:root{{--bg:#fbfaf7;--fg:#1d1d1b;--muted:#6b6a64;--line:#e4e1d8;--card:#fff;--accent:#2f5d8a;--ok:#2e7d4f;--bad:#b3412e;--warn:#8a6d1f}}
@media (prefers-color-scheme:dark){{:root{{--bg:#141413;--fg:#ecebe6;--muted:#a3a19a;--line:#2e2d2a;--card:#1c1c1a;--accent:#8fb4dc;--ok:#7cc79a;--bad:#e8907d;--warn:#d9bc6c}}}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 -apple-system,system-ui,Segoe UI,sans-serif}}
main{{max-width:1100px;margin:0 auto;padding:32px 16px 64px}} h1{{font-size:26px;margin:0 0 6px}} h2{{font-size:19px;margin:40px 0 8px}}
.muted{{color:var(--muted)}} .card{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin:12px 0}}
table{{width:100%;border-collapse:collapse;font-size:13.5px}} th,td{{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line);vertical-align:top}}
th{{font-weight:600;color:var(--muted);font-size:12.5px}} .scroll{{overflow-x:auto}} code{{font-size:12.5px}}
.tag{{display:inline-block;font-size:11px;padding:1px 6px;border-radius:9px;background:var(--line);margin-left:4px}}
.state{{font-style:italic;color:var(--muted)}} .nd{{opacity:.85}} .v-correct{{color:var(--ok);font-weight:600}} .v-wrong{{color:var(--bad);font-weight:600}}
.v-unverifiable{{color:var(--muted)}} tr.unv td{{opacity:.75}} li.head{{font-weight:600}} details{{margin:6px 0}} summary{{cursor:pointer}}
.flow{{display:flex;flex-wrap:wrap;gap:8px}} .flow span{{border:1px solid var(--line);border-radius:8px;padding:6px 10px;background:var(--card)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}}
</style></head><body><main>
<h1>Where can I get Samsung Electronics' marketing org chart?</h1>
<p class="muted">{question}</p>
<div class="flow"><span>1 · plan publisher categories</span><span>2 · search every provider via Telem</span>
<span>3 · pool sources</span><span>4 · score providers</span><span>5 · read DART + theorg</span>
<span>6 · match people & check claims</span><span>7 · org chart with evidence</span></div>

<h2>1 · The planner thinks in publishers, not websites</h2>
<div class="card"><p class="muted">One model call ({planner_model}). It names categories and queries — never a site it
expects. DART was found because the planner thought of <i>Korean regulator filings</i>.</p><ol>{plan_html}</ol>
<p><b>Skipped on purpose</b></p><ul>{skipped}</ul></div>

<h2>2 · Which search provider finds the sources? (Telem)</h2>
<div class="card"><p class="muted">{n_queries} queries × {n_providers} providers + Telem auto-routing → {n_cands} candidate
sources, about ${spent} in search. A <b>known-answer trial</b>: for each query in a category that should surface a known
source (regulator filings → DART, crowd-edited sites → theorg, own pages → samsung.com), did the provider return it?
Proportions shown with 90% intervals (Beta(1,1)) — small n, wide intervals. {review_note}</p>
<div class="scroll"><table><tr><th>provider</th><th>known-answer hit rate</th><th>known sources found (of 3)</th>
<th>precision</th><th>$ per good find</th><th>median latency</th></tr>{lb_rows}</table></div>
<p><b>Who found the known sources</b></p><table>{found}</table>
<p class="muted">Search results only <i>find</i> sources. None of them is ever used as evidence for a fact (rule R2).</p></div>

<h2>3 · The source map for Samsung Electronics</h2>
<div class="grid">
<div class="card"><b>DART</b> — official 2025 annual report <span class="tag">tier 1 · reference</span><br>
<span class="muted">{dart_execs} executives, {n_mk} with marketing responsibilities. Used as the reference;
not itself spot-checked today.</span><br><a href="{dart_url}">report {rcept}</a> · raw sha256 <code>{dart_sha}…</code></div>
<div class="card"><b>theorg.com</b> <span class="tag">tier 3 · crowd-edited</span><br>
<span class="muted">Public pages list {theorg_people} Samsung people; {matched} matched to a DART executive.</span><br>
<b>Marketing coverage: {cov_mk}</b> of DART's marketing executives.<br><a href="{theorg_url}">page</a> · raw sha256 <code>{theorg_sha}…</code></div>
<div class="card"><b>LinkedIn · Samsung's own pages</b><br><span class="state">not probed today</span>
<span class="muted"> — never shown as 0%.</span></div></div>
<div class="card"><table><tr><th>theorg claim</th><th>accuracy vs DART (prior Beta(2,1) for crowd-edited)</th></tr>
<tr><td>employment — "works at Samsung"</td><td>{emp}</td></tr>
<tr><td>title</td><td>{title}</td></tr></table>
<p class="muted">Unverifiable ≠ wrong: DART lists executives only, so engineers and managers on theorg can't be checked
against it. They are counted and shown, but never enter accuracy (rule R8).</p></div>

<h2>4 · Every number opens up to its checks</h2>
<div class="card scroll"><p class="muted">Names cross scripts (조성혁 ↔ Seong H. Cho), so every pair was decided by the judge,
which had to quote the DART row it used. A title "wrong" means it disagrees with DART as of 2025-12-31 — theorg may be
newer (e.g. a 2026 reassignment); the page shows it rather than hiding it.</p>
<table><tr><th>theorg person</th><th>theorg role</th><th>DART row (quote)</th><th>employment</th><th>title</th><th>judge's reason</th></tr>
{rows}</table></div>

<h2>5 · Samsung Electronics' marketing org chart (from DART)</h2>
<div class="card"><p class="muted">The {n_mk} executives whose responsibility (담당업무) is marketing, grouped by unit; heads in bold.
Tags show the few theorg also lists. Source: DART annual report {rcept}.</p>{units}</div>

<h2>Honest limits</h2>
<div class="card"><ul>
<li>One company: these are Samsung's numbers, not a segment's.</li>
<li>DART lists executives only, as of 2025-12-31. Below executive level, no source today can check claims.</li>
<li>Reporting lines (reports_to): DART has no manager field → unverifiable.</li>
<li>DART is the reference and was not spot-checked (rule R9 cut for today). Board directors are in another DART table
not parsed today, so Samsung's two co-CEOs show as unverifiable rather than correct.</li>
<li>theorg's public pages expose only the top of Samsung's chart; deeper reports need its private API.</li>
</ul></div>
</main></body></html>"""

if __name__ == "__main__":
    main()
