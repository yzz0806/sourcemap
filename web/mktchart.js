/* Marketing org chart below the CMO for US companies (data: D.marketing_depth, scripts/demo_marketing_depth.py).
   Official filings stop at the top officers, so each person carries an evidence level:
     confirmed   — in the SEC filing                       (solid blue card, ✓ CONFIRMED)
     own_page    — named on the company's own website      (white card, blue outline, ✓ OWN SITE)
     third_party — named only by other websites           (pale orange, dashed, ◐ OTHER SITES · n)
   Branches and reporting lines are inferred from titles. window.renderMarketingChart(el, depth). */
(function () {
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const initials = (n) => (n || "?").replace(/\(.*?\)/g, "").split(/[\s-]+/).filter(Boolean).map((w) => w[0].toUpperCase()).join("").slice(0, 3);
  const PILL = { confirmed: ["✓", "Confirmed"], own_page: ["✓", "Own site"], third_party: ["◐", "Other sites"] };

  function card(p, top) {
    const [g, label] = PILL[p.level] || PILL.third_party;
    const srcs = [...new Set((p.sources || []).map((s) => s.source))];
    const n = p.level === "third_party" ? ` · ${srcs.length}` : "";
    const links = (p.sources || []).filter((s, i, a) => a.findIndex((t) => t.source === s.source) === i).slice(0, 4)
      .map((s) => `<a href="${esc(s.url)}" target="_blank" rel="noopener" title="${esc(s.quote)}">${esc(s.source)}</a>`).join(" · ");
    return `<article class="mc-card mc-${p.level}${top ? " mc-top" : ""}">
      <span class="mc-pill"><span aria-hidden="true">${g}</span> ${label}${n}</span>
      <div class="mc-person"><span class="mc-av" aria-hidden="true">${esc(initials(p.name))}</span>
        <div><div class="mc-name">${esc(p.name)}</div><div class="mc-title">${esc(p.title)}</div></div></div>
      ${links ? `<div class="mc-src">${p.level === "confirmed" && !links ? "" : links}</div>` : ""}
    </article>`;
  }

  function column(name, people) {
    return `<li class="mc-col"><div class="mc-branch">${esc(name)}</div>
      <ul class="mc-kids" aria-label="${esc(name)}">${people.map((p) => `<li>${card(p)}</li>`).join("")}</ul></li>`;
  }

  function render(el, d) {
    if (!d) { el.innerHTML = ""; return; }
    const inside = d.people.filter((p) => p.under_cmo === true), outside = d.people.filter((p) => p.under_cmo === false),
      unclear = d.people.filter((p) => p.under_cmo !== true && p.under_cmo !== false);
    const groups = {};
    inside.forEach((p) => (groups[p.branch] = groups[p.branch] || []).push(p));
    const cols = Object.entries(groups).sort((a, b) => Math.min(...a[1].map((p) => p.rank)) - Math.min(...b[1].map((p) => p.rank)) || b[1].length - a[1].length);
    const count = (lv) => d.people.filter((p) => p.level === lv).length + (d.cmo && d.cmo.level === lv ? 1 : 0);
    el.innerHTML = `<div class="mc-legend">
        <span><span class="mc-sw mc-confirmed"></span>Confirmed in the SEC filing · ${count("confirmed")}</span>
        <span><span class="mc-sw mc-own_page"></span>Named on ${esc(d.company)}'s own site · ${count("own_page")}</span>
        <span><span class="mc-sw mc-third_party"></span>Named only by other sites · ${count("third_party")}</span>
        <span class="mc-note">Branches and reporting lines are inferred from titles. Names from other sites can be out of date: a page does not say when it was true.</span></div>
      <div class="mc-scroll"><div class="mc-chart">
        <div class="mc-root">${d.cmo ? card(d.cmo, true) : `<article class="mc-card mc-top mc-none"><div class="mc-name">Marketing lead not identified</div></article>`}</div>
        ${cols.length ? `<ul class="mc-row" aria-label="Reports to ${esc(d.cmo ? d.cmo.name : "marketing")}">${cols.map(([b, ps]) => column(b, ps)).join("")}</ul>` : ""}
      </div></div>
      ${outside.length ? `<div class="mc-outside"><p class="label">MARKETING LEADERS ELSEWHERE IN ${esc(d.company.toUpperCase())}</p>
        <p class="small">Their titles name another division or business, so they likely report outside the CMO's organisation.</p>
        <div class="mc-grid">${outside.map((p) => card(p)).join("")}</div></div>` : ""}
      ${unclear.length ? `<div class="mc-outside"><p class="label">PLACEMENT UNCLEAR</p>
        <p class="small">Marketing titles that don't say which part of ${esc(d.company)} they belong to.</p>
        <div class="mc-grid">${unclear.map((p) => card(p)).join("")}</div></div>` : ""}`;
  }
  window.renderMarketingChart = render;
})();
