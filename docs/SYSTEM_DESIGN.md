# SciForge System Design

## 1. Purpose and scope

SciForge is a local-first scientific teaching compiler. It ingests a paper or notes, creates structured scientific context, plans a lecture as an intermediate representation (IR), and renders several classroom and publishing outputs from that same plan.

This document describes the current implementation, including its deliberate constraints. It does not describe the aspirational end state as if it were already shipped.

## 2. Design goals

- Produce a complete, inspectable teaching pack from a single input workflow.
- Keep document facts, equation provenance, simulation results, and generated narration distinguishable.
- Make model providers optional and hide provider-specific HTTP/SDK behavior behind one router.
- Make compilation progress observable and persist enough state to resume project review after a restart.
- Keep renderers deterministic with respect to the validated `LecturePlan` and generated assets.

## 3. Non-goals and current limits

- It is not a hosted multi-tenant service or a safe public code-execution platform.
- It does not prove scientific claims or independently validate arbitrary papers.
- OCR is not full document-layout understanding and handwritten equations are not reliably parsed.
- The generic simulation is a teaching illustration, not experimental evidence from an arbitrary paper.
- Rendering is scene-card based; timed motion graphics are future work.

## 4. Runtime topology

```mermaid
flowchart TB
    subgraph LocalHost[Single local host]
        Browser[Browser: frontend HTML CSS JS]
        FastAPI[FastAPI application]
        ProjectStore[(projects/{id}.json)]
        OutputStore[(outputs/{id}/)]
        PyMuPDF[PyMuPDF]
        Tesseract[Tesseract OCR optional]
        Engines[Knowledge, simulation, director, TTS, exporters]
        FFmpeg[FFmpeg executable]
    end
    LLM[Optional remote or local LLM provider]
    EdgeTTS[Edge-TTS service]
    Browser <-->|HTTP and static files| FastAPI
    FastAPI --> ProjectStore
    FastAPI --> OutputStore
    FastAPI --> PyMuPDF
    PyMuPDF -. image-only page .-> Tesseract
    FastAPI --> Engines
    Engines <--> LLM
    Engines <--> EdgeTTS
    Engines --> FFmpeg
    Engines --> OutputStore
```

The launcher binds to loopback (`127.0.0.1`). Project JSON is persisted locally; generated artifacts are written beneath the corresponding output directory. There is no external database or queue service.

## 5. Compilation flow

```mermaid
sequenceDiagram
    actor User
    participant UI as Browser UI
    participant API as FastAPI
    participant Ingest as Ingestion Engine
    participant KG as Knowledge Engine
    participant Sim as Simulation Engine
    participant Director as Lecture Director
    participant TTS as Narration Engine
    participant Export as Exporter
    participant Render as Video Renderer
    participant Store as Local JSON/files

    User->>UI: Upload or select paper; choose direction
    UI->>API: Create project and ingest document
    API->>Ingest: Parse text/PDF; OCR only empty image-backed pages
    Ingest-->>API: SourceDocument
    UI->>API: Start compilation
    API->>Store: Save queued project state
    API->>KG: Analyze paper (LLM or topic template)
    KG-->>API: ScientificKnowledgeGraph
    API->>Sim: Run deterministic topic simulation
    Sim-->>API: Plot, code, measured metrics
    API->>Director: Build LecturePlan from source, graph, simulation
    Director-->>API: Validated scene IR
    API->>API: Reapply saved scene review overrides
    API->>TTS: Synthesize narration per scene
    TTS-->>API: Audio files and measured durations
    API->>Export: Generate slides, LaTeX, captions, metadata
    API->>Render: Render frames, encode clips, concatenate MP4
    API->>Store: Persist ready state and artifact paths
    UI->>API: Poll project state
    API-->>UI: Progress, lecture IR, and output URLs
    User->>UI: Save scene edit or regenerate one scene
    UI->>API: Update scene or request targeted regeneration
    API->>Store: Persist overrides; invalidate stale exports
```

Pipeline stages update `ProjectState.status`, `progress_pct`, `status_message`, and `engine_log`. The browser polls the project endpoint while the background task runs.

## 6. Component ownership

| Component | Owns | Does not own |
|---|---|---|
| `backend/app.py` | HTTP contracts, project persistence, job orchestration, status updates | Scientific interpretation and visual rendering internals |
| `engines/ingestion.py` | PDF/text extraction, page-level OCR fallback, section/equation/reference heuristics | Layout-faithful reconstruction or scientific verification |
| `engines/knowledge.py` | Graph construction from source text or topic templates | Rendering output files |
| `engines/science_sim.py` | Deterministic simulation code, measured metrics, plot generation | Claiming a generic simulation came from the paper |
| `engines/director.py` | Scene plan, deterministic scene normalization, tag/citation checks, review override application | Pixel generation or provider SDK calls |
| `engines/llm/` | Provider routing, prompts, HTTP/SDK calls, schema validation, failure reporting | Direct project mutation |
| `engines/audio_tts.py` | Scene audio and subtitle timing inputs | Lecture structure |
| `engines/exporter.py` | Slides, LaTeX sheet, simulation export, subtitles, publishing metadata | Re-planning the lecture independently |
| `engines/video_renderer.py` | Scene frames, FFmpeg clips, final video encoding | Scientific interpretation |
| `frontend/` | User controls, review experience, progress display, playback and download links | Provider secrets or pipeline orchestration |

## 7. Data contracts and persistence

The main data path is:

```text
PDF / notes
  -> SourceDocument
  -> ScientificKnowledgeGraph
  -> LecturePlan (LectureScene[])
  -> HTML slides / LaTeX / subtitles / audio / simulation / MP4
```

- `SourceDocument` retains extracted raw text, sections, equation page numbers, references, and image counts.
- `ScientificKnowledgeGraph` represents concepts, relations, assumptions, and limitations. `built_by` records the provider or template engine.
- `LecturePlan` is the canonical output contract. Scene ids, durations, visual specifications, and equation tags are owned by deterministic code after model output validation.
- `ProjectState` is serialized to `projects/{id}.json` at stage transitions. `scene_overrides` stores user-approved content to reapply during the next compilation.
- Generated files live under `outputs/{id}/`; those local artifacts are not source-controlled.

Projects are currently stored as whole JSON documents. This is simple for a single-user local tool but is not designed for concurrent multi-process writers or large project counts.

## 8. API surface

| Method | Endpoint | Contract |
|---|---|---|
| `GET` | `/api/health` | Application status, FFmpeg availability, supported settings, LLM availability |
| `GET` | `/api/themes`, `/api/personas`, `/api/samples` | UI configuration and bundled samples |
| `POST` | `/api/project/create` | Initialize `ProjectState` |
| `GET` | `/api/project/{id}` | Read project and compilation state |
| `POST` | `/api/project/{id}/load-sample/{sample_id}` | Load a bundled benchmark |
| `POST` | `/api/project/{id}/upload-paper` | Upload PDF or text/Markdown content |
| `POST` | `/api/project/{id}/compile` | Queue background compilation |
| `PUT` | `/api/project/{id}/scenes/{scene_id}` | Save title, narration, or equation review fields |
| `POST` | `/api/project/{id}/scenes/{scene_id}/regenerate` | Regenerate a single scene via configured LLM |
| `POST` | `/api/project/{id}/render-video` | Render an existing plan at requested resolution |
| `POST` | `/api/project/{id}/execute-python` | Execute user-supplied simulation code (unsafe; local development only) |

FastAPI OpenAPI docs are served at `/docs`.

## 9. Model and fallback behavior

All model calls go through `get_router().generate(...)`. Providers return schema-validated Pydantic outputs or `None`; engines then use deterministic templates where available. Paper content is delimited as data in prompts, not instructions. LLM calls in the compilation path use worker threads so progress polling can continue.

| Stage | Preferred path | Fallback/limit |
|---|---|---|
| Knowledge graph | Schema-validated LLM | Topic template or generic graph |
| Lecture plan | `LecturePlanDraft` from LLM, normalized into `LectureScene` | Per-topic deterministic lecture template |
| Simulation | Topic-specific deterministic Python | Generic damped oscillator is illustrative only |
| OCR | PyMuPDF text layer | Tesseract for image-backed pages without text |
| Narration | Edge-TTS | Synthetic tone is test/offline fallback, not intelligible narration |

## 10. Scene review consistency

Scene edits update the current plan and persist only the user-reviewed fields. A changed equation loses any old citation and is tagged `GENERATED`; the user should add verified sourcing through a future provenance-aware editor rather than retaining misleading source metadata. Text edits clear that scene's audio and recalculate duration/timestamps and chapter metadata. All lecture-derived exports are invalidated until the next compile succeeds.

On recompilation, overrides are applied to the newly generated plan before TTS and export. This prevents planning from silently discarding user edits while ensuring audio and all artifacts reflect the reviewed text.

## 11. Trust boundaries and security

### Current assumptions

- The application is for one trusted local user and binds to loopback.
- API upload names and content should be treated as untrusted input.
- `.env` is local-only and excluded from Git. Provider credentials must never enter project JSON, logs, or generated artifacts.
- Paper text is untrusted data. Prompt instructions explicitly separate source content from model instructions.

### High-risk boundary

`/api/project/{id}/execute-python` executes arbitrary Python with `exec()` in the application process. This can read files, access credentials, or modify the host. It is not a sandbox. Do not expose this endpoint to a network, and do not route LLM-generated code into it. A real sandbox requires process/container isolation, resource limits, filesystem/network restrictions, and explicit user consent.

The current permissive CORS middleware is also unsuitable for a network-exposed deployment. Loopback binding is a deployment assumption, not a substitute for authentication or authorization.

## 12. Reliability and operational behavior

- Each compilation stage saves status to disk; browser polling can recover current state after UI refresh.
- LLM provider errors fall back to templates for the knowledge and planning stages.
- Audio stage has an offline fallback used by tests; real Edge-TTS requires network access.
- FFmpeg and OCR are external executables and are checked or reported at runtime; they are not Python package dependencies.
- Render jobs currently run in-process. A server restart can interrupt a render; there is no durable job queue or automatic retry.
- Repeated project ids and concurrent writes are not coordinated across processes.

## 13. Verification

```powershell
python tests/test_pipeline.py
python -m pytest tests/test_llm.py tests/test_scene_review.py
```

The pipeline smoke test performs a short media render and may attempt online Edge-TTS before falling back. LLM tests are mocked and make no billable provider calls.

## 14. Evolution path

1. Add robust OCR layout, bounding boxes, figure crops, and equation provenance to the document IR.
2. Isolate executable simulations before accepting generated code.
3. Move project persistence and render jobs behind durable storage/queue boundaries if multi-user use is required.
4. Add motion renderers while keeping `LecturePlan` as the cross-output contract.
5. Add local TTS and portable PDF/PPTX export backends.