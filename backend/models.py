"""
SciForge Core Data Models (Intermediate Representation schemas)
"""
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
from pydantic.json_schema import SkipJsonSchema

class ExtractedEquation(BaseModel):
    id: str
    latex: str
    name: Optional[str] = None
    page: int = 1
    description: Optional[str] = None
    tag: str = "DERIVED"  # SOURCE, DERIVED, GENERATED, ASSUMED

class ExtractedSection(BaseModel):
    title: str
    page: int = 1
    content: str
    equations: List[str] = []

class SourceDocument(BaseModel):
    id: str
    filename: str
    num_pages: int
    raw_text: str
    sections: List[ExtractedSection] = []
    equations: List[ExtractedEquation] = []
    figures_found: int = 0
    references: List[str] = []

class ConceptNode(BaseModel):
    id: str
    name: str
    type: str  # problem, theory, assumption, equation, algorithm, experiment, interpretation
    description: str
    source_page: Optional[int] = None
    formula: Optional[str] = None

class ConceptEdge(BaseModel):
    source: str
    target: str
    relationship: str  # depends_on, implements, formalizes, tests, produces, limits

class ScientificKnowledgeGraph(BaseModel):
    nodes: List[ConceptNode] = []
    edges: List[ConceptEdge] = []
    core_problem: str
    core_thesis: str
    assumptions: List[str] = []
    limitations: List[str] = []
    # Which engine produced this graph ("template" or "provider:model"). Hidden from the
    # JSON schema because this model doubles as the LLM output schema.
    built_by: SkipJsonSchema[str] = "template"

class VisualSpec(BaseModel):
    theme: str = "blueprint"
    layout: str = "split_code_plot"  # full_equation, split_code_plot, concept_card, graph_focus, conclusion
    animation_type: str = "blueprint_grid"  # blueprint_grid, wave_oscillation, particle_flow, chalk_draw
    accent_color: Optional[str] = None
    diagram_type: Optional[str] = None

class LectureScene(BaseModel):
    id: str
    index: int
    title: str
    type: str  # hook_problem, mathematical_formulation, derivation, simulation_demo, plot_verification, engineering_application, takeaway
    duration: float = 30.0  # seconds
    narration: str
    visual_spec: VisualSpec = Field(default_factory=VisualSpec)
    equation: Optional[str] = None
    equation_tag: Optional[str] = None  # SOURCE, DERIVED, GENERATED, ASSUMED
    equation_explanation: List[str] = []
    code_snippet: Optional[str] = None
    figure_url: Optional[str] = None
    bullet_points: List[str] = []
    citation: Optional[str] = None
    audio_file: Optional[str] = None
    timestamp_start: float = 0.0
    timestamp_end: float = 30.0

class LecturePlan(BaseModel):
    project_id: str
    title: str
    topic: str
    theme: str
    persona: str
    target_audience: str
    target_duration_sec: int = 600
    actual_duration_sec: float = 0.0
    scenes: List[LectureScene] = []
    key_takeaways: List[str] = []
    youtube_metadata: Dict[str, Any] = {}
    planned_by: str = "template"  # "template" or "provider:model"

class ProjectState(BaseModel):
    id: str
    name: str
    topic: str
    theme: str = "blueprint"
    persona: str = "engineer"
    audience: str = "graduate_students"
    target_duration: int = 600
    resolution: str = "1080p"
    created_at: str
    status: str = "idle"  # idle, ingesting, analyzing, planning, simulating, synthesizing, rendering, ready, error
    progress_pct: int = 0
    status_message: str = "Initialized"
    document: Optional[SourceDocument] = None
    knowledge_graph: Optional[ScientificKnowledgeGraph] = None
    lecture_plan: Optional[LecturePlan] = None
    simulation_output: Optional[Dict[str, Any]] = None
    video_path: Optional[str] = None
    slides_path: Optional[str] = None
    latex_path: Optional[str] = None
    engine_log: List[str] = []  # which engine ran each stage, and why a fallback happened
    scene_overrides: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    review_dirty: bool = False


# ==================== LLM OUTPUT CONTRACTS ====================
# What the lecture director asks the model for. Converted into LectureScene / LecturePlan by
# deterministic code, which owns ids, timing, layout, figures and code excerpts.

SceneType = Literal[
    "hook_problem", "mathematical_formulation", "derivation", "simulation_demo",
    "plot_verification", "engineering_application", "takeaway",
]
EquationTag = Literal["SOURCE", "DERIVED", "GENERATED", "ASSUMED"]


class SceneDraft(BaseModel):
    title: str = Field(description="On-screen scene title, at most 8 words")
    type: SceneType
    narration: str = Field(description="Spoken script for text-to-speech: plain English, no LaTeX or markdown")
    equation: Optional[str] = Field(None, description="One display equation in LaTeX without $ delimiters, or null")
    equation_tag: Optional[EquationTag] = Field(None, description="Provenance of the equation; required when equation is set")
    equation_explanation: List[str] = Field(default_factory=list, description="Term-by-term glosses, e.g. 'A: \text{state transition matrix}'")
    bullet_points: List[str] = Field(description="2-4 short on-screen points, at most 12 words each")
    citation: Optional[str] = Field(None, description="Location in the paper, e.g. 'p. 4, Eq. 3'")


class LecturePlanDraft(BaseModel):
    title: str
    scenes: List[SceneDraft]
    key_takeaways: List[str]
    youtube_title: str
    youtube_tags: List[str]
