/* ============ Sapphire site — interactions ============ */
const D = window.SAPPHIRE;
const $ = (s, r = document) => r.querySelector(s);
const el = (t, c, h) => { const e = document.createElement(t); if (c) e.className = c; if (h != null) e.innerHTML = h; return e; };

/* ---------- hero EP trace ---------- */
function epPath(baseline, jitter, spikeAt) {
  const W = 1440, step = 12; let d = `M0 ${baseline}`;
  for (let x = step; x <= W; x += step) {
    let y = baseline + (Math.sin(x / 40) * 3) + (Math.random() - .5) * jitter;
    if (spikeAt.some(s => Math.abs(x - s) < 7)) y = baseline - 70 - Math.random() * 20;       // upstroke
    else if (spikeAt.some(s => x - s >= 7 && x - s < 20)) y = baseline + 26;                   // afterhyperpolarization
    d += ` L${x} ${y.toFixed(1)}`;
  }
  return d;
}
function seedTraces() {
  const spikes = [180, 470, 700, 980, 1230];
  $("#epTrace").setAttribute("d", epPath(170, 6, spikes));
  $("#epTrace2").setAttribute("d", epPath(210, 10, [330, 600, 1100]));
}
seedTraces();

/* ---------- stat chips ---------- */
const m = D.meta;
const chips = [
  [m.atlasFreq + "×", "Quiver Atlas in pipelines (top source)"],
  [m.capabilities, "capability areas"],
  [m.prompts, "customer prompts"],
  [m.pipelines, "pipelines decomposed"],
  [m.kgNodes, "knowledge-graph nodes"],
];
$("#statChips").append(...chips.map(([b, s]) => el("div", "chip", `<b>${b}</b><span>${s}</span>`)));

/* ---------- methodology pipeline ---------- */
const pipe = $("#pipeline"), pdet = $("#pipelineDetail");
D.methodology.forEach((s, i) => {
  const n = el("div", "pnode", `
    <div class="pnum ${s.n === "—" ? "dash" : ""}">${s.n}</div>
    <div class="pttl">${s.t}</div>
    ${i < D.methodology.length - 1 ? '<span class="parrow">&rarr;</span>' : ''}`);
  n.onclick = () => {
    document.querySelectorAll(".pnode").forEach(x => x.classList.remove("active"));
    n.classList.add("active");
    pdet.classList.remove("show");
    setTimeout(() => { pdet.innerHTML = `<b>${s.t}.</b> ${s.d}`; pdet.classList.add("show"); }, 120);
  };
  pipe.append(n);
});
pipe.firstChild.click();

/* ---------- tiers ---------- */
$("#tiers").append(...D.sampleQuery.tiers.map(([n, lat, p]) =>
  el("div", "tier", `<h4>${n}</h4><div class="lat">${lat}</div><p>${p}</p>`)));

/* ---------- cascade ---------- */
const sq = D.sampleQuery, casc = $("#cascade");
$("#cascadeQ").textContent = `“${sq.query}”  ·  ${sq.tier}`;
const spike = el("div", "spike"); casc.append(spike);
sq.stages.forEach(s => {
  casc.append(el("div", "stage", `
    <div class="sid">${s.id}</div>
    <div class="snm">${s.name}</div>
    <div class="sdet">${s.detail}</div>
    <div class="sres">${s.result.replace(/#7\s*&rarr;\s*#1|#7 -> #1/, '').replace('#7 → #1','')}</div>`));
});
// inject the rank badge into L3 + OUT results for emphasis
const stageEls = [...casc.querySelectorAll(".stage")];
stageEls[2].querySelector(".sres").innerHTML = 'Gene X corroborated — PPI with UBE3A + academic-screen hit &rarr; re-ranked <span class="rank-badge">#7 → #1</span>.';
stageEls[3].querySelector(".sres").innerHTML = 'Gene X <span class="rank-badge">#1</span> with provenance. Confidence: <b>HIGH</b>.';

const sleep = ms => new Promise(r => setTimeout(r, ms));
let cascadeRunning = false;
async function runCascade() {
  if (cascadeRunning) return;            // guard against overlapping runs (auto-run + manual click)
  cascadeRunning = true;
  const btn = $("#runBtn"); btn.disabled = true;
  stageEls.forEach(s => s.classList.remove("lit"));
  spike.style.transition = "none"; spike.style.opacity = "0";
  await sleep(60);
  for (let i = 0; i < stageEls.length; i++) {
    const s = stageEls[i];
    const cx = s.offsetLeft + s.offsetWidth / 2, cy = s.offsetTop + 26;
    spike.style.transition = "left .55s cubic-bezier(.5,0,.3,1), top .55s, background .4s, box-shadow .4s";
    spike.style.opacity = "1"; spike.style.left = cx + "px"; spike.style.top = cy + "px";
    // tint spike to the stage colour
    const tint = getComputedStyle(s).getPropertyValue("--sc").trim();
    spike.style.background = tint; spike.style.boxShadow = `0 0 16px 4px ${tint}`;
    await sleep(560);
    s.classList.add("lit");
    await sleep(620);
  }
  await sleep(300); spike.style.opacity = "0";
  btn.disabled = false; cascadeRunning = false;
}
$("#runBtn").onclick = runCascade;
// auto-run once when scrolled into view
new IntersectionObserver((es, o) => {
  es.forEach(e => { if (e.isIntersecting) { runCascade(); o.disconnect(); } });
}, { threshold: .4 }).observe($("#system"));

/* ---------- data layers ---------- */
const lwrap = $("#layers");
Object.entries(D.layers).forEach(([name, info], i) => {
  const srcs = info.sources.map(([n, f, t]) =>
    `<div class="src"><span class="sn">${n}</span>
       <span class="sf">${f}<span class="tierdot t${t}"></span></span></div>`).join("");
  const node = el("div", "layer" + (i === 0 ? " open" : ""), `
    <div class="layer-top">
      <h3>${name}</h3>
      <div class="lblurb">${info.blurb}</div>
    </div>
    <div class="srcs">${srcs}</div>
    <div class="ltoggle">${info.sources.length} sources &middot; tap to ${i === 0 ? "collapse" : "expand"}</div>`);
  node.dataset.l = name;
  const toggle = () => node.classList.toggle("open");
  node.querySelector(".layer-top").onclick = toggle;
  node.querySelector(".ltoggle").onclick = toggle;
  lwrap.append(node);
});

/* ---------- capabilities ---------- */
const statusKey = s => /Gap/.test(s) ? "Gap" : /Tested/.test(s) ? "Tested" : /Native/.test(s) ? "Native" : "Untested";
const layerKey = l => l.split(/[ +/]/)[0];   // Internal / Context / Predictivity / Meta

const cardsWrap = $("#cards");
function renderCards(fLayer, fStatus) {
  cardsWrap.innerHTML = "";
  D.capabilities.filter(c =>
    (fLayer === "All" || c.layer.includes(fLayer)) &&
    (fStatus === "All" || c.status.includes(fStatus))
  ).forEach(c => {
    const sk = statusKey(c.status);
    const card = el("div", "card", `
      <span class="cpc">${c.promptCount} prompts</span>
      <div class="card-id">${c.id}</div>
      <h3>${c.area}</h3>
      <div class="card-meta">
        <span class="badge layer">${layerKey(c.layer)}</span>
        <span class="badge b-${sk}">${c.status}</span>
      </div>`);
    card.dataset.layer = c.layer;
    card.onclick = () => openDrawer(c);
    cardsWrap.append(card);
  });
}
// filter buttons
const FILTERS = {
  layer: ["All", "Internal", "Context", "Predictivity", "Meta"],
  status: ["All", "Tested", "Native", "Untested", "Gap"],
};
const sel = { layer: "All", status: "All" };
document.querySelectorAll(".filter-group").forEach(g => {
  const grp = g.dataset.group;
  FILTERS[grp].forEach((v, i) => {
    const b = el("button", "fbtn" + (i === 0 ? " on" : ""), v);
    b.onclick = () => {
      g.querySelectorAll(".fbtn").forEach(x => x.classList.remove("on"));
      b.classList.add("on"); sel[grp] = v; renderCards(sel.layer, sel.status);
    };
    g.append(b);
  });
});
renderCards("All", "All");

/* ---------- drawer ---------- */
const drawer = $("#drawer"), scrim = $("#scrim");
function diseaseBars(td) {
  if (!td || !td.length) return "";
  const max = Math.max(...td.map(d => d[1]));
  return `<div class="drow"><div class="dk">Where it shows up (prompts)</div><div class="dis-bars">` +
    td.map(([n, c]) => `<div class="dis-bar"><span class="dn">${n}</span>
      <span class="bar" style="width:${Math.max(8, c / max * 100)}%"></span>
      <span class="dc">${c}</span></div>`).join("") + `</div></div>`;
}
function row(k, v, mono) { return v && v !== "—" ? `<div class="drow"><div class="dk">${k}</div><div class="dv${mono ? " mono" : ""}">${v}</div></div>` : ""; }
function openDrawer(c) {
  const sk = statusKey(c.status);
  drawer.innerHTML = `
    <span class="dclose" id="dclose">close ✕</span>
    <div class="did" style="color:var(--${sk === 'Gap' ? 'gap' : sk === 'Tested' ? 'boost' : sk === 'Native' ? 'quiver' : 'gold'})">${c.id} · ${layerKey(c.layer)} layer</div>
    <h2>${c.area}</h2>
    <p class="ddesc">${c.desc}</p>
    <div class="card-meta" style="margin-bottom:22px">
      <span class="badge layer" style="color:var(--${layerKey(c.layer) === 'Context' ? 'gate' : layerKey(c.layer) === 'Predictivity' ? 'boost' : layerKey(c.layer) === 'Meta' ? 'gold' : 'signal'})">${c.layer}</span>
      <span class="badge b-${sk}">${c.status}</span>
    </div>
    ${row("Quiver data needed", c.quiverData)}
    ${row("Candidate models / tools", c.models, true)}
    ${row("Key external data / tools", c.external, true)}
    ${c.verdict && c.verdict !== "—" ? `<div class="drow"><div class="dk">Empirical verdict</div><div class="verdict">${c.verdict}</div></div>` : ""}
    ${c.gap && c.gap !== "—" ? `<div class="drow"><div class="dk">Gap → build</div><div class="gapbox">${c.gap}</div></div>` : ""}
    ${row("Representative prompts", c.repPrompts, true)}
    ${diseaseBars(c.topDiseases)}`;
  drawer.hidden = false; scrim.hidden = false;
  $("#dclose").onclick = closeDrawer;
}
function closeDrawer() { drawer.hidden = true; scrim.hidden = true; }
scrim.onclick = closeDrawer;
document.addEventListener("keydown", e => { if (e.key === "Escape") closeDrawer(); });

/* ---------- nav active state ---------- */
const secs = [...document.querySelectorAll("section[id]")];
new IntersectionObserver(es => es.forEach(e => {
  if (e.isIntersecting) document.querySelectorAll(".nav-links a").forEach(a =>
    a.style.color = a.getAttribute("href") === "#" + e.target.id ? "var(--signal)" : "");
}), { rootMargin: "-45% 0px -50% 0px" }).observe(secs.find(s => s.id === "method")) ||
  secs.forEach(s => new IntersectionObserver(es => es.forEach(e => {
    if (e.isIntersecting) document.querySelectorAll(".nav-links a").forEach(a =>
      a.style.color = a.getAttribute("href") === "#" + e.target.id ? "var(--signal)" : "");
  }), { rootMargin: "-45% 0px -50% 0px" }).observe(s));
