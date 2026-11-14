/* sourcemap frontend — renders window.SOURCEMAP (built by scripts/build_web.py). No libraries; charts are SVG. */
(function () {
  const D = window.SOURCEMAP;
  const SEGS = Object.keys(D.segments);
  const INK = "#14141a", GREY = "#6e6e78", LINE = "#e6e6ea", BLUE = "#1f4fd8";
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const pct = (x) => (x == null ? "–" : Math.round(x * 100) + "%");
  const usd = (x) => (!x ? "$0" : "$" + (x < 0.01 ? x.toFixed(4) : x.toFixed(2)));
  const TELEM = '<span class="telem">TELEM</span>';

  /* --- SVG primitives ---------------------------------------------------------------------- */
  function accColor(s) {
    if (!s || s.state === "unmeasured") return { fill: "url(#hatch)", stroke: LINE };
    if (s.state === "not_enough_data") return { fill: "#fff", stroke: GREY };
    const t = Math.max(0.15, Math.min(1, (s.mean - 0.5) / 0.5));
    return { fill: BLUE, stroke: BLUE, opacity: t };
  }
  const HATCH = `<defs><pattern id="hatch" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="4" stroke="${LINE}" stroke-width="2"/></pattern></defs>`;

  /* accuracy square + interval bracket on a 0..1 axis + optional coverage bar */
  function cellSvg(acc, cov, w = 210) {
    const x0 = 22, x1 = w - 4, X = (v) => x0 + (x1 - x0) * v;
    const c = accColor(acc);
    let s = `<svg width="${w}" height="${cov ? 34 : 18}" role="img">${HATCH}`;
    s += `<rect x="0" y="2" width="14" height="14" fill="${c.fill}" stroke="${c.stroke}" ${c.opacity ? `fill-opacity="${c.opacity}"` : ""}/>`;
    s += `<line x1="${x0}" y1="9" x2="${x1}" y2="9" stroke="${LINE}"/>`;
    [0, 0.5, 1].forEach((v) => (s += `<line x1="${X(v)}" y1="6" x2="${X(v)}" y2="12" stroke="${LINE}"/>`));
    if (acc && acc.interval) {
      const [lo, hi] = acc.interval;
      s += `<line x1="${X(lo)}" y1="9" x2="${X(hi)}" y2="9" stroke="${INK}" stroke-width="1.5"/>`;
      s += `<line x1="${X(lo)}" y1="4" x2="${X(lo)}" y2="14" stroke="${INK}"/><line x1="${X(hi)}" y1="4" x2="${X(hi)}" y2="14" stroke="${INK}"/>`;
      if (acc.mean != null) s += `<circle cx="${X(acc.mean)}" cy="9" r="3" fill="${INK}"/>`;
    }
    if (cov) {
      const f = cov.total ? cov.found / cov.total : 0;
      s += `<rect x="${x0}" y="24" width="${x1 - x0}" height="5" fill="${LINE}"/>`;
      s += `<rect x="${x0}" y="24" width="${Math.max(f > 0 ? 2 : 0, (x1 - x0) * f)}" height="5" fill="${INK}"/>`;
    }
    return s + "</svg>";
  }
  function accText(a) {
    if (!a || a.state === "unmeasured") return '<span class="muted">unmeasured</span>';
    const iv = a.interval ? `[${a.interval[0].toFixed(2)}, ${a.interval[1].toFixed(2)}]` : "";
    const head = a.state === "measured" ? `<b>${a.mean.toFixed(2)}</b>` : '<span class="muted">not enough data</span>';
    return `${head} <span class="small">${iv} n=${a.n}${a.n_wrong ? ` · ${a.n_wrong} wrong` : ""}</span>`;
  }

  /* --- hero ------------------------------------------------------------------------------------ */
  function diagram() {
    const box = (x, y, w, h, title, sub, dark) =>
      `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="${dark ? INK : "#fff"}" stroke="${INK}"/>` +
      `<text x="${x + 14}" y="${y + 24}" font-family="Georgia" font-size="17" fill="${dark ? "#fff" : INK}">${title}</text>` +
      `<text x="${x + 14}" y="${y + 44}" font-family="Arial" font-size="12" fill="${dark ? "#c9c9d2" : GREY}">${sub}</text>`;
    const arrow = (x1, y1, x2, y2, label, blue) =>
      `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${blue ? BLUE : INK}" marker-end="url(#ar${blue ? "b" : ""})"/>` +
      (label ? `<text x="${(x1 + x2) / 2}" y="${(y1 + y2) / 2 - 7}" text-anchor="middle" font-family="Menlo,monospace" font-size="10" letter-spacing="1.2" fill="${blue ? BLUE : GREY}">${label}</text>` : "");
    $("diagram").innerHTML = `<svg viewBox="0 0 1160 250" width="100%" style="max-width:1160px">
      <defs><marker id="ar" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="8" markerHeight="8" orient="auto"><path d="M0,0 L8,4 L0,8" fill="none" stroke="${INK}"/></marker>
      <marker id="arb" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="8" markerHeight="8" orient="auto"><path d="M0,0 L8,4 L0,8" fill="none" stroke="${BLUE}"/></marker></defs>
      ${box(0, 70, 150, 64, "Agent", "a question")}
      ${arrow(150, 102, 300, 102, "DATA TYPE × SEGMENT")}
      <rect x="300" y="20" width="390" height="164" fill="none" stroke="${INK}"/>
      <text x="314" y="42" font-family="Poppins,Arial" font-weight="600" font-size="15">sourcemap</text>
      ${box(314, 54, 362, 56, "Source library", "which sources to cite · accuracy · coverage · cost", true)}
      ${box(314, 118, 362, 56, "Provider library", "which search provider reaches them")}
      ${arrow(690, 82, 820, 82, "CITE")}
      ${box(820, 50, 330, 64, "Trusted sources", "DART · SEC · theorg · Wikipedia · company pages")}
      ${arrow(690, 146, 820, 182, "", true)}
      <text x="755" y="196" text-anchor="middle" font-family="Menlo,monospace" font-size="10" letter-spacing="1.2" fill="${BLUE}">LOCATE · DISCOVER</text>
      <rect x="820" y="150" width="330" height="64" fill="#fff" stroke="${BLUE}"/>
      <text x="834" y="174" font-family="Georgia" font-size="17" fill="${BLUE}">Web search via Telem</text>
      <text x="834" y="194" font-family="Arial" font-size="12" fill="${GREY}">exa · you · parallel · brave · auto-routing</text>
      ${arrow(985, 150, 985, 116, "", true)}
    </svg>`;
    const s = D.stats;
    $("stats").innerHTML = [
      [s.n_companies, "companies"], [SEGS.length, "segments"], [s.n_sources, "sources measured"],
      [s.telem_calls, "Telem search calls " + TELEM], [usd(s.telem_usd), "spent on search"],
    ].map(([v, l]) => `<div class="stat"><b>${v}</b><span class="mono">${l}</span></div>`).join("");
  }

  /* --- ask --------------------------------------------------------------------------------------------- */
  const PRESETS = [
    { company: "samsung-electronics", q: "Marketing department org chart of Samsung Electronics" },
    { company: "nvidia", q: "Marketing leadership of Nvidia" },
    { company: "airbus", q: "Marketing leadership of Airbus" },
  ];
  function bestProvider(seg) {
    let best = null;
    D.providers.forEach((p) => {
      const r = p.segments[seg] && p.segments[seg].reference_found;
      if (r && (!best || r.mean > best.r.mean)) best = { p: p.provider, r };
    });
    return best;
  }
  function rankedSources(seg) {
    const order = { measured: 0, not_enough_data: 1, unmeasured: 2 };
    return D.library
      .map((row) => ({ row, c: row.segments[seg] }))
      .filter((x) => x.c && (x.c.reads.ok || 0) > 0)
      .sort((a, b) => order[a.c.title.state] - order[b.c.title.state] || (b.c.title.mean || 0) - (a.c.title.mean || 0) || b.c.coverage.found - a.c.coverage.found);
  }
  function renderAsk(i) {
    const p = PRESETS[i], co = D.companies[p.company], seg = co.segment, segInfo = D.segments[seg];
    document.querySelectorAll(".presets button").forEach((b, j) => b.classList.toggle("on", j === i));
    const bp = bestProvider(seg);
    const ref = `<div class="srcrow"><span class="rank">0</span><div><b>${esc(co.ref_kind)}</b><br><span class="small">reference · tier ${co.ref_tier ?? "–"}${co.ref_located_by_telem ? " · page located " + TELEM : ""}</span></div>
      <div class="small">${co.ref_size} people · ${co.ref_marketing} in marketing</div>
      <div class="small">${co.ref_failed ? "<b>failed:</b> " + esc(co.ref_failed).slice(0, 120) : `<a href="${esc(co.ref_url)}">open the reference</a>`}</div></div>`;
    const rows = rankedSources(seg).slice(0, 6).map((x, j) => `<div class="srcrow"><span class="rank">${j + 1}</span>
      <div><b>${esc(x.row.source)}</b><br><span class="small">tier ${x.row.tier} prior</span></div>
      <div>${cellSvg(x.c.title, x.c.coverage, 220)}</div>
      <div class="small">title ${accText(x.c.title)} · covers ${x.c.coverage.found}/${x.c.coverage.total} top leaders · ${x.c.marketing.found}/${x.c.marketing.total} marketing execs · ${usd(x.c.usd)}<br>
      locate the page ${TELEM} via <b>${esc(bp ? bp.p : "–")}</b>${bp ? ` (finds the segment reference in ${pct(bp.r.mean)} of calls)` : ""}</div></div>`).join("");
    $("route").innerHTML = `<p class="query">“${esc(p.q)}”</p>
      <div class="route">
        <div class="k mono">Data type</div><div>Org chart · marketing department</div>
        <div class="k mono">Segment</div><div>${esc(segInfo.name)} <span class="small">— verified against ${esc(segInfo.reference)}</span></div>
        <div class="k mono">Cite, in order</div><div>${ref}${rows}</div>
      </div>`;
    $("answer").innerHTML = p.company === "samsung-electronics" ? samsungAnswer() : otherAnswer(p.company);
  }
  function samsungAnswer() {
    const a = D.samsung_answer, n = a.units.reduce((s, u) => s + u.people.length, 0);
    return `<h3>The answer: ${n} marketing executives in ${a.units.length} units</h3>
      <p class="small">From DART, Samsung Electronics' 2025 annual report (<a href="${esc(a.url)}">${esc(a.rcept_no)}</a>,
      raw sha256 ${esc(a.sha)}…). Plain web search returned about ten of them, unverified. Heads in bold.</p>
      <div class="units">${a.units.map((u) => `<div class="unit"><h4 lang="ko">${esc(u.unit)}</h4><p class="mono">${u.people.length} executives</p>
        ${u.people.map((x) => `<div class="person ${x.head ? "head" : ""}"><span lang="ko">${esc(x.name)} · ${esc(x.rank)}</span><span lang="ko">${esc(x.role)}</span></div>`).join("")}</div>`).join("")}</div>`;
  }
  function otherAnswer(slug) {
    const co = D.companies[slug], seen = new Map();
    D.library.forEach((row) => {
      const c = row.segments[co.segment];
      (c ? c.pairs : []).filter((pp) => pp.company === slug).forEach((pp) => pp.checks.forEach((ch) => {
        if (ch.employment !== "correct") return;
        const k = ch.name.toLowerCase();
        const e = seen.get(k) || { name: ch.name, title: ch.title, ref: ch.ref, verdict: ch.verdict, sources: [] };
        e.sources.push(row.source);
        seen.set(k, e);
      }));
    });
    const list = [...seen.values()].sort((a, b) => b.sources.length - a.sources.length);
    const mk = list.filter((x) => /market|brand|cmo/i.test(x.title));
    return `<h3>The answer: ${list.length} leaders confirmed against the reference</h3>
      <p class="small">${esc(co.ref_kind)} lists ${co.ref_size} people, ${co.ref_marketing} in marketing. Marketing leaders below the
      officer level are not in any official reference here — they stay <i>unverifiable</i>, not wrong.
      ${mk.length ? `Confirmed marketing leaders: ${mk.map((x) => esc(x.name)).join(", ")}.` : "No marketing leader could be confirmed."}</p>
      <table><tr><th>Person</th><th>Title on source</th><th>Reference row</th><th>Title check</th><th>Cited by</th></tr>
      ${list.map((x) => `<tr><td><b>${esc(x.name)}</b></td><td>${esc(x.title)}</td><td class="small">${esc(x.ref)}</td>
        <td class="v-${x.verdict}">${x.verdict}</td><td class="small">${x.sources.map(esc).join(", ")}</td></tr>`).join("")}</table>`;
  }

  /* --- source library ----------------------------------------------------------------------------- */
  function renderLibrary() {
    const head = SEGS.map((g) => `<th>${esc(D.segments[g].name)}<br><span style="text-transform:none;letter-spacing:0;font-weight:400">vs ${esc(D.segments[g].reference)}</span></th>`).join("");
    const body = D.library.map((row, i) => `<tr><td><b>${esc(row.source)}</b><br><span class="small">tier ${row.tier} prior</span></td>${SEGS.map((g) => {
      const c = row.segments[g], r = c.reads;
      const reads = `${r.ok || 0} read${r.blocked ? ` · ${r.blocked} blocked` : ""}${r.not_found ? ` · ${r.not_found} not found` : ""}${r.empty ? ` · ${r.empty} empty` : ""}`;
      return `<td class="cell" data-i="${i}" data-g="${g}">${cellSvg(c.title, c.coverage)}<div class="small">title ${accText(c.title)}</div>
        <div class="small">${c.coverage.found}/${c.coverage.total} top leaders · ${c.marketing.found}/${c.marketing.total} marketing · ${reads} · ${usd(c.usd)}</div></td>`;
    }).join("")}</tr>`).join("");
    $("library-table").innerHTML = `<table><tr><th>Source</th>${head}</tr>${body}</table>`;
    document.querySelectorAll("td.cell").forEach((td) => td.addEventListener("click", () => {
      document.querySelectorAll("td.cell.sel").forEach((x) => x.classList.remove("sel"));
      td.classList.add("sel");
      drill(D.library[+td.dataset.i], td.dataset.g);
    }));
  }
  function drill(row, g) {
    const c = row.segments[g];
    $("drill").innerHTML = `<div class="drill"><p class="label">CHECKS BEHIND THIS CELL</p><h3>${esc(row.source)} × ${esc(D.segments[g].name)}</h3>
      ${c.pairs.map((pp) => `<div class="pair"><div class="head"><b>${esc(D.companies[pp.company].name)}</b>
        <span class="small">${esc(pp.status)}${pp.url ? ` · <a href="${esc(pp.url)}">page</a>` : ""}${pp.sha ? ` · raw ${esc(pp.sha)}…` : ""}
        · page found by search ${TELEM}</span></div>
        ${pp.checks.length ? `<div class="scroll"><table><tr><th>Person on source</th><th>Quote on the saved page</th><th>Reference row</th><th>Employment</th><th>Title</th><th>Why</th></tr>
        ${pp.checks.map((ch) => `<tr><td><b>${esc(ch.name)}</b><br><span class="small">${esc(ch.title)}</span></td><td class="quote">“${esc(ch.quote)}”</td>
          <td class="small" lang="ko">${esc(ch.ref) || "—"}</td><td class="v-${ch.employment}">${ch.employment}</td><td class="v-${ch.verdict}">${ch.verdict}</td>
          <td class="small">${esc(ch.reason)}</td></tr>`).join("")}</table></div>` : '<p class="small">No people to check.</p>'}</div>`).join("")}</div>`;
    $("drill").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  /* --- provider library ---------------------------------------------------------------------------- */
  function renderProviders() {
    const head = SEGS.map((g) => `<th>${esc(D.segments[g].name)}</th>`).join("");
    const rows = [...D.providers].sort((a, b) => (b.segments.kr_listed?.reference_found?.mean || 0) - (a.segments.kr_listed?.reference_found?.mean || 0));
    const body = rows.map((p) => `<tr><td><b>${esc(p.provider)}</b>${p.provider === "auto" ? '<br><span class="small">Telem auto-routing</span>' : ""}</td>${SEGS.map((g) => {
      const s = p.segments[g];
      if (!s) return "<td class='small'>–</td>";
      const r = s.reference_found;
      const acc = r ? { state: r.state, mean: r.mean, interval: [r.lo, r.hi], n: r.den, n_wrong: 0 } : null;
      return `<td>${cellSvg(acc, null)}<div class="small">reference found in <b>${r.num}/${r.den}</b> calls (${pct(r.mean)}) · ${s.pairs_found} source pages found ·
        ${usd(s.usd)} · ${s.latency_s ? s.latency_s.toFixed(1) + " s" : "–"}</div></td>`;
    }).join("")}</tr>`).join("");
    $("provider-table").innerHTML = `<table><tr><th>Provider ${TELEM}</th>${head}</tr>${body}</table>`;
  }

  /* --- method ------------------------------------------------------------------------------------------- */
  function renderMethod() {
    const steps = [
      ["01", "Plan", "A model plans publisher categories per segment — filings, own pages, org-chart sites, news — never specific websites."],
      ["02", "Discover " + TELEM, `Every query through every provider behind Telem: ${D.stats.seg_calls} calls, ${usd(D.stats.seg_usd)}.`],
      ["03", "Pick", "Domains found for at least three companies become candidate sources; social and login-only sites are skipped."],
      ["04", "Read", "Each page is saved unchanged; a model extracts people and titles, each with a quote that must be on the page."],
      ["05", "Verify", "Every person is matched to the segment's reference (DART, SEC, own page); the match quotes the reference row."],
      ["06", "Score", "Beta posterior per source × segment: accuracy with a 90% interval, coverage, cost. Unverifiable never counts as wrong."],
      ["07", "Route " + TELEM, "At question time: cite sources in library order; locate each page with the provider that reaches it best."],
      ["08", "Keep current " + TELEM, "Designed, not built today: daily re-checks, verdict expiry, a news monitor that reorders re-checks."],
    ];
    $("steps").innerHTML = steps.map(([n, t, d]) => `<div class="step"><span class="mono">${n}</span><b>${t}</b><span class="small">${d}</span></div>`).join("");
    $("refs").innerHTML = `<h3>What "verified" means per segment</h3><table><tr><th>Segment</th><th>Company</th><th>Reference</th><th>Size</th><th></th></tr>
      ${Object.entries(D.companies).map(([slug, c]) => `<tr><td>${esc(D.segments[c.segment].name)}</td><td><b>${esc(c.name)}</b></td>
        <td>${esc(c.ref_kind)}${c.ref_located_by_telem ? " · page located " + TELEM : ""}</td><td class="small">${c.ref_size} people · ${c.ref_marketing} marketing</td>
        <td class="small">${c.ref_failed ? "<b>failed:</b> " + esc(c.ref_failed).slice(0, 100) : `<a href="${esc(c.ref_url)}">open</a>`}</td></tr>`).join("")}</table>`;
    $("plans").innerHTML = `<h3>The planner, per segment</h3><div class="plans">${SEGS.map((g) => `<div class="plan"><p class="label">${esc(D.segments[g].name)}</p><ul>
      ${D.plans[g].map((c) => `<li><b>${esc(c.name)}</b><br><span class="small">${c.queries.map(esc).join(" · ")}</span></li>`).join("")}</ul></div>`).join("")}</div>`;
  }

  diagram();
  $("presets").innerHTML = PRESETS.map((p, i) => `<button data-i="${i}">${esc(D.companies[p.company].name)}<br><span class="small">${esc(D.segments[D.companies[p.company].segment].name)}</span></button>`).join("");
  document.querySelectorAll(".presets button").forEach((b) => b.addEventListener("click", () => renderAsk(+b.dataset.i)));
  renderAsk(0);
  renderLibrary();
  renderProviders();
  renderMethod();
})();
