import io
from fastapi.testclient import TestClient
import main


def test_transcribe(monkeypatch):
    client = TestClient(main.app)

    def fake_call_whisper(data, filename):
        return "transcribed"

    monkeypatch.setattr(main, "call_whisper", fake_call_whisper)

    files = {"file": ("test.mp3", io.BytesIO(b"123"), "audio/mpeg")}
    response = client.post("/transcribe", files=files)
    assert response.status_code == 200
    assert response.json() == {"text": "transcribed"}
