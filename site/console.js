/* ============ Sapphire Console — a chat over the orchestrator ============
   Left: conversation thread. Right: inspector (systems status + the active run's dossier,
   roundtable, synthesis). Multi-turn via the bridge (serve.py → /api/chat → Claude on your
   subscription). Offline (no bridge): the two shipped scenarios still run from window.SAPPHIRE_ORCH;
   anything else shows the engagement plan honestly. Every fact carries its true provenance.
*/
(() => {
  const OD = window.SAPPHIRE_ORCH;
  if (!OD) return;
  const $ = (s, r = document) => r.querySelector(s);
  const el = (t, c, h) => { const e = document.createElement(t); if (c) e.className = c; if (h != null) e.innerHTML = h; return e; };
  const esc = s => (s == null ? "" : String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"));

  const STANCE = { champion: "boost", conditional: "gold", skeptic: "gate", veto: "gap" };
  const LENS = { scientific: "signal", commercial: "gold", investability: "boost", regulatory: "gate", adversarial: "gap" };
  const PROV = {
    emet: ["✓", "pv-emet", "EMET (captured live)"],
    claude: ["◇", "pv-claude", "Claude reconstruction (EMET not queried)"],
    mock: ["◍", "pv-mock", "mock (no tool wired)"],
    other: ["·", "pv-other", "note"],
  };

  const thread = $("#chatThread"), input = $("#chatInput"), sendBtn = $("#chatSend"),
    presetsWrap = $("#chatPresets"), inspSystems = $("#inspSystems"), inspRun = $("#inspRun"), statusBadge = $("#orchStatus");

  const BRIDGE = { live: false, model: "", subsystems: { claude: "down", emet: "not-wired", qmodels: "mock", moat: "mock" } };
  const history = [];     // [{role, content}] sent to the bridge for follow-up context
  let currentRun = null, busy = false;

  /* ---------- planner mirror (offline routing + the plan) ---------- */
  const ROUTES = {
    pain: { keys: ["pain", "nav1.8", "nav1_8", "scn10a", "scn11a", "nav1.9", "neuropathic", "analgesic", "nocicept"], scenario: "nav1_8" },
    tsc: { keys: ["tsc2", "tsc1", "tuberous", "mtor", "rheb", "depdc5", "epilep", "fcd", "hyperexcitab"], scenario: "tsc2" },
  };
  const ENGAGE_KW = ["prioriti", "rank", "triage", "fundable", "diligence", "trial", "go/no-go", "portfolio", "franchise", "validate", "de-risk", "should we", "target"];
  const scenarioFor = q => { q = (q || "").toLowerCase(); for (const k in ROUTES) if (ROUTES[k].keys.some(w => q.includes(w))) return ROUTES[k].scenario; return null; };
  const looksLikeEngagement = q => { const m = (q || "").toLowerCase(); return ENGAGE_KW.some(w => m.includes(w)) || !!scenarioFor(q) || /\b[A-Z][A-Z0-9]{2,}\b/.test(q || ""); };

  /* ---------- systems status (the standing honesty surface) ---------- */
  const SYS_STATE = {
    "live": ["sys-live", "live"], "live-local": ["sys-live", "live · local"],
    "stub": ["sys-mock", "stub"], "mock": ["sys-mock", "mock"],
    "not-wired": ["sys-off", "not wired"], "down": ["sys-off", "down"],
  };
  function renderSystems() {
    const s = BRIDGE.subsystems;
    const row = (name, state, meaning) => {
      const [cls, label] = SYS_STATE[state] || ["sys-off", state || "—"];
      return `<div class="sys-row"><span class="sys-dot ${cls}"></span><span class="sys-name">${name}</span><span class="sys-state ${cls}">${label}</span><span class="sys-why">${meaning}</span></div>`;
    };
    const qm = s.qmodels;
    const qmWhy = qm === "live-local" ? "DTI / BBBP / Tox served live (CPU) — callable now via the model registry"
      : qm === "stub" ? "endpoint up, placeholder predictions — run setup to make CPU tools live"
      : "binding / ADMET / selectivity — endpoint down (start serve_local.sh); GPU tools via the launcher";
    inspSystems.innerHTML = `<div class="insp-h">Systems</div>` +
      row("Claude", s.claude === "live" ? "live" : "down", "the reasoning — your subscription") +
      row("EMET", s.emet, "BenchSci — not wired to the web; only shipped scenarios carry real EMET evidence") +
      row("Q-Models", qm, qmWhy) +
      row("internal moat", s.moat, "Quiver EP-CRISPR latent space — mock") +
      `<div class="sys-note">Claude is live. Q-Models exposes <b>${MODELS.length || "—"}</b> callable tools (registry). In a live <i>chat</i> answer, dossier facts are Claude's reconstruction; tool calls via the model registry carry their own provenance.</div>`;
  }

  // the callable Q-Models tool menu (from /api/tools) — the visible "any model" surface
  let MODELS = [];
  const TIER_LABEL = { "local-cpu": "CPU · sync", "gpu-launch": "GPU · async", "endpoint": "endpoint", "batch-ec2": "batch" };
  const STATUS_CLS = { "live-local": "pv-emet", "live": "pv-emet", "eval": "pv-mock", "experimental": "pv-mock", "deprecated": "pv-other", "todo": "pv-other" };
  async function loadModels() {
    let card = $("#inspModels");
    if (!card) { card = el("div", "insp-card", ""); card.id = "inspModels"; inspSystems.after(card); }
    try { MODELS = (await (await fetch("/api/tools", { cache: "no-store" })).json()).tools || []; }
    catch (e) { MODELS = []; }
    if (!MODELS.length) { card.innerHTML = `<div class="insp-h">Models</div><div class="insp-empty">Tool registry unavailable (start the bridge: serve.py).</div>`; renderSystems(); return; }
    const byTier = {};
    MODELS.forEach(m => { (byTier[m.tier] = byTier[m.tier] || []).push(m); });
    const groups = Object.keys(byTier).map(tier =>
      `<div class="mdl-grp"><div class="mdl-tier">${TIER_LABEL[tier] || tier}</div>` +
      byTier[tier].map(m => `<div class="mdl-row"><span class="mdl-id">${esc(m.label || m.id)}</span><span class="pvtag ${STATUS_CLS[m.status] || 'pv-other'}">${esc(m.status)}</span></div>`).join("") +
      `</div>`).join("");
    card.innerHTML = `<div class="insp-h">Models <span class="insp-sub">${MODELS.length} callable via the orchestrator</span></div>${groups}`;
    renderSystems();
  }

  async function health() {
    try {
      const h = await (await fetch("/api/health", { cache: "no-store" })).json();
      BRIDGE.live = !!h.live; BRIDGE.model = h.model || ""; if (h.subsystems) BRIDGE.subsystems = h.subsystems;
      statusBadge.innerHTML = BRIDGE.live ? `<span class="st-live"></span> live · Claude` : `<span class="st-demo"></span> demo`;
    } catch (e) {
      BRIDGE.live = false; statusBadge.innerHTML = `<span class="st-demo"></span> demo · static`;
    }
    renderSystems();
  }

  /* ---------- thread messages ---------- */
  const scrollEnd = () => { thread.scrollTop = thread.scrollHeight; };
  function addUser(text) { thread.append(el("div", "msg msg-user", `<div class="bubble">${esc(text)}</div>`)); scrollEnd(); }
  function addReply(text, cites) {
    const c = (cites && cites.length) ? `<div class="reply-cites">${cites.map(x => `<span class="cite">${esc(x)}</span>`).join("")}</div>` : "";
    thread.append(el("div", "msg msg-bot", `<div class="bot-mark">◆</div><div class="bubble bot-reply">${esc(text)}${c}</div>`)); scrollEnd();
  }
  function addThinking(label) {
    const m = el("div", "msg msg-bot thinking-msg", `<div class="bot-mark">◆</div><div class="bubble"><span class="think-dot"></span> ${esc(label)}</div>`);
    thread.append(m); scrollEnd(); return m;
  }
  function addRunMsg(run) {
    const live = run.origin === "live";
    const sy = run.synthesize || {};
    const m = el("div", "msg msg-bot",
      `<div class="bot-mark">◆</div>
       <div class="bubble bot-run">
         <div class="run-headline">${esc(run.headline || run.title || "")}</div>
         <div class="run-rec"><span class="run-rec-k">recommendation</span> ${esc(sy.recommendation || "")}</div>
         <div class="run-meta">
           <span class="run-prov ${live ? 'pv-claude' : 'pv-emet'}">${live ? '◇ Claude-reconstructed' : '✓ scenario · EMET captured'}</span>
           <button class="run-open">open in inspector →</button>
         </div>
       </div>`);
    m.querySelector(".run-open").onclick = () => { selectRun(run, m); };
    m.querySelector(".bot-run").onclick = e => { if (!e.target.closest(".run-open")) selectRun(run, m); };
    thread.append(m); scrollEnd();
    selectRun(run, m);
  }
  function selectRun(run, msgEl) {
    currentRun = run;
    thread.querySelectorAll(".msg-bot .bot-run.sel").forEach(x => x.classList.remove("sel"));
    if (msgEl) msgEl.querySelector(".bot-run")?.classList.add("sel");
    loadInspector(run);
  }

  /* ---------- inspector: the active run ---------- */
  const provBadge = p => { const x = PROV[p] || PROV.other; return `<span class="pvtag ${x[1]}" title="${x[2]}">${x[0]}</span>`; };
  const dots = n => `<span class="conv" title="conviction ${n}/5">${"●".repeat(n)}${"○".repeat(5 - n)}</span>`;
  const FLAG = { VETO: ["⛔", "fl-veto"], DIVERGENCE: ["⚡", "fl-div"], KNOWN_UNKNOWN: ["?", "fl-unk"] };

  function loadInspector(run) {
    const d = run.discover, c = run.consult, sy = run.synthesize, live = run.origin === "live";
    const banner = live
      ? `<div class="run-banner bn-live">Generated by Claude on your subscription. EMET / Q-Models / moat aren't connected — these facts are Claude's reconstruction, not live tool output.</div>`
      : `<div class="run-banner bn-cap">Shipped scenario — EMET evidence captured live via Playwright; Q-Models &amp; moat are mock.</div>`;
    const dossier = d.dossier.map(f => {
      const fl = FLAG[f.flag]; const tag = fl ? `<span class="dflag ${fl[1]}">${fl[0]} ${f.flag.replace("_", " ")}</span>` : "";
      return `<div class="drow2"><div class="df-field">${provBadge(f.provenance)} ${esc(f.field)}</div>
        <div class="df-val">${esc(f.value)} ${tag}<span class="df-src">${esc(f.source)}</span></div></div>`;
    }).join("");
    const flagLines = ["VETO", "DIVERGENCE", "KNOWN_UNKNOWNS"].flatMap(k => {
      const arr = (d.flags || {})[k] || []; const m = { VETO: ["⛔", "fl-veto", "VETO gate"], DIVERGENCE: ["⚡", "fl-div", "DIVERGENCE"], KNOWN_UNKNOWNS: ["?", "fl-unk", "KNOWN UNKNOWN"] }[k];
      return arr.map(v => `<div class="flagline ${m[1]}"><span class="fl-tag">${m[0]} ${m[2]}</span> ${esc(v)}</div>`);
    }).join("");
    const panel = c.round1.map(p => `
      <div class="pcard"><div class="pcard-top"><span class="badge lens-${LENS[p.lens] || 'muted'}">${esc(p.lens)}</span><span class="badge st-${STANCE[p.stance]}">${esc(p.stance)}</span>${dots(p.conviction)}</div>
        <div class="pcard-name">${esc(p.persona)}</div><div class="pcard-head">“${esc(p.headline)}”</div>
        <div class="pcard-more"><div class="pm-row"><span class="pm-k risk">risk</span> ${esc(p.top_risk)}</div><div class="pm-row"><span class="pm-k ask">ask</span> ${esc(p.ask)}</div></div></div>`).join("");
    const r2 = (c.round2 || []).map(r => `<div class="r2row">${dots(r.conviction)} <b>${esc((r.persona || "").split(",")[0])}</b> ${r.revised ? '<span class="r2-moved">↻</span>' : '<span class="r2-held">held</span>'} <span class="r2-shift">${esc(r.shift)}</span></div>`).join("");
    const sp = c.spread || {};

    inspRun.innerHTML =
      `<div class="insp-h">Active run <span class="insp-sub">${esc(run.title || "")}</span></div>
       ${banner}
       <details open class="insp-sec"><summary>Dossier · ${d.dossier.length} facts <span class="sec-tag">${esc(d.status || "")}</span></summary>
         <div class="dossier">${dossier}</div>${flagLines}</details>
       <details class="insp-sec"><summary>Validate · Q-Models <span class="sec-tag mock">${live ? "claude" : "mock"}</span></summary>
         ${(run.validate.runs || []).map(r => { const pv = r.provenance || (live ? "claude" : "mock"); return `<div class="qrow"><span class="qmodel">${provBadge(pv)} ${esc(r.model)}</span><span class="qout">${esc(r.out)}</span></div>`; }).join("")}
         <div class="ob-result">→ ${esc(run.validate.result)}</div></details>
       <details open class="insp-sec"><summary>Roundtable · ${c.round1.length} partners, 2 rounds</summary>
         <div class="pgrid">${panel}</div>
         ${r2 ? `<div class="rd-lbl">Round 2 — rebuttal</div>${r2}` : ""}
         <div class="convergent"><span class="cg-tag">CONVERGENT GATE</span> ${esc(sp.convergent_gate || "")}</div>
         <div class="dissent"><span class="cg-tag dim">SPREAD</span> conviction ${esc(sp.conviction_range || "")} · ${esc(sp.dissent || "")}</div></details>
       <details open class="insp-sec"><summary>Synthesis</summary>
         <div class="syn-rec">${esc(sy.recommendation || "")}</div>
         <div class="syn-cell"><span class="syn-k">confidence</span>${esc(sy.confidence || "")}</div>
         <div class="syn-cell exp"><span class="syn-k">proposed experiment</span>${esc(sy.proposed_experiment || "")}</div></details>`;
    inspRun.querySelectorAll(".pcard").forEach(card => card.onclick = () => card.classList.toggle("open"));
  }

  /* ---------- send ---------- */
  async function send(text) {
    if (busy) return;
    const msg = (text != null ? text : input.value).trim();
    if (!msg) return;
    busy = true; sendBtn.disabled = true; input.value = ""; autosize();
    addUser(msg); history.push({ role: "user", content: msg });

    if (BRIDGE.live) {
      const think = addThinking(looksLikeEngagement(msg) || !currentRun ? "Running the firm on your subscription — dossier, panel, synthesis… (~1–3 min)" : "Thinking over the dossier…");
      try {
        const resp = await fetch("/api/chat", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: msg, history: history.slice(-8), current_dossier: (currentRun && currentRun.discover && currentRun.discover.dossier) || [] }),
        });
        const data = await resp.json();
        think.remove();
        if (data.kind === "run" && data.run) { addRunMsg(data.run); history.push({ role: "assistant", content: (data.run.headline || "") + " — " + ((data.run.synthesize || {}).recommendation || "") }); }
        else { addReply(data.text || "(no answer)", data.cites); history.push({ role: "assistant", content: data.text || "" }); }
      } catch (e) { think.remove(); addReply("Live request failed (" + e.message + "). Try a shipped scenario."); }
    } else {
      // offline: scenarios still run from bundled data; otherwise show the plan honestly
      const sid = scenarioFor(msg);
      const idx = sid ? OD.scenarios.findIndex(s => s.id === sid) : -1;
      if (idx >= 0) { addRunMsg(OD.scenarios[idx]); history.push({ role: "assistant", content: OD.scenarios[idx].headline }); }
      else if (currentRun && !looksLikeEngagement(msg)) { addReply("Follow-ups need the live bridge — start it with `python sapphire-orchestrator/serve.py`, then ask again. (The dossier is in the inspector.)"); }
      else { addReply("No shipped scenario matches and the live bridge is off. Start `serve.py` to run this through Claude on your subscription, or try the Nav1.8 / TSC2 presets."); }
    }
    busy = false; sendBtn.disabled = false; input.focus();
  }

  /* ---------- presets + input wiring ---------- */
  OD.scenarios.forEach(s => {
    const chip = el("button", "preset-chip", esc(s.title.replace(/ —.*/, "")));
    chip.onclick = () => { if (!busy) send(s.query); };
    presetsWrap.append(chip);
  });
  function autosize() { input.style.height = "auto"; input.style.height = Math.min(input.scrollHeight, 130) + "px"; }
  input.addEventListener("input", autosize);
  input.addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } });
  sendBtn.onclick = () => send();

  /* ---------- init ---------- */
  inspRun.innerHTML = `<div class="insp-h">Active run</div><div class="insp-empty">Ask a question or pick a scenario — the dossier, roundtable, and synthesis appear here, each fact tagged with its source.</div>`;
  thread.append(el("div", "msg msg-bot", `<div class="bot-mark">◆</div><div class="bubble bot-reply">I'm the Sapphire orchestrator. Ask me to prioritize targets, validate a hypothesis, or assess fundability for a CNS program — I'll plan it, gather a cited dossier, convene a partner roundtable, and recommend. Try a preset below, or type your own.</div>`));
  health();
  loadModels();
})();
