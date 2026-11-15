"""People named in the Tavily results (titles + snippets) → people.json. Each person must appear verbatim in the
snippet or title it came from. Run from the project root: .venv/bin/python experiment/tavily-samsung-marketing-orgchart/people.py"""

import json
from pathlib import Path

from sourcemap.cli import load_env
from sourcemap.pipeline import demo_multi as M
from sourcemap.services.llm import JUDGE_MODEL, LLM

HERE = Path(__file__).parent
PROMPT = """Below are numbered search results (title + snippet) about Samsung Electronics. List every PERSON named in them
who is described as working (or having worked) at Samsung Electronics or a Samsung Electronics subsidiary, with the
title or role the text gives them, and the result numbers that name them. Copy each name exactly as written in the text.
Mark "marketing": true if the role is marketing, brand, advertising or communications-with-marketing.
Answer one JSON object only: {"people": [{"name": "...", "title": "...", "marketing": true, "results": [1, 4]}]}"""


def main():
    env = load_env(Path(".env"))
    data = json.loads((HERE / "results.json").read_text())
    hits = [(r["query"], h) for r in data["results"] for h in r["hits"]]
    text = "\n\n".join(f"[{i}] {h['title']}\n{h['snippet']}" for i, (_, h) in enumerate(hits, 1))
    L = LLM(env["OPENROUTER_API_KEY"], Path("data/llm_cache"), budget_usd=0.1)
    ans = L.ask_json(JUDGE_MODEL, "tavily_people/v1", PROMPT, text, max_tokens=6000)
    people = []
    for p in ans.get("people", []):
        found = []
        for i in p.get("results", []):
            if 1 <= i <= len(hits):
                q, h = hits[i - 1]
                if p["name"] in (h["title"] + " " + h["snippet"]):  # the name must really be in that result
                    found.append({"result": i, "query": q, "url": h["url"], "host": M.host(h["url"]), "title": h["title"]})
        if found:
            people.append({"name": p["name"], "title": p.get("title", ""), "marketing": bool(p.get("marketing")), "found_in": found})
    (HERE / "people.json").write_text(json.dumps({"people": people, "usd": L.spent_usd}, ensure_ascii=False, indent=1))
    print(len(people), "people ·", sum(p["marketing"] for p in people), "marketing · $", round(L.spent_usd, 4))
    for p in people:
        print(" ", p["name"], "|", p["title"][:60], "|", sorted({f["host"] for f in p["found_in"]}))


if __name__ == "__main__":
    main()
