/* sourcemap — interactive replay site. Renders window.SOURCEMAP (scripts/build_web.py).
   Views (hash routes): #/ dashboard · #/search?q= · #/type/<type>[/<segment>] · #/providers · #/method
   Everything shown is a replay of results measured on D.measured_on; nothing here calls an API. */
(function () {
  const D = window.SOURCEMAP;
  const SEGS = Object.keys(D.segments);
  const INK = "#14141a", GREY = "#6e6e78", LINE = "#e6e6ea", BLUE = "#1f4fd8";
  const view = document.getElementById("view");
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const pct = (x) => (x == null ? "–" : Math.round(x * 100) + "%");
  const usd = (x) => (!x ? "$0" : "$" + (x < 0.01 ? x.toFixed(4) : x.toFixed(2)));
  const TELEM = '<span class="telem">TELEM</span>';
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  let runId = 0; // cancels an animation when the route changes
  document.getElementById("foot").innerHTML =
    `sourcemap · replaying results measured on ${esc(D.measured_on)} · DART, SEC EDGAR, company pages, Telem search · nothing on this page calls an API`;

  /* ---------- SVG primitives (hand-drawn; no chart library) ---------- */
  const HATCH = `<defs><pattern id="hatch" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="4" stroke="${LINE}" stroke-width="2"/></pattern></defs>`;
  function accColor(s) {
    if (!s || s.state === "unmeasured") return { fill: "url(#hatch)", stroke: LINE };
    if (s.state === "not_enough_data") return { fill: "#fff", stroke: GREY };
    return { fill: BLUE, stroke: BLUE, opacity: Math.max(0.15, Math.min(1, (s.mean - 0.5) / 0.5)) };
  }
  function cellSvg(acc, cov, w = 210) {
    const x0 = 22, x1 = w - 4, X = (v) => x0 + (x1 - x0) * v, c = accColor(acc);
    let s = `<svg width="${w}" height="${cov ? 34 : 18}" role="img">${HATCH}`;
    s += `<rect x="0" y="2" width="14" height="14" fill="${c.fill}" stroke="${c.stroke}" ${c.opacity ? `fill-opacity="${c.opacity}"` : ""}/>`;
    s += `<line x1="${x0}" y1="9" x2="${x1}" y2="9" stroke="${LINE}"/>`;
    [0, 0.5, 1].forEach((v) => (s += `<line x1="${X(v)}" y1="6" x2="${X(v)}" y2="12" stroke="${LINE}"/>`));
    if (acc && acc.interval) {
      const [lo, hi] = acc.interval;
      s += `<line x1="${X(lo)}" y1="9" x2="${X(hi)}" y2="9" stroke="${INK}" stroke-width="1.5"/><line x1="${X(lo)}" y1="4" x2="${X(lo)}" y2="14" stroke="${INK}"/><line x1="${X(hi)}" y1="4" x2="${X(hi)}" y2="14" stroke="${INK}"/>`;
      if (acc.mean != null) s += `<circle cx="${X(acc.mean)}" cy="9" r="3" fill="${INK}"/>`;
    }
    if (cov) {
      const f = cov.total ? cov.found / cov.total : 0;
      s += `<rect x="${x0}" y="24" width="${x1 - x0}" height="5" fill="${LINE}"/><rect x="${x0}" y="24" width="${Math.max(f > 0 ? 2 : 0, (x1 - x0) * f)}" height="5" fill="${INK}"/>`;
    }
    return s + "</svg>";
  }
  function accText(a) {
    if (!a || a.state === "unmeasured") return '<span class="muted">unmeasured</span>';
    const iv = a.interval ? `[${a.interval[0].toFixed(2)}, ${a.interval[1].toFixed(2)}]` : "";
    const head = a.state === "measured" ? `<b>${a.mean.toFixed(2)}</b>` : '<span class="muted">not enough data</span>';
    return `${head} <span class="small">${iv} n=${a.n}${a.n_wrong ? ` · ${a.n_wrong} wrong` : ""}</span>`;
  }

  /* ---------- library helpers ---------- */
  const order = { measured: 0, not_enough_data: 1, unmeasured: 2 };
  function rankedSources(seg) {
    return D.library.map((row) => ({ row, c: row.segments[seg] }))
      .sort((a, b) => order[a.c.title.state] - order[b.c.title.state] || (b.c.title.mean || 0) - (a.c.title.mean || 0) || b.c.coverage.found - a.c.coverage.found);
  }
  function bestProvider(seg) {
    let best = null;
    D.providers.forEach((p) => { const r = p.segments[seg] && p.segments[seg].reference_found; if (r && (!best || r.mean > best.r.mean)) best = { p: p.provider, r }; });
    return best;
  }
  const pairOf = (row, seg, slug) => (row.segments[seg].pairs || []).find((p) => p.company === slug);
  const isMk = (t) => /market|brand|cmo|마케팅/i.test(t || "");

  /* ---------- query understanding (in the browser, rule-based) ---------- */
  const ALIASES = {
    "samsung-electronics": ["samsung electronics", "samsung", "삼성전자", "삼성"], "sk-hynix": ["sk hynix", "hynix", "sk하이닉스", "하이닉스"],
    naver: ["naver", "네이버"], nvidia: ["nvidia", "엔비디아"], apple: ["apple", "애플"], microsoft: ["microsoft", "msft", "마이크로소프트"],
    airbus: ["airbus", "에어버스"], sap: [" sap "], siemens: ["siemens", "지멘스"],
  };
  const TYPE_WORDS = {
    org_chart: ["org chart", "orgchart", "organization", "organisation", "leadership", "executive", "who leads", "who runs", "leads ", "team", "조직도", "임원", "경영진"],
    technographics: ["tech stack", "technographic", "tools", "software", "stack", "uses", "기술 스택"],
    leadership_signals: ["appointed", "appointment", "departure", "departed", "hired", "joins", "changes", "인사"],
  };
  const DEPTS = { marketing: ["marketing", "brand", "cmo", "마케팅"], sales: ["sales", "영업"], engineering: ["engineering", "r&d", "개발"], finance: ["finance", "cfo", "재무"] };
  function understand(q) {
    const t = " " + q.toLowerCase().replace(/[?.!,]/g, " ") + " ";
    let company = null, ctext = "";
    for (const [slug, names] of Object.entries(ALIASES)) for (const n of names) if (t.includes(n) && n.length > ctext.length) { company = slug; ctext = n; }
    const guessName = !company ? (q.match(/\b(?:of|at|for) ([A-Z][\w&.-]*(?: [A-Z][\w&.-]*)*)/) || [])[1] : null;
    let type = null;
    for (const [k, ws] of Object.entries(TYPE_WORDS)) if (!type && ws.some((w) => t.includes(w))) type = k;
    let dept = null;
    for (const [k, ws] of Object.entries(DEPTS)) if (!dept && ws.some((w) => t.includes(w))) dept = k;
    if (!type && (company || dept)) type = "org_chart";
    return { company, guessName, type, dept };
  }

  /* ---------- router ---------- */
  function route() {
    runId++;
    const h = location.hash || "#/";
    window.scrollTo(0, 0);
    if (h.startsWith("#/search")) return search(decodeURIComponent((h.split("q=")[1] || "").replace(/\+/g, " ")));
    if (h.startsWith("#/type/")) { const [, , type, seg] = h.slice(1).split("/"); return seg ? segmentPage(type, seg) : typePage(type); }
    if (h === "#/providers") return providersPage();
    if (h === "#/method") return methodPage();
    return dashboard();
  }
  window.addEventListener("hashchange", route);
  const go = (q) => { location.hash = "#/search?q=" + encodeURIComponent(q); };

  function searchBox(value = "") {
    const sugg = ["Marketing department org chart of Samsung Electronics", "Marketing leadership of Microsoft", "Org chart of NAVER marketing",
      "Who leads marketing at Airbus", "Tech stack of Nvidia", "Org chart of Hyundai Motor"];
    return `<form class="searchbox" id="sf"><input id="q" value="${esc(value)}" placeholder="Ask for data — e.g. Marketing department org chart of Samsung Electronics" autocomplete="off"><button>Route →</button></form>
      <div class="suggest">${sugg.map((s) => `<a href="#/search?q=${encodeURIComponent(s)}">${esc(s)}</a>`).join("")}</div>`;
  }
  function bindSearch() {
    const f = document.getElementById("sf");
    if (f) f.addEventListener("submit", (e) => { e.preventDefault(); const q = document.getElementById("q").value.trim(); if (q) go(q); });
  }

  /* ---------- dashboard ---------- */
  function dashboard() {
    const s = D.stats;
    view.innerHTML = `<section class="hero">
      <p class="label">THE MISSING LAYER BETWEEN AN AGENT AND WEB SEARCH</p>
      <h1>Ask for data. sourcemap routes the question to the sources measured to be right.</h1>
      ${searchBox()}
      <p class="replay">Replay mode: answers come from results measured on ${esc(D.measured_on)}.</p>
      <div class="stats">${[[s.n_companies, "companies"], [SEGS.length, "segments"], [s.n_sources, "sources measured"], [s.telem_calls, "Telem search calls " + TELEM], [usd(s.telem_usd), "spent on search"]]
        .map(([v, l]) => `<div class="stat"><b>${v}</b><span class="mono">${l}</span></div>`).join("")}</div>
    </section>
    <section><p class="label">THE INDEX</p><h2>Data types, their segments, and the sources to cite</h2>
      <div class="types">${D.data_types.map(typeCard).join("")}</div></section>`;
    bindSearch();
  }
  function typeCard(t) {
    if (t.status !== "measured") return `<div class="type off"><span class="status designed">designed · not built</span><h3>${esc(t.name)}</h3>
      <p class="small">${esc(t.what)}</p><p class="small">${esc(t.plan)}</p></div>`;
    return `<div class="type"><span class="status">measured</span><h3><a href="#/type/${t.slug}" style="color:inherit">${esc(t.name)}</a></h3>
      <p class="small">${esc(t.what)} Claims: ${t.claims.join(", ")}.</p>
      <div class="seglist">${SEGS.map((g) => {
        const top = rankedSources(g)[0], cos = Object.values(D.companies).filter((c) => c.segment === g).map((c) => c.name);
        return `<a class="segrow" href="#/type/${t.slug}/${g}"><span><b>${esc(D.segments[g].name)}</b><br><span class="small">vs ${esc(D.segments[g].reference)} · ${esc(cos.join(", "))}</span></span>
          <span class="small" style="text-align:right">best: <b>${esc(top.row.source)}</b><br>${accText(top.c.title)}</span></a>`;
      }).join("")}</div></div>`;
  }

  /* ---------- data type & segment pages ---------- */
  function typePage(type) {
    const t = D.data_types.find((x) => x.slug === type);
    if (!t || t.status !== "measured") {
      view.innerHTML = `<p class="crumbs"><a href="#/">Dashboard</a> / ${esc(t ? t.name : type)}</p><h2>${esc(t ? t.name : type)}</h2>
        <p class="note">${t ? esc(t.what) + "<br>" + esc(t.plan) : "Unknown data type."}</p><p><span class="status designed">designed · not built</span></p>`;
      return;
    }
    const head = SEGS.map((g) => `<th><a href="#/type/${type}/${g}">${esc(D.segments[g].name)}</a><br><span style="text-transform:none;letter-spacing:0;font-weight:400">vs ${esc(D.segments[g].reference)}</span></th>`).join("");
    const body = D.library.map((row) => `<tr><td><b>${esc(row.source)}</b><br><span class="small">tier ${row.tier} prior</span></td>${SEGS.map((g) => {
      const c = row.segments[g];
      return `<td class="cell" onclick="location.hash='#/type/${type}/${g}'">${cellSvg(c.title, c.coverage)}<div class="small">title ${accText(c.title)}</div>
        <div class="small">${c.coverage.found}/${c.coverage.total} top leaders · ${c.marketing.found}/${c.marketing.total} marketing · ${usd(c.usd)}</div></td>`;
    }).join("")}</tr>`).join("");
    view.innerHTML = `<p class="crumbs"><a href="#/">Dashboard</a> / ${esc(t.name)}</p><h2>${esc(t.name)} — the source map</h2>
      <p class="note">Sources × segments. <span class="key"><svg width="54" height="10"><rect x="0" y="3" width="54" height="4" fill="${LINE}"/><rect x="0" y="3" width="30" height="4" fill="${INK}"/></svg> coverage of top leaders</span>
      <span class="key"><svg width="12" height="12"><rect width="12" height="12" fill="${BLUE}"/></svg> title accuracy</span>
      <span class="key"><svg width="54" height="12"><line x1="4" y1="6" x2="50" y2="6" stroke="${INK}"/><line x1="4" y1="2" x2="4" y2="10" stroke="${INK}"/><line x1="50" y1="2" x2="50" y2="10" stroke="${INK}"/></svg> 90% interval</span> Open a segment to see its checks.</p>
      <div class="scroll"><table><tr><th>Source</th>${head}</tr>${body}</table></div>`;
  }
  function segmentPage(type, seg) {
    const S = D.segments[seg];
    if (!S) { view.innerHTML = `<p class="crumbs"><a href="#/">Dashboard</a></p><h2>Unknown segment</h2>`; return; }
    const cos = Object.entries(D.companies).filter(([, c]) => c.segment === seg);
    const rows = rankedSources(seg).map((x, j) => `<tr class="srcsel" data-s="${esc(x.row.source)}" style="cursor:pointer"><td class="rank">${j + 1}</td>
      <td><b>${esc(x.row.source)}</b><br><span class="small">tier ${x.row.tier} prior</span></td><td>${cellSvg(x.c.title, x.c.coverage)}</td>
      <td class="small">title ${accText(x.c.title)}<br>${x.c.coverage.found}/${x.c.coverage.total} top leaders · ${x.c.marketing.found}/${x.c.marketing.total} marketing · ${usd(x.c.usd)}</td></tr>`).join("");
    view.innerHTML = `<p class="crumbs"><a href="#/">Dashboard</a> / <a href="#/type/${type}">Org chart</a> / ${esc(S.name)}</p>
      <h2>${esc(S.name)}</h2><p class="note">Verified against <b>${esc(S.reference)}</b>.</p>
      <table><tr><th>Company</th><th>Reference</th><th>Size</th><th></th></tr>${cos.map(([slug, c]) => `<tr><td><b>${esc(c.name)}</b></td><td>${esc(c.ref_kind)}${c.ref_located_by_telem ? " · page located " + TELEM : ""}</td>
        <td class="small">${c.ref_size} people · ${c.ref_marketing} marketing</td><td class="small">${c.ref_failed ? "<b>failed:</b> " + esc(c.ref_failed).slice(0, 90) : `<a href="${esc(c.ref_url)}">open</a>`}</td></tr>`).join("")}</table>
      <h3>Sources to cite, in library order</h3><p class="small">Click a source to open its checks.</p>
      <table><tr><th></th><th>Source</th><th>Accuracy · coverage</th><th></th></tr>${rows}</table><div id="drill"></div>`;
    document.querySelectorAll("tr.srcsel").forEach((tr) => tr.addEventListener("click", () => drill(D.library.find((r) => r.source === tr.dataset.s), seg)));
  }
  function drill(row, g) {
    const c = row.segments[g], el = document.getElementById("drill");
    el.innerHTML = `<div class="drill"><p class="label">CHECKS BEHIND THIS CELL</p><h3>${esc(row.source)} × ${esc(D.segments[g].name)}</h3>
      ${c.pairs.map((pp) => `<div class="pair"><div class="head"><b>${esc(D.companies[pp.company].name)}</b>
        <span class="small">${esc(pp.status)}${pp.url ? ` · <a href="${esc(pp.url)}">page</a>` : ""}${pp.sha ? ` · raw ${esc(pp.sha)}…` : ""} · found by search ${TELEM}</span></div>
        ${pp.checks.length ? checksTable(pp.checks) : '<p class="small">No people to check.</p>'}</div>`).join("")}</div>`;
    el.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  const checksTable = (cs) => `<div class="scroll"><table><tr><th>Person on source</th><th>Quote on the saved page</th><th>Reference row</th><th>Employment</th><th>Title</th><th>Why</th></tr>
    ${cs.map((ch) => `<tr><td><b>${esc(ch.name)}</b><br><span class="small">${esc(ch.title)}</span></td><td class="quote">“${esc(ch.quote)}”</td><td class="small" lang="ko">${esc(ch.ref) || "—"}</td>
      <td class="v-${ch.employment}">${ch.employment}</td><td class="v-${ch.verdict}">${ch.verdict}</td><td class="small">${esc(ch.reason)}</td></tr>`).join("")}</table></div>`;

  /* ---------- search: the animated replay ---------- */
  async function search(q) {
    const my = runId, u = understand(q);
    let fast = false;
    view.innerHTML = `${searchBox(q)}<p class="replay">Replay of the routing process with results measured on ${esc(D.measured_on)}. <button class="skip" id="skip">Skip animation</button></p>
      <p class="query">“${esc(q)}”</p><div class="steps-live" id="sl"></div><div id="result"></div>`;
    bindSearch();
    document.getElementById("skip").onclick = () => { fast = true; };
    const alive = () => runId === my;
    const wait = async (ms) => { if (!fast) await sleep(ms); return alive(); };
    const sl = document.getElementById("sl");
    async function step(label, html, ms = 750) {
      const d = document.createElement("div");
      d.className = "sl run";
      d.innerHTML = `<div class="dot"></div><div class="mono">${label}</div><div>${html}</div>`;
      sl.appendChild(d);
      await sleep(20);
      d.classList.add("show");
      if (!(await wait(ms))) return null;
      d.classList.remove("run");
      d.classList.add("done");
      return d;
    }
    async function lines(d, items, ms = 260) {
      const box = d.querySelector(".lines");
      for (const it of items) {
        const l = document.createElement("div");
        l.className = "line";
        l.innerHTML = it;
        box.appendChild(l);
        await sleep(10);
        l.classList.add("show");
        if (!(await wait(ms))) return false;
      }
      return true;
    }

    // 01 · understand
    const typeName = u.type ? D.data_types.find((t) => t.slug === u.type).name : "not recognised";
    const chips = D.data_types.map((t) => `<span class="chip" data-t="${t.slug}">${esc(t.name)}</span>`).join("");
    let d = await step("01 · Understand", `<div class="chips" id="tchips">${chips}</div><div class="small" style="margin-top:8px">entity: <b>${esc(u.company ? D.companies[u.company].name : u.guessName || "not recognised")}</b>${u.dept ? ` · department: <b>${u.dept}</b>` : ""} · data type: <b>${esc(typeName)}</b></div>`, 400);
    if (!d) return;
    document.querySelectorAll("#tchips .chip").forEach((c) => c.classList.toggle("hit", c.dataset.t === u.type));
    if (!(await wait(500))) return;

    if (u.type !== "org_chart") {
      const t = D.data_types.find((x) => x.slug === u.type);
      await step("02 · Library", `<div class="notfound"><b>${t ? esc(t.name) + " is designed but not built yet." : "No data type recognised."}</b><br>
        <span class="small">${t ? esc(t.plan) : "Try an org-chart question, e.g. “Marketing department org chart of Samsung Electronics”."}</span></div>`, 300);
      return;
    }
    if (!u.company) {
      await step("02 · Segment", `<div class="notfound"><b>${esc(u.guessName || "This company")} is not in the library yet.</b><br>
        <span class="small">sourcemap would run <b>discovery</b>: classify its segment, have the planner write queries per publisher category, search every provider ${TELEM},
        read the candidates and verify them against the segment's reference — then add the measured sources to the library.</span></div>`, 300);
      return;
    }
    const co = D.companies[u.company], seg = co.segment, segInfo = D.segments[seg];

    // 02 · segment
    d = await step("02 · Segment", `<div class="chips" id="schips">${SEGS.map((g) => `<span class="chip" data-g="${g}">${esc(D.segments[g].name)}</span>`).join("")}</div>
      <div class="small" style="margin-top:8px">${esc(co.name)} → <b>${esc(segInfo.name)}</b> — verified against <b>${esc(segInfo.reference)}</b></div>`, 300);
    if (!d) return;
    for (const g of SEGS) {
      document.querySelectorAll("#schips .chip").forEach((c) => c.classList.toggle("hit", c.dataset.g === g));
      if (!(await wait(220))) return;
      if (g === seg) break;
    }
    document.querySelectorAll("#schips .chip").forEach((c) => c.classList.toggle("hit", c.dataset.g === seg));
    if (!(await wait(400))) return;

    // 03 · cite (library lookup)
    const ranked = rankedSources(seg).filter((x) => x.c.title.state !== "unmeasured" || (x.c.reads.ok || 0) > 0).slice(0, 6);
    d = await step("03 · Cite", `<div class="small">Source library · org chart × ${esc(segInfo.name)}, in order:</div><div class="lines"></div>`, 100);
    if (!d) return;
    if (!(await lines(d, [`<b>0 · ${esc(co.ref_kind)}</b> <span class="small">reference · tier ${co.ref_tier ?? "–"} · ${co.ref_size} people</span>`,
      ...ranked.map((x, j) => `<span style="display:inline-flex;gap:12px;align-items:center;flex-wrap:wrap"><b>${j + 1} · ${esc(x.row.source)}</b> ${cellSvg(x.c.title, null, 160)} <span class="small">title ${accText(x.c.title)}</span></span>`)]))) return;

    // 04 · locate (Telem)
    const bp = bestProvider(seg);
    d = await step("04 · Locate " + TELEM, `<div class="small">Provider library: for ${esc(segInfo.name)}, <b>${esc(bp.p)}</b> reaches the reference most often (${pct(bp.r.mean)} of calls).</div><div class="lines"></div>`, 100);
    if (!d) return;
    const locs = ranked.map((x) => {
      const pp = pairOf(x.row, seg, u.company);
      if (!pp || pp.status === "not_found") return `<span class="muted">${esc(x.row.source)} — not found by search for ${esc(co.name)}</span>`;
      if (pp.status !== "ok") return `<span class="bad">${esc(x.row.source)} — the site refused automated reading (${esc(pp.status.replace("failed: ", ""))})</span>`;
      return `${esc(x.row.source)} — page found <span class="small">${esc((pp.url || "").replace(/^https?:\/\/(www\.)?/, "").slice(0, 70))}</span>`;
    });
    if (!(await lines(d, locs, 230))) return;

    // 05 · read & verify
    d = await step("05 · Verify", `<div class="small">Each page saved unchanged; people extracted with quotes; matched to ${esc(co.ref_kind)}.</div><div class="lines"></div>`, 100);
    if (!d) return;
    const ver = ranked.map((x) => ({ x, pp: pairOf(x.row, seg, u.company) })).filter((v) => v.pp && v.pp.status === "ok").map(({ x, pp }) => {
      const ok = pp.checks.filter((c) => c.employment === "correct").length, wrong = pp.checks.filter((c) => c.verdict === "wrong").length;
      return `${esc(x.row.source)} — <span class="ok">${ok}/${pp.n_people}</span> confirmed${wrong ? ` · <span class="bad">${wrong} title${wrong > 1 ? "s" : ""} disagree</span>` : ""} <span class="small">· ${pp.n_people - ok} unverifiable (not in the reference)</span>`;
    });
    if (!(await lines(d, ver.length ? ver : ['<span class="muted">No readable source page for this company.</span>'], 230))) return;
    if (!(await step("06 · Answer", `<span class="small">Below: the answer, then the benchmark for this question.</span>`, 300))) return;

    const res = document.getElementById("result");
    res.className = "fade";
    res.innerHTML = answer(u, co, seg) + benchmark(u, co, seg, ranked);
    await sleep(30);
    res.classList.add("show");
    if (!fast) res.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function answer(u, co, seg) {
    const mk = u.dept === "marketing";
    if (u.company === "samsung-electronics" && mk) {
      const a = D.samsung_answer, n = a.units.reduce((s, x) => s + x.people.length, 0);
      return `<section><p class="label">THE ANSWER</p><h2>${n} marketing executives in ${a.units.length} units</h2>
        <p class="small">Cited from DART — Samsung Electronics' 2025 annual report (<a href="${esc(a.url)}">${esc(a.rcept_no)}</a>, raw ${esc(a.sha)}…). Heads in bold.</p>
        <div class="units">${a.units.map((x) => `<div class="unit"><h4 lang="ko">${esc(x.unit)}</h4><p class="mono">${x.people.length} executives</p>
          ${x.people.map((p) => `<div class="person ${p.head ? "head" : ""}"><span lang="ko">${esc(p.name)} · ${esc(p.rank)}</span><span lang="ko">${esc(p.role)}</span></div>`).join("")}</div>`).join("")}</div></section>`;
    }
    const confirmed = new Map(), claimed = new Map();
    D.library.forEach((row) => {
      const pp = pairOf(row, seg, u.company);
      if (!pp) return;
      pp.checks.forEach((ch) => {
        const ok = ch.employment === "correct";
        if (!ok && !(mk && isMk(ch.title))) return;
        const target = ok ? confirmed : claimed, key = ch.name.toLowerCase();
        const e = target.get(key) || { ...ch, sources: [] };
        e.sources.push(row.source);
        target.set(key, e);
      });
    });
    const conf = [...confirmed.values()].filter((x) => !mk || isMk(x.title));
    const refMk = co.marketing_rows || [];
    const table = (rows, verified) => rows.length ? `<table><tr><th>Person</th><th>Title on source</th>${verified ? "<th>Reference row</th><th>Title check</th>" : ""}<th>Cited by</th></tr>
      ${rows.map((x) => `<tr><td><b>${esc(x.name)}</b></td><td>${esc(x.title)}</td>${verified ? `<td class="small" lang="ko">${esc(x.ref)}</td><td class="v-${x.verdict}">${x.verdict}</td>` : ""}<td class="small">${x.sources.map(esc).join(", ")}</td></tr>`).join("")}</table>` : '<p class="small">None.</p>';
    const refBlock = refMk.length
      ? `<table><tr><th>Name</th><th>Title</th><th>Responsibility</th></tr>${refMk.map((r) => `<tr><td lang="ko"><b>${esc(r.name)}</b></td><td lang="ko">${esc(r.title)}</td><td class="small" lang="ko">${esc(r.role)}</td></tr>`).join("")}</table>`
      : `<p class="small">The reference lists no marketing executives${u.company === "sk-hynix" ? " (SK hynix is B2B; its commercial executives are titled Global Sales)" : seg === "kr_listed" ? "" : " — official filings here stop at the top officers"}.</p>`;
    return `<section><p class="label">THE ANSWER</p><h2>${mk ? "Marketing leaders" : "Leaders"} of ${esc(co.name)}</h2>
      ${mk ? `<h3>In the reference — ${esc(co.ref_kind)}</h3>${refBlock}` : ""}
      <h3>Confirmed by sources</h3>${table(mk ? conf : [...confirmed.values()], true)}
      ${mk ? `<h3>Named by sources, not verifiable</h3><p class="small">Marketing people that sources list but no official reference covers — shown, never counted as correct or wrong.</p>${table([...claimed.values()], false)}` : ""}</section>`;
  }

  function benchmark(u, co, seg, ranked) {
    const rows = ranked.map((x) => {
      const pp = pairOf(x.row, seg, u.company);
      const status = !pp || pp.status === "not_found" ? "not found" : pp.status !== "ok" ? "blocked" : `${pp.checks.filter((c) => c.employment === "correct").length}/${pp.n_people} confirmed`;
      return `<tr><td><b>${esc(x.row.source)}</b><br><span class="small">tier ${x.row.tier}</span></td><td>${cellSvg(x.c.title, x.c.coverage)}</td>
        <td class="small">title ${accText(x.c.title)}<br>${x.c.coverage.found}/${x.c.coverage.total} top leaders in ${esc(D.segments[seg].name)}</td>
        <td class="small">${status}</td><td class="small">${pp ? usd(pp.usd) : "$0"}</td></tr>`;
    }).join("");
    const cost = ranked.reduce((s, x) => { const pp = pairOf(x.row, seg, u.company); return s + (pp ? pp.usd : 0); }, 0);
    const ok = ranked.filter((x) => { const pp = pairOf(x.row, seg, u.company); return pp && pp.status === "ok"; }).length;
    return `<section><p class="label">THE BENCHMARK FOR THIS QUESTION</p><h2>Accuracy, coverage, cost</h2>
      <div class="kpis"><div class="kpi"><b>${co.ref_size}</b><span class="mono">people in the reference</span></div>
        <div class="kpi"><b>${ok}/${ranked.length}</b><span class="mono">sources readable</span></div>
        <div class="kpi"><b>${usd(cost)}</b><span class="mono">cost of this answer ${TELEM}</span></div></div>
      <p class="small">Accuracy and coverage are the library's segment-level numbers (${esc(D.segments[seg].name)}); status and cost are for ${esc(co.name)}.
      <a href="#/type/org_chart/${seg}">Open the segment →</a></p>
      <div class="scroll"><table><tr><th>Source</th><th>Accuracy · coverage</th><th></th><th>This company</th><th>Cost</th></tr>${rows}</table></div></section>`;
  }

  /* ---------- providers & method ---------- */
  function providersPage() {
    const head = SEGS.map((g) => `<th>${esc(D.segments[g].name)}</th>`).join("");
    const body = D.providers.map((p) => `<tr><td><b>${esc(p.provider)}</b>${p.provider === "auto" ? '<br><span class="small">Telem auto-routing</span>' : ""}</td>${SEGS.map((g) => {
      const s = p.segments[g];
      if (!s) return "<td>–</td>";
      const r = s.reference_found;
      return `<td>${cellSvg({ state: r.state, mean: r.mean, interval: [r.lo, r.hi], n: r.den }, null)}<div class="small">reference found in <b>${r.num}/${r.den}</b> calls (${pct(r.mean)}) · ${s.pairs_found} source pages · ${usd(s.usd)} · ${s.latency_s ? s.latency_s.toFixed(1) + " s" : "–"}</div></td>`;
    }).join("")}</tr>`).join("");
    view.innerHTML = `<p class="crumbs"><a href="#/">Dashboard</a> / Provider library</p><p class="label">PROVIDER LIBRARY ${TELEM}</p>
      <h2>Which search provider reaches the sources</h2><p class="note">The planner's queries through every provider behind Telem. <b>Reference found</b>: share of calls that returned the segment's
      official reference (DART · SEC · the company's own site). The router uses it to pick the provider that locates a source's page.</p>
      <div class="scroll"><table><tr><th>Provider</th>${head}</tr>${body}</table></div>`;
  }
  function methodPage() {
    const steps = [["01", "Plan", "A model plans publisher categories per segment — never specific websites."], ["02", "Discover " + TELEM, `Every query through every provider: ${D.stats.seg_calls} calls, ${usd(D.stats.seg_usd)}.`],
      ["03", "Pick", "Domains found for at least three companies become candidate sources."], ["04", "Read", "Pages saved unchanged; people extracted with quotes that must be on the page."],
      ["05", "Verify", "Each person matched to the segment's reference; the match quotes the reference row."], ["06", "Score", "Beta posterior per source × segment: accuracy, 90% interval, coverage, cost."],
      ["07", "Route " + TELEM, "At question time: cite in library order; locate pages with the best provider."], ["08", "Keep current " + TELEM, "Designed: re-checks, verdict expiry, a news monitor."]];
    view.innerHTML = `<p class="crumbs"><a href="#/">Dashboard</a> / Method</p><h2>How the library is built and kept honest</h2>
      <div class="steps">${steps.map(([n, t, d]) => `<div class="step"><span class="mono">${n}</span><b>${t}</b><span class="small">${d}</span></div>`).join("")}</div>
      <h3>The planner, per segment</h3><div class="plans">${SEGS.map((g) => `<div class="plan"><p class="label">${esc(D.segments[g].name)}</p><ul>${D.plans[g].map((c) => `<li><b>${esc(c.name)}</b><br><span class="small">${c.queries.map(esc).join(" · ")}</span></li>`).join("")}</ul></div>`).join("")}</div>
      <div class="limits"><p class="label">HONEST LIMITS</p><ul><li>Three companies per segment: intervals are wide.</li><li>Outside Korea, official filings list only top officers: most marketing claims are unverifiable, never wrong.</li>
      <li>Employment can only be confirmed with these references; title accuracy is the number that exposes errors.</li><li>Extraction and matching are model calls that must quote; the judge's error rate is not measured against humans.</li>
      <li>This site replays measured results; the live mode (model + Telem per query) is the next step.</li></ul></div>`;
  }

  route();
})();
