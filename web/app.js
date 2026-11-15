/* sourcemap — interactive replay site. Renders window.SOURCEMAP (scripts/build_web.py).
   Views (hash routes): #/ dashboard · #/search?q= · #/type/<type>[/<segment>] · #/type/org_chart/providers · #/method
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
  const DEPT_RE = { marketing: /market|brand|cmo|마케팅/i, product: /product|\bcpo\b|프로덕트/i };
  const isDept = (d, t) => !!(DEPT_RE[d] && DEPT_RE[d].test(t || ""));

  /* ---------- query understanding (in the browser, rule-based) ---------- */
  const ALIASES = {
    "samsung-electronics": ["samsung electronics", "samsung", "삼성전자", "삼성"], "sk-hynix": ["sk hynix", "hynix", "sk하이닉스", "하이닉스"],
    naver: ["naver", "네이버"], nvidia: ["nvidia", "엔비디아"], apple: ["apple", "애플"], microsoft: ["microsoft", "msft", "마이크로소프트"],
    airbus: ["airbus", "에어버스"], sap: [" sap "], siemens: ["siemens", "지멘스"],
    alphabet: ["alphabet", "google"], amazon: ["amazon"], meta: [" meta ", "facebook"], tesla: ["tesla"], broadcom: ["broadcom"],
    jpmorgan: ["jpmorgan", "jp morgan", "chase"], "eli-lilly": ["eli lilly", " lilly"], sprinklr: ["sprinklr"], typeform: ["typeform"],
  };
  const TYPE_WORDS = {  // checked in this order: "leadership changes" must win over "leadership"
    leadership_signals: ["leadership change", "executive change", "changes", "appointed", "appointment", "departure", "departed",
      "who left", "who joined", "stepped down", "steps down", "hired", "joins", "8-k", "인사"],
    org_chart: ["org chart", "orgchart", "organization", "organisation", "leadership", "executive", "who leads", "who runs", "leads ", "team", "조직도", "임원", "경영진"],
    technographics: ["tech stack", "technographic", "tools", "software", "stack", "uses", "기술 스택"],
  };
  const DEPTS = { marketing: ["marketing", "brand", "cmo", "마케팅"], sales: ["sales", "영업"], engineering: ["engineering", "r&d", "개발"], finance: ["finance", "cfo", "재무"], product: ["product", "cpo", "프로덕트"] };
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
    if (h.startsWith("#/type/")) {
      let [, , type, seg] = h.slice(1).split("/");
      const m = (type || "").match(/^(\w+)\?c=([\w-]+)$/);  // #/type/org_chart?c=nvidia opens that company's graph
      if (m) { type = m[1]; typePage.sel = m[2]; }
      if (type === "org_chart" && seg === "providers") return providersPage();
      return seg ? segmentPage(type, seg) : typePage(type);
    }
    if (h === "#/providers") { location.replace("#/type/org_chart/providers"); return; }
    if (h === "#/method") return methodPage();
    return dashboard();
  }
  window.addEventListener("hashchange", route);
  const go = (q) => { location.hash = "#/search?q=" + encodeURIComponent(q); };

  // Example questions under the search box: org charts with a measured answer, plus one leadership-change question.
  const EXAMPLES = [
    { q: "Marketing org chart of Samsung Electronics", co: "samsung-electronics", dept: "marketing" },
  ].filter((x) => D.companies[x.co]);
  function searchBox(value = "") {
    const sugg = EXAMPLES.map((x) => x.q);
    sugg.splice(1, 0, "Leadership changes at Nvidia");
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
    if (t.slug === "leadership_signals" && t.status === "measured" && D.signals && window.SignalsUI) return window.SignalsUI.card(t, D);
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
    if (type === "leadership_signals" && D.signals && window.SignalsUI) {
      view.innerHTML = `<p class="crumbs"><a href="#/">Dashboard</a> / ${esc(t.name)}</p>${window.SignalsUI.typePage(D)}`;
      return;
    }
    view.innerHTML = type === "org_chart"
      ? `${orgTabs("sources")}<h2>Which source to cite — by segment</h2>${sourceMap(type)}`
      : `<p class="crumbs"><a href="#/">Dashboard</a> / ${esc(t.name)}</p><h2>${esc(t.name)} — the source map</h2>${sourceMap(type)}`;
  }
  // Org chart page has two tabs: compare the sources to cite, and compare the search providers that find them.
  function orgTabs(active) {
    const tab = (k, href, label, sub) => `<a class="otab${k === active ? " on" : ""}" href="${href}"${k === active ? ' aria-current="page"' : ""}><b>${label}</b><span>${sub}</span></a>`;
    return `<p class="crumbs"><a href="#/">Dashboard</a> / Org chart</p>
      <nav class="otabs" aria-label="Org chart views">${tab("sources", "#/type/org_chart", "Sources", "which website to cite, per segment")}${tab("providers", "#/type/org_chart/providers", `Search providers ${TELEM}`, "which search API finds those websites")}</nav>`;
  }
  function sourceMap(type) {
    const cos = (g) => Object.values(D.companies).filter((c) => c.segment === g).map((c) => c.name).join(", ");
    const head = SEGS.map((g) => `<th><a href="#/type/${type}/${g}">${esc(D.segments[g].name)}</a>
      <div class="seghead"><span>Size: ${esc(D.segments[g].size || "")}</span><span>Companies: ${esc(cos(g))}</span><span>Checked against: ${esc(D.segments[g].reference)}</span></div></th>`).join("");
    const body = D.library.map((row) => `<tr><td><b>${esc(row.source)}</b><br><span class="small">tier ${row.tier} prior</span></td>${SEGS.map((g) => {
      const c = row.segments[g];
      return `<td class="cell" onclick="location.hash='#/type/${type}/${g}'">${cellSvg(c.title, c.coverage)}<div class="small">title ${accText(c.title)}</div>
        <div class="small">${c.coverage.found}/${c.coverage.total} top leaders · ${c.marketing.found}/${c.marketing.total} marketing · ${usd(c.usd)}</div></td>`;
    }).join("")}</tr>`).join("");
    return `<p class="note">Which sources to trust for org-chart data, by segment. A segment is a <b>country × company size</b>: the same source can be
      reliable for large companies and thin for small ones, so each is measured separately. ${SEGS.length} segments are measured so far, two of them mid-size;
      other countries and sizes (e.g. Korean mid-caps) would be separate segments.</p>
      <p class="note"><span class="key"><svg width="54" height="10"><rect x="0" y="3" width="54" height="4" fill="${LINE}"/><rect x="0" y="3" width="30" height="4" fill="${INK}"/></svg> coverage of top leaders</span>
      <span class="key"><svg width="12" height="12"><rect width="12" height="12" fill="${BLUE}"/></svg> title accuracy</span>
      <span class="key"><svg width="54" height="12"><line x1="4" y1="6" x2="50" y2="6" stroke="${INK}"/><line x1="4" y1="2" x2="4" y2="10" stroke="${INK}"/><line x1="50" y1="2" x2="50" y2="10" stroke="${INK}"/></svg> 90% interval</span> Click a cell to open a segment's checks.</p>
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
    let d = await step("01 · Understand", `<div class="chips" id="tchips">${chips}</div><div class="small" style="margin-top:8px">entity: <b>${esc(u.company ? (D.companies[u.company] || (D.signals && D.signals.companies && D.signals.companies[u.company]) || { name: u.company }).name : u.guessName || "not recognised")}</b>${u.dept ? ` · department: <b>${u.dept}</b>` : ""} · data type: <b>${esc(typeName)}</b></div>`, 400);
    if (!d) return;
    document.querySelectorAll("#tchips .chip").forEach((c) => c.classList.toggle("hit", c.dataset.t === u.type));
    if (!(await wait(500))) return;

    if (u.type === "leadership_signals" && D.signals && window.SignalsUI) {
      const SC = D.signals.companies || { nvidia: { name: "Nvidia" }, apple: { name: "Apple" }, microsoft: { name: "Microsoft" } };
      const US = Object.keys(SC);
      if (!u.company || !US.includes(u.company)) {
        await step("02 · Segment", `<div class="notfound"><b>Leadership-change signals are measured for US mega-cap only</b> (Nvidia, Apple, Microsoft), against SEC 8-K Item 5.02.<br>
          <span class="small">${u.company && D.companies[u.company] ? esc(D.companies[u.company].name) + " is in " + esc(D.segments[D.companies[u.company].segment].name) + ", not measured for this data type yet." : "Try “Leadership changes at Nvidia”."}</span></div>`, 300);
        return;
      }
      const co = { name: SC[u.company].name };
      d = await step("02 · Segment", `<div class="chips" id="schips">${SEGS.map((g) => `<span class="chip" data-g="${g}">${esc(D.segments[g].name)}</span>`).join("")}</div>
        <div class="small" style="margin-top:8px">${esc(co.name)} → <b>${esc(D.segments.us_listed.name)}</b> — verified against <b>SEC 8-K Item 5.02 (official filing)</b></div>`, 300);
      if (!d) return;
      for (const g of SEGS) { document.querySelectorAll("#schips .chip").forEach((c) => c.classList.toggle("hit", c.dataset.g === g)); if (!(await wait(220))) return; if (g === "us_listed") break; }
      const rk = window.SignalsUI.rankedSources(D).slice(0, 6), T = D.signals.total_ref_events;
      d = await step("03 · Cite", `<div class="small">Source library · leadership changes × US mega-cap, in order:</div><div class="lines"></div>`, 100);
      if (!d) return;
      if (!(await lines(d, [`<b>0 · SEC 8-K Item 5.02</b> <span class="small">reference · tier 1 · ${T} changes filed</span>`,
        ...rk.map((x, j) => `<b>${j + 1} · ${esc(x.source)}</b> <span class="small">reported ${x.coverage.found} of ${T} · accuracy ${x.accuracy.state === "measured" ? pct(x.accuracy.mean) : x.accuracy.state.replace(/_/g, " ")}</span>`)]))) return;
      d = await step("04 · Locate " + TELEM, `<div class="small">Searched every provider for ${esc(co.name)}'s executive changes; pages saved unchanged.</div><div class="lines"></div>`, 100);
      if (!d) return;
      if (!(await lines(d, rk.map((x) => x.companies.includes(u.company) ? `${esc(x.source)} — ${x.events.filter((e) => e.company === u.company).length} report${x.events.filter((e) => e.company === u.company).length === 1 ? "" : "s"} found`
        : `<span class="muted">${esc(x.source)} — nothing found for ${esc(co.name)}</span>`), 220))) return;
      d = await step("05 · Verify", `<div class="small">Each report matched to the 8-K filings: same person and same kind of change.</div><div class="lines"></div>`, 100);
      if (!d) return;
      if (!(await lines(d, rk.filter((x) => x.events.some((e) => e.company === u.company)).map((x) => { const ev = x.events.filter((e) => e.company === u.company);
        const ok = ev.filter((e) => e.verdict === "correct").length, bad = ev.filter((e) => e.verdict === "wrong").length;
        return `${esc(x.source)} — <span class="ok">${ok} match a filing</span>${bad ? ` · <span class="bad">${bad} contradict one</span>` : ""} <span class="small">· ${ev.length - ok - bad} not in any 8-K</span>`; }), 220))) return;
      if (!(await step("06 · Answer", `<span class="small">Below: the filed changes and who reported them, then the benchmark.</span>`, 300))) return;
      const res = document.getElementById("result");
      res.className = "fade";
      res.innerHTML = window.SignalsUI.answer(D, u.company);
      await sleep(30);
      res.classList.add("show");
      if (!fast) res.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    if (u.type !== "org_chart") {
      const t = D.data_types.find((x) => x.slug === u.type);
      await step("02 · Library", `<div class="notfound"><b>${t ? esc(t.name) + " is designed but not built yet." : "No data type recognised."}</b><br>
        <span class="small">${t ? esc(t.plan) : "Try an org-chart question, e.g. “Marketing department org chart of Samsung Electronics”."}</span></div>`, 300);
      return;
    }
    if (!u.company || !D.companies[u.company]) {
      const nm = u.company && D.signals && D.signals.companies && D.signals.companies[u.company] ? D.signals.companies[u.company].name : u.guessName;
      await step("02 · Segment", `<div class="notfound"><b>${esc(nm || "This company")} is not in the org-chart library yet.</b><br>
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
    d = await step("04 · Locate " + TELEM, `<div class="small"><a href="#/type/org_chart/providers">Search providers</a>: for ${esc(segInfo.name)}, <b>${esc(bp.p)}</b> reaches the reference most often (${pct(bp.r.mean)} of calls).</div><div class="lines"></div>`, 100);
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
    if (window.renderDartChart) res.querySelectorAll("[data-dartchart]").forEach((el) => window.renderDartChart(el, D.samsung_answer));
    if (window.renderMarketingChart) res.querySelectorAll("[data-mktchart]").forEach((el) => window.renderMarketingChart(el, D.marketing_depth[el.dataset.mktchart]));
    await sleep(30);
    res.classList.add("show");
    if (!fast) res.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function answer(u, co, seg) {
    const mk = u.dept === "marketing";
    if (u.company === "samsung-electronics" && mk) {
      const a = D.samsung_answer, n = a.units.reduce((s, x) => s + x.people.length, 0);
      return `<section><p class="label">THE ANSWER</p><h2>${n} marketing executives in ${a.units.length} units</h2>
        <p class="small">Every person below is from DART — Samsung Electronics' 2025 annual report (<a href="${esc(a.url)}">${esc(a.rcept_no)}</a>, raw ${esc(a.sha)}…), as of 2025-12-31.
        The structure comes from each executive's responsibility (담당업무): division → unit → center → people.</p>
        <div data-dartchart></div>
        <details style="margin-top:28px"><summary class="mono">Show as a list</summary>
        <p class="small">English names: a source's own spelling where one named the person, otherwise romanized (marked *). LinkedIn: only when the profile title shows the exact name,
        Samsung Electronics, and an executive or marketing role (or a source-spelled name) — found by search, not verified.</p>
        <div class="units">${a.units.map((x) => `<div class="unit"><h4 lang="ko">${esc(x.unit)}</h4><p class="mono">${x.people.length} executives</p>
          ${x.people.map((p) => `<div class="person ${p.head ? "head" : ""}"><span><span class="en">${esc(p.en || "")}${p.en_from && p.en_from.startsWith("romanized") ? "*" : ""}</span> <span class="muted" lang="ko">${esc(p.name)} · ${esc(p.rank)}</span>${p.linkedin ? ` <a class="li" href="${esc(p.linkedin)}" target="_blank" rel="noopener">LinkedIn ↗</a>` : ""}</span><span lang="ko">${esc(p.role)}</span></div>`).join("")}</div>`).join("")}</div></details></section>`;
    }
    const dp = DEPT_RE[u.dept] ? u.dept : null, dword = dp === "product" ? "product" : "marketing", Dword = dword[0].toUpperCase() + dword.slice(1);
    const confirmed = new Map(), claimed = new Map();
    D.library.forEach((row) => {
      const pp = pairOf(row, seg, u.company);
      if (!pp) return;
      pp.checks.forEach((ch) => {
        const ok = ch.employment === "correct";
        if (!ok && !(dp && isDept(dp, ch.title))) return;
        const target = ok ? confirmed : claimed, key = ch.name.toLowerCase();
        const e = target.get(key) || { ...ch, sources: [] };
        e.sources.push(row.source);
        target.set(key, e);
      });
    });
    const conf = [...confirmed.values()].filter((x) => !dp || isDept(dp, x.title) || isDept(dp, x.ref));
    const refMk = (dp === "product" ? co.product_rows : co.marketing_rows) || [];
    const table = (rows, verified) => rows.length ? `<table><tr><th>Person</th><th>Title on source</th>${verified ? "<th>Reference row</th><th>Title check</th>" : ""}<th>Cited by</th></tr>
      ${rows.map((x) => `<tr><td><b>${esc(x.name)}</b></td><td>${esc(x.title)}</td>${verified ? `<td class="small" lang="ko">${esc(x.ref)}</td><td class="v-${x.verdict}">${x.verdict}</td>` : ""}<td class="small">${x.sources.map(esc).join(", ")}</td></tr>`).join("")}</table>` : '<p class="small">None.</p>';
    const refBlock = refMk.length
      ? `<table><tr><th>Name</th><th>Title</th><th>Responsibility</th></tr>${refMk.map((r) => `<tr><td lang="ko"><b>${esc(r.name)}</b></td><td lang="ko">${esc(r.title)}</td><td class="small" lang="ko">${esc(r.role)}</td></tr>`).join("")}</table>`
      : `<p class="small">The reference lists no ${dword} executives${u.company === "sk-hynix" ? " (SK hynix is B2B; its commercial executives are titled Global Sales)" : seg === "kr_listed" ? "" : " — official filings here stop at the top officers"}.</p>`;
    return `<section><p class="label">THE ANSWER</p><h2>${dp ? Dword + " leaders" : "Leaders"} of ${esc(co.name)}</h2>
      ${dp === "marketing" && D.marketing_depth && D.marketing_depth[u.company] ? `<h3>The marketing organisation</h3>
        <p class="small">${esc(co.ref_kind)} names only the top officers, so the levels below come from ${esc(co.name)}'s own website and other sites, each marked by evidence.</p>
        <div data-mktchart="${esc(u.company)}"></div>` : ""}
      ${dp ? `<h3>In the reference — ${esc(co.ref_kind)}</h3>${refBlock}` : ""}
      <h3>Confirmed by sources</h3>${table(dp ? conf : [...confirmed.values()], true)}
      ${dp ? `<h3>Named by sources, not verifiable</h3><p class="small">${Dword} people that sources list but no official reference covers — shown, never counted as correct or wrong.</p>${table([...claimed.values()], false)}` : ""}</section>`;
  }

  function benchmark(u, co, seg, ranked) {
    const dp = DEPT_RE[u.dept] ? u.dept : null, mk = !!dp, dword = dp === "product" ? "product" : "marketing";
    const segName = D.segments[seg].name;
    // what the question asks for: the reference's marketing executives (or all its people for a leadership question)
    const target = dp === "product" ? co.ref_product : mk ? (u.company === "samsung-electronics" ? D.samsung_answer.units.reduce((n, x) => n + x.people.length, 0) : co.ref_marketing) : co.ref_size;
    const isRefMk = (q) => isDept(dp || "marketing", q);
    const rows = ranked.map((x) => {
      const pp = pairOf(x.row, seg, u.company);
      const status = !pp || pp.status === "not_found" ? "not found by search" : pp.status !== "ok" ? "site blocks reading" : pp.n_people ? "read" : "read · no people";
      const conf = pp ? pp.checks.filter((c) => c.employment === "correct") : [];
      const named = mk ? conf.filter((c) => isRefMk(c.ref)).length : conf.length;
      const titles = pp ? pp.checks.filter((c) => c.verdict === "correct" || c.verdict === "wrong") : [];
      return { x, pp, status, conf: conf.length, named, people: pp ? pp.n_people : 0, titlesOk: titles.filter((c) => c.verdict === "correct").length,
        titlesN: titles.length, usd: pp ? pp.usd : 0, perPerson: conf.length && pp ? pp.usd / conf.length : null };
    });
    const readable = rows.filter((r) => r.status === "read");
    const pick = (f, asc) => readable.filter((r) => f(r) != null).sort((a, b) => (asc ? f(a) - f(b) : f(b) - f(a)))[0];
    const bestCov = target ? pick((r) => r.named) : null;
    const bestAcc = pick((r) => (r.x.c.title.state === "measured" ? r.x.c.title.mean : null));
    const bestCost = pick((r) => r.perPerson, true);
    const maxUsd = Math.max(...rows.map((r) => r.usd), 0.001);
    const totalUsd = rows.reduce((s, r) => s + r.usd, 0);

    function hbar(frac, best, iv, w = 150) {
      const X = (v) => 1 + (w - 2) * Math.max(0, Math.min(1, v));
      let s = `<svg width="${w}" height="14" aria-hidden="true"><rect x="1" y="2" width="${w - 2}" height="10" fill="#f1f2f5"/>`;
      if (frac > 0) s += `<rect x="1" y="2" width="${Math.max(2, X(frac) - 1)}" height="10" fill="${best ? BLUE : INK}"/>`;
      if (iv) s += `<path d="M${X(iv[0])} 0v14M${X(iv[0])} 7H${X(iv[1])}M${X(iv[1])} 0v14" stroke="${GREY}" fill="none"/>`;
      return s + "</svg>";
    }
    const val = (txt, best) => `<span class="bv${best ? " best" : ""}">${txt}</span>`;
    const covCell = (r) => !target ? '<span class="muted">reference lists none</span>'
      : r.status !== "read" ? `<span class="muted">—</span>`
      : `${hbar(r.named / target, r === bestCov && r.named > 0)}${val(`${r.named} of ${target}`, r === bestCov && r.named > 0)}<div class="small">${r.conf} of ${r.people} people on the page confirmed</div>`;
    const accCell = (r) => {
      const t = r.x.c.title;
      if (t.state === "unmeasured") return '<span class="muted">not measured yet</span>';
      const best = r === bestAcc;
      return `${hbar(t.mean ?? (t.interval[0] + t.interval[1]) / 2, best, t.interval)}${val(t.state === "measured" ? pct(t.mean) : "not enough data", best)}
        <div class="small">${segName}: ${t.n} titles checked${t.n_wrong ? `, ${t.n_wrong} wrong` : ""}${r.titlesN ? ` · here ${r.titlesOk} of ${r.titlesN} correct` : ""}</div>`;
    };
    const costCell = (r) => r.status !== "read" ? `${val(usd(r.usd), false)}<div class="small">spent finding it</div>`
      : `${hbar(r.usd / maxUsd, r === bestCost, null)}${val(usd(r.usd), r === bestCost)}<div class="small">${r.perPerson != null ? usd(r.perPerson) + " per confirmed person" : "no confirmed person"}</div>`;
    const verdict = (r) => [r === bestCov && r.named > 0 && "most coverage", r === bestAcc && "most accurate", r === bestCost && "cheapest per person"].filter(Boolean).join(" · ");

    const refRow = `<tr class="refrow"><td><b>${esc(co.ref_kind)}</b><br><span class="small">the reference · tier ${co.ref_tier ?? "–"}</span></td>
      <td>${target ? `${hbar(1, false)}${val(`${target} of ${target}`, false)}<div class="small">the answer comes from here</div>` : '<span class="muted">lists no ${dword} executives</span>'}</td>
      <td>${val("official", false)}<div class="small">what every other source is checked against</div></td>
      <td>${val("$0", false)}<div class="small">free official data</div></td><td class="small">read</td><td></td></tr>`;
    const body = rows.map((r) => `<tr><td><b>${esc(r.x.row.source)}</b><br><span class="small">tier ${r.x.row.tier}</span></td>
      <td>${covCell(r)}</td><td>${accCell(r)}</td><td>${costCell(r)}</td><td class="small">${esc(r.status)}</td><td class="small"><b class="blue">${verdict(r)}</b></td></tr>`).join("");

    const line = target
      ? (bestCov && bestCov.named ? `The answer comes from ${esc(co.ref_kind)}. The best web source, <b>${esc(bestCov.x.row.source)}</b>, names only <b>${bestCov.named} of ${target}</b>.`
        : `The answer comes from ${esc(co.ref_kind)}. No web source names any of its ${target} ${mk ? dword + " executives" : "people"}.`)
      : `${esc(co.ref_kind)} lists no ${mk ? dword + " executives" : "people"}, so web sources can't be checked for this question.`;
    return `<section><p class="label">THE BENCHMARK FOR THIS QUESTION</p><h2>Which source to use — coverage, accuracy, cost</h2>
      <p class="lede" style="margin:8px 0 18px">${line}</p>
      <div class="kpis"><div class="kpi"><b>${target || "—"}</b><span class="mono">${mk ? dword + " execs" : "people"} in the reference</span></div>
        <div class="kpi"><b>${bestCov && bestCov.named ? `${bestCov.named} of ${target}` : "0"}</b><span class="mono">most any web source names</span></div>
        <div class="kpi"><b>${readable.length} of ${rows.length}</b><span class="mono">web sources readable</span></div>
        <div class="kpi"><b>${usd(totalUsd)}</b><span class="mono">cost of this answer ${TELEM}</span></div></div>
      <div class="bhow small"><span><b>Coverage</b> — how many of the reference's ${mk ? dword + " executives" : "people"} the source names (for ${esc(co.name)}).</span>
        <span><b>Accuracy</b> — share of the source's titles that match the reference, across ${esc(segName)} companies; the bracket is the 90% range.</span>
        <span><b>Cost</b> — what finding, reading and checking the source cost for this answer. <b class="blue">Blue</b> = best in the column.</span></div>
      <div class="scroll"><table class="btable"><tr><th>Source</th><th>Coverage</th><th>Accuracy</th><th>Cost</th><th>Status</th><th>Best at</th></tr>${refRow}${body}</table></div>
      <p class="small"><a href="#/type/org_chart/${seg}">See every check behind these numbers →</a></p></section>`;
  }

  /* ---------- providers & method ---------- */
  function providersPage() {
    const st = providersPage.st || (providersPage.st = { seg: "all" });
    const segName = (g) => (g === "all" ? "All segments" : D.segments[g].name);
    const segKeys = ["all", ...SEGS];
    const SOFT_BLUE = "#b7c6f2", AUTO_GREY = "#a9abb6";
    const money = (x) => (x == null ? "–" : x === 0 ? "free" : "$" + (x < 0.01 ? x.toFixed(4) : x.toFixed(3)));
    const all = D.providers.map((p) => ({ name: p.provider, auto: p.provider === "auto", s: p.segments[st.seg], segs: p.segments, why: p.unscorable }));
    const ran = all.filter((r) => r.s && !r.why), notRun = all.filter((r) => !r.s), unscored = all.filter((r) => r.s && r.why);
    const indiv = ran.filter((r) => !r.auto);
    const nProv = indiv.length;
    const callsEach = indiv.length ? indiv[0].s.calls : 0;
    const pool = D.provider_pool[st.seg] || 0;
    const sortBy = (f, asc) => [...ran].sort((a, b) => (asc ? f(a) - f(b) : f(b) - f(a)));
    const bestOf = (f, asc) => (indiv.length ? [...indiv].sort((a, b) => (asc ? f(a) - f(b) : f(b) - f(a)))[0].name : null);
    const findCost = (r) => (r.s.usd_per_find == null ? 1e9 : r.s.usd_per_find);

    /* ---- ranked bar chart: one row per provider, label · bar · value ---- */
    function barChart(rows, opts) {
      const W = 400, LBL = 82, VAL = 74, RH = 22, H = rows.length * RH + 4, x0 = LBL, x1 = W - VAL;
      const X = (v) => x0 + (x1 - x0) * Math.max(0, Math.min(1, v));
      let s = `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="${esc(opts.aria)}">`;
      rows.forEach((r, i) => {
        const y = i * RH + 4, f = opts.frac(r), best = !r.auto && r.name === opts.best;
        s += `<text x="0" y="${y + 12}" font-size="12" font-weight="700" fill="${r.auto ? GREY : INK}">${esc(r.auto ? "auto" : r.name)}</text>`;
        s += `<rect x="${x0}" y="${y + 3}" width="${x1 - x0}" height="11" fill="#f1f2f5"/>`;
        if (f > 0) s += `<rect x="${x0}" y="${y + 3}" width="${Math.max(2, X(f) - x0)}" height="11" fill="${r.auto ? AUTO_GREY : opts.color || BLUE}"/>`;
        if (opts.dark) { const d = opts.dark(r); if (d > 0) s += `<rect x="${x0}" y="${y + 3}" width="${Math.max(2, X(d) - x0)}" height="11" fill="${INK}"/>`; }
        s += `<text x="${W}" y="${y + 12}" font-size="11.5" text-anchor="end" font-family="ui-monospace, Menlo, monospace" font-weight="${best ? 700 : 400}" fill="${best ? BLUE : INK}">${esc(opts.label(r))}</text>`;
      });
      return s + "</svg>";
    }
    const miniTable = (head, rows) => `<details class="astable"><summary>As a table</summary><table class="mini"><tr>${head.map((h) => `<th>${h}</th>`).join("")}</tr>${rows.map((r) => `<tr>${r.map((c) => `<td>${c}</td>`).join("")}</tr>`).join("")}</table></details>`;

    // 01 coverage
    const cov = sortBy((r) => r.s.coverage.mean);
    const p1 = barChart(cov, { aria: "Coverage by provider", best: bestOf((r) => r.s.coverage.mean), color: SOFT_BLUE,
      frac: (r) => r.s.coverage.mean, dark: (r) => (r.s.exclusive || 0) / (pool || 1), label: (r) => (r.auto ? pct(r.s.coverage.mean) : `${pct(r.s.coverage.mean)} · ${r.s.exclusive} alone`) });
    const t1 = miniTable(["Provider", "Good finds", "Coverage", "90% range", "Alone"], cov.map((r) => [esc(r.name), `${r.s.coverage.num} of ${r.s.coverage.den}`, pct(r.s.coverage.mean), `${pct(r.s.coverage.lo)}–${pct(r.s.coverage.hi)}`, r.s.exclusive ?? "–"]));
    // 02 accuracy
    const acc = sortBy((r) => r.s.accuracy.mean);
    const p2 = barChart(acc, { aria: "Accuracy by provider", best: bestOf((r) => r.s.accuracy.mean), frac: (r) => r.s.accuracy.mean, label: (r) => pct(r.s.accuracy.mean) });
    const t2 = miniTable(["Provider", "Good results", "Accuracy", "90% range"], acc.map((r) => [esc(r.name), `${r.s.accuracy.num} of ${r.s.accuracy.den}`, pct(r.s.accuracy.mean), `${pct(r.s.accuracy.lo)}–${pct(r.s.accuracy.hi)}`]));
    // 03 cost (shorter is better)
    const cost = sortBy(findCost, true);
    const maxCost = Math.max(...cost.map((r) => r.s.usd_per_find || 0), 0.001);
    const p3 = barChart(cost, { aria: "Cost per good find by provider", best: bestOf(findCost, true), frac: (r) => (r.s.usd_per_find || 0) / maxCost, label: (r) => (r.s.usd_per_find == null ? "no finds" : money(r.s.usd_per_find)) });
    const t3 = miniTable(["Provider", "Per good find", "Per call", "Total"], cost.map((r) => [esc(r.name), money(r.s.usd_per_find), money(r.s.usd_per_call), money(r.s.usd)]));

    /* ---- 04 scatter: coverage (x) vs accuracy (y), axes fitted to the data ---- */
    function scatter() {
      const W = 600, H = 360, L = 52, R = 110, T = 16, B = 42;
      const xs = ran.map((r) => r.s.coverage.mean), ys = ran.map((r) => r.s.accuracy.mean);
      const step = 0.1, lo = (v) => Math.max(0, Math.floor((Math.min(...v) - 0.03) / step) * step), hi = (v) => Math.min(1, Math.ceil((Math.max(...v) + 0.03) / step) * step);
      const [xa, xb, ya, yb] = [lo(xs), hi(xs), lo(ys), hi(ys)];
      const PAD = 14, X = (v) => L + PAD + (W - L - R - 2 * PAD) * (v - xa) / (xb - xa), Y = (v) => H - B - PAD - (H - T - B - 2 * PAD) * (v - ya) / (yb - ya);
      let s = `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Coverage against accuracy">`;
      for (let v = xa; v <= xb + 1e-9; v += step) s += `<line x1="${X(v)}" y1="${T}" x2="${X(v)}" y2="${H - B}" stroke="${LINE}"/><text x="${X(v)}" y="${H - B + 16}" font-size="11" text-anchor="middle" fill="${GREY}" font-family="ui-monospace, Menlo, monospace">${Math.round(v * 100)}%</text>`;
      for (let v = ya; v <= yb + 1e-9; v += step) s += `<line x1="${L}" y1="${Y(v)}" x2="${W - R}" y2="${Y(v)}" stroke="${LINE}"/><text x="${L - 8}" y="${Y(v) + 4}" font-size="11" text-anchor="end" fill="${GREY}" font-family="ui-monospace, Menlo, monospace">${Math.round(v * 100)}%</text>`;
      s += `<text x="${(L + W - R) / 2}" y="${H - 6}" font-size="10.5" text-anchor="middle" fill="${GREY}" font-family="ui-monospace, Menlo, monospace" letter-spacing="1.2">COVERAGE →</text>`;
      s += `<text x="12" y="${(T + H - B) / 2}" font-size="10.5" text-anchor="middle" fill="${GREY}" font-family="ui-monospace, Menlo, monospace" letter-spacing="1.2" transform="rotate(-90 12 ${(T + H - B) / 2})">ACCURACY →</text>`;
      // labels to the right of each point; push apart when two would overlap
      const pts = ran.map((r) => ({ r, x: X(r.s.coverage.mean), y: Y(r.s.accuracy.mean) })).sort((a, b) => a.y - b.y);
      const placed = [];
      pts.forEach((p) => { let ly = p.y + 4; for (const q of placed) if (Math.abs(q.x - p.x) < 90 && Math.abs(q.ly - ly) < 13) ly = q.ly + 13; placed.push({ x: p.x, ly }); p.ly = ly; });
      pts.forEach((p) => {
        const c = p.r.auto ? AUTO_GREY : BLUE;
        s += p.r.auto ? `<circle cx="${p.x}" cy="${p.y}" r="5.5" fill="#fff" stroke="${GREY}" stroke-width="1.5"/>` : `<circle cx="${p.x}" cy="${p.y}" r="5.5" fill="${c}"/>`;
        if (Math.abs(p.ly - (p.y + 4)) > 1) s += `<line x1="${p.x + 6}" y1="${p.y}" x2="${p.x + 9}" y2="${p.ly - 4}" stroke="${LINE}"/>`;
        s += `<text x="${p.x + 10}" y="${p.ly}" font-size="12" font-weight="700" fill="${p.r.auto ? GREY : INK}">${esc(p.r.name)}</text>`;
      });
      return s + "</svg>";
    }

    /* ---- 05 dot plot: coverage per market, one row per provider ---- */
    function dotPlot() {
      const rows = D.providers.filter((p) => !p.unscorable && SEGS.some((g) => p.segments[g])).sort((a, b) => (b.segments.all?.coverage.mean || 0) - (a.segments.all?.coverage.mean || 0));
      const W = 600, LBL = 84, RH = 26, T = 8, H = rows.length * RH + T + 30, x0 = LBL, x1 = W - 16;
      const X = (v) => x0 + (x1 - x0) * v;
      const mk = [
        (x, y) => `<circle cx="${x}" cy="${y}" r="5" fill="${BLUE}"/>`,
        (x, y) => `<circle cx="${x}" cy="${y}" r="4.5" fill="#fff" stroke="${INK}" stroke-width="1.6"/>`,
        (x, y) => `<rect x="${x - 4.5}" y="${y - 4.5}" width="9" height="9" fill="${INK}" transform="rotate(45 ${x} ${y})"/>`,
        (x, y) => `<rect x="${x - 4}" y="${y - 4}" width="8" height="8" fill="#fff" stroke="${BLUE}" stroke-width="1.6"/>`,
        (x, y) => `<path d="M${x} ${y - 5}L${x + 5} ${y + 4}H${x - 5}Z" fill="${GREY}"/>`,
      ];
      let s = `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Coverage by market for each provider">`;
      [0, 0.25, 0.5, 0.75, 1].forEach((v) => (s += `<line x1="${X(v)}" y1="${T}" x2="${X(v)}" y2="${H - 26}" stroke="${LINE}"/><text x="${X(v)}" y="${H - 10}" font-size="11" text-anchor="middle" fill="${GREY}" font-family="ui-monospace, Menlo, monospace">${v * 100}%</text>`));
      rows.forEach((p, i) => {
        const y = T + i * RH + 12, vals = SEGS.map((g) => p.segments[g]?.coverage.mean).filter((v) => v != null);
        s += `<text x="0" y="${y + 4}" font-size="12" font-weight="700" fill="${p.provider === "auto" ? GREY : INK}">${esc(p.provider)}</text>`;
        if (vals.length > 1) s += `<line x1="${X(Math.min(...vals))}" y1="${y}" x2="${X(Math.max(...vals))}" y2="${y}" stroke="${AUTO_GREY}" stroke-width="1.5"/>`;
        SEGS.forEach((g, k) => { const v = p.segments[g]?.coverage.mean; if (v != null) s += mk[k](X(v), y); });
      });
      return { svg: s + "</svg>", legend: SEGS.map((g, k) => `<span class="lg"><svg width="14" height="14" aria-hidden="true">${mk[k](7, 7)}</svg>${esc(D.segments[g].name)}</span>`).join("") };
    }
    const dp = dotPlot();

    /* ---- full table ---- */
    const fullRows = sortBy((r) => r.s.coverage.mean).map((r) => `<tr><td><b>${esc(r.name)}</b>${r.auto ? ' <span class="small">auto-routing</span>' : ""}</td>
      <td>${pct(r.s.coverage.mean)} <span class="small">${r.s.coverage.num}/${r.s.coverage.den} · ${pct(r.s.coverage.lo)}–${pct(r.s.coverage.hi)}</span></td>
      <td>${r.s.exclusive ?? "–"}</td>
      <td>${pct(r.s.accuracy.mean)} <span class="small">${r.s.accuracy.num}/${r.s.accuracy.den} · ${pct(r.s.accuracy.lo)}–${pct(r.s.accuracy.hi)}</span></td>
      <td>${money(r.s.usd_per_find)}</td><td>${money(r.s.usd_per_call)}</td><td>${money(r.s.usd)}</td>
      <td>${r.s.reference_found ? pct(r.s.reference_found.mean) : "–"}</td><td>${r.s.latency_s ? r.s.latency_s.toFixed(1) + " s" : "–"}</td>
      <td>${r.s.calls}${r.s.failed ? ` <span class="small">${r.s.failed} failed</span>` : ""}</td></tr>`).join("");

    const meta = `${callsEach} queries each · top 5 results · ${Object.keys(D.companies).length} companies in ${SEGS.length} segments · ${pool} good finds · measured ${esc(D.measured_on)}`;
    view.innerHTML = `${orgTabs("providers")}
      <div class="segpick" role="group" aria-label="Segment">${segKeys.map((g) => `<button data-seg="${g}" class="${g === st.seg ? "on" : ""}" aria-pressed="${g === st.seg}">${esc(segName(g))}</button>`).join("")}</div>

      <article class="bcard">
        <p class="label blue">SEARCH PROVIDERS ${TELEM} · ${esc(segName(st.seg).toUpperCase())}</p>
        <h2 class="bh">${nProv} search providers, <span class="blue">measured three ways.</span></h2>
        <p class="bmeta">${meta}</p>
        <div class="bgrid3">
          <div class="bpanel"><p class="label">01 · COVERAGE</p><h3>Who finds the most sources.</h3>${p1}
            <p class="small">Share of all good finds this provider returned. Dark segment = good finds no other provider returned. Grey = Telem auto-routing.</p>${t1}</div>
          <div class="bpanel"><p class="label">02 · ACCURACY</p><h3>How many results are worth reading.</h3>${p2}
            <p class="small">Share of its results that were good finds; the rest were off-topic or unusable pages.</p>${t2}</div>
          <div class="bpanel"><p class="label">03 · COST</p><h3>What one good find costs.</h3>${p3}
            <p class="small">Telem spend divided by good finds. Shorter is better.</p>${t3}</div>
        </div>
        ${notRun.length || unscored.length ? `<p class="small bfoot">${unscored.map((r) => `<b>${esc(r.name)}</b> is not scored: ${esc(r.why)}, so none of its ${r.s.results} results can be matched to a source (${r.s.failed} of ${r.s.calls} calls also failed).`).join(" ")}${notRun.length ? ` Not run in this benchmark yet: ${notRun.map((r) => esc(r.name)).join(", ")}.` : ""}</p>` : ""}
      </article>

      <article class="bcard">
        <div class="bgrid2">
          <div class="bpanel"><p class="label">04 · COVERAGE VS ACCURACY</p><h3>Finding more is not the same as finding well.</h3>${scatter()}
            <p class="small">Up and right is better. Axes do not start at zero. Hollow grey point = Telem auto-routing, which calls several providers at once.</p></div>
          <div class="bpanel"><p class="label">05 · BY MARKET</p><h3>Coverage changes by market.</h3>
            <div class="lgrow">${dp.legend}</div>${dp.svg}
            <p class="small">Coverage of good finds within each segment. The grey line spans a provider's weakest to strongest market.</p></div>
        </div>
      </article>

      <details class="bcard allnums"><summary><span class="label">ALL NUMBERS</span> See every measure for ${esc(segName(st.seg))}</summary>
        <div class="scroll"><table><tr><th>Provider</th><th>Coverage</th><th>Alone</th><th>Accuracy</th><th>$ per find</th><th>$ per call</th><th>Total</th><th>Reference</th><th>Speed</th><th>Calls</th></tr>${fullRows}</table></div>
        <p class="small">Ranges are 90% intervals (Beta(1,1)). A good find is a source in the library for that company, or the official reference (DART · SEC · the company's own site).
          Coverage counts only sources some provider returned. The library's sources were chosen from the first run (exa, you, parallel, brave), so providers added later are scored on finding those.
          Accuracy means the results were relevant; whether the data in those sources is correct is measured per source on the Org chart pages.</p>
      </details>`;
    view.querySelectorAll(".segpick button").forEach((b) => b.addEventListener("click", () => { st.seg = b.dataset.seg; providersPage(); }));
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
