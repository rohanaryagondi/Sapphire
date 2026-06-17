/* ============ Sapphire Console — the orchestrator, live ============
   Front-facing layer for sapphire-orchestrator/orchestrator.py.
   - Shipped scenarios animate instantly from window.SAPPHIRE_ORCH (built by the engine).
   - A novel query routes to the local bridge (serve.py) → Claude on your subscription, when running.
     Otherwise it shows the engagement plan and falls back to the worked scenarios (static hosting).
   A JS mirror of the engine's planner runs the PLAN stage for ANY query, instantly.
*/
(() => {
  const OD = window.SAPPHIRE_ORCH;
  if (!OD) return;
  const $ = (s, r = document) => r.querySelector(s);
  const el = (t, c, h) => { const e = document.createElement(t); if (c) e.className = c; if (h != null) e.innerHTML = h; return e; };
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const esc = s => (s == null ? "" : String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"));

  const STANCE = { champion: "boost", conditional: "gold", skeptic: "gate", veto: "gap" };
  const LENS = { scientific: "signal", commercial: "gold", investability: "boost", regulatory: "gate", adversarial: "gap" };

  /* ---------- hero EP trace (app.js isn't loaded on the Console page) ---------- */
  (function seedTraces() {
    const t1 = $("#epTrace"), t2 = $("#epTrace2"); if (!t1) return;
    const path = (baseline, jitter, spikes) => {
      const W = 1440, step = 12; let d = `M0 ${baseline}`;
      for (let x = step; x <= W; x += step) {
        let y = baseline + Math.sin(x / 40) * 3 + (Math.random() - .5) * jitter;
        if (spikes.some(s => Math.abs(x - s) < 7)) y = baseline - 70 - Math.random() * 20;
        else if (spikes.some(s => x - s >= 7 && x - s < 20)) y = baseline + 26;
        d += ` L${x} ${y.toFixed(1)}`;
      }
      return d;
    };
    t1.setAttribute("d", path(170, 6, [180, 470, 700, 980, 1230]));
    t2.setAttribute("d", path(210, 10, [330, 600, 1100]));
  })();

  /* ---------- bridge health (is the live brain available?) ---------- */
  const BRIDGE = { live: false, model: "" };
  (async function health() {
    const badge = $("#orchStatus");
    try {
      const r = await fetch("/api/health", { cache: "no-store" });
      const h = await r.json();
      BRIDGE.live = !!h.live; BRIDGE.model = h.model || "";
      if (badge) badge.innerHTML = BRIDGE.live
        ? `<span class="st-live"></span> live · Claude (subscription)`
        : `<span class="st-demo"></span> demo · canned scenarios`;
    } catch (e) {
      if (badge) badge.innerHTML = `<span class="st-demo"></span> demo · static`;
    }
  })();

  /* ---------- JS mirror of the engine planner (triage/scope/seat) ---------- */
  const ROUTES = {
    pain: { keys: ["pain", "nav1.8", "nav1_8", "scn10a", "scn11a", "nav1.9", "neuropathic", "analgesic", "nocicept"],
      label: "neuropathic pain (peripheral sensory neuron)", scenario: "nav1_8",
      panel: [["scientific", "Biotech CSO — ion channels (Xenon)"], ["commercial", "Pharma BD — CNS pain (Lundbeck)"], ["investability", "Venture GP — neuro (RA Capital)"], ["regulatory", "Pharma Neuro SVP / ex-FDA (Takeda Neuro)"]] },
    tsc: { keys: ["tsc2", "tsc1", "tuberous", "mtor", "rheb", "depdc5", "epilep", "fcd", "hyperexcitab"],
      label: "tuberous sclerosis / mTORopathy CNS", scenario: "tsc2",
      panel: [["scientific", "Biotech CSO — CNS translational (Denali)"], ["commercial", "Pharma BD — rare disease (BioMarin)"], ["investability", "Venture GP — neuro (Third Rock)"], ["regulatory", "Pharma Neuro SVP / ex-FDA (Takeda Neuro)"]] },
  };
  const DELIV = [[["rank", "prioriti", "triage", "which target"], "a ranked, de-risked target list"],
    [["go/no-go", "advance", "kill", "should we"], "a go / no-go call"],
    [["trial", "phase ", "endpoint", "ind ", "fih"], "a trial-design assessment"],
    [["fund", "license", "deal", "invest", "diligence"], "an investability / BD read"],
    [["franchise", "portfolio", "platform"], "a franchise / portfolio thesis"]];
  const GROUPS = { A: "Target & mechanism", B: "Scientific validation", C: "Safety", D: "Clinical & regulatory", E: "Competitive, IP & commercial", F: "Ecosystem / perception" };

  function planFor(query) {
    const q = (query || "").toLowerCase();
    let dk = null;
    for (const k in ROUTES) if (ROUTES[k].keys.some(w => q.includes(w))) { dk = k; break; }
    const deliverable = (DELIV.find(([ks]) => ks.some(w => q.includes(w))) || [, "a ranked, de-risked target list"])[1];
    const modality = ["aso", "antisense", "sirna", "degrader", "gene therapy"].some(w => q.includes(w)) ? "ASO / genetic medicine" : "small molecule (default)";
    const type = (q.includes("diligence") || q.includes("fund") || q.includes("license")) ? "diligence"
      : (q.includes("trial") || q.includes("endpoint")) ? "trial-design"
      : (q.includes("portfolio") || q.includes("franchise")) ? "portfolio" : "prioritization";
    const req = new Set(["A", "B", "C"]);
    if (type === "trial-design" || type === "diligence") req.add("D");
    if (type === "diligence" || type === "portfolio") req.add("E");
    if (type === "portfolio") req.add("F");
    const required = [...req].sort();
    const agents = [{ name: "Internal Science Lead", why: "owns the moat hypothesis (the #N ranks)" },
      { name: "EMET Analyst", why: "genetics · pathway · drug-safety (live)" }];
    if (req.has("B")) agents.push({ name: "Q-Models Runner", why: "binding / selectivity / ADMET" });
    if (req.has("C")) agents.push({ name: "FDA Institutional Memory ⛔", why: "dispositive-veto check" }, { name: "Post-Market Safety", why: "class FAERS / labels" });
    if (req.has("D")) agents.push({ name: "Clinical-Trial Registry", why: "trial precedent" });
    if (req.has("E")) agents.push({ name: "Patent & IP ⛔", why: "freedom-to-operate veto" }, { name: "Financial & Investor", why: "pipeline + deals" }, { name: "Payer & Market Access", why: "reimbursement" });
    if (req.has("F")) agents.push({ name: "KOL & Social Signal", why: "expert sentiment" });
    const route = dk ? ROUTES[dk].panel : [["scientific", "Biotech CSO (disease-matched)"], ["commercial", "Pharma BD SVP"], ["investability", "Venture GP"], ["regulatory", "Pharma Neuro SVP / ex-FDA"]];
    const panel = route.map(([lens, arch]) => ({ lens, persona: arch, why: arch }));
    panel.push({ lens: "adversarial", persona: "Adversarial Red-Team (always seated)", why: "stress every claim" });
    return {
      disease: dk ? ROUTES[dk].label : "general CNS", scenarioId: dk ? ROUTES[dk].scenario : null,
      deliverable, modality, type,
      required_fields: required.map(g => `${g} ${GROUPS[g]}`),
      skip_fields: Object.keys(GROUPS).filter(g => !req.has(g)).map(g => `${g} ${GROUPS[g]}`),
      agents, panel,
    };
  }

  let active = 0, running = false;
  const tabsWrap = $("#orchTabs"), flow = $("#orchFlow"), input = $("#orchInput"), routeLine = $("#orchRoute"), runBtn = $("#orchRun");

  OD.scenarios.forEach((s, i) => {
    const t = el("button", "orch-tab" + (i === 0 ? " on" : ""), s.title);
    t.onclick = () => { if (running) return; active = i; selectTab(i); input.value = s.query; route(); reset(); };
    tabsWrap.append(t);
  });
  function selectTab(i) { tabsWrap.querySelectorAll(".orch-tab").forEach((x, k) => x.classList.toggle("on", k === i)); }

  function stageShell(id, label, sub) {
    return `<div class="ostage" data-st="${id}">
      <div class="ostage-rail"><span class="ostage-dot"></span><span class="ostage-label">${label}</span><span class="ostage-sub">${sub}</span></div>
      <div class="ostage-body" id="ob-${id}"></div></div>`;
  }
  function reset() {
    flow.innerHTML =
      stageShell("plan", "PLAN", "engagement lead") +
      stageShell("discover", "DISCOVER", "EMET → fact dossier") +
      stageShell("validate", "VALIDATE", "Q-Models") +
      stageShell("consult", "CONSULT", "roundtable · 2 rounds") +
      stageShell("synth", "SYNTHESIZE", "router");
  }

  function route() {
    const q = input.value.trim();
    const pl = planFor(q);
    const sIdx = pl.scenarioId ? OD.scenarios.findIndex(s => s.id === pl.scenarioId) : -1;
    if (sIdx >= 0) { active = sIdx; selectTab(sIdx); routeLine.innerHTML = `<span class="rt-ok">routed →</span> ${esc(OD.scenarios[sIdx].title)} <span class="rt-dim">(instant · from the engine)</span>`; }
    else if (BRIDGE.live) { selectTab(-1); routeLine.innerHTML = `<span class="rt-ok">live →</span> no shipped scenario; running it through <b>Claude on your subscription</b> (~1–3 min).`; }
    else { selectTab(-1); routeLine.innerHTML = `<span class="rt-warn">planner only →</span> no shipped scenario and no live bridge; showing the plan. Run <code>serve.py</code> for a live answer.`; }
    return { plan: pl, sIdx };
  }

  const dots = n => `<span class="conv" title="conviction ${n}/5">${"●".repeat(n)}${"○".repeat(5 - n)}</span>`;
  const tierDot = t => `<span class="tiertag tt-${(t || "").replace("-", "x")}" title="credibility ${t}">${esc(t)}</span>`;
  const FLAG = { VETO: ["⛔", "fl-veto"], DIVERGENCE: ["⚡", "fl-div"], KNOWN_UNKNOWN: ["?", "fl-unk"] };

  function planCard(pl) {
    const ag = pl.agents.map(a => `<li><b>${esc(a.name)}</b> <span class="pl-why">${esc(a.why)}</span></li>`).join("");
    const pan = pl.panel.map(s => `<li><span class="badge lens-${LENS[s.lens] || 'muted'}">${s.lens}</span> ${esc(s.persona)}</li>`).join("");
    const req = (pl.required_fields || []).map(f => `<span class="chip-req">${esc(f)}</span>`).join("");
    const skip = (pl.skip_fields || []).map(f => `<span class="chip-skip">${esc(f)}</span>`).join("");
    return `<div class="planwrap">
      <div class="pl-row"><span class="pl-k">deliverable</span> ${esc(pl.deliverable)} <span class="pl-sep">·</span> <span class="pl-k">type</span> ${esc(pl.type)} <span class="pl-sep">·</span> <span class="pl-k">disease</span> ${esc(pl.disease)} <span class="pl-sep">·</span> <span class="pl-k">modality</span> ${esc(pl.modality)}</div>
      <div class="pl-row"><span class="pl-k">dossier</span> ${req} ${skip ? `<span class="pl-skip-lbl">skip</span> ${skip}` : ""}</div>
      <div class="pl-cols">
        <div class="pl-col"><div class="pl-h">agents activated <span class="pl-only">— only what's needed</span></div><ul class="pl-list">${ag}</ul></div>
        <div class="pl-col"><div class="pl-h">panel seated <span class="pl-only">— one per lens + red-team</span></div><ul class="pl-list">${pan}</ul></div>
      </div></div>`;
  }

  function dossierTable(d) {
    const rows = d.dossier.map(f => {
      const fl = FLAG[f.flag]; const tag = fl ? `<span class="dflag ${fl[1]}">${fl[0]} ${f.flag.replace("_", " ")}</span>` : "";
      return `<div class="drow2"><div class="df-field">${esc(f.field)} ${tierDot(f.tier)}</div><div class="df-val">${esc(f.value)} ${tag}<span class="df-src">${esc(f.source)}</span></div></div>`;
    }).join("");
    const flagBar = ["VETO", "DIVERGENCE", "KNOWN_UNKNOWNS"].map(k => {
      const arr = d.flags[k]; if (!arr || !arr.length) return "";
      const m = { VETO: ["⛔", "fl-veto", "VETO gate"], DIVERGENCE: ["⚡", "fl-div", "DIVERGENCE — surfaced, not reconciled"], KNOWN_UNKNOWNS: ["?", "fl-unk", "KNOWN UNKNOWN"] }[k];
      return arr.map(v => `<div class="flagline ${m[1]}"><span class="fl-tag">${m[0]} ${m[2]}</span> ${esc(v)}</div>`).join("");
    }).join("");
    return `<div class="dossier">${rows}</div><div class="dstatus">dossier status: <b>${esc(d.status)}</b></div>${flagBar}`;
  }

  function personaCard(p) {
    const card = el("div", "pcard", `
      <div class="pcard-top"><span class="badge lens-${LENS[p.lens] || 'muted'}">${p.lens}</span><span class="badge st-${STANCE[p.stance]}">${p.stance}</span></div>
      <div class="pcard-name">${esc(p.persona)}</div><div class="pcard-role">${esc(p.role)}</div>
      <div class="pcard-head">“${esc(p.headline)}”</div>${dots(p.conviction)}
      <div class="pcard-more">
        <div class="pm-row"><span class="pm-k">why</span> ${esc(p.rationale)}</div>
        <div class="pm-row"><span class="pm-k risk">top risk</span> ${esc(p.top_risk)}</div>
        <div class="pm-row"><span class="pm-k ask">the ask</span> ${esc(p.ask)}</div>
      </div>`);
    card.onclick = e => { if (!e.target.closest(".pcard-more")) card.classList.toggle("open"); };
    return card;
  }

  async function lite(id) { const s = flow.querySelector(`[data-st=${id}]`); if (s) s.classList.add("lit"); await sleep(140); }

  // unified bucket renderer — works for canned scenarios AND live API runs (same shape)
  async function renderBuckets(run) {
    await lite("discover");
    $("#ob-discover").innerHTML =
      `<p class="ob-line">${esc(run.discover.summary)}</p><div class="ob-result"><b>→</b> ${esc(run.discover.result)}</div>` +
      dossierTable(run.discover) + `<div class="ob-src">source: ${esc(run.discover.source)}</div>`;
    await sleep(900);

    await lite("validate");
    $("#ob-validate").innerHTML = run.validate.runs.map(r => `<div class="qrow"><span class="qmodel">${esc(r.model)}</span><span class="qout">${esc(r.out)}</span></div>`).join("") +
      `<div class="ob-result"><b>→</b> ${esc(run.validate.result)}</div><div class="ob-src">source: ${esc(run.validate.source)}${run.validate.mock ? " · MOCK" : ""}</div>`;
    await sleep(850);

    await lite("consult");
    const body = $("#ob-consult");
    body.innerHTML = `<div class="ob-convening">Roundtable convened — ${run.consult.round1.length} viewpoints, grounded in the dossier above:</div><div class="rd-lbl">Round 1 — independent verdicts</div><div class="pgrid"></div>`;
    const grid = body.querySelector(".pgrid");
    for (const p of run.consult.round1) { const c = personaCard(p); c.style.opacity = 0; grid.append(c); await sleep(50); requestAnimationFrame(() => { c.style.transition = "opacity .4s, transform .4s"; c.style.opacity = 1; c.style.transform = "none"; }); await sleep(280); }
    if (run.consult.round2 && run.consult.round2.length) {
      const r2 = el("div", "round2", `<div class="rd-lbl">Round 2 — moderated rebuttal</div>`); body.append(r2);
      for (const r of run.consult.round2) {
        const moved = r.revised ? `<span class="r2-moved">↻ revised</span>` : `<span class="r2-held">held</span>`;
        const line = el("div", "r2row", `${dots(r.conviction)} <b>${esc(r.persona.split(",")[0])}</b> ${moved} <span class="r2-shift">${esc(r.shift)}</span>`);
        line.style.opacity = 0; r2.append(line); await sleep(50); requestAnimationFrame(() => { line.style.transition = "opacity .4s"; line.style.opacity = 1; }); await sleep(220);
      }
    }
    const sp = run.consult.spread;
    body.insertAdjacentHTML("beforeend",
      `<div class="convergent"><span class="cg-tag">CONVERGENT GATE</span> ${esc(sp.convergent_gate)}</div>
       <div class="dissent"><span class="cg-tag dim">SPREAD</span> conviction ${esc(sp.conviction_range)} · ${esc(sp.dissent)}</div>`);
    await sleep(600);

    await lite("synth");
    $("#ob-synth").innerHTML =
      `<div class="syn-rec">${esc(run.synthesize.recommendation)}</div>
       <div class="syn-grid">
         <div class="syn-cell"><span class="syn-k">consensus</span>${esc(run.synthesize.consensus)}</div>
         <div class="syn-cell"><span class="syn-k">confidence</span>${esc(run.synthesize.confidence)}</div>
         <div class="syn-cell exp"><span class="syn-k">proposed experiment</span>${esc(run.synthesize.proposed_experiment)}</div>
       </div>`;
  }

  async function run() {
    if (running) return; running = true; runBtn.disabled = true;
    const { plan: jsPlan, sIdx } = route();
    reset();
    await sleep(160);

    // PLAN — always, instant
    await lite("plan");
    $("#ob-plan").innerHTML = planCard(jsPlan);
    await sleep(650);

    if (sIdx >= 0) {                       // shipped scenario — instant
      await renderBuckets(OD.scenarios[sIdx]);
    } else if (BRIDGE.live) {              // novel — Claude on the subscription
      await lite("discover");
      const think = el("div", "thinking", `<span class="think-dot"></span> Claude is running the firm on your subscription — gathering the dossier, convening the panel… (~1–3 min)`);
      $("#ob-discover").innerHTML = ""; $("#ob-discover").append(think);
      try {
        const resp = await fetch("/api/run?q=" + encodeURIComponent(input.value.trim()), { cache: "no-store" });
        const live = await resp.json();
        if (live && live.live && live.discover) {
          $("#ob-plan").innerHTML = planCard(live.plan || jsPlan);   // authoritative engine plan
          await renderBuckets(live);
          routeLine.innerHTML = `<span class="rt-ok">live →</span> answered by <b>${esc(live.model || "Claude")}</b> on your subscription.`;
        } else {
          $("#ob-discover").innerHTML = `<p class="ob-line ob-skip">${esc((live && live.note) || "Live brain returned no run.")} </p>`;
          ["validate", "consult", "synth"].forEach(id => flow.querySelector(`[data-st=${id}]`).classList.add("lit", "muted-stage"));
        }
      } catch (e) {
        $("#ob-discover").innerHTML = `<p class="ob-line ob-skip">Live request failed (${esc(e.message)}). Pick a shipped scenario for a full run.</p>`;
      }
    } else {                              // planner-only (static)
      ["discover", "validate", "consult", "synth"].forEach(id => {
        $("#ob-" + id).innerHTML = `<p class="ob-line ob-skip">Awaiting live agents — start the bridge (<code>python sapphire-orchestrator/serve.py</code>) to run this query through Claude on your subscription, or pick a shipped scenario.</p>`;
        flow.querySelector(`[data-st=${id}]`).classList.add("lit", "muted-stage");
      });
    }
    runBtn.disabled = false; running = false;
  }

  runBtn.onclick = run;
  input.addEventListener("input", () => { if (!running) route(); });
  input.addEventListener("keydown", e => { if (e.key === "Enter") run(); });

  input.value = OD.scenarios[0].query;
  route(); reset();
  new IntersectionObserver((es, o) => es.forEach(e => { if (e.isIntersecting) { run(); o.disconnect(); } }), { threshold: .15 }).observe($("#console"));
})();
