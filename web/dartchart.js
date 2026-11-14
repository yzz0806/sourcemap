/* Samsung Electronics marketing org chart drawn from DART alone (2025 annual report, as of 2025-12-31).
   Structure comes from each executive's responsibility (담당업무): division → unit → sub-center → people.
   Heads are titles ending in 장; members are 담당임원. window.renderDartChart(el, samsung_answer). */
(function () {
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const COLW = 268, GAP = 30, IND = 34, SUBW = COLW - IND, STUB = 24, TRUNK = 16;
  const RANK = { 사장: "President", 부사장: "EVP", 상무: "VP" };
  const ORDER = { 사장: 0, 부사장: 1, 상무: 2 };
  const UNIT_EN = [
    [/^글로벌마케팅실/, "Global Marketing Office", "DX"],
    [/^Mobile eXperience 전략마케팅실/, "MX Strategic Marketing Office", "DX"],
    [/^Mobile eXperience 모바일마케팅센터/, "MX Mobile Marketing Center", "DX"],
    [/^영상디스플레이 전략마케팅팀/, "Visual Display Strategic Marketing Team", "DX"],
    [/^생활가전 전략마케팅팀/, "Digital Appliances Strategic Marketing Team", "DX"],
    [/^네트워크 전략마케팅팀/, "Networks Strategic Marketing Team", "DX"],
    [/^의료기기 전략마케팅팀/, "Medical Devices Strategic Marketing Team", "DX"],
    [/^한국총괄 마케팅팀/, "Korea Region Marketing Team", "DX"],
    [/^메모리 전략마케팅실/, "Memory Strategic Marketing Office", "DS"],
    [/^Foundry 전략마케팅실/, "Foundry Strategic Marketing Office", "DS"],
  ];
  const SUB_EN = { "글로벌브랜드센터": "Global Brand Center", "D2C센터": "D2C Center", "CX센터": "CX Center", "Big Data센터": "Big Data Center" };
  const DIV = { DX: ["Device eXperience (DX)", "디바이스경험(DX)부문"], DS: ["Device Solutions (DS)", "디바이스솔루션(DS)부문"] };

  const initials = (en) => (en || "?").replace(/\*/g, "").split(/[\s-]+/).filter(Boolean).map((w) => w[0].toUpperCase()).join("").slice(0, 3);

  /* people → {DX:[unit…], DS:[unit…]}, unit = {ko, en, head, members, subs:[{ko,en,head,members}]} */
  function structure(a) {
    const units = {};
    a.units.forEach((u) => u.people.forEach((p) => {
      const m = UNIT_EN.find(([re]) => re.test(p.role));
      const key = m ? m[1] : u.unit;
      const unitKo = m ? p.role.match(m[0])[0] : u.unit;
      const unit = units[key] || (units[key] = { ko: unitKo, en: key, div: m ? m[2] : "DX", head: [], members: [], subs: {} });
      const rest = p.role.slice(unitKo.length).trim();               // "", "장", "D2C센터장", "D2C센터 담당임원", "담당임원"
      const sm = rest.match(/^(.+?센터)(장| 담당임원)?$/);
      if (sm && SUB_EN[sm[1]] !== undefined) {
        const s = unit.subs[sm[1]] || (unit.subs[sm[1]] = { ko: sm[1], en: SUB_EN[sm[1]], head: [], members: [] });
        (sm[2] === "장" ? s.head : s.members).push(p);
      } else if (rest === "장" || (rest === "" && /장$/.test(p.role))) unit.head.push(p);
      else unit.members.push(p);
    }));
    const byRank = (x, y) => (ORDER[x.rank] ?? 9) - (ORDER[y.rank] ?? 9) || (x.en || "").localeCompare(y.en || "");
    const out = { DX: [], DS: [] };
    Object.values(units).forEach((u) => {
      u.members.sort(byRank);
      u.subs = Object.values(u.subs).map((s) => (s.members.sort(byRank), s));
      u.size = u.head.length + u.members.length + u.subs.reduce((n, s) => n + s.head.length + s.members.length, 0);
      out[u.div].push(u);
    });
    out.DX.sort((x, y) => y.size - x.size);
    out.DS.sort((x, y) => y.size - x.size);
    return out;
  }

  function person(p, big) {
    const roman = p.en_from && p.en_from.startsWith("romanized");
    return `<div class="dc-p ${big ? "big" : ""}"><div class="av confirmed" aria-hidden="true">${esc(initials(p.en))}</div><div>
      <div class="oc-name">${esc(p.en || p.name)}${roman ? '<span class="dc-star" title="romanized">*</span>' : ""}</div>
      <div class="oc-pko" lang="ko">${esc(p.name)} · ${esc(p.rank)} <span class="dc-rank">${esc(RANK[p.rank] || "")}</span></div>
      ${big ? `<div class="oc-role" lang="ko">${esc(p.role)}</div>` : ""}
      ${p.linkedin ? `<a class="oc-li" href="${esc(p.linkedin)}" target="_blank" rel="noopener" title="Found by search; not verified">LinkedIn ↗</a>` : ""}</div></div>`;
  }
  function card(cls, title, ko, count, heads, members) {
    return `<div class="dc-title">${title}</div><div class="oc-ko" lang="ko">${esc(ko)}${count ? ` · <span class="mono" style="font-size:10px">${count} execs</span>` : ""}</div>
      ${heads.length ? `<div class="dc-head-label mono">Head</div>${heads.map((p) => person(p, true)).join("")}` : ""}
      ${members.length ? `<div class="dc-head-label mono">${heads.length ? "Executives" : "Executives (no head listed)"}</div>${members.map((p) => person(p, false)).join("")}` : ""}`;
  }

  function render(el, a) {
    const S = structure(a), total = a.units.reduce((n, u) => n + u.people.length, 0);
    el.innerHTML = `<div class="oc-legend"><span class="lg"><span class="pill confirmed">✓ DART</span> every person is from the official filing, as of 2025-12-31</span>
      <span class="lg"><span class="mk-sq"></span>unit head (title ends in 장)</span><span class="lg"><b>Name*</b> romanized; no source spelled it</span>
      <span class="lg"><span class="oc-li">LinkedIn ↗</span> found by search, exact-name rule, not verified</span></div>
      <div class="oc-scroll"><div class="oc dc" role="tree" aria-label="Samsung Electronics marketing org chart from DART"></div></div>`;
    const box = el.querySelector(".oc");
    const W = Math.max(el.clientWidth || 1200, 1100);
    const perRow = Math.max(1, Math.floor((W - IND + GAP) / (COLW + GAP)));
    box.style.width = IND + perRow * (COLW + GAP) - GAP + "px";
    const L = [];
    const line = (x, y, w, h, label) => L.push([x, y, w, h, label]);
    function add(cls, x, w, html) {
      const d = document.createElement("div");
      d.className = "oc-card " + cls;
      d.setAttribute("role", "treeitem");
      Object.assign(d.style, { left: x + "px", top: "0px", width: w + "px" });
      d.innerHTML = html;
      box.appendChild(d);
      return d;
    }
    const place = (d, y) => { d.style.top = y + "px"; return y + d.offsetHeight; };

    // root
    const root = add("root dc-root", 0, 420, `<span class="pill confirmed">✓ DART · ${esc(a.rcept_no)}</span><div class="dc-title">Samsung Electronics — marketing</div>
      <div class="oc-ko" lang="ko">삼성전자 · 마케팅 담당 임원</div><div class="oc-role">${total} executives in ${a.units.length} units · 2025 annual report, as of 2025-12-31</div>`);
    let y = place(root, 0) + 22;
    const rootBottom = y - 22;
    line(TRUNK, rootBottom, 2, 22, "");

    ["DX", "DS"].forEach((dv) => {
      const units = S[dv];
      if (!units.length) return;
      const n = units.reduce((k, u) => k + u.size, 0);
      const dcard = add("dc-div", IND, 420, `<div class="dc-title">${esc(DIV[dv][0])}</div><div class="oc-ko" lang="ko">${esc(DIV[dv][1])} · ${n} marketing execs</div>`);
      line(TRUNK, y - 22, 2, 22 + 22, "");
      line(TRUNK, y + 22, IND - TRUNK, 2, `Samsung Electronics to ${DIV[dv][0]}`);
      const divBottom = place(dcard, y);
      const divTrunk = IND + TRUNK;
      let rowY = divBottom + 28, last = divBottom;
      for (let i = 0; i < units.length; i += perRow) {
        const row = units.slice(i, i + perRow), busY = rowY - 14;
        const centers = row.map((_, j) => IND + j * (COLW + GAP) + COLW / 2);
        line(divTrunk, last, 2, busY - last + 2, "");
        line(divTrunk, busY, centers[centers.length - 1] - divTrunk + 2, 2, "");
        let rowBottom = rowY;
        row.forEach((u, j) => {
          const x = IND + j * (COLW + GAP);
          line(centers[j], busY, 2, rowY - busY, `${DIV[dv][0]} to ${u.en}`);
          const uc = add("confirmed dc-unit", x, COLW, card("", `<span class="mk-sq"></span>${esc(u.en)}`, u.ko, u.size, u.head, u.subs.length ? [] : u.members));
          const ub = place(uc, rowY);
          let cy = ub + 16, lastStub = null;
          const spine = x + IND / 2;
          const kids = [...u.subs.map((s) => ({ s })), ...(u.subs.length && u.members.length ? [{ office: true }] : [])];
          kids.forEach((k) => {
            const html = k.office
              ? card("", "Office executives", u.ko + " 담당임원", 0, [], u.members)
              : card("", `<span class="mk-sq"></span>${esc(k.s.en)}`, k.s.ko, k.s.head.length + k.s.members.length, k.s.head, k.s.members);
            const sc = add("confirmed dc-sub", x + IND, SUBW, html);
            const sb = place(sc, cy);
            lastStub = cy + STUB;
            line(spine, lastStub, x + IND - spine, 2, `${u.en} to ${k.office ? "office executives" : k.s.en}`);
            cy = sb + 14;
          });
          if (lastStub !== null) line(spine, ub, 2, lastStub - ub + 2, "");
          rowBottom = Math.max(rowBottom, cy);
        });
        last = busY;
        rowY = rowBottom + 40;
      }
      y = rowY;
    });
    // the root trunk runs down the left edge to the last division
    const lastDivTop = [...box.querySelectorAll(".dc-div")].pop();
    if (lastDivTop) line(TRUNK, rootBottom, 2, parseFloat(lastDivTop.style.top) + 22 - rootBottom + 2, "");
    L.forEach(([x, yy, w, h, label]) => {
      if (h <= 0 && w <= 0) return;
      const d = document.createElement("div");
      d.className = "oc-line";
      Object.assign(d.style, { left: x + "px", top: yy + "px", width: Math.max(w, 2) + "px", height: Math.max(h, 2) + "px" });
      if (label) d.setAttribute("aria-label", label); else d.setAttribute("aria-hidden", "true");
      box.insertBefore(d, box.firstChild);
    });
    box.style.height = y + "px";
  }

  window.renderDartChart = render;
})();
