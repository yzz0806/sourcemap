/* Leadership-change signals UI (US mega-cap only). Renders D.signals (pipeline/sig_measure.py):
   the source map for this data type, the dashboard card, and the answer for one company.
   window.SignalsUI = { card(t, D), typePage(D), answer(D, slug), rankedSources(D) }. */
(function () {
  const INK = "#14141a", GREY = "#6e6e78", LINE = "#e6e6ea", BLUE = "#1f4fd8";
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const pct = (x) => (x == null ? "–" : Math.round(x * 100) + "%");
  const usd = (x) => (!x ? "$0" : "$" + (x < 0.01 ? x.toFixed(4) : x.toFixed(2)));
  const TELEM = '<span class="telem">TELEM</span>';
  const CO = { nvidia: "Nvidia", apple: "Apple", microsoft: "Microsoft" };
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
    return [...D.signals.sources].filter((s) => s.pages > 0)
      .sort((a, b) => b.coverage.found - a.coverage.found || order[a.accuracy.state] - order[b.accuracy.state] || (b.accuracy.mean || 0) - (a.accuracy.mean || 0));
  }

  function table(D, rows) {
    const S = D.signals, live = rows.filter((s) => s.pages > 0);
    const best = (f, asc) => live.filter((s) => f(s) != null).sort((a, b) => (asc ? f(a) - f(b) : f(b) - f(a)))[0];
    const bCov = best((s) => (s.coverage.found ? s.coverage.found : null));
    const bAcc = best((s) => (s.accuracy.state === "measured" ? s.accuracy.mean : null));
    const bFresh = best((s) => (s.freshness.n ? s.freshness.median_days : null), true);
    const bCost = best((s) => (s.coverage.found ? s.usd / s.coverage.found : null), true);
    const maxUsd = Math.max(...live.map((s) => s.usd), 0.001);
    const rowHtml = (s) => {
      const a = s.accuracy, f = s.freshness;
      const acc = a.state === "unmeasured" ? '<span class="muted">nothing checkable</span>'
        : `${hbar(a.mean ?? (a.interval[0] + a.interval[1]) / 2, s === bAcc, a.interval)}${val(a.state === "measured" ? pct(a.mean) : "not enough data", s === bAcc)}<div class="small">${a.n} report${a.n === 1 ? "" : "s"} checked${a.n_wrong ? `, ${a.n_wrong} wrong` : ""} · ${pct(a.unverifiable_share)} not in any 8-K</div>`;
      const fr = f.n ? `${strip(f.values, s === bFresh)}${val(fresh(f.median_days), s === bFresh)}<div class="small">median of ${f.n} report${f.n > 1 ? "s" : ""}</div>` : '<span class="muted">no dated match</span>';
      const status = s.pages ? `${s.pages} page${s.pages > 1 ? "s" : ""} read${s.blocked ? ` · ${s.blocked} blocked` : ""}` : `blocked (${s.blocked})`;
      const tags = [s === bCov && "most coverage", s === bAcc && "most accurate", s === bFresh && "fastest", s === bCost && "cheapest per change"].filter(Boolean).join(" · ");
      return `<tr><td><b>${esc(s.source)}</b><br><span class="small">tier ${s.tier} · ${esc(status)}</span></td>
        <td>${hbar(s.coverage.found / S.total_ref_events, s === bCov)}${val(`${s.coverage.found} of ${S.total_ref_events}`, s === bCov)}</td>
        <td>${acc}</td><td>${fr}</td><td>${hbar(s.usd / maxUsd, s === bCost)}${val(usd(s.usd), s === bCost)}${s.coverage.found ? `<div class="small">${usd(s.usd / s.coverage.found)} per change found</div>` : ""}</td>
        <td class="small"><b class="blue">${tags}</b></td></tr>`;
    };
    const shown = rows.filter((s) => s.coverage.found > 0), rest = rows.filter((s) => s.coverage.found === 0);
    const body = shown.map(rowHtml).join("") + (rest.length ? `<tr><td colspan="6"><details><summary class="mono">Show ${rest.length} more sources that matched no filed change</summary>
      <table class="btable">${rest.map(rowHtml).join("")}</table></details></td></tr>` : "");
    return `<div class="bhow small"><span><b>Coverage</b> — how many of the ${S.total_ref_events} changes filed in 8-Ks the source reported.</span>
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
      <b>${esc(e.person)}</b> — ${esc(CHANGE[e.change] || e.change)}${e.role ? `, ${esc(e.role)}` : ""}${slug ? "" : ` <span class="muted">· ${esc(CO[e.company] || e.company)}</span>`}
      <span class="small"> · ${esc(e.kind || "")} · <a href="${esc(e.url)}" target="_blank" rel="noopener">8-K</a></span>
      <div class="sig-rep">${e.reported_by.length ? e.reported_by.map((r) => `<span class="chip-s"><a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.source)}</a> ${r.days_late == null ? "" : `<span class="mono">${esc(fresh(r.days_late))}</span>`}</span>`).join("") : '<span class="muted small">no source reported it</span>'}</div>
      <div class="quote">“${esc((e.quote || "").slice(0, 220))}”</div></div></div>`).join("")}</div>`;
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
        <div class="seglist"><a class="segrow" href="#/type/${t.slug}"><span><b>US mega-cap</b><br><span class="small">vs SEC 8-K Item 5.02 · Nvidia, Apple, Microsoft · ${D.signals.total_ref_events} changes</span></span>
          <span class="small" style="text-align:right">most coverage: <b>${esc(top ? top.source : "–")}</b><br>${top ? `${top.coverage.found} of ${D.signals.total_ref_events}` : ""}</span></a>
          <div class="segrow muted"><span>Korean and European large-cap</span><span class="small">not measured yet</span></div></div></div>`;
    },
    typePage(D) {
      const S = D.signals;
      return `<h2>Leadership-change signals — the source map</h2>
        <p class="note">Which sources report executive appointments and departures correctly, completely and quickly — measured for <b>US mega-cap</b>
        (Nvidia, Apple, Microsoft) against every SEC 8-K Item 5.02 filed ${esc(S.window ? S.window.join(" → ") : "")}. Korean and European large-cap are not measured yet.</p>
        ${kpis(D)}${table(D, rankedSources(D))}
        <h3>Every filed change, and who reported it</h3><p class="small">Newest first. Chips show each source that reported the change and how many days after the filing.</p>${timeline(D)}`;
    },
    answer(D, slug) {
      return `<section><p class="label">THE ANSWER</p><h2>Leadership changes at ${esc(CO[slug] || slug)}</h2>
        <p class="small">From SEC 8-K Item 5.02 filings, ${esc(D.signals.window ? D.signals.window.join(" → ") : "")}.</p>${kpis(D, slug)}${timeline(D, slug)}</section>
        <section><p class="label">THE BENCHMARK · US MEGA-CAP</p><h2>Which source to use — coverage, accuracy, freshness, cost</h2>${table(D, rankedSources(D))}</section>`;
    },
  };
})();
