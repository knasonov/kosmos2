# kosmos2

This project provides a simple FastAPI backend that uses OpenAI's Whisper API
for speech-to-text. Send an audio file to `/transcribe` and receive the text
transcription.

## Usage

1. Install dependencies:
   ```bash
   pip install fastapi uvicorn
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

4. Visit `http://localhost:8000/` in your browser to use the upload page.
   Select an MP3 or M4A file, watch the progress bar as it uploads, and
   download the resulting transcription when it completes. You can also
   send a POST request with an audio file directly to
   `http://localhost:8000/transcribe`.

## Running tests

Tests require `pytest` and `fastapi`. Execute:

```bash
pytest
```

They patch the Whisper call to avoid real network usage.
