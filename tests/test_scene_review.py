import asyncio
from unittest.mock import patch

import backend.app as app_module
from backend.engines.director import LectureDirectorEngine
from backend.models import (
    LecturePlan,
    LectureScene,
    LectureScene as Scene,
    SceneDraft,
    ProjectState,
    ScientificKnowledgeGraph,
    SourceDocument,
)


def make_scene():
    return LectureScene(
        id="scene_01",
        index=1,
        title="Original title",
        type="derivation",
        narration="Original narration for this scene.",
        duration=20,
        equation="x = y",
        equation_tag="SOURCE",
        citation="p. 1, Eq. 1",
        timestamp_start=0,
        timestamp_end=20,
    )


def test_review_edits_persist_and_invalidate_exports():
    scene = make_scene()
    project = ProjectState(
        id="review1",
        name="Review test",
        topic="Test",
        created_at="now",
        status="ready",
        lecture_plan=LecturePlan(
            project_id="review1",
            title="Test plan",
            topic="Test",
            theme="blueprint",
            persona="engineer",
            target_audience="graduate_students",
            scenes=[scene],
        ),
        video_path="/old-video.mp4",
        slides_path="/old-slides.html",
        latex_path="/old-derivation.tex",
    )

    with (
        patch.object(app_module, "load_project_from_disk", return_value=project),
        patch.object(app_module, "save_project_to_disk"),
    ):
        updated = asyncio.run(app_module.update_scene_review(
            "review1",
            "scene_01",
            app_module.SceneReviewUpdate(
                title="Reviewed title",
                narration="Reviewed narration with additional detail.",
                equation="a = b",
            ),
        ))

    reviewed = updated.lecture_plan.scenes[0]
    assert reviewed.title == "Reviewed title"
    assert reviewed.narration.startswith("Reviewed narration")
    assert reviewed.equation == "a = b"
    assert reviewed.equation_tag == "GENERATED"
    assert reviewed.citation is None
    assert reviewed.audio_file is None
    assert updated.scene_overrides["scene_01"]["equation"] == "a = b"
    assert updated.review_dirty is True
    assert updated.video_path is updated.slides_path is updated.latex_path is None


def test_recompile_reapplies_review_overrides():
    scene = make_scene()
    plan = LecturePlan(
        project_id="review1",
        title="Test plan",
        topic="Test",
        theme="blueprint",
        persona="engineer",
        target_audience="graduate_students",
        scenes=[scene],
    )

    LectureDirectorEngine.apply_scene_overrides(
        plan,
        {"scene_01": {"title": "Saved title", "equation": None, "equation_tag": None}},
    )

    assert plan.scenes[0].title == "Saved title"
    assert plan.scenes[0].equation is None
    assert plan.scenes[0].equation_tag is None


def test_regeneration_replaces_only_requested_scene():
    class FakeRouter:
        def generate(self, task, system, user, schema):
            assert task == "scene_regeneration"
            assert "Current scene to revise" in user
            return SceneDraft(
                title="Revised derivation",
                type="derivation",
                narration="A revised spoken explanation.",
                equation="x = y + 1",
                equation_tag="GENERATED",
                bullet_points=["Updated point one", "Updated point two"],
            )

    original = make_scene()
    doc = SourceDocument(id="doc1", filename="paper.pdf", num_pages=1, raw_text="Source text")
    kg = ScientificKnowledgeGraph(core_problem="A test problem", core_thesis="A test thesis")

    result = LectureDirectorEngine.regenerate_scene(
        original,
        doc,
        kg,
        "blueprint",
        FakeRouter(),
    )

    assert result.id == original.id
    assert result.index == original.index
    assert result.title == "Revised derivation"
    assert result.narration == "A revised spoken explanation."
    assert result.equation_tag == "GENERATED"