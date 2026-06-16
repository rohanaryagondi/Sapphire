/* ============ Sapphire Console — the orchestrator, live ============ */
(() => {
  const OD = window.SAPPHIRE_ORCH;
  if (!OD) return;
  const $ = (s, r = document) => r.querySelector(s);
  const el = (t, c, h) => { const e = document.createElement(t); if (c) e.className = c; if (h != null) e.innerHTML = h; return e; };
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  const STANCE = { champion: "boost", conditional: "gold", skeptic: "gate", veto: "gap" };
  const LENS = { scientific: "signal", commercial: "gold", investability: "boost", regulatory: "gate" };

  let active = 0, running = false;
  const tabsWrap = $("#orchTabs"), flow = $("#orchFlow"), qline = $("#orchQuery"), runBtn = $("#orchRun");

  // tabs
  OD.scenarios.forEach((s, i) => {
    const t = el("button", "orch-tab" + (i === 0 ? " on" : ""), s.title);
    t.onclick = () => { if (running) return; active = i; tabsWrap.querySelectorAll(".orch-tab").forEach(x => x.classList.remove("on")); t.classList.add("on"); reset(); };
    tabsWrap.append(t);
  });

  function stageShell(id, label, sub) {
    return `<div class="ostage" data-st="${id}">
      <div class="ostage-rail"><span class="ostage-dot"></span><span class="ostage-label">${label}</span><span class="ostage-sub">${sub}</span></div>
      <div class="ostage-body" id="ob-${id}"></div></div>`;
  }
  function reset() {
    const s = OD.scenarios[active];
    qline.innerHTML = `<span class="oq-mark">QUERY</span> ${s.query}`;
    flow.innerHTML =
      stageShell("discover", "DISCOVER", "EMET + internal moat") +
      stageShell("validate", "VALIDATE", "Q-Models") +
      stageShell("consult", "CONSULT", "persona panel") +
      stageShell("synth", "SYNTHESIZE", "router");
  }

  const dots = n => `<span class="conv" title="conviction ${n}/5">` + "●".repeat(n) + "○".repeat(5 - n) + "</span>";

  function personaCard(p) {
    const card = el("div", "pcard", `
      <div class="pcard-top">
        <span class="badge lens-${LENS[p.lens] || 'muted'}">${p.lens}</span>
        <span class="badge st-${STANCE[p.stance]}">${p.stance}</span>
      </div>
      <div class="pcard-name">${p.persona}</div>
      <div class="pcard-role">${p.role}</div>
      <div class="pcard-head">“${p.headline}”</div>
      ${dots(p.conviction)}
      <div class="pcard-more">
        <div class="pm-row"><span class="pm-k">why</span> ${p.rationale}</div>
        <div class="pm-row"><span class="pm-k risk">top risk</span> ${p.top_risk}</div>
        <div class="pm-row"><span class="pm-k ask">the ask</span> ${p.ask}</div>
      </div>`);
    card.querySelector(".pcard-head").onclick = () => card.classList.toggle("open");
    card.onclick = e => { if (!e.target.closest(".pcard-more")) card.classList.toggle("open"); };
    return card;
  }

  async function lite(id) { const s = flow.querySelector(`[data-st=${id}]`); s.classList.add("lit"); await sleep(140); }

  async function run() {
    if (running) return; running = true; runBtn.disabled = true;
    reset();
    const s = OD.scenarios[active];
    await sleep(200);

    // DISCOVER
    await lite("discover");
    $("#ob-discover").innerHTML =
      `<p class="ob-line">${s.discover.summary}</p>
       <div class="ob-result"><b>&rarr;</b> ${s.discover.result}</div>
       <div class="ob-src">source: ${s.discover.source}</div>`;
    await sleep(900);

    // VALIDATE
    await lite("validate");
    const runsHtml = s.validate.runs.map(r => `<div class="qrow"><span class="qmodel">${r.model}</span><span class="qout">${r.out}</span></div>`).join("");
    $("#ob-validate").innerHTML = runsHtml + `<div class="ob-result"><b>&rarr;</b> ${s.validate.result}</div><div class="ob-src">source: ${s.validate.source}</div>`;
    await sleep(1000);

    // CONSULT
    await lite("consult");
    const body = $("#ob-consult");
    body.innerHTML = `<div class="ob-convening">Convening panel: ${s.panel.map(p => p.lens).join(" · ")} …</div><div class="pgrid"></div>`;
    const grid = body.querySelector(".pgrid");
    await sleep(500);
    body.querySelector(".ob-convening").innerHTML = `Panel convened — ${s.panel.length} viewpoints, grounded in the evidence above:`;
    for (const p of s.panel) { const c = personaCard(p); c.style.opacity = 0; grid.append(c); await sleep(60); requestAnimationFrame(() => { c.style.transition = "opacity .4s, transform .4s"; c.style.opacity = 1; c.style.transform = "none"; }); await sleep(360); }
    body.insertAdjacentHTML("beforeend",
      `<div class="convergent"><span class="cg-tag">CONVERGENT GATE</span> ${s.synthesize.convergent_gate}</div>
       <div class="dissent"><span class="cg-tag dim">DISSENT</span> ${s.synthesize.dissent}</div>`);
    await sleep(700);

    // SYNTHESIZE
    await lite("synth");
    $("#ob-synth").innerHTML =
      `<div class="syn-rec">${s.synthesize.recommendation}</div>
       <div class="syn-grid">
         <div class="syn-cell"><span class="syn-k">consensus</span>${s.synthesize.consensus}</div>
         <div class="syn-cell"><span class="syn-k">confidence</span>${s.synthesize.confidence}</div>
         <div class="syn-cell exp"><span class="syn-k">proposed experiment</span>${s.synthesize.proposed_experiment}</div>
       </div>`;
    await sleep(200);
    runBtn.disabled = false; running = false;
  }

  runBtn.onclick = run;
  reset();
  // auto-run once on scroll-in
  new IntersectionObserver((es, o) => es.forEach(e => { if (e.isIntersecting) { run(); o.disconnect(); } }), { threshold: .25 }).observe($("#console"));
})();
