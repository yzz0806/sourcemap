"""Builds the multi-segment source benchmark page from data/multi/*.json.

Run: .venv/bin/python scripts/demo_multi_page.py → data/multi/sourcemap_benchmark.html (no network)
"""

import html
import json
from collections import defaultdict
from pathlib import Path

from sourcemap.pipeline import demo_multi as M

D = Path("data/multi")
esc = html.escape
COMP = list(M.COMPANIES)


def load(n):
    return json.loads((D / n).read_text())


def top_set(slug, rows):
    if slug == "samsung-electronics":  # comparable "top leadership": board + president level and above
        return {i for i, r in enumerate(rows) if r.get("table") or r["title"] in ("회장", "부회장", "사장")}
    return set(range(len(rows)))


def acc_cell(s):
    if s["state"] == "unmeasured":
        return "<span class=st>unmeasured</span>"
    lo, hi = s["interval"]
    head = f"<b>{s['mean']:.2f}</b>" if s["mean"] is not None else "<span class=st>not enough data</span>"
    return f"{head}<br><span class=m>90% [{lo:.2f}, {hi:.2f}] · n={s['n']} ({s['n_wrong']} wrong)</span>"


def main():
    refs, plans, search, verified = load("refs.json"), load("plans.json"), load("search.json"), load("verified.json")
    sources = load("sources.json")
    scost = M.search_cost_by_source(search)

    # --- per (source, company) -----------------------------------------------------------------
    cell, pooled, cost = {}, defaultdict(list), defaultdict(float)
    for e in verified:
        k, c = e["source"], e["company"]
        rows = refs[c]["rows"]
        top = top_set(c, rows)
        matched = {ch["ref_index"] for ch in e.get("checks", []) if ch["ref_index"] is not None}
        usd = scost.get((k, c), 0) + e.get("extract_usd", 0) + e.get("verify_usd", 0)
        cost[k] += usd
        cell[(k, c)] = {"status": e["status"], "people": len(e.get("people", [])), "matched": len(matched),
                        "top_cov": (len(matched & top), len(top)), "usd": usd, "url": e.get("url"),
                        "url_from": e.get("url_from"), "sha": e.get("sha256", ""), "checks": e.get("checks", [])}
        pooled[k] += e.get("checks", [])

    # --- source leaderboard ------------------------------------------------------------------------
    board = []
    for s in sources:
        k = s["key"]
        tier = M.tier_of(k, {"own_domains": []})
        sc = M.score(pooled[k], tier)
        correct = sum(1 for ch in pooled[k] if ch["employment"] == "correct")
        ok_companies = sum(1 for c in COMP if cell.get((k, c), {}).get("status") == "ok" and cell[(k, c)]["people"])
        board.append((k, tier, sc, ok_companies, correct, cost[k]))
    board.sort(key=lambda b: (-(b[2]["employment"]["mean"] or 0), -b[4]))

    lb = "".join(
        f"<tr><td><b>{esc(k)}</b><br><span class=m>tier {int(t)} prior Beta{tuple(sc['employment']['prior'])}</span></td>"
        f"<td>{acc_cell(sc['employment'])}</td><td>{acc_cell(sc['title'])}</td>"
        f"<td>{oc}/3 companies<br><span class=m>{n} verified people</span></td>"
        f"<td>${c:.3f}<br><span class=m>{'$%.4f per verified person' % (c / n) if n else 'no verified person'}</span></td></tr>"
        for k, t, sc, oc, n, c in board)

    # --- companies × sources map -----------------------------------------------------------------
    def map_cell(k, c):
        x = cell.get((k, c))
        if not x or x["status"] == "not_found":
            return "<td class=nf>not found by search</td>"
        if x["status"] != "ok":
            return f"<td class=fail>{esc(x['status'].replace('failed: ', 'blocked · '))}</td>"
        if not x["people"]:
            return "<td class=nf>read · no people on page</td>"
        a, b = x["top_cov"]
        return (f"<td><b>{a}/{b}</b> top leaders<br><span class=m>{x['matched']}/{x['people']} people verified"
                f"{' · <i>URL from earlier search</i>' if x['url_from'] and 'earlier' in x['url_from'] else ''}</span></td>")

    head = "".join(f"<th>{esc(M.COMPANIES[c]['name'])}<br><span class=m>{esc(M.COMPANIES[c]['segment'])}</span></th>" for c in COMP)
    mp = "".join(f"<tr><td><b>{esc(s['key'])}</b></td>{''.join(map_cell(s['key'], c) for c in COMP)}</tr>" for s in sources)

    # --- references -------------------------------------------------------------------------------
    ref_rows = "".join(
        f"<tr><td>{esc(M.COMPANIES[c]['name'])}</td><td>{esc(M.COMPANIES[c]['segment'])}</td><td>{esc(refs[c]['kind'])}</td>"
        f"<td>{len(refs[c]['rows'])} people · top leadership {len(top_set(c, refs[c]['rows']))}</td>"
        f"<td><a href='{esc(refs[c]['url'])}'>source</a> · <code>{esc(refs[c]['sha256'][:12])}…</code></td></tr>" for c in COMP)

    # --- providers ----------------------------------------------------------------------------------
    prov = defaultdict(lambda: {"usd": 0.0, "found": set(), "lat": []})
    picked = {s["key"] for s in sources}
    for row in search["rows"]:
        for run in row["runs"]:
            p = prov[run["provider"]]
            p["usd"] += run["usd"]
            if run["latency_ms"]:
                p["lat"].append(run["latency_ms"])
            for h in run["hits"]:
                if M.source_key(h["url"]) in picked:
                    p["found"].add((M.source_key(h["url"]), row["company"]))
    prov_rows = "".join(
        f"<tr><td><b>{esc(p)}</b></td><td>{len(v['found'])}</td><td>${v['usd']:.3f}</td>"
        f"<td>{(sorted(v['lat'])[len(v['lat']) // 2] / 1000 if v['lat'] else 0):.1f}s</td></tr>"
        for p, v in sorted(prov.items(), key=lambda kv: -len(kv[1]["found"])))

    # --- planners -----------------------------------------------------------------------------------
    plan_html = "".join(
        f"<details><summary><b>{esc(M.COMPANIES[c]['name'])}</b> · {len(plans[c]['categories'])} categories</summary><ul>"
        + "".join(f"<li>{esc(cat['name'])}<br><span class=m>{' · '.join(esc(q) for q in cat['queries'][:2])}</span></li>"
                  for cat in plans[c]["categories"]) + "</ul></details>" for c in COMP)

    # --- drill-down -----------------------------------------------------------------------------------
    drill = []
    for s in sources:
        for c in COMP:
            x = cell.get((s["key"], c))
            if not x or not x["checks"]:
                continue
            trs = "".join(
                f"<tr><td>{esc(ch['person']['name'])}<br><span class=m>{esc(ch['person']['title'])}</span></td>"
                f"<td class=m>“{esc(ch['person'].get('quote', '')[:140])}”</td>"
                f"<td lang=ko>{esc(ch['ref_quote']) or '—'}</td>"
                f"<td class='v-{ch['employment']}'>{ch['employment']}</td><td class='v-{ch['title']}'>{ch['title']}</td>"
                f"<td class=m>{esc(ch['reason'][:140])}</td></tr>" for ch in x["checks"])
            drill.append(f"<details><summary><b>{esc(s['key'])}</b> × {esc(M.COMPANIES[c]['name'])} — "
                         f"{x['matched']}/{x['people']} verified · <a href='{esc(x['url'])}'>page</a> · raw "
                         f"<code>{esc(x['sha'][:12])}…</code></summary><div class=scroll><table><tr><th>person on source</th>"
                         f"<th>quote on the saved page</th><th>reference row (quote)</th><th>employment</th><th>title</th>"
                         f"<th>judge's reason</th></tr>{trs}</table></div></details>")

    total_search = search["spent_usd"]
    total = total_search + sum(e.get("extract_usd", 0) + e.get("verify_usd", 0) for e in verified)
    page = TEMPLATE.format(ref_rows=ref_rows, lb=lb, head=head, mp=mp, prov_rows=prov_rows, plan_html=plan_html,
                           drill="".join(drill), n_sources=len(sources), total=f"{total:.2f}",
                           search=f"{total_search:.2f}", n_calls=len(search["rows"]))
    out = D / "sourcemap_benchmark.html"
    out.write_text(page)
    print(out.resolve())


TEMPLATE = """<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width, initial-scale=1">
<title>sourcemap: source benchmark</title><style>
:root{{--bg:#fbfaf7;--fg:#1d1d1b;--m:#6b6a64;--line:#e4e1d8;--card:#fff;--ok:#2e7d4f;--bad:#b3412e;--nf:#f3f1ea}}
@media (prefers-color-scheme:dark){{:root{{--bg:#141413;--fg:#ecebe6;--m:#a3a19a;--line:#2e2d2a;--card:#1c1c1a;--ok:#7cc79a;--bad:#e8907d;--nf:#22211f}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 -apple-system,system-ui,Segoe UI,sans-serif}}
main{{max-width:1150px;margin:0 auto;padding:32px 16px 64px}}h1{{font-size:26px;margin:0 0 6px}}h2{{font-size:19px;margin:36px 0 8px}}
.m{{color:var(--m);font-size:12.5px}}.st{{font-style:italic;color:var(--m)}}.card{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:10px 0}}
table{{width:100%;border-collapse:collapse;font-size:13.5px}}th,td{{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line);vertical-align:top}}
th{{color:var(--m);font-weight:600;font-size:12.5px}}.scroll{{overflow-x:auto}}td.nf{{background:var(--nf);color:var(--m);font-style:italic}}
td.fail{{background:var(--nf);color:var(--bad);font-size:12.5px}}.v-correct{{color:var(--ok);font-weight:600}}.v-wrong{{color:var(--bad);font-weight:600}}
.v-unverifiable{{color:var(--m)}}details{{margin:6px 0}}summary{{cursor:pointer}}code{{font-size:12px}}
.flow{{display:flex;flex-wrap:wrap;gap:8px}}.flow span{{border:1px solid var(--line);border-radius:8px;padding:6px 10px;background:var(--card)}}
</style></head><body><main>
<h1>Which org-chart sources can you trust — by segment?</h1>
<p class=m>Fully automatic: a planner thinks in publisher categories, Telem searches every provider, sources are picked,
read, and every claim is checked against each segment's reference. Total cost ${total} (search ${search}).</p>
<div class=flow><span>1 plan</span><span>2 search via Telem ({n_calls} calls)</span><span>3 pick {n_sources} sources</span>
<span>4 read & extract (quotes checked)</span><span>5 verify vs reference</span><span>6 accuracy · coverage · cost</span></div>

<h2>The references — what "verified" means per segment</h2>
<div class="card scroll"><table><tr><th>company</th><th>segment</th><th>reference</th><th>size</th><th>evidence</th></tr>{ref_rows}</table>
<p class=m>Korea is checked against an official filing (DART, tier 1). The US and Europe are checked against the company's
own page (tier 2), which lists only top leaders — a weaker reference. People missing from a reference are
<i>unverifiable</i>, never wrong.</p></div>

<h2>Source leaderboard</h2>
<div class="card scroll"><table><tr><th>source</th><th>employment accuracy</th><th>title accuracy</th><th>coverage</th><th>cost</th></tr>{lb}</table>
<p class=m>Accuracy: Beta posterior with a tier prior, 90% interval, n decisive checks (stage 1 rules, ADR 0002); fewer than 5 →
"not enough data", none → "unmeasured". Cost = this source's share of search + reading + checking.</p></div>

<h2>Companies × sources</h2>
<div class="card scroll"><table><tr><th>source</th>{head}</tr>{mp}</table>
<p class=m>"Top leaders" = Samsung's board and president-level executives; everyone on Nvidia's and Airbus's own pages.
"Blocked" = the site refused automated reading (HTTP 403) — a real property of the source, not 0% coverage.</p></div>

<h2>Search providers (Telem)</h2>
<div class="card scroll"><table><tr><th>provider</th><th>(source, company) pairs found</th><th>cost</th><th>median latency</th></tr>{prov_rows}</table></div>

<h2>The planner's categories</h2><div class=card>{plan_html}</div>

<h2>Every number opens up to its checks</h2><div class=card>{drill}</div>

<h2>Honest limits</h2><div class=card><ul>
<li>One company per segment: these numbers describe Samsung, Nvidia and Airbus, not whole segments.</li>
<li>US and Europe references are the companies' own pages (top leaders only); deeper claims there are unverifiable.</li>
<li>Sources were picked automatically (found for ≥ 2 companies), not reviewed by a person.</li>
<li>Extraction and matching are model calls; every extracted person quotes the saved page, every match quotes the reference row.
The judge's own error rate is not measured against humans.</li>
<li><b>Employment accuracy can only go up here:</b> a person missing from a reference is unverifiable (the reference
lists top leaders or executives only), never wrong. So it shows how many claims were confirmed; <b>title accuracy is the
number that can expose errors</b>.</li>
<li>Points in time differ: DART is as of 2025-12-31; web pages as of today. A "wrong" title may be a later change.</li>
</ul></div>
</main></body></html>"""

if __name__ == "__main__":
    main()
