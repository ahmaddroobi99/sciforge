# SciForge

Local paper → lecture compiler. Drop a scientific PDF, get a structured lecture IR, classroom slides, and a rendered video. No DaVinci tab-flipping. No mandatory cloud API.

## What it is

A teaching compiler, not an AI video toy.

```
PDF / notes
    → ingest (text, headings, equations, keywords)
    → lecture IR (scenes, narration, timing)
    → deterministic backends
         ├─ slides PDF
         ├─ matplotlib scenes + simulation
         └─ ffmpeg video (720p / 1080p)
```

The LLM is optional and swappable. The application owns the workflow.

## Quick start

System packages already expected: `python3`, `ffmpeg`, `poppler-utils`.

```bash
cd sciforge
python3 examples/make_sample_paper.py
PYTHONPATH=. python3 -m sciforge compile examples/kalman_filter_note.pdf \
  --theme blueprint --duration 4 --width 1280 --height 720
```

GUI:

```bash
PYTHONPATH=. python3 -m sciforge serve --host 127.0.0.1 --port 8787
```

Open `http://127.0.0.1:8787`. Drop a PDF. Download slides + `lecture.mp4`.

Full source currently lives in the local workspace. Clone this repo after you push the remaining tree:

`git remote add origin https://github.com/ahmaddroobi99/sciforge.git`

## Design rules

1. Do not let a model emit pixels as the source of truth.
2. Emit a lecture IR. Render it deterministically.
3. Use AI later for script tone and OCR cleanup, not for fake experimental plots.
4. Keep teaching DNA on disk so the narrator stays the same person across papers.

## License

MIT
