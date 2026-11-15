/* Leadership-change signals UI (US mega-cap only). Renders D.signals (pipeline/sig_measure.py):
   the source map for this data type, the dashboard card, and the answer for one company.
   window.SignalsUI = { card(t, D), typePage(D), answer(D, slug), rankedSources(D) }. */
(function () {
  const INK = "#14141a", GREY = "#6e6e78", LINE = "#e6e6ea", BLUE = "#1f4fd8";
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const pct = (x) => (x == null ? "–" : Math.round(x * 100) + "%");
  const usd = (x) => (!x ? "$0" : "$" + (x < 0.01 ? x.toFixed(4) : x.toFixed(2)));
  const TELEM = '<span class="telem">TELEM</span>';
  const CO0 = { nvidia: "Nvidia", apple: "Apple", microsoft: "Microsoft" };
  let CO = CO0;  // replaced by D.signals.companies when present (v2: 10 companies)
  const CHANGE = { appointed: "Appointed", departed: "Departed", role_change: "Role change" };

  function hbar(frac, best, iv, w = 150) {
    const X = (v) => 1 + (w - 2) * Math.max(0, Math.min(1, v));
    let s = `<svg width="${w}" height="14" aria-hidden="true"><rect x="1" y="2" width="${w - 2}" height="10" fill="#f1f2f5"/>`;
    if (frac > 0) s += `<rect x="1" y="2" width="${Math.max(2, X(frac) - 1)}" height="10" fill="${best ? BLUE : INK}"/>`;
    if (iv) s += `<path d="M${X(iv[0])} 0v14M${X(iv[0])} 7H${X(iv[1])}M${X(iv[1])} 0v14" stroke="${GREY}" fill="none"/>`;
    return s + "</svg>";
  }
  /* freshness strip: each correct report as a dot on a −14…+90 day axis around the filing (day 0) */
  function strip(values, best, w = 170) {
    const lo = -14, hi = 90, X = (v) => 4 + (w - 8) * (Math.max(lo, Math.min(hi, v)) - lo) / (hi - lo);
    let s = `<svg width="${w}" height="18" aria-hidden="true"><line x1="4" y1="9" x2="${w - 4}" y2="9" stroke="${LINE}"/>`;
    s += `<line x1="${X(0)}" y1="2" x2="${X(0)}" y2="16" stroke="${GREY}"/>`;
    values.forEach((v) => (s += `<circle cx="${X(v)}" cy="9" r="3" fill="${best ? BLUE : INK}" fill-opacity=".7"/>`));
    return s + "</svg>";
  }
  const val = (t, best) => `<span class="bv${best ? " best" : ""}">${t}</span>`;
  const fresh = (d) => (d == null ? "–" : d === 0 ? "same day" : d < 0 ? `${-d} d before` : `${d} d after`);

  function rankedSources(D) {
    const order = { measured: 0, not_enough_data: 1, unmeasured: 2 };
    if (D.signals.companies) CO = Object.fromEntries(Object.entries(D.signals.companies).map(([k, v]) => [k, v.name]));
    const share = (s) => s.coverage.found / (s.coverage.total || D.signals.total_ref_events || 1);
    return [...D.signals.sources].filter((s) => s.pages > 0 || s.coverage.total)
      .sort((a, b) => share(b) - share(a) || order[a.accuracy.state] - order[b.accuracy.state] || (b.accuracy.mean || 0) - (a.accuracy.mean || 0));
  }

  function table(D, rows) {
    const S = D.signals, live = rows.filter((s) => s.pages > 0);
    const best = (f, asc) => live.filter((s) => f(s) != null).sort((a, b) => (asc ? f(a) - f(b) : f(b) - f(a)))[0];
    const bCov = best((s) => (s.coverage.found ? s.coverage.found / (s.coverage.total || S.total_ref_events) : null));
    const bAcc = best((s) => (s.accuracy.state === "measured" ? s.accuracy.mean : null));
    const bFresh = best((s) => (s.freshness.n ? s.freshness.median_days : null), true);
    const bCost = best((s) => (s.coverage.found ? s.usd / s.coverage.found : null), true);
    const maxUsd = Math.max(...live.map((s) => s.usd), 0.001);
    const rowHtml = (s) => {
      const a = s.accuracy, f = s.freshness;
      const acc = a.state === "unmeasured" ? '<span class="muted">nothing checkable</span>'
        : `${hbar(a.mean ?? (a.interval[0] + a.interval[1]) / 2, s === bAcc, a.interval)}${val(a.state === "measured" ? pct(a.mean) : "not enough data", s === bAcc)}<div class="small">${a.n} report${a.n === 1 ? "" : "s"} checked${a.n_wrong ? `, ${a.n_wrong} wrong` : ""} · ${pct(a.unverifiable_share)} not in any 8-K</div>`;
      const fr = f.n ? `${strip(f.values, s === bFresh)}${val(fresh(f.median_days), s === bFresh)}<div class="small">median of ${f.n} report${f.n > 1 ? "s" : ""}${f.median_bound_width != null ? ` · archive snapshots: precise to ±${Math.round(f.median_bound_width)} d` : ""}</div>` : '<span class="muted">no dated match</span>';
      const status = s.pages ? `${s.pages} page${s.pages > 1 ? "s" : ""} read${s.blocked ? ` · ${s.blocked} blocked` : ""}` : `blocked (${s.blocked})`;
      const tags = [s === bCov && "most coverage", s === bAcc && "most accurate", s === bFresh && "fastest", s === bCost && "cheapest per change"].filter(Boolean).join(" · ");
      return `<tr><td><b>${esc(s.source)}</b><br><span class="small">${s.kind ? esc(s.kind) + " · " : ""}tier ${s.tier} · ${esc(status)}</span></td>
        <td>${hbar(s.coverage.found / (s.coverage.total || S.total_ref_events), s === bCov)}${val(`${s.coverage.found} of ${s.coverage.total || S.total_ref_events}`, s === bCov)}${s.not_tracked ? `<div class="small">${s.not_tracked} changes not tracked by this kind of source</div>` : ""}</td>
        <td>${acc}</td><td>${fr}</td><td>${hbar(s.usd / maxUsd, s === bCost)}${val(usd(s.usd), s === bCost)}${s.coverage.found ? `<div class="small">${usd(s.usd / s.coverage.found)} per change found</div>` : ""}</td>
        <td class="small"><b class="blue">${tags}</b></td></tr>`;
    };
    const shown = rows.filter((s) => s.coverage.found > 0 || D.signals.version === 2), rest = rows.filter((s) => !(s.coverage.found > 0 || D.signals.version === 2));
    const body = shown.map(rowHtml).join("") + (rest.length ? `<tr><td colspan="6"><details><summary class="mono">Show ${rest.length} more sources that matched no filed change</summary>
      <table class="btable">${rest.map(rowHtml).join("")}</table></details></td></tr>` : "");
    return `<div class="bhow small"><span><b>Coverage</b> — share of the filed changes the source reflected (out of those its kind of page could show).</span>
      <span><b>Accuracy</b> — share of its reports that match a filing (contradictions are wrong; changes no 8-K covers are unverifiable). Bracket = 90% range.</span>
      <span><b>Freshness</b> — days between the 8-K filing (the line) and the source's publication; each dot is one report. <b>Cost</b> — search share + reading. <b class="blue">Blue</b> = best.</span></div>
      <div class="scroll"><table class="btable"><tr><th>Source</th><th>Coverage</th><th>Accuracy</th><th>Freshness</th><th>Cost</th><th>Best at</th></tr>
      <tr class="refrow"><td><b>SEC 8-K, Item 5.02</b><br><span class="small">the reference · tier 1</span></td><td>${hbar(1, false)}${val(`${S.total_ref_events} of ${S.total_ref_events}`, false)}</td>
        <td>${val("official", false)}<div class="small">filed within 4 business days of the change</div></td><td>${val("day 0", false)}<div class="small">the filing date</div></td><td>${val("$0", false)}<div class="small">free (EDGAR)</div></td><td></td></tr>
      ${body}</table></div>`;
  }

  function timeline(D, slug) {
    const evs = D.signals.timeline.filter((e) => !slug || e.company === slug);
    if (!evs.length) return '<p class="small">No Item 5.02 changes in the window.</p>';
    return `<div class="sig-tl">${evs.map((e) => `<div class="tl-row sig"><span class="d">${esc(e.filing_date)}</span><div>
      <span class="sig-tag sig-${esc(e.change)}">${esc(CHANGE[e.change] || e.change)}</span> <b class="sig-person">${esc(e.person)}</b>${e.role ? ` — ${esc(e.role)}` : ""}${slug ? "" : ` <span class="muted">· ${esc(CO[e.company] || e.company)}</span>`}
      <span class="small"> · ${esc(e.kind || "")} · <a href="${esc(e.url)}" target="_blank" rel="noopener">8-K</a></span>
      <div class="sig-rep">${e.reported_by.length ? e.reported_by.map((r) => `<span class="chip-s"><a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.source)}</a> ${r.days_late == null ? "" : `<span class="mono">${esc(fresh(r.days_late))}</span>`}</span>`).join("") : '<span class="muted small">no source reported it</span>'}</div>
      <div class="quote">“${esc((e.quote || "").slice(0, 220))}”</div></div></div>`).join("")}</div>`;
  }

  const TOP_ROLE = /chief executive|\bceo\b|chair|president|chief financial|\bcfo\b/i;
  function headline(D, slug) {
    const evs = D.signals.timeline.filter((e) => e.company === slug && TOP_ROLE.test(e.role || ""));
    if (!evs.length) return "";
    const latest = evs.map((e) => e.filing_date).sort().pop();
    const top = evs.filter((e) => e.filing_date === latest).sort((a, b) => (a.change === "departed" ? -1 : 0) - (b.change === "departed" ? -1 : 0));
    const first = (e) => { const r = e.reported_by.filter((x) => x.days_late != null).sort((a, b) => a.days_late - b.days_late)[0]; return r ? `${esc(r.source)} reported it ${esc(fresh(r.days_late))}` : "no web source reported it yet"; };
    return `<div class="sig-head"><p class="label">THE BIG CHANGE · 8-K FILED ${esc(latest)}</p>
      <div class="sig-cards">${top.map((e) => `<article class="sig-card sig-${esc(e.change)}">
        <span class="sig-tag sig-${esc(e.change)} big">${esc(CHANGE[e.change] || e.change)}</span>
        <h3>${esc(e.person)}</h3><p class="sig-role">${esc(e.role || "")}</p>
        <p class="quote">“${esc((e.quote || "").slice(0, 260))}”</p>
        <p class="small">${first(e)} · <a href="${esc(e.url)}" target="_blank" rel="noopener">read the 8-K</a></p></article>`).join("")}</div></div>`;
  }

  function kpis(D, slug) {
    const S = D.signals, evs = S.timeline.filter((e) => !slug || e.company === slug);
    const reported = evs.filter((e) => e.reported_by.length).length;
    const lates = evs.flatMap((e) => e.reported_by.map((r) => r.days_late)).filter((d) => d != null);
    const med = lates.length ? [...lates].sort((a, b) => a - b)[Math.floor(lates.length / 2)] : null;
    return `<div class="kpis"><div class="kpi"><b>${evs.length}</b><span class="mono">changes filed (8-K 5.02)</span></div>
      <div class="kpi"><b>${reported} of ${evs.length}</b><span class="mono">reported by any web source</span></div>
      <div class="kpi"><b>${esc(fresh(med))}</b><span class="mono">median lag vs the filing</span></div>
      <div class="kpi"><b>${usd(S.spent_usd)}</b><span class="mono">search + reading ${TELEM}</span></div></div>`;
  }

  window.SignalsUI = {
    rankedSources,
    card(t, D) {
      const top = rankedSources(D)[0];
      return `<div class="type"><span class="status">measured · ${esc(t.scope || "")}</span><h3><a href="#/type/${t.slug}" style="color:inherit">${esc(t.name)}</a></h3>
        <p class="small">${esc(t.what)} Checked against SEC 8-K Item 5.02 filings.</p>
        <div class="seglist"><a class="segrow" href="#/type/${t.slug}"><span><b>US mega-cap</b><br><span class="small">vs SEC 8-K Item 5.02 · ${Object.keys(D.signals.companies || CO0).length} companies · ${D.signals.total_ref_events} changes</span></span>
          <span class="small" style="text-align:right">most coverage: <b>${esc(top ? top.source : "–")}</b><br>${top ? `${top.coverage.found} of ${D.signals.total_ref_events}` : ""}</span></a>
          <div class="segrow muted"><span>Korean and European large-cap</span><span class="small">not measured yet</span></div></div></div>`;
    },
    typePage(D) {
      const S = D.signals;
      return `<h2>Leadership-change signals — the source map</h2>
        <p class="note">Which sources report executive appointments and departures correctly, completely and quickly — measured for <b>US mega-cap</b>
        (${esc(Object.values(CO).join(", "))}) against every SEC 8-K Item 5.02 filed ${esc(S.window ? S.window.join(" → ") : "")}. Korean and European large-cap are not measured yet.</p>
        ${kpis(D)}${table(D, rankedSources(D))}
        <h3>Every filed change, and who reported it</h3><p class="small">Newest first. Chips show each source that reported the change and how many days after the filing.</p>${timeline(D)}`;
    },
    answer(D, slug) {
      return `<section><p class="label">THE ANSWER</p><h2>Leadership changes at ${esc(CO[slug] || slug)}</h2>
        <p class="small">From SEC 8-K Item 5.02 filings, ${esc(D.signals.window ? D.signals.window.join(" → ") : "")}.</p>${headline(D, slug)}${kpis(D, slug)}
        <h3>Every filed change</h3>${timeline(D, slug)}</section>
        <section><p class="label">THE BENCHMARK · US MEGA-CAP</p><h2>Which source to use — coverage, accuracy, freshness, cost</h2>${table(D, rankedSources(D))}</section>`;
    },
  };
})();
