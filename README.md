# kosmos2

This project provides a simple FastAPI backend that uses OpenAI's Whisper API
for speech-to-text. Send an audio file to `/transcribe` and receive the text
transcription.

## Usage

1. Install dependencies (and ensure `ffmpeg` is available on your system):
   ```bash
   pip install fastapi uvicorn ffmpeg-python
   ```
   The `openai` package is not required because the API is called directly.

2. Set the API key environment variable:
   ```bash
   export OPENAI_API_KEY=your-key-here
   ```

3. Run the server:
   ```bash
   uvicorn main:app --reload
   ```
   You can also simply execute the `main.py` file which starts Uvicorn
   programmatically:
   ```bash
   python main.py
   ```

4. Open `http://localhost:8000/login` in your browser and log in with the
   username **kosmos** and password **kosmos**. After authenticating you will
  be redirected to `http://localhost:8000/` where you can upload an MP3 or
  M4A file. Other audio types such as OGG will be automatically converted to
  MP3 on the server before processing. Large uploads are automatically split
  into ten minute chunks so they can be processed by Whisper. The progress bar
  updates after each chunk is transcribed and the text appears incrementally.
  You can also send
   a POST request with an audio file directly to
   `http://localhost:8000/transcribe`.

## Running tests

Tests require `pytest` and `fastapi`. Execute:

```bash
pytest
```

They patch the Whisper call to avoid real network usage.
