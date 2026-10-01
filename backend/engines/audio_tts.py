"""
SciForge Audio Narration & Speech Synthesis Engine
Generates clear spoken audio for each lecture scene using Edge-TTS neural models,
calculates duration synchronization, and produces aligned subtitles/captions.
"""
import os
import asyncio
import wave
import struct
import math
from pathlib import Path
from typing import Dict, Any, List, Optional
import edge_tts
from backend.config import OUTPUTS_DIR, PERSONAS
from backend.models import LectureScene

class AudioNarrationEngine:
    """
    Handles speech synthesis for each scene in the lecture.
    Matches voice and pacing to the chosen Lecturer Persona.
    """

    @classmethod
    async def synthesize_scene_audio(
        cls,
        scene: LectureScene,
        persona_id: str,
        project_id: str
    ) -> Dict[str, Any]:
        """
        Synthesizes audio for a single lecture scene.
        Returns audio file path, actual duration in seconds, and subtitle timings.
        """
        out_dir = OUTPUTS_DIR / project_id / "audio"
        out_dir.mkdir(parents=True, exist_ok=True)
        audio_filename = f"scene_{scene.index:02d}.mp3"
        audio_path = out_dir / audio_filename

        persona = PERSONAS.get(persona_id, PERSONAS["engineer"])
        voice = persona["voice"]
        rate = persona.get("rate", "+0%")

        clean_text = cls._prepare_narration_text(scene.narration)

        try:
            communicate = edge_tts.Communicate(clean_text, voice, rate=rate)
            await communicate.save(str(audio_path))
            
            # Estimate or calculate duration
            duration = cls._get_audio_duration(audio_path, clean_text)
            
            # Generate word/sentence subtitles
            subtitles = cls._generate_sentence_cues(clean_text, duration)
            
            return {
                "success": True,
                "audio_filename": audio_filename,
                "audio_url": f"/outputs/{project_id}/audio/{audio_filename}",
                "audio_path": str(audio_path),
                "duration": duration,
                "subtitles": subtitles
            }
        except Exception as e:
            # Fallback to offline wave generator if edge-tts network fails
            print(f"[SciForge Audio] EdgeTTS offline/fallback for scene {scene.index}: {e}")
            fallback_filename = f"scene_{scene.index:02d}.wav"
            fallback_path = out_dir / fallback_filename
            est_dur = max(6.0, len(clean_text.split()) * 0.42)
            cls._generate_synth_fallback_audio(clean_text, str(fallback_path), est_dur)

            return {
                "success": True,
                "audio_filename": fallback_filename,
                "audio_url": f"/outputs/{project_id}/audio/{fallback_filename}",
                "audio_path": str(fallback_path),
                "duration": est_dur,
                "subtitles": cls._generate_sentence_cues(clean_text, est_dur),
                "is_fallback": True
            }

    @classmethod
    def _prepare_narration_text(cls, text: str) -> str:
        """Cleans LaTeX math and brackets so speech synthesizer reads naturally."""
        clean = text
        # Convert simple math symbols to spoken words
        clean = clean.replace(r"\hat{x}", "x hat")
        clean = clean.replace(r"\in", "in")
        clean = clean.replace(r"\sim", "distributed as")
        clean = clean.replace(r"\mathcal{N}", "Gaussian normal")
        clean = clean.replace(r"\dot{x}", "x dot")
        clean = clean.replace(r"\int", "integral")
        clean = clean.replace(r"\sum", "sum")
        clean = clean.replace(r"\theta", "theta")
        clean = clean.replace(r"\sigma", "sigma")
        clean = clean.replace(r"\sqrt", "square root of")
        clean = clean.replace(r"\cdot", "times")
        clean = clean.replace(r"\frac", "")
        # Remove remaining LaTeX slashes and braces
        clean = re_replace = "".join([c if c not in r'\{}^_$' else ' ' for c in clean])
        return " ".join(clean.split())

    @classmethod
    def _get_audio_duration(cls, path: Path, text: str) -> float:
        """Estimates duration from file size or word count (avg ~140 wpm)."""
        words = len(text.split())
        approx = max(5.0, words * 0.43)
        if path.exists():
            size_kb = path.stat().st_size / 1024
            # 64kbps MP3 is approx 8KB per second
            if size_kb > 5:
                est = size_kb / 8.0
                return round(est, 2)
        return round(approx, 2)

    @classmethod
    def _generate_sentence_cues(cls, text: str, total_duration: float) -> List[Dict[str, Any]]:
        """Splits text into sentences with start and end timestamps."""
        import re
        sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
        if not sentences:
            sentences = [text]

        total_words = sum(len(s.split()) for s in sentences)
        if total_words == 0:
            total_words = 1

        cues = []
        curr_time = 0.0
        for s in sentences:
            s_words = len(s.split())
            s_dur = (s_words / total_words) * total_duration
            cues.append({
                "text": s,
                "start": round(curr_time, 2),
                "end": round(curr_time + s_dur, 2)
            })
            curr_time += s_dur
        return cues

    @classmethod
    def _generate_synth_fallback_audio(cls, text: str, path: str, duration: float):
        """Generates an offline audible tone-modulated carrier so offline video compiling never fails."""
        sample_rate = 24000
        total_samples = int(sample_rate * duration)
        with wave.open(path, 'w') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            # Gentle soft ambient tone (440Hz warm pad)
            data = bytearray()
            for i in range(total_samples):
                t = float(i) / sample_rate
                # Modulate amplitude with speech cadence
                envelope = (0.5 + 0.5 * math.sin(2 * math.pi * 3.5 * t)) * (0.8 + 0.2 * math.sin(2 * math.pi * 0.5 * t))
                val = int(3000 * envelope * math.sin(2 * math.pi * 220 * t))
                data.extend(struct.pack('<h', val))
            wav_file.writeframes(data)
