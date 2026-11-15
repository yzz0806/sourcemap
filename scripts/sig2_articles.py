"""Runs the v2 article-source checks: every filed change × 5 sources → data/sig2/checks_articles.json.

  .venv/bin/python scripts/sig2_articles.py [--budget 1.6]
Searches are cached in data/sig2/search_cache.json and page reads in data/sig2/page_cache.json, so a
re-run (or a resumed run) never pays twice.
"""

import json
import statistics
import sys
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from sourcemap.cli import load_env
from sourcemap.pipeline import demo_multi as M
from sourcemap.pipeline import sig_sources as G
from sourcemap.pipeline.sig2_articles import SOURCES, on_site, query, site_prefix
from sourcemap.pipeline.sig_measure import _d, match_event
from sourcemap.sandbox.kit import BlockedByRobots, FetchError, Kit
from sourcemap.services.llm import JUDGE_MODEL, LLM
from sourcemap.services.websearch import Telem
from sourcemap.store.rawstore import RawStore

D = Path("data/sig2")
SEARCH_CACHE, PAGE_CACHE, OUT = D / "search_cache.json", D / "page_cache.json", D / "checks_articles.json"


def listing(url: str) -> bool:
    """Index / listing pages (page=…, pagesize=…, /news/<company>/ hubs) are not articles about one change."""
    u = url.lower()
    return "page=" in u or "pagesize=" in u or u.rstrip("/").endswith(("/news", "/newsroom", "/press-releases"))


def load(p, default):
    return json.loads(p.read_text()) if p.exists() else default


def main(budget=1.6):
    env = load_env(Path(".env"))
    refs = json.loads((D / "refs.json").read_text())
    cos = refs["companies"]
    scache, pcache = load(SEARCH_CACHE, {}), load(PAGE_CACHE, {})
    telem = Telem(env["TELEM_API_KEY"], budget_usd=budget)
    llm = LLM(env["OPENROUTER_API_KEY"], Path("data/llm_cache"), budget_usd=1.5)
    tls = threading.local()  # one polite Kit per worker thread (per-host spacing within each)
    lock = threading.Lock()

    def kit():
        if not hasattr(tls, "kit"):
            tls.kit = Kit(min_interval_s=1.0, max_retries=2, timeout_s=30)
        return tls.kit
    raw = RawStore("data/raw")
    spent = lambda: telem.spent_usd + llm.spent_usd  # noqa: E731

    def search(q, provider):
        key = f"{provider}|{q}"
        if key in scache:
            return scache[key], 0.0
        before = telem.spent_usd
        res = telem.search(q, providers=[provider], num_results=5)
        hits = [{"url": h.url, "title": h.title, "rank": h.rank} for r in res.runs for h in r.hits]
        scache[key] = hits
        return hits, telem.spent_usd - before

    def read(url, slug):
        key = f"{slug}|{url}"
        if key in pcache:
            return pcache[key], 0.0
        entry = {"status": "ok", "published": None, "events": [], "sha": None}
        before = llm.spent_usd
        try:
            r = kit().get(url)
            entry["sha"] = raw.put(r.body)
            ctype = r.headers.get("Content-Type", r.headers.get("content-type", "html"))
            if r.status != 200 or "html" not in ctype:
                entry["status"] = f"failed: HTTP {r.status}"
            else:
                html = r.text()
                entry["published"], _ = G.published(html)
                text = M.html_to_text(html, limit=15000)
                ans = llm.ask_json(JUDGE_MODEL, "sig_src_extract/v1", G.EXTRACT_PROMPT.format(company=cos[slug]["name"]), text, max_tokens=3000)
                tn = G.norm(text)
                entry["events"] = [e for e in (ans.get("events") or []) if isinstance(e, dict) and e.get("person") and G.event_ok(e, tn)]
        except BlockedByRobots:
            entry["status"] = "blocked_by_robots"
        except (FetchError, OSError) as e:
            entry["status"] = f"failed: {type(e).__name__}"
        except Exception as e:  # noqa: BLE001 — a judge/parse failure must not stop the run
            entry["status"] = f"failed: {type(e).__name__}"
        pcache[key] = entry
        return entry, llm.spent_usd - before

    events = refs["events"]
    jobs = [(ev, src) for ev in events for src in SOURCES]

    def check(job):
        ev, src = job
        slug = ev["company"]
        rec = {"event_id": ev["id"], "company": slug, "source": src, "status": "not_found", "verdict": None,
               "date": None, "days_late": None, "url": None, "evidence": None, "quote": None, "usd": 0.0}
        if spent() >= budget - 0.02:
            rec["status"] = "error"
            return rec
        prefix = site_prefix(src, cos[slug].get("newsroom", ""))
        q = query(ev, cos[slug]["name"], prefix)
        try:
            hits, usd = search(q, "parallel")
            rec["usd"] += usd
            on = [h for h in hits if on_site(h["url"], prefix) and not listing(h["url"])]
            if not on:  # the cheap provider found nothing on this site: one fallback provider
                hits, usd = search(q, "exa")
                rec["usd"] += usd
                on = [h for h in hits if on_site(h["url"], prefix) and not listing(h["url"])]
        except Exception as e:  # noqa: BLE001
            rec["status"] = "error"
            rec["quote"] = str(e)[:120]
            return rec
        fetched, blocked = 0, 0
        for h in sorted(on, key=lambda h: h.get("rank") or 99)[:2]:
            page, usd = read(h["url"], slug)
            rec["usd"] += usd
            if page["status"] != "ok":
                blocked += 1
                continue
            fetched += 1
            pub = _d(page.get("published"))
            for rep in page["events"]:
                verdict, _ = match_event(rep, [ev], pub)
                if verdict in ("correct", "wrong"):
                    rec.update(status="found", verdict=verdict, url=h["url"], evidence=h["url"], quote=rep.get("quote"),
                               date=(page.get("published") or "")[:10] or None,
                               days_late=(pub - _d(ev["filing_date"])).days if pub and _d(ev["filing_date"]) else None)
                    if verdict == "correct":
                        break
            if rec["verdict"] == "correct":
                break
        if rec["status"] != "found" and on and fetched == 0 and blocked:
            rec["status"] = "blocked"
        return rec

    out = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for i, rec in enumerate(pool.map(check, jobs), 1):
            out.append(rec)
            if i % 50 == 0:
                print(f"{i}/{len(jobs)} checks · spent ${spent():.3f}", flush=True)
                with lock:
                    SEARCH_CACHE.write_text(json.dumps(dict(scache)))
                    PAGE_CACHE.write_text(json.dumps(dict(pcache)))
                    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    SEARCH_CACHE.write_text(json.dumps(scache))
    PAGE_CACHE.write_text(json.dumps(pcache))
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"done: {len(out)} checks · spent ${spent():.3f} (search ${telem.spent_usd:.3f}, judge ${llm.spent_usd:.3f})")
    for src in SOURCES:
        rs = [r for r in out if r["source"] == src]
        c = Counter(r["status"] for r in rs)
        late = [r["days_late"] for r in rs if r["verdict"] == "correct" and r["days_late"] is not None]
        print(f"  {src:18} {dict(c)} wrong={sum(r['verdict'] == 'wrong' for r in rs)} "
              f"median_late={statistics.median(late) if late else None} (n={len(late)})")


if __name__ == "__main__":
    b = float(sys.argv[sys.argv.index("--budget") + 1]) if "--budget" in sys.argv else 1.6
    main(b)
