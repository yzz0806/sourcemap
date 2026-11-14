"""Finds a LinkedIn profile *candidate* for each person in the Samsung marketing answer, via Telem.

Search results only find; they never verify (R2). A candidate is accepted only when the result's
title contains the person's family name and a given-name token, and "Samsung" appears in the title
or snippet. Output: data/demo/people_linkedin.json. Cost: ~$0.001 a person (parallel), exa fallback.
"""

import json
import re
from pathlib import Path

from sourcemap.cli import load_env
from sourcemap.services.websearch import Telem

SPEC_EN = {"노태문": "TM Roh", "이원진": "Wonjin Lee", "정윤": "Yoonie Joung", "김철기": "Kim Cheol-gi",
           "한의택": "Han Eui-taek", "이영희": "Lee Young-hee"}
EXTRA = {"Allison Stransky": "Allison Stransky", "Olga Suvorova": "Olga Suvorova"}


def western(en: str, foreign: bool) -> str:
    """'Choi Seung-eun' -> 'Seung-eun Choi'; already-western names unchanged."""
    parts = en.split()
    if foreign or len(parts) != 2 or "-" not in parts[1]:
        return en
    return f"{parts[1]} {parts[0]}"


def tokens(name: str) -> tuple[str, list[str]]:
    parts = re.sub(r"[.\-]", " ", name.lower()).split()
    return parts[-1], parts[:-1]


def name_tokens(s: str) -> set[str]:
    s = re.sub(r"\(.*?\)", " ", s.lower())          # drop "(정윤)"
    return set(re.sub(r"[^a-z\s]", " ", s.replace("-", " ")).split())


def accept(hit, name: str) -> bool:
    """Exact name match on the LinkedIn title's name part (before ' - ' or ' | '), plus Samsung.
    Allowed variant: a hyphenated given name written as one word (Seung-eun -> Seungeun)."""
    if "linkedin.com/in/" not in hit.url:
        return False
    title_name = re.split(r"\s[-|–]\s", hit.title)[0]
    t = name_tokens(title_name)
    fam, given = tokens(name)
    exact = {fam, *given}
    joined = {fam, "".join(given)}
    text = (hit.title + " " + hit.snippet).lower()
    return (t == exact or t == joined) and ("samsung" in text or "삼성" in text)


def main():
    env = load_env(Path(".env"))
    t = Telem(env["TELEM_API_KEY"], budget_usd=0.8)
    en = json.loads(Path("data/demo/people_en.json").read_text())
    people = {ko: western(SPEC_EN.get(ko, v["en"]), v["foreign"]) for ko, v in en.items()}
    people.update(EXTRA)
    out = {}
    for key, name in people.items():
        out[key] = {"name": name, "url": None}
        for provider in ("parallel", "exa"):
            try:
                res = t.search(f"{name} Samsung LinkedIn", providers=[provider], num_results=5)
            except Exception as e:  # noqa: BLE001 — one failure never stops the run
                out[key]["error"] = str(e)[:120]
                break
            hits = [h for r in res.runs for h in r.hits]
            out[key].setdefault("hits", []).extend({"url": h.url, "title": h.title, "provider": provider} for h in hits)
            hit = next((h for h in hits if accept(h, name)), None)
            if hit:
                out[key].update(url=hit.url.split("?")[0], title=hit.title[:120], provider=provider)
                break
    Path("data/demo/people_linkedin.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    n = sum(1 for v in out.values() if v.get("url"))
    print(f"{n}/{len(out)} LinkedIn candidates · spent ${t.spent_usd:.3f}")


if __name__ == "__main__":
    main()
