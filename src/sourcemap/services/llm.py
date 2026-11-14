"""Single model calls through OpenRouter — the planner and the judge (ADR 0009).

`ask_json()` sends one chat request and parses a JSON object from the answer. Cost is taken from
OpenRouter's `usage.cost` when present, otherwise estimated. Answers are cached on disk by
(model, prompt version, input hash) so a repeated question is never paid twice.
"""

import hashlib
import json
import re
import urllib.error
import urllib.request
from pathlib import Path

URL = "https://openrouter.ai/api/v1/chat/completions"
PLANNER_MODEL = "anthropic/claude-sonnet-5.5"
JUDGE_MODEL = "anthropic/claude-haiku-5.5"


class LLM:
    def __init__(self, api_key: str, cache_dir: Path, *, budget_usd: float):
        self._key = api_key
        self._cache = Path(cache_dir)
        self._cache.mkdir(parents=True, exist_ok=True)
        self.budget_usd = budget_usd
        self.spent_usd = 0.0

    def ask_json(self, model: str, prompt_version: str, system: str, user: str, max_tokens: int = 4000) -> dict:
        key = hashlib.sha256(json.dumps([model, prompt_version, system, user]).encode()).hexdigest()
        cached = self._cache / f"{key}.json"
        if cached.exists():
            return json.loads(cached.read_text())["answer"]
        if self.spent_usd >= self.budget_usd:
            raise RuntimeError(f"model budget ${self.budget_usd:.2f} spent")
        body = json.dumps({"model": model, "max_tokens": max_tokens, "temperature": 0,
                           "usage": {"include": True},
                           "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
        req = urllib.request.Request(URL, data=body.encode(), method="POST", headers={
            "Authorization": f"Bearer {self._key}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                resp = json.loads(r.read())
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"OpenRouter HTTP {e.code}: {e.read()[:300]!r}") from None
        text = resp["choices"][0]["message"]["content"]
        usage = resp.get("usage") or {}
        cost = usage.get("cost")
        if cost is None:
            cost = (usage.get("prompt_tokens", 0) * 2 + usage.get("completion_tokens", 0) * 10) / 1e6
        self.spent_usd += float(cost)
        answer = parse_json(text)
        cached.write_text(json.dumps({"model": model, "prompt_version": prompt_version, "usd": cost,
                                      "input": {"system": system, "user": user}, "answer": answer},
                                     ensure_ascii=False, indent=1))
        return answer


def parse_json(text: str) -> dict:
    """The first JSON object in a model answer (models sometimes wrap it in ```json fences)."""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError(f"no JSON object in model answer: {text[:200]!r}")
    return json.loads(m.group(0))
