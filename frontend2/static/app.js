/* ============================================================================
   Sapphire frontend2 — vanilla JS, no framework.
   On submit: POST /api/run, read the Server-Sent Events stream, render the trace
   step-tree LIVE as `progress` events arrive, then populate the 3 panes from the
   final `result` dossier (the run_live contract dict).
   Honesty markers (● REAL / 🧪 simulated / ◆ CAPTURED) are derived from each fact's
   provenance verbatim — never relabeled, never fabricated.
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
  const traceTree = $("traceTree"), traceStatus = $("traceStatus");
  const planeInternal = $("planeInternal"), planeInternalBody = $("planeInternalBody");
  const planeExternal = $("planeExternal"), planeExternalBody = $("planeExternalBody");
  const rosterBody = $("rosterBody"), rosterMeta = $("rosterMeta"), planeSummary = $("planeSummary");

  let busy = false, activated = false;

  // ── helpers ───────────────────────────────────────────────────
  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
  function el(tag, cls, html) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    return e;
  }
  function scrollThread() { thread.scrollTop = thread.scrollHeight; }
  function scrollTrace() { const s = traceTree.parentElement; if (s) s.scrollTop = s.scrollHeight; }

  // Honesty class for a provenance string → ● REAL / 🧪 simulated / ◆ CAPTURED.
  // Real backends: moat-real, emet-live, aso-tox, boltz, gnomad, gtex, interpro, corpus, …
  function provClass(prov, via) {
    const p = String(prov || "").toLowerCase();
    if (p === "simulated") return "sim";
    if (via === "replay" || p === "captured") return "cap";
    if (p === "mock") return "sim"; // mock is a stand-in; mark it, never as REAL
    return "real";
  }
  function tierClass(tier) {
    const t = String(tier || "").toUpperCase();
    return (t === "T1" || t === "T2" || t === "T3") ? "tier-" + t : "";
  }
  // map a stance word → a verdict color class
  function stanceClass(stance) {
    return String(stance || "").toLowerCase().replace(/[^a-z]/g, "");
  }

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
  // LIVE TRACE — built from streamed `progress` events
  // ============================================================================
  const GROUP = {
    bucket1: { icon: "🧬", name: "Bucket 1 — cited fact dossier" },
    roundtable: { icon: "👥", name: "Bucket 2 — the persona roundtable (the spread)" },
  };
  const AGENT_LABEL = {
    "internal-science-lead": "Internal moat (Quiver CNS_DFP)",
    "emet-runner": "EMET — live BenchSci",
    "q-models-runner": "Q-Models launchpad",
    "fda-institutional-memory": "FDA institutional memory ⛔",
    "patent-ip": "Patent / IP ⛔",
    "global-regulatory-divergence": "Global regulatory divergence",
    "clinical-trial-registry": "Clinical-trial registry",
    "post-market-safety": "Post-market safety",
    "payer": "Payer / reimbursement",
    "financial": "Financial",
    "aso-tox": "ASO acute-tox screen",
    "boltz": "Boltz structure / binding",
    "gnomad-constraint": "gnomAD constraint",
    "gtex-expression": "GTEx expression",
    "interpro-domains": "InterPro domains",
    "geneset-enrichment": "g:Profiler enrichment",
    "robyn-scs": "robyn_scs connectivity",
  };
  function agentLabel(id) { return AGENT_LABEL[id] || id || "agent"; }

  // Trace runtime state — keyed nodes so we can flip running→done in place.
  let trace = null;
  function resetTrace() {
    traceTree.innerHTML = "";
    trace = { groups: {}, rows: {}, tops: {} };
  }
  function ensureGroup(stage) {
    if (trace.groups[stage]) return trace.groups[stage];
    const g = GROUP[stage] || { icon: "•", name: stage };
    const wrap = el("div", "trace-group");
    wrap.innerHTML =
      `<div class="tg-head"><span class="tg-icon">${g.icon}</span><span>${esc(g.name)}</span>` +
      `<span class="tg-meta" data-meta></span></div>`;
    traceTree.appendChild(wrap);
    trace.groups[stage] = wrap;
    return wrap;
  }
  function handleProgress(ev) {
    const stage = ev.stage, phase = ev.phase;
    // top-level steps: plan / flags / synthesis
    if (stage === "plan" || stage === "flags" || stage === "synthesis") {
      let node = trace.tops[stage];
      if (!node) {
        node = el("div", "trace-top");
        node.innerHTML = `<span class="tt-status">…</span><div class="tt-body">` +
          `<div class="tt-name" data-name></div><div class="tt-detail" data-detail></div></div>`;
        traceTree.appendChild(node);
        trace.tops[stage] = node;
      }
      node.querySelector("[data-name]").textContent = topName(stage);
      if (phase === "done") {
        node.querySelector(".tt-status").textContent = "✓";
        node.querySelector("[data-detail]").innerHTML = topDetail(stage, ev);
      }
      scrollTrace();
      return;
    }
    // grouped rows: bucket1 / roundtable
    const group = ensureGroup(stage);
    const key = stage + "::" + (ev.agent_id || "");
    let row = trace.rows[key];
    if (!row) {
      row = el("div", "trace-row running");
      row.innerHTML =
        `<span class="tr-status"><span class="spinner"></span></span>` +
        `<div class="tr-body"><div class="tr-name">${esc(rowName(stage, ev))}</div>` +
        `<div class="tr-detail" data-detail></div></div>`;
      group.appendChild(row);
      trace.rows[key] = row;
    }
    if (phase === "done") {
      const ok = ev.status === "ok";
      const cls = ok ? "ok" : "abstain";
      row.className = "trace-row " + cls;
      row.querySelector(".tr-status").textContent = ok ? "✓" : "⚠";
      row.querySelector("[data-detail]").innerHTML = rowDetail(stage, ev);
    }
    scrollTrace();
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
    return stage === "bucket1" ? agentLabel(ev.agent_id) : (ev.agent_id || "persona");
  }
  function rowDetail(stage, ev) {
    const t = ev.elapsed_s != null ? `<span class="tr-timing">${ev.elapsed_s}s</span>` : "";
    if (stage === "bucket1") {
      if (ev.status === "ok")
        return `<span>${ev.n_facts || 0} fact(s)</span> ${provChip(ev.provenance)} ${t}`;
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
    const c = provClass(prov);
    return `<span class="chip prov ${c}">${esc(prov)}</span>`;
  }

  // ============================================================================
  // PANES — populated from the final result dict
  // ============================================================================
  function chip(cls, label) { return `<span class="${cls}">${esc(label)}</span>`; }

  function findingCard(f, via) {
    const plane = f.plane === "internal" ? "internal" : "external";
    const pc = provClass(f.provenance, via);
    const chips = [
      f.tier ? chip("chip tier " + tierClass(f.tier), f.tier) : "",
      f.provenance ? chip("chip prov " + pc, f.provenance) : "",
      chip("chip plane " + plane, plane === "internal" ? "🔒 internal" : "🌐 external"),
      f.flag ? chip("chip flag " + esc(f.flag), f.flag) : "",
    ].join("");
    const detail = [
      f.field ? `<div class="kv"><span class="k">field</span><span>${esc(f.field)}</span></div>` : "",
      f.source ? `<div class="kv"><span class="k">source</span><span>${esc(f.source)}</span></div>` : "",
      f.confidence != null ? `<div class="kv"><span class="k">confidence</span><span>${esc(f.confidence)}</span></div>` : "",
      `<div class="kv"><span class="k">provenance</span><span>${esc(f.provenance || "—")}</span></div>`,
    ].join("");
    const card = el("div", "finding " + plane);
    card.innerHTML = `<div class="finding-value">${esc(f.value)}</div>` +
      `<div class="finding-meta">${chips}</div>` +
      `<div class="finding-detail">${detail}</div>`;
    card.addEventListener("click", () => card.classList.toggle("open"));
    return card;
  }

  function renderPlanes(result) {
    const via = result._via === "replay" || result._replay ? "replay" : "";
    const dossier = (result.discover && result.discover.dossier) || [];
    const internal = dossier.filter((f) => f.plane === "internal");
    const external = dossier.filter((f) => f.plane !== "internal");

    planeInternalBody.innerHTML = "";
    planeExternalBody.innerHTML = "";
    if (internal.length) {
      planeInternal.hidden = false;
      internal.forEach((f) => planeInternalBody.appendChild(findingCard(f, via)));
      planeInternal.querySelector(".plane-meta").textContent = `${internal.length} finding(s) · private`;
    } else { planeInternal.hidden = true; }
    if (external.length) {
      planeExternal.hidden = false;
      external.forEach((f) => planeExternalBody.appendChild(findingCard(f, via)));
      planeExternal.querySelector(".plane-meta").textContent = `${external.length} finding(s) · public`;
    } else { planeExternal.hidden = true; }

    planeSummary.textContent = `🔒 ${internal.length} · 🌐 ${external.length}`;
  }

  function renderRoster(result) {
    const agents = (result.discover && result.discover.agents) || [];
    rosterBody.innerHTML = "";
    if (!agents.length) {
      rosterBody.appendChild(el("div", "hint", "No agents reported."));
      rosterMeta.textContent = "0 agents";
      return;
    }
    let nOk = 0;
    agents.forEach((a) => {
      const ok = a.status === "ok";
      if (ok) nOk++;
      const dotCls = ok ? "ok" : "abstain";
      const row = el("div", "agent-row");
      row.innerHTML = `<span class="a-dot ${dotCls}"></span><div>` +
        `<div class="a-name">${esc(agentLabel(a.id))}</div>` +
        `<div class="a-note">${ok ? "✓" : "⚠"} ${esc(a.status)} ${provChip(a.provenance)}</div></div>`;
      rosterBody.appendChild(row);
    });
    rosterMeta.textContent = `${nOk}/${agents.length} answered`;
  }

  function renderAnswer(result, loadEl) {
    const via = result._via;
    const sim = !!result._simulated;
    const synth = result.synthesize || {};
    const consult = result.consult || {};
    const flags = (result.discover && result.discover.flags) || {};
    const block = el("div", "ai-block");

    // simulated banner
    if (sim) {
      block.appendChild(el("div", "sim-banner",
        `<b>🧪 Simulated-models run.</b> Real moat, EMET PMIDs, seams and Q-Models — but the roundtable ` +
        `verdicts and any claude fact-agent reasoning are <b>simulated</b> (labeled <code>simulated</code>), ` +
        `not real model output.`));
    }
    // partial-run banner
    const status = (result.discover && result.discover.status) || "";
    const ku = (flags.KNOWN_UNKNOWNS || []).length;
    if (status && status !== "complete") {
      block.appendChild(el("div", "partial-banner",
        `⚠ Partial run — status: ${esc(status)}${ku ? ` (${ku} known-unknown${ku > 1 ? "s" : ""})` : ""}`));
    }

    // synthesis
    const synthEl = el("div", "synthesis");
    synthEl.innerHTML =
      `<div class="synthesis-lbl">⬩ Synthesis — the recommendation</div>` +
      `<div class="synthesis-rec">${esc(synth.recommendation || "—")}</div>` +
      `<div class="synthesis-conf">Confidence: <b>${esc(synth.confidence || "—")}</b></div>` +
      (synth.proposed_experiment
        ? `<div class="experiment"><div class="ex-lbl">Proposed experiment</div>${esc(synth.proposed_experiment)}</div>`
        : "");
    block.appendChild(synthEl);

    // VETO / DIVERGENCE callouts (the alpha — surfaced, not reconciled)
    (flags.VETO || []).length && block.appendChild(flagCallout("VETO", "⛔ VETO — the roundtable adjudicates (not a silent kill)", flags.VETO));
    (flags.DIVERGENCE || []).length && block.appendChild(flagCallout("DIVERGENCE", "⚠ DIVERGENCE — internal vs external, surfaced not reconciled (often the alpha)", flags.DIVERGENCE));

    // roundtable spread
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

  function flagCallout(level, label, items) {
    const c = el("div", "flag-callout " + level);
    c.innerHTML = `<div class="fc-lbl">${esc(label)}</div><ul>` +
      items.map((x) => `<li>${esc(x)}</li>`).join("") + `</ul>`;
    return c;
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

  // ============================================================================
  // SUBMIT — POST /api/run and read the SSE stream
  // ============================================================================
  async function send() {
    const text = chatInput.value.trim();
    const profile = profileSel.value;
    if ((!text && profile !== "replay") || busy) return;
    busy = true;
    sendBtn.disabled = true;

    if (!activated) {
      emptyState.style.display = "none";
      threadInner.style.minHeight = "unset";
      msgList.style.display = "flex";
      chatCol.classList.add("active");
      activated = true;
    }

    chatInput.value = "";
    chatInput.style.height = "auto";

    const shownQ = text || "(replay captured TSC2 run)";
    msgList.appendChild(el("div", "msg-user", `<div class="user-bubble">${esc(shownQ)}</div>`));
    const loadEl = el("div", "msg-ai",
      `<div class="typing"><span class="t-dot"></span><span class="t-dot"></span><span class="t-dot"></span>` +
      `<span class="t-label">convening the firm…</span></div>`);
    msgList.appendChild(loadEl);
    scrollThread();

    resetTrace();
    traceStatus.textContent = "running";

    try {
      const resp = await fetch("/api/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: text, profile: profile }),
      });
      if (!resp.ok || !resp.body) throw new Error("HTTP " + resp.status);
      await readSSE(resp.body, loadEl);
    } catch (e) {
      loadEl.innerHTML = `<div class="partial-banner">⚠ The firm could not be convened (${esc(e.message)}). ` +
        `No answer is fabricated.</div>`;
      traceStatus.textContent = "error";
    } finally {
      busy = false;
      sendBtn.disabled = false;
      scrollThread();
    }
  }

  // Parse a Server-Sent Events stream from a ReadableStream.
  async function readSSE(body, loadEl) {
    const reader = body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    let result = null, lastTyping = "convening the firm…";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      // SSE frames are separated by a blank line.
      let idx;
      while ((idx = buf.indexOf("\n\n")) >= 0) {
        const frame = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        const { event, data } = parseFrame(frame);
        if (!event) continue;
        if (event === "open") {
          // nothing to render yet; the badge already reflects the profile
        } else if (event === "progress") {
          handleProgress(data);
          // keep the center "typing" label in step with the live trace
          lastTyping = typingLabel(data);
          const lbl = loadEl.querySelector(".t-label");
          if (lbl) lbl.textContent = lastTyping;
        } else if (event === "result") {
          result = data;
          renderPlanes(result);
          renderRoster(result);
          renderAnswer(result, loadEl);
        } else if (event === "error") {
          loadEl.innerHTML = `<div class="partial-banner">⚠ ${esc((data && data.error) || "run failed")} — ` +
            `no answer is fabricated.</div>`;
        } else if (event === "done") {
          traceStatus.textContent = result ? "complete" : "done";
        }
      }
    }
    return result;
  }

  function typingLabel(ev) {
    if (ev.stage === "plan") return "scoping the engagement…";
    if (ev.stage === "bucket1") return `gathering facts — ${agentLabel(ev.agent_id)}…`;
    if (ev.stage === "flags") return "checking VETO / DIVERGENCE…";
    if (ev.stage === "roundtable") return `roundtable — ${ev.agent_id || "partner"}…`;
    if (ev.stage === "synthesis") return "writing the synthesis…";
    return "convening the firm…";
  }

  function parseFrame(frame) {
    let event = null;
    const dataLines = [];
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
    this.style.height = "auto";
    this.style.height = Math.min(this.scrollHeight, 160) + "px";
  });
  document.querySelectorAll(".sug").forEach((btn) => {
    btn.addEventListener("click", () => { chatInput.value = btn.dataset.q; chatInput.focus();
      chatInput.dispatchEvent(new Event("input")); });
  });
})();
