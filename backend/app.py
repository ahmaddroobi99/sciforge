"""
SciForge Main FastAPI Application
Orchestrates the end-to-end scientific publishing pipeline.
"""
import os
import json
import uuid
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.config import (
    BASE_DIR,
    PROJECTS_DIR,
    OUTPUTS_DIR,
    SAMPLES_DIR,
    FRONTEND_DIR,
    THEMES,
    PERSONAS,
    RESOLUTIONS
)
from backend.models import ProjectState, SourceDocument, LecturePlan
from backend.engines.ingestion import OCRDependencyError, PaperIngestionEngine
from backend.engines.knowledge import ScientificKnowledgeEngine
from backend.engines.director import LectureDirectorEngine
from backend.engines.science_sim import ScientificSimulationEngine
from backend.engines.audio_tts import AudioNarrationEngine
from backend.engines.video_renderer import VideoRendererEngine
from backend.engines.exporter import ExporterEngine
from backend.engines.llm import LLMRouter, get_router
from backend.engines.llm.context import paper_is_truncated

app = FastAPI(
    title="SciForge — Scientific Teaching Compiler",
    description="Transforms research papers & notes into 10-minute cinematic lectures, slides, and simulations.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory project registry with filesystem persistence
ACTIVE_PROJECTS: Dict[str, ProjectState] = {}

def get_project_file(project_id: str) -> Path:
    return PROJECTS_DIR / f"{project_id}.json"

def save_project_to_disk(project: ProjectState):
    ACTIVE_PROJECTS[project.id] = project
    path = get_project_file(project.id)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(project.model_dump_json(indent=2))

def load_project_from_disk(project_id: str) -> Optional[ProjectState]:
    if project_id in ACTIVE_PROJECTS:
        return ACTIVE_PROJECTS[project_id]
    path = get_project_file(project_id)
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            proj = ProjectState(**data)
            ACTIVE_PROJECTS[project_id] = proj
            return proj
    return None

# Mount static outputs
app.mount("/outputs", StaticFiles(directory=str(OUTPUTS_DIR)), name="outputs")

# ==================== REST ENDPOINTS ====================

@app.get("/api/health")
async def health_check():
    """System health check and component discovery."""
    import subprocess
    ffmpeg_ok = False
    try:
        r = subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        ffmpeg_ok = (r.returncode == 0)
    except Exception:
        pass

    return {
        "status": "operational",
        "system": "SciForge v1.0.0",
        "ffmpeg_installed": ffmpeg_ok,
        "supported_themes": list(THEMES.keys()),
        "supported_personas": list(PERSONAS.keys()),
        "resolutions": list(RESOLUTIONS.keys()),
        "llm": get_router().describe()
    }

@app.get("/api/themes")
async def get_themes():
    return THEMES

@app.get("/api/personas")
async def get_personas():
    return PERSONAS

@app.get("/api/samples")
async def list_sample_papers():
    """Lists preloaded research papers available for instant demonstration."""
    samples = []
    for f in SAMPLES_DIR.glob("*.json"):
        try:
            with open(f, 'r', encoding='utf-8') as s_file:
                samples.append(json.load(s_file))
        except Exception:
            pass
    return samples

class CreateProjectRequest(BaseModel):
    name: str
    topic: str
    theme: str = "blueprint"
    persona: str = "engineer"
    audience: str = "graduate_students"
    target_duration: int = 600
    resolution: str = "1080p"


class SceneReviewUpdate(BaseModel):
    title: Optional[str] = None
    narration: Optional[str] = None
    equation: Optional[str] = None

@app.post("/api/project/create")
async def create_project(req: CreateProjectRequest):
    """Creates a new project compilation workspace."""
    proj_id = str(uuid.uuid4())[:8]
    project = ProjectState(
        id=proj_id,
        name=req.name,
        topic=req.topic,
        theme=req.theme,
        persona=req.persona,
        audience=req.audience,
        target_duration=req.target_duration,
        resolution=req.resolution,
        created_at=datetime.utcnow().isoformat(),
        status="idle",
        progress_pct=5,
        status_message="Project initialized. Ready for paper ingestion."
    )
    save_project_to_disk(project)
    return project

@app.get("/api/project/{project_id}")
async def get_project(project_id: str):
    """Retrieves full project state, scene graph, and compilation assets."""
    proj = load_project_from_disk(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    return proj


def _invalidate_review_exports(proj: ProjectState) -> None:
    proj.review_dirty = True
    proj.video_path = None
    proj.slides_path = None
    proj.latex_path = None
    proj.status_message = "Scene review saved. Compile again to refresh narration and exports."


def _update_review_timeline(plan: LecturePlan) -> None:
    elapsed = 0.0
    for scene in plan.scenes:
        scene.timestamp_start = round(elapsed, 1)
        elapsed += scene.duration
        scene.timestamp_end = round(elapsed, 1)
    plan.actual_duration_sec = round(elapsed, 1)
    LectureDirectorEngine.refresh_timing_metadata(plan)


@app.put("/api/project/{project_id}/scenes/{scene_id}")
async def update_scene_review(project_id: str, scene_id: str, update: SceneReviewUpdate):
    """Save a reviewed scene and persist its override for the next compilation."""
    proj = load_project_from_disk(project_id)
    if not proj or not proj.lecture_plan:
        raise HTTPException(status_code=404, detail="Compiled lecture not found")
    if proj.status not in {"ready", "error"}:
        raise HTTPException(status_code=409, detail="Wait for compilation to finish before editing scenes")
    scene = next((item for item in proj.lecture_plan.scenes if item.id == scene_id), None)
    if scene is None:
        raise HTTPException(status_code=404, detail="Scene not found")
    if not update.model_fields_set:
        raise HTTPException(status_code=400, detail="No scene changes provided")

    overrides = proj.scene_overrides.setdefault(scene_id, {})
    for field in update.model_fields_set:
        value = getattr(update, field)
        if field in {"title", "narration"}:
            value = (value or "").strip()
            if not value:
                raise HTTPException(status_code=422, detail=f"{field.title()} cannot be empty")
        elif field == "equation":
            value = (value or "").strip() or None
            if value != scene.equation:
                scene.equation_tag = "GENERATED" if value else None
                scene.citation = None
                overrides["equation_tag"] = scene.equation_tag
                overrides["citation"] = None
        setattr(scene, field, value)
        overrides[field] = value

    scene.audio_file = None
    scene.duration = round(max(8.0, len(scene.narration.split()) * 0.42), 1)
    _update_review_timeline(proj.lecture_plan)
    _invalidate_review_exports(proj)
    save_project_to_disk(proj)
    return proj


@app.post("/api/project/{project_id}/scenes/{scene_id}/regenerate")
async def regenerate_scene_review(project_id: str, scene_id: str):
    """Regenerate one scene with the configured LLM, retaining all other scenes."""
    proj = load_project_from_disk(project_id)
    if not proj or not proj.lecture_plan or not proj.document or not proj.knowledge_graph:
        raise HTTPException(status_code=404, detail="Compiled lecture context not found")
    if proj.status not in {"ready", "error"}:
        raise HTTPException(status_code=409, detail="Wait for compilation to finish before editing scenes")
    scene_index = next((i for i, item in enumerate(proj.lecture_plan.scenes) if item.id == scene_id), None)
    if scene_index is None:
        raise HTTPException(status_code=404, detail="Scene not found")

    llm = get_router()
    if not llm.available:
        raise HTTPException(status_code=503, detail="Configure an LLM provider to regenerate a scene")
    replacement = await asyncio.to_thread(
        LectureDirectorEngine.regenerate_scene,
        scene=proj.lecture_plan.scenes[scene_index],
        doc=proj.document,
        kg=proj.knowledge_graph,
        theme_id=proj.theme,
        llm=llm,
        sim_output=proj.simulation_output,
    )
    if replacement is None:
        raise HTTPException(status_code=502, detail=f"Scene regeneration failed: {llm.last_error or 'model returned no scene'}")

    proj.lecture_plan.scenes[scene_index] = replacement
    proj.scene_overrides[scene_id] = {
        field: getattr(replacement, field)
        for field in (
            "title", "narration", "type", "equation", "equation_tag",
            "equation_explanation", "bullet_points", "citation",
        )
    }
    _update_review_timeline(proj.lecture_plan)
    _invalidate_review_exports(proj)
    save_project_to_disk(proj)
    return proj

@app.post("/api/project/{project_id}/load-sample/{sample_id}")
async def load_sample_to_project(project_id: str, sample_id: str):
    """Loads a pre-packaged scientific paper into the project."""
    proj = load_project_from_disk(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    sample_file = SAMPLES_DIR / f"{sample_id}.json"
    if not sample_file.exists():
        # Match by prefix
        candidates = list(SAMPLES_DIR.glob(f"*{sample_id}*.json"))
        if candidates:
            sample_file = candidates[0]
        else:
            raise HTTPException(status_code=404, detail="Sample paper not found")

    with open(sample_file, 'r', encoding='utf-8') as f:
        sample_data = json.load(f)

    # Ingest sample text and field notes
    doc = PaperIngestionEngine.ingest_text(
        text_content=sample_data.get("sample_notes", "") + "\n\nAbstract:\n" + sample_data.get("abstract", ""),
        filename=f"{sample_data.get('title')}.pdf",
        doc_id=f"doc_{proj.id}"
    )

    proj.topic = sample_data.get("topic", proj.topic)
    proj.name = sample_data.get("title", proj.name)
    proj.document = doc
    proj.status = "ingested"
    proj.progress_pct = 25
    proj.status_message = f"Loaded sample paper: {sample_data.get('title')}"
    save_project_to_disk(proj)

    return proj

@app.post("/api/project/{project_id}/upload-paper")
async def upload_paper(
    project_id: str,
    file: Optional[UploadFile] = File(None),
    raw_text: Optional[str] = Form(None),
    topic_override: Optional[str] = Form(None)
):
    """Accepts uploaded PDF document or raw notes."""
    proj = load_project_from_disk(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    proj_dir = OUTPUTS_DIR / project_id
    proj_dir.mkdir(parents=True, exist_ok=True)

    if file and file.filename:
        filename = file.filename
        file_path = proj_dir / filename
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        if filename.lower().endswith(".pdf"):
            try:
                doc = PaperIngestionEngine.ingest_pdf(file_path, f"doc_{proj.id}")
            except OCRDependencyError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
        else:
            try:
                text_str = content.decode('utf-8', errors='ignore')
            except Exception:
                text_str = "Uploaded scientific document."
            doc = PaperIngestionEngine.ingest_text(text_str, filename, f"doc_{proj.id}")
    elif raw_text:
        filename = "field_notes.md"
        doc = PaperIngestionEngine.ingest_text(raw_text, filename, f"doc_{proj.id}")
    else:
        raise HTTPException(status_code=400, detail="No file or text provided")

    if topic_override:
        proj.topic = topic_override

    proj.document = doc
    proj.status = "ingested"
    proj.progress_pct = 25
    proj.status_message = f"Ingested {doc.filename} ({doc.num_pages} pages, {len(doc.equations)} equations)"
    save_project_to_disk(proj)

    return proj

def _engine_note(stage: str, used: str, llm: LLMRouter) -> str:
    """One engine_log line: which engine produced a stage, and why the LLM was skipped."""
    if used != "template":
        return f"{stage}: {used}"
    if llm.available:
        return f"{stage}: template fallback ({llm.last_error})"
    return f"{stage}: template (no LLM: {llm.reason})"

async def run_compilation_pipeline(project_id: str):
    """
    Background worker that runs the full compilation pipeline:
    Knowledge Graph -> Simulation -> Lecture Planning -> TTS Audio -> Exporter -> FFmpeg Video
    """
    proj = load_project_from_disk(project_id)
    if not proj or not proj.document:
        return

    llm = get_router()
    proj.engine_log = []

    try:
        # Step 1: Scientific Knowledge Graph Extraction
        proj.status = "analyzing"
        proj.status_message = f"Building conceptual dependency graph [{llm.label}]..."
        proj.progress_pct = 35
        if llm.available and paper_is_truncated(proj.document):
            proj.engine_log.append(f"paper text cut to SCIFORGE_LLM_MAX_CHARS for the LLM ({len(proj.document.raw_text)} chars total)")
        save_project_to_disk(proj)
        await asyncio.sleep(0.5)

        # LLM stages run in a worker thread so the event loop keeps serving progress polls.
        kg = await asyncio.to_thread(ScientificKnowledgeEngine.build_knowledge_graph, proj.document, proj.topic, llm)
        proj.knowledge_graph = kg
        proj.engine_log.append(_engine_note("knowledge graph", kg.built_by, llm))

        # Step 2: Deterministic Scientific Simulation
        proj.status = "simulating"
        proj.status_message = "Running verified numerical simulation & plotting phase dynamics..."
        proj.progress_pct = 50
        save_project_to_disk(proj)
        await asyncio.sleep(0.5)

        sim_out = ScientificSimulationEngine.run_simulation_for_topic(
            topic=proj.topic,
            theme_id=proj.theme,
            project_id=proj.id
        )
        proj.simulation_output = sim_out

        # Step 3: Lecture Direction & Scene Planning
        proj.status = "planning"
        proj.status_message = f"Directing {proj.target_duration // 60}-minute lecture with {proj.persona} persona [{llm.label}]..."
        proj.progress_pct = 65
        save_project_to_disk(proj)
        await asyncio.sleep(0.5)

        lecture_plan = await asyncio.to_thread(
            LectureDirectorEngine.compile_lecture_plan,
            doc=proj.document,
            kg=kg,
            topic=proj.topic,
            theme_id=proj.theme,
            persona_id=proj.persona,
            audience=proj.audience,
            target_duration=proj.target_duration,
            project_id=proj.id,
            llm=llm,
            sim_output=sim_out
        )
        LectureDirectorEngine.apply_scene_overrides(lecture_plan, proj.scene_overrides)
        proj.lecture_plan = lecture_plan
        proj.engine_log.append(_engine_note("lecture plan", lecture_plan.planned_by, llm))

        # Step 4: Narration & Speech Synthesis
        proj.status = "synthesizing"
        proj.status_message = "Synthesizing neural voice narration per scene..."
        proj.progress_pct = 80
        save_project_to_disk(proj)

        # Synthesize audio for each scene concurrently
        tasks = [
            AudioNarrationEngine.synthesize_scene_audio(scene, proj.persona, proj.id)
            for scene in lecture_plan.scenes
        ]
        audio_results = await asyncio.gather(*tasks)

        for s_idx, a_res in enumerate(audio_results):
            if a_res.get("success"):
                lecture_plan.scenes[s_idx].audio_file = a_res.get("audio_url")
                # Synchronize scene duration to actual audio speech length + 1.5s padding
                actual_dur = round(a_res.get("duration", lecture_plan.scenes[s_idx].duration) + 1.5, 1)
                lecture_plan.scenes[s_idx].duration = actual_dur

        # Recalculate timeline
        t_accum = 0.0
        for sc in lecture_plan.scenes:
            sc.timestamp_start = round(t_accum, 1)
            t_accum += sc.duration
            sc.timestamp_end = round(t_accum, 1)
        lecture_plan.actual_duration_sec = round(t_accum, 1)
        LectureDirectorEngine.refresh_timing_metadata(lecture_plan)
        proj.lecture_plan = lecture_plan

        # Step 5: Export Slide Deck, LaTeX, Python code, Subtitles
        proj.status_message = "Exporting classroom 16:9 slides, LaTeX sheet & simulation code..."
        save_project_to_disk(proj)

        export_paths = ExporterEngine.export_all(
            lecture_plan=lecture_plan,
            project_id=proj.id,
            simulation_code=sim_out.get("runnable_python_code", "# Python Simulation")
        )
        proj.slides_path = export_paths.get("slides_url")
        proj.latex_path = export_paths.get("latex_url")

        # Step 6: Video Compilation via FFmpeg
        proj.status = "rendering"
        proj.status_message = f"Compiling {proj.resolution} MP4 video via FFmpeg..."
        proj.progress_pct = 90
        save_project_to_disk(proj)

        video_res = VideoRendererEngine.render_full_lecture_video(
            lecture_plan=lecture_plan,
            project_id=proj.id,
            resolution_key=proj.resolution
        )
        if video_res.get("success"):
            proj.video_path = video_res.get("video_url")

        # Final Success State
        proj.status = "ready"
        proj.progress_pct = 100
        proj.review_dirty = False
        proj.status_message = f"Lecture compilation complete! Planned by {lecture_plan.planned_by}. Ready to present & export."
        save_project_to_disk(proj)

    except Exception as e:
        import traceback
        traceback.print_exc()
        proj.status = "error"
        proj.status_message = f"Compilation failed: {str(e)}"
        save_project_to_disk(proj)

@app.post("/api/project/{project_id}/compile")
async def compile_project(project_id: str, background_tasks: BackgroundTasks):
    """Triggers the autonomous compilation pipeline."""
    proj = load_project_from_disk(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    if not proj.document:
        raise HTTPException(status_code=400, detail="Cannot compile: No paper or notes ingested yet")

    proj.status = "queued"
    proj.status_message = "Pipeline queued for execution..."
    proj.progress_pct = 10
    save_project_to_disk(proj)

    background_tasks.add_task(run_compilation_pipeline, project_id)
    return {"message": "Compilation started", "project_id": project_id}

@app.post("/api/project/{project_id}/render-video")
async def trigger_video_render(project_id: str, resolution: str = "1080p"):
    """Re-renders video at requested resolution preset."""
    proj = load_project_from_disk(project_id)
    if not proj or not proj.lecture_plan:
        raise HTTPException(status_code=400, detail="Lecture plan must be compiled before rendering video")

    res = VideoRendererEngine.render_full_lecture_video(
        lecture_plan=proj.lecture_plan,
        project_id=proj.id,
        resolution_key=resolution
    )
    if res.get("success"):
        proj.video_path = res.get("video_url")
        proj.resolution = resolution
        save_project_to_disk(proj)
    return res

class CustomPythonRequest(BaseModel):
    code: str

@app.post("/api/project/{project_id}/execute-python")
async def execute_custom_python(project_id: str, req: CustomPythonRequest):
    """Executes arbitrary Python code in a safe local namespace to generate customized plots."""
    import io
    import base64
    import matplotlib.pyplot as plt

    local_vars = {"np": __import__("numpy"), "plt": plt}
    buf = io.BytesIO()

    try:
        exec(req.code, {}, local_vars)
        plt.savefig(buf, format='png', bbox_inches='tight')
        plt.close('all')
        buf.seek(0)
        img_b64 = base64.b64encode(buf.read()).decode('utf-8')
        return {"success": True, "image": f"data:image/png;base64,{img_b64}"}
    except Exception as e:
        plt.close('all')
        return {"success": False, "error": str(e)}

# Serve frontend single page app
@app.get("/")
async def serve_index():
    index_file = FRONTEND_DIR / "index.html"
    return FileResponse(str(index_file))

# Mount entire frontend static files
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")
