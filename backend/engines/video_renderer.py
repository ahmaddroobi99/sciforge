"""
SciForge Video Compiler & FFmpeg Assembly Engine
Composes individual scenes into high-definition video frames and compiles
the full lecture video with synchronized narration audio using FFmpeg.
"""
import os
import subprocess
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
from PIL import Image, ImageDraw, ImageFont
from backend.config import OUTPUTS_DIR, THEMES, PERSONAS, RESOLUTIONS
from backend.models import LecturePlan, LectureScene

class VideoRendererEngine:
    """
    Renders visual scene cards and invokes FFmpeg to generate final MP4 videos
    at 720p, 1080p, 2K, or 4K resolutions.
    """

    @classmethod
    def render_full_lecture_video(
        cls,
        lecture_plan: LecturePlan,
        project_id: str,
        resolution_key: str = "1080p"
    ) -> Dict[str, Any]:
        """
        End-to-end video compilation pipeline:
        1. Generates 16:9 composite visual frames for each scene
        2. Encodes each scene with its synchronized audio track
        3. Concatenates all scene clips into the master MP4 lecture video
        """
        res_cfg = RESOLUTIONS.get(resolution_key, RESOLUTIONS["1080p"])
        width = res_cfg["width"]
        height = res_cfg["height"]
        bitrate = res_cfg["bitrate"]

        out_dir = OUTPUTS_DIR / project_id
        frames_dir = out_dir / "video_frames"
        clips_dir = out_dir / "scene_clips"
        frames_dir.mkdir(parents=True, exist_ok=True)
        clips_dir.mkdir(parents=True, exist_ok=True)

        theme = THEMES.get(lecture_plan.theme, THEMES["blueprint"])
        persona = PERSONAS.get(lecture_plan.persona, PERSONAS["engineer"])

        scene_clips = []

        for idx, scene in enumerate(lecture_plan.scenes):
            frame_path = frames_dir / f"frame_{scene.index:02d}.png"
            clip_path = clips_dir / f"clip_{scene.index:02d}.mp4"

            # 1. Render Scene Frame Image
            cls._render_scene_frame(
                scene=scene,
                total_scenes=len(lecture_plan.scenes),
                topic=lecture_plan.topic,
                theme=theme,
                persona=persona,
                output_path=frame_path,
                width=width,
                height=height,
                project_id=project_id
            )

            # 2. Locate or create audio track for this scene
            audio_path = out_dir / "audio" / f"scene_{scene.index:02d}.mp3"
            if not audio_path.exists():
                audio_path = out_dir / "audio" / f"scene_{scene.index:02d}.wav"

            # 3. Compile Scene Clip with FFmpeg
            clip_success = cls._encode_scene_clip(
                frame_path=frame_path,
                audio_path=audio_path if audio_path.exists() else None,
                duration=scene.duration,
                output_path=clip_path,
                width=width,
                height=height,
                bitrate=bitrate
            )

            if clip_success and clip_path.exists():
                scene_clips.append(clip_path)

        # 4. Concatenate Scene Clips into Master Video
        final_video_name = f"lecture_{resolution_key}.mp4"
        final_video_path = out_dir / final_video_name

        if scene_clips:
            cls._concatenate_clips(scene_clips, final_video_path)
        else:
            print("[SciForge Video] No scene clips were created.")

        return {
            "success": final_video_path.exists(),
            "video_filename": final_video_name,
            "video_url": f"/outputs/{project_id}/{final_video_name}",
            "video_path": str(final_video_path),
            "resolution": resolution_key,
            "width": width,
            "height": height,
            "total_scenes": len(lecture_plan.scenes),
            "duration": lecture_plan.actual_duration_sec
        }

    @classmethod
    def _render_scene_frame(
        cls,
        scene: LectureScene,
        total_scenes: int,
        topic: str,
        theme: Dict[str, Any],
        persona: Dict[str, Any],
        output_path: Path,
        width: int,
        height: int,
        project_id: str
    ):
        """Draws a themed 16:9 lecture card."""
        bg_hex = theme["bg_color"]
        img = Image.new("RGB", (width, height), color=bg_hex)
        draw = ImageDraw.Draw(img)

        scale = width / 1920.0

        # Draw Blueprint / Laboratory background grid lines
        grid_step = int(60 * scale)
        grid_color = (30, 50, 80) if "blue" in theme["id"] else (25, 35, 45)
        for x in range(0, width, grid_step):
            draw.line([(x, 0), (x, height)], fill=grid_color, width=1)
        for y in range(0, height, grid_step):
            draw.line([(0, y), (width, y)], fill=grid_color, width=1)

        # Border overlay
        margin = int(30 * scale)
        accent_hex = theme.get("primary_color", "#00ADB5")
        draw.rectangle([margin, margin, width - margin, height - margin], outline=accent_hex, width=max(2, int(2 * scale)))

        # Header Badge
        header_text = f"SCIFORGE // {theme['name'].upper()} // {topic.upper()}"
        draw.text((margin + 25, margin + 25), header_text, fill=accent_hex)

        scene_badge = f"SCENE {scene.index:02d} / {total_scenes:02d}  [{scene.type.upper()}]"
        draw.text((width - margin - 350, margin + 25), scene_badge, fill=accent_hex)

        # Title
        title_y = int(100 * scale)
        title_text = scene.title
        draw.text((margin + 25, title_y), title_text, fill="#FFFFFF")

        # Divider line
        div_y = int(160 * scale)
        draw.line([(margin + 25, div_y), (width - margin - 25, div_y)], fill=accent_hex, width=max(1, int(1.5 * scale)))

        # Left Column: Equation / Code / Bullet Points
        left_x = margin + 35
        content_y = int(200 * scale)

        # If equation present
        if scene.equation:
            draw.text((left_x, content_y), "MATHEMATICAL FORMULATION:", fill=accent_hex)
            content_y += int(35 * scale)
            draw.text((left_x + 20, content_y), scene.equation, fill="#FDE047")
            content_y += int(60 * scale)

        # If code present
        if scene.code_snippet:
            draw.text((left_x, content_y), "ALGORITHM IMPLEMENTATION (PYTHON):", fill=accent_hex)
            content_y += int(30 * scale)
            code_lines = scene.code_snippet.split('\n')[:8]
            for cl in code_lines:
                draw.text((left_x + 15, content_y), cl, fill="#E2E8F0")
                content_y += int(25 * scale)
            content_y += int(25 * scale)

        # Bullet points
        draw.text((left_x, content_y), "KEY PRINCIPLES & DYNAMICS:", fill=accent_hex)
        content_y += int(35 * scale)
        for bp in scene.bullet_points:
            draw.text((left_x + 15, content_y), f"• {bp}", fill="#CBD5E1")
            content_y += int(40 * scale)

        # Right Column: Embedded Plot / Figure if available
        plot_path = None
        if scene.figure_url:
            plot_path = OUTPUTS_DIR / project_id / scene.figure_url.split('/')[-1]
        elif scene.type in ["simulation_demo", "plot_verification"]:
            # Auto-check for simulation plot
            for candidate in ["kalman_simulation.png", "attention_matrix.png", "neural_ode_flow.png", "generic_simulation.png"]:
                p = OUTPUTS_DIR / project_id / candidate
                if p.exists():
                    plot_path = p
                    break

        if plot_path and plot_path.exists():
            try:
                fig_img = Image.open(str(plot_path))
                fig_target_w = int(width * 0.42)
                fig_target_h = int(height * 0.58)
                fig_img.thumbnail((fig_target_w, fig_target_h), Image.Resampling.LANCZOS)
                fig_x = width - margin - fig_img.width - 40
                fig_y = int(200 * scale)
                # Draw border around plot
                draw.rectangle([fig_x - 4, fig_y - 4, fig_x + fig_img.width + 4, fig_y + fig_img.height + 4], outline=accent_hex, width=1)
                img.paste(fig_img, (fig_x, fig_y))
            except Exception as e:
                print(f"[SciForge Frame] Error embedding figure: {e}")

        # Footer: Persona, Citation & Progress
        footer_y = height - margin - int(50 * scale)
        persona_text = f"NARRATOR: {persona['name']}  |  TIMECODE: {scene.timestamp_start:.1f}s - {scene.timestamp_end:.1f}s"
        draw.text((margin + 25, footer_y), persona_text, fill="#94A3B8")

        if scene.citation:
            draw.text((width - margin - 350, footer_y), scene.citation, fill=accent_hex)

        # Progress bar at bottom
        p_bar_y = height - margin - 6
        p_width = int((width - 2 * margin) * (scene.index / total_scenes))
        draw.rectangle([margin, p_bar_y, margin + p_width, p_bar_y + 4], fill=accent_hex)

        img.save(str(output_path), "PNG")

    @classmethod
    def _encode_scene_clip(
        cls,
        frame_path: Path,
        audio_path: Optional[Path],
        duration: float,
        output_path: Path,
        width: int,
        height: int,
        bitrate: str
    ) -> bool:
        """Runs FFmpeg to marry frame and audio into an MP4 clip."""
        dur = max(3.0, duration)
        
        if audio_path and audio_path.exists():
            cmd = [
                "ffmpeg", "-y",
                "-loop", "1",
                "-i", str(frame_path),
                "-i", str(audio_path),
                "-c:v", "libx264",
                "-tune", "stillimage",
                "-c:a", "aac",
                "-b:a", "192k",
                "-pix_fmt", "yuv420p",
                "-s", f"{width}x{height}",
                "-b:v", bitrate,
                "-shortest",
                str(output_path)
            ]
        else:
            # Silent fallback clip
            cmd = [
                "ffmpeg", "-y",
                "-loop", "1",
                "-i", str(frame_path),
                "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                "-t", str(dur),
                "-c:v", "libx264",
                "-tune", "stillimage",
                "-c:a", "aac",
                "-b:a", "192k",
                "-pix_fmt", "yuv420p",
                "-s", f"{width}x{height}",
                "-b:v", bitrate,
                "-shortest",
                str(output_path)
            ]

        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=90)
            return res.returncode == 0
        except Exception as e:
            print(f"[SciForge FFmpeg] Error encoding clip {output_path.name}: {e}")
            return False

    @classmethod
    def _concatenate_clips(cls, clips: List[Path], final_output: Path) -> bool:
        """Concatenates all scene MP4 clips using FFmpeg concat demuxer."""
        concat_file = final_output.parent / "clips_manifest.txt"
        with open(concat_file, 'w', encoding='utf-8') as f:
            for c in clips:
                clean_path = str(c).replace('\\', '/')
                f.write(f"file '{clean_path}'\n")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-c", "copy",
            str(final_output)
        ]

        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
            if concat_file.exists():
                concat_file.unlink()
            return res.returncode == 0
        except Exception as e:
            print(f"[SciForge FFmpeg Concat] Error: {e}")
            return False
