# ---------------------------------------------------------------------------
# Ported verbatim from MatthewCarey24/design-form-agent -- Matt Carey, Quiver
# <matthew.carey@quiverbioscience.com> (upstream afcf01b, imported 2026-06-23).
# The scientific content below (domain prompt / MENUS_REFERENCE / schema) is
# preserved CHARACTER-FOR-CHARACTER (CONVENTIONS section 4) -- do NOT paraphrase
# or edit the domain values. Canonical original: vendor/design-form-agent/.
# ---------------------------------------------------------------------------

"""
Schema for structured extraction from Quiver experiment planning meetings.

This defines what the LLM extraction step should produce from a raw Otter transcript.
The output is reviewed by the team before being used to generate Excel sheets.
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


# ── Confidence levels for extracted fields ──────────────────────────
class Confidence(str, Enum):
    HIGH = "high"        # Explicitly stated, unambiguous
    MEDIUM = "medium"    # Implied or partially stated, likely correct
    LOW = "low"          # Inferred from context, needs confirmation
    UNRESOLVED = "unresolved"  # Discussed but no decision reached


@dataclass
class ExtractedField:
    """Wraps any extracted value with confidence and source."""
    value: object
    confidence: Confidence
    source_summary: str  # Brief note on where this came from in the transcript
    timestamp: Optional[str] = None  # Approximate timestamp if available


# ── Core experiment metadata ────────────────────────────────────────
@dataclass
class ExperimentMetadata:
    project_code: Optional[ExtractedField] = None  # e.g. "QNP-012"
    experiment_title: Optional[ExtractedField] = None
    experiment_description: Optional[ExtractedField] = None
    round_number: Optional[ExtractedField] = None  # e.g. "Rd2"
    assay_type: Optional[ExtractedField] = None  # Excitability, Synaptic, Other
    sub_assay_type: Optional[ExtractedField] = None  # AMPAR, GABAR, Mixed Glutamatergic
    is_follow_up_to: Optional[str] = None  # Reference to prior experiment if applicable


# ── Culture details ─────────────────────────────────────────────────
@dataclass
class CellGenotype:
    name: ExtractedField  # e.g. "Control 11a NGN2D.S."
    density: Optional[ExtractedField] = None  # e.g. "49k/well (70%)"
    lot_number: Optional[ExtractedField] = None


@dataclass
class VirusInfo:
    name: Optional[ExtractedField] = None  # e.g. "pQS071-05"
    description: Optional[ExtractedField] = None  # e.g. "(fhSyn-Cre)"
    volume: Optional[ExtractedField] = None  # e.g. "23nL/well"


@dataclass
class CultureDetails:
    genotypes: list[CellGenotype] = field(default_factory=list)
    num_plates: Optional[ExtractedField] = None
    plate_type: Optional[ExtractedField] = None  # e.g. "96-well Ibidi"
    viruses: list[VirusInfo] = field(default_factory=list)
    glia: Optional[ExtractedField] = None  # Yes/No
    glia_addition_date: Optional[ExtractedField] = None  # e.g. "DIV-7"
    glia_density: Optional[ExtractedField] = None
    glia_lot: Optional[ExtractedField] = None


# ── Imaging details ─────────────────────────────────────────────────
@dataclass
class ImagingDetails:
    imaging_date: Optional[ExtractedField] = None
    imaging_div: Optional[ExtractedField] = None  # e.g. "DIV30", "DIV31"
    stim_protocol: Optional[ExtractedField] = None
    scan_direction: Optional[ExtractedField] = None
    fovs_per_well: Optional[ExtractedField] = None
    temperature: Optional[ExtractedField] = None
    imaging_type: Optional[ExtractedField] = None  # Single measurement, Pre/post, etc.
    imaging_buffer: Optional[ExtractedField] = None  # Tyrodes, Brainphys, etc.
    synaptic_blockers: Optional[ExtractedField] = None


# ── Treatment / compound details ────────────────────────────────────
@dataclass
class TreatmentCondition:
    compound_name: ExtractedField  # e.g. "TTX", "Diazepam", "KMeSO4"
    concentrations: list[ExtractedField] = field(default_factory=list)
    vehicle: Optional[ExtractedField] = None  # DMSO, Water, etc.
    timing: Optional[ExtractedField] = None  # e.g. "48 hours before imaging"
    addition_protocol: Optional[ExtractedField] = None  # Manual, Viaflo, Mini Janus, etc.
    purpose: Optional[str] = None  # Why this condition is being tested


@dataclass 
class PlateLayoutDescription:
    """High-level description of the plate layout. 
    Detailed well-by-well mapping is generated in step 3."""
    layout_strategy: Optional[ExtractedField] = None  # e.g. "one row per condition, standard/low/high repeating"
    conditions_per_plate: Optional[ExtractedField] = None
    controls: list[ExtractedField] = field(default_factory=list)  # e.g. vehicle, no-inhibitory-neuron control
    notes: list[str] = field(default_factory=list)


# ── Scheduling / calendar ───────────────────────────────────────────
@dataclass
class TimelineEvent:
    event: str  # e.g. "Glia plating", "Neuron plating", "Virus addition", "Treatment", "Imaging"
    relative_day: Optional[ExtractedField] = None  # e.g. "DIV-7", "DIV0", "DIV28", "DIV30"
    absolute_date: Optional[ExtractedField] = None  # e.g. "2026.01.20"
    notes: Optional[str] = None


@dataclass
class ExperimentTimeline:
    events: list[TimelineEvent] = field(default_factory=list)
    target_imaging_date: Optional[ExtractedField] = None
    plating_date: Optional[ExtractedField] = None


# ── Action items ────────────────────────────────────────────────────
@dataclass
class ActionItem:
    description: str
    assignee: Optional[str] = None  # Person responsible
    deadline: Optional[str] = None
    status: str = "pending"  # pending, in_progress, done
    priority: Optional[str] = None  # high, medium, low


# ── Open questions / unresolved decisions ───────────────────────────
@dataclass
class OpenQuestion:
    question: str
    context: str  # Why this matters
    proposed_answers: list[str] = field(default_factory=list)
    who_should_decide: Optional[str] = None


# ── Top-level extraction result ─────────────────────────────────────
@dataclass
class MeetingExtraction:
    """Complete structured extraction from one experiment planning meeting."""
    
    # Meeting metadata
    meeting_title: str
    meeting_date: str
    attendees: list[str] = field(default_factory=list)
    meeting_type: str = ""  # "initial_planning", "follow_up", "design_review", etc.
    
    # Experiment details (may be partial — that's okay)
    experiments: list['ExperimentPlan'] = field(default_factory=list)
    
    # Cross-cutting items
    action_items: list[ActionItem] = field(default_factory=list)
    open_questions: list[OpenQuestion] = field(default_factory=list)
    
    # Raw notes that don't fit schema but seem important
    additional_notes: list[str] = field(default_factory=list)


@dataclass
class ExperimentPlan:
    """One discrete experiment discussed in the meeting.
    A single meeting may discuss multiple experiments."""
    
    metadata: ExperimentMetadata = field(default_factory=ExperimentMetadata)
    culture: CultureDetails = field(default_factory=CultureDetails)
    imaging: ImagingDetails = field(default_factory=ImagingDetails)
    treatments: list[TreatmentCondition] = field(default_factory=list)
    plate_layout: PlateLayoutDescription = field(default_factory=PlateLayoutDescription)
    timeline: ExperimentTimeline = field(default_factory=ExperimentTimeline)
    analysis_notes: list[str] = field(default_factory=list)  # How they want data analyzed/plotted
    
    # Relationship to other experiments
    depends_on: list[str] = field(default_factory=list)  # Other experiments that must happen first
    can_share_plates_with: list[str] = field(default_factory=list)
