"""T3.3: TTS service — build-time pre-baked question audio (AD-2).

Key guarantee: EVERY ontology question has a pre-baked mp3, so the kiosk
"engages within 1 second" is literal — playback is a static-file fetch.
The bake script (infra/scripts/bake_tts.py) generates services/tts/audio;
manifest coverage is verified here (CI fails if a question lacks audio).
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

AUDIO_DIR = Path("services/tts/audio")


@pytest.fixture()
def c():
    from medikiosk_tts.main import app

    return TestClient(app)


def test_healthz(c):
    assert c.get("/healthz").status_code == 200


def test_manifest_covers_all_ontology_questions(tmp_path, monkeypatch):
    """Manifest keys must cover every question id in every complaint + AYUSH."""
    from medikiosk_ontology.loader import load_ontology

    onto = load_ontology(Path("packages/ontology/data"))
    monkeypatch.setenv("TTS_AUDIO_DIR", str(AUDIO_DIR))

    manifest_path = AUDIO_DIR / "manifest.json"
    if not manifest_path.exists():  # bake not yet run in this checkout
        pytest.skip("run infra/scripts/bake_tts.py to generate audio manifest")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    missing = []
    for cc in onto.chief_complaints.values():
        for q in cc.questions:
            for lang in ("hi", "en"):
                key = f"{cc.name}:{q.id}:{lang}"
                if key not in manifest:
                    missing.append(key)
    assert not missing, f"pre-baked TTS missing: {missing}"


def test_serve_baked_audio(c):
    manifest_path = AUDIO_DIR / "manifest.json"
    if not manifest_path.exists():
        pytest.skip("bake not run")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    some_key = next(iter(manifest))
    lang, qkey = some_key.split(":", 2)[1], some_key
    r = c.get(f"/tts/{some_key}.mp3")
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/mpeg"