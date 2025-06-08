import io
import os
import sys
import tempfile

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Set up temporary database before importing main
TMPDIR = tempfile.TemporaryDirectory()
os.environ["DB_PATH"] = os.path.join(TMPDIR.name, "test.db")

import main
import db


def setup_module(module):
    db.init_db()
    db.add_user("tester", "pw", 1)  # 1 minute limit


def client_with_auth():
    client = TestClient(main.app)
    client.cookies.set("auth", "1")
    client.cookies.set("username", "tester")
    return client


def test_transcribe(monkeypatch):
    client = client_with_auth()

    def fake_call_whisper(data, filename, language=None):
        return "transcribed"

    monkeypatch.setattr(main, "call_whisper", fake_call_whisper)

    files = {"file": ("test.mp3", io.BytesIO(b"123"), "audio/mpeg")}
    response = client.post("/transcribe", files=files)
    assert response.status_code == 200
    assert response.json() == {"text": "transcribed"}


def test_transcribe_language(monkeypatch):
    client = client_with_auth()
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


def test_remaining_endpoint():
    client = client_with_auth()
    db.set_limit("tester", 5)
    response = client.get("/remaining")
    assert response.status_code == 200
    assert response.json() == {"minutes": 5}


def test_transcribe_conversion(monkeypatch):
    client = client_with_auth()
    called = {}

    def fake_convert_to_mp3(data, ext):
        called['convert'] = True
        return b'mp3data'

    def fake_call_whisper(data, filename, language=None):
        assert data == b'mp3data'
        return 'ok'

    monkeypatch.setattr(main, 'convert_to_mp3', fake_convert_to_mp3)
    monkeypatch.setattr(main, 'call_whisper', fake_call_whisper)

    files = {"file": ("test.ogg", io.BytesIO(b"123"), "audio/ogg")}
    response = client.post("/transcribe", files=files)
    assert response.status_code == 200
    assert response.json() == {"text": "ok"}
    assert called.get('convert')


def test_sniff_m4a_skips_conversion(monkeypatch):
    client = client_with_auth()
    called = {}

    def fake_convert_to_mp3(data, ext):
        called['convert'] = True
        return b''

    def fake_call_whisper(data, filename, language=None):
        called['whisper'] = data
        return 'done'

    def fake_fix(data):
        called['fix'] = True
        return data

    monkeypatch.setattr(main, 'convert_to_mp3', fake_convert_to_mp3)
    monkeypatch.setattr(main, 'fix_m4a_faststart', fake_fix)
    monkeypatch.setattr(main, 'call_whisper', fake_call_whisper)

    # Minimal m4a/MP4 header: size + 'ftyp' marker
    m4a_data = b"\x00\x00\x00\x18ftypm4a "
    files = {"file": ("voice.ogg", io.BytesIO(m4a_data + b"123"), "audio/ogg")}
    response = client.post("/transcribe", files=files)
    assert response.status_code == 200
    assert response.json() == {"text": "done"}
    assert 'convert' not in called
    assert called.get('fix')


def test_fix_m4a_called(monkeypatch):
    client = client_with_auth()
    called = {}

    def fake_fix(data):
        called['fix'] = True
        return b'fixed'

    def fake_call_whisper(data, filename, language=None):
        called['data'] = data
        return 'ok'

    monkeypatch.setattr(main, 'fix_m4a_faststart', fake_fix)
    monkeypatch.setattr(main, 'call_whisper', fake_call_whisper)

    m4a_data = b"\x00\x00\x00\x18ftypm4a " + b'123'
    files = {"file": ("voice.m4a", io.BytesIO(m4a_data), "audio/mp4")}
    response = client.post("/transcribe", files=files)
    assert response.status_code == 200
    assert response.json() == {"text": "ok"}
    assert called.get('fix')
    assert called['data'] == b'fixed'


def test_call_whisper_sets_m4a_mime(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test')
    captured = {}

    def fake_urlopen(req):
        captured['data'] = req.data
        class Resp(io.BytesIO):
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                pass
        return Resp(b'{"text": "hi"}')

    monkeypatch.setattr(main.urllib.request, 'urlopen', fake_urlopen)

    result = main.call_whisper(b'data', 'voice.m4a')
    assert result == 'hi'
    assert b'Content-Type: audio/m4a' in captured['data']
