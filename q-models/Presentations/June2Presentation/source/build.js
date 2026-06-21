const pptxgen = require("pptxgenjs");
const p = new pptxgen();
p.defineLayout({ name: "QW", width: 10, height: 5.625 });
p.layout = "QW";

// ---- Brand palette ----
const PURPLE="9C02FA", RED="F51D3F", MAGENTA="C20CA9", DARKP="7300BF",
      WHITE="FFFFFF", INK="1A1A24", GREY="55556A";
const FONT="Poppins";
const LOGO="quiver_logo_slide_white.png",
      EMB_W="quiver_emblem_white.png", EMB_C="quiver_emblem_color.png",
      BG_GRAD="bg_gradient.png";

// ---- helpers ----
function emblem(s){ s.addImage({ path:EMB_C, x:9.30, y:5.02, w:0.40, h:0.32 }); }
function pageno(s, n){ s.addText(String(n), { x:8.75, y:5.05, w:0.4, h:0.25,
  fontFace:FONT, fontSize:9, color:GREY, align:"right" }); }
function titleBox(s, txt, w){
  s.addText(txt, { x:0.45, y:0.34, w:w||7.8, h:0.62, rectRadius:0.10, shape:"roundRect",
    line:{ color:PURPLE, width:1.5 }, fill:{ type:"none" },
    fontFace:FONT, fontSize:22, bold:true, color:INK,
    align:"left", valign:"middle", margin:[2,10,2,10] });
}
// Simple bullet list: each item = {lead, body}; "•" + bold-purple lead, then black body.
function bulletList(s, items, o){
  const runs=[];
  items.forEach((it,idx)=>{
    const last = idx===items.length-1;
    runs.push({ text: "•   "+it.lead, options:{ bold:true,
      color:PURPLE, fontFace:FONT, fontSize:o.fs, breakLine:false } });
    runs.push({ text: it.body, options:{ color:INK, fontFace:FONT, fontSize:o.fs,
      breakLine:true, paraSpaceAfter: last?0:(o.sp!=null?o.sp:16) } });
  });
  s.addText(runs, { x:o.x, y:o.y, w:o.w, h:o.h, valign:"top", lineSpacingMultiple:1.04 });
}

// =========================================================
// SLIDE 1 — TITLE (gradient)
// =========================================================
let s = p.addSlide();
s.background = { path: BG_GRAD };
s.addImage({ path:LOGO, x:0.45, y:0.40, w:2.10, h:2.10*(179/2048) });
s.addText("Evaluating IBM MAMMAL\nfor Quiver", {
  x:0.45, y:1.85, w:8.6, h:1.5, fontFace:FONT, fontSize:40, bold:true,
  color:WHITE, align:"left", lineSpacingMultiple:1.0 });
s.addText("Does it work on our problems — out of the box?", {
  x:0.47, y:3.30, w:8.6, h:0.5, fontFace:FONT, fontSize:18, color:WHITE, align:"left" });
s.addText("Workflow tool  ·  occasional enrichment  ·  or Sapphire's shared latent-space layer?", {
  x:0.47, y:3.86, w:8.6, h:0.4, fontFace:FONT, fontSize:12.5, italic:true,
  color:"F3E3FF", align:"left" });
s.addText("Rohan Aryagondi   ·   June 2026", {
  x:0.47, y:4.85, w:3.5, h:0.40, rectRadius:0.20, shape:"roundRect",
  line:{ color:WHITE, width:1 }, fill:{ type:"none" },
  fontFace:FONT, fontSize:11.5, color:WHITE, align:"center", valign:"middle" });
s.addImage({ path:EMB_W, x:9.30, y:5.02, w:0.40, h:0.32 });

// =========================================================
// SLIDE 2 — WHAT MAMMAL IS
// =========================================================
s = p.addSlide();
s.background = { color: WHITE };
titleBox(s, "What MAMMAL is");
bulletList(s, [
  { lead:"Foundation model, 458M params", body:" — IBM biomedical model biomed.omics.bl.sm.ma-ted-458m." },
  { lead:"2B+ samples, 3 modalities", body:" — proteins, small molecules, single-cell genes." },
  { lead:"One model, many tasks", body:" — a prompt syntax that does classify / regress / generate, within or across modalities." },
  { lead:"Base model + 9 task heads", body:" — the public release; the paper's antibody-design & PPI-generation heads are not public." },
], { x:0.55, y:1.45, w:8.9, h:3.4, fs:16, sp:18 });
emblem(s); pageno(s,2);

// =========================================================
// SLIDE 3 — WHAT I'VE DONE
// =========================================================
s = p.addSlide();
s.background = { color: WHITE };
titleBox(s, "What I've done");
bulletList(s, [
  { lead:"Tested it on our tasks, not leaderboards", body:" — Phases 0–6 plus an in-house fine-tune pilot on AWS (~$0.80)." },
  { lead:"Confirmed the paper is honest", body:" — every public head reproduces: DTI NRMSE 0.88, BBBP 0.968, TCR 0.931, ClinTox ~1.0." },
  { lead:"Built the Quiver MAMMAL Explorer", body:" — a UI exposing every public head with our empirical reliability verdict on each prediction." },
  { lead:"Meta-lesson", body:" — naive eval gives false negatives; we flipped our own conclusions 3× by fixing the I/O, not the model." },
], { x:0.55, y:1.45, w:8.9, h:3.4, fs:16, sp:18 });
emblem(s); pageno(s,3);

// =========================================================
// SLIDE 4 — WHAT IT'S GOOD AT (one bullet per UI category)
// =========================================================
s = p.addSlide();
s.background = { color: WHITE };
titleBox(s, "What it's GOOD at — by UI category");
bulletList(s, [
  { lead:"Protein / gene embeddings", body:" — places same-family proteins together (right family retrieved 92% of the time, beating ESM-2 650M's 84%). Use for CRISPR-N clustering and the KG." },
  { lead:"Protein solubility", body:" — predicts soluble vs not at AUROC 0.83, on par with the dedicated DeepSol model. Calibrated." },
  { lead:"TCR–epitope binding", body:" — does a T-cell receptor bind a given epitope? AUROC 0.93, calibrated. Immuno-oncology, peripheral to CNS." },
  { lead:"Protein–protein interaction", body:" — do two proteins interact? Paper-validated; our spot check reads P≈0.95. Reliable for clear cases." },
  { lead:"BBB penetrance", body:" — AUROC 0.97 looks near-perfect, but it over-calls \"crosses\" (catches only 70% of non-penetrant drugs) and gives a hard yes/no — so a \"crosses\" call is a soft positive, never a rule-out." },
], { x:0.55, y:1.28, w:8.9, h:3.9, fs:13, sp:10 });
emblem(s); pageno(s,4);

// =========================================================
// SLIDE 5 — WHAT IT'S BAD AT (one bullet per UI category)
// =========================================================
s = p.addSlide();
s.background = { color: WHITE };
titleBox(s, "What it's BAD at — by UI category", 8.6);
bulletList(s, [
  { lead:"Drug–target binding (DTI)", body:" — not a single-target binding oracle: on one target, binders score no better than random decoys (Nav1.8, mTOR); only coarse cross-target ranking (Spearman 0.43); suzetrigine→Nav1.8 fails." },
  { lead:"Clinical toxicity (ClinTox)", body:" — memorizes its training toxics: 0% sensitivity to external ones (misses cerivastatin, terfenadine, thalidomide). Don't gate on it." },
  { lead:"Molecule generation", body:" — span-infill only: grammar-valid analogs, 1/8 exact recovery, no de-novo design. The paper's design heads aren't public." },
  { lead:"Cross-modal embeddings", body:" — protein & SMILES vectors are near-orthogonal (cosine 0.08); no shared space where a target and its ligands are neighbors. The Sapphire \"shared latent space\" pitch is falsified." },
  { lead:"FDA approval", body:" — ~94% of the benchmark is positive, so an \"approved\" call carries little information. Sanity-check only." },
], { x:0.55, y:1.28, w:8.9, h:3.9, fs:13, sp:10 });
emblem(s); pageno(s,5);

// =========================================================
// SLIDE 6 — VERDICT
// =========================================================
s = p.addSlide();
s.background = { color: WHITE };
titleBox(s, "Verdict", 3.0);
s.addText([
  {text:"MAMMAL is ",options:{color:INK}},
  {text:"commodity enrichment, not core infrastructure",options:{color:PURPLE,bold:true}},
  {text:" — a useful de-risking + representation layer, not a binding oracle.",options:{color:INK}},
], { x:0.55, y:1.55, w:8.9, h:1.1, fontFace:FONT, fontSize:22, align:"left", valign:"top", lineSpacingMultiple:1.06 });
bulletList(s, [
  { lead:"Off-the-shelf ≠ moat", body:" — the moat stays V1-T + functional trace data." },
  { lead:"Fine-tuning only beats IBM where they have no head", body:" — i.e. Quiver targets (needs Quiver data; same base + same public data = same ceiling)." },
], { x:0.55, y:3.05, w:8.9, h:1.8, fs:15, sp:16 });
emblem(s); pageno(s,6);

p.writeFile({ fileName: "MAMMAL_overview.pptx" }).then(f=>console.log("WROTE", f));
