import os
import json
import uuid
import mimetypes
import urllib.request

from fastapi import FastAPI, UploadFile, File, HTTPException

app = FastAPI()

OPENAI_URL = "https://api.openai.com/v1/audio/transcriptions"


def call_whisper(file_bytes: bytes, filename: str) -> str:
    """Send audio to OpenAI Whisper API and return the transcript."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    boundary = uuid.uuid4().hex
    fields = {
        "model": "whisper-1",
        "response_format": "json",
    }

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

    req = urllib.request.Request(OPENAI_URL, data=body, headers=headers)
    with urllib.request.urlopen(req) as resp:
        data = json.load(resp)
    return data.get("text", "")


@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    """Receive an audio file and return the transcription."""
    data = await file.read()
    await file.close()
    try:
        text = call_whisper(data, file.filename)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"text": text}
