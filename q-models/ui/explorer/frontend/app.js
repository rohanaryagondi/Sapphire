/* Quiver Capability Explorer — SPA (vanilla JS, no frameworks, same-origin).
 *
 * Sidebar app: grouped track nav + live filter, command palette (Cmd/Ctrl-K),
 * light/dark theme toggle, hash routing (#/overview, #/t/<id>, #/history,
 * #/report), an overview dashboard of track cards, and the per-track detail
 * with the empirical-verdict panel + a result renderer per score_kind.
 * Backend API (unchanged): /api/meta, /api/tracks, /api/examples/{id},
 * /api/predict/{id}(/batch), /api/history, /api/report, /doc/{path}.
 */

const API = ""; // same-origin

// ---- global state ----
let META = null;
let BADGES = {};
let TRACKS = [];
let TRACK_BY_ID = {};
let active = "overview";       // route key: "overview" | trackId | "history" | "report"
let mode = "single";           // "single" | "batch"
let pendingFill = null;         // inputs to repopulate after a tab switch (History → Load)
let batchState = null;          // last batch response (client-side re-sort / CSV export)
let launchQueue = [];           // Launch Hub: queued jobs [{qid,track,inputs,label,status,result,error}]
let launchSeq = 0;              // monotonic id for queue rows
try { const s = JSON.parse(localStorage.getItem("qx-launch-queue") || "[]"); if (Array.isArray(s)) launchQueue = s; } catch (_) {}
function saveQueue() { try { localStorage.setItem("qx-launch-queue", JSON.stringify(launchQueue)); } catch (_) {} }

// sidebar grouping (frontend concern; robust to unknown ids → "Other")
// Groups hold CONTIGUOUS track numbers so the sidebar medallions read in ascending order
// (01,02,03 · 04,05 · 06,07 · 08,09) — no number jumps.
const GROUPS = [
  { name: "Discovery & Binding", ids: ["family_clustering", "dti", "structure_binding"] },
  { name: "De-risking", ids: ["bbbp", "toxicity"] },
  { name: "Knowledge & Generation", ids: ["kg_hypothesis", "generative"] },
  { name: "Selectivity & Variants", ids: ["selectivity", "variant_effect"] },
];

// ============================================================ dom helpers
function el(tag, attrs = {}, ...kids) {
  const e = document.createElement(tag);
  for (const k in attrs) {
    if (attrs[k] == null || attrs[k] === false) continue;
    if (k === "class") e.className = attrs[k];
    else if (k === "html") e.innerHTML = attrs[k];
    else if (k === "onclick") e.onclick = attrs[k];
    else e.setAttribute(k, attrs[k]);
  }
  for (const c of kids) {
    if (c == null || c === false) continue;
    e.append(c.nodeType ? c : document.createTextNode(c));
  }
  return e;
}
function escapeHtml(s) {
  return (s == null ? "" : String(s)).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}
function trunc(s, n) { s = String(s); return s.length > n ? s.slice(0, n) + "…" : s; }
function badgeMeta(key) { return BADGES[key] || { label: key, desc: "" }; }
function varColor(badge) { return `var(--c-${badge || "low_value"})`; }

// ---- iconography (clean inline SVG, currentColor; no emoji) ----
const SVG_ICONS = {
  overview: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="2.5" y="2.5" width="6" height="6" rx="1.5"/><rect x="11.5" y="2.5" width="6" height="6" rx="1.5"/><rect x="2.5" y="11.5" width="6" height="6" rx="1.5"/><rect x="11.5" y="11.5" width="6" height="6" rx="1.5"/></svg>',
  history: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="10" cy="10" r="7.3"/><path d="M10 5.6V10l3 1.9" stroke-linecap="round"/></svg>',
  report: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><path d="M4 16V9M10 16V4M16 16v-5"/></svg>',
  search: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.7"><circle cx="9" cy="9" r="5.4"/><path d="M16.8 16.8l-3.7-3.7" stroke-linecap="round"/></svg>',
  menu: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><path d="M3 6h14M3 10h14M3 14h14"/></svg>',
  close: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><path d="M5 5l10 10M15 5L5 15"/></svg>',
  sun: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><circle cx="10" cy="10" r="3.5"/><path d="M10 1.6v2M10 16.4v2M1.6 10h2M16.4 10h2M4.1 4.1l1.4 1.4M14.5 14.5l1.4 1.4M15.9 4.1l-1.4 1.4M5.5 14.5l-1.4 1.4"/></svg>',
  moon: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"><path d="M16.5 11.6A6.6 6.6 0 1 1 8.4 3.5a5.1 5.1 0 0 0 8.1 8.1z"/></svg>',
  build: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12.4 5.3a3 3 0 0 0-3.9 3.9l-5 5 1.4 1.4 5-5a3 3 0 0 0 3.9-3.9l-1.8 1.8-1.4-1.4z"/></svg>',
  launch: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.55" stroke-linecap="round" stroke-linejoin="round"><path d="M10 2.5c2.7 1.2 4.3 3.8 4.3 7 0 1.4-.3 2.6-.6 3.4l-2-1.2H8.3l-2 1.2c-.3-.8-.6-2-.6-3.4 0-3.2 1.6-5.8 4.3-7z"/><circle cx="10" cy="8.3" r="1.3"/><path d="M7.7 14.5l-1.5 2.8M12.3 14.5l1.5 2.8M10 14.7v2.8"/></svg>',
  results: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.55" stroke-linecap="round" stroke-linejoin="round"><path d="M3 4.5h14M3 9h9M3 13.5h6"/><path d="M13.2 14.4l1.7 1.7 3-3.4"/></svg>',
};
function svgIcon(name, cls) { const s = el("span", { class: "ic" + (cls ? " " + cls : "") }); s.innerHTML = SVG_ICONS[name] || ""; return s; }
function trackMedallion(n, cls) { return el("span", { class: "numico" + (cls ? " " + cls : "") }, String(n == null ? "" : n).padStart(2, "0")); }
// icon node for any route key (track → numbered medallion; special view → svg)
function keyIcon(key) {
  if (key === "overview") return svgIcon("overview");
  if (key === "launch") return svgIcon("launch");
  if (key === "results") return svgIcon("results");
  if (key === "history") return svgIcon("history");
  if (key === "report") return svgIcon("report");
  const t = TRACK_BY_ID[key];
  return trackMedallion(t ? t.n : "");
}

function copyBtn(text) {
  const b = el("button", { class: "copy-btn", type: "button", title: "Copy" }, "copy");
  b.onclick = async (ev) => {
    ev.stopPropagation();
    try { await navigator.clipboard.writeText(text); b.textContent = "copied"; b.classList.add("done"); }
    catch (_) { b.textContent = "⌘C"; }
    setTimeout(() => { b.textContent = "copy"; b.classList.remove("done"); }, 1100);
  };
  return b;
}

// ============================================================ routing
function keyToHash(key) {
  if (key === "overview") return "#/overview";
  if (key === "launch") return "#/launch";
  if (key === "results") return "#/results";
  if (key === "history") return "#/history";
  if (key === "report") return "#/report";
  return "#/t/" + key;
}
function hashToKey() {
  const h = location.hash || "";
  if (h.startsWith("#/t/")) return decodeURIComponent(h.slice(4));
  if (h === "#/launch") return "launch";
  if (h === "#/results") return "results";
  if (h === "#/history") return "history";
  if (h === "#/report") return "report";
  return "overview";
}
function navigate(key) {
  mode = "single";
  closeNav();
  const nh = keyToHash(key);
  if (location.hash === nh) render();   // same hash → no hashchange event, render directly
  else location.hash = nh;              // else hashchange handler renders
}
window.addEventListener("hashchange", () => { active = hashToKey(); render(); });

// ============================================================ verdict panel
function evidenceLinks(source) {
  return (source || "")
    .split(",").map((s) => s.trim()).filter(Boolean)
    .map((p) => {
      const path = p.split(/\s/)[0];
      return `<a href="/doc/${encodeURI(path)}" target="_blank" rel="noopener">${escapeHtml(p)}</a>`;
    }).join(", ");
}
function relPanel(track, verdict) {
  const v = verdict || (track && track.verdict) || {};
  const badge = (verdict && verdict.badge) || (track && track.badge) || "low_value";
  const bm = badgeMeta(badge);
  const label = (verdict && verdict.badge_label) || bm.label;
  const p = el("div", { class: `rel bl-${badge}` });
  p.append(el("div", {},
    el("span", { class: `badge bg-${badge}` }, label),
    el("span", { class: "headline" }, v.headline || "")));
  if (v.why) p.append(el("div", { class: "why" }, v.why));
  if (v.recommended_use) p.append(el("div", { class: "use", html: `<b>Recommended use:</b> ${escapeHtml(v.recommended_use)}` }));
  if (v.source) p.append(el("div", { class: "src", html: `evidence: ${evidenceLinks(v.source)}` }));
  return p;
}

// ============================================================ sidebar
function groupOf(id) {
  for (const g of GROUPS) if (g.ids.includes(id)) return g.name;
  return "Other";
}
function navItem(key, label, badge) {
  const it = el("button", {
    class: "nav-item" + (key === active ? " active" : ""),
    type: "button", "data-key": key, "data-search": (label + " " + (key || "")).toLowerCase(),
    role: "tab", "aria-selected": key === active ? "true" : "false",
  },
    el("span", { class: "ni-ic" }, keyIcon(key)),
    el("span", { class: "ni-label" }, label),
    badge ? el("span", { class: "ni-dot", style: `background:${varColor(badge)}`, title: badgeMeta(badge).label }) : null);
  it.onclick = () => navigate(key);
  return it;
}
function renderSidebar() {
  const nav = document.getElementById("side-nav");
  nav.innerHTML = "";
  // Launch Hub is the primary entry point — pinned to the top, styled distinctly.
  const launch = navItem("launch", "Launch Hub");
  launch.classList.add("nav-primary");
  nav.append(launch);
  nav.append(navItem("overview", "Overview"));

  // ordered groups, then any leftover tracks
  const placed = new Set();
  for (const g of GROUPS) {
    const items = TRACKS.filter((t) => g.ids.includes(t.id));
    if (!items.length) continue;
    nav.append(el("div", { class: "nav-group-label" }, g.name));
    for (const t of items) { nav.append(navItem(t.id, t.label, t.badge)); placed.add(t.id); }
  }
  const rest = TRACKS.filter((t) => !placed.has(t.id));
  if (rest.length) {
    nav.append(el("div", { class: "nav-group-label" }, "Other"));
    for (const t of rest) nav.append(navItem(t.id, t.label, t.badge));
  }

  nav.append(el("div", { class: "nav-group-label" }, "Workspace"));
  nav.append(navItem("results", "Results"));
  nav.append(navItem("history", "History"));
  nav.append(navItem("report", "Report"));

  // sidebar foot: demo chip + strategic context
  const foot = document.getElementById("side-foot");
  foot.innerHTML = "";
  const liveN = (META && META.live_tracks && META.live_tracks.length) || 0;
  if (liveN) {
    // Some tracks are served by live local fine-tunes (CPU, no AWS).
    foot.append(el("span", { class: "live-chip", title: `Live local fine-tunes: ${(META.live_tracks||[]).join(', ')} (DTI/BBBP/Tox run in-process on CPU). Other tracks are AWS-served / demo.` },
      el("span", { class: "pulse" }), `${liveN} track${liveN === 1 ? "" : "s"} live`));
  } else if (META && META.stubbed) {
    foot.append(el("span", { class: "demo-chip", title: "Model calls are stubbed until EXPLORER_AWS_ENDPOINT or EXPLORER_LOCAL_MODELS is set" },
      el("span", { class: "pulse" }), "Demo mode"));
  }
  applyNavFilter(document.getElementById("nav-filter").value || "");
}
function applyNavFilter(q) {
  q = (q || "").trim().toLowerCase();
  const nav = document.getElementById("side-nav");
  const items = [...nav.querySelectorAll(".nav-item")];
  for (const it of items) {
    const key = it.getAttribute("data-key");
    const always = key === "overview" || key === "launch" || key === "results" || key === "history" || key === "report";
    const hit = !q || always || (it.getAttribute("data-search") || "").includes(q) ||
      ((TRACK_BY_ID[key] && (TRACK_BY_ID[key].best_model || "").toLowerCase().includes(q)));
    it.classList.toggle("is-hidden", !hit);
  }
  // hide a group label whose following track items are all hidden
  const kids = [...nav.children];
  kids.forEach((node, i) => {
    if (!node.classList.contains("nav-group-label")) return;
    let anyVisible = false;
    for (let j = i + 1; j < kids.length; j++) {
      if (kids[j].classList.contains("nav-group-label")) break;
      if (kids[j].classList.contains("nav-item") && !kids[j].classList.contains("is-hidden")) { anyVisible = true; break; }
    }
    node.style.display = anyVisible ? "" : "none";
  });
}

// ============================================================ topbar crumb
function setCrumb(key) {
  const crumb = document.getElementById("crumb");
  crumb.innerHTML = "";
  if (key === "overview") crumb.append(svgIcon("overview", "cr-em"), "Overview");
  else if (key === "launch") crumb.append(svgIcon("launch", "cr-em"), "Launch Hub");
  else if (key === "results") crumb.append(svgIcon("results", "cr-em"), "Results");
  else if (key === "history") crumb.append(svgIcon("history", "cr-em"), "History");
  else if (key === "report") crumb.append(svgIcon("report", "cr-em"), "Capability Report");
  else {
    const t = TRACK_BY_ID[key];
    if (!t) { crumb.append("—"); return; }
    crumb.append(trackMedallion(t.n, "cr-em"), t.label);
  }
}

// ============================================================ render dispatch
function render() {
  // sidebar active states
  for (const it of document.querySelectorAll(".nav-item")) {
    const on = it.getAttribute("data-key") === active;
    it.classList.toggle("active", on);
    it.setAttribute("aria-selected", on ? "true" : "false");
  }
  setCrumb(active);
  updateQueueChip();          // keep the global queue indicator in sync on every page
  const card = document.getElementById("card");
  card.innerHTML = "";
  const view = el("div", { class: "view" });
  card.append(view);
  if (active === "overview") return renderOverview(view);
  if (active === "launch") return renderLaunchHub(view);
  if (active === "results") return renderResults(view);
  if (active === "history") return renderHistory(view);
  if (active === "report") return renderReport(view);
  const t = TRACK_BY_ID[active];
  if (!t) { view.append(el("div", { class: "err" }, `Unknown track: ${active}`)); return; }
  renderTrack(view, t);
}

// ============================================================ overview dashboard
function renderOverview(view) {
  view.append(el("h2", { class: "page-title" }, META && META.title ? META.title : "Quiver Capability Explorer"));

  // ---- Launch Hub hero: a wide horizontal bar, treated distinctly from track cards ----
  const s = queueStats();
  const hero = el("div", { class: "launch-hero" });
  const heroL = el("div", { class: "lh-left" },
    el("div", { class: "lh-ic" }, svgIcon("launch")),
    el("div", {}, el("div", { class: "lh-title" }, "Launch Hub"),
      el("div", { class: "lh-sub" }, "Queue many compounds across any track — paste a list or drop a CSV — and run them all at once.")));
  const heroR = el("div", { class: "lh-right" });
  if (s.n) heroR.append(el("span", { class: "lh-stat" },
    `${s.n} in queue${s.done ? ` · ${s.done} done` : ""}${s.error ? ` · ${s.error} err` : ""}`));
  const open = el("button", { class: "primary lh-cta", type: "button" }, "Open Launch Hub →");
  open.onclick = () => navigate("launch");
  heroR.append(open);
  if (s.done || s.error) { const r = el("button", { class: "ghost", type: "button" }, "Results"); r.onclick = () => navigate("results"); heroR.append(r); }
  hero.append(heroL, heroR);
  view.append(hero);

  // track card grid
  const grid = el("div", { class: "grid" });
  for (const t of TRACKS) {
    const bm = badgeMeta(t.badge);
    const card = el("button", { class: "tcard", type: "button", "aria-label": t.label });
    card.style.setProperty("--tc-accent", varColor(t.badge));
    card.onclick = () => navigate(t.id);
    card.append(el("div", { class: "tc-top" },
      trackMedallion(t.n, "tc-em"),
      el("div", { class: "tc-t" },
        el("div", { class: "tc-n" }, "TRACK " + (t.n ?? "")),
        el("div", { class: "tc-label" }, t.label)),
      el("span", { class: `vbadge bg-${t.badge}` }, bm.label)));
    card.append(el("div", { class: "tc-model" }, "Best: ", el("b", {}, t.best_model || "—")));
    const perf = (t.performance && t.performance.headline) || "";
    if (perf) card.append(el("div", { class: "tc-perf" }, perf));
    card.append(el("div", { class: "tc-foot" },
      el("span", { class: "tc-runtime", title: "Estimated inference time" },
        svgIcon("history"), "Est. runtime ", el("b", {}, t.est_runtime || "—"))));
    grid.append(card);
  }
  view.append(grid);
}

// ============================================================ track detail
function renderTrack(view, t) {
  const head = el("div", { class: "track-head" },
    trackMedallion(t.n, "th-em"),     // the medallion is the track number — no "Track N" text needed
    el("div", { class: "th-txt" },
      el("h2", {}, t.label),
      el("div", { class: "th-q" }, t.question || "")));
  view.append(head);
  if (t.tagline) view.append(el("div", { class: "tagline" }, t.tagline));

  // best-model chip row
  const chips = el("div", { class: "chips" });
  const mchip = el("span", { class: "chip" }, el("span", { class: "lbl" }, "Best model"), el("span", { class: "model" }, t.best_model || "—"));
  if (t.best_model) mchip.append(copyBtn(t.best_model));
  chips.append(mchip);
  if (t.license) chips.append(el("span", { class: "chip lic" }, t.license));
  if (t.est_runtime) chips.append(el("span", { class: "chip rt" }, svgIcon("history"),
    el("span", { class: "lbl" }, "Est. runtime"), el("span", {}, t.est_runtime)));
  if (t.performance && t.performance.headline) chips.append(el("span", { class: "chip perf" }, t.performance.headline));
  view.append(chips);

  view.append(relPanel(t));

  if (t.informational) return renderInformational(view, t);

  if (t.batch) {
    const toggle = el("div", { class: "modes", role: "group", "aria-label": "Prediction mode" });
    for (const m of ["single", "batch"]) {
      const b = el("button", { class: mode === m ? "on" : "", type: "button" }, m === "single" ? "Single" : "Batch triage");
      b.onclick = () => { mode = m; render(); };
      toggle.append(b);
    }
    view.append(toggle);
  } else if (mode !== "single") mode = "single";

  // per-track queue + results panels (a filtered slice of the global launch queue)
  let repaintPanels = () => {};
  if (t.batch && mode === "batch") renderBatch(view, t);
  else renderSingleForm(view, t, () => repaintPanels());
  repaintPanels = renderTrackPanels(view, t);
}

// Filtered views of the global launch queue, scoped to ONE track: what's queued for it +
// its results. Returns a paint() so the track's "Add to queue" can refresh live.
function renderTrackPanels(view, t) {
  const wrap = el("div", { class: "track-qpanels" });
  view.append(wrap);
  function miniRow(cells) { const tr = el("tr", {}); for (const c of cells) tr.append(el("td", {}, c)); return tr; }
  function paint() {
    wrap.innerHTML = "";
    const queued = launchQueue.filter((j) => j.track === t.id && (j.status === "queued" || j.status === "running"));
    const ran = launchQueue.filter((j) => j.track === t.id && (j.status === "done" || j.status === "error"));

    // --- Queued for this track ---
    const qp = el("div", { class: "tqp-card" });
    const qh = el("div", { class: "tqp-h" }, svgIcon("launch"), el("b", {}, `Queued for this track`),
      el("span", { class: "tqp-count" }, String(queued.length)));
    const qlink = el("button", { class: "linklike", type: "button" }, "Launch Hub →"); qlink.onclick = () => navigate("launch");
    qh.append(qlink); qp.append(qh);
    if (queued.length) {
      const tbl = el("table", { class: "report tqp-table" });
      const body = el("tbody", {});
      for (const job of queued) {
        const tr = el("tr", {});
        tr.append(el("td", {}, el("span", { class: "hub-inp", title: JSON.stringify(job.inputs) }, trunc(job.label, 48))));
        tr.append(el("td", {}, hubStatusChip(job.status)));
        const del = el("button", { class: "hub-x", type: "button", title: "Remove" }, "✕");
        del.onclick = () => { launchQueue = launchQueue.filter((j) => j.qid !== job.qid); saveQueue(); updateQueueChip(); paint(); };
        tr.append(el("td", {}, del)); body.append(tr);
      }
      tbl.append(body); qp.append(tbl);
      const run = el("button", { type: "button", class: "tqp-run" }, `Run ${queued.length} queued`);
      run.onclick = async () => { run.disabled = true; await runQueue(() => paint()); paint(); };
      qp.append(run);
    } else qp.append(el("div", { class: "tqp-empty" }, "Nothing queued — use “Add to queue” on the form above, or the Launch Hub."));
    wrap.append(qp);

    // --- Results for this track ---
    const rp = el("div", { class: "tqp-card" });
    const rh = el("div", { class: "tqp-h" }, svgIcon("results"), el("b", {}, "Results for this track"),
      el("span", { class: "tqp-count" }, String(ran.filter((j) => j.status === "done").length)));
    if (ran.length) { const rlink = el("button", { class: "linklike", type: "button" }, "All results →"); rlink.onclick = () => navigate("results"); rh.append(rlink); }
    rp.append(rh);
    if (ran.length) {
      const sorted = ran.slice().sort((a, b) => (b.status === "done" ? batchScore(b.result).val : -Infinity) - (a.status === "done" ? batchScore(a.result).val : -Infinity));
      const tbl = el("table", { class: "report tqp-table" });
      const body = el("tbody", {});
      for (const j of sorted) {
        const tr = el("tr", {});
        tr.append(el("td", {}, el("span", { class: "hub-inp", title: JSON.stringify(j.inputs) }, trunc(j.label, 42))));
        if (j.status === "done") {
          const pr = j.result, sc = batchScore(pr);
          let v = sc.txt;
          if (pr.score_kind === "affinity" && pr.value != null) v = "P " + Number(pr.value).toFixed(2);
          else if (pr.score_kind === "probability" && pr.value != null) v = (Number(pr.value) * 100).toFixed(0) + "%";
          tr.append(el("td", { class: "res-val" }, v));
          const call = pr.binder_call || pr.call || sc.call;
          tr.append(el("td", {}, call ? el("span", { class: "call-pill " + callPillClass(call) }, call) : "—"));
        } else { const ec = el("td", { class: "err-inline" }, trunc(j.error || "error", 60)); ec.setAttribute("colspan", "2"); tr.append(ec); }
        body.append(tr);
      }
      tbl.append(body); rp.append(tbl);
    } else rp.append(el("div", { class: "tqp-empty" }, "No results yet — queue some compounds and Run."));
    wrap.append(rp);
  }
  paint();
  return paint;
}

function renderInformational(view, t) {
  const ru = (t.verdict && t.verdict.recommended_use) || "";
  view.append(el("div", { class: "buildplan" },
    el("div", { class: "bp-title" }, svgIcon("build"), `Build plan — ${t.best_model || "build, don't buy"}`),
    el("div", { class: "bp-body" }, ru || "No public model fits this task. The moat is Quiver's own paired data.")));
  for (const f of t.inputs || []) {
    view.append(el("label", { for: "f_" + f.name }, f.label + (f.optional ? " (optional)" : "")));
    const inp = el("textarea", { id: "f_" + f.name, "aria-label": f.label, readonly: "readonly" });
    if (f.placeholder) inp.placeholder = f.placeholder;
    view.append(inp);
  }
  view.append(el("div", { class: "hint" },
    "This track is informational — there is no model call. See the verdict above for the empirical basis."));
}

function renderSingleForm(view, t, onQueue) {
  const inputs = {};
  for (const f of t.inputs || []) {
    view.append(el("label", { for: "f_" + f.name }, f.label + (f.optional ? " (optional)" : "")));
    let inp;
    if (f.type === "textarea") inp = el("textarea", { id: "f_" + f.name });
    else inp = el("input", { id: "f_" + f.name, type: "text" });
    inp.setAttribute("aria-label", f.label);
    if (f.placeholder) inp.placeholder = f.placeholder;
    inputs[f.name] = inp;
    view.append(inp);
  }
  if (pendingFill) {
    for (const f of t.inputs || []) if (pendingFill[f.name] != null && inputs[f.name]) inputs[f.name].value = pendingFill[f.name];
    pendingFill = null;
  }

  const btn = el("button", { id: "btn-run", type: "button" }, "Run");
  const ex = el("button", { class: "ghost", id: "btn-example", type: "button" }, "Load example");
  const addq = el("button", { class: "ghost", type: "button", title: "Add these inputs to the launch queue for this track" }, "+ Add to queue");
  addq.onclick = () => {
    const vals = {}; for (const f of t.inputs || []) vals[f.name] = (inputs[f.name].value || "").trim();
    if (enqueue(t.id, vals)) { if (onQueue) onQueue(); }
    else out.innerHTML = `<div class="hint">Fill at least one input to queue.</div>`;
  };
  view.append(el("div", { class: "row" }, btn, ex, addq));
  const out = el("div", { class: "result", id: "out" });
  view.append(out);

  ex.onclick = async () => {
    try {
      const r = await fetch(`${API}/api/examples/${t.id}`);
      const e = await r.json();
      if (!r.ok) { out.innerHTML = `<div class="err">${escapeHtml(JSON.stringify(e.detail || e, null, 2))}</div>`; return; }
      const exv = e.example || e;
      for (const f of t.inputs || []) if (exv[f.name] != null && inputs[f.name]) inputs[f.name].value = exv[f.name];
      const note = e.example_note || exv._note;
      out.innerHTML = note ? `<div class="hint">example: ${escapeHtml(note)}</div>` : "";
    } catch (err) { out.innerHTML = `<div class="err">${escapeHtml(String(err))}</div>`; }
  };

  btn.onclick = async () => {
    const body = {};
    for (const f of t.inputs || []) { const v = (inputs[f.name].value || "").trim(); if (v) body[f.name] = v; }
    btn.disabled = true;
    out.innerHTML = `<div class="spin">running ${escapeHtml(t.best_model || "model")}…</div>`;
    try {
      const res = await fetch(`${API}/api/predict/${t.id}`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) { out.innerHTML = `<div class="err">${escapeHtml(JSON.stringify(data.detail || data, null, 2))}</div>`; return; }
      renderResult(out, data, t);
    } catch (err) { out.innerHTML = `<div class="err">${escapeHtml(String(err))}</div>`; }
    finally { btn.disabled = false; }
  };
}

// ============================================================ result rendering (per score_kind)
function callPillClass(call) {
  const c = (call || "").toLowerCase();
  if (/(bbb\+|likely binder|binder|^yes|high)/.test(c)) return "pos";
  if (/(bbb-|non-binder|^no|low)/.test(c)) return "neg";
  return "mid";
}
function renderResult(out, data, track) {
  out.innerHTML = "";
  if (data.stubbed)
    out.append(el("div", { class: "hint" }, el("span", { class: "demo-tag" }, "Demo"),
      " Illustrative shape from the track contract, not a real prediction."));
  const pr = data.prediction || {};
  const model = data.model || (track && track.best_model) || "";
  renderPrediction(out, pr, model);
  out.append(relPanel(track, data.verdict));
}
function renderPrediction(out, pr, model) {
  switch (pr.score_kind) {
    case "embedding": return renderEmbedding(out, pr, model);
    case "affinity": return renderAffinity(out, pr, model);
    case "probability": return renderProbability(out, pr, model);
    case "panel": return renderPanel(out, pr, model);
    case "ranking": return renderRanking(out, pr, model);
    case "complex": return renderComplex(out, pr, model);
    case "analogs": return renderAnalogs(out, pr, model);
    case "panel_ranking": return renderPanelRanking(out, pr, model);
    case "none": return;
    default:
      out.append(providerShell(model || "result",
        el("div", { class: "big" }, pr.value != null ? String(pr.value) : "—"),
        pr.note ? el("div", { class: "hint" }, pr.note) : null));
  }
}
function providerShell(name, ...kids) {
  const card = el("div", { class: "provider" }, el("div", { class: "pname" }, name));
  for (const k of kids) if (k) card.append(k);
  return card;
}
function renderEmbedding(out, pr, model) {
  const card = providerShell(model || "Embedding",
    el("div", { class: "big" }, pr.nearest_family || "—"),
    el("div", { class: "sub" }, `nearest reference family${pr.dim ? ` · dim ${pr.dim}` : ""}`));
  if (pr.family_scores) {
    const rows = Object.entries(pr.family_scores).sort((a, b) => b[1] - a[1]);
    const max = Math.max(...rows.map((r) => r[1]), 1e-9);
    const tbl = el("table", { class: "kv" }, el("tr", {}, el("th", {}, "Family"), el("th", {}, "Score"), el("th", {}, "")));
    for (const [fam, sc] of rows) {
      const w = Math.round((sc / max) * 100);
      tbl.append(el("tr", {}, el("td", {}, fam), el("td", { class: "num" }, Number(sc).toFixed(3)),
        el("td", {}, el("span", { class: "bar track" }, el("i", { style: `width:${w}%` })))));
    }
    card.append(tbl);
  }
  if (pr.note) card.append(el("div", { class: "hint" }, pr.note));
  out.append(card);
}
function renderAffinity(out, pr, model) {
  const val = pr.value != null ? Number(pr.value).toFixed(2) : "—";
  const card = providerShell(model || "Affinity", el("div", { class: "big" }, `${val} ${pr.units || "pKd"}`));
  if (pr.binder_call) card.append(el("div", { class: "sub" }, el("span", { class: `pill ${callPillClass(pr.binder_call)}` }, pr.binder_call)));
  if (pr.note) card.append(el("div", { class: "hint" }, pr.note));
  out.append(card);
}
function renderProbability(out, pr, model) {
  const pct = pr.value != null ? (Number(pr.value) * 100).toFixed(1) + "%" : "—";
  const card = providerShell(model || "Probability", el("div", { class: "big" }, pct));
  if (pr.call) card.append(el("div", { class: "sub" }, el("span", { class: `pill ${callPillClass(pr.call)}` }, pr.call)));
  if (pr.note) card.append(el("div", { class: "hint" }, pr.note));
  out.append(card);
  if (Array.isArray(pr.providers)) {
    for (const p of pr.providers) {
      const ppct = p.value != null ? (Number(p.value) * 100).toFixed(1) + "%" : "—";
      out.append(providerShell(p.name || "provider", el("div", { class: "big" }, ppct),
        p.call ? el("div", { class: "sub" }, el("span", { class: `pill ${callPillClass(p.call)}` }, p.call)) : null));
    }
  }
}
function renderPanel(out, pr, model) {
  const card = providerShell(model || "Safety panel");
  const tbl = el("table", { class: "kv" }, el("tr", {}, el("th", {}, "Endpoint"), el("th", {}, "Risk"), el("th", {}, "Call"), el("th", {}, "Model")));
  for (const e of pr.endpoints || []) {
    tbl.append(el("tr", {}, el("td", {}, e.name), el("td", { class: "num" }, e.value != null ? Number(e.value).toFixed(2) : "—"),
      el("td", {}, e.call ? el("span", { class: `pill ${callPillClass(e.call)}` }, e.call) : "—"), el("td", { class: "hint" }, e.model || "")));
  }
  card.append(tbl);
  if (pr.note) card.append(el("div", { class: "hint" }, pr.note));
  out.append(card);
}
function renderRanking(out, pr, model) {
  const card = providerShell(model || "KG ranking");
  if (pr.rank_percentile != null)
    card.append(el("div", { class: "big" }, `${(Number(pr.rank_percentile) * 100).toFixed(1)}%`),
      el("div", { class: "sub" }, "binder-rank percentile (lower = stronger KG support)"));
  if (Array.isArray(pr.shortlist) && pr.shortlist.length) {
    const tbl = el("table", { class: "kv" }, el("tr", {}, el("th", {}, "Drug"), el("th", {}, "Rank %ile"), el("th", {}, "Note")));
    for (const r of pr.shortlist) {
      tbl.append(el("tr", {}, el("td", {}, r.drug), el("td", { class: "num" }, r.rank_pct != null ? (Number(r.rank_pct) * 100).toFixed(1) + "%" : "—"),
        el("td", { class: "hint" }, r.note || "")));
    }
    card.append(tbl);
  }
  if (pr.note) card.append(el("div", { class: "hint" }, pr.note));
  out.append(card);
}
function renderComplex(out, pr, model) {
  const card = providerShell(model || "Co-folded complex");
  const tbl = el("table", { class: "kv" }, el("tr", {}, el("th", {}, "Metric"), el("th", {}, "Value")));
  if (pr.confidence != null) tbl.append(el("tr", {}, el("td", {}, "Complex confidence"), el("td", { class: "num" }, Number(pr.confidence).toFixed(2))));
  if (pr.affinity != null) tbl.append(el("tr", {}, el("td", {}, "Predicted affinity"), el("td", { class: "num" }, `${Number(pr.affinity).toFixed(2)} ${pr.units || "pKd"}`)));
  card.append(tbl);
  if (pr.note) card.append(el("div", { class: "hint" }, pr.note));
  out.append(card);
}
function renderAnalogs(out, pr, model) {
  const card = providerShell(model || "Analogs");
  const tbl = el("table", { class: "kv" }, el("tr", {}, el("th", {}, "Neighbor SMILES"), el("th", {}, "Name"), el("th", {}, "Similarity"), el("th", {}, "")));
  for (const n of pr.neighbors || []) {
    tbl.append(el("tr", {}, el("td", { class: "mono" }, n.smiles), el("td", {}, n.name || "—"),
      el("td", { class: "num" }, n.similarity != null ? Number(n.similarity).toFixed(2) : "—"),
      el("td", {}, n.smiles ? copyBtn(n.smiles) : null)));
  }
  card.append(tbl);
  if (pr.note) card.append(el("div", { class: "hint" }, pr.note));
  out.append(card);
}
function renderPanelRanking(out, pr, model) {
  const card = providerShell(model || "Selectivity ranking");
  const tbl = el("table", { class: "kv" }, el("tr", {}, el("th", {}, "#"), el("th", {}, "Target"), el("th", {}, "Score"), el("th", {}, "")));
  const ranked = (pr.ranking || []).slice().sort((a, b) => (a.rank ?? 99) - (b.rank ?? 99));
  const max = Math.max(...ranked.map((r) => r.score || 0), 1e-9);
  for (const r of ranked) {
    const w = Math.round(((r.score || 0) / max) * 100);
    tbl.append(el("tr", {}, el("td", { class: "num" }, r.rank != null ? String(r.rank) : "—"), el("td", {}, r.target),
      el("td", { class: "num" }, r.score != null ? Number(r.score).toFixed(2) : "—"),
      el("td", {}, el("span", { class: "bar track" }, el("i", { style: `width:${w}%` })))));
  }
  card.append(tbl);
  if (pr.note) card.append(el("div", { class: "hint" }, pr.note));
  out.append(card);
}

// ============================================================ Launch Hub
// Command center: queue inputs across ANY track (manual, paste, or CSV/TSV drag-drop), run
// them all, analyze on the Results page. The queue persists (localStorage) and the topbar
// chip + overview hero reflect it on every page. Orchestrates client-side over
// /api/predict/{track} (every track) with a small concurrency cap — no backend change.

function hubTracks() {
  return TRACKS.filter((t) => !t.informational && (t.inputs || []).length);
}
function resolveTrackId(s) {
  if (!s) return null;
  const v = String(s).trim().toLowerCase();
  for (const t of hubTracks()) {
    if (t.id.toLowerCase() === v || (t.label || "").toLowerCase() === v || String(t.n) === v) return t.id;
  }
  const hit = hubTracks().find((t) => t.id.toLowerCase().includes(v) || (t.label || "").toLowerCase().includes(v));
  return hit ? hit.id : null;
}
function jobLabel(track, inputs) {
  const t = TRACK_BY_ID[track];
  const primary = (t && t.inputs && t.inputs[0] && t.inputs[0].name) || "smiles";
  return inputs.name || inputs[primary] || Object.values(inputs).find((v) => v) || "(row)";
}
function enqueue(track, inputs, label) {
  const clean = {}; for (const k in inputs) { const v = inputs[k]; if (v != null && String(v).trim() !== "") clean[k] = String(v).trim(); }
  if (!Object.keys(clean).length) return false;
  launchQueue.push({ qid: ++launchSeq, track, inputs: clean, label: label || jobLabel(track, clean),
                     status: "queued", result: null, error: null });
  saveQueue(); updateQueueChip(); return true;
}

// Parse a pasted/dropped table. Delimiter auto (comma/tab). Header row with known field names
// (or track/name) → column mapping; a 'track' column routes each row. Else each line is the
// default track's primary input ("value, name").
function parseHubTable(text, defaultTrack) {
  const lines = (text || "").split(/\r?\n/).map((l) => l.replace(/﻿/g, "").trimEnd()).filter((l) => l.trim() && !l.trim().startsWith("#"));
  if (!lines.length) return { jobs: [], skipped: 0, usedHeader: false };
  const delim = (lines[0].match(/\t/) && "\t") || ",";
  const split = (l) => l.split(delim).map((c) => c.trim());
  const knownFields = new Set(["track", "name", "label"]);
  for (const t of hubTracks()) for (const f of t.inputs) knownFields.add(f.name.toLowerCase());
  const head = split(lines[0]).map((h) => h.toLowerCase());
  const usedHeader = head.some((h) => knownFields.has(h));
  const jobs = []; let skipped = 0;
  for (const line of (usedHeader ? lines.slice(1) : lines)) {
    const cells = split(line);
    let track = defaultTrack, inputs = {}, label = null;
    if (usedHeader) {
      head.forEach((h, i) => {
        const v = (cells[i] || "").trim(); if (!v) return;
        if (h === "track") track = resolveTrackId(v) || track;
        else if (h === "name" || h === "label") label = v;
        else inputs[h] = v;
      });
    } else {
      const t = TRACK_BY_ID[defaultTrack];
      const primary = (t && t.inputs && t.inputs[0] && t.inputs[0].name) || "smiles";
      inputs[primary] = cells[0]; if (cells[1]) label = cells.slice(1).join(" ").trim();
    }
    if (!track || !Object.values(inputs).some((v) => v)) { skipped++; continue; }
    jobs.push({ track, inputs, label });
  }
  return { jobs, skipped, usedHeader };
}

async function runQueue(onTick) {
  const pending = launchQueue.filter((j) => j.status === "queued" || j.status === "error");
  let i = 0; const CONC = 4;
  async function worker() {
    while (i < pending.length) {
      const job = pending[i++];
      job.status = "running"; job.error = null; saveQueue(); updateQueueChip(); onTick();
      try {
        const res = await fetch(`${API}/api/predict/${job.track}`, {
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(job.inputs),
        });
        const data = await res.json();
        if (!res.ok) { job.status = "error"; job.error = (data && (data.detail || JSON.stringify(data))) || `HTTP ${res.status}`; }
        else { job.status = "done"; job.result = data.prediction || data; job._stubbed = !!data.stubbed; }
      } catch (e) { job.status = "error"; job.error = String(e); }
      saveQueue(); updateQueueChip(); onTick();
    }
  }
  await Promise.all(Array.from({ length: Math.min(CONC, pending.length) || 1 }, worker));
}

function queueStats() {
  const q = launchQueue;
  return { n: q.length, queued: q.filter((j) => j.status === "queued").length,
           running: q.filter((j) => j.status === "running").length,
           done: q.filter((j) => j.status === "done").length, error: q.filter((j) => j.status === "error").length };
}
// Global topbar chip — kept in sync on every page (called from render() + on every mutation).
function updateQueueChip() {
  const chip = document.getElementById("queue-chip"); if (!chip) return;
  const s = queueStats();
  if (!s.n) { chip.hidden = true; chip.innerHTML = ""; return; }
  chip.hidden = false; chip.innerHTML = "";
  chip.append(svgIcon("launch"));
  const parts = [];
  if (s.queued) parts.push(`${s.queued} queued`);
  if (s.running) parts.push(`${s.running} running`);
  if (s.done) parts.push(`${s.done} done`);
  if (s.error) parts.push(`${s.error} err`);
  chip.append(el("span", {}, parts.join(" · ")));
  chip.classList.toggle("busy", s.running > 0);
  chip.onclick = () => navigate(s.done && !s.queued && !s.running ? "results" : "launch");
}

function hubStatusChip(s) {
  const m = { queued: ["queued", "q"], running: ["running…", "r"], done: ["done", "d"], error: ["error", "e"] };
  const [t, k] = m[s] || [s, "q"]; return el("span", { class: "hub-st hub-st-" + k }, t);
}

// ---- Launch Hub page: compact toolbar + two-column builder + queue ----
function renderLaunchHub(view) {
  const head = el("div", { class: "hub-head" },
    el("div", { class: "hub-lead" }, "Queue inputs across any track — add a row, paste a list, or drop a CSV — then Run all. Outcomes collect on the Results page."));
  const tools = el("div", { class: "hub-tools" });
  const runBtn = el("button", { type: "button", class: "primary" }, "Run all");
  const resBtn = el("button", { class: "ghost", type: "button" }, "View results →");
  const clrBtn = el("button", { class: "ghost", type: "button" }, "Clear queue");
  tools.append(runBtn, resBtn, clrBtn); head.append(tools); view.append(head);

  const tracks = hubTracks();
  const builder = el("div", { class: "hub-builder" });

  // -- left: add a single row (fields laid out side-by-side) --
  const left = el("div", { class: "hub-card" });
  left.append(el("div", { class: "hub-h" }, svgIcon("launch"), "Add a row"));
  const trackSel = el("select", { class: "hub-sel" });
  for (const t of tracks) trackSel.append(el("option", { value: t.id }, `${String(t.n).padStart(2, "0")} · ${t.label}`));
  const fieldGrid = el("div", { class: "hub-fieldgrid" });
  const inputEls = {};
  function buildFields() {
    fieldGrid.innerHTML = ""; for (const k in inputEls) delete inputEls[k];
    const t = TRACK_BY_ID[trackSel.value];
    for (const f of t.inputs || []) {
      const inp = f.type === "textarea" ? el("textarea", {}) : el("input", { type: "text" });
      if (f.placeholder) inp.placeholder = f.placeholder; inp.setAttribute("aria-label", f.label);
      inputEls[f.name] = inp;
      fieldGrid.append(el("div", { class: "hub-field" + (f.type === "textarea" ? " wide" : "") },
        el("label", { class: "hub-lbl" }, f.label + (f.optional ? " (opt)" : "")), inp));
    }
  }
  trackSel.onchange = buildFields; buildFields();
  const addBtn = el("button", { type: "button" }, "Add to queue");
  const exBtn = el("button", { class: "ghost", type: "button" }, "Example");
  addBtn.onclick = () => { const v = {}; for (const k in inputEls) v[k] = inputEls[k].value;
    if (enqueue(trackSel.value, v)) { for (const k in inputEls) inputEls[k].value = ""; refresh(); } };
  exBtn.onclick = () => { const t = TRACK_BY_ID[trackSel.value]; for (const f of t.inputs || []) if (t.example && t.example[f.name] != null && inputEls[f.name]) inputEls[f.name].value = t.example[f.name]; };
  left.append(el("label", { class: "hub-lbl" }, "Track"), trackSel, fieldGrid, el("div", { class: "row" }, addBtn, exBtn));

  // -- right: bulk import (drop / browse / paste) --
  const right = el("div", { class: "hub-card" });
  right.append(el("div", { class: "hub-h" }, svgIcon("results"), "Bulk import"));
  const dzTrackSel = el("select", { class: "hub-sel" });
  for (const t of tracks) dzTrackSel.append(el("option", { value: t.id }, t.label));
  const dz = el("div", { class: "hub-dropzone", tabindex: "0" }, svgIcon("launch"),
    el("div", {}, el("b", {}, "Drop a CSV / TSV"), el("div", { class: "hub-hint" }, "or click to browse")));
  const fileInp = el("input", { type: "file", accept: ".csv,.tsv,.txt,text/csv", style: "display:none" });
  const paste = el("textarea", { class: "hub-paste", placeholder: "track,smiles,uniprot_acc,name\ndti,CC(=O)Oc1ccccc1C(=O)O,P14416,aspirin\n…or paste one entry per line for the default track" });
  const addBulk = el("button", { type: "button" }, "Add rows");
  const bulkMsg = el("span", { class: "hub-hint" });
  right.append(dz, fileInp,
    el("div", { class: "hub-bulkrow" }, el("label", { class: "hub-lbl" }, "Default track"), dzTrackSel),
    el("div", { class: "hub-hint" }, "CSV header maps columns (", el("code", {}, "track, smiles, uniprot_acc, gene, variant, name"), "); a ", el("code", {}, "track"), " column routes rows."),
    paste, el("div", { class: "row" }, addBulk, bulkMsg));
  function ingest(text, src) {
    const { jobs, skipped, usedHeader } = parseHubTable(text, dzTrackSel.value);
    let added = 0; for (const j of jobs) if (enqueue(j.track, j.inputs, j.label)) added++;
    bulkMsg.textContent = `${added} queued${skipped ? `, ${skipped} skipped` : ""}${usedHeader ? " (mapped)" : ` (→ ${TRACK_BY_ID[dzTrackSel.value].label})`}${src ? " · " + src : ""}`;
    refresh();
  }
  const readFile = (f) => { const r = new FileReader(); r.onload = () => ingest(String(r.result), f.name); r.readAsText(f); };
  addBulk.onclick = () => ingest(paste.value, null);
  dz.onclick = () => fileInp.click();
  dz.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileInp.click(); } };
  fileInp.onchange = () => { const f = fileInp.files[0]; if (f) readFile(f); };
  ["dragenter", "dragover"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("over"); }));
  ["dragleave", "drop"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("over"); }));
  dz.addEventListener("drop", (e) => { const f = e.dataTransfer.files[0]; if (f) readFile(f); });

  builder.append(left, right); view.append(builder);

  const queueWrap = el("div", { class: "result hub-queuewrap" });
  view.append(queueWrap);

  function syncToolbar() {
    const s = queueStats();
    runBtn.disabled = !(s.queued || s.error) || s.running > 0;
    resBtn.disabled = !(s.done || s.error); clrBtn.disabled = !s.n;
    runBtn.textContent = s.running ? "Running…" : "Run all" + (s.queued ? ` (${s.queued})` : "");
  }
  function refresh() { renderHubQueue(queueWrap); syncToolbar(); }
  runBtn.onclick = async () => { runBtn.disabled = true; clrBtn.disabled = true; await runQueue(() => refresh()); refresh(); navigate("results"); };
  resBtn.onclick = () => navigate("results");
  clrBtn.onclick = () => { if (confirm("Clear the whole queue?")) { launchQueue = []; saveQueue(); updateQueueChip(); refresh(); } };
  refresh();
}

function renderHubQueue(wrap) {
  wrap.innerHTML = "";
  const s = queueStats();
  if (!s.n) {
    wrap.append(el("div", { class: "hub-empty" }, svgIcon("launch"),
      el("div", {}, el("b", {}, "Queue is empty"), el("div", { class: "hub-hint" }, "Add a row or drop a CSV above — each row runs on its track's model."))));
    return;
  }
  wrap.append(el("div", { class: "hub-qcap" }, `Queue · ${s.n} job${s.n === 1 ? "" : "s"}${s.done ? ` · ${s.done} done` : ""}${s.error ? ` · ${s.error} error` : ""}`));
  const tbl = el("table", { class: "report hub-qtable" });
  tbl.append(el("thead", {}, el("tr", {}, el("th", {}, ""), el("th", {}, "Track"), el("th", {}, "Input"), el("th", {}, "Status"), el("th", {}, ""))));
  const body = el("tbody", {});
  for (const job of launchQueue) {
    const t = TRACK_BY_ID[job.track]; const tr = el("tr", {});
    tr.append(el("td", {}, trackMedallion(t ? t.n : "?", "rep-num")));
    tr.append(el("td", { class: "model" }, t ? t.label : job.track));
    tr.append(el("td", {}, el("span", { class: "hub-inp", title: JSON.stringify(job.inputs) }, trunc(job.label, 48))));
    tr.append(el("td", {}, hubStatusChip(job.status)));
    const del = el("button", { class: "hub-x", type: "button", title: "Remove" }, "✕");
    del.onclick = () => { launchQueue = launchQueue.filter((j) => j.qid !== job.qid); saveQueue(); updateQueueChip(); renderHubQueue(wrap); };
    tr.append(el("td", {}, del)); body.append(tr);
  }
  tbl.append(body); wrap.append(tbl);
}

function exportQueueCSV() {
  const fieldSet = new Set(); for (const j of launchQueue) for (const k in j.inputs) fieldSet.add(k);
  const fields = [...fieldSet];
  const head = ["track", "label", ...fields, "status", "score", "call", "confidence", "error"];
  const esc = (v) => { v = v == null ? "" : String(v); return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; };
  const lines = [head.join(",")];
  for (const j of launchQueue) {
    const sc = j.result ? batchScore(j.result) : { val: "", call: "" };
    lines.push([j.track, j.label, ...fields.map((f) => j.inputs[f] || ""), j.status,
      (j.result && (j.result.value ?? sc.val)) ?? "", (j.result && (j.result.binder_call || j.result.call)) || sc.call || "",
      (j.result && j.result.confidence) || "", j.error || ""].map(esc).join(","));
  }
  const blob = new Blob([lines.join("\n")], { type: "text/csv" });
  const a = el("a", { href: URL.createObjectURL(blob), download: "launch_hub_results.csv" });
  document.body.append(a); a.click(); a.remove();
}

// ============================================================ Results page
// Dedicated analysis of everything run: summary, then per-track sections sorted best-first,
// with score + call + confidence; CSV export. Reads the same launchQueue → syncs across pages.
function renderResults(view) {
  const done = launchQueue.filter((j) => j.status === "done");
  const err = launchQueue.filter((j) => j.status === "error");
  const nTracks = new Set([...done, ...err].map((j) => j.track)).size;
  const head = el("div", { class: "hub-head" },
    el("div", { class: "hub-lead" }, (done.length || err.length)
      ? `${done.length} prediction${done.length === 1 ? "" : "s"} across ${nTracks} track${nTracks === 1 ? "" : "s"}${err.length ? ` · ${err.length} error${err.length === 1 ? "" : "s"}` : ""}`
      : "Run a queue in the Launch Hub to see results here."));
  const tools = el("div", { class: "hub-tools" });
  const expBtn = el("button", { type: "button" }, "Export CSV"); expBtn.disabled = !done.length;
  const hubBtn = el("button", { class: "ghost", type: "button" }, "← Launch Hub");
  const clrBtn = el("button", { class: "ghost", type: "button" }, "Clear all");
  tools.append(expBtn, hubBtn, clrBtn); head.append(tools); view.append(head);
  expBtn.onclick = exportQueueCSV; hubBtn.onclick = () => navigate("launch");
  clrBtn.onclick = () => { if (confirm("Clear all queued jobs + results?")) { launchQueue = []; saveQueue(); updateQueueChip(); render(); } };

  if (!done.length && !err.length) {
    view.append(el("div", { class: "hub-empty" }, svgIcon("results"),
      el("div", {}, el("b", {}, "Nothing run yet"), el("div", { class: "hub-hint" }, "Queue jobs in the Launch Hub and press Run all."))));
    const go = el("button", { type: "button", class: "primary" }, "Open Launch Hub"); go.onclick = () => navigate("launch");
    view.append(el("div", { class: "row" }, go));
    return;
  }

  const byTrack = {};
  for (const j of launchQueue) if (j.status === "done" || j.status === "error") (byTrack[j.track] = byTrack[j.track] || []).push(j);
  const tids = Object.keys(byTrack).sort((a, b) => ((TRACK_BY_ID[a] || {}).n || 99) - ((TRACK_BY_ID[b] || {}).n || 99));

  // summary cards
  const summary = el("div", { class: "res-summary" });
  for (const tid of tids) {
    const t = TRACK_BY_ID[tid], rows = byTrack[tid], d = rows.filter((r) => r.status === "done");
    const card = el("button", { class: "res-sumcard", type: "button", title: "Jump to section" },
      trackMedallion(t ? t.n : "?", "rep-num"),
      el("div", {}, el("div", { class: "res-sumlabel" }, t ? t.label : tid),
        el("div", { class: "hub-hint" }, `${d.length} done${rows.length - d.length ? ` · ${rows.length - d.length} err` : ""}`)));
    card.onclick = () => { const s = document.getElementById("res-" + tid); if (s) s.scrollIntoView({ behavior: "smooth", block: "start" }); };
    summary.append(card);
  }
  view.append(summary);

  // per-track sections, best-first
  for (const tid of tids) {
    const t = TRACK_BY_ID[tid];
    const sect = el("div", { class: "res-section", id: "res-" + tid });
    sect.append(el("div", { class: "res-secthead" }, trackMedallion(t ? t.n : "?", "rep-num"),
      el("b", {}, t ? t.label : tid), t ? el("span", { class: "hub-hint" }, "Best: " + (t.best_model || "")) : null));
    const rows = byTrack[tid].slice().sort((a, b) =>
      (b.status === "done" ? batchScore(b.result).val : -Infinity) - (a.status === "done" ? batchScore(a.result).val : -Infinity));
    const tbl = el("table", { class: "report res-table" });
    tbl.append(el("thead", {}, el("tr", {}, el("th", {}, "Input"), el("th", {}, "Score"), el("th", {}, "Call"), el("th", {}, "Confidence"))));
    const body = el("tbody", {});
    for (const j of rows) {
      const tr = el("tr", {});
      tr.append(el("td", {}, el("span", { class: "hub-inp", title: JSON.stringify(j.inputs) }, trunc(j.label, 52))));
      if (j.status === "done") {
        const pr = j.result, sc = batchScore(pr);
        let v = sc.txt;
        if (pr.score_kind === "affinity" && pr.value != null) v = "P " + Number(pr.value).toFixed(2);
        else if (pr.score_kind === "probability" && pr.value != null) v = (Number(pr.value) * 100).toFixed(0) + "%";
        tr.append(el("td", { class: "res-val" }, v));
        const call = pr.binder_call || pr.call || sc.call;
        tr.append(el("td", {}, call ? el("span", { class: "call-pill " + callPillClass(call) }, call) : "—"));
        tr.append(el("td", { class: "hub-hint" }, pr.confidence ? trunc(pr.confidence, 46) : "—"));
      } else {
        const ec = el("td", { class: "err-inline" }, trunc(j.error || "error", 90)); ec.setAttribute("colspan", "3");
        tr.append(ec);
      }
      body.append(tr);
    }
    tbl.append(body); sect.append(tbl); view.append(sect);
  }
}

// ============================================================ batch triage
function parseList(text) {
  return (text || "").split(/\r?\n/).map((l) => l.trim()).filter((l) => l && !l.startsWith("#"))
    .map((l) => { const parts = l.split(/[,\t]/); return { value: parts[0].trim(), name: parts.slice(1).join(",").trim() }; })
    .filter((r) => r.value);
}
function renderBatch(view, t) {
  const entity = (t.batch && t.batch.entity) || "smiles";
  const label = (t.batch && t.batch.label) || `${entity} — one per line`;
  const out = el("div", { class: "result", id: "bout" });
  view.append(el("label", { for: "b_list" }, label));
  const ta = el("textarea", { id: "b_list", "aria-label": label });
  ta.style.minHeight = "130px";
  if (t.inputs && t.inputs[0] && t.inputs[0].placeholder) ta.placeholder = t.inputs[0].placeholder;
  view.append(ta);
  const run = el("button", { id: "b_run", type: "button" }, "Rank");
  const ex = el("button", { class: "ghost", type: "button" }, "Load example");
  view.append(el("div", { class: "row" }, run, ex), out);

  ex.onclick = async () => {
    let seed = (t.example && t.example[entity]) || "";
    const extras = {
      bbbp: "\nCC(C)CC1=CC=C(C=C1)C(C)C(=O)O, ibuprofen\nCC(=O)OC1=CC=CC=C1C(=O)O, aspirin\nNCCc1ccc(O)c(O)c1, dopamine",
      toxicity: "\nCC(=O)OC1=CC=CC=C1C(=O)O, aspirin\nCN1C=NC2=C1C(=O)N(C(=O)N2C)C, caffeine",
    };
    ta.value = (seed || "") + (extras[t.id] || "");
    if (!ta.value.trim()) {
      try { const e = await (await fetch(`${API}/api/examples/${t.id}`)).json(); const exv = (e.example || e)[entity]; if (exv) ta.value = exv; } catch (_) {}
    }
    out.innerHTML = t.example_note ? `<div class="hint">example: ${escapeHtml(t.example_note)}</div>` : "";
  };

  run.onclick = async () => {
    const es = parseList(ta.value);
    if (!es.length) { out.innerHTML = `<div class="err">No input rows — paste at least one entry.</div>`; return; }
    const rows = es.map((e) => ({ [entity]: e.value }));
    const labels = es.map((e) => e.name || e.value);
    run.disabled = true;
    out.innerHTML = `<div class="spin">ranking ${rows.length} row${rows.length === 1 ? "" : "s"}…</div>`;
    try {
      const res = await fetch(`${API}/api/predict/${t.id}/batch`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ rows }),
      });
      const data = await res.json();
      if (!res.ok) { out.innerHTML = `<div class="err">${escapeHtml(JSON.stringify(data.detail || data, null, 2))}</div>`; return; }
      batchState = { trackId: t.id, data, labels, sortKey: "rank", sortDir: 1 };
      renderBatchResult(out, t);
    } catch (err) { out.innerHTML = `<div class="err">${escapeHtml(String(err))}</div>`; }
    finally { run.disabled = false; }
  };

  if (batchState && batchState.trackId === t.id) renderBatchResult(out, t);
}
function batchScore(pr) {
  if (!pr) return { txt: "—", val: -Infinity, call: null };
  if (pr.score_kind === "probability") return { txt: (Number(pr.value) * 100).toFixed(1) + "%", val: Number(pr.value), call: pr.call };
  if (pr.score_kind === "affinity") return { txt: `${Number(pr.value).toFixed(2)} ${pr.units || "pKd"}`, val: Number(pr.value), call: pr.binder_call };
  if (pr.score_kind === "panel") {
    const eps = pr.endpoints || [];
    const worst = eps.reduce((m, e) => Math.max(m, e.value ?? 0), 0);
    const txt = eps.map((e) => `${e.name} ${Number(e.value).toFixed(2)}`).join(" · ");
    return { txt, val: -worst, call: eps.find((e) => /high|flag/i.test(e.call || "")) ? "flag" : "low risk" };
  }
  if (pr.value != null) return { txt: String(pr.value), val: Number(pr.value), call: pr.call };
  return { txt: "—", val: -Infinity, call: null };
}
function batchLabel(rec) { return (batchState.labels && batchState.labels[rec.index]) || JSON.stringify(rec.inputs); }
function sortedBatchRows() {
  const k = batchState.sortKey, dir = batchState.sortDir;
  const rows = (batchState.data.rows || []).slice();
  const keyfn = k === "name" ? (r) => batchLabel(r).toLowerCase()
    : k === "score" ? (r) => batchScore(r.prediction).val
    : (r) => (r.rank == null ? Infinity : r.rank);
  rows.sort((a, b) => { const x = keyfn(a), y = keyfn(b); if (x < y) return -1 * dir; if (x > y) return 1 * dir; return a.index - b.index; });
  return rows;
}
function renderBatchResult(out, t) {
  const d = batchState.data;
  out.innerHTML = "";
  if (d.stubbed)
    out.append(el("div", { class: "hint" }, el("span", { class: "demo-tag" }, "Demo"),
      " Every row returns the track's stub shape (same value); ranking is illustrative."));
  const allRows = d.rows || [];
  const scored = allRows.filter((r) => r.rank != null).length;
  const errs = allRows.length - scored;
  const processed = d.processed != null ? d.processed : allRows.length;
  let summary = `Ranked ${scored} of ${processed} row${processed === 1 ? "" : "s"}`;
  if (errs) summary += ` · ${errs} could not be scored`;
  if (d.dropped) summary += ` · ${d.dropped} dropped (cap reached)`;
  out.append(el("div", { class: "hint" }, summary));
  const csv = el("button", { class: "ghost", type: "button" }, "Download CSV");
  csv.onclick = () => downloadBatchCsv(t);
  out.append(el("div", { class: "row" }, csv));

  const tbl = el("table", { class: "batch" });
  const head = el("tr", {});
  const cols = [["rank", "#"], ["name", "Entry"], ["score", "Score"], ["class", "Call"], ["note", "Note"]];
  for (const [key, label] of cols) {
    const arrow = batchState.sortKey === key ? (batchState.sortDir > 0 ? " ▲" : " ▼") : "";
    const th = el("th", {}, label + arrow);
    if (["rank", "name", "score"].includes(key)) {
      th.setAttribute("role", "button"); th.setAttribute("tabindex", "0");
      const sort = () => { if (batchState.sortKey === key) batchState.sortDir *= -1; else { batchState.sortKey = key; batchState.sortDir = key === "score" ? -1 : 1; } renderBatchResult(out, t); };
      th.onclick = sort;
      th.onkeydown = (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); sort(); } };
    }
    head.append(th);
  }
  tbl.append(head);
  for (const rec of sortedBatchRows()) {
    const pr = rec.prediction, sc = batchScore(pr);
    const tr = el("tr", { class: rec.error ? "bad" : "" });
    tr.append(el("td", { class: "num" }, rec.rank != null ? String(rec.rank) : "—"));
    tr.append(el("td", { class: "mono" }, batchLabel(rec)));
    tr.append(el("td", { class: "num" }, sc.txt));
    tr.append(el("td", {}, sc.call ? el("span", { class: `pill ${callPillClass(sc.call)}` }, sc.call) : ""));
    tr.append(el("td", { class: "hint" }, rec.error || (pr && pr.note ? trunc(pr.note, 60) : "")));
    tbl.append(tr);
  }
  out.append(tbl);
  out.append(relPanel(t, d.verdict || d.reliability));
}
function downloadBatchCsv(t) {
  const head = ["rank", "label", "input", "score_kind", "value", "call", "error"];
  const esc = (v) => { const s = v == null ? "" : String(v); return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
  const lines = [head.join(",")];
  for (const rec of sortedBatchRows()) {
    const pr = rec.prediction || {}; const sc = batchScore(pr);
    const entity = (t.batch && t.batch.entity) || "smiles";
    const input = (rec.inputs && rec.inputs[entity]) || JSON.stringify(rec.inputs);
    lines.push([rec.rank, batchLabel(rec), input, pr.score_kind, pr.value, sc.call, rec.error].map(esc).join(","));
  }
  const blob = new Blob([lines.join("\n")], { type: "text/csv" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = `${t.id}_batch.csv`; a.click(); URL.revokeObjectURL(a.href);
}

// ============================================================ history
function inputPreview(inp) {
  return Object.entries(inp || {}).map(([k, v]) => `${k}=${trunc(String(v), 46)}`).join("  ·  ") || "(no inputs)";
}
function fmtSummary(s) {
  if (!s) return "—";
  const k = s.score_kind;
  if (k === "affinity") return `${s.value != null ? Number(s.value).toFixed(2) : "?"} ${s.units || "pKd"}${s.binder_call ? " · " + s.binder_call : ""}`;
  if (k === "probability") return `${s.value != null ? (Number(s.value) * 100).toFixed(1) + "%" : "?"}${s.call ? " · " + s.call : ""}`;
  if (k === "embedding") return `nearest family: ${s.nearest_family || "?"}`;
  if (k === "ranking") return `rank %ile: ${s.rank_percentile != null ? (Number(s.rank_percentile) * 100).toFixed(1) + "%" : "?"}`;
  if (k === "complex") return `conf ${s.confidence ?? "?"} · aff ${s.affinity ?? "?"}`;
  if (k === "panel") return (s.endpoints || []).map((e) => `${e.name} ${e.value}`).join(" · ") || "panel";
  if (k === "panel_ranking") { const r = (s.ranking || [])[0]; return r ? `top: ${r.target} (${r.score})` : "ranking"; }
  if (k === "analogs") return `${(s.neighbors || []).length} analog(s)`;
  if (k === "none") return "(informational)";
  return s.value != null ? String(s.value) : "—";
}
function loadHistoryRecord(rec) { pendingFill = rec.inputs || {}; navigate(rec.track || rec.task); }
function historyRow(rec) {
  const trackId = rec.track || rec.task;
  const t = TRACK_BY_ID[trackId];
  const label = t ? t.label : trackId;
  const bm = badgeMeta(rec.badge);
  const summary = rec.summary || rec.prediction;
  const row = el("div", { class: "provider" });
  row.append(el("div", { class: "pname" }, el("span", { class: "hdot", style: `background:${varColor(rec.badge)}` }), " " + label,
    el("span", { class: "kind", style: "margin-left:8px;color:var(--text-faint)" }, rec.ts ? new Date(rec.ts).toLocaleString() : "")));
  row.append(el("div", { class: "big", html: `<span style="font-size:18px;word-break:break-all">${escapeHtml(fmtSummary(summary))}</span>` }));
  row.append(el("div", { class: "sub", html: `<span style="font-family:var(--mono);font-size:11.5px">${escapeHtml(inputPreview(rec.inputs))}</span>` }));
  const loadBtn = el("button", { class: "ghost", type: "button" }, "Load into track");
  loadBtn.onclick = () => loadHistoryRecord(rec);
  if (!t) loadBtn.disabled = true;
  row.append(el("div", { class: "row" }, loadBtn));
  return row;
}
function renderHistory(view) {
  view.append(el("div", { class: "hub-lead" }, "Every prediction you've run (most recent first). Persists on the server across restarts."));
  const list = el("div", { class: "result", id: "hist" });
  const refresh = el("button", { class: "ghost", type: "button" }, "Refresh");
  const clr = el("button", { class: "ghost", type: "button" }, "Clear history");
  view.append(el("div", { class: "row" }, refresh, clr), list);
  async function load() {
    list.innerHTML = '<div class="spin">loading…</div>';
    try {
      const data = await (await fetch(`${API}/api/history?limit=200`)).json();
      list.innerHTML = "";
      const records = data.records || [];
      if (!records.length) { list.append(el("div", { class: "hist-empty" }, "No predictions yet — run something in a track and it shows up here.")); return; }
      list.append(el("div", { class: "hint" }, `${data.count ?? records.length} prediction${(data.count ?? records.length) === 1 ? "" : "s"} logged`));
      for (const rec of records) list.append(historyRow(rec));
    } catch (err) { list.innerHTML = `<div class="err">${escapeHtml(String(err))}</div>`; }
  }
  refresh.onclick = load;
  clr.onclick = async () => { if (confirm("Clear all prediction history?")) { try { await fetch(`${API}/api/history`, { method: "DELETE" }); } catch (_) {} load(); } };
  load();
}

// ============================================================ report page
const SCORECARD_DOC = "/doc/docs/models_tracks_scorecard.md";
// The report and the scorecard doc now share one sequential 1–9 numbering (the doc's
// old "Track 7 — Cross-modal" was removed and the doc renumbered to match the Explorer),
// so a row's `n` is exactly its doc section number. The renderer exposes each as a
// stable `id="track-N"`, so the deep-link is just `#track-{n}`.
function scorecardAnchor(r) {
  return `${SCORECARD_DOC}#track-${r.n}`;
}
async function renderReport(view) {
  view.append(el("div", { class: "report-intro hub-lead" },
    "The best model per Quiver track, its license, headline performance, and the empirical operating-envelope verdict. The scorecard link on each row opens that track's full section in the report."));
  // Link to the full rendered scorecard (top of the doc).
  const scLink = el("a", { class: "scorecard-link", href: SCORECARD_DOC, target: "_blank", rel: "noopener" });
  scLink.append(svgIcon("report"), "Open the full models scorecard");
  view.append(el("div", { class: "report-actions" }, scLink));
  const wrap = el("div", { class: "result", id: "report" });
  view.append(wrap);
  wrap.innerHTML = '<div class="spin">loading report…</div>';
  let rows;
  try { const data = await (await fetch(`${API}/api/report`)).json(); rows = data.tracks || []; }
  catch (err) { wrap.innerHTML = `<div class="err">${escapeHtml(String(err))}</div>`; return; }
  wrap.innerHTML = "";
  const tbl = el("table", { class: "report" });
  tbl.append(el("thead", {}, el("tr", {}, el("th", {}, "Track"), el("th", {}, "Best model"), el("th", {}, "License"),
    el("th", {}, "Est. runtime"), el("th", {}, "Headline performance"), el("th", {}, "Verdict"))));
  const body = el("tbody", {});
  for (const r of rows.slice().sort((a, b) => (a.n ?? 99) - (b.n ?? 99))) {
    const bm = badgeMeta(r.badge);
    const perf = (r.performance && r.performance.headline) || r.performance_headline || "—";
    const vhead = (r.verdict && r.verdict.headline) || r.verdict_headline || "";
    const tr = el("tr", {});
    // The track name jumps into the in-app track tab; the scorecard chip
    // deep-links to that track's section in the rendered scorecard doc.
    const name = el("span", { class: "trk" }, trackMedallion(r.n, "rep-num"), r.label || r.id);
    name.style.cursor = "pointer";
    name.onclick = () => navigate(r.id);
    const scAnchor = el("a", {
      class: "trk-scorecard", href: scorecardAnchor(r),
      target: "_blank", rel: "noopener", title: "Open this track in the scorecard",
    }, "scorecard ↗");
    const trk = el("td", {}, el("div", { class: "trk-cell" }, name, scAnchor));
    tr.append(trk);
    tr.append(el("td", { class: "model" }, r.best_model || "—"));
    tr.append(el("td", {}, el("span", { class: "lic" }, r.license || "—")));
    tr.append(el("td", { class: "rt" }, r.est_runtime || "—"));
    tr.append(el("td", { class: "perf" }, perf));
    const vcell = el("td", {});
    vcell.append(el("span", { class: `vbadge bg-${r.badge}` }, bm.label));
    if (vhead) vcell.append(el("div", { class: "vline" }, vhead));
    tr.append(vcell);
    body.append(tr);
  }
  tbl.append(body);
  wrap.append(tbl);
  const legend = el("div", { class: "legend" });
  legend.append(el("h3", {}, "Verdict legend"));
  const grid = el("div", { class: "leg-grid" });
  for (const key of ["reliable", "caution", "split", "low_value", "build", "dont_use"]) {
    if (!BADGES[key]) continue;
    const b = BADGES[key];
    grid.append(el("div", { class: "leg-item" }, el("span", { class: `badge bg-${key}` }, b.label), el("span", { class: "leg-desc" }, b.desc || "")));
  }
  legend.append(grid);
  wrap.append(legend);
}

// ============================================================ theme
function currentTheme() { return document.documentElement.getAttribute("data-theme") || "dark"; }
function applyTheme(t) {
  document.documentElement.setAttribute("data-theme", t);
  try { localStorage.setItem("qx-theme", t); } catch (_) {}
  const btn = document.getElementById("theme-btn");
  if (btn) { btn.innerHTML = SVG_ICONS[t === "dark" ? "sun" : "moon"]; btn.title = t === "dark" ? "Switch to light" : "Switch to dark"; }
}
function toggleTheme() { applyTheme(currentTheme() === "dark" ? "light" : "dark"); }

// ============================================================ command palette
let palItems = [], palSel = 0;
function paletteEntries() {
  const arr = [{ key: "overview", label: "Overview", sub: "all tracks at a glance" }];
  arr.push({ key: "launch", label: "Launch Hub", sub: "queue many inputs across tracks · CSV drop · run all" });
  arr.push({ key: "results", label: "Results", sub: "batch run outcomes, grouped by track · export" });
  for (const t of TRACKS) arr.push({ key: t.id, label: t.label, sub: `Track ${t.n} · ${t.best_model || ""}` });
  arr.push({ key: "history", label: "History", sub: "past predictions" });
  arr.push({ key: "report", label: "Report", sub: "model-per-track table" });
  arr.push({ key: "__theme", label: "Toggle light / dark theme", sub: "appearance", icon: "theme" });
  return arr;
}
function openPalette() {
  const p = document.getElementById("palette");
  p.hidden = false;
  const inp = document.getElementById("palette-input");
  inp.value = ""; palSel = 0;
  filterPalette("");
  inp.focus();
}
function closePalette() { document.getElementById("palette").hidden = true; }
function filterPalette(q) {
  q = (q || "").trim().toLowerCase();
  palItems = paletteEntries().filter((e) => !q || (e.label + " " + (e.sub || "")).toLowerCase().includes(q));
  palSel = 0;
  drawPalette();
}
function drawPalette() {
  const list = document.getElementById("palette-list");
  list.innerHTML = "";
  if (!palItems.length) { list.append(el("div", { class: "pal-empty" }, "No matches")); return; }
  palItems.forEach((e, i) => {
    const ic = e.icon === "theme" ? svgIcon("sun") : keyIcon(e.key);
    const it = el("div", { class: "pal-item" + (i === palSel ? " sel" : ""), "data-i": i },
      el("span", { class: "pe" }, ic),
      el("span", { class: "pl" }, e.label, el("small", {}, e.sub || "")),
      i === palSel ? el("span", { class: "pk" }, "Enter") : null);
    it.onclick = () => choosePalette(i);
    it.onmousemove = () => { if (palSel !== i) { palSel = i; drawPalette(); } };
    list.append(it);
  });
}
function choosePalette(i) {
  const e = palItems[i];
  if (!e) return;
  closePalette();
  if (e.key === "__theme") toggleTheme();
  else navigate(e.key);
}

// ============================================================ sidebar drawer (mobile)
function openNav() { document.getElementById("app").classList.add("nav-open"); }
function closeNav() { document.getElementById("app").classList.remove("nav-open"); }

// ============================================================ global wiring
function wireChrome() {
  // static icons (no emoji)
  document.getElementById("menu-btn").innerHTML = SVG_ICONS.menu;
  document.getElementById("side-close").innerHTML = SVG_ICONS.close;
  const sbic = document.querySelector("#search-btn .sb-ic");
  if (sbic) sbic.innerHTML = SVG_ICONS.search;

  // theme button
  applyTheme(currentTheme());
  document.getElementById("theme-btn").onclick = toggleTheme;

  // sidebar filter
  const nf = document.getElementById("nav-filter");
  nf.oninput = () => applyNavFilter(nf.value);

  // mobile drawer
  document.getElementById("menu-btn").onclick = openNav;
  document.getElementById("side-close").onclick = closeNav;
  document.getElementById("scrim").onclick = closeNav;

  // command palette
  document.getElementById("search-btn").onclick = openPalette;
  const pinp = document.getElementById("palette-input");
  pinp.oninput = () => filterPalette(pinp.value);
  document.getElementById("palette").onclick = (ev) => { if (ev.target.id === "palette") closePalette(); };

  // global keyboard
  document.addEventListener("keydown", (ev) => {
    const pal = document.getElementById("palette");
    const palOpen = !pal.hidden;
    if ((ev.metaKey || ev.ctrlKey) && (ev.key === "k" || ev.key === "K")) { ev.preventDefault(); palOpen ? closePalette() : openPalette(); return; }
    if (palOpen) {
      if (ev.key === "Escape") { ev.preventDefault(); closePalette(); }
      else if (ev.key === "ArrowDown") { ev.preventDefault(); palSel = Math.min(palSel + 1, palItems.length - 1); drawPalette(); }
      else if (ev.key === "ArrowUp") { ev.preventDefault(); palSel = Math.max(palSel - 1, 0); drawPalette(); }
      else if (ev.key === "Enter") { ev.preventDefault(); choosePalette(palSel); }
      return;
    }
    // "/" focuses the sidebar filter (unless typing in a field)
    const tag = (ev.target.tagName || "").toLowerCase();
    const typing = tag === "input" || tag === "textarea" || tag === "select";
    if (ev.key === "/" && !typing) { ev.preventDefault(); document.getElementById("nav-filter").focus(); }
    if (ev.key === "Escape") closeNav();
  });
}

// ============================================================ boot
async function boot() {
  wireChrome();
  try {
    META = await (await fetch(`${API}/api/meta`)).json();
    BADGES = META.badges || {};
    if (META.title) { document.getElementById("brand-title").textContent = "Capability Explorer"; document.title = META.title; }
  } catch (err) {
    document.getElementById("card").innerHTML = `<div class="err">Could not load /api/meta — is the backend running?</div>`;
  }
  try {
    const data = await (await fetch(`${API}/api/tracks`)).json();
    TRACKS = (data.tracks || []).slice().sort((a, b) => (a.n ?? 99) - (b.n ?? 99));
    TRACK_BY_ID = {};
    for (const t of TRACKS) TRACK_BY_ID[t.id] = t;
  } catch (err) {
    document.getElementById("card").innerHTML = `<div class="err">Could not load tracks: ${escapeHtml(String(err))}</div>`;
    return;
  }
  renderSidebar();
  active = hashToKey();
  render();
}

boot();
