"""The Samsung DX marketing org-chart tree (data from the user's spec, assembled in the Tavily
experiment in experiment/tavily-samsung-marketing-orgchart/), cross-checked against DART.

Each person with a Korean name gets the DART row(s) with that name (as of 2025-12-31); each unit
whose head is unknown gets the DART row whose responsibility names that unit's head. These are
added as dated notes — the spec's statuses are not changed.
"""

import json
import re
from pathlib import Path

C, S, U, V, N = "confirmed", "snippet", "unknown", "vacant", None

TREE = {
    "unit": "Samsung Electronics · DX Division", "ko": "디바이스경험(DX)부문", "root": True,
    "person": {"en": "TM Roh", "ko": "노태문", "role": "President & CEO, Head of DX", "init": "TR"}, "status": C,
    "children": [
        {"unit": "Global Marketing Office", "ko": "글로벌마케팅실", "mk": True, "struck": True, "status": C,
         "person": {"en": "Wonjin Lee", "ko": "이원진", "role": "President until 2026-05-04", "init": "WL"},
         "note": "Downsized May 2026.", "dart_unit": r"^글로벌마케팅실장$",
         "children": [
             {"unit": "Global Brand Center", "ko": "글로벌브랜드센터", "mk": True, "status": C, "dart_unit": r"글로벌브랜드센터장$",
              "person": {"en": "Choi Seung-eun", "ko": "최승은", "role": "VP, head since May 2026", "init": "CSE"},
              "children": [
                  {"unit": "Brand Marketing Group", "ko": "브랜드마케팅그룹", "mk": True, "status": C,
                   "person": {"en": "Choi Bo-ram", "ko": "최보람", "role": "Managing Director", "init": "CBR"},
                   "note": "Placement under the Brand Center is an assumption."}]},
             {"unit": "D2C Center", "ko": "D2C센터", "mk": True, "status": U, "note": "Online and offline Samsung stores",
              "dart_unit": r"D2C센터장$"},
             {"unit": "CX-MDE Center", "ko": "CX-MDE센터", "mk": True, "status": U,
              "note": "Connected-device customer experience", "dart_unit": r"CX센터장$"}]},
        {"unit": "MX Business (Mobile)", "ko": "MX사업부", "status": N, "note": "Smartphones and tablets", "container": True,
         "children": [
             {"unit": "Mobile Marketing Center", "ko": "모바일마케팅센터", "mk": True, "status": C, "dart_unit": r"모바일마케팅센터장$",
              "person": {"en": "Choi Seung-eun", "ko": "최승은", "role": "VP, concurrent with Global Brand Center", "init": "CSE"}},
             {"unit": "Strategic Marketing Office", "ko": "전략마케팅실", "mk": True, "status": S,
              "dart_unit": r"Mobile eXperience 전략마케팅실장$",
              "person": {"en": "Choi Bang-seop", "ko": "최방섭", "role": "VP, head (older blog list)", "init": "CBS"},
              "note": "LinkedIn lists Seong H. Cho, EVP, instead. Current head not checked."}]},
        {"unit": "VD Business (TVs, displays)", "ko": "VD사업부", "status": C,
         "person": {"en": "Wonjin Lee", "ko": "이원진", "role": "President since 2026-05-04", "init": "WL"},
         "children": [
             {"unit": "Strategic Marketing Team", "ko": "전략마케팅팀", "mk": True, "status": C, "dart_unit": r"영상디스플레이 전략마케팅팀장$",
              "person": {"en": "Lee Heon", "ko": "이헌", "role": "VP, team head; moved from MX in 2024", "init": "LH"}},
             {"unit": "Custom Marketing Team", "ko": "커스텀마케팅팀", "mk": True, "struck": True, "status": V,
              "vacant_text": "Vacant: Park Chul-woo left in 2026; not refilled"}]},
        {"unit": "DA Business (Appliances)", "ko": "생활가전(DA)사업부", "status": C,
         "person": {"en": "Kim Cheol-gi", "ko": "김철기", "role": "VP, business head", "init": "KCG"},
         "children": [
             {"unit": "Sales Strategy Group", "ko": "영업전략그룹", "mk": False, "status": C,
              "person": {"en": "Han Eui-taek", "ko": "한의택", "role": "VP", "init": "HET"},
              "note": "Sales; runs the unified product-launch process"}]},
        {"unit": "Samsung Electronics America", "ko": "미주", "status": S,
         "person": {"en": "Yoonie Joung", "ko": "정윤", "role": "President & CEO, North America", "init": "YJ"},
         "children": [
             {"unit": "Corporate Marketing (CMO)", "ko": "", "mk": True, "status": S,
              "person": {"en": "Allison Stransky", "ko": "", "role": "CMO, reported leaving for Boston Beer", "init": "AS"},
              "note": "Successor not found"},
             {"unit": "MX Marketing, US", "ko": "", "mk": True, "status": S,
              "person": {"en": "Olga Suvorova", "ko": "", "role": "CMO, Mobile Experience (BizKonnect)", "init": "OS"},
              "note": "Exa search found Keena Grigsby as CMO, US MX. Unresolved."}]},
    ]}

TIMELINE = [
    ["to 2024-11", "Lee Young-hee (이영희), President, Head of Global Marketing Office"],
    ["2024-11", "Wonjin Lee (이원진), President, returns from retirement to head the office"],
    ["2026-05-04", "Wonjin Lee moves to VD. Office downsized, placed directly under DX"],
    ["2026-05", "Choi Seung-eun (최승은) named head of Global Brand Center"],
]
GAPS = [
    "Heads of the D2C Center and the CX-MDE Center.",
    "Whether D2C and CX-MDE survived the May 2026 change, or moved to business units.",
    "Current head of MX Strategic Marketing (two names).",
    "Marketing in the semiconductor (DS) division and in Korea and other regions. Out of scope here.",
    "Samsung's year-end 2026 reshuffle, usually late November, may change all of this.",
]


def build(root: Path) -> dict:
    dart = json.loads((root / "data/seg/refs.json").read_text())["samsung-electronics"]["rows"]
    li = json.loads((root / "data/demo/people_linkedin_strict.json").read_text())

    def dart_person(ko):
        return [f"{r['title']} · {r['responsibility']}" for r in dart if ko and r["name"] == ko]

    def dart_head(pattern):
        rows = [r for r in dart if re.search(pattern, r.get("responsibility", ""))]
        return [f"{r['name']} · {r['title']} · {r['responsibility']}" for r in rows]

    def walk(n):
        p = n.get("person")
        if p:
            key = p["ko"] or p["en"]
            p["dart"] = dart_person(p["ko"])
            p["linkedin"] = (li.get(key) or {}).get("url")
        if n.get("dart_unit"):
            n["dart_head"] = dart_head(n.pop("dart_unit"))
        for c in n.get("children", []):
            walk(c)
        return n

    return {"tree": walk(json.loads(json.dumps(TREE))), "timeline": TIMELINE, "gaps": GAPS,
            "dart_date": "2025-12-31", "provenance": "experiment/tavily-samsung-marketing-orgchart (Tavily search + page reads)"}


if __name__ == "__main__":
    print(json.dumps(build(Path(__file__).resolve().parents[1]), ensure_ascii=False, indent=1)[:3000])
