"""
LLM layer tests - no network, no API spend.
Run: python tests/test_llm.py   (or: python -m pytest tests/test_llm.py)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json

import anthropic
import httpx

from backend.engines import topics
from backend.engines.director import LectureDirectorEngine
from backend.engines.ingestion import PaperIngestionEngine
from backend.engines.knowledge import ScientificKnowledgeEngine
from backend.engines.llm import LLMError, LLMRouter
from backend.engines.llm.anthropic_provider import AnthropicProvider
from backend.engines.llm.openai_compat import OpenAICompatibleProvider
from backend.models import (
    ConceptEdge, ConceptNode, LecturePlanDraft, SceneDraft, ScientificKnowledgeGraph,
)

NOTES = """# Kalman Filter Notes
--- Page 1 ---
Dynamics: $x_k = A x_{k-1} + w_k$
--- Page 2 ---
Gain: $K = P H^T (H P H^T + R)^{-1}$
"""
SIM = {
    "type": "kalman_state_estimation",
    "plot_filename": "kalman_simulation.png",
    "metrics": {"error_reduction_pct": 33.2},
    "runnable_python_code": "import numpy as np\n\ndef run_kalman_filter(z):\n    return z\n",
}


class FakeProvider:
    """Returns canned objects (or raises) in call order."""
    name, model = "fake", "fake-1"

    def __init__(self, *outputs):
        self.outputs = list(outputs)
        self.calls = []

    def generate(self, *, system, user, schema, max_tokens):
        self.calls.append({"system": system, "user": user, "schema": schema})
        out = self.outputs.pop(0)
        if isinstance(out, Exception):
            raise out
        return out


def _doc():
    return PaperIngestionEngine.ingest_text(NOTES, "notes.md", "doc_test")


def _kg():
    return ScientificKnowledgeGraph(
        nodes=[ConceptNode(id="node_1", name="Problem", type="problem", description="Noisy sensors")],
        core_problem="Estimate state from noisy sensors.",
        core_thesis="Fuse model and measurement optimally.",
    )


def _draft(*scenes):
    return LecturePlanDraft(
        title="Kalman, From Scratch", scenes=list(scenes), key_takeaways=["Fuse model and data"],
        youtube_title="Kalman Filter in 10 Minutes", youtube_tags=["kalman", "estimation"],
    )


def _scene(type_, **kw):
    base = dict(title=f"A {type_} scene", type=type_, narration="word " * 50, bullet_points=["One point"])
    base.update(kw)
    return SceneDraft(**base)


# ---------------- topic classifier ----------------

def test_classify_topic_uses_whole_words():
    assert topics.classify_topic("Kalman Filtering & Optimal State Estimation") == topics.KALMAN
    assert topics.classify_topic("Scaled Dot-Product Attention & Transformers") == topics.ATTENTION
    assert topics.classify_topic("Continuous-Depth Neural ODEs") == topics.NEURAL_ODE
    # These all hit a template under the old substring checks.
    assert topics.classify_topic("Diffusion Models") == topics.GENERIC           # "m-ode-l"
    assert topics.classify_topic("Bloom Filter Data Structures") == topics.GENERIC
    assert topics.classify_topic("Solid State Batteries") == topics.GENERIC
    assert topics.classify_topic("Encoder design") == topics.GENERIC             # "enc-ode-r"


# ---------------- router ----------------

def test_router_without_provider_returns_none():
    router = LLMRouter(reason="no key")
    assert router.generate("t", system="s", user="u", schema=LecturePlanDraft) is None
    assert router.label == "templates" and router.describe()["reason"] == "no key"


def test_router_swallows_provider_errors():
    router = LLMRouter(FakeProvider(LLMError("HTTP 403: out of credits")))
    assert router.generate("lecture_plan", system="s", user="u", schema=LecturePlanDraft) is None
    assert "out of credits" in router.last_error


def test_schemas_hide_internal_fields_from_llm():
    assert "built_by" not in ScientificKnowledgeGraph.model_json_schema()["properties"]


# ---------------- knowledge engine ----------------

def test_knowledge_graph_from_llm_is_sanitised():
    kg = ScientificKnowledgeGraph(
        nodes=[
            ConceptNode(id="node_1", name="Problem", type="problem", description="d", source_page=1),
            ConceptNode(id="node_2", name="Gain", type="equation", description="d", source_page=99, formula="K"),
        ],
        edges=[
            ConceptEdge(source="node_1", target="node_2", relationship="formalizes"),
            ConceptEdge(source="node_2", target="node_404", relationship="produces"),
        ],
        core_problem="Estimate state.", core_thesis="Fuse.",
    )
    router = LLMRouter(FakeProvider(kg))
    out = ScientificKnowledgeEngine.build_knowledge_graph(_doc(), "Kalman Filter", router)
    assert out.built_by == "fake:fake-1"
    assert [(e.source, e.target) for e in out.edges] == [("node_1", "node_2")]  # dangling edge dropped
    assert out.nodes[1].source_page is None  # page 99 does not exist
    assert "<paper>" in router.provider.calls[0]["user"]


def test_knowledge_graph_falls_back_to_template():
    router = LLMRouter(FakeProvider(LLMError("boom")))
    out = ScientificKnowledgeEngine.build_knowledge_graph(_doc(), "Kalman Filter", router)
    assert out.built_by == "template" and len(out.nodes) > 2


# ---------------- director ----------------

def test_director_converts_llm_draft():
    draft = _draft(
        _scene("hook_problem"),
        _scene("mathematical_formulation", equation="$x_k = A x_{k-1}$", equation_tag="SOURCE", citation="p. 1, Eq. 1"),
        _scene("derivation", equation="K = P H^T S^{-1}", equation_tag="SOURCE", citation="Section 3"),
        _scene("simulation_demo"),
        _scene("plot_verification"),
        _scene("takeaway"),
    )
    router = LLMRouter(FakeProvider(draft))
    plan = LectureDirectorEngine.compile_lecture_plan(
        _doc(), _kg(), "Kalman Filter", target_duration=300, project_id="t", llm=router, sim_output=SIM)
    s = plan.scenes
    assert plan.planned_by == "fake:fake-1" and plan.title == "Kalman, From Scratch"
    assert plan.youtube_metadata["title"] == "Kalman Filter in 10 Minutes"
    assert [x.index for x in s] == [1, 2, 3, 4, 5, 6] and s[0].id == "scene_01"
    assert s[1].equation == "x_k = A x_{k-1}"                       # $ delimiters stripped
    assert s[1].equation_tag == "SOURCE" and s[1].citation == "p. 1, Eq. 1 | SOURCE"
    assert s[2].equation_tag == "GENERATED"                         # SOURCE claim without a page
    assert s[3].code_snippet.startswith("def run_kalman_filter")    # real executed code, not LLM code
    assert s[4].figure_url == "kalman_simulation.png"
    assert s[5].visual_spec.layout == "conclusion"
    assert s[0].duration == 21.0 and plan.actual_duration_sec == 126.0  # 50 words * 0.42 s
    user_msg = router.provider.calls[0]["user"]
    assert "33.2" in user_msg and "SIMULATION AVAILABLE" in user_msg


def test_director_drops_simulation_scenes_for_generic_topics():
    draft = _draft(_scene("hook_problem"), _scene("plot_verification"), _scene("takeaway"))
    router = LLMRouter(FakeProvider(draft))
    plan = LectureDirectorEngine.compile_lecture_plan(
        _doc(), _kg(), "Diffusion Models", project_id="t", llm=router, sim_output=SIM)
    assert plan.scenes[1].type == "engineering_application"
    assert plan.scenes[1].figure_url is None
    assert "NO SIMULATION" in router.provider.calls[0]["user"]


def test_director_falls_back_on_thin_plan():
    router = LLMRouter(FakeProvider(_draft(_scene("hook_problem"), _scene("takeaway"))))
    plan = LectureDirectorEngine.compile_lecture_plan(_doc(), _kg(), "Kalman Filter", project_id="t", llm=router)
    assert plan.planned_by == "template" and "only 2 scenes" in router.last_error


# ---------------- Anthropic provider (mocked HTTP stream) ----------------

def _sse(events):
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events).encode()


def _claude_stream(*blocks, stop_reason="end_turn"):
    """blocks: text strings, or dicts for non-text content blocks (e.g. a fallback switch point)."""
    message = {"id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5", "content": [],
               "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": 10, "output_tokens": 1}}
    events = [{"type": "message_start", "message": message}]
    for i, block in enumerate(blocks):
        if isinstance(block, dict):
            events.append({"type": "content_block_start", "index": i, "content_block": block})
        else:
            events += [
                {"type": "content_block_start", "index": i, "content_block": {"type": "text", "text": ""}},
                {"type": "content_block_delta", "index": i, "delta": {"type": "text_delta", "text": block}},
            ]
        events.append({"type": "content_block_stop", "index": i})
    events += [
        {"type": "message_delta", "delta": {"stop_reason": stop_reason, "stop_sequence": None}, "usage": {"output_tokens": 50}},
        {"type": "message_stop"},
    ]
    return _sse(events)


def _anthropic_provider(body_bytes, seen):
    def handler(request):
        seen["body"] = json.loads(request.content)
        seen["beta"] = request.headers.get("anthropic-beta", "")
        return httpx.Response(200, content=body_bytes, headers={"content-type": "text/event-stream"})
    client = anthropic.Anthropic(api_key="test", http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    return AnthropicProvider(model="claude-opus-5", effort="high", client=client)


def test_anthropic_provider_request_and_parse():
    seen = {}
    kg_json = _kg().model_dump_json(exclude={"built_by"})
    provider = _anthropic_provider(_claude_stream(kg_json), seen)
    out = provider.generate(system="sys", user="paper", schema=ScientificKnowledgeGraph, max_tokens=32000)
    assert out.core_problem == "Estimate state from noisy sensors."
    body = seen["body"]
    assert body["model"] == "claude-opus-5" and body["stream"] is True and body["max_tokens"] == 32000
    assert body["thinking"] == {"type": "adaptive"}
    assert body["output_config"]["effort"] == "high"
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert body["fallbacks"] == [{"model": "claude-opus-4-8"}]
    assert "server-side-fallback-2026-06-01" in seen["beta"]


def _expect_llm_error(provider, fragment):
    try:
        provider.generate(system="s", user="u", schema=ScientificKnowledgeGraph, max_tokens=1000)
    except LLMError as e:
        assert fragment in str(e), str(e)
    else:
        raise AssertionError(f"expected LLMError containing {fragment!r}")


def test_anthropic_provider_reports_refusal_not_json_error():
    _expect_llm_error(_anthropic_provider(_claude_stream('{"nod', stop_reason="refusal"), {}), "declined")


def test_anthropic_provider_reports_truncation_not_json_error():
    _expect_llm_error(_anthropic_provider(_claude_stream('{"nodes": [', stop_reason="max_tokens"), {}), "truncated")


def test_anthropic_provider_uses_text_after_fallback_switch():
    good = _kg().model_dump_json(exclude={"built_by"})
    switch = {"type": "fallback", "from": {"model": "claude-opus-5"}, "to": {"model": "claude-opus-4-8"}}
    provider = _anthropic_provider(_claude_stream('{"nodes": [{"id', switch, good), {})
    out = provider.generate(system="s", user="u", schema=ScientificKnowledgeGraph, max_tokens=1000)
    assert out.core_problem == "Estimate state from noisy sensors."


# ---------------- OpenAI-compatible provider (xAI / OpenAI / Ollama) ----------------

def _compat_provider(name, responses, seen):
    def handler(request):
        seen.append(json.loads(request.content))
        status, payload = responses.pop(0)
        return httpx.Response(status, json=payload)
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return OpenAICompatibleProvider(name, "https://api.example/v1", "key", "m-1", http=http)


def _completion(content):
    return {"choices": [{"message": {"content": content}, "finish_reason": "stop"}]}


def test_compat_provider_repairs_invalid_json_once():
    seen = []
    good = _kg().model_dump_json(exclude={"built_by"})
    provider = _compat_provider("xai", [(200, _completion('{"nodes": "oops"}')), (200, _completion(f"```json\n{good}\n```"))], seen)
    out = provider.generate(system="s", user="u", schema=ScientificKnowledgeGraph, max_tokens=500)
    assert out.core_thesis == "Fuse model and measurement optimally."
    assert len(seen) == 2 and "failed validation" in seen[1]["messages"][-1]["content"]
    assert seen[0]["response_format"] == {"type": "json_object"} and seen[0]["max_tokens"] == 500


def test_compat_provider_http_error_message():
    seen = []
    provider = _compat_provider("openai", [(403, {"error": {"message": "no credits"}})], seen)
    try:
        provider.generate(system="s", user="u", schema=ScientificKnowledgeGraph, max_tokens=500)
    except LLMError as e:
        assert "HTTP 403" in str(e) and "no credits" in str(e)
    else:
        raise AssertionError("HTTP error did not raise")
    assert "max_completion_tokens" in seen[0]


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for name, fn in tests:
        fn()
        print(f"[PASS] {name}")
    print(f"\n[SUCCESS] {len(tests)} LLM-layer tests passed")
