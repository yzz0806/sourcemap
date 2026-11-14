"""Builds the segment-level marketing org-chart benchmark page from data/seg/*.json.

Run: .venv/bin/python scripts/demo_segments_page.py → data/seg/sourcemap_segments.html (no network)
"""

import html
import json
from collections import defaultdict
from pathlib import Path

from sourcemap.pipeline import demo_multi as M
from sourcemap.pipeline import demo_segments as S

D = Path("data/seg")
esc = html.escape
SEGS = list(S.SEGMENTS)


def load(n):
    return json.loads((D / n).read_text())


def acc(s):
    if s["state"] == "unmeasured":
        return "<span class=st>unmeasured</span>"
    lo, hi = s["interval"]
    head = f"<b>{s['mean']:.2f}</b>" if s["mean"] is not None else "<span class=st>not enough data</span>"
    return f"{head} <span class=m>[{lo:.2f}, {hi:.2f}] n={s['n']}{', %d wrong' % s['n_wrong'] if s['n_wrong'] else ''}</span>"


def main():
    refs, plans, search, verified = load("refs.json"), load("plans.json"), load("search.json"), load("verified.json")
    sources = load("sources.json")
    scost = M.search_cost_by_source(search)

    seg_checks = defaultdict(list)          # (source, seg) -> checks
    seg_cost = defaultdict(float)           # (source, seg) -> usd
    mk_found = defaultdict(set)             # (source, seg) -> {(company, ref_index)} of reference marketing people
    status = defaultdict(lambda: defaultdict(int))  # (source, seg) -> status counts
    for e in verified:
        k, c, seg = e["source"], e["company"], e["segment"]
        seg_cost[(k, seg)] += scost.get((k, c), 0) + e.get("extract_usd", 0) + e.get("verify_usd", 0)
        st = e["status"] if e["status"] in ("ok", "not_found") else "blocked"
        if st == "ok" and not e.get("people"):
            st = "no people"
        status[(k, seg)][st] += 1
        seg_checks[(k, seg)] += e.get("checks", [])
        mi = set(refs.get(c, {}).get("marketing_idx", []))
        for ch in e.get("checks", []):
            if ch["ref_index"] in mi:
                mk_found[(k, seg)].add((c, ch["ref_index"]))
    mk_total = {seg: sum(len(refs.get(c, {}).get("marketing_idx", [])) for c, v in S.COMPANIES.items() if v["segment"] == seg)
                for seg in SEGS}

    def cell(k, seg):
        sc = M.score(seg_checks[(k, seg)], M.tier_of(k, {"own_domains": []}))
        st = status[(k, seg)]
        reads = f"{st.get('ok', 0)}/3 read" + (f" · {st['blocked']} blocked" if st.get("blocked") else "") + \
                (f" · {st['not_found']} not found" if st.get("not_found") else "")
        mk = f"{len(mk_found[(k, seg)])}/{mk_total[seg]} marketing execs" if mk_total[seg] else "reference lists no marketing execs"
        return (f"<td>title {acc(sc['title'])}<br><span class=m>{mk} · {reads} · ${seg_cost[(k, seg)]:.3f}</span></td>")

    head = "".join(f"<th>{esc(S.SEGMENTS[s]['name'])}<br><span class=m>vs {esc(S.SEGMENTS[s]['reference'])}</span></th>"
                   for s in SEGS)
    rows = "".join(f"<tr><td><b>{esc(s['key'])}</b></td>{''.join(cell(s['key'], g) for g in SEGS)}</tr>" for s in sources)

    # best source per segment by title accuracy (measured only), then marketing coverage
    best = []
    for seg in SEGS:
        cand = []
        for s in sources:
            sc = M.score(seg_checks[(s["key"], seg)], M.tier_of(s["key"], {"own_domains": []}))["title"]
            if sc["state"] == "measured":
                cand.append((sc["mean"], len(mk_found[(s["key"], seg)]), s["key"], sc))
        cand.sort(reverse=True)
        if cand:
            m, mk, k, sc = cand[0]
            best.append(f"<li><b>{esc(S.SEGMENTS[seg]['name'])}:</b> {esc(k)} — title {acc(sc)}</li>")
        else:
            best.append(f"<li><b>{esc(S.SEGMENTS[seg]['name'])}:</b> <span class=st>no source has enough checks</span></li>")

    ref_rows = "".join(
        f"<tr><td>{esc(S.SEGMENTS[c['segment']]['name'])}</td><td>{esc(c['name'])}</td>"
        f"<td>{esc(refs.get(slug, {}).get('kind', 'missing'))}</td>"
        f"<td>{len(refs.get(slug, {}).get('rows', []))} people · {len(refs.get(slug, {}).get('marketing_idx', []))} marketing</td>"
        f"<td>{('<a href=' + chr(39) + esc(refs[slug]['url']) + chr(39) + '>source</a>') if refs.get(slug, {}).get('url') else ''}"
        f"{(' · <b>failed:</b> ' + esc(refs[slug].get('failed', ''))[:140]) if refs.get(slug, {}).get('failed') else ''}</td></tr>"
        for slug, c in S.COMPANIES.items())

    plan_html = "".join(
        f"<details><summary><b>{esc(S.SEGMENTS[g]['name'])}</b> · {len(plans[g]['categories'])} categories</summary><ul>"
        + "".join(f"<li>{esc(cat['name'])}<br><span class=m>{' · '.join(esc(q) for q in cat['queries'][:2])}</span></li>"
                  for cat in plans[g]["categories"]) + "</ul></details>" for g in SEGS)

    drill = []
    for e in verified:
        if not e.get("checks"):
            continue
        ref = refs[e["company"]]
        trs = "".join(
            f"<tr><td>{esc(ch['person']['name'])}<br><span class=m>{esc(ch['person']['title'])}</span></td>"
            f"<td class=m>“{esc(ch['person'].get('quote', '')[:130])}”</td><td lang=ko>{esc(ch['ref_quote']) or '—'}</td>"
            f"<td class='v-{ch['employment']}'>{ch['employment']}</td><td class='v-{ch['title']}'>{ch['title']}</td>"
            f"<td class=m>{esc(ch['reason'][:130])}</td></tr>" for ch in e["checks"])
        n_ok = sum(ch["employment"] == "correct" for ch in e["checks"])
        drill.append(f"<details><summary><b>{esc(e['source'])}</b> × {esc(S.COMPANIES[e['company']]['name'])} "
                     f"<span class=m>({esc(S.SEGMENTS[e['segment']]['name'])}) — {n_ok}/{len(e['checks'])} confirmed · "
                     f"<a href='{esc(e['url'])}'>page</a> · raw <code>{esc(e.get('sha256', '')[:12])}…</code> · reference: "
                     f"{esc(ref['kind'])}</span></summary><div class=scroll><table><tr><th>person on source</th>"
                     f"<th>quote on saved page</th><th>reference row</th><th>employment</th><th>title</th><th>reason</th></tr>"
                     f"{trs}</table></div></details>")

    total = search["spent_usd"] + sum(e.get("extract_usd", 0) + e.get("verify_usd", 0) for e in verified)
    out = D / "sourcemap_segments.html"
    out.write_text(TEMPLATE.format(head=head, rows=rows, best="".join(best), ref_rows=ref_rows, plan_html=plan_html,
                                   drill="".join(drill), n_calls=len(search["rows"]), total=f"{total:.2f}",
                                   n_sources=len(sources)))
    print(out.resolve())


TEMPLATE = """<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width, initial-scale=1">
<title>sourcemap: marketing org charts by segment</title><style>
:root{{--bg:#fbfaf7;--fg:#1d1d1b;--m:#6b6a64;--line:#e4e1d8;--card:#fff;--ok:#2e7d4f;--bad:#b3412e}}
@media (prefers-color-scheme:dark){{:root{{--bg:#141413;--fg:#ecebe6;--m:#a3a19a;--line:#2e2d2a;--card:#1c1c1a;--ok:#7cc79a;--bad:#e8907d}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 -apple-system,system-ui,Segoe UI,sans-serif}}
main{{max-width:1180px;margin:0 auto;padding:32px 16px 64px}}h1{{font-size:26px;margin:0 0 6px}}h2{{font-size:19px;margin:36px 0 8px}}
.m{{color:var(--m);font-size:12.5px}}.st{{font-style:italic;color:var(--m)}}.card{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:10px 0}}
table{{width:100%;border-collapse:collapse;font-size:13.5px}}th,td{{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line);vertical-align:top}}
th{{color:var(--m);font-weight:600;font-size:12.5px}}.scroll{{overflow-x:auto}}.v-correct{{color:var(--ok);font-weight:600}}.v-wrong{{color:var(--bad);font-weight:600}}
.v-unverifiable{{color:var(--m)}}details{{margin:6px 0}}summary{{cursor:pointer}}code{{font-size:12px}}
.flow{{display:flex;flex-wrap:wrap;gap:8px}}.flow span{{border:1px solid var(--line);border-radius:8px;padding:6px 10px;background:var(--card)}}
</style></head><body><main>
<h1>Where can I get a company's marketing org chart — and which source can I trust, by segment?</h1>
<p class=m>Three segments, three companies each, one reference type per segment. Fully automatic: the planner plans
publisher categories per segment, Telem searches every provider ({n_calls} calls), {n_sources} sources are picked, read raw,
and every person is checked against the segment's reference. Cost of these results ${total}.</p>
<div class=flow><span>1 plan per segment</span><span>2 search via Telem</span><span>3 pick sources found for ≥3 companies</span>
<span>4 read & extract (quotes checked)</span><span>5 verify vs segment reference</span><span>6 score per segment</span></div>

<h2>Best source per segment (title accuracy, measured cells only)</h2><div class=card><ul>{best}</ul></div>

<h2>Source map — sources × segments</h2>
<div class="card scroll"><table><tr><th>source</th>{head}</tr>{rows}</table>
<p class=m>Each cell: title accuracy (Beta posterior with tier prior, 90% interval, n), how many of the reference's marketing
executives the source names, how many of the segment's companies could be read, and the cost (search share + reading + checking).
"Blocked" = the site refuses automated reading; never counted as 0%.</p></div>

<h2>What "verified" means per segment</h2>
<div class="card scroll"><table><tr><th>segment</th><th>company</th><th>reference</th><th>size</th><th>evidence</th></tr>{ref_rows}</table>
<p class=m><b>The finding behind the map:</b> official data goes deep in Korea (DART lists every executive with their
responsibility, down to marketing VPs) and stops at the top elsewhere (SEC lists ~5 executive officers; European
companies publish board/committee pages). So outside Korea, almost every marketing claim is <i>unverifiable</i> — not wrong.</p></div>

<h2>The planner, per segment</h2><div class=card>{plan_html}</div>
<h2>Every number opens up to its checks</h2><div class=card>{drill}</div>
<h2>Honest limits</h2><div class=card><ul>
<li>Three companies per segment: intervals are wide; the numbers describe these panels.</li>
<li>Employment can only be confirmed, never refuted, with these references (absent ≠ wrong); title accuracy is the number that can expose errors.</li>
<li>SAP has no reference: sap.com's robots.txt forbids automated reading.</li>
<li>Extraction and matching are model calls with quotes; the judge's own error rate is not measured against humans.</li>
<li>Points in time differ: filings are as of their report date; web pages as of today.</li>
</ul></div></main></body></html>"""

if __name__ == "__main__":
    main()
