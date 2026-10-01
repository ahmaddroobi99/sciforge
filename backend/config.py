"""
SciForge Configuration & System Constants
"""
import os
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
FRONTEND_DIR = BASE_DIR / "frontend"
PROJECTS_DIR = BASE_DIR / "projects"
OUTPUTS_DIR = BASE_DIR / "outputs"
SAMPLES_DIR = BACKEND_DIR / "sample_papers"

# Ensure runtime directories exist
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader (KEY=VALUE per line). Real environment variables take precedence."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(BASE_DIR / ".env")

# LLM Router (backend/engines/llm). "auto" picks the first provider whose API key is set.
LLM_PROVIDER = os.getenv("SCIFORGE_LLM_PROVIDER", "auto").strip().lower()
LLM_MODEL = os.getenv("SCIFORGE_LLM_MODEL", "").strip()
LLM_EFFORT = os.getenv("SCIFORGE_LLM_EFFORT", "high").strip().lower()
LLM_TIMEOUT_SEC = float(os.getenv("SCIFORGE_LLM_TIMEOUT", "600"))
# Paper text beyond this many characters is cut before it is sent (and the cut is logged).
LLM_MAX_DOC_CHARS = int(os.getenv("SCIFORGE_LLM_MAX_CHARS", "400000"))

# Auto-detection order follows this dict's order.
LLM_KEY_ENV = {
    "anthropic": "ANTHROPIC_API_KEY",
    "xai": "XAI_API_KEY",
    "openai": "OPENAI_API_KEY",
}
LLM_DEFAULT_MODELS = {
    "anthropic": "claude-opus-5",
    "xai": "grok-4",
    "openai": "gpt-5",
    "ollama": "llama3.1",
}
_ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434").strip().rstrip("/")
if not _ollama_host.startswith("http"):
    _ollama_host = "http://" + _ollama_host
LLM_BASE_URLS = {
    "xai": "https://api.x.ai/v1",
    "openai": "https://api.openai.com/v1",
    "ollama": _ollama_host + "/v1",
}

# Video Resolutions
RESOLUTIONS = {
    "720p": {"width": 1280, "height": 720, "fps": 30, "bitrate": "2500k"},
    "1080p": {"width": 1920, "height": 1080, "fps": 30, "bitrate": "6000k"},
    "2K": {"width": 2560, "height": 1440, "fps": 30, "bitrate": "12000k"},
    "4K": {"width": 3840, "height": 2160, "fps": 30, "bitrate": "25000k"},
}

# Supported Visual Themes
THEMES = {
    "blueprint": {
        "id": "blueprint",
        "name": "Blueprint Technical",
        "bg_color": "#0B192C",
        "grid_color": "rgba(30, 80, 140, 0.35)",
        "primary_color": "#00ADB5",
        "accent_color": "#EEEEEE",
        "secondary_accent": "#FF9A3C",
        "font_family": "'Fira Code', 'Courier New', monospace",
        "border_style": "dashed 1px #00ADB5",
        "aesthetic": "Engineering blueprints, precise coordinate grids, dashed dimension markers, circuit & vector overlays."
    },
    "laboratory": {
        "id": "laboratory",
        "name": "Cybernetics / Laboratory",
        "bg_color": "#0D1117",
        "grid_color": "rgba(56, 189, 248, 0.15)",
        "primary_color": "#10B981",
        "accent_color": "#38BDF8",
        "secondary_accent": "#F59E0B",
        "font_family": "'Inter', 'Segoe UI', sans-serif",
        "border_style": "solid 1px #38BDF8",
        "aesthetic": "Clean modern research facility, oscilloscope curves, glowing HUD metrics, data stream monitors."
    },
    "chalkboard": {
        "id": "chalkboard",
        "name": "Quantum Slate / Chalkboard",
        "bg_color": "#1A251D",
        "grid_color": "rgba(255, 255, 255, 0.08)",
        "primary_color": "#FDE047",
        "accent_color": "#FFFFFF",
        "secondary_accent": "#93C5FD",
        "font_family": "'KaTeX_Main', 'Cambria Math', serif",
        "border_style": "solid 2px rgba(255, 255, 255, 0.2)",
        "aesthetic": "Deep blackboard slate, handwritten chalk derivations, warm amber highlighting, university lecture feel."
    },
    "expedition": {
        "id": "expedition",
        "name": "Frontier Expedition",
        "bg_color": "#171412",
        "grid_color": "rgba(217, 119, 6, 0.15)",
        "primary_color": "#F59E0B",
        "accent_color": "#E5E7EB",
        "secondary_accent": "#EF4444",
        "font_family": "'Cinzel', 'Georgia', serif",
        "border_style": "double 3px #B45309",
        "aesthetic": "Scientific discovery journey, navigational compass rose, parchment topographic contours, hypothesis maps."
    },
    "minimalist": {
        "id": "minimalist",
        "name": "Minimalist Academic",
        "bg_color": "#090A0F",
        "grid_color": "rgba(255, 255, 255, 0.05)",
        "primary_color": "#E2E8F0",
        "accent_color": "#60A5FA",
        "secondary_accent": "#C084FC",
        "font_family": "'Computer Modern', 'Latin Modern Roman', serif",
        "border_style": "solid 1px #334155",
        "aesthetic": "Pristine LaTeX publication style, high typographical contrast, elegant minimalism, distraction-free."
    }
}

# Personas / Lecturers
PERSONAS = {
    "engineer": {
        "id": "engineer",
        "name": "The Curious Systems Engineer",
        "tone": "Hands-on, direct, grounded in physical sensors, actuators, noise, and real-world failure modes.",
        "voice": "en-US-GuyNeural",
        "rate": "+5%",
        "style_prompt": "Ground every abstract variable into a physical intuition. Point out where models break down in reality."
    },
    "theorist": {
        "id": "theorist",
        "name": "The Rigorous Mathematician",
        "tone": "Formal, uncompromising on mathematical beauty, step-by-step proofs, optimality bounds, convergence.",
        "voice": "en-GB-RyanNeural",
        "rate": "+0%",
        "style_prompt": "State assumptions explicitly. Walk through the transformation step-by-step with geometric elegance."
    },
    "visionary": {
        "id": "visionary",
        "name": "The First-Principles Explorer",
        "tone": "Inspirational, starts with the core paradoxical problem, builds intuition before unleashing equations.",
        "voice": "en-US-ChristopherNeural",
        "rate": "+3%",
        "style_prompt": "Ask intriguing questions. Use thought experiments and visual metaphors before introducing mathematical machinery."
    },
    "dynamic_professor": {
        "id": "dynamic_professor",
        "name": "The Dynamic Workshop Master",
        "tone": "Engaging classroom educator who balances derivation with live interactive simulation and projector checks.",
        "voice": "en-US-JennyNeural",
        "rate": "+2%",
        "style_prompt": "Speak directly to students. Highlight key exam & research takeaways, encourage running the demo code."
    }
}
