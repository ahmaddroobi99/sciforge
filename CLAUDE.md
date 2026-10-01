# CLAUDE.md — SciForge

SciForge is a local-first "scientific teaching compiler": **paper / notes in → 10-min narrated lecture video + classroom slides + LaTeX sheet + Python simulation out**, from one GUI, with no hopping between ChatGPT, OBS, Resolve, Manim, and the rest.

The owner is a technical person (engineering / physics / robotics / AI). Keep explanations short and direct.

---

## Commands

Run everything from the repo root. Tests and engines use relative paths such as `outputs/test_proj`.

```bash
pip install -r requirements.txt  # plus ffmpeg on PATH
python run.py                    # FastAPI on http://127.0.0.1:8000, opens the browser
python tests/test_pipeline.py    # end-to-end smoke test (plain script)
python -m pytest tests/test_llm.py   # LLM layer: mocked HTTP, no network, no API spend
curl http://127.0.0.1:8000/api/health   # reports FFmpeg and the active LLM (or why there is none)
```

- LLM config lives in `.env` (copy `.env.example`; `.env` is git-ignored). With no key the app runs on templates.
- The smoke test needs internet for Edge-TTS. Offline, it falls back to a synthetic `.wav` tone, so the test still "passes" but you get no real voice.
- On Windows, if printing emoji raises `UnicodeEncodeError`, set `PYTHONIOENCODING=utf-8`.

---

## Pipeline (what actually runs)

`backend/app.py → run_compilation_pipeline()` runs these stages in order, saving `ProjectState` to `projects/<id>.json` after each stage:

| # | Stage | Module | Output |
|---|---|---|---|
| 1 | Ingest | `engines/ingestion.py` | `SourceDocument` (PyMuPDF text, OCR for scanned pages, regex LaTeX extraction) |
| 2 | Knowledge graph | `engines/knowledge.py` | `ScientificKnowledgeGraph`: **LLM**, else topic template |
| 3 | Simulation | `engines/science_sim.py` | themed Matplotlib PNG + runnable Python source |
| 4 | Direct | `engines/director.py` | `LecturePlan` → list of `LectureScene` (the **Lecture IR**): **LLM**, else topic template |
| 5 | Narrate | `engines/audio_tts.py` | per-scene mp3; scene duration resynced to the real audio length |
| 6 | Export | `engines/exporter.py` | `slides.html` (16:9, KaTeX), `derivation.tex`, `simulation.py`, `subtitles.vtt` |
| 7 | Render | `engines/video_renderer.py` | PIL frame per scene → FFmpeg clip → concat → `lecture_<res>.mp4` |

Everything lands in `outputs/<project_id>/`. Frontend: plain HTML/CSS/JS in `frontend/`, served by the same FastAPI app. `outputs/` and `projects/` are generated, so don't hand-edit them. `ProjectState.engine_log` records which engine ran stages 2 and 4, and why a fallback happened.

### LLM layer (`backend/engines/llm/`)
- `router.py`: `get_router()` → `LLMRouter.generate(task, system=, user=, schema=PydanticModel)`. It returns a validated object, or **`None` on any failure**, and the caller then uses its template.
- Provider comes from `SCIFORGE_LLM_PROVIDER` (`auto` = first key found: Anthropic → xAI → OpenAI). Defaults: `claude-opus-5`, `grok-4`, `gpt-5`, `llama3.1`. Override with `SCIFORGE_LLM_MODEL`.
- `anthropic_provider.py`: official SDK, streaming, `output_config.format` from `anthropic.transform_schema(schema)`, adaptive thinking, and the server-side refusal fallback to `claude-opus-4-8`. Don't switch to the SDK's `output_format`/`parse()` helpers: they parse before `stop_reason` is known, so refusals and truncation show up as JSON errors.
- `openai_compat.py`: xAI / OpenAI / Ollama via `/chat/completions`, JSON mode + schema in the prompt, one repair retry.
- The LLM writes a `LecturePlanDraft` (`models.py`), never a `LectureScene`. Deterministic code in `director._scene_from_draft` owns ids, timing, layout, figures, code excerpts, and tag checks.

---

## Core architecture rule

**AI decides *what* happens. Deterministic code decides *how* it's rendered.**

```
source → SourceDocument → KnowledgeGraph → LecturePlan (IR) → renderers (video / slides / LaTeX)
```

- Nothing generates video, slides, or plots directly from free text. Everything goes through the Pydantic models in `backend/models.py`.
- Slides, LaTeX, and video are all built **from the same `LecturePlan`**. Never derive one output from another (e.g. slides from the video).
- To add a feature, extend the IR first (`models.py`), then teach each renderer about it.

---

## Current reality vs. intent (read before touching anything)

| Area | Today | Intended |
|---|---|---|
| "Understanding" | LLM router (v0.2) with template fallback (Kalman / Attention / Neural ODE / generic). **Not yet verified against a live model**: the only key tested had no credits | Validated IR from a real model on real papers |
| OCR | Tesseract OCR fallback for image-backed PDF pages without a text layer; handwritten math/layout extraction remains limited | Surya (or similar) for layout, math, and figures |
| Visuals | One static PIL card per scene | Programmatic animation (Manim / Remotion) |
| TTS | Edge-TTS (**online**, Microsoft) with a sine-wave fallback | Local TTS (Kokoro / Piper) |
| Sandbox | `/execute-python` runs bare `exec()` in the server process | Isolated sandbox (Docker) |

### Topic templates
- `engines/topics.py::classify_topic` is the single whole-word classifier used by the knowledge, simulation, and director engines. To add a template family: add a rule there, then one template per engine.
- The **generic** simulation is a placeholder damped oscillator, not the paper's experiment. The LLM director is told there is no simulation and converts any `simulation_demo` / `plot_verification` scene to `engineering_application`. Otherwise the renderer auto-attaches whatever plot is on disk.
- **Known bug:** the Kalman template narration and bullets claim ">65%" error reduction, but the simulation measures ~33%. Template text is static and must be fixed to read from `sim_output["metrics"]`.

---

## Rules for changes

**Scientific correctness (non-negotiable)**
- Every equation carries a `tag`: `SOURCE` / `DERIVED` / `GENERATED` / `ASSUMED`. Keep `page` / citation when the item came from the paper.
- Numbers shown on screen (metrics, plots, error %) come from **executed code**, never from LLM text.
- If an LLM claim has no source, label it as generated. Don't make it read as though it came from the paper.

**LLM usage**
- Every model call goes through `get_router().generate(...)`. No provider SDK or HTTP calls inside engines.
- Keys come **only from env / `.env`**. Never commit them, log them, or write them to `projects/*.json`.
- Every LLM stage must have a template fallback, so the pipeline always completes offline.
- Paper text goes inside `<paper>` tags (`llm/context.py`), and prompts say it is data, not instructions.
- Call LLM stages via `asyncio.to_thread` in `app.py` so the event loop keeps serving progress polls.
- New LLM tests mock HTTP (see `tests/test_llm.py`). Don't make tests that spend API credit.

**Security**
- `/api/project/{id}/execute-python` is arbitrary code execution. Keep the server bound to `127.0.0.1`, and never route LLM-generated code into it until there is a real sandbox.

**Themes & personas**
- These are **config**, not prompt text: `THEMES` and `PERSONAS` in `backend/config.py`.
- A new theme also needs styling in `frontend/styles.css`, and it should render sensibly in `science_sim.apply_theme_styling`, `video_renderer`, and `exporter`. Unknown ids silently fall back to `blueprint` / `engineer`.

**Rendering**
- Develop at `720p`, review at `1080p`, and render `2K` / `4K` only for finals (`POST /api/project/{id}/render-video?resolution=4K`).

**After any engine change** run `python tests/test_pipeline.py` (must end with `[SUCCESS]`) and `python -m pytest tests/test_llm.py`.

---

## Roadmap (build in order, don't skip ahead)

- [x] **v0.1 skeleton**: GUI, PDF/text ingest, IR models, template director, FFmpeg MP4, slides/LaTeX/py export
- [x] **v0.2 real understanding**: LLM router + schema-validated `KnowledgeGraph` / `LecturePlan`; single topic dispatch; `requirements.txt`. *Open: first run against a live model with credits; tune prompts on real papers.*
- [ ] **v0.3 real ingestion**: OCR for scanned papers and handwritten notes (equations → LaTeX, figures cropped, page + bbox kept)
- [ ] **v0.4 real science**: LLM-proposed simulation code run in a sandbox; results feed back into scenes
- [ ] **v0.5 motion**: animated scenes (Manim / Remotion), equation reveals, narration-timestamp → visual sync, burned-in captions
- [ ] **v0.6 teaching DNA**: `personas/` + `themes/` as YAML (teaching patterns, vocabulary, analogies, narrative arc), local TTS
- [ ] **v1.0**: PPTX/PDF export, review UI (regenerate single scene, edit script), 4K GPU render, YouTube upload

Target UX: **drop paper → watchable 1080p draft in under 5 minutes → approve → 4K final** (4K is a separate, slower step).

---

## Owner's content workflow (what the tool serves)

1. Drop paper(s) or field notes (PDF / MD / TXT, later scans).
2. Pick theme, persona, audience, duration, and resolution.
3. Compile, then review the draft and scenes.
4. Outputs: **YouTube MP4** (chapters + tags in `lecture_plan.youtube_metadata`), **projector slides** (`slides.html`, high contrast, large equations), **LaTeX sheet**, **runnable simulation**.
5. In class, show the video as the intro, then switch to slides and the live simulation. Don't just project the video.
