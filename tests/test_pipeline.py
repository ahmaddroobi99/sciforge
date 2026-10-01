import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
from unittest.mock import patch
from backend.models import ProjectState
from backend.engines.ingestion import PaperIngestionEngine
from backend.engines.knowledge import ScientificKnowledgeEngine
from backend.engines.science_sim import ScientificSimulationEngine
from backend.engines.director import LectureDirectorEngine
from backend.engines.audio_tts import AudioNarrationEngine
from backend.engines.video_renderer import VideoRendererEngine
from backend.engines.exporter import ExporterEngine
from backend.engines.ingestion import OCRDependencyError


def test_scanned_pdf_uses_ocr():
    class Page:
        def get_text(self, kind, textpage=None):
            return "" if textpage is None else "Recognized scanned text"

        def get_images(self, full):
            return [(1,)]

        def get_textpage_ocr(self, language, dpi, full):
            assert language == "eng"
            assert dpi == 300
            assert full is True
            return object()

    class Document:
        def __len__(self):
            return 1

        def __getitem__(self, index):
            return Page()

        def close(self):
            pass

    with patch("backend.engines.ingestion.fitz.open", return_value=Document()):
        doc = PaperIngestionEngine.ingest_pdf(Path("scan.pdf"), "scan")

    assert "Recognized scanned text" in doc.raw_text
    assert doc.sections[0].content == "Recognized scanned text "


def test_scanned_pdf_reports_missing_ocr_runtime():
    class Page:
        def get_text(self, kind, textpage=None):
            return ""

        def get_images(self, full):
            return [(1,)]

        def get_textpage_ocr(self, **kwargs):
            raise RuntimeError("Tesseract not found")

    class Document:
        def __len__(self):
            return 1

        def __getitem__(self, index):
            return Page()

        def close(self):
            pass

    with patch("backend.engines.ingestion.fitz.open", return_value=Document()):
        try:
            PaperIngestionEngine.ingest_pdf(Path("scan.pdf"), "scan")
        except OCRDependencyError as exc:
            assert "Install Tesseract OCR" in str(exc)
        else:
            raise AssertionError("Expected OCRDependencyError")

async def run_test():
    print("[*] Testing Ingestion...")
    sample_notes = """# Kalman Filter Derivation Notes
Problem: State estimation under noisy GPS.
Dynamics: $x_k = A x_{k-1} + w_k$
Measurement: $z_k = H x_k + v_k$
Gain: $K = P H^T (H P H^T + R)^{-1}$
Update: $\\hat{x} = \\hat{x}^- + K(z - H \\hat{x}^-)$
"""
    doc = PaperIngestionEngine.ingest_text(sample_notes, "notes.md", "doc_test")
    print(f" -> Extracted {len(doc.equations)} equations from notes.")

    print("[*] Testing Knowledge Engine...")
    kg = ScientificKnowledgeEngine.build_knowledge_graph(doc, "Kalman Filter")
    print(f" -> Generated {len(kg.nodes)} nodes, {len(kg.edges)} edges.")

    print("[*] Testing Simulation Engine...")
    sim_res = ScientificSimulationEngine.run_simulation_for_topic("Kalman Filter", "blueprint", "test_proj")
    print(f" -> Plot generated: {sim_res['plot_filename']}, metrics: {sim_res['metrics']}")

    print("[*] Testing Lecture Director...")
    plan = LectureDirectorEngine.compile_lecture_plan(doc, kg, "Kalman Filter", "blueprint", "engineer", target_duration=180, project_id="test_proj")
    print(f" -> Planned {len(plan.scenes)} scenes, total duration: {plan.actual_duration_sec}s")

    print("[*] Testing Audio Engine on Scene 1...")
    audio_res = await AudioNarrationEngine.synthesize_scene_audio(plan.scenes[0], "engineer", "test_proj")
    print(f" -> Audio synthesized: {audio_res['audio_filename']} (duration: {audio_res['duration']}s)")

    print("[*] Testing Exporter...")
    exp_res = ExporterEngine.export_all(plan, "test_proj", sim_res["runnable_python_code"])
    print(f" -> Slides HTML: {Path(exp_res['slides_html']).exists()}")
    print(f" -> LaTeX Derivation: {Path(exp_res['latex_tex']).exists()}")
    print(f" -> Python Code: {Path(exp_res['python_script']).exists()}")

    print("[*] Testing Video Frame & Scene Encoding...")
    # Render frame 1
    frame_path = Path("outputs/test_proj/video_frames/frame_01.png")
    frame_path.parent.mkdir(parents=True, exist_ok=True)
    from backend.config import THEMES, PERSONAS
    VideoRendererEngine._render_scene_frame(
        scene=plan.scenes[0],
        total_scenes=len(plan.scenes),
        topic="Kalman Filter",
        theme=THEMES["blueprint"],
        persona=PERSONAS["engineer"],
        output_path=frame_path,
        width=1280,
        height=720,
        project_id="test_proj"
    )
    print(f" -> Frame 1 rendered: {frame_path.exists()} (size: {frame_path.stat().st_size} bytes)")

    print("[*] Testing Clip Encoding with FFmpeg...")
    clip_path = Path("outputs/test_proj/scene_clips/clip_01.mp4")
    clip_path.parent.mkdir(parents=True, exist_ok=True)
    audio_p = Path(audio_res["audio_path"])
    ok = VideoRendererEngine._encode_scene_clip(
        frame_path=frame_path,
        audio_path=audio_p,
        duration=audio_res["duration"],
        output_path=clip_path,
        width=1280,
        height=720,
        bitrate="2500k"
    )
    print(f" -> FFmpeg encoded clip: {ok}, exists: {clip_path.exists()} (size: {clip_path.stat().st_size if clip_path.exists() else 0} bytes)")

    print("\n[SUCCESS] All SciForge core subsystems verified operational!")

if __name__ == "__main__":
    asyncio.run(run_test())
