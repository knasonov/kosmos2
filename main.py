import os
import json
import uuid
import mimetypes
import urllib.request
import urllib.error
import socket
import logging
import math
import subprocess
import tempfile
import shutil

# Ensure .m4a files are recognised with a suitable MIME type
mimetypes.add_type("audio/m4a", ".m4a")

import db

from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Form
import re
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse

try:
    import uvicorn
except ImportError:  # pragma: no cover - uvicorn is only needed to run the server
    uvicorn = None

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI()

db.init_db()
db.populate_defaults()

BYTES_PER_MINUTE = 1024 * 1024  # rough estimate


def convert_to_mp3(data: bytes, ext: str) -> bytes:
    """Convert audio bytes of given extension to MP3 using ffmpeg."""
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, "input" + ext)
        output_path = os.path.join(tmpdir, "output.mp3")
        with open(input_path, "wb") as f:
            f.write(data)
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            input_path,
            output_path,
        ]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as exc:
            logger.exception("ffmpeg conversion failed")
            raise RuntimeError("Audio conversion failed") from exc
        with open(output_path, "rb") as f:
            return f.read()


def fix_m4a_faststart(data: bytes) -> bytes:
    """Rewrite an M4A file so the moov atom is at the front.

    If ``ffmpeg`` is not available or fails this function returns the original
    bytes instead of raising an exception. This avoids 500 errors when the
    server does not have ``ffmpeg`` installed.
    """
    if shutil.which("ffmpeg") is None:
        logger.warning("ffmpeg not found; skipping faststart fix")
        return data

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, "input.m4a")
        output_path = os.path.join(tmpdir, "output.m4a")
        with open(input_path, "wb") as f:
            f.write(data)
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            input_path,
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            output_path,
        ]
        try:
            subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            # Log the error but fall back to the original data so that
            # transcription can still proceed.
            logger.exception("ffmpeg faststart failed; returning original data")
            return data
        with open(output_path, "rb") as f:
            return f.read()


def sniff_extension(data: bytes) -> str | None:
    """Guess the audio file extension based on its header."""
    if not data:
        return None
    if data[:3] == b"ID3" or (len(data) > 1 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0):
        return ".mp3"
    if len(data) > 12 and data[4:8] == b"ftyp":
        return ".m4a"
    if data.startswith(b"OggS"):
        return ".ogg"
    return None


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve a minimal HTML page for uploading audio."""
    if request.cookies.get("auth") != "1" or not request.cookies.get("username"):
        return RedirectResponse("/login")
    path = os.path.join(os.path.dirname(__file__), "frontend", "index.html")
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


@app.get("/Test10.mp3")
async def serve_test_audio():
    """Return the bundled Test10.mp3 file for testing."""
    path = os.path.join(os.path.dirname(__file__), "Test10.mp3")
    return FileResponse(path, media_type="audio/mpeg")


@app.get("/login", response_class=HTMLResponse)
async def login_page():
    """Serve the login page."""
    path = os.path.join(os.path.dirname(__file__), "frontend", "login.html")
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    """Authenticate the user and redirect to the upload page."""
    user = db.get_user(username)
    if user and user["password"] == password:
        response = RedirectResponse("/", status_code=303)
        response.set_cookie("auth", "1", httponly=True)
        response.set_cookie("username", username, httponly=True)
        return response
    return HTMLResponse("Invalid credentials", status_code=401)


@app.get("/logout")
async def logout():
    """Clear the auth cookie and go to login page."""
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("auth")
    response.delete_cookie("username")
    return response


@app.get("/remaining")
async def remaining(request: Request):
    """Return minutes remaining for the authenticated user."""
    if request.cookies.get("auth") != "1":
        raise HTTPException(status_code=401, detail="Unauthorized")
    username = request.cookies.get("username")
    if not username:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user = db.get_user(username)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {"minutes": user["minutes_remaining"]}

OPENAI_URL = "https://api.openai.com/v1/audio/transcriptions"


def format_sentences(text: str) -> str:
    """Insert a newline after each sentence."""
    return re.sub(r"(?<=[.!?]) +", "\n", text.strip())


def call_whisper(file_bytes: bytes, filename: str, language: str | None = None) -> str:
    """Send audio to OpenAI Whisper API and return the transcript."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    timeout = int(os.getenv("OPENAI_TIMEOUT", "300"))

    logger.debug(
        "Calling Whisper with file '%s' (%d bytes) (timeout=%d)",
        filename,
        len(file_bytes),
        timeout,
    )

    boundary = uuid.uuid4().hex
    fields = {
        "model": "whisper-1",
        "response_format": "json",
    }
    if language:
        fields["language"] = language

    parts = []
    for name, value in fields.items():
        parts.append(f"--{boundary}")
        parts.append(f'Content-Disposition: form-data; name="{name}"')
        parts.append("")
        parts.append(value)

    mimetype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    parts.append(f"--{boundary}")
    parts.append(
        f'Content-Disposition: form-data; name="file"; filename="{filename}"'
    )
    parts.append(f"Content-Type: {mimetype}")
    parts.append("")

    body_pre = "\r\n".join(parts).encode() + b"\r\n"
    body_post = f"\r\n--{boundary}--\r\n".encode()
    body = body_pre + file_bytes + body_post

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }

    logger.debug("Sending request to %s", OPENAI_URL)
    req = urllib.request.Request(OPENAI_URL, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as exc:  # pragma: no cover - network errors hard to trigger in tests
        try:
            body = exc.read().decode()
            try:
                body_json = json.loads(body)
                body = body_json.get("error", {}).get("message", body)
            except Exception:
                pass
        except Exception:
            body = exc.reason
        logger.exception("Whisper HTTP error %s: %s", exc.code, body)
        raise RuntimeError(f"Whisper API error {exc.code}: {body}") from exc
    except socket.timeout as exc:  # pragma: no cover - network errors hard to trigger in tests
        logger.exception("Whisper request timed out")
        raise RuntimeError(f"Whisper API timed out after {timeout} seconds") from exc
    except Exception as exc:  # pragma: no cover - network errors hard to trigger in tests
        logger.exception("Whisper request failed")
        raise
    logger.debug("Whisper response: %s", data)
    return data.get("text", "")


@app.post("/transcribe")
async def transcribe(
    request: Request, file: UploadFile = File(...), language: str | None = None
):
    """Receive an audio file and return the transcription."""
    if request.cookies.get("auth") != "1":
        raise HTTPException(status_code=401, detail="Unauthorized")
    username = request.cookies.get("username")
    if not username:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user = db.get_user(username)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    data = await file.read()
    await file.close()
    logger.debug("Received %s (%d bytes)", file.filename, len(data))

    ext = os.path.splitext(file.filename or "")[1].lower()
    sniffed_ext = sniff_extension(data)
    sniffed = sniffed_ext or ext

    if sniffed in (".mp3", ".m4a"):
        # Use the sniffed extension if it differs from the provided one
        file.filename = os.path.splitext(file.filename or "audio")[0] + sniffed
        if sniffed == ".m4a":
            try:
                data = fix_m4a_faststart(data)
            except Exception as exc:
                raise HTTPException(status_code=500, detail=str(exc))
    else:
        try:
            data = convert_to_mp3(data, sniffed or ".dat")
            file.filename = os.path.splitext(file.filename or "audio")[0] + ".mp3"
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    minutes = len(data) / BYTES_PER_MINUTE
    if user["minutes_remaining"] < minutes:
        raise HTTPException(status_code=400, detail="Recognition limit exceeded")

    try:
        text = call_whisper(data, file.filename, language)
        text = format_sentences(text)
    except Exception as exc:
        logger.exception("Transcription failed")
        raise HTTPException(status_code=500, detail=str(exc))

    db.deduct_minutes(username, minutes)
    return {"text": text}


if __name__ == "__main__":  # pragma: no cover - server start
    if uvicorn is None:
        raise RuntimeError("uvicorn must be installed to run the server")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("RELOAD", "0") == "1",
    )
