/* Org-chart graph for one company (spec: root card → bus → 5 columns; children stacked on a left spine;
   grandchild on a sub-spine). Three-state status encoded redundantly: outline style + fill + pill + avatar.
   Absolute positioning in one relative container; card heights are measured, then lines are drawn.
   window.renderOrgChart(el, data) where data = {tree, timeline, gaps, dart_date, provenance}. */
(function () {
  const COLW = 272, GAP = 48, CHILDW = 236, CHILD_IND = 36, GCW = 204, GC_IND = 32, ROOTW = 340, STUB_Y = 26;
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const PILL = { confirmed: "✓ Confirmed", vacant: "✓ Confirmed", snippet: "◐ Snippet only", unknown: "? Unknown" };

  function cardHtml(n, dartDate) {
    const st = n.root ? "confirmed" : n.status;
    const cls = n.container ? "" : st === "vacant" ? "confirmed" : st || "";
    const pill = n.container || !st ? "" : `<span class="pill ${st === "vacant" ? "confirmed" : st}">${PILL[st]}</span><br>`;
    const title = `<div class="oc-title ${n.struck ? "struck" : ""}">${n.mk ? '<span class="mk-sq" aria-label="Marketing unit"></span>' : ""}${esc(n.unit)}</div>
      ${n.ko ? `<div class="oc-ko" lang="ko">${esc(n.ko)}</div>` : ""}`;
    let person = "";
    if (n.person) {
      const p = n.person, avc = st === "snippet" ? "snippet" : "confirmed";
      person = `<div class="oc-person"><div class="av ${avc}" aria-hidden="true">${esc(p.init)}</div><div>
        <div class="oc-name ${st === "snippet" ? "snippet" : ""}">${esc(p.en)}</div>
        ${p.ko ? `<div class="oc-pko" lang="ko">${esc(p.ko)}</div>` : ""}
        <div class="oc-role">${esc(p.role)}</div>
        ${p.linkedin ? `<a class="oc-li" href="${esc(p.linkedin)}" target="_blank" rel="noopener" title="Found by search; not verified">LinkedIn ↗ candidate</a>` : ""}</div></div>`;
    } else if (st === "unknown") {
      person = `<div class="oc-person"><div class="av unknown" aria-hidden="true">?</div><div><div class="oc-role">Head not found</div></div></div>`;
    } else if (st === "vacant") {
      person = `<div class="oc-person"><div class="av vacant" aria-hidden="true">—</div><div><div class="oc-name">Vacant</div><div class="oc-role">${esc((n.vacant_text || "").replace(/^Vacant:\s*/, ""))}</div></div></div>`;
    }
    const note = n.note ? `<div class="oc-note">${esc(n.note)}</div>` : "";
    const dart = [];
    if (n.person && n.person.dart && n.person.dart.length) dart.push(`${esc(n.person.ko)}: ${n.person.dart.map(esc).join("; ")}`);
    if (n.dart_head && n.dart_head.length && !(n.person && n.dart_head.some((h) => h.startsWith(n.person.ko + " ")))) dart.push(`Unit head: ${n.dart_head.map(esc).join("; ")}`);
    const dartHtml = dart.length ? `<div class="oc-dart"><b>DART ${esc(dartDate)}</b> · <span lang="ko">${dart.join("<br>")}</span></div>` : "";
    return { cls: `oc-card ${cls} ${n.root ? "root" : ""}`, html: pill + title + person + note + dartHtml };
  }

  function render(el, data) {
    const T = data.tree, cols = T.children || [];
    const W = cols.length * COLW + (cols.length - 1) * GAP;
    el.innerHTML = `<div class="oc-legend" role="list">
        <span class="lg" role="listitem"><span class="pill confirmed">✓ Confirmed</span> name read on the source page</span>
        <span class="lg" role="listitem"><span class="pill snippet">◐ Snippet only</span> seen only in a search snippet</span>
        <span class="lg" role="listitem"><span class="pill unknown">? Unknown</span> unit exists, head not found</span>
        <span class="lg" role="listitem"><span class="mk-sq"></span>Marketing unit</span>
        <span class="lg" role="listitem"><span class="oc-title struck" style="font-weight:400">Struck title</span> downsized or vacant</span>
        <span class="lg" role="listitem"><b class="mono" style="font-size:10px">DART ${esc(data.dart_date)}</b> official filing, for comparison</span>
      </div>
      <div class="oc-scroll"><div class="oc" style="width:${W}px" role="tree" aria-label="Samsung Electronics DX marketing org chart"></div></div>`;
    const box = el.querySelector(".oc");
    const lines = [];
    function card(n, x, w) {
      const c = cardHtml(n, data.dart_date), d = document.createElement("div");
      d.className = c.cls;
      d.setAttribute("role", "treeitem");
      d.style.left = x + "px";
      d.style.top = "0px";
      d.style.width = w + "px";
      d.innerHTML = c.html;
      box.appendChild(d);
      return d;
    }
    function line(x, y, w, h, label) {
      lines.push([x, y, w, h, label]);
    }
    const place = (d, y) => { d.style.top = y + "px"; return y + d.offsetHeight; };

    // root and bus
    const rootX = (W - ROOTW) / 2, root = card(T, rootX, ROOTW);
    const rootBottom = place(root, 0), busY = rootBottom + 28, colY = busY + 28;
    line(W / 2 - 1, rootBottom, 2, busY - rootBottom + 1, "");
    const centers = cols.map((_, i) => i * (COLW + GAP) + COLW / 2);
    line(centers[0], busY, centers[centers.length - 1] - centers[0] + 2, 2, "");
    let maxBottom = 0;
    cols.forEach((col, i) => {
      const x = i * (COLW + GAP);
      line(centers[i], busY, 2, colY - busY, `From ${T.unit} to ${col.unit}`);
      const head = card(col, x, COLW);
      const headBottom = place(head, colY);
      let y = headBottom + 20, lastStub = null;
      const spineX = x + CHILD_IND / 2;
      (col.children || []).forEach((ch) => {
        const cx = x + CHILD_IND, cd = card(ch, cx, CHILDW);
        const bottom = place(cd, y);
        lastStub = y + STUB_Y;
        line(spineX, lastStub, cx - spineX, 2, `From ${col.unit} to ${ch.unit}`);
        y = bottom + 16;
        (ch.children || []).forEach((gc) => {
          const gx = cx + GC_IND, gd = card(gc, gx, GCW), gb = place(gd, y), sub = cx + GC_IND / 2;
          line(sub, bottom, 2, y + STUB_Y - bottom + 2, "");
          line(sub, y + STUB_Y, gx - sub, 2, `From ${ch.unit} to ${gc.unit}`);
          y = gb + 16;
        });
      });
      if (lastStub !== null) line(spineX, headBottom, 2, lastStub - headBottom + 2, "");
      maxBottom = Math.max(maxBottom, y);
    });
    lines.forEach(([x, y, w, h, label]) => {
      const l = document.createElement("div");
      l.className = "oc-line";
      Object.assign(l.style, { left: x + "px", top: y + "px", width: w + "px", height: h + "px" });
      if (label) l.setAttribute("aria-label", label); else l.setAttribute("aria-hidden", "true");
      box.insertBefore(l, box.firstChild);
    });
    box.style.height = maxBottom + 8 + "px";
    const sc = el.querySelector(".oc-scroll");
    if (sc.scrollWidth > sc.clientWidth + 4) sc.insertAdjacentHTML("beforebegin", '<p class="oc-hint">Scroll sideways to see all five units →</p>');

    el.insertAdjacentHTML("beforeend", `<div class="oc-panels">
      <section class="oc-panel"><p class="label">Timeline</p><h3>Who led global marketing</h3>
        ${data.timeline.map(([d, t]) => `<div class="tl-row"><span class="d">${esc(d)}</span><span>${esc(t)}</span></div>`).join("")}</section>
      <section class="oc-panel"><p class="label">Gaps</p><h3>What we could not confirm</h3>
        <ul>${data.gaps.map((g) => `<li>${esc(g)}</li>`).join("")}</ul></section>
      <section class="oc-panel"><p class="label">Cross-check · DART ${esc(data.dart_date)}</p><h3>What the official filing adds</h3>
        <ul><li>D2C Center head: <b lang="ko">조철호</b> (Cho Cheol-ho), EVP — before the May 2026 change.</li>
        <li>CX Center head: <b lang="ko">이종민</b> (Lee Jong-min), EVP — DART names a CX Center; whether it is today's CX-MDE Center is not confirmed.</li>
        <li>MX Strategic Marketing head: <b lang="ko">조성혁</b> (Seong H. Cho), EVP — the LinkedIn name, not the older blog's.</li>
        <li>Global Brand Center head before May 2026: <b lang="ko">박정미</b> (Park Jeong-mi), EVP.</li>
        <li>Choi Bo-ram is listed under the CX Center, not the Brand Center — consistent with the placement being an assumption.</li>
        <li>Han Eui-taek is listed as DA <i>Strategic Marketing</i> team executive in DART.</li></ul>
        <p class="small">Tree data: ${esc(data.provenance)}. DART notes are dated and do not change the statuses above.</p></section>
    </div>`);
  }

  window.renderOrgChart = render;
})();
