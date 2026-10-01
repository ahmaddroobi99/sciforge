"""
SciForge Topic Classifier
Single source of truth for mapping a free-text topic onto the built-in template families.
Used by the knowledge, simulation and director engines so their choices always agree.
"""
import re

KALMAN = "kalman"
ATTENTION = "attention"
NEURAL_ODE = "neural_ode"
GENERIC = "generic"

# Whole-word patterns, checked in order. Substring checks sent "Diffusion Models" to the
# Neural ODE template ("m-ode-l") and anything containing "state" or "filter" to Kalman.
_RULES = [
    (KALMAN, re.compile(r"\bkalman\b|\bstate[- ]estimation\b", re.IGNORECASE)),
    (ATTENTION, re.compile(r"\battention\b|\btransformers?\b", re.IGNORECASE)),
    (NEURAL_ODE, re.compile(r"\bneural odes?\b|\bodes?\b|\bordinary differential equations?\b", re.IGNORECASE)),
]


def classify_topic(topic: str) -> str:
    """Returns one of KALMAN, ATTENTION, NEURAL_ODE or GENERIC."""
    for kind, pattern in _RULES:
        if pattern.search(topic or ""):
            return kind
    return GENERIC
