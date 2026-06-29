/* ============================================================================
   Sapphire frontend2 — Hayes's adopted console design, realized as the live UI.
   Vanilla JS, no framework.

   On submit: POST /api/run, read the Server-Sent Events stream, and
     • build the AGENT WING (left) live — categorized per-subagent cards, status
       flipping queued→active→ok/abstain as `progress` events arrive;
     • stream the LIVE TRACE step-tree (right panel) from the same events;
     • on the final `result` (the full run_live dict): fill the EVIDENCE rows
       (right panel, grouped by data plane), attach each fact to its agent card
       as a source, and render the CENTER — synthesis with ATTRIBUTED FINDINGS
       (click → open + highlight the responsible agent in the wing) + the spread.

   Honesty markers (● REAL / 🧪 simulated / ◆ CAPTURED) are derived from each
   fact's provenance verbatim — never relabeled, never fabricated. An abstention
   is marked ⚠, never a false ✓.
   ============================================================================ */
(function () {
  "use strict";

  // ── elements ──────────────────────────────────────────────────
  const $ = (id) => document.getElementById(id);
  const leftToggle = $("leftToggle"), rightToggle = $("rightToggle");
  const leftPanel = $("leftPanel"), rightPanel = $("rightPanel");
  const chatCol = $("chatCol"), emptyState = $("emptyState"), msgList = $("msgList");
  const chatInput = $("chatInput"), sendBtn = $("sendBtn"), thread = $("thread"), threadInner = $("threadInner");
  const profileSel = $("profile"), liveBadge = $("liveBadge"), liveLabel = $("liveLabel");
  const modelSel = $("model"), modelBadge = $("modelBadge");
  const traceTree = $("traceTree"), traceStatus = $("traceStatus"), traceMeta = $("traceMeta");
  const agentTree = $("agentTree"), wingMeta = $("wingMeta");
  const evidenceBody = $("evidenceBody"), evidenceMeta = $("evidenceMeta"), rightScroll = $("rightScroll");

  let busy = false, activated = false;

  // ── agent metadata: id → {name, cat}. Names from the firm roster; categories group
  //    the wing exactly as Hayes's mock does. Drives both the wing cards and finding labels.
  const AGENT_META = {
    "internal-science-lead":        { name: "Internal Science Lead (Quiver moat)", cat: "Internal Science & Moat" },
    "robyn-scs":                    { name: "robyn_scs connectivity",              cat: "Internal Science & Moat" },
    "emet-runner":                  { name: "EMET Analyst — live BenchSci",        cat: "Biomedical Evidence (EMET)" },
    "q-models-runner":              { name: "Q-Models launchpad",                  cat: "Quantitative Models" },
    "boltz":                        { name: "Boltz structure / binding",           cat: "Quantitative Models" },
    "gnomad-constraint":            { name: "gnomAD constraint",                   cat: "Genetics & Constraint" },
    "gtex-expression":              { name: "GTEx expression",                     cat: "Genetics & Constraint" },
    "interpro-domains":             { name: "InterPro domains",                    cat: "Genetics & Constraint" },
    "geneset-enrichment":           { name: "g:Profiler enrichment",               cat: "Genetics & Constraint" },
    "aso-tox":                      { name: "ASO acute-tox screen",                cat: "Quiver Tools" },
    "fda-institutional-memory":     { name: "FDA Institutional Memory ⛔",          cat: "Regulatory Memory (veto-class)" },
    "patent-ip":                    { name: "Patent / IP ⛔",                       cat: "Patent & IP (veto-class)" },
    "global-regulatory-divergence": { name: "Global regulatory divergence",        cat: "Semantic Web" },
    "dea-scheduling":               { name: "DEA scheduling",                      cat: "Semantic Web" },
    "clinical-trial-registry":      { name: "Clinical-trial registry",             cat: "Semantic Web" },
    "post-market-safety":           { name: "Post-market safety",                  cat: "Semantic Web" },
    "financial":                    { name: "Financial / investor",               cat: "Semantic Web" },
    "payer":                        { name: "Payer / reimbursement",               cat: "Semantic Web" },
    "manufacturing-cmc":            { name: "Manufacturing / CMC",                 cat: "Semantic Web" },
    "patient-advocacy":             { name: "Patient advocacy",                    cat: "Semantic Web" },
    "kol-social":                   { name: "KOL / social signal",                 cat: "Semantic Web" },
    "policy-legislative":           { name: "Policy / legislative",                cat: "Semantic Web" },
    "reputational":                 { name: "Reputational",                        cat: "Semantic Web" },
  };
  // Category display order in the wing.
  const CAT_ORDER = [
    "Internal Science & Moat", "Biomedical Evidence (EMET)", "Quantitative Models",
    "Genetics & Constraint", "Quiver Tools", "Regulatory Memory (veto-class)",
    "Patent & IP (veto-class)", "Semantic Web", "Roundtable Partners",
  ];
  function agentName(id) { return (AGENT_META[id] && AGENT_META[id].name) || id || "agent"; }
  function agentCat(id) { return (AGENT_META[id] && AGENT_META[id].cat) || "Other"; }

  // ── helpers ───────────────────────────────────────────────────
  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
  function el(tag, cls, html) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    return e;
  }
  function scrollThread() { thread.scrollTop = thread.scrollHeight; }
  function scrollRight() { if (rightScroll) rightScroll.scrollTop = rightScroll.scrollHeight; }

  // Honesty class for a provenance string → real / sim / cap (● REAL / 🧪 simulated / ◆ CAPTURED).
  function provClass(prov, via) {
    const p = String(prov || "").toLowerCase();
    if (p === "simulated") return "sim";
    if (via === "replay" || p === "captured") return "cap";
    if (p === "mock") return "sim"; // a stand-in — mark it, never as REAL
    return "real";
  }
  function tierClass(tier) {
    const t = String(tier || "").toUpperCase();
    return (t === "T1" || t === "T2" || t === "T3") ? "tier-" + t : "";
  }
  function stanceClass(stance) { return String(stance || "").toLowerCase().replace(/[^a-z]/g, ""); }

  // ── profile / live badge ─────────────────────────────────────
  function syncBadge() {
    const p = profileSel.value;
    liveBadge.className = "live-badge";
    if (p === "simulate") { liveBadge.classList.add("sim"); liveLabel.textContent = "Simulated"; }
    else if (p === "demo") { liveBadge.classList.add("demo"); liveLabel.textContent = "Demo"; }
    else if (p === "replay") { liveBadge.classList.add("cap"); liveLabel.textContent = "Captured"; }
    else { liveLabel.textContent = "Live"; }
  }
  profileSel.addEventListener("change", syncBadge);
  syncBadge();

  // ── URL-param preselection (?mode=replay | ?profile=<name>) ─────────────────
  // Keeps the $0 canned demo shareable: /?mode=replay instantly selects `replay`.
  // ?profile=simulate (or any valid option value) also preselects that profile.
  (function () {
    const params = new URLSearchParams(window.location.search);
    const target = params.get("mode") === "replay"
      ? "replay"
      : (params.get("profile") || "");
    if (target) {
      const valid = Array.from(profileSel.options).map(o => o.value);
      if (valid.indexOf(target) !== -1) {
        profileSel.value = target;
        syncBadge();
      }
    }
  })();

  // ── panel toggles ────────────────────────────────────────────
  function bindToggle(btn, panel) {
    btn.classList.toggle("active", panel.classList.contains("open"));
    btn.setAttribute("aria-pressed", String(panel.classList.contains("open")));
    btn.addEventListener("click", () => {
      const open = panel.classList.toggle("open");
      btn.classList.toggle("active", open);
      btn.setAttribute("aria-pressed", String(open));
    });
  }
  bindToggle(leftToggle, leftPanel);
  bindToggle(rightToggle, rightPanel);

  // ============================================================================
  // AGENT WING — categorized per-subagent cards, built + updated live (Hayes)
  // ============================================================================
  // wing state: cards keyed by agent_id; categories created lazily in CAT_ORDER.
  let wing = null;
  function resetWing() {
    agentTree.innerHTML = "";
    wing = { cats: {}, cards: {}, order: [] };
    wingMeta.textContent = "convening…";
  }
  function ensureCat(cat) {
    if (wing.cats[cat]) return wing.cats[cat];
    const node = el("div", "cat open");
    node.dataset.cat = cat;
    node.innerHTML =
      `<div class="cat-head"><span class="cat-chev">›</span>` +
      `<span class="cat-name">${esc(cat)}</span><span class="cat-stat" data-stat></span></div>` +
      `<div class="cat-body" data-body></div>`;
    // insert in CAT_ORDER position
    const idx = CAT_ORDER.indexOf(cat);
    let inserted = false;
    if (idx >= 0) {
      for (const other of Array.from(agentTree.children)) {
        const oi = CAT_ORDER.indexOf(other.dataset.cat);
        if (oi < 0 || oi > idx) { agentTree.insertBefore(node, other); inserted = true; break; }
      }
    }
    if (!inserted) agentTree.appendChild(node);
    wing.cats[cat] = node;
    return node;
  }
  function ensureCard(id) {
    if (wing.cards[id]) return wing.cards[id];
    const cat = ensureCat(agentCat(id));
    const body = cat.querySelector("[data-body]");
    const card = el("div", "agent-card");
    card.dataset.agent = id;
    card.innerHTML =
      `<div class="ac-head"><span class="ac-dot active" data-dot></span>` +
      `<span class="ac-title" data-title>${esc(agentName(id))}</span><span class="ac-chev">›</span></div>` +
      `<div class="ac-detail"><div class="ac-task" data-task>working…</div>` +
      `<div class="ac-brief" data-brief></div><div data-srcwrap></div></div>`;
    body.appendChild(card);
    wing.cards[id] = card;
    wing.order.push(id);
    return card;
  }
  function setCardStatus(id, status, ev) {
    const card = ensureCard(id);
    const dot = card.querySelector("[data-dot]");
    const cls = status === "ok" ? "ok" : (status === "active" ? "active" : "abstain");
    dot.className = "ac-dot " + cls;
    const task = card.querySelector("[data-task]");
    if (status === "active") { task.textContent = "working…"; return; }
    // done: a one-line outcome
    if (status === "ok") {
      const nf = ev && ev.n_facts != null ? `${ev.n_facts} fact(s)` : "complete";
      task.innerHTML = `✓ ${esc(nf)} ${provChip(ev && ev.provenance)}`;
    } else {
      const why = ev && ev.error ? ` — ${esc(ev.error)}` : "";
      task.innerHTML = `⚠ ${esc((ev && ev.status) || "abstained")}${why} ${provChip(ev && ev.provenance)}`;
    }
    updateCatStat(agentCat(id));
  }
  function updateCatStat(cat) {
    const node = wing.cats[cat]; if (!node) return;
    let ok = 0, warn = 0, total = 0;
    node.querySelectorAll(".agent-card [data-dot]").forEach((d) => {
      total++; if (d.classList.contains("ok")) ok++; else if (d.classList.contains("abstain")) warn++;
    });
    const stat = node.querySelector("[data-stat]");
    stat.innerHTML = `<span class="ok">${ok}✓</span>` + (warn ? ` <span class="warn">${warn}⚠</span>` : "") + ` / ${total}`;
  }

  // ── card expand/collapse + finding linkage ───────────────────
  function setFindingsLinked(id, on) {
    if (!id) return;
    msgList.querySelectorAll('.finding[data-agent="' + cssEsc(id) + '"]').forEach((f) => f.classList.toggle("linked", on));
  }
  function cssEsc(s) { return String(s).replace(/"/g, '\\"'); }
  agentTree.addEventListener("click", (e) => {
    const catHead = e.target.closest(".cat-head");
    if (catHead) { catHead.parentNode.classList.toggle("open"); return; }
    const acHead = e.target.closest(".ac-head");
    if (acHead) {
      const card = acHead.parentNode;
      const open = card.classList.toggle("open");
      setFindingsLinked(card.dataset.agent, open);
    }
  });
  // open a specific agent: reveal wing, expand its category + card, highlight it
  function openAgent(id) {
    const card = wing && wing.cards[id];
    if (!card) return;
    if (!leftPanel.classList.contains("open")) {
      leftPanel.classList.add("open"); leftToggle.classList.add("active");
      leftToggle.setAttribute("aria-pressed", "true");
    }
    card.closest(".cat").classList.add("open");
    const prev = agentTree.querySelector(".agent-card.target");
    if (prev && prev !== card) prev.classList.remove("target");
    card.classList.add("open", "target");
    setFindingsLinked(id, true);
    card.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  // ============================================================================
  // LIVE TRACE — built from streamed `progress` events (right panel)
  // ============================================================================
  const GROUP = {
    bucket1: { icon: "🧬", name: "Bucket 1 — cited fact dossier" },
    roundtable: { icon: "👥", name: "Bucket 2 — the persona roundtable (the spread)" },
  };
  let trace = null;
  function resetTrace() {
    traceTree.innerHTML = "";
    trace = { groups: {}, rows: {}, tops: {} };
    traceMeta.textContent = "";
  }
  function ensureGroup(stage) {
    if (trace.groups[stage]) return trace.groups[stage];
    const g = GROUP[stage] || { icon: "•", name: stage };
    const wrap = el("div", "trace-group",
      `<div class="tg-head"><span class="tg-icon">${g.icon}</span><span>${esc(g.name)}</span>` +
      `<span class="tg-meta" data-meta></span></div>`);
    traceTree.appendChild(wrap);
    trace.groups[stage] = wrap;
    return wrap;
  }
  function handleProgress(ev) {
    const stage = ev.stage, phase = ev.phase;

    // mirror Bucket-1 + roundtable agent lifecycle into the WING
    if (stage === "bucket1") {
      if (phase === "start") setCardStatus(ev.agent_id, "active", ev);
      else if (phase === "done") setCardStatus(ev.agent_id, ev.status === "ok" ? "ok" : "abstain", ev);
    } else if (stage === "roundtable") {
      const id = "rt::" + (ev.agent_id || "partner");
      ensurePersonaCard(id, ev);
      if (phase === "done") setPersonaCard(id, ev);
    }

    // top-level steps: plan / flags / synthesis
    if (stage === "plan" || stage === "flags" || stage === "synthesis") {
      let node = trace.tops[stage];
      if (!node) {
        node = el("div", "trace-top",
          `<span class="tt-status"><span class="spinner"></span></span><div class="tt-body">` +
          `<div class="tt-name" data-name></div><div class="tt-detail" data-detail></div></div>`);
        traceTree.appendChild(node);
        trace.tops[stage] = node;
      }
      node.querySelector("[data-name]").textContent = topName(stage);
      if (phase === "done") {
        node.classList.add("done");
        node.querySelector(".tt-status").textContent = "✓";
        node.querySelector("[data-detail]").innerHTML = topDetail(stage, ev);
      }
      scrollRight();
      return;
    }
    // grouped rows: bucket1 / roundtable
    const group = ensureGroup(stage);
    const key = stage + "::" + (ev.agent_id || "");
    let row = trace.rows[key];
    if (!row) {
      row = el("div", "trace-row running",
        `<span class="tr-status"><span class="spinner"></span></span>` +
        `<div class="tr-body"><div class="tr-name">${esc(rowName(stage, ev))}</div>` +
        `<div class="tr-detail" data-detail></div></div>`);
      group.appendChild(row);
      trace.rows[key] = row;
    }
    if (phase === "done") {
      const ok = ev.status === "ok";
      row.className = "trace-row " + (ok ? "ok" : "abstain");
      row.querySelector(".tr-status").textContent = ok ? "✓" : "⚠";
      row.querySelector("[data-detail]").innerHTML = rowDetail(stage, ev);
    }
    // group meta = running tally
    const meta = group.querySelector("[data-meta]");
    const done = group.querySelectorAll(".trace-row.ok, .trace-row.abstain").length;
    const all = group.querySelectorAll(".trace-row").length;
    if (meta) meta.textContent = `${done}/${all}`;
    scrollRight();
  }
  function topName(stage) {
    return { plan: "Plan — scoping the engagement", flags: "Flags — VETO / DIVERGENCE",
             synthesis: "Synthesis — the recommendation" }[stage] || stage;
  }
  function topDetail(stage, ev) {
    if (stage === "plan")
      return esc(`${ev.disease || "—"} · ${ev.modality || "—"} · ${(ev.agents || []).length} fact agents · ${(ev.panel || []).length} panel`);
    if (stage === "flags")
      return `<span class="chip flag VETO">⛔ ${ev.n_veto || 0} VETO</span> ` +
             `<span class="chip flag DIVERGENCE">⚠ ${ev.n_divergence || 0} DIVERGENCE</span> ` +
             `<span class="chip">${ev.n_known_unknowns || 0} known-unknown(s)</span>`;
    if (stage === "synthesis")
      return esc(`${ev.recommendation || ""} (confidence: ${ev.confidence || "—"})`);
    return "";
  }
  function rowName(stage, ev) {
    return stage === "bucket1" ? agentName(ev.agent_id) : (ev.agent_id || "persona");
  }
  function rowDetail(stage, ev) {
    const t = ev.elapsed_s != null ? `<span class="tr-timing">${ev.elapsed_s}s</span>` : "";
    if (stage === "bucket1") {
      if (ev.status === "ok") return `<span>${ev.n_facts || 0} fact(s)</span> ${provChip(ev.provenance)} ${t}`;
      const err = ev.error ? ` — ${esc(ev.error)}` : "";
      return `<span>⚠ ${esc(ev.status || "abstained")}${err}</span> ${provChip(ev.provenance)} ${t}`;
    }
    if (stage === "roundtable") {
      if (ev.status === "ok") {
        const cv = ev.conviction != null ? ` · conviction ${ev.conviction}` : "";
        return `<span>${esc(ev.stance || "?")}${esc(cv)}</span> ${t}`;
      }
      return `<span>⚠ abstained (${esc(ev.status || "?")})</span> ${t}`;
    }
    return t;
  }
  function provChip(prov) {
    if (!prov) return "";
    return `<span class="chip prov ${provClass(prov)}">${esc(prov)}</span>`;
  }

  // ── roundtable persona cards in the wing ─────────────────────
  function ensurePersonaCard(id, ev) {
    if (wing.cards[id]) return wing.cards[id];
    const cat = ensureCat("Roundtable Partners");
    const body = cat.querySelector("[data-body]");
    const card = el("div", "agent-card");
    card.dataset.agent = id;
    card.innerHTML =
      `<div class="ac-head"><span class="ac-dot active" data-dot></span>` +
      `<span class="ac-title" data-title>${esc(ev.agent_id || "partner")}</span><span class="ac-chev">›</span></div>` +
      `<div class="ac-detail"><div class="ac-task" data-task>deliberating…</div>` +
      `<div class="ac-brief" data-brief></div></div>`;
    body.appendChild(card);
    wing.cards[id] = card;
    return card;
  }
  function setPersonaCard(id, ev) {
    const card = wing.cards[id]; if (!card) return;
    const dot = card.querySelector("[data-dot]");
    const ok = ev.status === "ok";
    dot.className = "ac-dot " + (ok ? "ok" : "abstain");
    const task = card.querySelector("[data-task]");
    if (ok) {
      const cv = ev.conviction != null ? ` · conviction ${ev.conviction}` : "";
      task.innerHTML = `✓ ${esc(ev.stance || "?")}${esc(cv)}`;
    } else {
      task.innerHTML = `⚠ abstained (${esc(ev.status || "?")})`;
    }
    updateCatStat("Roundtable Partners");
  }

  // ============================================================================
  // RESULT — fill EVIDENCE rows, attach agent sources, render the CENTER
  // ============================================================================
  function chip(cls, label) { return `<span class="${cls}">${esc(label)}</span>`; }
  function planeIcon(plane) { return plane === "internal" ? "🔒" : "🌐"; }

  // Attribute a fact to an agent id by its provenance (+ a source heuristic for the
  // shared `semantic-web` provenance). Returns an agent id or "".
  const PROV_TO_AGENT = {
    "moat-real": "internal-science-lead", "robyn-scs": "robyn-scs",
    "emet-live": "emet-runner", "qmodels": "q-models-runner", "boltz": "boltz",
    "gnomad": "gnomad-constraint", "gtex": "gtex-expression", "interpro": "interpro-domains",
    "gprofiler": "geneset-enrichment", "aso-tox": "aso-tox",
    "fda-primary": "fda-institutional-memory", "corpus": "fda-institutional-memory",
  };
  function attributeFact(f) {
    const p = String(f.provenance || "").toLowerCase();
    if (PROV_TO_AGENT[p]) return PROV_TO_AGENT[p];
    if (p === "semantic-web") {
      const s = (String(f.source || "") + " " + String(f.value || "")).toLowerCase();
      if (/patent|uspto|google patents|orange book|composition|method-of-use|\bwo\d|\bus\d/.test(s)) return "patent-ip";
      if (/clinicaltrials|\bnct\d|trial|phase [123]|endpoint/.test(s)) return "clinical-trial-registry";
      if (/fda|ema|pmda|mhra|designation|fast track|orphan/.test(s)) return "global-regulatory-divergence";
      if (/faers|openfda|adverse|boxed warning|label|safety/.test(s)) return "post-market-safety";
      if (/payer|cms|coverage|reimburs|formular/.test(s)) return "payer";
      if (/\$|series [a-d]|raise|sec |edgar|8-k|10-q|runway|funding/.test(s)) return "financial";
      if (/cmc|manufactur|gmp|supply/.test(s)) return "manufacturing-cmc";
      if (/advocacy|patient|community|caregiver/.test(s)) return "patient-advocacy";
      if (/kol|opinion leader|social|forum|congress|abstract/.test(s)) return "kol-social";
      if (/dea|schedul|controlled substance/.test(s)) return "dea-scheduling";
      if (/policy|legislat|medicaid|medicare act/.test(s)) return "policy-legislative";
      return "global-regulatory-divergence"; // a seated semantic agent — never unattributed
    }
    return "";
  }

  function renderEvidence(result) {
    const via = result._via === "replay" || result._replay ? "replay" : "";
    const dossier = (result.discover && result.discover.dossier) || [];
    evidenceBody.innerHTML = "";
    if (!dossier.length) {
      evidenceBody.appendChild(el("div", "hint", "No cited facts in this run (the firm abstained where it lacked evidence — never fabricated)."));
      evidenceMeta.textContent = "0 facts";
      return;
    }
    let nInt = 0, nExt = 0;
    // internal plane first (the moat), then external — Hayes groups by plane.
    const ordered = dossier.slice().sort((a, b) =>
      (a.plane === "internal" ? 0 : 1) - (b.plane === "internal" ? 0 : 1));
    ordered.forEach((f) => {
      const plane = f.plane === "internal" ? "internal" : "external";
      if (plane === "internal") nInt++; else nExt++;
      const agentId = attributeFact(f);
      const row = el("div", "src-row " + plane);
      const ref = [f.source, f.provenance].filter(Boolean).join(" · ");
      row.innerHTML =
        `<div class="src-text">${esc(f.value || "(no value)")}</div>` +
        `<div class="src-meta">` +
        `<span class="src-plane">${planeIcon(plane)}</span>` +
        (f.tier ? `<span class="src-tier">${esc(f.tier)}</span>` : "") +
        `<span class="chip prov ${provClass(f.provenance, via)}">${esc(f.provenance || "—")}</span>` +
        (f.flag ? chip("chip flag " + esc(f.flag), f.flag) : "") +
        `<span class="src-ref" title="${esc(ref)}">${esc(f.source || "")}</span>` +
        `</div>`;
      if (agentId) {
        row.style.cursor = "pointer";
        row.title = "↳ " + agentName(agentId);
        row.addEventListener("click", () => openAgent(agentId));
      }
      evidenceBody.appendChild(row);
    });
    evidenceMeta.textContent = `🔒 ${nInt} · 🌐 ${nExt}`;
  }

  // Attach each fact to its agent card as a source list (so the wing cards show what
  // each subagent actually surfaced — Hayes's per-agent "sources").
  function attachAgentSources(result) {
    const via = result._via === "replay" || result._replay ? "replay" : "";
    const dossier = (result.discover && result.discover.dossier) || [];
    const byAgent = {};
    dossier.forEach((f) => {
      const id = attributeFact(f); if (!id) return;
      (byAgent[id] = byAgent[id] || []).push(f);
    });
    // also fold in the engine's agent list so abstained agents still get a card + task
    const agents = (result.discover && result.discover.agents) || [];
    agents.forEach((a) => {
      const card = ensureCard(a.id);
      const dot = card.querySelector("[data-dot]");
      // only set from the result if the live stream didn't already (e.g. replay path)
      if (dot.classList.contains("active")) setCardStatus(a.id, a.status === "ok" ? "ok" : "abstain", a);
    });
    Object.keys(byAgent).forEach((id) => {
      const card = ensureCard(id);
      const wrap = card.querySelector("[data-srcwrap]");
      const facts = byAgent[id];
      wrap.innerHTML = `<div class="ac-srch">Sources · ${facts.length}</div>` +
        facts.slice(0, 8).map((f) =>
          `<div class="ac-src"><span class="ac-src-tier">${esc(f.tier || "—")}</span>` +
          `<span>${esc((f.value || f.source || "").slice(0, 130))}</span></div>`).join("") +
        (facts.length > 8 ? `<div class="ac-src"><span class="ac-src-tier">+</span><span>${facts.length - 8} more</span></div>` : "");
      // a one-line brief if the card task is still generic
      const brief = card.querySelector("[data-brief]");
      if (brief && !brief.innerHTML) {
        const plane = facts[0].plane === "internal" ? "internal (🔒 Quiver moat)" : "external (🌐 public)";
        brief.innerHTML = `<p>Surfaced ${facts.length} cited fact(s) on the ${plane} plane, provenance <code>${esc(facts[0].provenance || "—")}</code>.</p>`;
      }
    });
    updateAllCatStats();
    // wing summary — count both from the DOM so the denominator matches the rendered cards
    const total = agentTree.querySelectorAll(".agent-card").length;
    const ok = agentTree.querySelectorAll(".agent-card [data-dot].ok").length;
    wingMeta.textContent = `${ok}/${total} answered`;
  }
  function updateAllCatStats() { Object.keys(wing.cats).forEach(updateCatStat); }

  // ── the center answer ────────────────────────────────────────
  function renderAnswer(result, loadEl) {
    const via = result._via;
    const sim = !!result._simulated;
    const synth = result.synthesize || {};
    const consult = result.consult || {};
    const flags = (result.discover && result.discover.flags) || {};
    const block = el("div", "ai-block");

    // simulated / captured / partial banners (honesty)
    if (sim) {
      block.appendChild(el("div", "sim-banner",
        `<b>🧪 Simulated-models run.</b> Real moat, EMET PMIDs, seams and Q-Models — but the roundtable ` +
        `verdicts and any claude fact-agent reasoning are <b>simulated</b> (labeled <code>simulated</code>), not real model output.`));
    } else if (via === "replay" || result._replay) {
      block.appendChild(el("div", "sim-banner",
        `<b>◆ Captured run.</b> A frozen real engagement (real moat + real EMET PMIDs + the live spread), replayed $0 — provenance/tier/flags verbatim.`));
    }
    const status = (result.discover && result.discover.status) || "";
    const ku = (flags.KNOWN_UNKNOWNS || []).length;
    if (status && status !== "complete") {
      block.appendChild(el("div", "partial-banner",
        `⚠ ${esc(status)}${ku ? ` — ${ku} known-unknown${ku > 1 ? "s" : ""}` : ""}`));
    }

    // synthesis — with an ATTRIBUTED-FINDINGS row (one finding per contributing agent)
    const synthEl = el("div", "synthesis");
    synthEl.innerHTML =
      `<div class="synthesis-lbl">⬩ Synthesis — the recommendation</div>` +
      `<div class="synthesis-rec">${esc(synth.recommendation || "—")}</div>` +
      `<div class="synthesis-conf">Confidence: <b>${esc(synth.confidence || "—")}</b></div>` +
      (synth.proposed_experiment
        ? `<div class="experiment"><div class="ex-lbl">Proposed experiment</div>${esc(synth.proposed_experiment)}</div>` : "");
    block.appendChild(synthEl);

    const findingsRow = buildFindingsRow(result);
    if (findingsRow) block.appendChild(findingsRow);

    // VETO / DIVERGENCE callouts (the alpha — surfaced, not reconciled)
    (flags.VETO || []).length && block.appendChild(flagCallout("VETO", "⛔ VETO — the roundtable adjudicates (not a silent kill)", flags.VETO));
    (flags.DIVERGENCE || []).length && block.appendChild(flagCallout("DIVERGENCE", "⚠ DIVERGENCE — internal vs external, surfaced not reconciled (often the alpha)", flags.DIVERGENCE));

    // the roundtable spread
    const round = consult.round2 && consult.round2.length ? consult.round2 : (consult.round1 || []);
    const roundLbl = consult.round2 && consult.round2.length ? "round 2 (rebuttal)" : "round 1";
    if (round.length) {
      block.appendChild(el("div", "sec-head",
        `The spread <span class="count">— ${round.length} partner${round.length > 1 ? "s" : ""}, no forced consensus · ${roundLbl}</span>`));
      const spread = el("div", "spread");
      round.forEach((v) => spread.appendChild(verdictCard(v, via)));
      block.appendChild(spread);
    }

    loadEl.innerHTML = "";
    loadEl.appendChild(block);
  }

  // attributed findings: one clickable finding per agent that contributed facts; click
  // opens + highlights that agent's card in the wing (Hayes's finding↔agent linkage).
  function buildFindingsRow(result) {
    const dossier = (result.discover && result.discover.dossier) || [];
    const counts = {};
    dossier.forEach((f) => { const id = attributeFact(f); if (id) counts[id] = (counts[id] || 0) + 1; });
    const ids = Object.keys(counts);
    if (!ids.length) return null;
    const row = el("div", "ai-body");
    row.style.marginTop = "2px";
    row.innerHTML = `<div class="sec-head">Cited by <span class="count">— click a finding to jump to the agent that surfaced it</span></div>` +
      `<p>` + ids.map((id) =>
        `<span class="finding" data-agent="${esc(id)}" tabindex="0" role="button">` +
        `${esc(agentName(id))} <span style="opacity:.6">(${counts[id]})</span>` +
        `<span class="finding-tip">open ${esc(agentName(id))} in the wing</span></span>`).join("&nbsp; ") +
      `</p>`;
    return row;
  }

  function flagCallout(level, label, items) {
    return el("div", "flag-callout " + level,
      `<div class="fc-lbl">${esc(label)}</div><ul>` + items.map((x) => `<li>${esc(x)}</li>`).join("") + `</ul>`);
  }

  function verdictCard(v, via) {
    const ok = v.status === "ok";
    const cls = ok ? stanceClass(v.stance) : "abstain";
    const c = el("div", "verdict " + cls);
    const conv = (ok && v.conviction != null) ? `<span class="v-conviction">conviction ${esc(v.conviction)}</span>` : "";
    const claims = (v.fact_claims || []).length
      ? `<div class="v-claims">${v.fact_claims.map((f) => chip("chip", String(f).slice(0, 70))).join("")}</div>` : "";
    c.innerHTML =
      `<div class="verdict-top"><span class="v-persona">${esc(v.persona || "partner")}</span>` +
      (v.stance ? `<span class="v-stance">${esc(v.stance)}</span>` : "") +
      (v.provenance ? provChip(v.provenance) : "") + conv + `</div>` +
      `<div class="v-rationale">${esc(v.rationale || (ok ? "" : "abstained"))}</div>` + claims;
    return c;
  }

  // findings click/keyboard → open the agent in the wing
  msgList.addEventListener("click", (e) => {
    const f = e.target.closest(".finding");
    if (f && f.dataset.agent) openAgent(f.dataset.agent);
  });
  msgList.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    const f = e.target.closest(".finding");
    if (f && f.dataset.agent) { e.preventDefault(); openAgent(f.dataset.agent); }
  });

  // ============================================================================
  // SUBMIT — POST /api/run and read the SSE stream
  // ============================================================================
  async function send() {
    const text = chatInput.value.trim();
    const profile = profileSel.value;
    if ((!text && profile !== "replay") || busy) return;
    busy = true; sendBtn.disabled = true;

    if (!activated) {
      emptyState.style.display = "none";
      threadInner.style.minHeight = "unset";
      msgList.style.display = "flex";
      chatCol.classList.add("active");
      activated = true;
    }
    chatInput.value = ""; chatInput.style.height = "auto";

    const shownQ = text || "(replay captured TSC2 run)";
    msgList.appendChild(el("div", "msg-user", `<div class="user-bubble">${esc(shownQ)}</div>`));
    const loadEl = el("div", "msg-ai",
      `<div class="typing"><span class="t-dot"></span><span class="t-dot"></span><span class="t-dot"></span>` +
      `<span class="t-label">convening the firm…</span></div>`);
    msgList.appendChild(loadEl);
    scrollThread();

    resetTrace(); resetWing();
    traceStatus.textContent = "running";

    try {
      const resp = await fetch("/api/run", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: text, profile, model: modelSel.value }),
      });
      if (!resp.ok || !resp.body) throw new Error("HTTP " + resp.status);
      await readSSE(resp.body, loadEl);
    } catch (e) {
      loadEl.innerHTML = `<div class="partial-banner">⚠ The firm could not be convened (${esc(e.message)}). No answer is fabricated.</div>`;
      traceStatus.textContent = "error";
    } finally {
      busy = false; sendBtn.disabled = false; scrollThread();
    }
  }

  // Parse an SSE stream from a ReadableStream, dispatching each frame.
  async function readSSE(body, loadEl) {
    const reader = body.getReader();
    const dec = new TextDecoder();
    let buf = "", result = null;
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let idx;
      while ((idx = buf.indexOf("\n\n")) >= 0) {
        const frame = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        const { event, data } = parseFrame(frame);
        if (!event) continue;
        if (event === "progress") {
          handleProgress(data);
          const lbl = loadEl.querySelector(".t-label");
          if (lbl) lbl.textContent = typingLabel(data);
        } else if (event === "result") {
          result = data;
          // Show which model was actually used (honest — from result._model, never fabricated).
          if (result._model) {
            modelBadge.textContent = "model: " + result._model;
            modelBadge.style.display = "";
          } else {
            modelBadge.style.display = "none";
          }
          renderEvidence(result);
          attachAgentSources(result);
          renderAnswer(result, loadEl);
        } else if (event === "error") {
          loadEl.innerHTML = `<div class="partial-banner">⚠ ${esc((data && data.error) || "run failed")} — no answer is fabricated.</div>`;
        } else if (event === "done") {
          traceStatus.textContent = result ? "complete" : "done";
          if (result && result.engagement_id) traceMeta.textContent = result.engagement_id;
        }
      }
    }
    return result;
  }
  function typingLabel(ev) {
    if (ev.stage === "plan") return "scoping the engagement…";
    if (ev.stage === "bucket1") return `gathering facts — ${agentName(ev.agent_id)}…`;
    if (ev.stage === "flags") return "checking VETO / DIVERGENCE…";
    if (ev.stage === "roundtable") return `roundtable — ${ev.agent_id || "partner"}…`;
    if (ev.stage === "synthesis") return "writing the synthesis…";
    return "convening the firm…";
  }
  function parseFrame(frame) {
    let event = null; const dataLines = [];
    for (const line of frame.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) dataLines.push(line.slice(5).replace(/^ /, ""));
    }
    let data = null;
    if (dataLines.length) {
      try { data = JSON.parse(dataLines.join("\n")); } catch (e) { data = dataLines.join("\n"); }
    }
    return { event, data };
  }

  // ── wiring ───────────────────────────────────────────────────
  sendBtn.addEventListener("click", send);
  chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  });
  chatInput.addEventListener("input", function () {
    this.style.height = "auto"; this.style.height = Math.min(this.scrollHeight, 160) + "px";
  });
  document.querySelectorAll(".sug").forEach((btn) => {
    btn.addEventListener("click", () => {
      chatInput.value = btn.dataset.q; chatInput.focus();
      chatInput.dispatchEvent(new Event("input"));
    });
  });
})();
