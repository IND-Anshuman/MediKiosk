"""Bake TTS audio for every ontology question (plan T3.3, AD-2).

Generates services/tts/audio/<complaint>:<qid>:<lang>.mp3 + manifest.json.
Run at Docker build time (needs network once); runtime playback is offline.

Usage: uv run python infra/scripts/bake_tts.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
AUDIO_DIR = REPO / "services" / "tts" / "audio"
ONTOLOGY_DIR = REPO / "packages" / "ontology" / "data"
I18N_DIR = REPO / "packages" / "i18n" / "locales"

VOICES = {"hi": "hi-IN-SwaraNeural", "en": "en-IN-NeerjaNeural"}


async def _bake_one(text: str, lang: str, out_path: Path) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(text, VOICES[lang])
    await communicate.save(str(out_path))


async def main() -> int:
    from medikiosk_ontology.loader import load_ontology

    onto = load_ontology(ONTOLOGY_DIR)
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, str] = {}
    tasks = []

    # Pre-baked i18n UI strings
    import json

    def fname(key: str) -> str:
        # ':' is illegal in Windows filenames — use '__' on disk
        return key.replace(":", "__") + ".mp3"

    for lang in ("hi", "en"):
        strings = json.loads((I18N_DIR / f"{lang}.json").read_text(encoding="utf-8"))
        for key, text in strings.items():
            out = AUDIO_DIR / fname(f"ui:{key}:{lang}")
            manifest[f"ui:{key}:{lang}"] = out.name
            tasks.append(_bake_one(text, lang, out))

    # Ontology questions
    for cc in onto.chief_complaints.values():
        for q in cc.questions:
            for lang, field in (("hi", "voice_hi"), ("en", "voice_en")):
                out = AUDIO_DIR / fname(f"{cc.name}:{q.id}:{lang}")
                manifest[f"{cc.name}:{q.id}:{lang}"] = out.name
                tasks.append(_bake_one(getattr(q, field), lang, out))

    print(f"Baking {len(tasks)} clips to {AUDIO_DIR} ...")
    await asyncio.gather(*tasks)

    (AUDIO_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    print(f"OK: {len(manifest)} clips + manifest")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))