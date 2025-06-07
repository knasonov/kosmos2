import io
import os
import sys
from fastapi.testclient import TestClient

# Ensure the application module can be imported when tests are run directly
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import main


def test_transcribe(monkeypatch):
    client = TestClient(main.app)

    def fake_call_whisper(data, filename, language=None):
        return "transcribed"

    monkeypatch.setattr(main, "call_whisper", fake_call_whisper)

    files = {"file": ("test.mp3", io.BytesIO(b"123"), "audio/mpeg")}
    response = client.post("/transcribe", files=files)
    assert response.status_code == 200
    assert response.json() == {"text": "transcribed"}


def test_transcribe_language(monkeypatch):
    client = TestClient(main.app)

    captured = {}

    def fake_call_whisper(data, filename, language=None):
        captured['lang'] = language
        return "words"

    monkeypatch.setattr(main, "call_whisper", fake_call_whisper)

    files = {"file": ("test.mp3", io.BytesIO(b"123"), "audio/mpeg")}
    response = client.post("/transcribe?language=en", files=files)
    assert response.status_code == 200
    assert response.json() == {"text": "words"}
    assert captured['lang'] == 'en'
