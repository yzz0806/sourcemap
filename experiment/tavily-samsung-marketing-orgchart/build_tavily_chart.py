"""Org chart of the 13 marketing people Tavily's results named (people.json) → tavily-marketing-orgchart.html.
Who sits where is inferred from each person's title in the snippets; evidence = where Tavily found them."""
import json
from html import escape as e
from pathlib import Path

HERE = Path(__file__).parent
P = {p["name"]: p for p in json.loads((HERE / "people.json").read_text())["people"]}
OWN = ("samsung.com", "samsungsemiconductor.com")
EN = {"최보람": "Choi Bo-ram", "최승은": "Choi Seung-eun", "최방섭": "Choi Bang-seop", "이헌": "Lee Heon", "장소연": "Jang So-yeon"}


def hosts(name):
    seen, out = set(), []
    for f in P[name]["found_in"]:
        h = f["host"].removeprefix("www.").removeprefix("m.")
        if h not in seen:
            seen.add(h)
            out.append((h, f["url"]))
    return out


def status(name):
    return "own" if any(h.endswith(OWN) for h, _ in hosts(name)) else "other"


def initials(n):
    return "".join(w[0] for w in n.replace("-", " ").split()[:3]).upper()


def person(name, role, note=""):
    st, en = status(name), EN.get(name, name)
    ko = name if name in EN else ""
    src = " ".join(f'<a class="src{" own" if h.endswith(OWN) else ""}" href="{e(u)}" target="_blank" rel="noopener">{e(h)}</a>' for h, u in hosts(name))
    pill = ('<span class="pill p-own">✓ Samsung site</span>' if st == "own" else f'<span class="pill p-other">◐ Other sites · {len(hosts(name))}</span>')
    return (f'{pill}<div class="person"><span class="av av-{st}" aria-hidden="true">{e(initials(en))}</span><div class="pp">'
            f'<span class="nm">{e(en)}</span>{f"<span class=kr>{e(ko)}</span>" if ko else ""}<span class="role">{e(role)}</span></div></div>'
            + (f'<p class="note">{e(note)}</p>' if note else "") + f'<div class="srcs">{src}</div>'), st


def card(title, kr="", who=None, note="", mk=True, struck=False, plain=False):
    body, st = ("", "none")
    if who:
        body, st = person(*who)
    cls = "plain" if plain else f"c-{st}"
    t = f'<h3 class="ut{" mk" if mk else ""}{" struck" if struck else ""}">{e(title)}</h3>{f"<span class=uk>{e(kr)}</span>" if kr else ""}'
    n = f'<p class="note">{e(note)}</p>' if note and not who else ""
    return f'<article class="card {cls}">{t}{n}{body}</article>'


def kids(items, cls="kids"):
    return f'<ul class="{cls}">' + "".join(f"<li>{x}</li>" for x in items) + "</ul>"


root = card("Samsung Electronics · DX Division", "디바이스경험(DX)부문", mk=False, plain=True,
            note="Phones, TVs, appliances. Head: TM Roh (Tae-Moon Roh), President & CEO — named on samsung.com.")
cols = [
    (card("Global Marketing Office", "글로벌마케팅실", struck=True, plain=True,
          note="Downsized May 2026. Last head Won-Jin Lee moved to run VD (see VD column)."),
     [card("Global Brand Center", "글로벌브랜드센터", ("최승은", "VP, head — the Global Marketing Office's successor")) +
      kids([card("Brand Marketing Group", "브랜드마케팅그룹", ("최보람", "Managing Director (상무), group head"))], "kids sub")]),
    (card("MX Business (Mobile)", "MX사업부", mk=False, plain=True, note="Smartphones and tablets."),
     [card("Strategic Marketing Office", "전략마케팅실", ("최방섭", "VP, office head (부사장, 전략마케팅실장)"))]),
    (card("VD Business (TVs)", "VD사업부", ("Won-Jin Lee", "President, business head since May 2026; ex-head of Global Marketing"), mk=False),
     [card("Strategic Marketing Team", "전략마케팅팀", ("이헌", "VP, team head (부사장, 전략마케팅팀장)"))]),
    (card("Korea Region", "한국총괄", mk=False, plain=True, note="Sales and marketing in Korea."),
     [card("Marketing Team", "마케팅팀", ("장소연", "VP, deputy team head (부사장, 부팀장)"))]),
    (card("Samsung Electronics America", "미주", mk=False, plain=True, note="US subsidiary."),
     [card("Corporate Marketing", "", ("Allison Stransky", "VP & Chief Marketing Officer", "Reported leaving for Boston Beer.")),
      card("Mobile (MX) Marketing", "", ("Olga Suvorova", "Chief Marketing Officer, Mobile Experience")),
      card("TV & Mobile Services, Advertising", "", ("Cathy Oh", "Marketing Officer")),
      card("Marketing", "", ("Rebecca Gonzales", "Director of Marketing"))]),
]
former = [card("Global Marketing (until 2024)", "", ("YoungHee Lee", "President & Head of Global Marketing")),
          card("America CMO (earlier)", "", ("Marc Mathieu", "Chief Marketing Officer, Samsung Electronics America")),
          card("Digital Media marketing (2002–2007)", "", ("Dr. Steel", "VP and head of marketing"))]

n_now = 10
css = (HERE / "samsung-marketing-orgchart.html").read_text().split("<style>")[1].split("</style>")[0]
extra = """
.c-own { border: 1.5px solid var(--blue); }
.c-other { background: var(--org-bg); border: 1.5px dashed var(--org); }
.plain { background: #fff; border: 1px solid var(--hair); }
.p-own { background: var(--blue); color: #fff; border: 1px solid var(--blue); }
.p-other { background: #fff; color: var(--org); border: 1px solid var(--org); }
.av-own { background: var(--blue); color: #fff; }
.av-other { background: #fff; color: var(--org); border: 1.5px dashed var(--org); }
.c-other .nm { font-style: italic; text-decoration: underline dotted; text-underline-offset: 3px; }
.ut.mk::before { content: ""; display: inline-block; width: 8px; height: 8px; background: var(--blue); margin-right: 7px; vertical-align: 1px; }
.srcs { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 8px; }
.src { font-family: var(--mono); font-size: 10.5px; border: 1px solid var(--hair); padding: 1px 6px; color: var(--grey); background: #fff; text-decoration: none; }
.src.own { border-color: var(--blue); color: var(--blue); }
.former { border-top: 1px solid var(--ink); padding-top: 20px; }
.former .row { display: grid; grid-template-columns: repeat(3, 272px); gap: 48px; margin-top: 12px; }
.kpis { display: flex; gap: 0; border-top: 1px solid var(--hair); border-bottom: 1px solid var(--hair); }
.kpis div { padding: 12px 32px 12px 0; margin-right: 32px; border-right: 1px solid var(--hair); }
.kpis div:last-child { border-right: 0; }
.kpis b { display: block; font: 400 30px Georgia, serif; }
.kpis span { font: 700 10.5px var(--mono); letter-spacing: .1em; text-transform: uppercase; color: var(--grey); }
"""
all_names = ["최승은", "최보람", "최방섭", "Won-Jin Lee", "이헌", "장소연", "Allison Stransky", "Olga Suvorova", "Cathy Oh",
             "Rebecca Gonzales", "YoungHee Lee", "Marc Mathieu", "Dr. Steel"]
own_n = sum(status(n) == "own" for n in all_names)
srcs = {h for n in all_names for h, _ in hosts(n)}
html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=1680">
<title>Tavily Samsung Marketing Chart</title><style>{css}{extra}</style></head><body><div class="page">
<header class="top"><div>
  <p class="eyebrow">Sourcemap experiment · Tavily search only · 2026-11-14</p>
  <h1>Samsung Electronics marketing people Tavily found</h1>
  <p class="lede">The 13 marketing people named in Tavily's 50 results, placed where their titles put them. Who sits under whom is inferred from titles; every card lists the websites Tavily found the person on.</p>
</div>
<ul class="legend"><li><span class="pill p-own" style="margin:0">✓ Samsung site</span></li><li>Named on a Samsung website</li>
<li><span class="pill p-other" style="margin:0">◐ Other sites</span></li><li>Named only by other websites</li>
<li class="lg-mk">Marketing unit</li><li><span class="lg-struck">Struck-through</span>&nbsp;= downsized</li></ul></header>
<div class="kpis"><div><b>13</b><span>marketing people</span></div><div><b>{n_now}</b><span>in current roles</span></div>
<div><b>{own_n}</b><span>named on a Samsung site</span></div><div><b>{13 - own_n}</b><span>only on other sites</span></div><div><b>{len(srcs)}</b><span>data sources</span></div></div>
<section class="chart" aria-label="Org chart">
  <div class="root-wrap">{root}</div>
  <ul class="l2row">{''.join(f'<li class="col">{top}{kids(ch)}</li>' for top, ch in cols)}</ul>
</section>
<section class="former"><h2>Earlier marketing heads Tavily also found</h2><p class="lede" style="margin-top:4px">Past roles: shown for context, not part of today's chart.</p>
<div class="row">{''.join(former)}</div></section>
<footer>Search: Tavily through Telem (5 queries, 50 results), names taken from result titles and snippets — leads, not verified evidence. Placement is inferred from titles. Data: people.json, results.json.</footer>
</div></body></html>"""
(HERE / "tavily-marketing-orgchart.html").write_text(html)
print("ok", own_n, len(srcs))
