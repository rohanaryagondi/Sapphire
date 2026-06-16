// Auto-generated from sapphire-orchestrator/ by _build/build_orch_data.py
window.SAPPHIRE_ORCH = {
  "scenarios": [
    {
      "id": "nav1_8",
      "title": "Nav1.8 / SCN10A neuropathic-pain network",
      "query": "Prioritize novel analgesic targets in the peripheral sensory-neuron / Nav1.8 network for a systemic neuropathic-pain program.",
      "headline": "The moat's #7 (SCN11A / Nav1.9) is promoted to #1 — then the persona panel converges on one gating risk.",
      "discover": {
        "source": "EMET (live in the cascade) + internal moat (mock)",
        "summary": "Internal moat ranked SCN11A/Nav1.9 at #7 (ultra-slow persistent current under-detected by the optical-EP assay). EMET gate vetoed CACNA2D1 & NGF (CRITICAL safety), demoted TRPV1 (class hyperthermia); EMET boost promoted SCN11A on strong Mendelian FEPS3 genetics + SAFE class (PMID 26243570).",
        "result": "SCN11A/Nav1.9: #7 → #1 (SAFE + FEPS3 genetics). CACNA2D1, NGF removed."
      },
      "validate": {
        "source": "Q-Models launchpad (MOCK; AWS later)",
        "runs": [
          {
            "model": "Boltz-2",
            "out": "pKd 7.2, prob_binder 0.88 — binds; BUT Nav1.5 cross-pKd 6.9 (~2× selectivity vs >100× needed)"
          },
          {
            "model": "Quiver ion-channel fine-tune",
            "out": "Nav1.9 correctly #1/9 paralogs, but Nav1.5 margin weak"
          },
          {
            "model": "CardioGenAI",
            "out": "moderate hERG, elevated Nav1.5 risk"
          }
        ],
        "result": "Bindable, but cardiac (Nav1.5/hERG) selectivity is the hard, quantified gate."
      },
      "panel": [
        {
          "persona": "Dr. Robin Sherrington, Xenon Pharmaceuticals",
          "role": "EVP Strategy & Innovation",
          "lens": "scientific",
          "stance": "conditional",
          "conviction": 3,
          "headline": "Genetics and safety are real; cardiac selectivity is unproven and gating",
          "rationale": "The SCN11A/Nav1.9 promotion rests on credible pillars: SAFE EMET class with LoF tolerability and no clinical tox (PMID 26243570) plus strong FEPS3 Mendelian genetics (0.89), which appropriately rescue a target the optical-EP moat under-detected. But Boltz-2 shows only ~2× Nav1.5 sparing (pKd 7.2 vs 6.9) against a >100× bar, and CardioGenAI flags elevated Nav1.5 plus moderate hERG — for a systemic program this is a cardiac-liability showstopper. SAFE is also provisional: no clinical-stage Nav1.9 inhibitor exists.",
          "top_risk": "Nav1.5 cross-reactivity (~2× vs >100× needed) — systemic cardiac arrhythmia risk",
          "ask": "Resolve Nav1.9 persistent-current in the oEP assay and demonstrate >100× functional Nav1.5 sparing for a lead chemotype before greenlight"
        },
        {
          "persona": "Dr. Henrik Sorensen, H. Lundbeck A/S",
          "role": "SVP, External Innovation & BD",
          "lens": "commercial",
          "stance": "conditional",
          "conviction": 3,
          "headline": "Genuine whitespace, Mendelian-validated, but selectivity gap blocks a deal today",
          "rationale": "Nav1.9/SCN11A is real non-opioid pain whitespace versus the crowded, already-prosecuted Nav1.7/Nav1.8 field, and the FEPS3 genetics (0.89) plus the panel's only SAFE classification give a clean genetic-basis story that fits our focused-innovator heritage. But as a ~$3B player I won't win a bidding war on a hot pain asset, and the ~2× vs >100× Nav1.5 selectivity gap is a hard chemistry liability that kills value if unresolved.",
          "top_risk": "~2× vs >100× cardiac Nav1.5 selectivity gap — no clinical precedent",
          "ask": "Option/research-collab (sub-$50M upfront, milestone-heavy) gated on the oEP experiment establishing >100× Nav1.5 sparing"
        },
        {
          "persona": "Dr. Sam Ostrowski, RA Capital Management",
          "role": "Managing Director, Neuroscience",
          "lens": "investability",
          "stance": "conditional",
          "conviction": 4,
          "headline": "Fundable first-in-class story gated entirely on cardiac selectivity",
          "rationale": "Exactly the asymmetric setup I look for: clean human-genetics validation (Mendelian FEPS3 GoF, PMID 26243570) de-risks the biology, and a SAFE profile with no clinical-stage Nav1.9 inhibitor gives genuine first-in-class whitespace. But the thesis lives or dies on the Boltz-2 ~2× Nav1.5 selectivity vs the >100× a systemic analgesic needs — that gap is the kill-or-cure milestone. The same oEP assay that under-detected this must first prove it can quantify Nav1.9 pharmacology.",
          "top_risk": "Cardiac Nav1.5 liability: ~2× measured vs >100× required",
          "ask": "A real chemical series showing >100× Nav1.5-sparing Nav1.9 block in a validated oEP assay — that single gate would make me lead a Series A"
        },
        {
          "persona": "Dr. Sarah Sheikh, Takeda",
          "role": "Head, Neuroscience TAU",
          "lens": "regulatory",
          "stance": "conditional",
          "conviction": 3,
          "headline": "Genetics is compelling; Nav1.5 selectivity is the clinical-hold gate",
          "rationale": "The FEPS3 GoF genetics (0.89) is genuine human Mendelian validation, and SCN11A's SAFE class (PMID 26243570) is the cleanest in the panel — far better than the correctly vetoed NGF (RPOA, PMID 37652258) and CACNA2D1 (respiratory depression). But Boltz-2 gives ~2× Nav1.5 cross-reactivity where >100× is required, and CardioGenAI flags hERG + Nav1.5 — a proarrhythmia profile that draws a clinical hold or QT-driven dose cap before efficacy is testable.",
          "top_risk": "Insufficient cardiac selectivity → proarrhythmia clinical-hold liability",
          "ask": "Patch-clamp Nav1.9-vs-Nav1.5 panel showing >100× sparing, hERG + iPSC-cardiomyocyte data, and an oEP target-engagement biomarker before FIH dosing"
        }
      ],
      "synthesize": {
        "recommendation": "Advance SCN11A / Nav1.9 to a focused cardiac-selectivity de-risking experiment — not yet to a full program. Structure any external deal as option / milestone-heavy.",
        "consensus": "Unanimous: the #7→#1 promotion is scientifically sound — human Mendelian genetics + the panel's only SAFE class make Nav1.9 genuine first-in-class non-opioid pain whitespace.",
        "dissent": "Low divergence. Conviction 3 (Xenon, Lundbeck, Takeda) vs 4 (RA Capital — weights the asymmetric first-in-class upside higher). No champion, no veto — all four 'conditional'.",
        "convergent_gate": "All four independently flagged the SAME risk: cardiac Nav1.5 selectivity (~2× measured vs >100× needed).",
        "proposed_experiment": "Resolve Nav1.9's persistent current in Quiver's oEP assay (the signal the moat under-detected) AND demonstrate >100× functional Nav1.5 sparing for a lead chemotype — closing the active-learning loop on the moat's own blind spot.",
        "confidence": "Biology: HIGH. Overall program: CONDITIONAL on the selectivity gate."
      }
    },
    {
      "id": "tsc2",
      "title": "TSC2 / mTOR network — tuberous sclerosis",
      "query": "Prioritize novel targets to normalize TSC2-loss mTORC1 hyperactivation for a tuberous-sclerosis CNS program (chronic paediatric + adult dosing).",
      "headline": "The moat's #7 (RHEB) becomes the #1 novel target — then the panel reframes it from a small molecule to a genetic medicine.",
      "discover": {
        "source": "EMET (live in the cascade) + internal moat (mock)",
        "summary": "Internal moat ranked RHEB at #7 (small GTPase, subtle functional signature). EMET gate vetoed PPARD (CRITICAL carcinogenicity), flagged MTOR (everolimus immunosuppression/growth, PMID 31335226). EMET boost promoted RHEB on near-perfect PPI-to-mTOR (0.999) + 2nd somatic cause of FCD. DEPDC5 (best Mendelian genetics) abstained as intractable.",
        "result": "RHEB: #7 → #1 novel actionable. MTOR = incumbent (set aside). PPARD removed. DEPDC5 abstained."
      },
      "validate": {
        "source": "Q-Models launchpad (MOCK; AWS later)",
        "runs": [
          {
            "model": "Boltz-2",
            "out": "pKd 5.4, prob_binder 0.41 — weak; shallow GTPase pocket"
          },
          {
            "model": "ATOMICA dock",
            "out": "dock score -6.1, shallow solvent-exposed pose — no deep druggable pocket"
          },
          {
            "model": "ADMET-AI",
            "out": "clean tox (low DILI/hERG), BBB borderline — but moot until ligandability solved"
          }
        ],
        "result": "Genetically + network validated, but small-molecule ligandability is HARD → points to an ASO / degrader modality."
      },
      "panel": [
        {
          "persona": "Dr. Ryan Watts, Denali Therapeutics",
          "role": "CEO & Co-Founder",
          "lens": "scientific",
          "stance": "conditional",
          "conviction": 4,
          "headline": "RHEB biology is right; deliver it as a CNS-penetrant modality",
          "rationale": "RHEB is the cleanest node downstream of TSC2 loss — a selective RHEB inhibitor sits directly above mTORC1 and should phenocopy rapalog efficacy while plausibly sparing the pan-mTOR immunosuppression and growth impairment that limit everolimus in children. But Boltz-2 pKd 5.4 / prob_binder 0.41 and a shallow solvent-exposed ATOMICA pose mean small-molecule ligandability is genuinely hard. This is an ASO/degrader problem — and for chronic paediatric CNS dosing the chemistry is moot unless you solve BBB delivery (a TfR transcytosis platform earns its keep here).",
          "top_risk": "A degrader/ASO that knocks down RHEB but can't be delivered across the BBB at safe, repeat-dosable paediatric exposures",
          "ask": "Confirm RHEB knockdown (ASO/degrader, not FTI) normalizes the oEP hyperexcitability signature, then a CNS PK/PD study showing brain target engagement with a BBB-delivery vehicle"
        },
        {
          "persona": "Dr. James Chen, BioMarin",
          "role": "EVP, Chief Business Officer",
          "lens": "commercial",
          "stance": "conditional",
          "conviction": 3,
          "headline": "Novel node-specific mechanism, but modality risk gates the deal",
          "rationale": "TSC is a genetically defined orphan indication with a validated axis and an assessable phenotype (oEP excitability) — squarely our model. RHEB's appeal is differentiation: a node-specific play downstream of TSC2 that dodges everolimus's pan-mTOR immunosuppression and growth impairment (50,182 FAERS). But Boltz-2 pKd 5.4 with a shallow pocket points to ASO/degrader — a genetic-medicine model with chronic CNS-delivery and reimbursement burdens, and safety is inferred (MONITOR), not clinical.",
          "top_risk": "Ligandability-hard target forces an unproven CNS ASO/degrader with no clinical RHEB safety read",
          "ask": "Quiver oEP proof that RHEB modulation normalizes excitability + a node-specific safety margin vs pan-mTOR + a deliverable CNS modality; structured option/milestone-heavy"
        },
        {
          "persona": "Dr. Catherine Brennan, Third Rock Ventures",
          "role": "Partner, Neuroscience",
          "lens": "investability",
          "stance": "conditional",
          "conviction": 3,
          "headline": "Fundable genetic-medicine NewCo if RHEB ligandability becomes a platform",
          "rationale": "RHEB has what I underwrite: human genetic validation (2nd somatic cause of FCD), near-perfect mechanistic coupling (PPI-to-mTOR 0.999), clean ADMET, and a node-specific thesis that could spare everolimus's paediatric liabilities. But Boltz-2 pKd 5.4 / 0.41 and shallow docking say small molecule is HARD — so the bet is a genetic-medicine modality platform across the TSC2/mTOR axis (RHEB now, DEPDC5 GATOR1-reactivation later), not a single asset.",
          "top_risk": "Ligandability failure: weak pocket forces an unproven CNS ASO/degrader with inferred safety",
          "ask": "Show RHEB knockdown normalizes the oEP phenotype AND a node-specific safety margin vs pan-mTOR, with a credible CNS delivery/CMC plan, before I anchor a launch round"
        },
        {
          "persona": "Dr. Sarah Sheikh, Takeda",
          "role": "Head, Neuroscience TAU",
          "lens": "regulatory",
          "stance": "conditional",
          "conviction": 3,
          "headline": "Node-specific RHEB plausibly safer than mTOR; modality risk unproven",
          "rationale": "In chronic paediatric TSC, everolimus's WARNING-class liabilities are the bar: immunosuppression, vaccine blunting, growth impairment (50,182 FAERS; PMID 31335226) are unacceptable over years in a developing child. A node-specific RHEB inhibitor downstream of TSC2 plausibly spares that — a genuinely differentiated safety thesis. But RHEB is MONITOR-class with no clinical inhibitor (safety inferred), and it's ligandability-hard (Boltz-2 pKd 5.4), forcing an unproven CNS ASO/degrader. Research commitment, not a development decision.",
          "top_risk": "Inferred-only RHEB safety + chronic intrathecal ASO in children = unproven long-term CNS/developmental risk",
          "ask": "Head-to-head juvenile-animal tox (RHEB modulation vs pan-mTOR: immune competence, growth, neurodevelopment) + chronic intrathecal ASO CNS tolerability, plus oEP phenotype normalization"
        }
      ],
      "synthesize": {
        "recommendation": "Pursue RHEB as a genetic-medicine (ASO / degrader) platform bet on the TSC2–mTOR axis — a research commitment, not a small-molecule program.",
        "consensus": "Unanimous: RHEB biology is right (node-specific downstream of TSC2, PPI 0.999, 2nd somatic FCD cause) and could spare everolimus's pan-mTOR paediatric liabilities.",
        "dissent": "Low divergence. Conviction 4 (Denali — sees direct BBB-platform fit) vs 3 (BioMarin, Third Rock, Takeda — gate on modality + paediatric safety). No champion, no veto.",
        "convergent_gate": "All four independently reframed the target: small-molecule ligandability is the blocker (Boltz-2 pKd 5.4, shallow pocket) → the modality must be ASO/degrader, and CNS delivery + paediatric chronic safety are the real gates.",
        "proposed_experiment": "Show RHEB knockdown/degradation normalizes the oEP excitability phenotype the moat under-resolved, with a node-specific safety margin vs pan-mTOR and a credible CNS-delivery (BBB) plan for the chosen modality.",
        "confidence": "Biology: HIGH. Modality / feasibility: CONDITIONAL — reframed from inhibitor to genetic medicine."
      }
    }
  ],
  "catalog": [
    {
      "id": "boltz-2",
      "task": "binding_affinity",
      "name": "Boltz-2",
      "inputs": [
        "target_seq",
        "ligand_smiles"
      ],
      "outputs": [
        "pKd",
        "prob_binder",
        "selectivity_vs_offtarget"
      ],
      "hardware": "GPU (g4dn/g5)",
      "status": "mock",
      "real_script": "aws/boltz_runner.py",
      "note": "AF3-class co-folding + affinity head; the cascade already proved it runs on a T4."
    },
    {
      "id": "admet-ai",
      "task": "admet",
      "name": "ADMET-AI",
      "inputs": [
        "ligand_smiles"
      ],
      "outputs": [
        "BBB",
        "DILI",
        "hERG",
        "CYP",
        "clearance"
      ],
      "hardware": "CPU",
      "status": "mock",
      "real_script": "aws/comprehensive_admet_char.py",
      "note": "calibrated ADMET; preferred over MAMMAL ClinTox (Q-Mammal)."
    },
    {
      "id": "cardiogenai",
      "task": "cardiotoxicity",
      "name": "CardioGenAI",
      "inputs": [
        "ligand_smiles"
      ],
      "outputs": [
        "hERG_risk",
        "Nav1.5_risk",
        "Cav1.2_risk"
      ],
      "hardware": "GPU",
      "status": "mock",
      "real_script": "aws/cardiogenai_eval.py",
      "note": "cardiac ion-channel liability profiler."
    },
    {
      "id": "cns-dti",
      "task": "dti_triage",
      "name": "CNS DTI head",
      "inputs": [
        "target_seq",
        "ligand_smiles"
      ],
      "outputs": [
        "binding_prob"
      ],
      "hardware": "GPU",
      "status": "mock",
      "real_script": "aws/cns_dti_benchmark_eval.py",
      "note": "single-target triage; off-the-shelf ~chance on Nav (Q-Mammal) — Quiver fine-tune is the lever."
    },
    {
      "id": "ionchannel-ft",
      "task": "channel_selectivity",
      "name": "Quiver ion-channel fine-tune",
      "inputs": [
        "target_seq",
        "ligand_smiles",
        "paralog_panel"
      ],
      "outputs": [
        "selectivity_profile"
      ],
      "hardware": "GPU",
      "status": "mock",
      "real_script": "aws/ionchannel_finetune_eval.py",
      "note": "QUIVER-DATA fine-tune — the one place a trained head beats off-the-shelf."
    },
    {
      "id": "atomica-dock",
      "task": "docking",
      "name": "ATOMICA dock",
      "inputs": [
        "target_struct",
        "ligand_smiles"
      ],
      "outputs": [
        "pose",
        "dock_score"
      ],
      "hardware": "GPU",
      "status": "mock",
      "real_script": "aws/atomica_dock_nav18_eval.py"
    },
    {
      "id": "esm-embed",
      "task": "embedding",
      "name": "ESM-2 / Ankh",
      "inputs": [
        "protein_seq"
      ],
      "outputs": [
        "embedding",
        "family_cluster"
      ],
      "hardware": "GPU",
      "status": "mock",
      "real_script": "aws/esm2_big_layer_sweep.py",
      "note": "protein-family embeddings; ties/edges MAMMAL (Q-Mammal)."
    }
  ]
};
