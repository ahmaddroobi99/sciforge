"""
SciForge Export & Classroom Deck Generator
Generates:
1. Interactive 16:9 HTML/PDF Classroom Slides Deck with KaTeX and keyboard navigation
2. Standalone LaTeX Derivation Sheet (derivation.tex)
3. Verified Python Simulation Script (simulation.py)
4. YouTube Metadata & SRT/VTT Subtitle Files
"""
from pathlib import Path
from typing import Dict, Any, List
from backend.config import OUTPUTS_DIR, THEMES, PERSONAS
from backend.models import LecturePlan

class ExporterEngine:
    """
    Exports multi-format educational packs from the compiled Lecture IR.
    """

    @classmethod
    def export_all(cls, lecture_plan: LecturePlan, project_id: str, simulation_code: str) -> Dict[str, str]:
        """Runs all exporters and returns file paths."""
        out_dir = OUTPUTS_DIR / project_id
        out_dir.mkdir(parents=True, exist_ok=True)

        slides_path = cls.export_classroom_slides(lecture_plan, out_dir)
        latex_path = cls.export_latex_derivation(lecture_plan, out_dir)
        code_path = cls.export_python_script(simulation_code, out_dir)
        vtt_path = cls.export_subtitles_vtt(lecture_plan, out_dir)

        return {
            "slides_html": str(slides_path),
            "slides_url": f"/outputs/{project_id}/slides.html",
            "latex_tex": str(latex_path),
            "latex_url": f"/outputs/{project_id}/derivation.tex",
            "python_script": str(code_path),
            "python_url": f"/outputs/{project_id}/simulation.py",
            "subtitles_vtt": str(vtt_path),
            "subtitles_url": f"/outputs/{project_id}/subtitles.vtt"
        }

    @classmethod
    def export_classroom_slides(cls, plan: LecturePlan, out_dir: Path) -> Path:
        """Creates a standalone, beautiful HTML 16:9 presentation slide deck."""
        theme = THEMES.get(plan.theme, THEMES["blueprint"])
        persona = PERSONAS.get(plan.persona, PERSONAS["engineer"])

        slides_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{plan.title} - Classroom Presentation Deck</title>
    <!-- KaTeX for crisp LaTeX math rendering -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.css">
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.js"></script>
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/contrib/auto-render.min.js"
        onload="renderMathInElement(document.body);"></script>
    <style>
        :root {{
            --bg-color: {theme['bg_color']};
            --primary: {theme['primary_color']};
            --accent: {theme['accent_color']};
            --secondary: {theme.get('secondary_accent', '#F59E0B')};
            --font-family: {theme['font_family']};
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            background: #000;
            color: #fff;
            font-family: var(--font-family);
            overflow: hidden;
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100vh;
        }}
        .deck-container {{
            width: 100vw;
            height: 56.25vw; /* 16:9 */
            max-height: 100vh;
            max-width: 177.78vh;
            background: var(--bg-color);
            position: relative;
            border: 2px solid var(--primary);
            box-shadow: 0 0 40px rgba(0,0,0,0.8);
            display: flex;
            flex-direction: column;
        }}
        .slide {{
            display: none;
            flex-direction: column;
            width: 100%;
            height: 100%;
            padding: 3rem 4rem;
            position: relative;
        }}
        .slide.active {{ display: flex; }}
        .slide-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px dashed var(--primary);
            padding-bottom: 1rem;
            margin-bottom: 2rem;
        }}
        .slide-tag {{ color: var(--primary); font-size: 1.1rem; text-transform: uppercase; letter-spacing: 2px; }}
        .slide-title {{ font-size: 2.2rem; font-weight: 700; color: #fff; margin-top: 0.5rem; }}
        .slide-body {{
            display: grid;
            grid-template-columns: 1.2fr 1fr;
            gap: 2.5rem;
            flex: 1;
            align-items: center;
        }}
        .slide-body.full {{ grid-template-columns: 1fr; }}
        .equation-box {{
            background: rgba(0,0,0,0.3);
            border-left: 4px solid var(--primary);
            padding: 1.5rem;
            font-size: 1.6rem;
            color: var(--secondary);
            margin-bottom: 1.5rem;
            border-radius: 4px;
        }}
        .bullets li {{
            font-size: 1.35rem;
            color: #E2E8F0;
            margin-bottom: 1rem;
            line-height: 1.5;
            list-style: none;
            position: relative;
            padding-left: 1.8rem;
        }}
        .bullets li::before {{
            content: "►";
            position: absolute;
            left: 0;
            color: var(--primary);
            font-size: 1rem;
        }}
        .code-box {{
            background: #050811;
            border: 1px solid var(--primary);
            padding: 1.2rem;
            font-family: monospace;
            font-size: 1.05rem;
            color: #A5F3FC;
            border-radius: 6px;
            white-space: pre-wrap;
        }}
        .slide-footer {{
            display: flex;
            justify-content: space-between;
            border-top: 1px solid rgba(255,255,255,0.1);
            padding-top: 1rem;
            margin-top: auto;
            color: #94A3B8;
            font-size: 0.95rem;
        }}
        .nav-hint {{
            position: absolute;
            bottom: 15px;
            right: 25px;
            background: rgba(0,0,0,0.6);
            padding: 5px 12px;
            border-radius: 4px;
            font-size: 0.85rem;
            color: var(--primary);
        }}
    </style>
</head>
<body>
    <div class="deck-container">
"""

        for idx, scene in enumerate(plan.scenes):
            active_class = "active" if idx == 0 else ""
            has_fig = bool(scene.figure_url)
            body_class = "full" if not has_fig and not scene.code_snippet else ""

            slides_html += f"""
        <div class="slide {active_class}" id="slide-{idx}">
            <div class="slide-header">
                <div>
                    <div class="slide-tag">SCENE {scene.index:02d} // {scene.type.upper()}</div>
                    <div class="slide-title">{scene.title}</div>
                </div>
                <div style="text-align: right; color: var(--primary); font-size: 1.2rem;">
                    {idx+1} / {len(plan.scenes)}
                </div>
            </div>
            <div class="slide-body {body_class}">
                <div>
"""
            if scene.equation:
                slides_html += f"""
                    <div class="equation-box">
                        $${scene.equation}$$
                    </div>
"""
            slides_html += """
                    <ul class="bullets">
"""
            for bp in scene.bullet_points:
                slides_html += f"                        <li>{bp}</li>\n"
            slides_html += """
                    </ul>
                </div>
"""
            if scene.code_snippet:
                slides_html += f"""
                <div>
                    <div class="code-box">{scene.code_snippet}</div>
                </div>
"""
            elif scene.figure_url:
                slides_html += f"""
                <div style="text-align: center;">
                    <img src="{scene.figure_url}" style="max-width: 100%; max-height: 400px; border: 1px solid var(--primary); border-radius: 6px;">
                </div>
"""
            slides_html += f"""
            </div>
            <div class="slide-footer">
                <div>LECTURER: {persona['name']}</div>
                <div>{scene.citation or ''}</div>
                <div>PROJECTOR MODE [Press Space / Arrows to Advance, F for Fullscreen]</div>
            </div>
        </div>
"""

        slides_html += """
    </div>
    <div class="nav-hint">⌨️ Arrows/Space: Navigate | F: Fullscreen</div>
    <script>
        let currentSlide = 0;
        const slides = document.querySelectorAll('.slide');
        function showSlide(index) {
            if (index < 0) index = 0;
            if (index >= slides.length) index = slides.length - 1;
            slides[currentSlide].classList.remove('active');
            currentSlide = index;
            slides[currentSlide].classList.add('active');
        }
        window.addEventListener('keydown', (e) => {
            if (e.key === 'ArrowRight' || e.key === ' ' || e.key === 'PageDown') showSlide(currentSlide + 1);
            if (e.key === 'ArrowLeft' || e.key === 'PageUp') showSlide(currentSlide - 1);
            if (e.key === 'f' || e.key === 'F') {
                if (!document.fullscreenElement) document.documentElement.requestFullscreen();
                else document.exitFullscreen();
            }
        });
    </script>
</body>
</html>
"""
        target = out_dir / "slides.html"
        target.write_text(slides_html, encoding='utf-8')
        return target

    @classmethod
    def export_latex_derivation(cls, plan: LecturePlan, out_dir: Path) -> Path:
        """Produces a pristine LaTeX publication derivation document."""
        latex_content = f"""\\documentclass[11pt,a4paper]{{article}}
\\usepackage[utf8]{{inputenc}}
\\usepackage{{amsmath,amssymb,amsfonts,amsthm}}
\\usepackage{{geometry}}
\\usepackage{{hyperref}}
\\usepackage{{listings}}
\\usepackage{{xcolor}}

\\geometry{{margin=1in}}
\\hypersetup{{colorlinks=true, linkcolor=blue, citecolor=red}}

\\title{{\\textbf{{{plan.title}}}}}
\\author{{SciForge Autonomous Scientific Lecture Compiler}}
\\date{{\\today}}

\\begin{{document}}
\\maketitle

\\begin{{abstract}}
This document provides the formal mathematical derivation and theoretical foundations for \\textbf{{{plan.topic}}}, prepared for {plan.target_audience.replace('_', ' ')}. Synthesized from original research paper and verified computational simulation.
\\end{{abstract}}

\\section{{Executive Summary}}
{plan.youtube_metadata.get('description', '')}

"""
        for s in plan.scenes:
            latex_content += f"\\section{{{s.title}}}\n"
            latex_content += f"\\textbf{{Pedagogical Function:}} {s.type.replace('_', ' ').capitalize()}\\\\ \n"
            latex_content += f"\\textbf{{Narration:}} {s.narration}\n\n"

            if s.equation:
                latex_content += f"\\begin{{equation}}\n{s.equation}\n\\end{{equation}}\n\n"

            if s.bullet_points:
                latex_content += "\\begin{itemize}\n"
                for bp in s.bullet_points:
                    latex_content += f"  \\item {bp}\n"
                latex_content += "\\end{itemize}\n\n"

            if s.code_snippet:
                latex_content += "\\begin{lstlisting}[language=Python, basicstyle=\\small\\ttfamily]\n"
                latex_content += s.code_snippet + "\n"
                latex_content += "\\end{lstlisting}\n\n"

        latex_content += "\\section{Key Takeaways}\n\\begin{enumerate}\n"
        for kt in plan.key_takeaways:
            latex_content += f"  \\item {kt}\n"
        latex_content += "\\end{enumerate}\n\n"
        latex_content += "\\end{document}\n"

        target = out_dir / "derivation.tex"
        target.write_text(latex_content, encoding='utf-8')
        return target

    @classmethod
    def export_python_script(cls, code: str, out_dir: Path) -> Path:
        """Exports the runnable Python simulation file."""
        target = out_dir / "simulation.py"
        target.write_text(code, encoding='utf-8')
        return target

    @classmethod
    def export_subtitles_vtt(cls, plan: LecturePlan, out_dir: Path) -> Path:
        """Exports WebVTT subtitles."""
        vtt = "WEBVTT - Generated by SciForge\n\n"
        for s in plan.scenes:
            m1, s1 = divmod(int(s.timestamp_start), 60)
            m2, s2 = divmod(int(s.timestamp_end), 60)
            vtt += f"{m1:02d}:{s1:02d}.000 --> {m2:02d}:{s2:02d}.000\n"
            vtt += f"[{s.title}]\n"
            vtt += f"{s.narration}\n\n"

        target = out_dir / "subtitles.vtt"
        target.write_text(vtt, encoding='utf-8')
        return target
