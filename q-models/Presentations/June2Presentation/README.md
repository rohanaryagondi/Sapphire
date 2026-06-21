# June 2 Presentation — MAMMAL evaluation overview

Internal Quiver deck presenting the IBM MAMMAL evaluation, built to hand off into a **live UI demo**
(run separately at `localhost:8000`). Audience = Quiver scientists. Bar = empirical results on our
problems, not paper benchmarks.

- **Deck:** [`MAMMAL_overview.pptx`](MAMMAL_overview.pptx) — 6 slides
- **Rebuild:** [`source/`](source) (pptxgenjs script + brand image assets)
- **Presenter:** Rohan Aryagondi · June 2026

---

## Deck structure (6 slides)

| # | Slide | One-line speaker cue |
|---|-------|----------------------|
| 1 | **Title** | "Does MAMMAL work on *our* problems, out of the box — tool, enrichment, or Sapphire's latent layer?" |
| 2 | **What MAMMAL is** | "One 458M model, 2B+ samples, 3 modalities, 9 public heads — antibody/PPI-generation heads aren't public." |
| 3 | **What I've done** | "Tested on our tasks not leaderboards; the paper reproduces honestly; built the Explorer UI; the win was fixing the I/O." |
| 4 | **GOOD at — by UI category** | "Walk the UI tabs that work: embeddings, solubility, TCR, PPI, and BBBP as a *qualified* soft-positive." |
| 5 | **BAD at — by UI category** | "The UI tabs to distrust: DTI single-target, ClinTox, generation, cross-modal embeddings, FDA." |
| 6 | **Verdict** | "Commodity enrichment, not core infrastructure — the moat stays V1-T + functional trace data." |

The deck **ends before the demo** by design — slide 3's "How it works" prompt-syntax diagram and the
UI demo are presented live, not on slides.

---

## The three headline verdicts (do not soften)

1. **Commodity enrichment, not a binding oracle.** Useful de-risking + representation layer; single-target
   binder triage ≈ chance.
2. **The Sapphire cross-modal pitch is falsified off-the-shelf.** Protein & SMILES embeddings are
   near-orthogonal (cosine 0.08) — no shared space where a target and its ligands are neighbors.
3. **ClinTox is unusable.** Memorization, 0% sensitivity to external clinical toxics. Don't gate on it.

## Numbers — source of truth

Every figure is verified against, and must stay consistent with:
- `docs/COMPLETE_UNDERSTANDING.md` (master synthesis — §5 scorecard)
- `CLAUDE.md` (one-line verdicts)
- `docs/ui_spec.md §2` (the reliability table the UI renders)

Key values used: embeddings NN recall **0.92** vs ESM-2 650M **0.84**; solubility AUROC **0.83**;
BBBP AUROC **0.97** with TNR **0.70** (over-calls "crosses"); TCR **0.93**; PGK2 homolog selectivity
**0.97**; DTI cross-target Spearman **0.43** (~9% over the mean), single-target ≈ chance,
suzetrigine→Nav1.8 fails; cross-modal cosine **0.08**; ClinTox **0%** external sensitivity; generation
**1/8** exact recovery; FDA benchmark ~**94%** positive. **Keep these exact — the project's bar is empirical.**

GOOD/BAD slides map **one bullet per UI category** so each lines up with a demo tab and its reliability
badge (✅ reliable · ⚠️ caution · ❌ don't use · ➖ low value). Embeddings appears on *both* slides on
purpose — family clustering ✅, cross-modal/shared-latent-space ❌ — mirroring the UI's own split.

---

## Design / branding

Built with the **`quiver-branding`** skill (Quiver colors, Poppins, emblem bottom-right, gradient title).
- Title slide = signature gradient (purple `#9C02FA` → magenta `#C20CA9` → red `#F51D3F`).
- Content slides = **white** background, purple-bordered rounded title box, **simple bullet points**.
- Body text is plain black; **Quiver purple** is used only for the bolded lead phrase of each bullet.

## Feedback that shaped this deck (Rohan, June 2)

Captured so the next revision doesn't undo these decisions:
- **Brief, numbers over adjectives.** ~6 slides, scientist audience, end into the live demo.
- **Removed** the "How it works" prompt-syntax diagram slide and the dedicated "UI → live demo" slide —
  *those are demoed live*, not on slides.
- **Backgrounds must be white**, not pale lavender/pink; no navy content slides. Keep one consistent scheme.
- **Basic PowerPoint.** Simple bullet points — no cards, accent bars, or stat sidebars. No colored body
  text *except* Quiver purple in spots for bolding.
- **Clarity over compression on GOOD/BAD.** State *what each head predicts* and *what the number means* —
  e.g. don't write "solubility AUROC 0.83" without saying it predicts soluble-vs-not; explain why a
  near-perfect BBBP 0.97 is still only a *soft* positive (it over-calls "crosses" + hard yes/no).
- **One bullet per UI category** on the GOOD/BAD slides, so they line up with the demo tabs.
- **Added** a "What I've done" slide before the GOOD/BAD slides.

---

## Rebuild

Requires Node + `pptxgenjs` (global). From this folder:

```bash
cd source
export NODE_PATH=$(npm root -g)
node build.js          # writes MAMMAL_overview.pptx into source/
```

Render for visual QA (LibreOffice + Poppler):

```bash
"/Applications/LibreOffice.app/Contents/MacOS/soffice" --headless --convert-to pdf MAMMAL_overview.pptx
pdftoppm -jpeg -r 110 MAMMAL_overview.pdf slide
```

**Note on bullets:** the bullet dots are literal `•` glyphs (not PowerPoint's auto-bullet engine) so they
render identically in PowerPoint/Keynote/LibreOffice. If you edit bullet text in PowerPoint, the `•` is
part of the line rather than an auto-bullet — swap to native bullets if you prefer that for editing.
